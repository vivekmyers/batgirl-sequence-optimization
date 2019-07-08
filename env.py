import numpy as np
import pandas as pd
from tqdm import tqdm
from random import *

class GuideEnv:
    '''Stores labeled sequences, reserving some for validation, and runs agents on them.'''

    def __init__(self, files, batch=1000, validation=0.2, initial=0.0):
        '''Initialize environment.
        files: csv files to read data from
        batch: number of sequences selected per action
        validation: portion of sequences to save for validation
        initial: portion of sequences given to each agent on construction
        '''
        assert 0 <= validation < 1
        assert 0 <= initial < 1
        dfs = list(map(pd.read_csv, files))
        data = [(strand + seq, score) for df in dfs
            for _, strand, seq, score in 
            df[['Strand', 'sgRNA', 'Normalized efficacy']].itertuples()]
        self.len = len(data[0][0])
        shuffle(data)
        r = int(validation * len(data))
        self.env = data[r:]
        self.val = tuple(np.array(x) for x in zip(*data[:r]))
        # start agent with some portion of initial sequences
        r = int(initial * len(self.env))
        self.prior = dict(self.env[:r])
        self.env = dict(self.env[r:])
        self.batch = batch
        assert batch < len(self.env)
        
    def run(self, Agent, cutoff=None):
        '''Run agent, getting batch-sized list of actions (sequences) to try,
        and calling observe with the labeled sequences until all sequences
        have been tried (or the batch number specified by the cutoff parameter
        has been reached). Returns the validation performance after each batch
        (measured using Pearson correlation with the agent's predict method 
        on validation data), as well as the average performance of the best 
        10 guides the agent has seen after each batch.
        '''
        data = self.env.copy()
        pbar = tqdm(total=min(len(data) // self.batch * self.batch, (cutoff - 1) * self.batch) + len(self.prior))
        agent = Agent(self.prior.copy(), self.len, self.batch)
        seen = list(self.prior.values())
        corrs = []
        top10 = []
        predicted = np.array(agent.predict(self.val[0].copy()))
        corrs.append(np.corrcoef(predicted, self.val[1])[0, 1])
        top10.append(np.array(sorted(seen))[-10:].mean())
        pbar.update(len(self.prior))
        while len(data) > self.batch and (cutoff is None or len(corrs) < cutoff):
            sampled = agent.act(list(data.keys()))
            agent.observe({seq: data[seq] for seq in sampled})
            for seq in sampled:
                seen.append(data[seq])
                del data[seq]
            predicted = np.array(agent.predict(self.val[0].copy()))
            corrs.append(np.corrcoef(predicted, self.val[1])[0, 1])
            top10.append(np.array(sorted(seen))[-10:].mean())
            pbar.update(self.batch)
        pbar.close()
        return np.array(corrs), np.array(top10)
    
