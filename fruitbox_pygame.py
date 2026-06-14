import pygame
import pygame_gui
import sys
import time
import os
import fruitbox_stats
from fruitbox_game import FruitBoxGame

# ── layout constants ──────────────────────────────────────────────
CELL    = 52
PADDING = 16
HUD_H   = 72
COLS    = 17
ROWS    = 10

WIN_W = COLS * CELL + PADDING * 2
WIN_H = ROWS * CELL + PADDING * 2 + HUD_H

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

_THEME = os.path.join(
    getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))),
    "theme.json",
)

# HUD button layout
_BTN_H  = 26
_BTN_Y  = (HUD_H - _BTN_H) // 2   # 23
_BTN_X0 = PADDING + 90              # 106  (score area ends around x=80)

_PAUSE_W   = 34
_MENU_W    = 56
_RESTART_W = 70


def draw_rounded_rect(surf, color, rect, radius=8):
    pygame.draw.rect(surf, color, rect, border_radius=radius)


def draw_rounded_rect_border(surf, color, rect, width=1, radius=8):
    pygame.draw.rect(surf, color, rect, width=width, border_radius=radius)


class FruitBoxPygame:
    def __init__(self, game=None, screen=None):
        if screen is None:
            pygame.init()
            self.screen = pygame.display.set_mode((WIN_W, WIN_H))
        else:
            self.screen = screen
        pygame.display.set_caption("Fruit Box")
        self.clock = pygame.time.Clock()

        self.font_num      = pygame.font.SysFont("Arial", 22, bold=True)
        self.font_score    = pygame.font.SysFont("Arial", 20, bold=True)
        self.font_label    = pygame.font.SysFont("Arial", 13)
        self.font_over     = pygame.font.SysFont("Arial", 36, bold=True)
        self.font_over_sub = pygame.font.SysFont("Arial", 18)

        self.game = game if game is not None else FruitBoxGame()
        if game is None:
            self.game.reset()

        self.drag_start = None
        self.drag_end   = None
        self.sel_valid  = False

        self.game_over        = False
        self.over_reason      = ""
        self._game_start      = time.time()
        self._result_recorded = False
        self.show_game_over   = True
        self.close_over_rect  = pygame.Rect(0, 0, 0, 0)

        self.overlay = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)

        # ── pygame_gui ────────────────────────────────────────────
        self.ui = pygame_gui.UIManager((WIN_W, WIN_H), _THEME)

        bx = _BTN_X0
        self.pause_btn = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(bx, _BTN_Y, _PAUSE_W, _BTN_H),
            text="||",
            manager=self.ui,
        )
        bx += _PAUSE_W + 8
        self.menu_btn = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(bx, _BTN_Y, _MENU_W, _BTN_H),
            text="Menu",
            manager=self.ui,
        )
        bx += _MENU_W + 8
        self.restart_btn = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(bx, _BTN_Y, _RESTART_W, _BTN_H),
            text="Restart",
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
        if 0 <= row < ROWS and 0 <= col < COLS:
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
        pygame.draw.rect(self.screen, (235, 233, 226), (0, 0, WIN_W, HUD_H))
        pygame.draw.line(self.screen, CELL_BORDER, (0, HUD_H), (WIN_W, HUD_H), 1)

        self.screen.blit(self.font_label.render("SCORE", True, TEXT_SECONDARY), (PADDING, 12))
        self.screen.blit(self.font_score.render(str(self.game.score), True, TEXT_PRIMARY), (PADDING, 28))

        t    = self.game.time_remaining
        tcol = TIMER_OK if t > 30 else (TIMER_WARN if t > 10 else TIMER_DANGER)

        bar_w  = 180
        bar_x  = WIN_W - PADDING - bar_w
        bar_y  = 48
        bar_h  = 6
        fill_w = int(bar_w * (t / self.game.time_limit))
        pygame.draw.rect(self.screen, CELL_BORDER, (bar_x, bar_y, bar_w, bar_h), border_radius=3)
        pygame.draw.rect(self.screen, tcol,        (bar_x, bar_y, fill_w, bar_h), border_radius=3)

        self.screen.blit(self.font_label.render("TIME", True, TEXT_SECONDARY), (bar_x, 12))
        self.screen.blit(self.font_score.render(f"{int(t):d}s", True, tcol),   (bar_x, 28))

        new_pause_text = ">" if self.game.paused else "||"
        if self.pause_btn.text != new_pause_text:
            self.pause_btn.set_text(new_pause_text)

    def draw_grid(self):
        bounds = self.selection_bounds()

        for row in range(ROWS):
            for col in range(COLS):
                rect    = self.cell_rect(row, col)
                val     = self.game.grid[row][col]
                cleared = (val == -1)

                draw_rounded_rect(self.screen, CLEARED_BG if cleared else CELL_BG, rect, radius=6)
                draw_rounded_rect_border(self.screen, CELL_BORDER, rect, width=1, radius=6)

                if not cleared:
                    num_surf = self.font_num.render(str(val), True, TEXT_PRIMARY)
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
            pygame.draw.rect(self.overlay, VALID_FILL if self.sel_valid else SEL_FILL, sel, border_radius=8)
            self.screen.blit(self.overlay, (0, 0))
            pygame.draw.rect(self.screen, VALID_BOR if self.sel_valid else SEL_BORDER, sel, width=2, border_radius=8)

    def draw_paused(self):
        grid_rect = pygame.Rect(PADDING, HUD_H + PADDING, COLS * CELL, ROWS * CELL)
        pygame.draw.rect(self.screen, (180, 178, 170), grid_rect)
        font_p = pygame.font.SysFont("Arial", 36, bold=True)
        surf   = font_p.render("Paused", True, TEXT_PRIMARY)
        self.screen.blit(surf, (
            grid_rect.x + (grid_rect.width  - surf.get_width())  // 2,
            grid_rect.y + (grid_rect.height - surf.get_height()) // 2,
        ))

    def draw_game_over(self):
        dim = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
        dim.fill((44, 44, 42, 160))
        self.screen.blit(dim, (0, 0))

        card_w, card_h = 340, 180
        card_x = (WIN_W - card_w) // 2
        card_y = (WIN_H - card_h) // 2
        card   = pygame.Rect(card_x, card_y, card_w, card_h)
        draw_rounded_rect(self.screen, (255, 255, 255), card, radius=14)
        draw_rounded_rect_border(self.screen, CELL_BORDER, card, width=1, radius=14)

        self.screen.blit(self.font_over.render("Game over", True, TEXT_PRIMARY),
                         (card_x + (card_w - self.font_over.size("Game over")[0]) // 2, card_y + 28))
        self.screen.blit(self.font_over_sub.render(self.over_reason, True, TEXT_SECONDARY),
                         (card_x + (card_w - self.font_over_sub.size(self.over_reason)[0]) // 2, card_y + 78))
        score_text = f"Final score: {self.game.score}"
        self.screen.blit(self.font_score.render(score_text, True, TEXT_PRIMARY),
                         (card_x + (card_w - self.font_score.size(score_text)[0]) // 2, card_y + 110))
        self.screen.blit(self.font_over_sub.render("Press R to play again", True, TEXT_SECONDARY),
                         (card_x + (card_w - self.font_over_sub.size("Press R to play again")[0]) // 2, card_y + 146))

        font_btn = pygame.font.SysFont("Arial", 13, bold=True)
        x_surf = font_btn.render("X", True, TEXT_SECONDARY)
        x_pad  = 6
        x_w    = x_surf.get_width()  + x_pad * 2
        x_h    = x_surf.get_height() + x_pad * 2
        self.close_over_rect = pygame.Rect(card_x + card_w - x_w - 8, card_y + 8, x_w, x_h)
        if self.close_over_rect.collidepoint(pygame.mouse.get_pos()):
            pygame.draw.rect(self.screen, (230, 228, 222), self.close_over_rect, border_radius=5)
        self.screen.blit(x_surf, (self.close_over_rect.x + x_pad, self.close_over_rect.y + x_pad))

    # ── state ─────────────────────────────────────────────────────

    def restart(self):
        self.game.reset()
        self.drag_start       = None
        self.drag_end         = None
        self.sel_valid        = False
        self.game_over        = False
        self.over_reason      = ""
        self.show_game_over   = True
        self._game_start      = time.time()
        self._result_recorded = False
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
                    if event.key == pygame.K_ESCAPE:
                        return
                    if event.key == pygame.K_r:
                        self.restart()

                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if self.game_over and self.show_game_over and self.close_over_rect.collidepoint(event.pos):
                        self.show_game_over = False
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
                            self.game.apply_move(*bounds)
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

            self.screen.fill(BG)
            self.draw_hud()
            self.draw_grid()
            if self.game.paused:
                self.draw_paused()

            self.ui.update(dt)
            self.ui.draw_ui(self.screen)

            if self.game_over and self.show_game_over:
                self.draw_game_over()

            pygame.display.flip()


if __name__ == "__main__":
    FruitBoxPygame().run()
