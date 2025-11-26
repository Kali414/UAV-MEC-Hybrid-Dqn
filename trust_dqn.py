import os
import json
import math
import random
from collections import deque
from datetime import datetime
from typing import List, Tuple, Dict

import numpy as np
import matplotlib.pyplot as plt
import networkx as nx
from tqdm import tqdm

import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers, models, optimizers


import os, json, csv, math, random, inspect
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
from matplotlib.patches import Circle
from collections import deque
from PIL import Image
import tensorflow as tf
from tensorflow.keras import layers, models, optimizers


# ============================================================
# Trust-Aware DQN
# ============================================================

class ReplayBuffer:
    """Basic experience replay buffer for DQN transitions."""
    def __init__(self, capacity=100000):
        self.buf = deque(maxlen=capacity)
    def push(self, s, a, r, ns, d): self.buf.append((s, a, r, ns, d))
    def sample(self, b):
        batch = random.sample(self.buf, b)
        S, A, R, NS, D = zip(*batch)
        return np.array(S), np.array(A), np.array(R), np.array(NS), np.array(D)
    def __len__(self): return len(self.buf)


def build_q_network(input_dim, n_actions, lr=3e-4):
    """
    Build a Q-network using Deep Neural Network layers.
    Architecture:
        [512 → 256 → 128 → output(n_actions)]
    Activation: ReLU
    Loss: Huber (robust to outliers)
    Optimizer: Adam
    """
    inp = layers.Input(shape=(input_dim,))
    x = layers.Dense(512, activation='relu')(inp)
    x = layers.Dense(256, activation='relu')(x)
    x = layers.Dense(128, activation='relu')(x)
    out = layers.Dense(n_actions, activation='linear')(x)
    model = models.Model(inputs=inp, outputs=out)
    model.compile(optimizer=optimizers.Adam(learning_rate=lr),
                  loss=tf.keras.losses.Huber())
    return model


class TrustAwareDQN:
    """
    DQN with Trust- and Cost-aware reward function.
    ------------------------------------------------
    - Learns per-user offloading actions
    - Balances trust vs latency/energy cost
    - Uses soft target updates (tau)
    - Supports batch memory for multi-user transitions
    """
    def __init__(self, input_dim, n_actions, lr=3e-4, gamma=0.99, tau=0.005,
                 eps_start=1.0, eps_end=0.05, eps_decay=0.995,
                 trust_weight=0.6, cost_weight=0.4, batch_size=256):

        # Core RL parameters
        self.gamma, self.tau = gamma, tau
        self.eps, self.eps_min, self.eps_decay = eps_start, eps_end, eps_decay
        self.trust_weight, self.cost_weight = trust_weight, cost_weight
        self.batch_size = batch_size

        # Build primary and target networks
        self.net = build_q_network(input_dim, n_actions, lr)
        self.tgt = build_q_network(input_dim, n_actions, lr)
        self.tgt.set_weights(self.net.get_weights())

        # Experience replay memory
        self.memory = ReplayBuffer()

    # ------------------------------------------------------------
    # Action selection (ε-greedy)
    # ------------------------------------------------------------
    def select_actions(self, states):
        """Select per-MU actions via epsilon-greedy policy."""
        if np.random.rand() < self.eps:
            # Random exploration
            return np.random.randint(0, self.net.output_shape[-1], states.shape[0])
        # Greedy exploitation
        q = self.net.predict(states, verbose=0)
        return np.argmax(q, axis=1)

    # ------------------------------------------------------------
    # Trust-aware reward
    # ------------------------------------------------------------
    def compute_trust_reward(self, info):
        """
        Compute scalar trust-aware reward using environment stats:
          trust_reward = trust_weight - cost_weight * normalized_cost
        """
        T, E = np.mean(info["T_mean"]), np.mean(info["E_mean"])
        norm_cost = (T + E) / (1 + T + E)
        return self.trust_weight - self.cost_weight * norm_cost

    # ------------------------------------------------------------
    # Memory management
    # ------------------------------------------------------------
    def remember(self, s, a, r, ns, d):
        """Push individual state transitions into buffer."""
        for i in range(s.shape[0]):
            self.memory.push(s[i], int(a[i]), r, ns[i], d)

    def remember_batch(self, states, actions, reward, next_states, done):
        """
        Stores transitions for all MUs (batch-level).
        Automatically handles scalar or vector rewards.
        """
        batch_size = states.shape[0]
        reward_vec = np.full(batch_size, reward) if np.isscalar(reward) else np.asarray(reward)
        done_flag = float(done)

        for i in range(batch_size):
            self.memory.push(states[i], int(actions[i]), reward_vec[i],
                             next_states[i], done_flag)

    # ------------------------------------------------------------
    # DQN Training Step
    # ------------------------------------------------------------
    def train_step(self):
        """Perform a single mini-batch update."""
        if len(self.memory) < self.batch_size:
            return

        S, A, R, NS, D = self.memory.sample(self.batch_size)

        # Current Q-values
        qvals = self.net.predict(S, verbose=0)

        # Target Q-values using double DQN logic
        next_q = self.tgt.predict(NS, verbose=0)
        max_next = np.max(next_q, axis=1)
        targets = R + (1 - D) * self.gamma * max_next

        # Update target entries for chosen actions
        qvals[np.arange(self.batch_size), A] = targets

        # Train online network
        self.net.train_on_batch(S, qvals)

        # Epsilon decay
        self.eps = max(self.eps * self.eps_decay, self.eps_min)

        # Soft update target network
        w, wt = self.net.get_weights(), self.tgt.get_weights()
        self.tgt.set_weights([self.tau * wn + (1 - self.tau) * wt for wn, wt in zip(w, wt)])
