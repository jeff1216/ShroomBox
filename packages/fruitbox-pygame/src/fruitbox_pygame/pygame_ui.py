import pygame
import pygame_gui
import sys
import time
import os
from fruitbox_core import stats as fruitbox_stats
from . import config as fruitbox_config
from . import colors as fruitbox_colors
from fruitbox_core.game import FruitBoxGame

# ── layout constants ──────────────────────────────────────────────
CELL    = 52
PADDING = 16
HUD_H   = 72
COLS    = 17
ROWS    = 10

WIN_W = COLS * CELL + PADDING * 2
WIN_H = ROWS * CELL + PADDING * 2 + HUD_H


def game_window_size(rows, cols):
    return (cols * CELL + PADDING * 2, rows * CELL + PADDING * 2 + HUD_H)

FPS = 60

# ── palette ───────────────────────────────────────────────────────
BG           = (245, 243, 238)
CELL_BG      = (255, 255, 255)
CELL_BORDER  = (210, 208, 200)
CLEARED_BG   = (230, 228, 222)

SEL_FILL     = (55,  138, 221, 60)
SEL_BORDER   = (24,   95, 165)
INVALID_FILL = (226,  75,  74, 60)
INVALID_BOR  = (163,  45,  45)
VALID_FILL   = (29,  158, 117, 60)
VALID_BOR    = (15,  110,  86)

TEXT_PRIMARY   = (44,  44,  42)
TEXT_SECONDARY = (95,  94,  90)
TEXT_CLEARED   = (180, 178, 170)

TIMER_OK     = (15,  110,  86)
TIMER_WARN   = (186, 117,  23)
TIMER_DANGER = (163,  45,  45)

BTN_COLOR        = (210, 208, 200)
BTN_HOVER_COLOR  = (190, 188, 180)
BTN_BORDER_COLOR = (160, 158, 150)

_BASE_DIR   = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
_ASSETS     = os.path.join(_BASE_DIR, "assets")
_THEME      = os.path.join(_ASSETS, "theme.json")
_THEME_DARK = os.path.join(_ASSETS, "theme_dark.json")


def get_theme():
    return _THEME_DARK if fruitbox_colors.is_dark() else _THEME

# HUD button layout
_BTN_H  = 34
_BTN_Y  = (HUD_H - _BTN_H) // 2   # 23
_BTN_X0 = PADDING + 90              # 106  (score area ends around x=80)

_PAUSE_W   = 34
_MENU_W    = 56
_RESTART_W = 34


def draw_rounded_rect(surf, color, rect, radius=8):
    pygame.draw.rect(surf, color, rect, border_radius=radius)


def draw_rounded_rect_border(surf, color, rect, width=1, radius=8):
    pygame.draw.rect(surf, color, rect, width=width, border_radius=radius)


