import sys
import os
import time
import math

import pygame
import pygame_gui

class ActionMasker:
    """Minimal action-mask wrapper (no sb3/torch dependency)."""
    def __init__(self, env, mask_fn):
        self.env = env
        self._mask_fn = mask_fn
    def action_masks(self):
        return self._mask_fn(self.env)
    def reset(self, **kwargs):
        return self.env.reset(**kwargs)
    def step(self, action):
        return self.env.step(action)

from fruitbox_core.env import FruitBoxEnv
from . import colors as fruitbox_colors
from . import config as fruitbox_config
from .pygame_ui import (
    FPS, CELL, PADDING, HUD_H, COLS, ROWS, WIN_W, WIN_H,
    get_theme, _ASSETS,
)

_BTN_H = 34
_BTN_Y = (HUD_H - _BTN_H) // 2
_BTN_X0 = PADDING + 90

AI_INTERVAL = 0.5


def mask_fn(env):
    return env.action_masks()


class FruitBoxAiWatch:
    def __init__(self, screen=None, grid_type="solvable"):
        if screen is None:
            pygame.init()
            self.screen = pygame.display.set_mode((WIN_W, WIN_H))
        else:
            self.screen = screen
        pygame.display.set_caption("Fruit Box — Watch AI")
        self.clock = pygame.time.Clock()

        self.font_num   = pygame.font.SysFont("Arial", 22, bold=True)
        self.font_score = pygame.font.SysFont("Arial", 20, bold=True)
        self.font_label = pygame.font.SysFont("Arial", 13)
        self.font_over  = pygame.font.SysFont("Arial", 36, bold=True)
        self.font_sub   = pygame.font.SysFont("Arial", 18)
        self.font_btn   = pygame.font.SysFont("Arial", 13, bold=True)

        self.ai_env = ActionMasker(FruitBoxEnv(grid_type=grid_type), mask_fn)
        self.game   = self.ai_env.env.game
        self.model  = self._create_model()

        self.overlay         = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
        self.close_over_rect = pygame.Rect(0, 0, 0, 0)

        # ── pygame_gui ────────────────────────────────────────────
        self.ui = pygame_gui.UIManager((WIN_W, WIN_H), get_theme())

        _icon_sz = _BTN_H - 8
        self._icon_restart = fruitbox_colors.load_icon(os.path.join(_ASSETS, "arrow.counterclockwise.circle.png"), _icon_sz)

        bx = _BTN_X0
        self.menu_btn = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(bx, _BTN_Y, 56, _BTN_H),
            text="Menu",
            manager=self.ui,
        )
        bx += 56 + 8
        self.restart_btn = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(bx, _BTN_Y, _BTN_H, _BTN_H),
            text="",
            manager=self.ui,
        )

        self.reset()

    def reset(self):
        self.ai_env.reset()
        self.game_over      = False
        self.game_over_at   = None
        self.show_game_over = True
        self.last_ai_move   = time.time() + AI_INTERVAL
        self.sel_start      = None
        self.sel_end        = None
        self.sel_clear_at   = 0

    def _create_model(self):
        raise NotImplementedError("subclass must implement _create_model()")

    # ── drawing ───────────────────────────────────────────────────

    def _cell_rect(self, row, col):
        return pygame.Rect(
            PADDING + col * CELL,
            HUD_H + PADDING + row * CELL,
            CELL - 1, CELL - 1,
        )

    def _draw_hud(self):
        C = fruitbox_colors.C
        pygame.draw.rect(self.screen, C["HUD_BG"], (0, 0, WIN_W, HUD_H))
        pygame.draw.line(self.screen, C["CELL_BORDER"], (0, HUD_H), (WIN_W, HUD_H), 1)

        self.screen.blit(self.font_label.render("SCORE", True, C["TEXT_SECONDARY"]), (PADDING, 12))
        self.screen.blit(self.font_score.render(str(self.game.score), True, C["TEXT_PRIMARY"]), (PADDING, 28))

        t    = self.game.time_remaining
        tcol = C["TIMER_OK"] if t > 30 else (C["TIMER_WARN"] if t > 10 else C["TIMER_DANGER"])
        bar_w  = 180
        bar_x  = WIN_W - PADDING - bar_w
        self.screen.blit(self.font_label.render("TIME", True, C["TEXT_SECONDARY"]), (bar_x, 12))
        self.screen.blit(self.font_score.render(f"{int(t)}s", True, tcol), (bar_x, 28))
        bar_y, bar_h = 48, 6
        fill_w = int(bar_w * (t / self.game.time_limit))
        pygame.draw.rect(self.screen, C["CELL_BORDER"], (bar_x, bar_y, bar_w, bar_h), border_radius=3)
        pygame.draw.rect(self.screen, tcol, (bar_x, bar_y, fill_w, bar_h), border_radius=3)

    def _draw_board(self):
        C = fruitbox_colors.C
        for row in range(ROWS):
            for col in range(COLS):
                rect    = self._cell_rect(row, col)
                val     = self.game.grid[row][col]
                cleared = val == -1
                pygame.draw.rect(self.screen, C["CLEARED_BG"] if cleared else C["CELL_BG"], rect, border_radius=6)
                pygame.draw.rect(self.screen, C["CELL_BORDER"], rect, width=1, border_radius=6)
                if not cleared:
                    surf = self.font_num.render(str(val), True, C["TEXT_PRIMARY"])
                    self.screen.blit(surf, (
                        rect.x + (CELL - 1 - surf.get_width())  // 2,
                        rect.y + (CELL - 1 - surf.get_height()) // 2,
                    ))

        if self.sel_start and self.sel_end:
            C  = fruitbox_colors.C
            r1 = min(self.sel_start[0], self.sel_end[0])
            c1 = min(self.sel_start[1], self.sel_end[1])
            r2 = max(self.sel_start[0], self.sel_end[0])
            c2 = max(self.sel_start[1], self.sel_end[1])
            tl  = self._cell_rect(r1, c1)
            br  = self._cell_rect(r2, c2)
            sel = pygame.Rect(tl.x, tl.y, br.right - tl.x, br.bottom - tl.y)
            self.overlay.fill((0, 0, 0, 0))
            pygame.draw.rect(self.overlay, C["VALID_FILL"], sel, border_radius=8)
            self.screen.blit(self.overlay, (0, 0))
            pygame.draw.rect(self.screen, C["VALID_BOR"], sel, width=2, border_radius=8)

    def _draw_game_over(self):
        C = fruitbox_colors.C
        dim = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
        dim.fill(C["DIM"])
        self.screen.blit(dim, (0, 0))

        card_w, card_h = 340, 160
        cx = (WIN_W - card_w) // 2
        cy = (WIN_H - card_h) // 2
        card = pygame.Rect(cx, cy, card_w, card_h)
        pygame.draw.rect(self.screen, C["CARD_BG"], card, border_radius=14)
        pygame.draw.rect(self.screen, C["CARD_BORDER"], card, width=1, border_radius=14)

        remaining = max(0.0, 5.0 - (time.time() - self.game_over_at)) if self.game_over_at else 5.0
        over  = self.font_over.render("Done", True, C["TEXT_PRIMARY"])
        score = self.font_sub.render(f"Final score: {self.game.score}", True, C["TEXT_SECONDARY"])
        again = self.font_sub.render(f"Restarting in {math.ceil(remaining)}…", True, C["TEXT_SECONDARY"])
        self.screen.blit(over,  (cx + (card_w - over.get_width())  // 2, cy + 20))
        self.screen.blit(score, (cx + (card_w - score.get_width()) // 2, cy + 72))
        self.screen.blit(again, (cx + (card_w - again.get_width()) // 2, cy + 112))

        x_surf = self.font_btn.render("X", True, C["TEXT_SECONDARY"])
        x_pad  = 6
        x_w    = x_surf.get_width()  + x_pad * 2
        x_h    = x_surf.get_height() + x_pad * 2
        self.close_over_rect = pygame.Rect(cx + card_w - x_w - 8, cy + 8, x_w, x_h)
        if self.close_over_rect.collidepoint(pygame.mouse.get_pos()):
            pygame.draw.rect(self.screen, C["BTN_CLOSE_HOV"], self.close_over_rect, border_radius=5)
        self.screen.blit(x_surf, (self.close_over_rect.x + x_pad, self.close_over_rect.y + x_pad))

    # ── AI ────────────────────────────────────────────────────────

    def _step_ai(self):
        obs    = self.ai_env.env._obs()
        masks  = self.ai_env.env.action_masks()
        action, _ = self.model.predict(obs, action_masks=masks, deterministic=True)
        r0, c0, r1, c1 = self.ai_env.env._decode(int(action))
        self.sel_start    = (r0, c0)
        self.sel_end      = (r1, c1)
        self.sel_clear_at = time.time() + 0.3
        _, no_moves = self.game.apply_move(r0, c0, r1, c1)
        if no_moves:
            self.game_over    = True
            self.game_over_at = time.time()

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
                    self._step_ai()
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
