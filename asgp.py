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

class AGSPOptimizer:
    """
    Adaptive Genetic + Swarm + Simulated Annealing-inspired Optimizer (AGSP)
    -----------------------------------------------------------------------
    Used to refine offloading decisions (actions) for all M mobile users.

    Core idea:
      - Initialize multiple random particle solutions (action vectors)
      - Evaluate each particle using environment fitness (QoE)
      - Keep the best and resample others iteratively
      - Optionally seeded by DQN’s predicted actions for hybrid control

    Works as a fast heuristic fallback / refinement for DQN policies.
    """
    def __init__(self, M=20, K=2, iters=30, n_particles=20, seed=123):
        self.M = M                      # Number of users
        self.K = K                      # Number of UAVs
        self.iters = iters              # Optimization iterations
        self.n_particles = n_particles  # Number of particles (population)
        self.rng = np.random.default_rng(seed)  # Random generator for reproducibility

    def optimize(self, env, init_actions=None):
        """
        Run AGSP optimization for given environment.

        Inputs:
          env          : DynamicMECEnv (environment with cost model)
          init_actions : Optional action vector from DQN (for hybrid use)

        Output:
          best : optimized action vector of shape (M,)
        """
        M = env.M
        n_actions = env.K + 2  # (0=local, 1..K=UAVs, K+1=cloud)

        # Initialize random population of solutions (particles)
        particles = self.rng.integers(0, n_actions, (self.n_particles, M))

        # Seed first particle with DQN actions (hybrid start)
        if init_actions is not None:
            particles[0] = init_actions

        best = particles[0].copy()
        best_fit = -np.inf

        # --- Iterate over multiple generations ---
        for _ in range(self.iters):
            for p in particles:
                # Evaluate fitness of each particle
                fit = self._fitness(env, p)
                if fit > best_fit:
                    best_fit, best = fit, p.copy()

            # Resample new random population (simplified PSO/GA)
            particles = self.rng.integers(0, n_actions, (self.n_particles, M))

        return best

    def _fitness(self, env, A):
        """
        Fitness evaluation: computes QoE given an action set A.

        Uses the environment’s delay (T) and energy (E) cost model.
        """
        T, E = env._compute_costs(A)
        QoE = np.exp(-env.alpha * (T / T.max())) * np.exp(-env.beta * (E / E.max()))
        QoE[T > env.T_deadline] *= env.deadline_penalty
        return QoE.mean()