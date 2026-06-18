import json
import os
import sys
import pygame


def _settings_path() -> str:
    if getattr(sys, "frozen", False):
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        data_dir = os.path.join(base, "FruitBox")
        os.makedirs(data_dir, exist_ok=True)
        return os.path.join(data_dir, "settings.json")
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")


_PATH = _settings_path()

_DEFAULTS: dict[str, int] = {
    "key_pause":  pygame.K_SPACE,
    "key_restart": pygame.K_r,
    "key_menu":   pygame.K_ESCAPE,
    "dark_mode":  1,
}

_cfg: dict[str, int] = {}


def load():
    global _cfg
    try:
        with open(_PATH, encoding="utf-8") as f:
            _cfg = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        _cfg = {}


def _save():
    with open(_PATH, "w", encoding="utf-8") as f:
        json.dump(_cfg, f, indent=2)


def get(key: str) -> int:
    return _cfg.get(key, _DEFAULTS[key])


def set_key(key: str, value: int):
    _cfg[key] = value
    _save()


load()
