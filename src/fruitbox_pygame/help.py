import pygame
from . import colors as fruitbox_colors

_SECTIONS = [
    ("How to play:", [
        "Drag the mouse to exactly enclose some tiles so the numbers in the tiles total 10.",
        "You get 1 point per tile.",
    ]),
    ("Modes:", [
        "Random: the grid is randomly generated.",
        "Solvable: the grid is generated such that it is possible to use all tiles.",
    ]),
]


def _wrap(font, text, max_w):
    words = text.split()
    lines, current = [], ""
    for word in words:
        test = (current + " " + word).strip()
        if font.size(test)[0] <= max_w:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


class HelpOverlay:
    def __init__(self):
        self.visible     = False
        self._card_rect  = pygame.Rect(0, 0, 0, 0)
        self.close_rect  = pygame.Rect(0, 0, 0, 0)
        self._font_title   = None
        self._font_header  = None
        self._font_body    = None
        self._font_btn     = None

    def _ensure_fonts(self):
        if self._font_title is None:
            self._font_title  = pygame.font.SysFont("Arial", 28, bold=True)
            self._font_header = pygame.font.SysFont("Arial", 15, bold=True)
            self._font_body   = pygame.font.SysFont("Arial", 15)
            self._font_btn    = pygame.font.SysFont("Arial", 15, bold=True)

    def toggle(self):
        self.visible = not self.visible

    def handle_event(self, event):
        if not self.visible:
            return False

        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.visible = False
            return True

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if not self._card_rect.collidepoint(event.pos) or self.close_rect.collidepoint(event.pos):
                self.visible = False
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

        card_w, card_h = 440, 320
        cx = (w - card_w) // 2
        cy = (h - card_h) // 2
        self._card_rect = pygame.Rect(cx, cy, card_w, card_h)
        pygame.draw.rect(screen, C["CARD_BG"], self._card_rect, border_radius=14)
        pygame.draw.rect(screen, C["CARD_BORDER"], self._card_rect, width=1, border_radius=14)

        title = self._font_title.render("Help", True, C["TEXT_PRIMARY"])
        screen.blit(title, (cx + (card_w - title.get_width()) // 2, cy + 22))

        x_surf = self._font_btn.render("X", True, C["TEXT_SECONDARY"])
        x_pad  = 6
        x_w    = x_surf.get_width()  + x_pad * 2
        x_h    = x_surf.get_height() + x_pad * 2
        self.close_rect = pygame.Rect(cx + card_w - x_w - 8, cy + 8, x_w, x_h)
        if self.close_rect.collidepoint(mouse):
            pygame.draw.rect(screen, C["BTN_CLOSE_HOV"], self.close_rect, border_radius=5)
        screen.blit(x_surf, (self.close_rect.x + x_pad, self.close_rect.y + x_pad))

        pad      = 32
        text_w   = card_w - pad * 2
        y        = cy + 68
        line_h   = self._font_body.get_linesize()

        pygame.draw.line(screen, C["DIVIDER"], (cx + pad, y - 12), (cx + card_w - pad, y - 12))

        for header, lines in _SECTIONS:
            screen.blit(self._font_header.render(header, True, C["TEXT_PRIMARY"]), (cx + pad, y))
            y += line_h + 2
            for para in lines:
                for wrapped_line in _wrap(self._font_body, para, text_w):
                    screen.blit(self._font_body.render(wrapped_line, True, C["TEXT_SECONDARY"]), (cx + pad, y))
                    y += line_h
            y += 10
