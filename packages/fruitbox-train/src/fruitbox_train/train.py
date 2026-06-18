import os
import argparse
import torch
from stable_baselines3.common.env_util import make_vec_env
from stable_baselines3.common.vec_env import VecMonitor
from stable_baselines3.common.callbacks import CheckpointCallback
from sb3_contrib import MaskablePPO
from sb3_contrib.common.wrappers import ActionMasker

from fruitbox_core.env import FruitBoxEnv
from .watch_callback import WatchCallback

MODEL_PATH  = "fruitbox_ppo_final"
NEW = False

def mask_fn(env):
    return env.action_masks()


def make_env():
    env = FruitBoxEnv()
    env = ActionMasker(env, mask_fn)
    return env


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--watch", action="store_true", help="Render a game episode every N steps during training")
    args = parser.parse_args()

    os.makedirs("logs", exist_ok=True)
    os.makedirs("checkpoints", exist_ok=True)

    n_envs = 16
    n_steps = 256
    vec_env = make_vec_env(make_env, n_envs=n_envs)
    vec_env = VecMonitor(vec_env, filename="logs/monitor")

    callbacks = [
        CheckpointCallback(
            save_freq=n_steps * n_envs * 2,
            save_path="checkpoints/",
            name_prefix="fruitbox_ppo",
        ),
    ]
    if args.watch:
        callbacks.append(WatchCallback(render_freq=1000, step_delay=0.4))

    print(f"Device: {'cuda (' + torch.cuda.get_device_name(0) + ')' if torch.cuda.is_available() else 'cpu'}")

    if NEW:
        model = MaskablePPO(
            "MultiInputPolicy",
            vec_env,
            learning_rate=3e-4,
            n_steps=n_steps,
            batch_size=256,
            n_epochs=4,
            gamma=0.99,
            gae_lambda=0.95,
            clip_range=0.2,
            ent_coef=0.02,
            verbose=1,
            policy_kwargs=dict(net_arch=[512, 512]),
            device="auto",
        )
    else:
        model = MaskablePPO.load(MODEL_PATH, env=vec_env, device="auto")
    model.learn(total_timesteps=n_steps * n_envs, callback=callbacks, progress_bar=True)
    model.save("fruitbox_ppo_final")
    print("Training complete.")


if __name__ == "__main__":
    main()
