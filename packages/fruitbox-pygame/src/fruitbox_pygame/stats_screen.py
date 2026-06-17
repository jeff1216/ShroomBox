import pygame
import pygame_gui
import time
import subprocess
from fruitbox_core import stats as fruitbox_stats
from . import colors as fruitbox_colors
from .pygame_ui import WIN_W as _W, WIN_H as _H, get_theme

_CARD_W = 440
_CARD_H = 360
_CX     = (_W - _CARD_W) // 2
_CY     = (_H - _CARD_H) // 2
_PAD    = 32

# y offset where "BEST SCORE" section starts inside the card:
# title(66) + row(44) + row(44) + div(16) + row(44) + div(16) = 230
_BEST_SCORE_Y = _CY + 230

_MODE_LABEL = {
    "single_player": "Single",
    "vs_ai":         "VS AI",
    "watch_ai":      "Watch AI",
}


def _fmt_time(seconds):
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        m, s = divmod(seconds, 60)
        return f"{m}m {s}s"
    else:
        h, rem = divmod(seconds, 3600)
        return f"{h}h {rem // 60}m"


def _to_clipboard(text):
    try:
        subprocess.run("clip", input=text.encode("utf-16-le"), check=True, shell=True)
    except Exception:
        pass


class StatsOverlay:
    def __init__(self):
        self.visible          = False
        self._view            = "stats"
        self._card_rect       = pygame.Rect(0, 0, 0, 0)
        self.close_rect       = pygame.Rect(0, 0, 0, 0)
        self.history_btn_rect = pygame.Rect(0, 0, 0, 0)
        self.back_btn_rect    = pygame.Rect(0, 0, 0, 0)
        self._font_title      = None
        self._font_label      = None
        self._font_value      = None
        self._font_btn        = None
        self._font_col        = None
        self._summary         = None
        self._history         = []
        self._scroll          = 0
        self._row_h           = 24
        self._visible_rows    = 0
        self._row_area_rect   = pygame.Rect(0, 0, 0, 0)
        self._selected_row    = None
        self._copied_at       = 0.0
        self._seed_rect       = pygame.Rect(0, 0, 0, 0)

        # ── pygame_gui ────────────────────────────────────────────
        self._grid_filter  = "random"
        self._last_ui_time = time.time()
        self._build_ui()

    def _build_ui(self):
        self.ui = pygame_gui.UIManager((_W, _H), get_theme())
        self._dropdown = pygame_gui.elements.UIDropDownMenu(
            options_list=["Random", "Solvable"],
            starting_option=self._grid_filter.capitalize(),
            relative_rect=pygame.Rect(_CX + _PAD + 84, _BEST_SCORE_Y - 1, 120, 26),
            manager=self.ui,
        )
        if not self.visible:
            self._dropdown.hide()

    def reload_theme(self):
        self._build_ui()

    def _ensure_fonts(self):
        if self._font_title is None:
            self._font_title = pygame.font.SysFont("Arial", 28, bold=True)
            self._font_label = pygame.font.SysFont("Arial", 13)
            self._font_value = pygame.font.SysFont("Arial", 20, bold=True)
            self._font_btn   = pygame.font.SysFont("Arial", 13, bold=True)
            self._font_col   = pygame.font.SysFont("Arial", 13)

    def toggle(self):
        self.visible = not self.visible
        if self.visible:
            self._view         = "stats"
            self._scroll       = 0
            self._selected_row = None
            self._summary      = fruitbox_stats.get_summary()
            self._dropdown.show()
        else:
            self._dropdown.hide()

    def _open_history(self):
        self._view         = "history"
        self._scroll       = 0
        self._selected_row = None
        self._history      = fruitbox_stats.get_history()[:20]
        self._dropdown.hide()

    def handle_event(self, event):
        if not self.visible:
            return False

        # Forward all events to the UI manager
        self.ui.process_events(event)

        if event.type == pygame_gui.UI_DROP_DOWN_MENU_CHANGED:
            if event.ui_element == self._dropdown:
                self._grid_filter = event.text.lower()
                return True

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if self._view == "history":
                    self._view = "stats"
                    self._dropdown.show()
                else:
                    self.visible = False
                    self._dropdown.hide()
            return True

        if event.type == pygame.MOUSEWHEEL and self._view == "history":
            max_scroll = max(0, len(self._history) - self._visible_rows)
            self._scroll = max(0, min(self._scroll - event.y, max_scroll))
            return True

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.close_rect.collidepoint(event.pos):
                self.visible = False
                self._dropdown.hide()
                return True
            if self._view == "stats":
                if self.history_btn_rect.collidepoint(event.pos):
                    self._open_history()
                    return True
                s = self._summary
                if s and self._seed_rect.collidepoint(event.pos):
                    key = "random_best_seed" if self._grid_filter == "random" else "solvable_best_seed"
                    if s[key] is not None:
                        _to_clipboard(str(s[key]))
                        self._copied_at = time.time()
            elif self._view == "history":
                if self.back_btn_rect.collidepoint(event.pos):
                    self._view = "stats"
                    self._dropdown.show()
                    return True
                if self._row_area_rect.collidepoint(event.pos):
                    idx = (event.pos[1] - self._row_area_rect.y) // self._row_h + self._scroll
                    if 0 <= idx < len(self._history):
                        self._selected_row = idx
                        _to_clipboard(str(self._history[idx]["seed"]))
                        self._copied_at = time.time()
            if not self._card_rect.collidepoint(event.pos):
                self.visible = False
                self._dropdown.hide()
            return True

        if event.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONUP):
            return True
        return False

    # ── shared helpers ────────────────────────────────────────────

    def _draw_card(self, screen, card_w, card_h):
        C    = fruitbox_colors.C
        w, h = screen.get_size()
        cx = (w - card_w) // 2
        cy = (h - card_h) // 2
        self._card_rect = pygame.Rect(cx, cy, card_w, card_h)

        dim = pygame.Surface((w, h), pygame.SRCALPHA)
        dim.fill(C["DIM"])
        screen.blit(dim, (0, 0))

        pygame.draw.rect(screen, C["CARD_BG"], self._card_rect, border_radius=14)
        pygame.draw.rect(screen, C["CARD_BORDER"], self._card_rect, width=1, border_radius=14)

        x_surf = self._font_btn.render("X", True, C["TEXT_SECONDARY"])
        x_pad  = 6
        x_w    = x_surf.get_width()  + x_pad * 2
        x_h    = x_surf.get_height() + x_pad * 2
        self.close_rect = pygame.Rect(cx + card_w - x_w - 8, cy + 8, x_w, x_h)
        if self.close_rect.collidepoint(pygame.mouse.get_pos()):
            pygame.draw.rect(screen, C["BTN_CLOSE_HOV"], self.close_rect, border_radius=5)
        screen.blit(x_surf, (self.close_rect.x + x_pad, self.close_rect.y + x_pad))

        return cx, cy

    def _draw_copied_toast(self, screen, cx, cy, card_w, card_h):
        if time.time() - self._copied_at < 1.2:
            toast = self._font_label.render("Copied!", True, (15, 110, 86))
            screen.blit(toast, (cx + card_w - toast.get_width() - 12,
                                cy + card_h - toast.get_height() - 10))

    # ── stats view ────────────────────────────────────────────────

    def _draw_stats(self, screen):
        C      = fruitbox_colors.C
        s      = self._summary
        cx, cy = self._draw_card(screen, _CARD_W, _CARD_H)
        mouse  = pygame.mouse.get_pos()

        title = self._font_title.render("Stats", True, C["TEXT_PRIMARY"])
        screen.blit(title, (cx + (_CARD_W - title.get_width()) // 2, cy + 20))

        y = cy + 66

        def row(label, value):
            nonlocal y
            screen.blit(self._font_label.render(label, True, C["TEXT_SECONDARY"]), (cx + _PAD, y))
            screen.blit(self._font_value.render(value, True, C["TEXT_PRIMARY"]),   (cx + _PAD, y + 14))
            y += 44

        def divider():
            nonlocal y
            pygame.draw.line(screen, C["DIVIDER"], (cx + _PAD, y), (cx + _CARD_W - _PAD, y))
            y += 16

        row("GAMES PLAYED", str(s["total_games"]))
        row("TIME PLAYED",  _fmt_time(s["total_time"]))
        divider()
        row("VS AI RECORD", f"{s['vs_wins']}W   {s['vs_losses']}L   {s['vs_ties']}T")
        divider()

        # Best score section — dropdown selects grid type
        _bs_surf = self._font_label.render("BEST SCORE", True, C["TEXT_SECONDARY"])
        _bs_y    = y + (26 // 2) - _bs_surf.get_height() // 2 - 1  # vertically center with 26px dropdown
        screen.blit(_bs_surf, (cx + _PAD, _bs_y))
        # (dropdown drawn by ui.draw_ui below)

        score_key = f"{self._grid_filter}_best"
        seed_key  = f"{self._grid_filter}_best_seed"
        time_key  = f"{self._grid_filter}_best_time"
        score     = s[score_key]
        seed      = s[seed_key]
        best_time = s[time_key]

        value = "—" if score is None else str(score)
        screen.blit(self._font_value.render(value, True, C["TEXT_PRIMARY"]), (cx + _PAD, _bs_y + 14))

        if score is not None and best_time is not None:
            time_surf  = self._font_value.render(f"  •  {int(best_time)}s", True, C["TEXT_PRIMARY"])
            score_surf = self._font_value.render(value, True, C["TEXT_PRIMARY"])
            screen.blit(time_surf, (cx + _PAD + score_surf.get_width(), _bs_y + 14))

        if score is not None:
            sub_x    = cx + _PAD
            sub_y    = _bs_y + 38
            sub_text = f"Seed: {seed}"
            sub_surf = self._font_label.render(sub_text, True, C["TEXT_SECONDARY"])
            sr = pygame.Rect(sub_x - 2, sub_y - 2, sub_surf.get_width() + 4, sub_surf.get_height() + 4)
            self._seed_rect = sr
            if sr.collidepoint(mouse):
                pygame.draw.rect(screen, C["BTN_CLOSE_HOV"], sr, border_radius=3)
            screen.blit(sub_surf, (sub_x, sub_y))

        y += 68

        btn_surf = self._font_btn.render("Full History", True, C["TEXT_PRIMARY"])
        bp_x, bp_y = 12, 6
        bw = btn_surf.get_width()  + bp_x * 2
        bh = btn_surf.get_height() + bp_y * 2
        bx = cx + (_CARD_W - bw) // 2
        by = cy + _CARD_H - bh - 16
        self.history_btn_rect = pygame.Rect(bx, by, bw, bh)
        hov = self.history_btn_rect.collidepoint(mouse)
        pygame.draw.rect(screen, C["BTN_HOV"] if hov else C["BTN"], self.history_btn_rect, border_radius=6)
        pygame.draw.rect(screen, C["BTN_BORDER"], self.history_btn_rect, width=1, border_radius=6)
        screen.blit(btn_surf, (bx + bp_x, by + bp_y))

        self._draw_copied_toast(screen, cx, cy, _CARD_W, _CARD_H)

    # ── history view ──────────────────────────────────────────────

    def _draw_history(self, screen):
        C      = fruitbox_colors.C
        card_w, card_h = 520, 400
        cx, cy = self._draw_card(screen, card_w, card_h)
        mouse  = pygame.mouse.get_pos()
        pad    = 20

        title = self._font_title.render("Full History", True, C["TEXT_PRIMARY"])
        screen.blit(title, (cx + (card_w - title.get_width()) // 2, cy + 18))

        back_surf = self._font_btn.render("← Back", True, C["TEXT_SECONDARY"])
        bp_x, bp_y = 8, 6
        bw = back_surf.get_width()  + bp_x * 2
        bh = back_surf.get_height() + bp_y * 2
        self.back_btn_rect = pygame.Rect(cx + pad, cy + 16, bw, bh)
        if self.back_btn_rect.collidepoint(mouse):
            pygame.draw.rect(screen, C["BTN_CLOSE_HOV"], self.back_btn_rect, border_radius=5)
        screen.blit(back_surf, (cx + pad + bp_x, cy + 16 + bp_y))

        header_y = cy + 56
        cols = [
            (cx + pad,       "MODE"),
            (cx + pad + 90,  "GRID"),
            (cx + pad + 175, "SCORE"),
            (cx + pad + 240, "OPP"),
            (cx + pad + 305, "SEED"),
        ]
        for x, label in cols:
            screen.blit(self._font_label.render(label, True, C["TEXT_SECONDARY"]), (x, header_y))

        hint = self._font_label.render("Click row to copy seed", True, C["TEXT_SECONDARY"])
        screen.blit(hint, (cx + card_w - hint.get_width() - pad, header_y + 2))

        pygame.draw.line(screen, C["DIVIDER"], (cx + pad, header_y + 18), (cx + card_w - pad, header_y + 18))

        row_area_y = header_y + 24
        row_area_h = card_h - (row_area_y - cy) - pad
        self._visible_rows  = max(1, row_area_h // self._row_h)
        self._row_area_rect = pygame.Rect(cx + pad, row_area_y, card_w - pad * 2, row_area_h)

        screen.set_clip(pygame.Rect(cx + pad, row_area_y, card_w - pad * 2, row_area_h))

        for i, game in enumerate(self._history[self._scroll:self._scroll + self._visible_rows]):
            ry       = row_area_y + i * self._row_h
            idx      = i + self._scroll
            row_rect = pygame.Rect(cx + pad, ry, card_w - pad * 2, self._row_h)

            if idx == self._selected_row:
                bg = C["ROW_SEL"]
            elif row_rect.collidepoint(mouse):
                bg = C["ROW_HOV"]
            elif i % 2 == 1:
                bg = C["ROW_ALT"]
            else:
                bg = None

            if bg:
                pygame.draw.rect(screen, bg, row_rect)

            mode  = _MODE_LABEL.get(game["gamemode"], game["gamemode"])
            grid  = game["grid_type"].capitalize()
            score = str(game["self_score"])
            opp   = str(game["opp_score"]) if game["opp_score"] is not None else "—"
            seed  = str(game["seed"])

            screen.blit(self._font_col.render(mode,  True, C["TEXT_PRIMARY"]),   (cx + pad,       ry + 4))
            screen.blit(self._font_col.render(grid,  True, C["TEXT_PRIMARY"]),   (cx + pad + 90,  ry + 4))
            screen.blit(self._font_col.render(score, True, C["TEXT_PRIMARY"]),   (cx + pad + 175, ry + 4))
            screen.blit(self._font_col.render(opp,   True, C["TEXT_SECONDARY"]), (cx + pad + 240, ry + 4))
            screen.blit(self._font_col.render(seed,  True, C["TEXT_SECONDARY"]), (cx + pad + 305, ry + 4))

        screen.set_clip(None)

        total = len(self._history)
        if total > self._visible_rows:
            bar_h = max(20, int(row_area_h * self._visible_rows / total))
            bar_y = row_area_y + int((row_area_h - bar_h) * self._scroll / max(1, total - self._visible_rows))
            bar_x = cx + card_w - pad + 4
            pygame.draw.rect(screen, C["CELL_BORDER"],    (bar_x, row_area_y, 4, row_area_h), border_radius=2)
            pygame.draw.rect(screen, C["TEXT_SECONDARY"], (bar_x, bar_y,      4, bar_h),      border_radius=2)

        self._draw_copied_toast(screen, cx, cy, card_w, card_h)

    # ── main entry ────────────────────────────────────────────────

    def draw(self, screen):
        if not self.visible:
            return
        self._ensure_fonts()
        if self._view == "stats":
            self._draw_stats(screen)
        else:
            self._draw_history(screen)

        now = time.time()
        dt  = now - self._last_ui_time
        self._last_ui_time = now
        self.ui.update(dt)
        self.ui.draw_ui(screen)
