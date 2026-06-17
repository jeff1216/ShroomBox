import sys
import os
import time
import threading
import argparse

import pygame
import pygame_gui
from sb3_contrib import MaskablePPO
from sb3_contrib.common.wrappers import ActionMasker

from .game import FruitBoxGame
from .env import FruitBoxEnv
from . import stats as fruitbox_stats
from . import config as fruitbox_config
from . import colors as fruitbox_colors
from .pygame_ui import FPS, get_theme, _ASSETS
from .solver import solve


def _resource(rel):
    if getattr(sys, "frozen", False):
        return os.path.join(sys._MEIPASS, rel)
    # project root is two directories above src/fruitbox/
    return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), rel)


MODEL_PATH  = _resource("fruitbox_ppo_final")
ONNX_PATH   = _resource("web_assets/fruitbox_policy.onnx")
AI_INTERVAL = 0.5

CELL    = 50
PADDING = 14
HUD_H   = 80
COLS    = 17
ROWS    = 10
GAP     = 24

BOARD_W = COLS * CELL
BOARD_H = ROWS * CELL
WIN_W   = BOARD_W * 2 + PADDING * 4 + GAP
WIN_H   = BOARD_H + PADDING * 2 + HUD_H

# HUD button layout — buttons are right-aligned from the AI board's right edge
_BTN_H = 34
_BTN_Y = (HUD_H - _BTN_H) // 2

# Pre-calculate right edge of AI board
_AI_BOARD_RIGHT = PADDING * 3 + BOARD_W + GAP + BOARD_W  # = WIN_W - PADDING


def mask_fn(env):
    return env.action_masks()


