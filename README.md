# Fruit Box

A puzzle game where you select groups of fruits whose numbers sum to 10 to clear them from the grid — race the clock to maximize your score.

## Download

- **[fruitbox.exe](https://github.com/jeff1216/Fruitbox/releases/latest/download/fruitbox.exe)** — PyTorch / SB3 inference
- **[fruitbox-onnx.exe](https://github.com/jeff1216/Fruitbox/releases/latest/download/fruitbox-onnx.exe)** — ONNX inference (no PyTorch)

Windows only. No installation required — just run the executable.

## Game Modes

| Mode | Description |
|---|---|
| Single Player | Clear as many fruits as possible before time runs out |
| vs AI | Play head-to-head against a trained RL agent on a split screen |
| Custom | Configure grid size, seed, time limit, and grid type |
| Demo | Watch the AI play on its own |

## How to Play

Click and drag to select a rectangular region of fruits. If the numbers in the selection sum to exactly **10**, the fruits are cleared and you score points. Keep clearing until no valid moves remain or the timer runs out.

## Controls

| Key | Action |
|---|---|
| Drag | Select fruits |
| `Space` | Pause / resume |
| `R` | Restart |
| `Esc` | Return to menu |

## Custom Mode

Use the gear icon in the pill selector to configure:
- **Grid size** — columns × rows (5–30 × 3–20)
- **Seed** — fixed seed for a reproducible grid (leave blank for random)
- **Grid type** — Random or Solvable
- **Time** — time limit in seconds (default 120)

Scores in Custom mode are not counted towards the highscore.

## Building from Source

This repo is a [uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/) with hatchling-built packages:

| Package | Role |
|---|---|
| `fruitbox-core` | Game logic, gym env, solver |
| `fruitbox-pygame` | Pygame UI and menus |
| `fruitbox-app-torch` | Desktop app with SB3/PyTorch (`fruitbox` CLI) |
| `fruitbox-app-onnx` | Desktop app with ONNX only (`fruitbox-onnx` CLI) |
| `fruitbox-train` | Training and watch CLIs |
| `fruitbox-web` | pygbag / WASM web overlay |

```bash
uv sync --extra cpu --all-packages   # install everything (CPU PyTorch)
uv run fruitbox                      # PyTorch desktop app
uv run fruitbox-onnx                 # ONNX desktop app
uv run fruitbox-train --watch        # train with live preview
```

Windows executables are built in CI via PyInstaller (`fruitbox.exe` and `fruitbox-onnx.exe`). The ONNX model is bundled from [Hugging Face](https://huggingface.co/Fungster/fruitbox-ppo/blob/main/fruitbox_policy.onnx).
