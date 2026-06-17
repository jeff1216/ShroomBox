import asyncio
import math
import time
import pygame
import pygame_gui

from fruitbox_pygame.ai_watch import FruitBoxAiWatch, AI_INTERVAL
from fruitbox_pygame import colors as fruitbox_colors
from fruitbox_pygame import config as fruitbox_config
from ._common import is_wasm, ONNX_PATH, ONNX_URL, GRID_N


class WebAiWatch(FruitBoxAiWatch):
    """FruitBoxAiWatch using OnnxAgent / JsOnnxAgent with an async run() for pygbag."""

    def _create_model(self):
        return None  # deferred to _init_model() at the start of run()

    async def _init_model(self):
        if is_wasm():
            from .js_onnx_agent import JsOnnxAgent
            self.model = await JsOnnxAgent.create(ONNX_URL, GRID_N)
        else:
            from fruitbox_app_onnx.onnx_agent import OnnxAgent
            self.model = OnnxAgent(ONNX_PATH)

    async def _step_ai_async(self):
        obs   = self.ai_env.env._obs()
        masks = self.ai_env.env.action_masks()
        action, _ = await self.model.predict_async(obs, action_masks=masks, deterministic=True)
        r0, c0, r1, c1 = self.ai_env.env._decode(int(action))
        self.sel_start    = (r0, c0)
        self.sel_end      = (r1, c1)
        self.sel_clear_at = time.time() + 0.3
        _, no_moves = self.game.apply_move(r0, c0, r1, c1)
        if no_moves:
            self.game_over    = True
            self.game_over_at = time.time()

    async def run(self):
        await self._init_model()

        while True:
            dt = self.clock.tick(60) / 1000.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return

                if event.type == pygame_gui.UI_BUTTON_PRESSED:
                    if event.ui_element == self.menu_btn:
                        return
                    if event.ui_element == self.restart_btn:
                        self.reset()

                if event.type == pygame.KEYDOWN:
                    if event.key == fruitbox_config.get("key_menu"):
                        return
                    if event.key == pygame.K_r:
                        self.reset()

                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if self.game_over and self.show_game_over and self.close_over_rect.collidepoint(event.pos):
                        self.show_game_over = False

                self.ui.process_events(event)

            if not self.game_over:
                timed_out = self.game.tick(dt)
                if timed_out:
                    self.game_over    = True
                    self.game_over_at = time.time()

                now = time.time()
                if now >= self.last_ai_move:
                    self.last_ai_move = now + AI_INTERVAL
                    await self._step_ai_async()
                if now >= self.sel_clear_at:
                    self.sel_start = self.sel_end = None

            if self.game_over and self.show_game_over and self.game_over_at is not None:
                if time.time() - self.game_over_at >= 5.0:
                    self.reset()
                    continue

            self.screen.fill(fruitbox_colors.C["BG"])
            self._draw_hud()
            self._draw_board()

            self.ui.update(dt)
            self.ui.draw_ui(self.screen)

            btn_r = self.restart_btn.get_abs_rect()
            self.screen.blit(self._icon_restart, self._icon_restart.get_rect(center=btn_r.center))

            if self.game_over and self.show_game_over:
                self._draw_game_over()

            pygame.display.flip()
            await asyncio.sleep(0)