class FruitBoxVs:
    def __init__(self, opponent="solver", screen=None, grid_type="random"):
        self.opponent  = opponent
        self.grid_type = grid_type

        if screen is None:
            pygame.init()
            self.screen = pygame.display.set_mode((WIN_W, WIN_H))
        else:
            self.screen = screen
        _labels = {"solver": "Solver", "rl_model": "RL Model", "onnx": "ONNX"}
        pygame.display.set_caption(f"Fruit Box — vs {_labels.get(opponent, opponent)}")
        self.clock = pygame.time.Clock()

        self.font_num   = pygame.font.SysFont("Arial", 20, bold=True)
        self.font_score = pygame.font.SysFont("Arial", 23, bold=True)
        self.font_label = pygame.font.SysFont("Arial", 15)
        self.font_over  = pygame.font.SysFont("Arial", 38, bold=True)
        self.font_sub   = pygame.font.SysFont("Arial", 20)
        self.font_btn   = pygame.font.SysFont("Arial", 13, bold=True)

        self.human_game = FruitBoxGame(grid_type=grid_type)
        self.ai_game    = FruitBoxGame(grid_type=grid_type)

        if opponent == "rl_model":
            self.ai_env  = ActionMasker(FruitBoxEnv(), mask_fn)
            self.ai_game = self.ai_env.env.game
            self.model   = MaskablePPO.load(MODEL_PATH)
        elif opponent == "onnx":
            from .onnx_agent import OnnxAgent
            self.ai_env  = ActionMasker(FruitBoxEnv(), mask_fn)
            self.ai_game = self.ai_env.env.game
            self.model   = OnnxAgent(ONNX_PATH)
        else:
            self.ai_env = None
            self.model  = None

        self.overlay          = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
        self.ai_board_visible = False
        self.close_over_rect      = pygame.Rect(0, 0, 0, 0)
        self._game_over_card_rect = pygame.Rect(0, 0, 0, 0)
        self._restart_over_rect   = pygame.Rect(0, 0, 0, 0)
        self.stats            = fruitbox_stats.get_vs_stats()

        # ── pygame_gui ────────────────────────────────────────────
        self.ui = pygame_gui.UIManager((WIN_W, WIN_H), get_theme())

        _icon_sz = _BTN_H - 8
        self._icon_pause     = fruitbox_colors.load_icon(os.path.join(_ASSETS, "pause.circle.png"), _icon_sz)
        self._icon_play      = fruitbox_colors.load_icon(os.path.join(_ASSETS, "play.circle.png"), _icon_sz)
        self._icon_restart   = fruitbox_colors.load_icon(os.path.join(_ASSETS, "arrow.counterclockwise.circle.png"), _icon_sz)
        self._icon_eye       = fruitbox_colors.load_icon_fit(os.path.join(_ASSETS, "eye.png"), _icon_sz, _icon_sz)
        self._icon_eye_slash = fruitbox_colors.load_icon_fit(os.path.join(_ASSETS, "eye.slash.png"), _icon_sz, _icon_sz)

        # Buttons placed right-to-left from AI board right edge
        # Visual order left→right: Menu | Pause | Restart | Hide
        rx = _AI_BOARD_RIGHT - PADDING

        # Hide toggle (rightmost)
        self.toggle_btn = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(rx - 34, _BTN_Y, 34, _BTN_H),
            text="",
            manager=self.ui,
        )
        rx -= 34 + 8

        # Restart
        self.restart_btn = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(rx - 34, _BTN_Y, 34, _BTN_H),
            text="",
            manager=self.ui,
        )
        rx -= 34 + 8

        # Pause
        self.pause_btn = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(rx - 34, _BTN_Y, 34, _BTN_H),
            text="",
            manager=self.ui,
        )
        rx -= 34 + 8

        # Menu (leftmost)
        self.menu_btn = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(rx - 56, _BTN_Y, 56, _BTN_H),
            text="Menu",
            manager=self.ui,
        )

        self.reset()

    # ── board x offsets ───────────────────────────────────────────

    def _human_x(self):
        return PADDING

    def _ai_x(self):
        return PADDING * 3 + BOARD_W + GAP

    # ── geometry ──────────────────────────────────────────────────

    def _cell_rect(self, row, col, board_x):
        return pygame.Rect(
            board_x + col * CELL,
            HUD_H + PADDING + row * CELL,
            CELL - 1, CELL - 1,
        )

    def _pixel_to_cell(self, px, py):
        col = (px - self._human_x()) // CELL
        row = (py - HUD_H - PADDING) // CELL
        if 0 <= row < ROWS and 0 <= col < COLS:
            return row, col
        return None

    def _selection_bounds(self):
        if self.drag_start is None or self.drag_end is None:
            return None
        r1 = min(self.drag_start[0], self.drag_end[0])
        c1 = min(self.drag_start[1], self.drag_end[1])
        r2 = max(self.drag_start[0], self.drag_end[0])
        c2 = max(self.drag_start[1], self.drag_end[1])
        return r1, c1, r2, c2

    # ── drawing ───────────────────────────────────────────────────

    def _draw_board(self, game, board_x, drag_start=None, drag_end=None):
        C = fruitbox_colors.C
        for row in range(ROWS):
            for col in range(COLS):
                rect    = self._cell_rect(row, col, board_x)
                val     = game.grid[row][col]
                cleared = val == -1
                pygame.draw.rect(self.screen, C["CLEARED_BG"] if cleared else C["CELL_BG"], rect, border_radius=5)
                pygame.draw.rect(self.screen, C["CELL_BORDER"], rect, width=1, border_radius=5)
                if not cleared:
                    surf = self.font_num.render(str(val), True, C["TEXT_PRIMARY"])
                    self.screen.blit(surf, (
                        rect.x + (CELL - 1 - surf.get_width())  // 2,
                        rect.y + (CELL - 1 - surf.get_height()) // 2,
                    ))

        if drag_start and drag_end:
            r1 = min(drag_start[0], drag_end[0])
            c1 = min(drag_start[1], drag_end[1])
            r2 = max(drag_start[0], drag_end[0])
            c2 = max(drag_start[1], drag_end[1])
            valid = game.validate_move(r1, c1, r2, c2)
            tl  = self._cell_rect(r1, c1, board_x)
            br  = self._cell_rect(r2, c2, board_x)
            sel = pygame.Rect(tl.x, tl.y, br.right - tl.x, br.bottom - tl.y)
            self.overlay.fill((0, 0, 0, 0))
            pygame.draw.rect(self.overlay, C["VALID_FILL"] if valid else C["SEL_FILL"], sel, border_radius=8)
            self.screen.blit(self.overlay, (0, 0))
            pygame.draw.rect(self.screen, C["VALID_BOR"] if valid else C["SEL_BORDER"], sel, width=2, border_radius=8)

    def _draw_hud(self):
        C = fruitbox_colors.C
        pygame.draw.rect(self.screen, C["HUD_BG"], (0, 0, WIN_W, HUD_H))
        pygame.draw.line(self.screen, C["CELL_BORDER"], (0, HUD_H), (WIN_W, HUD_H), 1)

        self.screen.blit(self.font_label.render("YOU", True, C["TEXT_SECONDARY"]), (self._human_x(), 12))
        self.screen.blit(self.font_score.render(str(self.human_game.score), True, C["TEXT_PRIMARY"]), (self._human_x(), 28))

        ai_label = {"solver": "SOLVER", "rl_model": "RL MODEL", "onnx": "ONNX"}.get(self.opponent, self.opponent.upper())
        self.screen.blit(self.font_label.render(ai_label, True, C["TEXT_SECONDARY"]), (self._ai_x(), 12))
        self.screen.blit(self.font_score.render(str(self.ai_game.score), True, C["TEXT_PRIMARY"]), (self._ai_x(), 28))

        t    = self.human_game.time_remaining
        tcol = C["TIMER_OK"] if t > 30 else (C["TIMER_WARN"] if t > 10 else C["TIMER_DANGER"])
        timer_surf = self.font_score.render(f"{int(t)}s", True, tcol)
        tx = (WIN_W - timer_surf.get_width()) // 2
        self.screen.blit(self.font_label.render("TIME", True, C["TEXT_SECONDARY"]), (tx, 12))
        self.screen.blit(timer_surf, (tx, 28))


    def _draw_paused(self):
        C         = fruitbox_colors.C
        alpha     = int(self._pause_alpha)
        grid_rect = pygame.Rect(self._human_x(), HUD_H + PADDING, BOARD_W, BOARD_H)
        bg = pygame.Surface((grid_rect.width, grid_rect.height))
        bg.fill(C["PAUSE_COVER"])
        bg.set_alpha(alpha)
        self.screen.blit(bg, (grid_rect.x, grid_rect.y))
        surf = self.font_sub.render("Paused", True, C["TEXT_PRIMARY"])
        surf.set_alpha(alpha)
        self.screen.blit(surf, (
            grid_rect.x + (BOARD_W - surf.get_width())  // 2,
            grid_rect.y + (BOARD_H - surf.get_height()) // 2,
        ))

    def _draw_thinking(self):
        ax    = self._ai_x()
        cover = pygame.Rect(ax, HUD_H + PADDING, BOARD_W, BOARD_H)
        pygame.draw.rect(self.screen, (20, 20, 20), cover)
        dots = "." * (int(time.time() * 2) % 4)
        surf = self.font_sub.render(f"Solving{dots}", True, (200, 200, 200))
        self.screen.blit(surf, (
            ax + (BOARD_W - surf.get_width())  // 2,
            HUD_H + PADDING + (BOARD_H - surf.get_height()) // 2,
        ))

    def _draw_game_over(self):
        C = fruitbox_colors.C
        dim = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
        dim.fill(C["DIM"])
        self.screen.blit(dim, (0, 0))

        card_w, card_h = 380, 215
        cx = (WIN_W - card_w) // 2
        cy = (WIN_H - card_h) // 2
        card = pygame.Rect(cx, cy, card_w, card_h)
        self._game_over_card_rect = card

        h, a = self.human_game.score, self.ai_game.score
        if   h > a: card_bg, card_border = C["WIN_CARD_BG"],  C["WIN_CARD_BOR"]
        elif a > h: card_bg, card_border = C["LOSE_CARD_BG"], C["LOSE_CARD_BOR"]
        else:       card_bg, card_border = C["TIE_CARD_BG"],  C["TIE_CARD_BOR"]

        pygame.draw.rect(self.screen, card_bg,     card, border_radius=14)
        pygame.draw.rect(self.screen, card_border, card, width=2, border_radius=14)

        over = self.font_over.render("Game Over", True, C["TEXT_PRIMARY"])
        rsn  = self.font_sub.render(self.over_reason, True, C["TEXT_SECONDARY"])
        w, l, t = self.stats["wins"], self.stats["losses"], self.stats["ties"]
        rec  = self.font_label.render(f"Record: {w}W  {l}L  {t}T", True, C["TEXT_SECONDARY"])

        self.screen.blit(over, (cx + (card_w - over.get_width()) // 2, cy + 22))
        self.screen.blit(rsn,  (cx + (card_w - rsn.get_width())  // 2, cy + 74))
        self.screen.blit(rec,  (cx + (card_w - rec.get_width())  // 2, cy + 112))

        mouse  = pygame.mouse.get_pos()
        r_surf = self.font_btn.render("Restart", True, C["TEXT_PRIMARY"])
        r_px, r_py = 20, 8
        r_w = r_surf.get_width()  + r_px * 2
        r_h = r_surf.get_height() + r_py * 2
        self._restart_over_rect = pygame.Rect(cx + (card_w - r_w) // 2, cy + 156, r_w, r_h)
        r_hov = self._restart_over_rect.collidepoint(mouse)
        pygame.draw.rect(self.screen, C["BTN_HOV"] if r_hov else C["BTN"], self._restart_over_rect, border_radius=6)
        pygame.draw.rect(self.screen, C["BTN_BORDER"], self._restart_over_rect, width=1, border_radius=6)
        self.screen.blit(r_surf, (self._restart_over_rect.x + r_px, self._restart_over_rect.y + r_py))

        x_surf = self.font_btn.render("X", True, C["TEXT_SECONDARY"])
        x_pad  = 6
        x_w    = x_surf.get_width()  + x_pad * 2
        x_h    = x_surf.get_height() + x_pad * 2
        self.close_over_rect = pygame.Rect(cx + card_w - x_w - 8, cy + 8, x_w, x_h)
        if self.close_over_rect.collidepoint(mouse):
            pygame.draw.rect(self.screen, C["BTN_CLOSE_HOV"], self.close_over_rect, border_radius=5)
        self.screen.blit(x_surf, (self.close_over_rect.x + x_pad, self.close_over_rect.y + x_pad))

    # ── AI logic ──────────────────────────────────────────────────

    def _run_solver(self, grid):
        solver_grid = [[0 if v == -1 else v for v in row] for row in grid]
        sol, _ = solve(solver_grid)
        self._solver_moves = sol['moves'][:]
        self._solver_ready = True

    def _step_ai(self):
        if self.opponent == "solver":
            if not self._solver_ready:
                return
            if not self._solver_moves:
                self.ai_over = True
                return
            _, r0, c0, r1, c1 = self._solver_moves.pop(0)
            self.ai_drag_start   = (r0, c0)
            self.ai_drag_end     = (r1, c1)
            self.ai_sel_clear_at = time.time() + 0.3
            _, no_moves = self.ai_game.apply_move(r0, c0, r1, c1)
            if no_moves:
                self.ai_over = True
        else:
            obs   = self.ai_env.env._obs()
            masks = self.ai_env.env.action_masks()
            action, _ = self.model.predict(obs, action_masks=masks, deterministic=True)
            r0, c0, r1, c1 = self.ai_env.env._decode(int(action))
            self.ai_drag_start   = (r0, c0)
            self.ai_drag_end     = (r1, c1)
            self.ai_sel_clear_at = time.time() + 0.2
            _, no_moves = self.ai_game.apply_move(r0, c0, r1, c1)
            if no_moves:
                self.ai_over = True

    # ── state ─────────────────────────────────────────────────────

    def reset(self):
        self.human_game.reset()
        self.human_game.paused = False

        if self.opponent in ("rl_model", "onnx"):
            self.ai_env.reset()
            self.ai_game.grid = self.human_game.grid.copy()
        else:
            self.ai_game.reset()
            self.ai_game.grid = self.human_game.grid.copy()

        self.drag_start = None
        self.drag_end   = None

        self.ai_drag_start   = None
        self.ai_drag_end     = None
        self.ai_sel_clear_at = 0
        self.last_ai_move    = time.time() + AI_INTERVAL

        self.human_over       = False
        self.ai_over          = False
        self.game_over        = False
        self.over_reason      = ""
        self.show_game_over   = True
        self._result_recorded = False
        self._game_start      = time.time()
        self._pause_alpha     = 0.0

        self._solver_moves = []
        self._solver_ready = self.opponent != "solver"
        if self.opponent == "solver":
            threading.Thread(
                target=self._run_solver,
                args=(self.human_game.grid.tolist(),),
                daemon=True,
            ).start()

        self.pause_btn.enable()

    # ── main loop ─────────────────────────────────────────────────

    def run(self):
        self.clock.tick()
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
                    self._step_ai()

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


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--opponent", choices=["solver", "rl_model", "onnx"], default="solver")
    args = parser.parse_args()
    FruitBoxVs(opponent=args.opponent).run()
