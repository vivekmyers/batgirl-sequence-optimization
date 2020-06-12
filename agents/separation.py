import numpy as np
from random import *
import agents.random
from models.auto_cnn import CNN
from models.featurizer import Featurizer
import utils.mcmc


def SeparationAgent(epochs=30, initial_epochs=None, k=1., dim=5):
    '''Constructs agent with CNN to predict sequence values that trains with each observation.
    Greedily selects kN sequences with best predicions, then downsamples to the N most separated.
    '''
    if initial_epochs is None:
        initial_epochs = epochs // 4

    class Agent(agents.random.RandomAgent(epochs, initial_epochs)):

        def __init__(self, *args):
            super().__init__(*args)
            self.model = Featurizer(self.encode, shape=self.shape, dim=dim)
            if len(self.prior):
                self.model.fit(*zip(*self.prior.items()), epochs=initial_epochs)
        
        def act(self, seqs):
            selections = np.array(list(zip(*sorted(zip(self.model.predict(seqs), seqs))[-int(k * self.batch):]))[1])
            idx = utils.mcmc.mcmc(self.batch, self.model.embed(selections),
                            iters=1000) if k > 1. else np.arange(len(selections))
            return selections[idx]

        def observe(self, data):
            super().observe(data)
            self.model.fit(*zip(*self.seen.items()), epochs=epochs) 
        
    return Agent