class FruitBoxPygame:
    def __init__(self, game=None, screen=None, gamemode="single_player", restart_seed=None):
        self.game         = game if game is not None else FruitBoxGame()
        self.gamemode     = gamemode
        self._restart_seed = restart_seed
        if game is None:
            self.game.reset()

        self._win_w, self._win_h = game_window_size(self.game.rows, self.game.columns)

        if screen is None:
            pygame.init()
            self.screen = pygame.display.set_mode((self._win_w, self._win_h))
        else:
            self.screen = screen
        pygame.display.set_caption("Fruit Box")
        self.clock = pygame.time.Clock()

        self.font_num      = pygame.font.SysFont("Arial", 22, bold=True)
        self.font_score    = pygame.font.SysFont("Arial", 20, bold=True)
        self.font_label    = pygame.font.SysFont("Arial", 13)
        self.font_over     = pygame.font.SysFont("Arial", 36, bold=True)
        self.font_over_sub = pygame.font.SysFont("Arial", 18)

        self.drag_start = None
        self.drag_end   = None
        self.sel_valid  = False

        self.game_over        = False
        self.over_reason      = ""
        self._game_start      = time.time()
        self._result_recorded = False
        self.show_game_over         = True
        self.close_over_rect        = pygame.Rect(0, 0, 0, 0)
        self._game_over_card_rect   = pygame.Rect(0, 0, 0, 0)
        self._restart_over_rect     = pygame.Rect(0, 0, 0, 0)
        self._pause_alpha           = 0.0

        self.overlay = pygame.Surface((self._win_w, self._win_h), pygame.SRCALPHA)

        # ── pygame_gui ────────────────────────────────────────────
        self.ui = pygame_gui.UIManager((self._win_w, self._win_h), get_theme())

        _icon_sz = _BTN_H - 8
        self._icon_pause   = fruitbox_colors.load_icon(os.path.join(_ASSETS, "pause.circle.png"), _icon_sz)
        self._icon_play    = fruitbox_colors.load_icon(os.path.join(_ASSETS, "play.circle.png"), _icon_sz)
        self._icon_restart = fruitbox_colors.load_icon(os.path.join(_ASSETS, "arrow.counterclockwise.circle.png"), _icon_sz)

        bx = _BTN_X0
        self.menu_btn = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(bx, _BTN_Y, _MENU_W, _BTN_H),
            text="Menu",
            manager=self.ui,
        )
        bx += _MENU_W + 8
        self.pause_btn = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(bx, _BTN_Y, _PAUSE_W, _BTN_H),
            text="",
            manager=self.ui,
        )
        bx += _PAUSE_W + 8
        self.restart_btn = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(bx, _BTN_Y, _RESTART_W, _BTN_H),
            text="",
            manager=self.ui,
        )

    # ── geometry ──────────────────────────────────────────────────

    def cell_rect(self, row, col):
        x = PADDING + col * CELL
        y = HUD_H + PADDING + row * CELL
        return pygame.Rect(x, y, CELL - 1, CELL - 1)

    def pixel_to_cell(self, px, py):
        col = (px - PADDING) // CELL
        row = (py - HUD_H - PADDING) // CELL
        if 0 <= row < self.game.rows and 0 <= col < self.game.columns:
            return row, col
        return None

    def selection_bounds(self):
        if self.drag_start is None or self.drag_end is None:
            return None
        r1 = min(self.drag_start[0], self.drag_end[0])
        c1 = min(self.drag_start[1], self.drag_end[1])
        r2 = max(self.drag_start[0], self.drag_end[0])
        c2 = max(self.drag_start[1], self.drag_end[1])
        return r1, c1, r2, c2

    # ── drawing ───────────────────────────────────────────────────

    def draw_hud(self):
        C = fruitbox_colors.C
        pygame.draw.rect(self.screen, C["HUD_BG"], (0, 0, self._win_w, HUD_H))
        pygame.draw.line(self.screen, C["CELL_BORDER"], (0, HUD_H), (self._win_w, HUD_H), 1)

        self.screen.blit(self.font_label.render("SCORE", True, C["TEXT_SECONDARY"]), (PADDING, 12))
        self.screen.blit(self.font_score.render(str(self.game.score), True, C["TEXT_PRIMARY"]), (PADDING, 28))

        t    = self.game.time_remaining
        tcol = C["TIMER_OK"] if t > 30 else (C["TIMER_WARN"] if t > 10 else C["TIMER_DANGER"])

        bar_w  = 180
        bar_x  = self._win_w - PADDING - bar_w
        bar_y  = 48
        bar_h  = 6
        fill_w = int(bar_w * (t / self.game.time_limit))
        pygame.draw.rect(self.screen, C["CELL_BORDER"], (bar_x, bar_y, bar_w, bar_h), border_radius=3)
        pygame.draw.rect(self.screen, tcol,             (bar_x, bar_y, fill_w, bar_h), border_radius=3)

        self.screen.blit(self.font_label.render("TIME", True, C["TEXT_SECONDARY"]), (bar_x, 12))
        self.screen.blit(self.font_score.render(f"{int(t):d}s", True, tcol),        (bar_x, 28))

    def draw_grid(self):
        C      = fruitbox_colors.C
        bounds = self.selection_bounds()

        for row in range(self.game.rows):
            for col in range(self.game.columns):
                rect    = self.cell_rect(row, col)
                val     = self.game.grid[row][col]
                cleared = (val == -1)

                draw_rounded_rect(self.screen, C["CLEARED_BG"] if cleared else C["CELL_BG"], rect, radius=6)
                draw_rounded_rect_border(self.screen, C["CELL_BORDER"], rect, width=1, radius=6)

                if not cleared:
                    num_surf = self.font_num.render(str(val), True, C["TEXT_PRIMARY"])
                    self.screen.blit(num_surf, (
                        rect.x + (CELL - 1 - num_surf.get_width())  // 2,
                        rect.y + (CELL - 1 - num_surf.get_height()) // 2,
                    ))

        if bounds:
            r1, c1, r2, c2 = bounds
            self.sel_valid = self.game.validate_move(r1, c1, r2, c2)
            tl  = self.cell_rect(r1, c1)
            br  = self.cell_rect(r2, c2)
            sel = pygame.Rect(tl.x, tl.y, br.right - tl.x, br.bottom - tl.y)
            self.overlay.fill((0, 0, 0, 0))
            pygame.draw.rect(self.overlay, C["VALID_FILL"] if self.sel_valid else C["SEL_FILL"], sel, border_radius=8)
            self.screen.blit(self.overlay, (0, 0))
            pygame.draw.rect(self.screen, C["VALID_BOR"] if self.sel_valid else C["SEL_BORDER"], sel, width=2, border_radius=8)

    def draw_paused(self):
        C         = fruitbox_colors.C
        alpha     = int(self._pause_alpha)
        grid_rect = pygame.Rect(PADDING, HUD_H + PADDING, self.game.columns * CELL, self.game.rows * CELL)
        bg = pygame.Surface((grid_rect.width, grid_rect.height))
        bg.fill(C["PAUSE_COVER"])
        bg.set_alpha(alpha)
        self.screen.blit(bg, (grid_rect.x, grid_rect.y))
        font_p = pygame.font.SysFont("Arial", 36, bold=True)
        surf   = font_p.render("Paused", True, C["TEXT_PRIMARY"])
        surf.set_alpha(alpha)
        self.screen.blit(surf, (
            grid_rect.x + (grid_rect.width  - surf.get_width())  // 2,
            grid_rect.y + (grid_rect.height - surf.get_height()) // 2,
        ))

    def draw_game_over(self):
        C = fruitbox_colors.C
        dim = pygame.Surface((self._win_w, self._win_h), pygame.SRCALPHA)
        dim.fill(C["DIM"])
        self.screen.blit(dim, (0, 0))

        card_w, card_h = 340, 210
        card_x = (self._win_w - card_w) // 2
        card_y = (self._win_h - card_h) // 2
        card   = pygame.Rect(card_x, card_y, card_w, card_h)
        self._game_over_card_rect = card
        draw_rounded_rect(self.screen, C["CARD_BG"], card, radius=14)
        draw_rounded_rect_border(self.screen, C["CARD_BORDER"], card, width=1, radius=14)

        self.screen.blit(self.font_over.render("Game over", True, C["TEXT_PRIMARY"]),
                         (card_x + (card_w - self.font_over.size("Game over")[0]) // 2, card_y + 28))
        self.screen.blit(self.font_over_sub.render(self.over_reason, True, C["TEXT_SECONDARY"]),
                         (card_x + (card_w - self.font_over_sub.size(self.over_reason)[0]) // 2, card_y + 78))
        score_text = f"Final score: {self.game.score}"
        self.screen.blit(self.font_score.render(score_text, True, C["TEXT_PRIMARY"]),
                         (card_x + (card_w - self.font_score.size(score_text)[0]) // 2, card_y + 110))

        font_btn = pygame.font.SysFont("Arial", 13, bold=True)
        mouse    = pygame.mouse.get_pos()

        r_surf = font_btn.render("Restart", True, C["TEXT_PRIMARY"])
        r_px, r_py = 20, 8
        r_w = r_surf.get_width()  + r_px * 2
        r_h = r_surf.get_height() + r_py * 2
        self._restart_over_rect = pygame.Rect(card_x + (card_w - r_w) // 2, card_y + 156, r_w, r_h)
        r_hov = self._restart_over_rect.collidepoint(mouse)
        pygame.draw.rect(self.screen, C["BTN_HOV"] if r_hov else C["BTN"], self._restart_over_rect, border_radius=6)
        pygame.draw.rect(self.screen, C["BTN_BORDER"], self._restart_over_rect, width=1, border_radius=6)
        self.screen.blit(r_surf, (self._restart_over_rect.x + r_px, self._restart_over_rect.y + r_py))

        x_surf = font_btn.render("X", True, C["TEXT_SECONDARY"])
        x_pad  = 6
        x_w    = x_surf.get_width()  + x_pad * 2
        x_h    = x_surf.get_height() + x_pad * 2
        self.close_over_rect = pygame.Rect(card_x + card_w - x_w - 8, card_y + 8, x_w, x_h)
        if self.close_over_rect.collidepoint(mouse):
            pygame.draw.rect(self.screen, C["BTN_CLOSE_HOV"], self.close_over_rect, border_radius=5)
        self.screen.blit(x_surf, (self.close_over_rect.x + x_pad, self.close_over_rect.y + x_pad))

    # ── state ─────────────────────────────────────────────────────

    def restart(self):
        self.game.reset(seed=self._restart_seed)
        self.game.paused      = False
        self.drag_start       = None
        self.drag_end         = None
        self.sel_valid        = False
        self.game_over        = False
        self.over_reason      = ""
        self.show_game_over   = True
        self._game_start      = time.time()
        self._result_recorded = False
        self._pause_alpha     = 0.0
        self.pause_btn.enable()

    # ── main loop ─────────────────────────────────────────────────

    def run(self):
        while True:
            dt = self.clock.tick(FPS) / 1000.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()

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


if __name__ == "__main__":
    FruitBoxPygame().run()
