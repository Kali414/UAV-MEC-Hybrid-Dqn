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


from asgp import AGSPOptimizer

from trust_dqn import TrustAwareDQN, ReplayBuffer

from MU_env import DynamicMECEnv


class HybridAgent:
    """
    Hybrid Learning Agent combining:
    ---------------------------------
    - Deep Q-Learning (TrustAwareDQN)
    - AGSP Metaheuristic optimization

    Modes:
      'online'  : AGSP used periodically during training
      'offline' : DQN-only training, AGSP applied post-training

    This hybridization helps the agent escape local minima
    and improves exploration and global search of action space.
    """
    def __init__(self, dqn_agent: TrustAwareDQN, agsp_opt: AGSPOptimizer,
                 mode='online', agsp_iters=30, agsp_particles=30):
        assert mode in ('online', 'offline')
        self.dqn = dqn_agent
        self.agsp = agsp_opt
        self.mode = mode

        # Configure AGSP hyperparameters
        self.agsp.iters = agsp_iters
        self.agsp.n_particles = agsp_particles

    # ------------------------------------------------------------
    # Hybrid Training Loop
    # ------------------------------------------------------------
    def train(self, env: DynamicMECEnv, episodes: int = 300,
              steps_per_ep: int = 150, agsp_refine_every: int = 5):
        """
        Hybrid training procedure:
          - DQN learns via experience replay
          - AGSP periodically refines actions
        """
        for ep in range(episodes):
            s = env.reset()
            total_r = 0.0

            for step in range(steps_per_ep):
                # 1️⃣ DQN selects base actions
                dqn_actions = self.dqn.select_actions(s)

                # 2️⃣ Apply AGSP refinement every N steps
                if self.mode == 'online' and (step % agsp_refine_every == 0):
                    try:
                        actions = self.agsp.optimize(env, init_actions=dqn_actions)
                    except TypeError:
                        actions = self.agsp.optimize(env)
                else:
                    actions = dqn_actions

                # 3️⃣ Execute step and get environment feedback
                ns, _, done, info = env.step(actions, adaptive_weights=True)

                # 4️⃣ Compute trust-based reward and train DQN
                reward_for_dqn = self.dqn.compute_trust_reward(info)
                self.dqn.remember_batch(s, actions, reward_for_dqn, ns, done)
                self.dqn.train_step()

                # 5️⃣ Progress updates
                s = ns
                total_r += reward_for_dqn
                if done:
                    break

            # Episode summary log
            if (ep + 1) % 10 == 0:
                print(f"[Hybrid] Ep {ep+1}/{episodes} | "
                      f"AvgReward={total_r/steps_per_ep:.4f} | eps={self.dqn.eps:.4f}")