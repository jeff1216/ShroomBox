import asyncio
import time
import pygame
import pygame_gui

from fruitbox_pygame.vs import FruitBoxVs, FPS, HUD_H, PADDING, BOARD_W, BOARD_H, AI_INTERVAL
from fruitbox_pygame import colors as fruitbox_colors
from fruitbox_core import stats as fruitbox_stats
from fruitbox_pygame import config as fruitbox_config
from ._common import is_wasm, ONNX_PATH, ONNX_URL, GRID_N


class WebVs(FruitBoxVs):
    """FruitBoxVs using OnnxAgent / JsOnnxAgent with an async run() for pygbag."""

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
        self.ai_drag_start   = (r0, c0)
        self.ai_drag_end     = (r1, c1)
        self.ai_sel_clear_at = time.time() + 0.2
        _, no_moves = self.ai_game.apply_move(r0, c0, r1, c1)
        if no_moves:
            self.ai_over = True

    async def run(self):
        await self._init_model()

        self.clock.tick()
        while True:
            dt = self.clock.tick(FPS) / 1000.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return

                if event.type == pygame_gui.UI_BUTTON_PRESSED:
                    if event.ui_element == self.menu_btn:
                        return
                    if event.ui_element == self.restart_btn:
                        self.reset()
                    if event.ui_element == self.toggle_btn:
                        self.ai_board_visible = not self.ai_board_visible
                    if event.ui_element == self.pause_btn and not self.game_over:
                        self.human_game.toggle_pause()
                        self.drag_start = self.drag_end = None
                        if not self.human_game.paused:
                            self.last_ai_move = time.time() + AI_INTERVAL

                if event.type == pygame.KEYDOWN:
                    if event.key == fruitbox_config.get("key_menu"):
                        return
                    if event.key == fruitbox_config.get("key_restart"):
                        self.reset()
                    if event.key == fruitbox_config.get("key_pause") and not self.game_over:
                        self.human_game.toggle_pause()
                        self.drag_start = self.drag_end = None
                        if not self.human_game.paused:
                            self.last_ai_move = time.time() + AI_INTERVAL

                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if self.game_over and self.show_game_over:
                        if not self._game_over_card_rect.collidepoint(event.pos):
                            self.show_game_over = False
                        elif self.close_over_rect.collidepoint(event.pos):
                            self.show_game_over = False
                        elif self._restart_over_rect.collidepoint(event.pos):
                            self.reset()
                    else:
                        if self.game_over or (not self.human_over and not self.human_game.paused):
                            cell = self._pixel_to_cell(*event.pos)
                            if cell:
                                self.drag_start = self.drag_end = cell

                if event.type == pygame.MOUSEMOTION and self.drag_start:
                    if self.game_over or (not self.human_over and not self.human_game.paused):
                        cell = self._pixel_to_cell(*event.pos)
                        if cell:
                            self.drag_end = cell

                if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                    if not self.game_over and not self.human_over and not self.human_game.paused:
                        bounds = self._selection_bounds()
                        if bounds:
                            _, no_moves = self.human_game.apply_move(*bounds)
                            if no_moves:
                                self.human_over = True
                    self.drag_start = self.drag_end = None

                self.ui.process_events(event)

            if not self.game_over:
                timed_out = self.human_game.tick(dt)
                if not self.human_game.paused:
                    self.ai_game.elapsed = self.human_game.elapsed

                if timed_out:
                    self.human_over = self.ai_over = True

                now = time.time()

                if not self.ai_over and not self.human_game.paused and now >= self.last_ai_move:
                    self.last_ai_move = now + AI_INTERVAL
                    await self._step_ai_async()

                if now >= self.ai_sel_clear_at:
                    self.ai_drag_start = self.ai_drag_end = None

                if self.human_over and self.ai_over:
                    self.game_over = True
                    h, a = self.human_game.score, self.ai_game.score
                    opp  = {"solver": "Solver", "rl_model": "RL Model", "onnx": "ONNX"}.get(self.opponent, self.opponent)
                    if   h > a: self.over_reason = f"You win!  {h} – {a}"
                    elif a > h: self.over_reason = f"{opp} wins!  {h} – {a}"
                    else:       self.over_reason = f"Tie!  {h} – {a}"
                    self.pause_btn.disable()
                    if not self._result_recorded:
                        fruitbox_stats.record(fruitbox_stats.GameInfo(
                            gamemode="vs_ai",
                            grid_type=self.grid_type,
                            self_score=h,
                            opp_score=a,
                            time_elapsed=time.time() - self._game_start,
                            seed=self.human_game.seed,
                        ))
                        self.stats = fruitbox_stats.get_vs_stats()
                        self._result_recorded = True

            if self.human_game.paused:
                self._pause_alpha = min(255.0, self._pause_alpha + dt * 800)
            else:
                self._pause_alpha = 0.0

            self.screen.fill(fruitbox_colors.C["BG"])
            self._draw_hud()
            self._draw_board(self.human_game, self._human_x(), self.drag_start, self.drag_end)
            if self.human_game.paused:
                self._draw_paused()

            if self.opponent == "solver" and not self._solver_ready:
                self._draw_thinking()
            elif self.ai_board_visible:
                self._draw_board(self.ai_game, self._ai_x(), self.ai_drag_start, self.ai_drag_end)
            else:
                ai_cover = pygame.Rect(self._ai_x(), HUD_H + PADDING, BOARD_W, BOARD_H)
                pygame.draw.rect(self.screen, (0, 0, 0), ai_cover)

            self.ui.update(dt)
            self.ui.draw_ui(self.screen)

            icon  = self._icon_play if self.human_game.paused else self._icon_pause
            btn_r = self.pause_btn.get_abs_rect()
            self.screen.blit(icon, icon.get_rect(center=btn_r.center))

            btn_r = self.restart_btn.get_abs_rect()
            self.screen.blit(self._icon_restart, self._icon_restart.get_rect(center=btn_r.center))

            icon_eye = self._icon_eye_slash if self.ai_board_visible else self._icon_eye
            btn_r = self.toggle_btn.get_abs_rect()
            self.screen.blit(icon_eye, icon_eye.get_rect(center=btn_r.center))

            if self.game_over and self.show_game_over:
                self._draw_game_over()

            pygame.display.flip()
            await asyncio.sleep(0)
