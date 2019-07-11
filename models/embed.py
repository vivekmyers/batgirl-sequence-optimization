import numpy as np
from random import *
import os, sys
import torch
from torch import nn
import torch.functional as F

class Embedding:
    '''Generates sequence embedding from scores.'''

    def _make_net(self, alpha, opt, shape, dim):

        class Model(nn.Module):

            def __init__(self):
                super().__init__()
                conv = self.conv = [nn.Conv1d(shape[1], 64, 7, stride=1, padding=3),
                    nn.Conv1d(64, 64, 5, stride=1, padding=2),
                    nn.Conv1d(64, 32, 3, stride=1, padding=1)]
                self.conv_layers = nn.Sequential(
                    conv[0], nn.ReLU(), conv[1], nn.ReLU(),
                    conv[2], nn.ReLU()) 
                self.fc_layers = nn.Sequential(
                    nn.Linear(32 * shape[0], 100), nn.ReLU(), nn.Linear(100, dim))
                self.score = nn.Linear(dim, 1)

            def forward(self, x):
                filtered = self.conv_layers(x.permute(0, 2, 1))
                return torch.squeeze(self.score(
                    self.fc_layers(filtered.reshape(filtered.shape[0], -1))))

            def embed(self, x):
                if len(x) == 0: return torch.tensor([])
                filtered = self.conv_layers(x.permute(0, 2, 1))
                return self.fc_layers(filtered.reshape(filtered.shape[0], -1))
            
            def l2(self):
                return sum(torch.norm(param, 2) for c in self.conv for param in c.parameters())

        self.model = Model().to(self.device)

    def refit(self, seqs, scores, epochs, minibatch):
        '''Refit embedding with labeled sequences.'''
        D = list(zip([self.encode(x) for x in seqs], scores))
        M = len(D) // minibatch
        for ep in range(epochs):
            shuffle(D)
            for mb in range(M):
                X, Y = map(lambda t: torch.tensor(t).to(self.device), 
                            zip(*D[mb * minibatch : (mb + 1) * minibatch]))
                loss = torch.norm(Y - self.model(X.float()), 2) + self.lam * self.model.l2()
                self.opt.zero_grad()
                loss.backward()
                self.opt.step()
    
    def __call__(self, seqs):
        '''Embed list of sequences.'''
        return self.model.embed(
                torch.tensor([self.encode(seq) for seq in seqs])
                .float().to(self.device)).detach().cpu().numpy()

    def __init__(self, encoder, dim, shape=(), alpha=1e-4, lam=1e-3):
        '''Embeds sequences encoded by encoder with learning rate alpha and l2 regularization lambda,
        fitting a function from embedding of dimension dim to the labels.
        '''
        super().__init__()
        if not torch.cuda.is_available():
            print('CUDA not available')
            self.device = 'cpu'
        else:
            self.device = 'cuda'
        self.encode = encoder
        self.lam = lam
        self.alpha = alpha
        self._make_net(alpha, 'adam', shape, dim)
        self.opt = torch.optim.Adam(self.model.parameters(), lr=self.alpha)
