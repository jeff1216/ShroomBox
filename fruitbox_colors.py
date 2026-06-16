import fruitbox_config

_LIGHT = {
    "BG":             (245, 243, 238),
    "CELL_BG":        (255, 255, 255),
    "CELL_BORDER":    (210, 208, 200),
    "CLEARED_BG":     (230, 228, 222),
    "HUD_BG":         (235, 233, 226),
    "CARD_BG":        (255, 255, 255),
    "CARD_BORDER":    (210, 208, 200),
    "DIVIDER":        (220, 218, 210),
    "ROW_ALT":        (248, 247, 244),
    "ROW_SEL":        (220, 235, 255),
    "ROW_HOV":        (235, 233, 226),
    "TEXT_PRIMARY":   (44,  44,  42),
    "TEXT_SECONDARY": (95,  94,  90),
    "TEXT_CLEARED":   (180, 178, 170),
    "ACCENT":         (24,  95, 165),
    "ACCENT_LIGHT":   (220, 235, 255),
    "SEL_FILL":       (55,  138, 221, 60),
    "SEL_BORDER":     (24,   95, 165),
    "INVALID_FILL":   (226,  75,  74, 60),
    "INVALID_BOR":    (163,  45,  45),
    "VALID_FILL":     (29,  158, 117, 60),
    "VALID_BOR":      (15,  110,  86),
    "TIMER_OK":       (15,  110,  86),
    "TIMER_WARN":     (186, 117,  23),
    "TIMER_DANGER":   (163,  45,  45),
    "BTN":            (210, 208, 200),
    "BTN_HOV":        (190, 188, 180),
    "BTN_BORDER":     (160, 158, 150),
    "BTN_CLOSE_HOV":  (230, 228, 222),
    "PILL_BG":        (220, 235, 255),
    "PILL_BORDER":    (24,   95, 165),
    "DIM":            (44,  44,  42, 160),
    "PAUSE_COVER":    (180, 178, 170),
    "WIN_CARD_BG":    (232, 252, 240),
    "WIN_CARD_BOR":   (22,  163,  74),
    "LOSE_CARD_BG":   (254, 234, 234),
    "LOSE_CARD_BOR":  (185,  60,  60),
    "TIE_CARD_BG":    (255, 251, 220),
    "TIE_CARD_BOR":   (180, 140,  30),
}

_DARK = {
    "BG":             (22,  22,  20),
    "CELL_BG":        (38,  37,  34),
    "CELL_BORDER":    (58,  56,  52),
    "CLEARED_BG":     (30,  30,  27),
    "HUD_BG":         (28,  28,  26),
    "CARD_BG":        (38,  37,  34),
    "CARD_BORDER":    (65,  63,  58),
    "DIVIDER":        (55,  53,  49),
    "ROW_ALT":        (44,  43,  40),
    "ROW_SEL":        (20,  50,  90),
    "ROW_HOV":        (50,  49,  45),
    "TEXT_PRIMARY":   (220, 218, 212),
    "TEXT_SECONDARY": (130, 128, 122),
    "TEXT_CLEARED":   (65,  63,  58),
    "ACCENT":         (80,  150, 230),
    "ACCENT_LIGHT":   (20,  45,  80),
    "SEL_FILL":       (80,  150, 230, 60),
    "SEL_BORDER":     (80,  150, 230),
    "INVALID_FILL":   (226,  75,  74, 60),
    "INVALID_BOR":    (200,  70,  70),
    "VALID_FILL":     (29,  158, 117, 60),
    "VALID_BOR":      (20,  140, 105),
    "TIMER_OK":       (20,  140, 105),
    "TIMER_WARN":     (210, 140,  35),
    "TIMER_DANGER":   (200,  70,  70),
    "BTN":            (55,  54,  50),
    "BTN_HOV":        (70,  68,  63),
    "BTN_BORDER":     (80,  78,  72),
    "BTN_CLOSE_HOV":  (55,  54,  50),
    "PILL_BG":        (20,  45,  80),
    "PILL_BORDER":    (80,  150, 230),
    "DIM":            (0,   0,   0,  180),
    "PAUSE_COVER":    (45,  44,  40),
    "WIN_CARD_BG":    (15,  45,  25),
    "WIN_CARD_BOR":   (22,  163,  74),
    "LOSE_CARD_BG":   (55,  15,  15),
    "LOSE_CARD_BOR":  (185,  60,  60),
    "TIE_CARD_BG":    (50,  45,  10),
    "TIE_CARD_BOR":   (180, 140,  30),
}

C: dict = {}
_dark = False


def is_dark() -> bool:
    return _dark


def set_dark(v: bool):
    global _dark
    _dark = bool(v)
    C.clear()
    C.update(_DARK if _dark else _LIGHT)
    fruitbox_config.set_key("dark_mode", int(_dark))


def tint_icon(surf, color):
    """Turn a black-on-transparent icon into the given color using additive blend."""
    import pygame
    result = surf.copy()
    r, g, b = color[0], color[1], color[2]
    result.fill((r, g, b, 0), special_flags=pygame.BLEND_ADD)
    return result


def load_icon(path, size):
    """Load, scale, and auto-tint an icon for the current theme."""
    import pygame
    raw    = pygame.image.load(path).convert_alpha()
    scaled = pygame.transform.smoothscale(raw, (size, size))
    if _dark:
        return tint_icon(scaled, C["TEXT_PRIMARY"])
    return scaled


def load_icon_fit(path, max_w, max_h):
    """Load and tint an icon scaled to fit within (max_w, max_h), preserving aspect ratio."""
    import pygame
    raw = pygame.image.load(path).convert_alpha()
    iw, ih = raw.get_size()
    scale = min(max_w / iw, max_h / ih)
    new_size = (max(1, int(iw * scale)), max(1, int(ih * scale)))
    scaled = pygame.transform.smoothscale(raw, new_size)
    if _dark:
        return tint_icon(scaled, C["TEXT_PRIMARY"])
    return scaled


def _load():
    global _dark
    _dark = bool(fruitbox_config.get("dark_mode"))
    C.update(_DARK if _dark else _LIGHT)


_load()
