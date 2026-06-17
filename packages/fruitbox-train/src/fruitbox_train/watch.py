import sys
import time
import pygame
from sb3_contrib import MaskablePPO
from sb3_contrib.common.wrappers import ActionMasker

from fruitbox_core.env import FruitBoxEnv
from fruitbox_pygame.pygame_ui import FruitBoxPygame, BG

MODEL_PATH = "fruitbox_ppo_final"
STEP_DELAY = 0.1   # seconds to show each selection before applying the move


def mask_fn(env):
    return env.action_masks()


def main():
    env = ActionMasker(FruitBoxEnv(), mask_fn)
    model = MaskablePPO.load(MODEL_PATH)

    obs, _ = env.reset()
    viz = FruitBoxPygame(game=env.env.game)

    pending_action = None
    next_step_at = time.time() + STEP_DELAY

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_r:
                obs, _ = env.reset()
                viz.game_over = False
                viz.over_reason = ""
                viz.drag_start = None
                viz.drag_end = None
                pending_action = None
                next_step_at = time.time() + STEP_DELAY

        now = time.time()

        if not viz.game_over and now >= next_step_at:
            if pending_action is not None:
                # apply the move that was highlighted
                obs, _reward, terminated, truncated, _ = env.step(pending_action)
                viz.drag_start = None
                viz.drag_end = None
                pending_action = None

                if terminated or truncated:
                    viz.game_over = True
                    viz.over_reason = "No more valid moves" if terminated else "Time's up!"

            if not viz.game_over:
                # pick next action and highlight the selection
                action, _ = model.predict(obs, action_masks=env.action_masks(), deterministic=True)
                r1, c1, r2, c2 = env.env._decode(int(action))
                viz.drag_start = (r1, c1)
                viz.drag_end = (r2, c2)
                pending_action = action
                next_step_at = now + STEP_DELAY

        viz.screen.fill(BG)
        viz.draw_hud()
        viz.draw_grid()
        if viz.game_over:
            viz.draw_game_over()
        pygame.display.flip()
        viz.clock.tick(60)


if __name__ == "__main__":
    main()
