import os
import sys
import pygame
import pygame_gui

from fruitbox_game import FruitBoxGame
from fruitbox_settings import SettingsOverlay
from fruitbox_stats_screen import StatsOverlay
from fruitbox_pygame import (
    FruitBoxPygame,
    WIN_W as GAME_W, WIN_H as GAME_H,
    BG, TEXT_PRIMARY, TEXT_SECONDARY,
    _THEME, _ASSETS,
)

MENU_W = GAME_W
MENU_H = GAME_H

ACCENT       = (24,  95, 165)

GRID_TYPES = ["random", "solvable"]

# card button dimensions (Single Player / vs AI)
_CARD_W = 280
_CARD_H = 80
_CARD_Y = 240

# top-right buttons
_TOP_BTN_Y = 14


class FruitBoxMenu:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((MENU_W, MENU_H))
        pygame.display.set_caption("Fruit Box")
        self.clock       = pygame.time.Clock()
        self.font_title  = pygame.font.SysFont("Arial", 52, bold=True)
        self.font_hint   = pygame.font.SysFont("Arial", 12)
        self.font_toggle = pygame.font.SysFont("Arial", 20, bold=True)
        self.font_label  = pygame.font.SysFont("Arial", 15)
        self.font_btn    = pygame.font.SysFont("Arial", 13)

        _raw = pygame.image.load(os.path.join(_ASSETS, "arrowtriangle.left.fill.png")).convert_alpha()
        self._icon_arr_l = pygame.transform.smoothscale(_raw, (32, 32))
        _raw = pygame.image.load(os.path.join(_ASSETS, "arrowtriangle.right.fill.png")).convert_alpha()
        self._icon_arr_r = pygame.transform.smoothscale(_raw, (32, 32))

        self.grid_type_idx    = 0
        self.left_arrow_rect  = pygame.Rect(0, 0, 0, 0)
        self.right_arrow_rect = pygame.Rect(0, 0, 0, 0)

        self.settings       = SettingsOverlay()
        self.stats_overlay  = StatsOverlay()

        # ── pygame_gui ────────────────────────────────────────────
        self.ui = pygame_gui.UIManager((MENU_W, MENU_H), _THEME)

        # Mode card buttons (side by side, centred)
        card_gap = 24
        cards_x  = (MENU_W - _CARD_W * 2 - card_gap) // 2

        self.sp_btn = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(cards_x, _CARD_Y, _CARD_W, _CARD_H),
            text="Single Player",
            manager=self.ui,
            object_id="#card_btn",
        )
        self.vs_btn = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(cards_x + _CARD_W + card_gap, _CARD_Y, _CARD_W, _CARD_H),
            text="vs AI",
            manager=self.ui,
            object_id="#card_btn",
        )

        # Top-right icon buttons (Settings + Stats), both square
        s_h  = 32
        s_x  = MENU_W - s_h - 14
        st_x = s_x - s_h - 8

        _raw = pygame.image.load(os.path.join(_ASSETS, "gearshape.png")).convert_alpha()
        self._icon_settings = pygame.transform.smoothscale(_raw, (s_h - 6, s_h - 6))
        _raw = pygame.image.load(os.path.join(_ASSETS, "waveform.path.ecg.png")).convert_alpha()
        self._icon_stats    = pygame.transform.smoothscale(_raw, (s_h - 6, s_h - 6))

        self.settings_btn = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(s_x, _TOP_BTN_Y, s_h, s_h),
            text="",
            manager=self.ui,
            object_id="#top_btn",
        )
        self.stats_btn = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(st_x, _TOP_BTN_Y, s_h, s_h),
            text="",
            manager=self.ui,
            object_id="#top_btn",
        )

        # Hidden watch-AI button (bottom-right corner, small)
        self.watch_btn_rect = pygame.Rect(MENU_W - 60, MENU_H - 30, 60, 30)

    @property
    def grid_type(self):
        return GRID_TYPES[self.grid_type_idx]

    # ── drawing ───────────────────────────────────────────────────

    def _draw(self, dt):
        self.screen.fill(BG)

        # title
        title = self.font_title.render("Fruit Box", True, TEXT_PRIMARY)
        self.screen.blit(title, ((MENU_W - title.get_width()) // 2, 100))

        # grid type selector
        gt_cy = _CARD_Y + _CARD_H + 60

        pill_surf  = self.font_toggle.render(self.grid_type.capitalize(), True, ACCENT)
        pill_pad_x, pill_pad_y = 28, 12
        pill_w = max(pill_surf.get_width() + pill_pad_x * 2, 180)
        pill_h = pill_surf.get_height() + pill_pad_y * 2

        arr_click_w = self._icon_arr_l.get_width() + 24
        spacing     = 18

        total_w = arr_click_w + spacing + pill_w + spacing + arr_click_w
        x = (MENU_W - total_w) // 2

        self.left_arrow_rect = pygame.Rect(x, gt_cy - pill_h // 2, arr_click_w, pill_h)
        self.screen.blit(self._icon_arr_l, self._icon_arr_l.get_rect(center=(x + arr_click_w // 2, gt_cy)))
        x += arr_click_w + spacing

        pill_rect = pygame.Rect(x, gt_cy - pill_h // 2, pill_w, pill_h)
        pygame.draw.rect(self.screen, (220, 235, 255), pill_rect, border_radius=20)
        pygame.draw.rect(self.screen, ACCENT, pill_rect, width=2, border_radius=20)
        self.screen.blit(pill_surf, (
            x + (pill_w - pill_surf.get_width())  // 2,
            gt_cy - pill_surf.get_height() // 2,
        ))
        x += pill_w + spacing

        self.right_arrow_rect = pygame.Rect(x, gt_cy - pill_h // 2, arr_click_w, pill_h)
        self.screen.blit(self._icon_arr_r, self._icon_arr_r.get_rect(center=(x + arr_click_w // 2, gt_cy)))

        # bottom hint
        hint = self.font_hint.render("Press ESC during a game to return here", True, TEXT_SECONDARY)
        self.screen.blit(hint, ((MENU_W - hint.get_width()) // 2, MENU_H - 26))

        overlay_open = self.settings.visible or self.stats_overlay.visible
        for btn in (self.sp_btn, self.vs_btn, self.settings_btn, self.stats_btn):
            if overlay_open and btn.is_enabled:
                btn.disable()
            elif not overlay_open and not btn.is_enabled:
                btn.enable()

        self.ui.update(dt)
        self.ui.draw_ui(self.screen)

        btn_r = self.settings_btn.get_abs_rect()
        self.screen.blit(self._icon_settings, self._icon_settings.get_rect(center=btn_r.center))
        btn_r = self.stats_btn.get_abs_rect()
        self.screen.blit(self._icon_stats, self._icon_stats.get_rect(center=btn_r.center))

        # Overlays drawn after ui.draw_ui so they appear on top of the card buttons
        self.settings.draw(self.screen)
        self.stats_overlay.draw(self.screen)

        pygame.display.flip()

    # ── menu loop ─────────────────────────────────────────────────

    def _menu_loop(self):
        while True:
            dt = self.clock.tick(60) / 1000.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()

                # Overlays consume events when visible
                if self.settings.handle_event(event):
                    self.ui.process_events(event)
                    continue
                if self.stats_overlay.handle_event(event):
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

                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if self.left_arrow_rect.collidepoint(event.pos):
                        self.grid_type_idx = (self.grid_type_idx - 1) % len(GRID_TYPES)
                    elif self.right_arrow_rect.collidepoint(event.pos):
                        self.grid_type_idx = (self.grid_type_idx + 1) % len(GRID_TYPES)
                    elif self.watch_btn_rect.collidepoint(event.pos):
                        return "watch_ai"

                self.ui.process_events(event)

            self._draw(dt)

    # ── helpers ───────────────────────────────────────────────────

    @staticmethod
    def _resize_keep_top(w, h):
        """Resize the window: horizontally centered on the old window, top edge fixed."""
        try:
            import ctypes, ctypes.wintypes
            hwnd = pygame.display.get_wm_info()["window"]
            rect = ctypes.wintypes.RECT()
            ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
            cx = (rect.left + rect.right) // 2
            y  = rect.top
            screen = pygame.display.set_mode((w, h))
            hwnd = pygame.display.get_wm_info()["window"]
            ctypes.windll.user32.SetWindowPos(
                hwnd, 0, cx - w // 2, y, 0, 0,
                0x0001 | 0x0004,
            )
            return screen
        except Exception:
            return pygame.display.set_mode((w, h))

    # ── launchers ─────────────────────────────────────────────────

    def _launch(self, mode):
        if mode == "single_player":
            game = FruitBoxGame(grid_type=self.grid_type)
            game.reset()
            screen = pygame.display.set_mode((GAME_W, GAME_H))
            FruitBoxPygame(game=game, screen=screen).run()
            self.screen = pygame.display.set_mode((MENU_W, MENU_H))

        elif mode == "vs_ai":
            loading_surf = pygame.font.SysFont("Arial", 21, bold=True).render(
                "Loading model…", True, TEXT_SECONDARY)
            self.screen.fill(BG)
            self.screen.blit(loading_surf, (
                (MENU_W - loading_surf.get_width())  // 2,
                (MENU_H - loading_surf.get_height()) // 2,
            ))
            pygame.display.flip()

            from fruitbox_vs import FruitBoxVs, WIN_W as VS_W, WIN_H as VS_H
            screen = self._resize_keep_top(VS_W, VS_H)
            screen.fill(BG)
            screen.blit(loading_surf, (
                (VS_W - loading_surf.get_width())  // 2,
                (VS_H - loading_surf.get_height()) // 2,
            ))
            pygame.display.flip()
            FruitBoxVs(opponent="rl_model", screen=screen, grid_type=self.grid_type).run()
            self.screen = self._resize_keep_top(MENU_W, MENU_H)

        elif mode == "watch_ai":
            loading_surf = pygame.font.SysFont("Arial", 21, bold=True).render(
                "Loading model…", True, TEXT_SECONDARY)
            self.screen.fill(BG)
            self.screen.blit(loading_surf, (
                (MENU_W - loading_surf.get_width())  // 2,
                (MENU_H - loading_surf.get_height()) // 2,
            ))
            pygame.display.flip()

            from fruitbox_ai_watch import FruitBoxAiWatch
            screen = pygame.display.set_mode((GAME_W, GAME_H))
            screen.fill(BG)
            screen.blit(loading_surf, (
                (GAME_W - loading_surf.get_width())  // 2,
                (GAME_H - loading_surf.get_height()) // 2,
            ))
            pygame.display.flip()
            FruitBoxAiWatch(screen=screen, grid_type=self.grid_type).run()
            self.screen = pygame.display.set_mode((MENU_W, MENU_H))

    # ── main ──────────────────────────────────────────────────────

    def run(self):
        while True:
            mode = self._menu_loop()
            self._launch(mode)


if __name__ == "__main__":
    FruitBoxMenu().run()
