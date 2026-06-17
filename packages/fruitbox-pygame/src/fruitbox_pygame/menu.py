import os
import sys
import pygame
import pygame_gui
from . import colors as fruitbox_colors

from fruitbox_core.game import FruitBoxGame
from .settings import SettingsOverlay
from .stats_screen import StatsOverlay
from .help import HelpOverlay
from .pygame_ui import (
    FruitBoxPygame,
    WIN_W as GAME_W, WIN_H as GAME_H,
    game_window_size,
    get_theme, _ASSETS,
)

MENU_W = GAME_W
MENU_H = GAME_H

ACCENT       = (24,  95, 165)

GRID_TYPES = ["random", "solvable", "custom"]

# card button dimensions (Single Player / vs AI)
_CARD_W = 280
_CARD_H = 80
_CARD_Y = 240

# top-right buttons
_TOP_BTN_Y = 14

# gear icon dimensions for custom pill
_GEAR_SZ  = 22
_GEAR_GAP = 8


class _CustomOverlay:
    def __init__(self):
        self.visible        = False
        self._card_rect     = pygame.Rect(0, 0, 0, 0)
        self.close_rect     = pygame.Rect(0, 0, 0, 0)
        self._reset_rect    = pygame.Rect(0, 0, 0, 0)
        self._confirm_rect  = pygame.Rect(0, 0, 0, 0)
        self._font_title    = None
        self._font_label    = None
        self._font_btn      = None
        self.ui             = None
        self._cols_entry    = None
        self._rows_entry    = None
        self._seed_entry    = None
        self._time_entry    = None
        self._grid_dd       = None
        self._grid_type_str = "Random"
        self._reset()

    def _ensure_fonts(self):
        if self._font_title is None:
            self._font_title = pygame.font.SysFont("Arial", 28, bold=True)
            self._font_label = pygame.font.SysFont("Arial", 13)
            self._font_btn   = pygame.font.SysFont("Arial", 13, bold=True)

    def _build_ui(self):
        card_w  = 440
        card_h  = 350
        cx      = (MENU_W - card_w) // 2
        cy      = (MENU_H - card_h) // 2
        pad     = 32
        field_h = 30
        right_x = cx + card_w - pad
        y       = cy + 100
        row_gap = 48

        self.ui = pygame_gui.UIManager((MENU_W, MENU_H), get_theme())

        col_w = 55
        row_w = 55
        gap_x = 30

        self._cols_entry = pygame_gui.elements.UITextEntryLine(
            relative_rect=pygame.Rect(right_x - col_w - gap_x - row_w, y - 6, col_w, field_h),
            manager=self.ui,
        )
        self._cols_entry.set_text(str(self._cols))

        self._rows_entry = pygame_gui.elements.UITextEntryLine(
            relative_rect=pygame.Rect(right_x - row_w, y - 6, row_w, field_h),
            manager=self.ui,
        )
        self._rows_entry.set_text(str(self._rows))

        y += row_gap
        self._time_entry = pygame_gui.elements.UITextEntryLine(
            relative_rect=pygame.Rect(right_x - 100, y - 6, 100, field_h),
            manager=self.ui,
        )
        self._time_entry.set_text(str(self._time_limit))

        y += row_gap
        self._grid_dd = pygame_gui.elements.UIDropDownMenu(
            options_list=["Random", "Solvable"],
            starting_option=self._grid_type_str,
            relative_rect=pygame.Rect(right_x - 160, y - 6, 160, field_h),
            manager=self.ui,
        )

        y += row_gap
        self._seed_entry = pygame_gui.elements.UITextEntryLine(
            relative_rect=pygame.Rect(right_x - 200, y - 6, 200, field_h),
            manager=self.ui,
        )
        self._seed_entry.set_text("" if self._seed < 0 else str(self._seed))

    def reload_theme(self):
        self._save_values()
        self._build_ui()

    def _save_values(self):
        if self._cols_entry:
            t = self._cols_entry.get_text().strip()
            if t.isdigit():
                self._cols = max(5, min(30, int(t)))
        if self._rows_entry:
            t = self._rows_entry.get_text().strip()
            if t.isdigit():
                self._rows = max(3, min(20, int(t)))
        if self._seed_entry:
            t = self._seed_entry.get_text().strip()
            self._seed = int(t) if t.isdigit() else -1
        if self._time_entry:
            t = self._time_entry.get_text().strip()
            if t.isdigit() and int(t) > 0:
                self._time_limit = max(10, min(3600, int(t)))

    def _reset(self):
        self._cols          = 17
        self._rows          = 10
        self._seed          = -1
        self._time_limit    = 120
        self._grid_type_str = "Random"
        self._build_ui()

    def get_settings(self):
        self._save_values()
        return {
            "cols":       self._cols,
            "rows":       self._rows,
            "seed":       None if self._seed < 0 else self._seed,
            "grid_base":  "solvable" if self._grid_type_str == "Solvable" else "random",
            "time_limit": self._time_limit,
        }

    def toggle(self):
        self.visible = not self.visible
        if self.visible:
            self._build_ui()

    def handle_event(self, event) -> bool:
        if not self.visible:
            return False
        if self.ui:
            self.ui.process_events(event)
        if event.type == pygame_gui.UI_DROP_DOWN_MENU_CHANGED:
            if event.ui_element == self._grid_dd:
                self._grid_type_str = event.text
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.close_rect.collidepoint(event.pos):
                self.visible = False
            elif self._reset_rect.collidepoint(event.pos):
                self._reset()
            elif self._confirm_rect.collidepoint(event.pos):
                self._save_values()
                self.visible = False
        return True

    def draw(self, screen, dt):
        if not self.visible:
            return
        self._ensure_fonts()
        C     = fruitbox_colors.C
        w, h  = screen.get_size()
        mouse = pygame.mouse.get_pos()

        dim = pygame.Surface((w, h), pygame.SRCALPHA)
        dim.fill(C["DIM"])
        screen.blit(dim, (0, 0))

        card_w, card_h = 440, 350
        cx = (w - card_w) // 2
        cy = (h - card_h) // 2
        self._card_rect = pygame.Rect(cx, cy, card_w, card_h)
        pygame.draw.rect(screen, C["CARD_BG"],     self._card_rect, border_radius=14)
        pygame.draw.rect(screen, C["CARD_BORDER"], self._card_rect, width=1, border_radius=14)

        title = self._font_title.render("Custom Mode", True, C["TEXT_PRIMARY"])
        screen.blit(title, (cx + (card_w - title.get_width()) // 2, cy + 18))

        note = self._font_label.render("Scores will not be counted towards highscore", True, C["TEXT_SECONDARY"])
        screen.blit(note, (cx + (card_w - note.get_width()) // 2, cy + 56))

        x_surf = self._font_btn.render("X", True, C["TEXT_SECONDARY"])
        x_pad  = 6
        x_w    = x_surf.get_width()  + x_pad * 2
        x_h    = x_surf.get_height() + x_pad * 2
        self.close_rect = pygame.Rect(cx + card_w - x_w - 8, cy + 8, x_w, x_h)
        if self.close_rect.collidepoint(mouse):
            pygame.draw.rect(screen, C["BTN_CLOSE_HOV"], self.close_rect, border_radius=5)
        screen.blit(x_surf, (self.close_rect.x + x_pad, self.close_rect.y + x_pad))

        pad     = 32
        y       = cy + 100
        row_gap = 48
        pygame.draw.line(screen, C["DIVIDER"], (cx + pad, y - 22), (cx + card_w - pad, y - 22))

        for i, lbl in enumerate(["GRID SIZE", "TIME (SEC)", "GRID TYPE", "SEED"]):
            s = self._font_label.render(lbl, True, C["TEXT_SECONDARY"])
            screen.blit(s, (cx + pad, y + i * row_gap))

        if self._cols_entry and self._rows_entry:
            cr = self._cols_entry.get_abs_rect()
            rr = self._rows_entry.get_abs_rect()
            xm = self._font_label.render("×", True, C["TEXT_SECONDARY"])
            screen.blit(xm, (
                cr.right + (rr.left - cr.right - xm.get_width()) // 2,
                cr.centery - xm.get_height() // 2,
            ))

        btn_py = 6
        btn_gap = 12
        btn_area_w = card_w - pad * 2
        btn_w = (btn_area_w - btn_gap) // 2
        btn_y = cy + card_h - 16

        rst_surf = self._font_btn.render("Reset to Defaults", True, C["TEXT_PRIMARY"])
        rst_h    = rst_surf.get_height() + btn_py * 2
        rst_x    = cx + pad
        rst_y    = btn_y - rst_h
        self._reset_rect = pygame.Rect(rst_x, rst_y, btn_w, rst_h)
        hov_rst = self._reset_rect.collidepoint(mouse)
        pygame.draw.rect(screen, C["BTN_HOV"] if hov_rst else C["BTN"], self._reset_rect, border_radius=6)
        pygame.draw.rect(screen, C["BTN_BORDER"], self._reset_rect, width=1, border_radius=6)
        screen.blit(rst_surf, (rst_x + (btn_w - rst_surf.get_width()) // 2, rst_y + btn_py))

        cfm_surf = self._font_btn.render("Confirm", True, C["BG"])
        cfm_h    = cfm_surf.get_height() + btn_py * 2
        cfm_x    = cx + pad + btn_w + btn_gap
        cfm_y    = btn_y - cfm_h
        self._confirm_rect = pygame.Rect(cfm_x, cfm_y, btn_w, cfm_h)
        hov_cfm = self._confirm_rect.collidepoint(mouse)
        _a = C["ACCENT"]
        _cfm_bg = tuple(min(255, v + 20) for v in _a) if hov_cfm else _a
        pygame.draw.rect(screen, _cfm_bg, self._confirm_rect, border_radius=6)
        screen.blit(cfm_surf, (cfm_x + (btn_w - cfm_surf.get_width()) // 2, cfm_y + btn_py))

        if self.ui:
            self.ui.update(dt)
            self.ui.draw_ui(screen)


class FruitBoxMenu:
    vs_class = None
    watch_class = None
    model_opponent = "rl_model"

    def _vs_class(self):
        if self.vs_class is not None:
            return self.vs_class
        from .vs import FruitBoxVs
        return FruitBoxVs

    def _watch_class(self):
        if self.watch_class is not None:
            return self.watch_class
        from .ai_watch import FruitBoxAiWatch
        return FruitBoxAiWatch

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

        self.grid_type_idx    = 0
        self.left_arrow_rect  = pygame.Rect(0, 0, 0, 0)
        self.right_arrow_rect = pygame.Rect(0, 0, 0, 0)

        self.settings       = SettingsOverlay()
        self.stats_overlay  = StatsOverlay()
        self.help_overlay   = HelpOverlay()
        self.custom_overlay = _CustomOverlay()
        self.gear_btn_rect  = pygame.Rect(0, 0, 0, 0)

        self._build_ui()

    def _build_ui(self):
        icon_sz = 32 - 6  # 26

        def _load_tint(name, sz):
            raw = pygame.image.load(os.path.join(_ASSETS, name)).convert_alpha()
            raw = pygame.transform.smoothscale(raw, (sz, sz))
            return fruitbox_colors.tint_icon(raw, fruitbox_colors.C["PILL_BORDER"])
        self._icon_arr_l = _load_tint("arrowtriangle.left.fill.png",  32)
        self._icon_arr_r = _load_tint("arrowtriangle.right.fill.png", 32)
        self._icon_settings = fruitbox_colors.load_icon(os.path.join(_ASSETS, "gearshape.png"), icon_sz)
        self._icon_stats    = fruitbox_colors.load_icon(os.path.join(_ASSETS, "waveform.path.ecg.png"), icon_sz)
        self._icon_help     = fruitbox_colors.load_icon(os.path.join(_ASSETS, "questionmark.circle.png"), icon_sz)
        self._icon_dm       = fruitbox_colors.load_icon(os.path.join(_ASSETS, "circle.lefthalf.fill.png"), icon_sz)
        _raw = pygame.image.load(os.path.join(_ASSETS, "gearshape.png")).convert_alpha()
        _raw = pygame.transform.smoothscale(_raw, (_GEAR_SZ, _GEAR_SZ))
        self._icon_gear_sm  = fruitbox_colors.tint_icon(_raw, fruitbox_colors.C["ACCENT"])

        self.ui = pygame_gui.UIManager((MENU_W, MENU_H), get_theme())

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

        s_h   = 32
        s_x   = MENU_W - s_h - 14
        st_x  = s_x   - s_h - 8
        hlp_x = st_x  - s_h - 8
        dm_x  = hlp_x - s_h - 8

        self.settings_btn = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(s_x, _TOP_BTN_Y, s_h, s_h),
            text="", manager=self.ui, object_id="#top_btn",
        )
        self.stats_btn = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(st_x, _TOP_BTN_Y, s_h, s_h),
            text="", manager=self.ui, object_id="#top_btn",
        )
        self.help_btn = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(dm_x, _TOP_BTN_Y, s_h, s_h),
            text="", manager=self.ui, object_id="#top_btn",
        )
        self.dm_btn = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(hlp_x, _TOP_BTN_Y, s_h, s_h),
            text="", manager=self.ui, object_id="#top_btn",
        )
        self.watch_btn = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(MENU_W - 70, MENU_H - 34, 60, 24),
            text="Demo", manager=self.ui, object_id="#top_btn",
        )

    @property
    def grid_type(self):
        return GRID_TYPES[self.grid_type_idx]

    # ── drawing ───────────────────────────────────────────────────

    def _draw(self, dt):
        C     = fruitbox_colors.C
        mouse = pygame.mouse.get_pos()
        self.screen.fill(C["BG"])

        # title
        title = self.font_title.render("Fruit Box", True, C["TEXT_PRIMARY"])
        self.screen.blit(title, ((MENU_W - title.get_width()) // 2, 100))

        # grid type selector
        gt_cy = _CARD_Y + _CARD_H + 60

        pill_surf  = self.font_toggle.render(self.grid_type.capitalize(), True, C["ACCENT"])
        pill_pad_x, pill_pad_y = 28, 12
        _max_cw = 0
        for _gt in GRID_TYPES:
            _s = self.font_toggle.render(_gt.capitalize(), True, C["ACCENT"])
            _w = _s.get_width() + (_GEAR_GAP + _GEAR_SZ if _gt == "custom" else 0)
            _max_cw = max(_max_cw, _w)
        pill_w = max(_max_cw + pill_pad_x * 2, 200)
        pill_h = pill_surf.get_height() + pill_pad_y * 2

        arr_click_w = self._icon_arr_l.get_width() + 24
        spacing     = 18

        total_w = arr_click_w + spacing + pill_w + spacing + arr_click_w
        x = (MENU_W - total_w) // 2

        _hov_col = (255, 255, 255, 55) if fruitbox_colors.is_dark() else (0, 0, 0, 35)
        _arr_r = self._icon_arr_l.get_width() // 2 + 6
        self.left_arrow_rect = pygame.Rect(x, gt_cy - pill_h // 2, arr_click_w, pill_h)
        _lcx = x + arr_click_w // 2
        if self.left_arrow_rect.collidepoint(mouse):
            _circ = pygame.Surface((_arr_r * 2, _arr_r * 2), pygame.SRCALPHA)
            pygame.draw.circle(_circ, _hov_col, (_arr_r, _arr_r), _arr_r)
            self.screen.blit(_circ, (_lcx - _arr_r, gt_cy - _arr_r))
        self.screen.blit(self._icon_arr_l, self._icon_arr_l.get_rect(center=(_lcx, gt_cy)))
        x += arr_click_w + spacing

        pill_rect = pygame.Rect(x, gt_cy - pill_h // 2, pill_w, pill_h)
        pygame.draw.rect(self.screen, C["PILL_BG"], pill_rect, border_radius=20)
        pygame.draw.rect(self.screen, C["PILL_BORDER"], pill_rect, width=2, border_radius=20)
        if self.grid_type == "custom":
            _cw  = pill_surf.get_width() + _GEAR_GAP + _GEAR_SZ
            _csx = x + (pill_w - _cw) // 2
            self.screen.blit(pill_surf, (_csx, gt_cy - pill_surf.get_height() // 2))
            _gx  = _csx + pill_surf.get_width() + _GEAR_GAP
            _gy  = gt_cy - _GEAR_SZ // 2
            _gcr = _GEAR_SZ // 2 + 5
            _gcx = _gx + _GEAR_SZ // 2
            self.gear_btn_rect = pygame.Rect(_gcx - _gcr, gt_cy - _gcr, _gcr * 2, _gcr * 2)
            if self.gear_btn_rect.collidepoint(mouse):
                _circ = pygame.Surface((_gcr * 2, _gcr * 2), pygame.SRCALPHA)
                pygame.draw.circle(_circ, _hov_col, (_gcr, _gcr), _gcr)
                self.screen.blit(_circ, self.gear_btn_rect.topleft)
            self.screen.blit(self._icon_gear_sm, (_gx, _gy))
        else:
            self.gear_btn_rect = pygame.Rect(0, 0, 0, 0)
            self.screen.blit(pill_surf, (
                x + (pill_w - pill_surf.get_width()) // 2,
                gt_cy - pill_surf.get_height() // 2,
            ))
        x += pill_w + spacing

        self.right_arrow_rect = pygame.Rect(x, gt_cy - pill_h // 2, arr_click_w, pill_h)
        _rcx = x + arr_click_w // 2
        if self.right_arrow_rect.collidepoint(mouse):
            _circ = pygame.Surface((_arr_r * 2, _arr_r * 2), pygame.SRCALPHA)
            pygame.draw.circle(_circ, _hov_col, (_arr_r, _arr_r), _arr_r)
            self.screen.blit(_circ, (_rcx - _arr_r, gt_cy - _arr_r))
        self.screen.blit(self._icon_arr_r, self._icon_arr_r.get_rect(center=(_rcx, gt_cy)))

        # bottom hint
        hint = self.font_hint.render("Press ESC during a game to return here", True, C["TEXT_SECONDARY"])
        self.screen.blit(hint, ((MENU_W - hint.get_width()) // 2, MENU_H - 26))


        overlay_open = self.settings.visible or self.stats_overlay.visible or self.help_overlay.visible or self.custom_overlay.visible
        for btn in (self.sp_btn, self.settings_btn, self.stats_btn, self.help_btn, self.dm_btn, self.watch_btn):
            if overlay_open and btn.is_enabled:
                btn.disable()
            elif not overlay_open and not btn.is_enabled:
                btn.enable()
        vs_enabled = not overlay_open and self.grid_type != "custom"
        if vs_enabled and not self.vs_btn.is_enabled:
            self.vs_btn.enable()
        elif not vs_enabled and self.vs_btn.is_enabled:
            self.vs_btn.disable()

        self.ui.update(dt)
        self.ui.draw_ui(self.screen)

        btn_r = self.settings_btn.get_abs_rect()
        self.screen.blit(self._icon_settings, self._icon_settings.get_rect(center=btn_r.center))
        btn_r = self.stats_btn.get_abs_rect()
        self.screen.blit(self._icon_stats, self._icon_stats.get_rect(center=btn_r.center))
        btn_r = self.help_btn.get_abs_rect()
        self.screen.blit(self._icon_help, self._icon_help.get_rect(center=btn_r.center))
        btn_r = self.dm_btn.get_abs_rect()
        self.screen.blit(self._icon_dm, self._icon_dm.get_rect(center=btn_r.center))

        # Overlays drawn after ui.draw_ui so they appear on top of the card buttons
        self.settings.draw(self.screen)
        self.stats_overlay.draw(self.screen)
        self.help_overlay.draw(self.screen)
        self.custom_overlay.draw(self.screen, dt)

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
            if self.grid_type == "custom":
                _s   = self.custom_overlay.get_settings()
                game = FruitBoxGame(rows=_s["rows"], columns=_s["cols"], grid_type=_s["grid_base"], time_limit=_s["time_limit"])
                game.reset(seed=_s["seed"])
                screen = self._resize_keep_top(*game_window_size(_s["rows"], _s["cols"]))
            else:
                game = FruitBoxGame(grid_type=self.grid_type)
                game.reset()
                screen = self._resize_keep_top(GAME_W, GAME_H)
            _gamemode = "Custom" if self.grid_type == "custom" else "single_player"
            _rseed    = _s["seed"] if self.grid_type == "custom" else None
            FruitBoxPygame(game=game, screen=screen, gamemode=_gamemode, restart_seed=_rseed).run()
            self.screen = self._resize_keep_top(MENU_W, MENU_H)

        elif mode == "vs_ai":
            C = fruitbox_colors.C
            loading_surf = pygame.font.SysFont("Arial", 21, bold=True).render(
                "Loading model…", True, C["TEXT_SECONDARY"])
            self.screen.fill(C["BG"])
            self.screen.blit(loading_surf, (
                (MENU_W - loading_surf.get_width())  // 2,
                (MENU_H - loading_surf.get_height()) // 2,
            ))
            pygame.display.flip()

            from .vs import WIN_W as VS_W, WIN_H as VS_H
            screen = self._resize_keep_top(VS_W, VS_H)
            screen.fill(C["BG"])
            screen.blit(loading_surf, (
                (VS_W - loading_surf.get_width())  // 2,
                (VS_H - loading_surf.get_height()) // 2,
            ))
            pygame.display.flip()
            _gt = self.custom_overlay.get_settings()["grid_base"] if self.grid_type == "custom" else self.grid_type
            self._vs_class()(opponent=self.model_opponent, screen=screen, grid_type=_gt).run()
            self.screen = self._resize_keep_top(MENU_W, MENU_H)

        elif mode == "watch_ai":
            C = fruitbox_colors.C
            loading_surf = pygame.font.SysFont("Arial", 21, bold=True).render(
                "Loading model…", True, C["TEXT_SECONDARY"])
            self.screen.fill(C["BG"])
            self.screen.blit(loading_surf, (
                (MENU_W - loading_surf.get_width())  // 2,
                (MENU_H - loading_surf.get_height()) // 2,
            ))
            pygame.display.flip()

            from .ai_watch import FruitBoxAiWatch
            screen = pygame.display.set_mode((GAME_W, GAME_H))
            screen.fill(C["BG"])
            screen.blit(loading_surf, (
                (GAME_W - loading_surf.get_width())  // 2,
                (GAME_H - loading_surf.get_height()) // 2,
            ))
            pygame.display.flip()
            _gt = self.custom_overlay.get_settings()["grid_base"] if self.grid_type == "custom" else self.grid_type
            self._watch_class()(screen=screen, grid_type=_gt).run()
            self.screen = pygame.display.set_mode((MENU_W, MENU_H))

    # ── main ──────────────────────────────────────────────────────

    def run(self):
        while True:
            mode = self._menu_loop()
            self._launch(mode)


def main():
    FruitBoxMenu().run()


if __name__ == "__main__":
    main()
