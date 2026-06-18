import asyncio
import sys
import pygame
import pygame_gui

from fruitbox_pygame.menu import FruitBoxMenu, MENU_W, MENU_H, GRID_TYPES
from fruitbox_pygame.pygame_ui import FruitBoxPygame, WIN_W as GAME_W, WIN_H as GAME_H, game_window_size
from fruitbox_core.game import FruitBoxGame
from fruitbox_pygame import colors as fruitbox_colors
from fruitbox_pygame import config as fruitbox_config

from .play  import WebPlay
from .watch import WebAiWatch
from .vs    import WebVs
from fruitbox_pygame.vs import WIN_W as VS_W, WIN_H as VS_H


class WebMenu(FruitBoxMenu):
    """
    FruitBoxMenu with async game-loop and async launchers.
    'vs AI' uses OnnxAgent instead of MaskablePPO.
    """

    async def _menu_loop_async(self) -> str:
        """Async version of _menu_loop(). Returns a mode string."""
        while True:
            dt = self.clock.tick(60) / 1000.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return "quit"

                if self.settings.handle_event(event):
                    self.ui.process_events(event)
                    continue
                if self.stats_overlay.handle_event(event):
                    self.ui.process_events(event)
                    continue
                if self.help_overlay.handle_event(event):
                    self.ui.process_events(event)
                    continue
                if self.custom_overlay.handle_event(event):
                    self.ui.process_events(event)
                    continue

                if event.type == pygame_gui.UI_BUTTON_PRESSED:
                    if event.ui_element == self.sp_btn:
                        return "single_player"
                    if event.ui_element == self.vs_btn:
                        return "vs_ai"
                    if event.ui_element == self.settings_btn:
                        self.settings.toggle()
                    if event.ui_element == self.stats_btn:
                        self.stats_overlay.toggle()
                    if event.ui_element == self.help_btn:
                        self.help_overlay.toggle()
                    if event.ui_element == self.dm_btn:
                        fruitbox_colors.set_dark(not fruitbox_colors.is_dark())
                        self.stats_overlay.reload_theme()
                        self.custom_overlay.reload_theme()
                        self._build_ui()
                    if event.ui_element == self.watch_btn:
                        return "watch_ai"

                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if self.left_arrow_rect.collidepoint(event.pos):
                        self.grid_type_idx = (self.grid_type_idx - 1) % len(GRID_TYPES)
                    elif self.right_arrow_rect.collidepoint(event.pos):
                        self.grid_type_idx = (self.grid_type_idx + 1) % len(GRID_TYPES)
                    elif self.gear_btn_rect.collidepoint(event.pos):
                        self.custom_overlay.toggle()

                self.ui.process_events(event)

            self._draw(dt)
            await asyncio.sleep(0)

    def _show_loading(self, w, h):
        C = fruitbox_colors.C
        surf = pygame.font.SysFont("Arial", 21, bold=True).render(
            "Loading model…", True, C["TEXT_SECONDARY"])
        self.screen.fill(C["BG"])
        self.screen.blit(surf, ((w - surf.get_width()) // 2, (h - surf.get_height()) // 2))
        pygame.display.flip()

    async def _launch_async(self, mode: str) -> None:
        if mode == "single_player":
            if self.grid_type == "custom":
                _s   = self.custom_overlay.get_settings()
                game = FruitBoxGame(rows=_s["rows"], columns=_s["cols"],
                                    grid_type=_s["grid_base"], time_limit=_s["time_limit"])
                game.reset(seed=_s["seed"])
                screen = self._resize_keep_top(*game_window_size(_s["rows"], _s["cols"]))
                _mode  = "Custom"
                _rseed = _s["seed"]
            else:
                game   = FruitBoxGame(grid_type=self.grid_type)
                game.reset()
                screen = self._resize_keep_top(GAME_W, GAME_H)
                _mode  = "single_player"
                _rseed = None
            await WebPlay(game=game, screen=screen, gamemode=_mode, restart_seed=_rseed).run()
            self.screen = self._resize_keep_top(MENU_W, MENU_H)

        elif mode == "vs_ai":
            self._show_loading(MENU_W, MENU_H)
            screen = self._resize_keep_top(VS_W, VS_H)
            self._show_loading(VS_W, VS_H)
            _gt = self.custom_overlay.get_settings()["grid_base"] if self.grid_type == "custom" else self.grid_type
            await WebVs(opponent="onnx", screen=screen, grid_type=_gt).run()
            self.screen = self._resize_keep_top(MENU_W, MENU_H)

        elif mode == "watch_ai":
            self._show_loading(MENU_W, MENU_H)
            screen = self._resize_keep_top(GAME_W, GAME_H)
            self._show_loading(GAME_W, GAME_H)
            _gt = self.custom_overlay.get_settings()["grid_base"] if self.grid_type == "custom" else self.grid_type
            await WebAiWatch(screen=screen, grid_type=_gt).run()
            self.screen = self._resize_keep_top(MENU_W, MENU_H)

    async def run(self):
        while True:
            mode = await self._menu_loop_async()
            if mode == "quit":
                return
            await self._launch_async(mode)
