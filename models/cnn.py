from keras.layers import *
from keras.models import *
import numpy as np
from random import *
import tensorflow as tf
import keras.backend as K
from keras.callbacks import History

class CNN(Sequential):
    def make_net(self, alpha, opt, shape):
        self.add(Conv1D(64, kernel_size=7,
                           activation='relu',
                           input_shape=shape, kernel_regularizer=regularizers.l2(0.001)))
        self.add(Conv1D(64, kernel_size=5,
                           activation='relu', kernel_regularizer=regularizers.l2(0.001)))
        self.add(Conv1D(32, kernel_size=3,
                           activation='relu', kernel_regularizer=regularizers.l2(0.001)))
        self.add(Flatten())
        self.add(Dense(100, activation='relu'))
        self.add(Dropout(0.5))
        self.add(Dense(1, activation='sigmoid'))
        self.compile(loss='mse',
                    optimizer=opt,
                    metrics=['accuracy'])
        K.set_value(self.optimizer.lr, alpha)
    
    def encode(self, seq):
        if seq in self.encode_cache:
            return self.encode_cache[seq]
        assert seq[0] in '+-'
        arr = np.zeros([len(seq), 4])
        arr[0, :] = 1 if seq[0] == '-' else 0
        arr[(np.arange(1, len(seq)), ['ATCG'.index(i) for i in seq[1:]])] = 1
        self.encode_cache[seq] = arr
        return arr

    def fit(self, seqs, scores, val=([], []), epochs=1, verbose=2):
        x_val, y_val = val
        result = super().fit(x=np.array([self.encode(x) for x in seqs]), 
                        y=np.array(scores), validation_data=(np.array(
                            list(map(self.encode, x_val))), np.array(y_val)) if val[0] else None, 
                        verbose=verbose, epochs=epochs + self.current_epoch, 
                        initial_epoch=self.current_epoch, callbacks=[self.history])
        self.current_epoch += epochs
    
    def predict(self, seqs):
        return np.squeeze(super().predict(np.array([self.encode(x) for x in seqs])))
    
    def __call__(self, seqs):
        return self.predict(seqs)

    def __init__(self, alpha=1e-4, shape=()):
        super().__init__()
        self.history = History()
        self.encode_cache = {}
        self.current_epoch = 0
        self.alpha = alpha
        self.make_net(alpha, 'adam', shape)
