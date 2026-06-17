import pygame
from . import config as fruitbox_config
from . import colors as fruitbox_colors

_BINDINGS = [
    ("key_pause",   "Pause"),
    ("key_restart", "Restart"),
    ("key_menu",    "Menu"),
]


class SettingsOverlay:
    def __init__(self):
        self.visible       = False
        self._card_rect    = pygame.Rect(0, 0, 0, 0)
        self.close_rect    = pygame.Rect(0, 0, 0, 0)
        self._font_title   = None
        self._font_label   = None
        self._font_value   = None
        self._font_btn     = None
        self._font_hint    = None
        self._waiting_for  = None
        self._key_rects: dict[str, pygame.Rect] = {}

    def _ensure_fonts(self):
        if self._font_title is None:
            self._font_title = pygame.font.SysFont("Arial", 28, bold=True)
            self._font_label = pygame.font.SysFont("Arial", 13)
            self._font_value = pygame.font.SysFont("Arial", 13, bold=True)
            self._font_btn   = pygame.font.SysFont("Arial", 13, bold=True)
            self._font_hint  = pygame.font.SysFont("Arial", 11)

    def toggle(self):
        self.visible      = not self.visible
        self._waiting_for = None

    def handle_event(self, event):
        if not self.visible:
            return False

        if event.type == pygame.KEYDOWN:
            if self._waiting_for:
                if event.key != pygame.K_ESCAPE:
                    fruitbox_config.set_key(self._waiting_for, event.key)
                self._waiting_for = None
            else:
                if event.key == pygame.K_ESCAPE:
                    self.visible = False
            return True

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if not self._card_rect.collidepoint(event.pos) or self.close_rect.collidepoint(event.pos):
                self.visible      = False
                self._waiting_for = None
            else:
                for cfg_key, rect in self._key_rects.items():
                    if rect.collidepoint(event.pos):
                        self._waiting_for = cfg_key
                        break
            return True

        if event.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONUP):
            return True
        return False

    def draw(self, screen):
        if not self.visible:
            return
        self._ensure_fonts()
        C     = fruitbox_colors.C
        w, h  = screen.get_size()
        mouse = pygame.mouse.get_pos()

        dim = pygame.Surface((w, h), pygame.SRCALPHA)
        dim.fill(C["DIM"])
        screen.blit(dim, (0, 0))

        card_w, card_h = 380, 272
        cx = (w - card_w) // 2
        cy = (h - card_h) // 2
        self._card_rect = pygame.Rect(cx, cy, card_w, card_h)
        pygame.draw.rect(screen, C["CARD_BG"], self._card_rect, border_radius=14)
        pygame.draw.rect(screen, C["CARD_BORDER"], self._card_rect, width=1, border_radius=14)

        title = self._font_title.render("Settings", True, C["TEXT_PRIMARY"])
        screen.blit(title, (cx + (card_w - title.get_width()) // 2, cy + 22))

        x_surf = self._font_btn.render("X", True, C["TEXT_SECONDARY"])
        x_pad  = 6
        x_w    = x_surf.get_width()  + x_pad * 2
        x_h    = x_surf.get_height() + x_pad * 2
        self.close_rect = pygame.Rect(cx + card_w - x_w - 8, cy + 8, x_w, x_h)
        if self.close_rect.collidepoint(mouse):
            pygame.draw.rect(screen, C["BTN_CLOSE_HOV"], self.close_rect, border_radius=5)
        screen.blit(x_surf, (self.close_rect.x + x_pad, self.close_rect.y + x_pad))

        pad = 32
        y   = cy + 72
        self._key_rects = {}
        pygame.draw.line(screen, C["DIVIDER"], (cx + pad, y - 15), (cx + card_w - pad, y - 15))

        for cfg_key, label in _BINDINGS:
            label_surf = self._font_label.render(label.upper(), True, C["TEXT_SECONDARY"])
            screen.blit(label_surf, (cx + pad, y))

            is_waiting = self._waiting_for == cfg_key
            key_name   = "..." if is_waiting else pygame.key.name(fruitbox_config.get(cfg_key)).upper()
            key_surf   = self._font_value.render(key_name, True, C["TEXT_PRIMARY"] if not is_waiting else C["ACCENT"])

            btn_px, btn_py = 14, 5
            btn_w  = max(key_surf.get_width() + btn_px * 2, 80)
            btn_h  = key_surf.get_height() + btn_py * 2
            btn_x  = cx + card_w - pad - btn_w
            btn_y  = y - (btn_h - label_surf.get_height()) // 2
            btn_rect = pygame.Rect(btn_x, btn_y, btn_w, btn_h)
            self._key_rects[cfg_key] = btn_rect

            hov    = btn_rect.collidepoint(mouse) and not is_waiting
            bg     = C["ACCENT_LIGHT"] if is_waiting else (C["BTN_HOV"] if hov else C["BTN"])
            border = C["ACCENT"]       if is_waiting else C["BTN_BORDER"]
            pygame.draw.rect(screen, bg,     btn_rect, border_radius=6)
            pygame.draw.rect(screen, border, btn_rect, width=1, border_radius=6)
            screen.blit(key_surf, (btn_x + (btn_w - key_surf.get_width()) // 2, btn_y + btn_py))

            y += 32

        if self._waiting_for:
            hint = self._font_hint.render(
                "Press any key to bind  •  ESC to cancel", True, C["TEXT_SECONDARY"])
            screen.blit(hint, (cx + (card_w - hint.get_width()) // 2, cy + card_h - 22))
