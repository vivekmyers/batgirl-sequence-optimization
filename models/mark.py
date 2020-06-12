import numpy as np
from random import *
import os, sys
import torch
from torch import nn
import torch.functional as F
from abc import ABC, abstractmethod
import utils.model


class MarkEmbedding:
    '''Embedding with marker sequence penalization term.'''

    def make_model(self, shape, dim):

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
                    nn.Linear(32 * shape[0], 100), nn.ReLU(), nn.Linear(100, 1 + dim), nn.Sigmoid())

            def forward(self, x):
                filtered = self.conv_layers(x.permute(0, 2, 1))
                fc = self.fc_layers(filtered.reshape(filtered.shape[0], -1))
                return fc[:, 0]

            def embed(self, x):
                filtered = self.conv_layers(x.permute(0, 2, 1))
                fc = self.fc_layers(filtered.reshape(filtered.shape[0], -1))
                return fc[:, 1:]

            def l2(self):
                return sum(torch.sum(param ** 2) for c in self.conv for param in c.parameters())

        return Model()

    def _make_net(self, alpha, opt, shape, dim):
        self.model = self.make_model(shape, dim).to(self.device)

    def fit(self, seqs, scores, epochs, markers):
        '''Refit embedding with labeled sequences.'''
        self.model.train()
        markers = np.array([[self.encode(x)] for x in markers])
        D = list(zip([self.encode(x) for x in seqs], scores))
        M = len(D) // self.minibatch + bool(len(D) % self.minibatch)
        for ep in range(epochs):
            shuffle(D)
            for mb in range(M):
                X, Y = map(lambda t: torch.tensor(t).to(self.device), 
                            zip(*D[mb * self.minibatch : (mb + 1) * self.minibatch]))
                idx_a, idx_b = sample(list(range(len(markers))), 2)
                mark_a = markers[idx_a]
                mark_b = markers[idx_b]
                loss = torch.mean((Y - self.model(X.float())) ** 2) \
                        + self.lam * self.model.l2() \
                        + torch.clamp(self.clip - \
                            torch.norm(self.model.embed(torch.tensor(mark_a).float().to(self.device)) \
                            - self.model.embed(torch.tensor(mark_b).float().to(self.device)), 2), min=0)
                self.opt.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(self.model.parameters(), 1)
                self.opt.step()

    @utils.model.batch
    def predict(self, seqs):
        self.model.eval()
        return self.model(torch.tensor([self.encode(seq) for seq in seqs]).float()
                    .to(self.device)).detach().cpu().numpy()
    
    @utils.model.batch
    def __call__(self, seqs):
        '''Embed list of sequences.'''
        self.model.eval()
        return self.model.embed(
                torch.tensor([self.encode(seq) for seq in seqs])
                .float().to(self.device)).detach().cpu().numpy()

    def __init__(self, encoder, dim, shape, alpha=1e-3, lam=0, clip=0.2, minibatch=100):
        '''Embeds sequences encoded by encoder with learning rate alpha and l2 regularization lambda,
        fitting a function from embedding of dimension dim to the labels. Markers are moved at least
        clip apart when training.
        '''
        super().__init__()
        if not torch.cuda.is_available():
            self.device = 'cpu'
        else:
            self.device = 'cuda'
        self.minibatch = minibatch
        self.encode = encoder
        self.lam = lam
        self.alpha = alpha
        self.clip = clip
        self._make_net(alpha, 'adam', shape, dim)
        self.opt = torch.optim.Adam(self.model.parameters(), lr=self.alpha)


