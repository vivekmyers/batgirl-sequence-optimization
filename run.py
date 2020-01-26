import matplotlib
matplotlib.use('Agg')
import os, argparse
import seaborn as sns
import matplotlib.pyplot as plt
import importlib
import traceback
import numpy as np
import multiprocessing
import torch
import signal
import environment.env
import random
sns.set_style('darkgrid')
signal.signal(signal.SIGINT, lambda x, y: exit(1))
np.seterr(divide='ignore', invalid='ignore')


def make_plot(title, yaxis, data, loc):
    '''Make a plot of [(Datum, Label)] data and save to given location in results.'''
    plt.figure()
    plt.title(title)
    plt.xlabel('Batch')
    plt.ylabel(yaxis)
    for datum, label in data:  
        if label is None:
            plt.plot(datum)
        else:
            plt.plot(datum, label=label)
    if any([label is not None for _, label in data]):
        plt.legend()
    plt.savefig(f'results/{loc}.png')


def run_agent(arg):
    '''Run agent in provided environment, with given arguments.'''
    env, agent, pos, args, seed, loc = arg
    if not torch.cuda.is_available() and pos == 0: print('CUDA not available')
    name = agent + ' ' * (max(map(len, args.agents)) - len(agent))
    try:
        random.seed(seed[1])
        np.random.seed(seed[1])
        torch.manual_seed(seed[1])
        if torch.cuda.is_available():
            with torch.cuda.device(pos % torch.cuda.device_count()):
                corrs, reward, regret, time = env.run(eval(agent, mods, {}), args.cutoff, name, pos)
        else:
            corrs, reward, regret, time = env.run(eval(agent, mods, {}), args.cutoff, name, pos)
    except: 
        traceback.print_exc()
        return None
    data = dict(
        env=args.env,
        agent=agent,
        batch=args.batch,
        pretrain=args.pretrain,
        validation=args.validation,
        metric=args.metric,
        correlations=corrs,
        reward=reward,
        regret=regret,
        time=time,
        seed=seed)
    existing = []
    try:
        existing = list(np.load(f'results/{loc}/results.npy', allow_pickle=True))
    except:
        pass
    existing.append(data)
    np.save(f'results/{loc}/results.npy', existing)
    return data


if __name__ == '__main__':

    # Parse environment parameters
    parser = argparse.ArgumentParser(description='run flags')
    parser.add_argument('--agents', nargs='+', type=str, help='agent classes to use', required=True)
    parser.add_argument('--batch', type=int, default=1000, help='batch size')
    parser.add_argument('--cutoff', type=int, default=None, help='max number of batches to run')
    parser.add_argument('--pretrain', action='store_true', help='pretrain on azimuth data')
    parser.add_argument('--validation', type=float, default=0.2, help='validation data portion')
    parser.add_argument('--nocorr', action='store_true', help='do not compute prediction correlations')
    parser.add_argument('--metric', type=float, default=0.2, help='percent of sequences used for metric computation')
    parser.add_argument('--env', type=str, default='GuideEnv', help='environment to run agents')
    parser.add_argument('--reps', type=int, default=1, help='number of trials to average')
    parser.add_argument('--name', type=str, default=None, help='output directory')
    parser.add_argument('--cpus', type=int, default=multiprocessing.cpu_count(), help='number of agents to run concurrently')
    parser.add_argument('--seed', type=int, default=None, help='random seed')


    args = parser.parse_args()

    if args.seed is not None:
        seed = args.seed
    else:
        seed = random.randint(0, (1 << 32) - 1)
    random.seed(seed)

    env = eval(f'{args.env}', environment.env.__dict__, {})(batch=args.batch, validation=args.validation, pretrain=args.pretrain, nocorr=args.nocorr, metric=args.metric)

    # Load agent modules
    files = [f for f in os.listdir('agents') if f.endswith('.py')]
    mods = {}

    for f in files :
        mod = importlib.import_module('agents.' + f[:-3])
        mods.update(mod.__dict__)

    # Run agents
    loc = ",".join(args.agents) if args.name is None else args.name
    assert len(loc) > 0
    try: os.remove(f'results/{loc}/results.npy')
    except OSError: pass
    thunks = [(env, agent, i * args.reps + j, args, 
                (seed, random.randint(0, (1 << 32) - 1)), loc)
                            for i, agent in enumerate(args.agents)
                            for j in range(args.reps)]
    random.shuffle(thunks)
    pool = multiprocessing.Pool(processes=args.cpus, maxtasksperchild=1)
    collected = [x for x in pool.map(run_agent, thunks, chunksize=1) if x is not None]

    # Write output
    try: os.mkdir(f'results/{loc}')
    except OSError: pass
    np.save(f'results/{loc}/results.npy', collected)

    def process_data(attr, title):
        global collected
        results = {}
        for agent in [x['agent'] for x in collected]:
            data = [x[attr] for x in collected if x['agent'] == agent]
            n = max(map(len, data))
            def pad(x, n):
                x = list(x)
                while len(x) < n:
                    x.append(np.nan)
                return x
            results[agent] = np.array([pad(x, n) for x in data]).mean(axis=0)
        make_plot(f'batch={args.batch}, env={args.env}, reps={args.reps}', title, 
                    [(datum, agent) for agent, datum in results.items()],
                    f'{loc}/{attr}')

    if not args.nocorr:
        process_data('correlations', 'Correlation')
    process_data('reward', 'Reward')
    process_data('regret', 'Regret')
    process_data('time', 'Time')

