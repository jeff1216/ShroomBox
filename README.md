# Fruit Box

A puzzle game where you select groups of fruits whose numbers sum to 10 to clear them from the grid — race the clock to maximize your score.

## Download

**[Download FruitBox.exe](https://github.com/jeff1216/Fruitbox/releases/latest/download/FruitBox.exe)**

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

```
uv sync --extra cu128
uv run --extra cu128 python fruitbox_menu.py
```

To build the Windows executable:

```
uv sync --group build
uv run --extra cpu python -m PyInstaller --onefile --windowed --name FruitBox \
  --add-data "fruitbox_ppo_final.zip;." \
  --add-data "theme.json;." \
  --add-data "theme_dark.json;." \
  --add-data "assets;assets" \
  --collect-data stable_baselines3 \
  --collect-data sb3_contrib \
  --collect-data pygame_gui \
  fruitbox_menu.py
```
