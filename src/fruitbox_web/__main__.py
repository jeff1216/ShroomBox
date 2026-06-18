"""
Fruit Box — web build entry point (pygbag-compatible).

Run locally:
    uv run python -m fruitbox_web

Pygbag deploy (Phase 4):
    pygbag --ume_block 0 src/fruitbox_web
"""

import asyncio
import os
import sys
import pygame

# Make `fruitbox` importable when running from project root
_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from .menu import WebMenu


async def main():
    pygame.init()
    await WebMenu().run()
    pygame.quit()


asyncio.run(main())
