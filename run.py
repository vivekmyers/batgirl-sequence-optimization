import os, argparse
import dna.env
import seaborn as sns
import matplotlib.pyplot as plt
import importlib
import numpy as np
sns.set_style('darkgrid')


def make_plot(title, yaxis, data, loc):
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


if __name__ == '__main__':

    # Parse environment parameters
    parser = argparse.ArgumentParser(description='run flags')
    parser.add_argument('--agents', nargs='+', type=str, help='agent classes to use', required=True)
    parser.add_argument('--batch', type=int, default=1000, help='batch size')
    parser.add_argument('--cutoff', type=int, default=None, help='max number of batches to run')
    parser.add_argument('--pretrain', action='store_true', help='pretrain on azimuth data')
    parser.add_argument('--validation', type=float, default=0.2, help='validation data portion')
    parser.add_argument('--collect', action='store_true', help='collect into joint graphs')
    parser.add_argument('--noplot', action='store_true', help='do not save individual graphs')

    args = parser.parse_args()

    env = dna.env.GuideEnv(batch=args.batch, 
            initial='data/Azimuth/azimuth_preds.csv.gz' if args.pretrain else None, 
            validation=args.validation, files=[f'data/DeepCRISPR/{f}' 
                for f in os.listdir('data/DeepCRISPR') if f.endswith('.csv')])

    # Load agent modules
    files = [f for f in os.listdir('agents') if f.endswith('.py')]
    mods = {}

    for f in files :
        mod = importlib.import_module('agents.' + f[:-3])
        mods.update(mod.__dict__)

    # Run agents
    collected = []

    for agent in args.agents:
        print()
        print(f'Running {agent}...')
        corrs, top10 = env.run(eval(agent, mods, {}), args.cutoff)
        print(f'Saving to results/{agent}...')
        try: os.mkdir(f'results/{agent}')
        except OSError: pass
        if not args.noplot:
            make_plot(f'{agent}, batch={args.batch}', 'Correlation', [(corrs, None)], 
                        f'{agent}/{agent}-batch={args.batch}-corr')
            make_plot(f'{agent}, batch={args.batch}', 'Top 10 Average', [(top10, None)], 
                        f'{agent}/{agent}-batch={args.batch}-top10')
        collected.append((agent, corrs, top10))
        np.save(f'results/{agent}/{agent}-batch={args.batch}.npy', dict(
            agent=agent,
            batch=args.batch,
            pretrain=args.pretrain,
            validation=args.validation,
            correlations=corrs,
            top10=top10))
        print()

    # If collecting, make joint graph
    if args.collect and len(args.agents) > 1:
        loc = ",".join(args.agents)
        try: os.mkdir(f'results/{loc}')
        except OSError: pass
        make_plot(f'Agent Performance, batch={args.batch}', 'Correlation', 
                    [(datum, agent) for agent, datum, _ in collected],
                    f'{loc}/{loc}-batch={args.batch}-corr')
        make_plot(f'Agent Performance, batch={args.batch}', 'Top 10 Average', 
                    [(datum, agent) for agent, _, datum in collected],
                    f'{loc}/{loc}-batch={args.batch}-top10')

