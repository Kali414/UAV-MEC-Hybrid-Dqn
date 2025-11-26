from collections import deque
from datetime import datetime
from typing import List, Tuple, Dict

import os, json, csv, math, random, inspect
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Circle


class DynamicMECEnv:
    """
    UAV-assisted Multi-Access Edge Computing (MEC) Environment.
    ------------------------------------------------------------
    Simulates mobile users (MUs), Unmanned Aerial Vehicles (UAVs),
    wireless communication, energy consumption, and task offloading.

    Each MU chooses one action per time step:
        0   → Local computation (on device)
        1..K → Offload to UAV-k
        K+1 → Offload to Cloud

    The environment dynamically updates:
        - MU/UAV positions
        - Task generation
        - UAV energy and queues
        - Quality of Experience (QoE)
    """

    def __init__(self, M=20, K=2, area_size=1000.0, uav_range=500.0,user_cpu=1.8e9, uav_cpu=4e9, cloud_cpu=2e10,kappa_mu=1e-28,
            kappa_uav=5e-28,uav_energy_cap=1000,seed=42, max_steps=200):
        """
        Initialize a new MEC environment.
        ------------------------------------------------------------
        Parameters:
            M : int       → number of mobile users
            K : int       → number of UAVs
            area_size : float → simulation area (m)
            uav_range : float → communication radius of UAV (m)
            seed : int    → RNG seed for reproducibility
            max_steps : int → maximum simulation time steps
        """
        # Validate inputs
        if M <= 0:
            raise ValueError(f"Number of mobile users (M) must be positive, got {M}")
        if K < 0:
            raise ValueError(f"Number of UAVs (K) must be non-negative, got {K}")
        
        self.M = M
        self.K = K
        self.area = area_size
        self.uav_range = uav_range
        self.rng = np.random.default_rng(seed)
        self.max_steps = max_steps

        # ------------------------------------------------------------
        # Radio / Computation parameters
        # ------------------------------------------------------------
        self.Pm = 0.1          # Transmit power (Watts)
        self.B = 10e6          # Bandwidth (Hz)
        self.N0 = 1e-17        # Noise power spectral density
        self.kappa_mu = kappa_mu  # Energy coefficient (local)
        self.kappa_uav = kappa_uav # Energy coefficient (UAV)
        self.f_user = user_cpu   # CPU freq (user)
        self.f_uav = uav_cpu     # CPU freq (UAV)
        self.f_cloud = cloud_cpu    # CPU freq (cloud)
        self.h_uav = 100.0     # UAV altitude (m)

        # ------------------------------------------------------------
        # UAV energy model (hover, move, computation)
        # ------------------------------------------------------------
        self.E_hover = 200.0
        self.E_move = 250.0
        self.E_comp_factor = 1e-8
        self.uav_energy = np.ones(self.K) * uav_energy_cap if self.K > 0 else np.array([])

        # ------------------------------------------------------------
        # QoE computation weights
        # ------------------------------------------------------------
        self.alpha = 0.5  # latency weight
        self.beta = 0.2   # energy weight
        self.deadline_penalty = 0.5

        # ------------------------------------------------------------
        # Position and history initialization
        # ------------------------------------------------------------
        self.mu_pos = np.zeros((self.M, 2))     # MU positions
        self.uav_pos = np.zeros((self.K, 2))    # UAV positions
        self.euav_queues = [deque() for _ in range(self.K)]  # task queues
        self.history = {
            "QoE": [], "T_mean": [], "E_mean": [], "queue_mean": []
        }

        self.reset()  # initialize environment state

    # ------------------------------------------------------------
    # Reset the environment for a new episode
    # ------------------------------------------------------------
    def reset(self):
        """
        Randomly initialize all positions, queues, energy, and tasks.
        Returns initial state observation for DQN or optimizer.
        """
        self.mu_pos = self.rng.uniform(0, self.area, (self.M, 2))
        self.uav_pos = self.rng.uniform(0, self.area, (self.K, 2)) if self.K > 0 else np.zeros((0, 2))
        
        if self.K > 0:
            self.uav_energy[:] = 1000.0  # reset energy
        
        self.euav_queues = [deque() for _ in range(self.K)]
        self.history = {k: [] for k in self.history}
        self.t = 0
        self.generate_tasks()
        return self._get_state()

    # ------------------------------------------------------------
    # Task generation per MU
    # ------------------------------------------------------------
    def generate_tasks(self):
        """
        Each MU receives a random task:
          - D : input data size (bits)
          - Cpb : computation cycles per bit
          - T_deadline : time deadline (seconds)
        """
        self.D = self.rng.uniform(0.5e6, 5e6, size=self.M)
        self.Cpb = self.rng.uniform(600, 1200, size=self.M)
        self.T_deadline = self.rng.uniform(0.2, 1.0, size=self.M)

    # ------------------------------------------------------------
    # UAV Movement (simple centroid following)
    # ------------------------------------------------------------
    def _update_positions(self):
        """
        Each UAV moves slightly toward the centroid of all MUs.
        Propulsion and hover energy are deducted per step.
        """
        if self.K == 0 or self.M == 0:
            return
            
        center = np.mean(self.mu_pos, axis=0)
        for k in range(self.K):
            direction = center - self.uav_pos[k]
            norm = np.linalg.norm(direction)
            if norm > 1e-9:
                self.uav_pos[k] += 2.0 * (direction / norm)
            self.uav_energy[k] -= (self.E_hover + 0.01 * self.E_move)

    # ------------------------------------------------------------
    # Wireless channel and path-loss model
    # ------------------------------------------------------------
    def _path_loss_gain(self):
        """
        Compute distance-dependent path gain between each MU-UAV pair.
        Returns:
            gain : (M,K) matrix of channel gains
            d_3d : (M,K) matrix of 3D distances
        """
        if self.K == 0:
            return np.zeros((self.M, 0)), np.zeros((self.M, 0))
            
        mu = self.mu_pos[:, None, :]
        uav = self.uav_pos[None, :, :]
        d_2d = np.linalg.norm(mu - uav, axis=-1)
        d_3d = np.sqrt(d_2d**2 + self.h_uav**2)
        PL = 20 * np.log10(d_3d + 1e-9) + 20 * np.log10(2.4e9) - 147.55
        gain = 10 ** (-PL / 10.0)
        return gain, d_3d

    def _uplink_rate(self, gain):
        """Compute uplink transmission rate (Shannon formula)."""
        snr = (self.Pm * gain) / (self.N0 * self.B + 1e-30)
        return self.B * np.log2(1 + snr)

    # ------------------------------------------------------------
    # Compute delay and energy cost for all users
    # ------------------------------------------------------------
    def _compute_costs(self, actions):
        """
        Given MU actions, compute:
          - T[i]: total delay per MU
          - E[i]: total energy per MU
        Incorporates local, UAV, and cloud execution models.
        """
        M = self.M
        T = np.zeros(M)
        E = np.zeros(M)
        
        if M == 0:
            return T, E
            
        gain, d = self._path_loss_gain()
        rate = self._uplink_rate(gain)
        
        # Handle case with no UAVs
        if self.K > 0 and rate.size > 0:
            best_rate = rate.max(axis=1)
        else:
            best_rate = np.full(M, self.B * 0.1)  # Default low rate for cloud

        for i, a in enumerate(actions):
            cycles = self.D[i] * self.Cpb[i]

            # --- Local computation ---
            if a == 0:
                T[i] = cycles / self.f_user
                E[i] = self.kappa_mu * cycles * (self.f_user ** 2)

            # --- Offload to UAV ---
            elif 1 <= a <= self.K and self.K > 0:
                k = a - 1
                if d[i, k] <= self.uav_range and self.uav_energy[k] > 0:
                    t_tx = self.D[i] / (rate[i, k] + 1e-9)
                    t_exe = cycles / self.f_uav
                    T[i] = t_tx + t_exe + len(self.euav_queues[k]) * 0.02
                    E[i] = self.Pm * t_tx + self.kappa_uav * cycles * (self.f_uav ** 2)
                    self.euav_queues[k].append({"cycles": cycles})
                    self.uav_energy[k] -= self.E_comp_factor * cycles
                else:
                    # out-of-range → fallback to cloud
                    T[i] = (self.D[i] / best_rate[i]) + (cycles / self.f_cloud)
                    E[i] = self.Pm * (self.D[i] / best_rate[i])

            # --- Offload to Cloud ---
            else:
                T[i] = (self.D[i] / best_rate[i]) + (cycles / self.f_cloud)
                E[i] = self.Pm * (self.D[i] / best_rate[i])

        return T, E

    # ------------------------------------------------------------
    # Step environment forward
    # ------------------------------------------------------------
    def step(self, actions, adaptive_weights=True):
        """
        Perform one environment step:
          1. Update positions and tasks
          2. Compute delay and energy
          3. Calculate QoE-based reward
          4. Update UAV energy and queues
        Returns: (next_state, reward, done, info)
        """
        # Validate actions
        if len(actions) != self.M:
            raise ValueError(f"Expected {self.M} actions, got {len(actions)}")
        
        # --- Movement and occasional task regeneration ---
        self._update_positions()
        if (self.t % 50 == 0 and self.t != 0):
            self.generate_tasks()

        # --- Compute costs ---
        T, E = self._compute_costs(actions)
        
        # --- Safe normalization ---
        T_max = T.max() if T.size > 0 and T.max() > 0 else 1.0
        E_max = E.max() if E.size > 0 and E.max() > 0 else 1.0
        
        T_norm = T / (T_max + 1e-9)
        E_norm = E / (E_max + 1e-9)

        # --- Adaptive weighting for energy-aware QoE ---
        if adaptive_weights and self.K > 0:
            avg_energy = self.uav_energy.mean() / 1000.0
            alpha = 0.4 + 0.3 * (1 - avg_energy)
            beta = 0.2 + 0.3 * (1 - avg_energy)
        else:
            alpha, beta = self.alpha, self.beta

        # --- Compute per-MU QoE ---
        QoE_i = np.exp(-(alpha * T_norm + beta * E_norm))
        QoE_i[T > self.T_deadline] *= self.deadline_penalty
        reward = QoE_i.mean() if QoE_i.size > 0 else 0.0

        # --- Update simulation counters and history ---
        self.t += 1
        done = (self.t >= self.max_steps or (self.K > 0 and np.any(self.uav_energy <= 0)))
        
        self.history["QoE"].append(QoE_i.mean() if QoE_i.size > 0 else 0.0)
        self.history["T_mean"].append(T.mean() if T.size > 0 else 0.0)
        self.history["E_mean"].append(E.mean() if E.size > 0 else 0.0)
        self.history["queue_mean"].append(np.mean([len(q) for q in self.euav_queues]) if self.K > 0 else 0.0)

        # --- Build info dict for analysis ---
        info = {
            "QoE_mean": QoE_i.mean() if QoE_i.size > 0 else 0.0,
            "T_mean": T.mean() if T.size > 0 else 0.0,
            "E_mean": E.mean() if E.size > 0 else 0.0,
            "euav_queue_lengths": [len(q) for q in self.euav_queues],
            "uav_energy": self.uav_energy.copy(),
            "mu_pos": self.mu_pos.copy(),
            "uav_pos": self.uav_pos.copy()
        }

        return self._get_state(), reward, done, info

    # ------------------------------------------------------------
    # Build observation for DQN or Optimizer
    # ------------------------------------------------------------
    def _get_state(self):
        """
        Generate per-user state features used by RL agents.

        State format (M × 7):
            [ max_gain,
            mean_gain,
            nearest_distance,
            task_size,
            cycles_per_bit,
            avg_uav_energy_ratio,
            deadline ]
        """

        # Compute gain matrix and distances
        gain, dist = self._path_loss_gain()

        # ---- SAFE HANDLING FOR EMPTY UAV CASE ----
        if gain.size > 0:   # Normal case: UAVs exist
            max_gain = gain.max(axis=1)
            mean_gain = gain.mean(axis=1)
        else:   # No UAVs → treat as no wireless advantage
            max_gain = np.zeros(self.M)
            mean_gain = np.zeros(self.M)

        if dist.size > 0:
            nearest_dist = dist.min(axis=1)
        else:
            # No UAVs → assign large dummy distance
            nearest_dist = np.full(self.M, 9999.0)

        # ---- UAV ENERGY NORMALIZATION ----
        if hasattr(self, "uav_energy") and len(self.uav_energy) > 0:
            # Use normalized average energy value
            energy_ratio = np.full(self.M, np.mean(self.uav_energy) / (np.max(self.uav_energy) + 1e-8))
        else:
            energy_ratio = np.zeros(self.M)

        # ---- STACK FINAL OBSERVATION MATRIX ----
        obs = np.stack([
            max_gain,
            mean_gain,
            nearest_dist,
            self.D,            # Task size for each user
            self.Cpb,          # Computation complexity
            energy_ratio,
            self.T_deadline
        ], axis=1)

        return obs.astype(np.float32)