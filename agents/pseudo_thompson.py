import numpy as np
from random import *
from models.uncertain import UncertainCNN
from models.cnn import CNN
import agents.base
from torch.distributions import Normal
from torch import tensor

def PseudoThompsonAgent(epochs=50, initial_epochs=None):
    '''Constructs agent with a CNN trained to predict gaussians with uncertainty, 
    using Thompson sampling with the network's uncertainty to select batches, and 
    refitting the model to update the predicted distributions between batches.
    '''
    if initial_epochs is None:
        initial_epochs = epochs // 4

    class Agent(agents.base.BaseAgent):

        def __init__(self, *args):
            super().__init__(*args)
            self.model = UncertainCNN(encoder=self.encode, shape=self.shape)
            if len(self.prior):
                self.model.fit(*zip(*self.prior.items()), epochs=initial_epochs, minibatch=100)
            
        def act(self, seqs):
            mu, sigma = map(tensor, self.model.predict(seqs))
            sampled = Normal(mu, sigma).sample().numpy()
            return [*zip(*sorted(zip(sampled, seqs))[-self.batch:])][1]

        def observe(self, data):
            super().observe(data)
            self.model.fit(*zip(*self.seen.items()), epochs=epochs, minibatch=min(len(self.seen), 100))
        
        def predict(self, seqs):
            model = CNN(encoder=self.encode, shape=self.shape)
            if self.prior: model.fit(*zip(*self.prior.items()), epochs=initial_epochs, minibatch=100)
            if self.seen: model.fit(*zip(*self.seen.items()), epochs=epochs, minibatch=100)
            return model.predict(seqs)

    return Agent
