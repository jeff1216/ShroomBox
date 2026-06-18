import asyncio
import time
import pygame
import pygame_gui

from fruitbox_pygame.pygame_ui import FruitBoxPygame, FPS
from fruitbox_pygame import colors as fruitbox_colors
from fruitbox_core import stats as fruitbox_stats
from fruitbox_pygame import config as fruitbox_config


class WebPlay(FruitBoxPygame):
    """FruitBoxPygame with an async run() for pygbag."""

    async def run(self):
        while True:
            dt = self.clock.tick(FPS) / 1000.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return

                if event.type == pygame_gui.UI_BUTTON_PRESSED:
                    if event.ui_element == self.menu_btn:
                        return
                    if event.ui_element == self.restart_btn:
                        self.restart()
                    if event.ui_element == self.pause_btn and not self.game_over:
                        self.game.toggle_pause()
                        self.drag_start = self.drag_end = None

                if event.type == pygame.KEYDOWN:
                    if event.key == fruitbox_config.get("key_menu"):
                        return
                    if event.key == fruitbox_config.get("key_restart"):
                        self.restart()
                    if event.key == fruitbox_config.get("key_pause") and not self.game_over:
                        self.game.toggle_pause()
                        self.drag_start = self.drag_end = None

                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if self.game_over and self.show_game_over:
                        if self.close_over_rect.collidepoint(event.pos):
                            self.show_game_over = False
                        elif self._restart_over_rect.collidepoint(event.pos):
                            self.restart()
                    else:
                        if self.game_over or not self.game.paused:
                            cell = self.pixel_to_cell(*event.pos)
                            if cell:
                                self.drag_start = cell
                                self.drag_end   = cell

                if event.type == pygame.MOUSEMOTION and self.drag_start:
                    if self.game_over or not self.game.paused:
                        cell = self.pixel_to_cell(*event.pos)
                        if cell:
                            self.drag_end = cell

                if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                    if not self.game_over and not self.game.paused:
                        bounds = self.selection_bounds()
                        if bounds:
                            r1, c1, r2, c2 = bounds
                            _, no_moves = self.game.apply_move(r1, c1, r2, c2)
                            if no_moves:
                                self.game_over   = True
                                self.over_reason = "No more valid moves"
                                self.pause_btn.disable()
                                if not self._result_recorded:
                                    fruitbox_stats.record(fruitbox_stats.GameInfo(
                                        gamemode=self.gamemode,
                                        grid_type=self.game.grid_type,
                                        self_score=self.game.score,
                                        time_elapsed=time.time() - self._game_start,
                                        seed=self.game.seed,
                                    ))
                                    self._result_recorded = True
                    self.drag_start = None
                    self.drag_end   = None

                self.ui.process_events(event)

            if not self.game_over:
                timed_out = self.game.tick(dt)
                if timed_out:
                    self.game_over   = True
                    self.over_reason = "Time's up!"
                    self.pause_btn.disable()
                    if not self._result_recorded:
                        fruitbox_stats.record(fruitbox_stats.GameInfo(
                            gamemode="single_player",
                            grid_type=self.game.grid_type,
                            self_score=self.game.score,
                            time_elapsed=time.time() - self._game_start,
                            seed=self.game.seed,
                        ))
                        self._result_recorded = True

            if self.game.paused:
                self._pause_alpha = min(255.0, self._pause_alpha + dt * 800)
            else:
                self._pause_alpha = 0.0

            self.screen.fill(fruitbox_colors.C["BG"])
            self.draw_hud()
            self.draw_grid()
            if self.game.paused:
                self.draw_paused()

            self.ui.update(dt)
            self.ui.draw_ui(self.screen)

            icon  = self._icon_play if self.game.paused else self._icon_pause
            btn_r = self.pause_btn.get_abs_rect()
            self.screen.blit(icon, icon.get_rect(center=btn_r.center))

            btn_r = self.restart_btn.get_abs_rect()
            self.screen.blit(self._icon_restart, self._icon_restart.get_rect(center=btn_r.center))

            if self.game_over and self.show_game_over:
                self.draw_game_over()

            pygame.display.flip()
            await asyncio.sleep(0)
