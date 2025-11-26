from flask import Flask, render_template, request, jsonify
import numpy as np
import tensorflow as tf

import os

from asgp import AGSPOptimizer
from hybrid_agent import HybridAgent
from trust_dqn import TrustAwareDQN
from MU_env import DynamicMECEnv

app = Flask(__name__)


@app.route('/')
def home():
    return render_template('home.html')


@app.route('/simulate')
def simulate():
    return render_template('simulate.html')


@app.route("/result", methods=["POST"])
def result():
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"status": "error", "message": "No data received"}), 400

        print("Received data:", data)  # Debug log

        # ------------------- Extract and Validate User Input ------------------------
        try:
            uav_count = int(data.get("uavCount", 3))
            user_count = int(data.get("userCount", 20))
            bandwidth = float(data.get("bandwidth", 100))
            task_size = float(data.get("taskSize", 10))
            cycles_required = float(data.get("cycles", 100))
            area_size = float(data.get("areaSize", 1000))
            uav_range = float(data.get("uavRange", 500))
            sim_steps = int(data.get("simSteps", 200))

            user_cpu = float(data.get("userCPU", 1.8)) * 1e9
            uav_cpu = float(data.get("uavCPU", 4.0)) * 1e9
            cloud_cpu = float(data.get("cloudCPU", 20)) * 1e9

            kappa_mu = float(data.get("kappaMU", 1e-28))
            kappa_uav = float(data.get("kappaUAV", 5e-28))
            battery_capacity = float(data.get("uavBattery", 1000))
        except (ValueError, TypeError) as e:
            return jsonify({"status": "error", "message": f"Invalid input values: {str(e)}"}), 400

        # Validate ranges
        if user_count <= 0:
            return jsonify({"status": "error", "message": "Number of users must be positive"}), 400
        if uav_count < 0:
            return jsonify({"status": "error", "message": "Number of UAVs cannot be negative"}), 400
        if sim_steps <= 0:
            return jsonify({"status": "error", "message": "Simulation steps must be positive"}), 400

        print(f"Creating environment with M={user_count}, K={uav_count}")

        # ------------------- Initialize Environment ------------------------
        env = DynamicMECEnv(
            M=user_count,
            K=uav_count,
            area_size=area_size,
            uav_range=uav_range,
            max_steps=sim_steps
        )

        # Apply runtime config
        env.B = bandwidth * 1e6
        env.f_user = user_cpu
        env.f_uav = uav_cpu
        env.f_cloud = cloud_cpu
        env.kappa_mu = kappa_mu
        env.kappa_uav = kappa_uav
        if env.K > 0:
            env.uav_energy = np.ones(env.K) * battery_capacity

        obs = env.reset()
        input_dim = obs.shape[1]
        n_actions = env.K + 2

        print(f"Environment initialized: input_dim={input_dim}, n_actions={n_actions}")

        # ------------------- Load Model ------------------------
        dqn = TrustAwareDQN(input_dim=input_dim, n_actions=n_actions)
        
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        model_path = os.path.join(BASE_DIR, "models", "trust_dqn_model.keras")

        try:
            dqn.net = tf.keras.models.load_model(model_path, compile=True)
            dqn.tgt = tf.keras.models.clone_model(dqn.net)
            dqn.tgt.set_weights(dqn.net.get_weights())
        except Exception as e:
            return jsonify({"status": "error", "message": f"Failed to load DQN model: {str(e)}"}), 500

        agsp = AGSPOptimizer(M=env.M, K=env.K, iters=50, n_particles=40)
        hybrid = HybridAgent(dqn_agent=dqn, agsp_opt=agsp)

        # ------------------- Policy Runner ------------------------
        def run_policy(policy, policy_name):
            print(f"Running {policy_name} policy...")
            env_copy = DynamicMECEnv(
                M=user_count,
                K=uav_count,
                area_size=area_size,
                uav_range=uav_range,
                max_steps=sim_steps
            )
            env_copy.B = bandwidth * 1e6
            env_copy.f_user = user_cpu
            env_copy.f_uav = uav_cpu
            env_copy.f_cloud = cloud_cpu
            env_copy.kappa_mu = kappa_mu
            env_copy.kappa_uav = kappa_uav
            if env_copy.K > 0:
                env_copy.uav_energy = np.ones(env_copy.K) * battery_capacity

            state = env_copy.reset()
            actions_trace = []

            QoE_list, latency_list, energy_list = [], [], []

            for step in range(sim_steps):
                try:
                    if isinstance(policy, TrustAwareDQN):
                        action = policy.select_actions(state)
                    elif isinstance(policy, AGSPOptimizer):
                        action = policy.optimize(env_copy)
                    elif isinstance(policy, HybridAgent):
                        dqn_action = policy.dqn.select_actions(state)
                        try:
                            action = policy.agsp.optimize(env_copy, init_actions=dqn_action)
                        except:
                            action = policy.agsp.optimize(env_copy)
                    else:
                        raise ValueError(f"Unknown policy type: {type(policy)}")

                    actions_trace.append(action.tolist())

                    next_state, _, done, info = env_copy.step(action)

                    QoE_list.append(info["QoE_mean"])
                    latency_list.append(info["T_mean"])
                    energy_list.append(info["E_mean"])

                    state = next_state
                    if done:
                        print(f"{policy_name} finished at step {step}")
                        break
                except Exception as e:
                    print(f"Error in {policy_name} at step {step}: {str(e)}")
                    raise

            return QoE_list, latency_list, energy_list, actions_trace

        # Run all 3 algorithms
        try:
            results = {
                "DQN": run_policy(dqn, "DQN"),
                "AGSP": run_policy(agsp, "AGSP"),
                "Hybrid": run_policy(hybrid, "Hybrid")
            }
        except Exception as e:
            return jsonify({"status": "error", "message": f"Simulation failed: {str(e)}"}), 500

        # ------------------- Latency Breakdown ------------------------
        avg_latency = float(np.mean(results["Hybrid"][1])) if results["Hybrid"][1] else 0.0

        latency_breakdown = {
            "transmission": avg_latency * 0.40,
            "processing": avg_latency * 0.25,
            "queue": avg_latency * 0.25,
            "propagation": avg_latency * 0.10
        }

        print("Simulation completed successfully")

        # ------------------- Build Position Snapshot for Visualization ------------------------
        final_env = DynamicMECEnv(
            M=user_count, K=uav_count, area_size=area_size,
            uav_range=uav_range, max_steps=sim_steps
        )

        final_env.B = bandwidth * 1e6
        final_env.f_user = user_cpu
        final_env.f_uav = uav_cpu
        final_env.f_cloud = cloud_cpu
        final_env.kappa_mu = kappa_mu
        final_env.kappa_uav = kappa_uav
        final_env.uav_energy = np.ones(final_env.K) * battery_capacity

        # Re-run environment using Hybrid final actions:
        state = final_env.reset()
        for action in results["Hybrid"][3]:
            final_env.step(np.array(action))

        positions = {
            "users": final_env.mu_pos.tolist(),
            "uavs": final_env.uav_pos.tolist(),
            "cloud": [final_env.area + 60, final_env.area + 60]
        }


        # ------------------- Return JSON ------------------------
        return jsonify({
            "status": "success",
            "labels": list(range(len(results["DQN"][0]))),

            "DQN": {
                "QoE": results["DQN"][0],
                "Latency": results["DQN"][1],
                "Energy": results["DQN"][2]
            },
            "AGSP": {
                "QoE": results["AGSP"][0],
                "Latency": results["AGSP"][1],
                "Energy": results["AGSP"][2]
            },
            "Hybrid": {
                "QoE": results["Hybrid"][0],
                "Latency": results["Hybrid"][1],
                "Energy": results["Hybrid"][2],
                "Offloading": results["Hybrid"][3]   # <-- actions list needed for visualization
            },

            "positions": positions,  # <-- NOW SENT TO FRONTEND
            "latencyBreakdown": latency_breakdown
        })


    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"Unexpected error: {str(e)}"}), 500


if __name__ == '__main__':
    app.run(debug=True)