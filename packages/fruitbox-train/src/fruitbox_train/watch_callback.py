import os
import time
import tempfile
import multiprocessing as mp
import queue

import pygame
from stable_baselines3.common.callbacks import BaseCallback
from sb3_contrib import MaskablePPO
from sb3_contrib.common.wrappers import ActionMasker

from fruitbox_core.env import FruitBoxEnv
from fruitbox_pygame.pygame_ui import FruitBoxPygame, BG


def mask_fn(env):
    return env.action_masks()


def _viz_worker(q, step_delay):
    """Separate process: loads models from the queue and plays episodes continuously."""

    # wait for the first model before opening the window
    model_path = q.get()
    if model_path == "STOP":
        return
    model = MaskablePPO.load(model_path)
    viz = None

    while True:
        # set up a fresh episode
        env = ActionMasker(FruitBoxEnv(), mask_fn)
        obs, _ = env.reset()

        if viz is None:
            viz = FruitBoxPygame(game=env.env.game)
        else:
            viz.game = env.env.game
            viz.game_over = False
            viz.over_reason = ""
            viz.drag_start = None
            viz.drag_end = None

        pending_action = None
        next_step_at = time.time() + step_delay

        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return

            now = time.time()

            if not viz.game_over and now >= next_step_at:
                if pending_action is not None:
                    obs, _, terminated, truncated, _ = env.step(pending_action)
                    viz.drag_start = None
                    viz.drag_end = None
                    pending_action = None

                    if terminated or truncated:
                        viz.game_over = True
                        viz.over_reason = "No more valid moves" if terminated else "Time's up!"

                if not viz.game_over:
                    action, _ = model.predict(
                        obs, action_masks=env.action_masks(), deterministic=True
                    )
                    r1, c1, r2, c2 = env.env._decode(int(action))
                    viz.drag_start = (r1, c1)
                    viz.drag_end = (r2, c2)
                    pending_action = action
                    next_step_at = now + step_delay

            elif viz.game_over and now >= next_step_at:
                break  # start next episode

            viz.screen.fill(BG)
            viz.draw_hud()
            viz.draw_grid()
            if viz.game_over:
                viz.draw_game_over()
            pygame.display.flip()
            viz.clock.tick(60)

        # between episodes: pick up the latest model if one arrived
        latest = None
        try:
            while True:
                msg = q.get_nowait()
                if msg == "STOP":
                    return
                latest = msg
        except queue.Empty:
            pass

        if latest is not None:
            model = MaskablePPO.load(latest)


class WatchCallback(BaseCallback):
    """Streams model snapshots to a background viz process every render_freq steps.
    Training never pauses — the window runs continuously in parallel.
    """

    def __init__(self, render_freq=100_000, step_delay=0.1, verbose=0):
        super().__init__(verbose)
        self.render_freq = render_freq
        self.step_delay = step_delay
        self._last_render = 0
        self._tmp_dir = tempfile.gettempdir()
        self._queue = mp.Queue()
        self._process = mp.Process(
            target=_viz_worker, args=(self._queue, step_delay), daemon=True
        )
        self._process.start()

    def _on_step(self):
        if self.num_timesteps - self._last_render >= self.render_freq:
            self._last_render = self.num_timesteps
            # unique filename per snapshot avoids read/write race condition
            path = os.path.join(self._tmp_dir, f"fruitbox_watch_{self.num_timesteps}")
            self.model.save(path)
            self._queue.put(path + ".zip")
        return True

    def _on_training_end(self):
        self._queue.put("STOP")
        self._process.join(timeout=5)
