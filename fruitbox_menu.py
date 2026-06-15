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
    _THEME,
)

MENU_W = GAME_W
MENU_H = GAME_H

ACCENT       = (24,  95, 165)
ARROW_COLOR  = (220, 130, 50)
ARROW_HOVER  = (180,  90, 20)

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
        self.font_toggle = pygame.font.SysFont("Arial", 15, bold=True)
        self.font_arrow  = pygame.font.SysFont("Arial", 22, bold=True)
        self.font_label  = pygame.font.SysFont("Arial", 15)
        self.font_btn    = pygame.font.SysFont("Arial", 13)

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

        # Top-right buttons  (Settings, then Stats to its left)
        btn_pad_x, btn_pad_y = 10, 5
        s_surf  = self.font_btn.render("Settings", True, TEXT_SECONDARY)
        s_w     = s_surf.get_width()  + btn_pad_x * 2
        s_h     = s_surf.get_height() + btn_pad_y * 2
        s_x     = MENU_W - s_w - 14

        st_surf = self.font_btn.render("Stats", True, TEXT_SECONDARY)
        st_w    = st_surf.get_width()  + btn_pad_x * 2
        st_h    = st_surf.get_height() + btn_pad_y * 2
        st_x    = s_x - st_w - 8

        self.settings_btn = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(s_x, _TOP_BTN_Y, s_w, s_h),
            text="Settings",
            manager=self.ui,
            object_id="#top_btn",
        )
        self.stats_btn = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(st_x, _TOP_BTN_Y, st_w, st_h),
            text="Stats",
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
        mouse = pygame.mouse.get_pos()

        # title
        title = self.font_title.render("Fruit Box", True, TEXT_PRIMARY)
        self.screen.blit(title, ((MENU_W - title.get_width()) // 2, 100))

        # grid type selector
        gt_cy = _CARD_Y + _CARD_H + 60

        pill_surf  = self.font_toggle.render(self.grid_type.capitalize(), True, ACCENT)
        pill_pad_x, pill_pad_y = 20, 8
        pill_w = max(pill_surf.get_width() + pill_pad_x * 2, 140)
        pill_h = pill_surf.get_height() + pill_pad_y * 2

        arr_l       = self.font_arrow.render("<", True, ARROW_COLOR)
        arr_r       = self.font_arrow.render(">", True, ARROW_COLOR)
        arr_click_w = arr_l.get_width() + 24
        spacing     = 18

        total_w = arr_click_w + spacing + pill_w + spacing + arr_click_w
        x = (MENU_W - total_w) // 2

        self.left_arrow_rect = pygame.Rect(x, gt_cy - pill_h // 2, arr_click_w, pill_h)
        l_hov = self.left_arrow_rect.collidepoint(mouse)
        self.screen.blit(
            self.font_arrow.render("<", True, ARROW_HOVER if l_hov else ARROW_COLOR),
            (x + 12, gt_cy - arr_l.get_height() // 2),
        )
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
        r_hov = self.right_arrow_rect.collidepoint(mouse)
        self.screen.blit(
            self.font_arrow.render(">", True, ARROW_HOVER if r_hov else ARROW_COLOR),
            (x + 12, gt_cy - arr_r.get_height() // 2),
        )

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
    def _center_window(w, h):
        try:
            import ctypes
            sizes = pygame.display.get_desktop_sizes()
            if sizes:
                sw, sh = sizes[0]
                hwnd = pygame.display.get_wm_info()["window"]
                ctypes.windll.user32.SetWindowPos(
                    hwnd, 0,
                    (sw - w) // 2, (sh - h) // 2,
                    0, 0,
                    0x0001 | 0x0004,  # SWP_NOSIZE | SWP_NOZORDER
                )
        except Exception:
            pass

    # ── launchers ─────────────────────────────────────────────────

    def _launch(self, mode):
        if mode == "single_player":
            game = FruitBoxGame(grid_type=self.grid_type)
            game.reset()
            screen = pygame.display.set_mode((GAME_W, GAME_H))
            self._center_window(GAME_W, GAME_H)
            FruitBoxPygame(game=game, screen=screen).run()
            self.screen = pygame.display.set_mode((MENU_W, MENU_H))
            self._center_window(MENU_W, MENU_H)

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
            screen = pygame.display.set_mode((VS_W, VS_H))
            self._center_window(VS_W, VS_H)
            screen.fill(BG)
            screen.blit(loading_surf, (
                (VS_W - loading_surf.get_width())  // 2,
                (VS_H - loading_surf.get_height()) // 2,
            ))
            pygame.display.flip()
            FruitBoxVs(opponent="rl_model", screen=screen, grid_type=self.grid_type).run()
            self.screen = pygame.display.set_mode((MENU_W, MENU_H))
            self._center_window(MENU_W, MENU_H)

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
            self._center_window(GAME_W, GAME_H)
            screen.fill(BG)
            screen.blit(loading_surf, (
                (GAME_W - loading_surf.get_width())  // 2,
                (GAME_H - loading_surf.get_height()) // 2,
            ))
            pygame.display.flip()
            FruitBoxAiWatch(screen=screen, grid_type=self.grid_type).run()
            self.screen = pygame.display.set_mode((MENU_W, MENU_H))
            self._center_window(MENU_W, MENU_H)

    # ── main ──────────────────────────────────────────────────────

    def run(self):
        while True:
            mode = self._menu_loop()
            self._launch(mode)


if __name__ == "__main__":
    FruitBoxMenu().run()
