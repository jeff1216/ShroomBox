'use strict';

// ── Constants ─────────────────────────────────────────────────────────────────
const DEFAULT_ROWS = 10, DEFAULT_COLS = 17;
const isMobileRotated = () => window.matchMedia('(max-width: 700px)').matches;
const CELL = 46, GAP = 2;
const VS_CELL = 46, VS_GAP = 2;
const DEFAULT_TIME = 120;
const AI_INTERVAL_MS = 480;
const ONNX_URL = './fruitbox_policy.onnx';

// ── Theme ─────────────────────────────────────────────────────────────────────
const THEME_COLORS = {
  dark: {
    bg: '#161614', cellBg: '#262522', cellBorder: '#3a3834', cleared: '#1e1e1b',
    text: '#dcdad4', textDim: '#82807a',
    selFill: 'rgba(80,150,230,0.23)',   selBorder: '#5096e6',
    validFill: 'rgba(29,158,117,0.25)', validBorder: '#1d9e75',
    badFill: 'rgba(226,75,74,0.23)',    badBorder: '#c84646',
    aiSel: 'rgba(180,100,240,0.35)',    aiBorder: '#b064f0',
  },
  light: {
    bg: '#f5f4ef', cellBg: '#e2e1db', cellBorder: '#c8c7c0', cleared: '#d8d7d2',
    text: '#1c1b18', textDim: '#6e6c65',
    selFill: 'rgba(24,101,190,0.15)',   selBorder: '#1865be',
    validFill: 'rgba(15,110,75,0.18)',  validBorder: '#0f7850',
    badFill: 'rgba(180,50,50,0.15)',    badBorder: '#b83232',
    aiSel: 'rgba(120,50,200,0.25)',     aiBorder: '#8032c8',
  },
};

let C = { ...THEME_COLORS.dark };
let darkMode = localStorage.getItem('darkMode') !== '0';

function applyTheme(dark) {
  darkMode = dark;
  C = { ...THEME_COLORS[dark ? 'dark' : 'light'] };
  document.documentElement.dataset.theme = dark ? '' : 'light';
  localStorage.setItem('darkMode', dark ? '1' : '0');
}

// ── Keybindings ───────────────────────────────────────────────────────────────
const KEY_DEFAULTS = { pause: 'Space', restart: 'KeyR', menu: 'Escape' };
let keybinds = { ...KEY_DEFAULTS };

let vsAiDefaultHidden = true;

function loadSettings() {
  try {
    const saved = JSON.parse(localStorage.getItem('keybinds') || '{}');
    keybinds = { ...KEY_DEFAULTS, ...saved };
  } catch { keybinds = { ...KEY_DEFAULTS }; }
  const savedHidden = localStorage.getItem('vsAiDefaultHidden');
  if (savedHidden !== null) vsAiDefaultHidden = savedHidden !== '0';
}

function saveSettings() {
  localStorage.setItem('keybinds', JSON.stringify(keybinds));
}

function keyCodeDisplay(code) {
  if (code === 'Space')  return 'SPACE';
  if (code === 'Escape') return 'ESC';
  if (code.startsWith('Key'))   return code.slice(3);
  if (code.startsWith('Digit')) return code.slice(5);
  return code;
}

// ── Custom mode state ─────────────────────────────────────────────────────────
const CUSTOM_DEFAULTS = { rows: 10, cols: 17, timeLimit: 120, seed: null, gridBase: 'random' };
let customSettings = { ...CUSTOM_DEFAULTS };

// ── Grid-type pill state ──────────────────────────────────────────────────────
const GRID_TYPES = ['random', 'solvable', 'custom'];
let gridTypeIdx = 0;

function selectedGridType() { return GRID_TYPES[gridTypeIdx]; }

// ── Game state ────────────────────────────────────────────────────────────────
let pyodide = null, onnxSession = null, opfsMount = null;

let playRows = DEFAULT_ROWS, playCols = DEFAULT_COLS, playTimeLimit = DEFAULT_TIME;
let playGrid = null, playScore = 0, playTimeRemaining = 0;
let playGameOver = false, playPaused = false;
let playGameSeed = null, playGameStart = 0, playIsCustom = false;

let vsHumanGrid = null, vsAiGrid = null;
let vsHumanScore = 0, vsAiScore = 0, vsTimeRemaining = 0;
let vsHumanOver = false, vsAiOver = false, vsGameOver = false;
let vsGameSeed = null, vsGameStart = 0, vsPaused = false;
let vsMobilePovAi = false;
let lastAiMoveTs = 0, aiHighlight = null;

let watchGrid = null, watchScore = 0, watchTimeRemaining = 0;
let watchOver = false, watchGameStart = 0;
let lastWatchAiTs = 0, watchHighlight = null;

let dragStart = null, dragEnd = null;
let animId = null, lastTs = null;

// ── DOM helpers ───────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);
const showScreen = id => {
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
  $(id).classList.add('active');
};
const setGameUrl = (mode, seed, gridType) => {
  const url = `${location.pathname}?seed=${seed}&mode=${mode}&grid=${gridType}`;
  history.replaceState(null, '', url);
};
const clearGameUrl = () => history.replaceState(null, '', location.pathname);
const setProgress = (pct, msg) => {
  $('progress-fill').style.width = pct + '%';
  $('loading-status').textContent = msg;
};
const fmt = secs => {
  const m = Math.floor(secs / 60), s = Math.floor(secs % 60);
  return `${m}:${String(s).padStart(2, '0')}`;
};
const fmtTime = secs => {
  if (secs < 60)   return secs + 's';
  if (secs < 3600) { const m = Math.floor(secs/60), s = secs%60; return s ? `${m}m ${s}s` : `${m}m`; }
  const h = Math.floor(secs/3600), m = Math.floor((secs%3600)/60); return `${h}h ${m}m`;
};
const showOver = (id, cls) => {
  const el = $(id); el.classList.add('show');
  const card = el.querySelector('.over-card');
  card.className = 'over-card ' + (cls || '');
};
const hideOver = id => $(id).classList.remove('show');

let toastTimer = null;
function showToast(msg = 'Copied!') {
  const t = $('toast');
  t.textContent = msg;
  t.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove('show'), 1500);
}

// ── Overlay management ────────────────────────────────────────────────────────
function openOverlay(id) {
  closeAllOverlays();
  $(id).classList.add('visible');
}
function closeOverlay(id) { $(id).classList.remove('visible'); }
function closeAllOverlays() {
  document.querySelectorAll('.overlay.visible').forEach(o => o.classList.remove('visible'));
}
function anyOverlayOpen() {
  return !!document.querySelector('.overlay.visible');
}

// ── Python helpers string ─────────────────────────────────────────────────────
const PYTHON_HELPERS = `
import sys, json as _json
import numpy as np
from fruitbox_core.game import FruitBoxGame
from fruitbox_core.env import FruitBoxEnv
import fruitbox_core.stats as _stats

_play = None
_play_time_limit = 120
_vs_human = None
_vs_env = None
_watch_env = None

# ── single player ─────────────────────────────────────────────────────────────
def play_init(grid_type, seed=None, rows=10, cols=17, time_limit=120):
    global _play, _play_time_limit
    _play_time_limit = int(time_limit)
    _play = FruitBoxGame(rows=int(rows), columns=int(cols),
                         grid_type=str(grid_type), time_limit=_play_time_limit)
    _play.reset(None if seed is None else int(seed))

def play_grid():       return _play.grid.flatten().tolist()
def play_tick(dt):     return bool(_play.tick(float(dt)))
def play_score():      return int(_play.score)
def play_time():       return float(_play.time_remaining)
def play_seed():       return int(_play.seed)
def play_elapsed():    return float(_play.elapsed)
def play_paused():     return bool(_play.paused)
def play_pause():      _play.pause()
def play_resume():     _play.resume()
def play_rows():       return int(_play.grid.shape[0])
def play_cols():       return int(_play.grid.shape[1])
def play_time_limit(): return _play_time_limit

def play_validate(r1, c1, r2, c2):
    return bool(_play.validate_move(int(r1),int(c1),int(r2),int(c2)))

def play_apply(r1, c1, r2, c2):
    pts, done = _play.apply_move(int(r1),int(c1),int(r2),int(c2))
    return [int(pts), bool(done)]

# ── vs AI ─────────────────────────────────────────────────────────────────────
def vs_init(grid_type, seed=None):
    global _vs_human, _vs_env
    _seed = None if seed is None else int(seed)
    _vs_human = FruitBoxGame(grid_type=grid_type)
    _vs_human.reset(_seed)
    _vs_env = FruitBoxEnv(grid_type=grid_type)
    _vs_env.game.reset(_seed)
    _vs_env.game.grid = _vs_human.grid.copy()

def vs_human_grid():  return _vs_human.grid.flatten().tolist()
def vs_ai_grid():     return _vs_env.game.grid.flatten().tolist()
def vs_human_score(): return int(_vs_human.score)
def vs_ai_score():    return int(_vs_env.game.score)
def vs_time():        return float(_vs_human.time_remaining)
def vs_seed():        return int(_vs_human.seed)
def vs_elapsed():     return float(_vs_human.elapsed)
def vs_paused():      return bool(_vs_human.paused)
def vs_pause():       _vs_human.pause();  _vs_env.game.pause()
def vs_resume():      _vs_human.resume(); _vs_env.game.resume()

def vs_tick(dt):
    dt = float(dt)
    timed = bool(_vs_human.tick(dt))
    _vs_env.game.elapsed = _vs_human.elapsed
    return timed

def vs_human_validate(r1, c1, r2, c2):
    return bool(_vs_human.validate_move(int(r1),int(c1),int(r2),int(c2)))

def vs_human_apply(r1, c1, r2, c2):
    pts, done = _vs_human.apply_move(int(r1),int(c1),int(r2),int(c2))
    return [int(pts), bool(done)]

def vs_ai_inputs():
    obs = _vs_env._obs()
    return {'grid': obs['grid'].astype(np.float32).tolist(), 'score': float(obs['score'][0])}

def vs_ai_valid_moves():
    return [list(m) for m in _vs_env.game.get_valid_moves()]

def vs_ai_decode(action):
    r1,c1,r2,c2 = _vs_env._decode(int(action))
    return [int(r1),int(c1),int(r2),int(c2)]

def vs_ai_apply(r1, c1, r2, c2):
    pts, done = _vs_env.game.apply_move(int(r1),int(c1),int(r2),int(c2))
    return [int(pts), bool(done)]

# ── watch AI ──────────────────────────────────────────────────────────────────
def watch_init(grid_type, seed=None):
    global _watch_env
    _watch_env = FruitBoxEnv(grid_type=grid_type)
    _watch_env.game.reset(None if seed is None else int(seed))

def watch_grid():    return _watch_env.game.grid.flatten().tolist()
def watch_score():   return int(_watch_env.game.score)
def watch_time():    return float(_watch_env.game.time_remaining)
def watch_seed():    return int(_watch_env.game.seed)
def watch_elapsed(): return float(_watch_env.game.elapsed)

def watch_tick(dt):
    return bool(_watch_env.game.tick(float(dt)))

def watch_inputs():
    obs = _watch_env._obs()
    return {'grid': obs['grid'].astype(np.float32).tolist(), 'score': float(obs['score'][0])}

def watch_valid_moves():
    return [list(m) for m in _watch_env.game.get_valid_moves()]

def watch_decode(action):
    r1,c1,r2,c2 = _watch_env._decode(int(action))
    return [int(r1),int(c1),int(r2),int(c2)]

def watch_apply(r1, c1, r2, c2):
    pts, done = _watch_env.game.apply_move(int(r1),int(c1),int(r2),int(c2))
    return [int(pts), bool(done)]

# ── stats ─────────────────────────────────────────────────────────────────────
def stats_record(gamemode, grid_type, self_score, seed, time_elapsed, opp_score=None):
    _stats.record(_stats.GameInfo(
        gamemode=str(gamemode), grid_type=str(grid_type),
        self_score=int(self_score), seed=int(seed),
        time_elapsed=float(time_elapsed),
        opp_score=int(opp_score) if opp_score is not None else None,
    ))

def stats_summary_json():
    return _json.dumps(_stats.get_summary())

def stats_history_json():
    return _json.dumps(_stats.get_history())
`;

// ── Pyodide init ──────────────────────────────────────────────────────────────
async function initPyodide() {
  setProgress(5, 'Loading Python runtime…');
  pyodide = await loadPyodide();

  setProgress(25, 'Loading packages…');
  await pyodide.loadPackage(['numpy', 'sqlite3']);

  setProgress(40, 'Mounting storage…');
  await mountOPFS();

  setProgress(55, 'Loading game engine…');
  await loadFruitboxCore();

  if (opfsMount) {
    try {
      await pyodide.runPythonAsync(`
import fruitbox_core.stats as _s
_s._PATH = "/fruitbox/fruitbox_stats.db"
`);
    } catch (e) {
      console.warn('Failed to configure stats path:', e);
    }
  }

  setProgress(75, 'Running init…');
  await pyodide.runPythonAsync(PYTHON_HELPERS);

  setProgress(85, 'Loading AI model…');
  await loadOnnx();

  setProgress(100, 'Ready');
}

async function mountOPFS() {
  try {
    const opfsRoot = await navigator.storage.getDirectory();
    const dir = await opfsRoot.getDirectoryHandle('fruitbox', { create: true });
    opfsMount = await pyodide.mountNativeFS('/fruitbox', dir);
  } catch (e) {
    console.warn('OPFS unavailable, stats will not persist:', e);
  }
}

async function loadFruitboxCore() {
  const files = ['__init__.py', 'game.py', 'grid.py', 'stats.py', 'env.py'];
  pyodide.FS.mkdir('/home/pyodide/fruitbox_core');
  await Promise.all(files.map(async f => {
    const r = await fetch(`./fruitbox_core/${f}`);
    if (!r.ok) return;
    pyodide.FS.writeFile(`/home/pyodide/fruitbox_core/${f}`, await r.text());
  }));
}

async function loadOnnx() {
  ort.env.wasm.numThreads = 1;
  onnxSession = await ort.InferenceSession.create(ONNX_URL);
}

async function syncStats() {
  if (opfsMount) {
    try { await opfsMount.syncfs(); } catch (e) { console.warn('syncfs failed', e); }
  }
}

// ── py() helper ───────────────────────────────────────────────────────────────
function py(name, ...args) {
  const result = pyodide.globals.get(name)(...args);
  if (result && typeof result.toJs === 'function') {
    const js = result.toJs({ dict_converter: Object.fromEntries });
    result.destroy();
    return js;
  }
  return result;
}

// ── ONNX inference ────────────────────────────────────────────────────────────
async function onnxStep(inputs, validMoves) {
  const N = DEFAULT_ROWS * DEFAULT_COLS;
  const gridData  = new Float32Array(inputs.grid);
  const scoreData = new Float32Array([inputs.score]);
  const results = await onnxSession.run({
    grid:  new ort.Tensor('float32', gridData,  [1, N]),
    score: new ort.Tensor('float32', scoreData, [1, 1]),
  });
  const logits = results.logits.data;
  const masked = new Float32Array(N * N).fill(-1e9);
  for (const [r1, c1, r2, c2] of validMoves) {
    const a = (r1 * DEFAULT_COLS + c1) * N + (r2 * DEFAULT_COLS + c2);
    masked[a] = logits[a];
  }
  let best = 0, bestVal = -Infinity;
  for (let i = 0; i < masked.length; i++) {
    if (masked[i] > bestVal) { bestVal = masked[i]; best = i; }
  }
  return best;
}

// ── Canvas rendering ──────────────────────────────────────────────────────────
function setupCanvas(canvas, rows, cols, cellSize, gap) {
  const step = cellSize + gap;
  const rot = isMobileRotated();
  const w = step * (rot ? rows : cols) - gap;
  const h = step * (rot ? cols : rows) - gap;
  canvas.width = w; canvas.height = h;
  return { step, w, h };
}

function pixelToCell(canvas, px, py_, cellSize, gap, rows, cols) {
  const step = cellSize + gap;
  const rect = canvas.getBoundingClientRect();
  const x = (px - rect.left) * (canvas.width / rect.width);
  const y = (py_ - rect.top)  * (canvas.height / rect.height);
  const rot = isMobileRotated();
  const r = Math.floor((rot ? x : y) / step);
  const c = Math.floor((rot ? y : x) / step);
  if (r >= 0 && r < rows && c >= 0 && c < cols) return [r, c];
  return null;
}

function selBounds(a, b) {
  if (!a || !b) return null;
  return [Math.min(a[0],b[0]), Math.min(a[1],b[1]),
          Math.max(a[0],b[0]), Math.max(a[1],b[1])];
}

function drawBoard(canvas, grid, rows, cols, cellSize, gap, {
  drag = null, validDrag = null, aiSel = null, paused = false,
} = {}) {
  if (!grid) return;
  const ctx  = canvas.getContext('2d');
  const step = cellSize + gap;
  const rot = isMobileRotated();

  ctx.fillStyle = C.bg;
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  const fontSize = Math.floor(cellSize * 0.46);
  ctx.font = `600 ${fontSize}px system-ui, sans-serif`;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';

  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const v = grid[r * cols + c];
      const x = (rot ? r : c) * step, y = (rot ? c : r) * step;
      if (v === -1) {
        ctx.fillStyle = C.cleared;
        ctx.fillRect(x, y, cellSize, cellSize);
      } else {
        ctx.fillStyle = C.cellBg;
        ctx.fillRect(x, y, cellSize, cellSize);
        ctx.strokeStyle = C.cellBorder;
        ctx.lineWidth = 1;
        ctx.strokeRect(x + 0.5, y + 0.5, cellSize - 1, cellSize - 1);
        ctx.fillStyle = C.text;
        ctx.fillText(v, x + cellSize / 2, y + cellSize / 2);
      }
    }
  }

  if (aiSel) {
    const [r1,c1,r2,c2] = aiSel;
    const sx = (rot ? r1 : c1)*step, sy = (rot ? c1 : r1)*step;
    const sw = (rot ? r2-r1 : c2-c1)*step+cellSize, sh = (rot ? c2-c1 : r2-r1)*step+cellSize;
    ctx.fillStyle = C.aiSel;   ctx.fillRect(sx, sy, sw, sh);
    ctx.strokeStyle = C.aiBorder; ctx.lineWidth = 2;
    ctx.strokeRect(sx+1, sy+1, sw-2, sh-2);
  }

  if (drag) {
    const [r1,c1,r2,c2] = drag;
    const sx = (rot ? r1 : c1)*step, sy = (rot ? c1 : r1)*step;
    const sw = (rot ? r2-r1 : c2-c1)*step+cellSize, sh = (rot ? c2-c1 : r2-r1)*step+cellSize;
    ctx.fillStyle   = validDrag === true  ? C.validFill  : validDrag === false ? C.badFill  : C.selFill;
    ctx.strokeStyle = validDrag === true  ? C.validBorder: validDrag === false ? C.badBorder: C.selBorder;
    ctx.fillRect(sx, sy, sw, sh);
    ctx.lineWidth = 2;
    ctx.strokeRect(sx+1, sy+1, sw-2, sh-2);
  }

}

// ── Timer bar ─────────────────────────────────────────────────────────────────
function updateTimerBar(barId, remaining, timeLimit) {
  const pct = Math.max(0, remaining / timeLimit * 100);
  const bar = $(barId);
  bar.style.width = pct + '%';
  bar.style.background =
    remaining > 30 ? 'var(--timer-ok)' :
    remaining > 10 ? 'var(--timer-warn)' : 'var(--timer-danger)';
}

// ── Grid loading overlay ──────────────────────────────────────────────────────
function drawGridOverlay(...canvases) {
  for (const canvas of canvases) {
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue('--card-bg').trim();
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = C.text;
    ctx.font = '700 36px system-ui, sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText('Generating…', canvas.width / 2, canvas.height / 2);
  }
}

// ── Single player ─────────────────────────────────────────────────────────────
async function startPlay(gridType, opts = {}) {
  const rows      = opts.rows      ?? DEFAULT_ROWS;
  const cols      = opts.cols      ?? DEFAULT_COLS;
  playTimeLimit   = opts.timeLimit ?? DEFAULT_TIME;
  const seed      = opts.seed      ?? null;
  playIsCustom    = opts.isCustom  ?? false;

  if (opts.overlay) {
    $('play-canvas-wrap').classList.remove('board-paused');
    drawGridOverlay($('canvas-play'));
  } else {
    setProgress(100, 'Generating grid…');
    showScreen('screen-loading');
  }
  await new Promise(r => setTimeout(r, 0));

  py('play_init', gridType, seed, rows, cols, playTimeLimit);
  playRows = py('play_rows');
  playCols = py('play_cols');
  playTimeLimit = py('play_time_limit');
  playGrid = py('play_grid');
  playScore = 0; playTimeRemaining = playTimeLimit;
  playGameOver = false; playPaused = false;
  $('play-pause-icon').src = './assets/pause.circle.png';
  $('play-canvas-wrap').classList.remove('board-paused');
  playGameSeed = py('play_seed');
  setGameUrl('single', playGameSeed, gridType);
  playGameStart = performance.now();
  dragStart = null; dragEnd = null;

  const canvas = $('canvas-play');
  setupCanvas(canvas, playRows, playCols, CELL, GAP);
  hideOver('play-over');
  $('play-score').textContent = '0';
  $('play-timer').textContent = fmt(playTimeLimit);
  updateTimerBar('play-timerbar', playTimeLimit, playTimeLimit);

  showScreen('screen-play');
  lastTs = null;
  if (animId) cancelAnimationFrame(animId);
  animId = requestAnimationFrame(playLoop);
}

function playLoop(ts) {
  animId = null;

  const bounds = selBounds(dragStart, dragEnd);

  if (playGameOver) {
    drawBoard($('canvas-play'), playGrid, playRows, playCols, CELL, GAP,
      { drag: bounds, validDrag: null, paused: false });
    animId = requestAnimationFrame(playLoop);
    return;
  }

  const dt = lastTs === null ? 0 : (ts - lastTs) / 1000;
  lastTs = ts;

  if (!playPaused) {
    const timedOut = py('play_tick', dt);
    playTimeRemaining = py('play_time');
    playScore = py('play_score');
    if (timedOut) { endPlay("Time's up!"); return; }
  }

  playGrid = py('play_grid');
  let isValid = null;
  if (bounds) isValid = py('play_validate', ...bounds);

  drawBoard($('canvas-play'), playGrid, playRows, playCols, CELL, GAP,
    { drag: bounds, validDrag: isValid, paused: playPaused });

  $('play-score').textContent = playScore;
  $('play-timer').textContent = fmt(playTimeRemaining);
  updateTimerBar('play-timerbar', playTimeRemaining, playTimeLimit);

  animId = requestAnimationFrame(playLoop);
}

function endPlay(reason) {
  playGameOver = true;
  if (!animId) animId = requestAnimationFrame(playLoop);
  $('play-over-reason').textContent = reason;
  $('play-over-score').textContent = playScore;
  showOver('play-over', '');
  try {
    const gamemode = playIsCustom ? 'custom' : 'single_player';
    py('stats_record', gamemode, selectedGridType() === 'custom' ? customSettings.gridBase : selectedGridType(),
      playScore, playGameSeed, (performance.now() - playGameStart) / 1000);
    syncStats();
  } catch(e) { console.warn('stats_record failed', e); }
}

function setupPlayInput() {
  const canvas = $('canvas-play');
  canvas.addEventListener('mousedown', e => {
    if (playPaused || anyOverlayOpen()) return;
    const cell = pixelToCell(canvas, e.clientX, e.clientY, CELL, GAP, playRows, playCols);
    if (cell) { dragStart = cell; dragEnd = cell; }
  });
  canvas.addEventListener('mousemove', e => {
    if (!dragStart || playPaused) return;
    const cell = pixelToCell(canvas, e.clientX, e.clientY, CELL, GAP, playRows, playCols);
    if (cell) dragEnd = cell;
  });
  canvas.addEventListener('mouseup', () => {
    if (!dragStart || playPaused) return;
    if (!playGameOver) {
      const bounds = selBounds(dragStart, dragEnd);
      if (bounds) {
        const [pts, noMoves] = py('play_apply', ...bounds);
        if (noMoves) { dragStart = null; dragEnd = null; endPlay('No more moves'); return; }
      }
    }
    dragStart = null; dragEnd = null;
  });
  canvas.addEventListener('mouseleave', () => { dragStart = null; dragEnd = null; });

  canvas.addEventListener('touchstart', e => {
    if (playPaused || anyOverlayOpen()) return;
    const t = e.touches[0];
    const cell = pixelToCell(canvas, t.clientX, t.clientY, CELL, GAP, playRows, playCols);
    if (cell) { dragStart = cell; dragEnd = cell; }
    e.preventDefault();
  }, { passive: false });
  canvas.addEventListener('touchmove', e => {
    if (!dragStart || playPaused) return;
    const t = e.touches[0];
    const cell = pixelToCell(canvas, t.clientX, t.clientY, CELL, GAP, playRows, playCols);
    if (cell) dragEnd = cell;
    e.preventDefault();
  }, { passive: false });
  canvas.addEventListener('touchend', e => {
    if (!dragStart || playPaused) return;
    if (!playGameOver) {
      const bounds = selBounds(dragStart, dragEnd);
      if (bounds) {
        const [, noMoves] = py('play_apply', ...bounds);
        if (noMoves) { dragStart = null; dragEnd = null; endPlay('No more moves'); return; }
      }
    }
    dragStart = null; dragEnd = null;
  });
  canvas.addEventListener('touchcancel', () => { dragStart = null; dragEnd = null; });

  $('play-pause').onclick = () => {
    if (playGameOver) return;
    if (playPaused) { py('play_resume'); playPaused = false; $('play-pause-icon').src = './assets/pause.circle.png'; $('play-canvas-wrap').classList.remove('board-paused'); lastTs = null; }
    else            { py('play_pause');  playPaused = true;  $('play-pause-icon').src = './assets/play.circle.png';  $('play-canvas-wrap').classList.add('board-paused'); }
  };
  $('play-restart').onclick = () => {
    cancelAnimationFrame(animId);
    startPlay(selectedGridType() === 'custom' ? customSettings.gridBase : selectedGridType(),
      selectedGridType() === 'custom' ? { ...customSettings, isCustom: true, overlay: true } : { overlay: true });
  };
  $('play-back').onclick = () => { cancelAnimationFrame(animId); showMenu(); };
  $('play-over-again').onclick = () => $('play-restart').onclick();
  $('play-over-share').onclick = () => {
    const elapsed = Math.floor(playTimeLimit - playTimeRemaining);
    const timeStr = `${elapsed}s`;
    const text = `I've reached ${playScore} on ShroomBox in ${timeStr}\nTry beating me here! ${location.href}`;
    navigator.clipboard.writeText(text).then(() => {
      const btn = $('play-over-share');
      btn.textContent = 'Copied!';
      setTimeout(() => { btn.textContent = 'Share'; }, 2000);
    });
  };
  $('play-over-menu').onclick  = () => showMenu();
  $('play-over-close').onclick = () => hideOver('play-over');
}

// ── VS AI ─────────────────────────────────────────────────────────────────────
async function startVs(gridType, seed = null, overlay = false) {
  if (overlay) {
    $('vs-human-canvas-wrap').classList.remove('board-paused');
    drawGridOverlay($('canvas-human'), $('canvas-ai-board'));
  } else {
    setProgress(100, 'Generating grid…');
    showScreen('screen-loading');
  }
  await new Promise(r => setTimeout(r, 0));

  py('vs_init', gridType, seed);
  vsHumanGrid = py('vs_human_grid');
  vsAiGrid    = py('vs_ai_grid');
  vsHumanScore = 0; vsAiScore = 0; vsTimeRemaining = DEFAULT_TIME;
  vsHumanOver = false; vsAiOver = false; vsGameOver = false; vsPaused = false;
  $('vs-pause-icon').src = './assets/pause.circle.png';
  $('vs-human-canvas-wrap').classList.remove('board-paused');
  $('vs-ai-board-wrap').classList.toggle('board-covered', vsAiDefaultHidden);
  $('vs-toggle-ai-icon').src = vsAiDefaultHidden ? './assets/eye.slash.png' : './assets/eye.png';
  $('vs-toggle-ai-board').title = vsAiDefaultHidden ? 'Show AI board' : 'Hide AI board';
  if (window.matchMedia('(max-width: 700px)').matches) {
    vsMobilePovAi = false;
    $('vs-ai-board-wrap').classList.remove('board-covered');
    $('vs-human-canvas-wrap').closest('.board-wrap').classList.remove('pov-hidden');
    $('vs-ai-board-wrap').closest('.board-wrap').classList.add('pov-hidden');
    $('vs-toggle-ai-board').title = 'Switch to AI board';
  }
  vsGameSeed  = py('vs_seed');
  setGameUrl('vs', vsGameSeed, gridType);
  vsGameStart = performance.now();
  dragStart = null; dragEnd = null;
  lastAiMoveTs = performance.now() + 800;
  aiHighlight = null;

  setupCanvas($('canvas-human'),   DEFAULT_ROWS, DEFAULT_COLS, VS_CELL, VS_GAP);
  setupCanvas($('canvas-ai-board'),DEFAULT_ROWS, DEFAULT_COLS, VS_CELL, VS_GAP);
  hideOver('vs-over');
  $('vs-human-score').textContent = '0';
  $('vs-ai-score').textContent = '0';
  $('vs-timer').textContent = fmt(DEFAULT_TIME);
  updateTimerBar('vs-timerbar', DEFAULT_TIME, DEFAULT_TIME);

  showScreen('screen-vs');
  lastTs = null;
  if (animId) cancelAnimationFrame(animId);
  animId = requestAnimationFrame(vsLoop);
}

function vsLoop(ts) {
  animId = null;
  if (vsGameOver) return;

  const dt = lastTs === null ? 0 : (ts - lastTs) / 1000;
  lastTs = ts;

  if (!vsPaused) {
    if (!vsHumanOver || !vsAiOver) {
      const timedOut = py('vs_tick', dt);
      vsTimeRemaining = py('vs_time');
      vsHumanScore = py('vs_human_score');
      vsAiScore    = py('vs_ai_score');
      if (timedOut) { vsHumanOver = true; vsAiOver = true; }
    }
    if (!vsAiOver && ts >= lastAiMoveTs) {
      lastAiMoveTs = ts + AI_INTERVAL_MS;
      runVsAiStep();
    }
  }

  if (aiHighlight && ts > aiHighlight.until) aiHighlight = null;

  vsHumanGrid = py('vs_human_grid');
  vsAiGrid    = py('vs_ai_grid');

  const bounds = selBounds(dragStart, dragEnd);
  let isValid = null;
  if (bounds && !vsHumanOver) isValid = py('vs_human_validate', ...bounds);

  drawBoard($('canvas-human'),   vsHumanGrid, DEFAULT_ROWS, DEFAULT_COLS, VS_CELL, VS_GAP,
    { drag: bounds, validDrag: isValid, paused: vsPaused });
  drawBoard($('canvas-ai-board'), vsAiGrid,   DEFAULT_ROWS, DEFAULT_COLS, VS_CELL, VS_GAP,
    { aiSel: aiHighlight ? [aiHighlight.r1,aiHighlight.c1,aiHighlight.r2,aiHighlight.c2] : null });

  $('vs-human-score').textContent = vsHumanScore;
  $('vs-ai-score').textContent    = vsAiScore;
  $('vs-timer').textContent       = fmt(vsTimeRemaining);
  updateTimerBar('vs-timerbar', vsTimeRemaining, DEFAULT_TIME);

  if ((vsHumanOver && vsAiOver) || vsTimeRemaining <= 0) { endVs(); return; }

  animId = requestAnimationFrame(vsLoop);
}

async function runVsAiStep() {
  try {
    const inputs = py('vs_ai_inputs');
    const validMovesProxy = pyodide.globals.get('vs_ai_valid_moves')();
    const validMoves = validMovesProxy.toJs();
    validMovesProxy.destroy();
    if (!validMoves || validMoves.length === 0) { vsAiOver = true; return; }
    const action = await onnxStep(inputs, validMoves);
    const move = py('vs_ai_decode', action);
    const [, noMoves] = py('vs_ai_apply', ...move);
    aiHighlight = { r1:move[0], c1:move[1], r2:move[2], c2:move[3], until: performance.now() + 250 };
    if (noMoves) vsAiOver = true;
  } catch(e) { console.error('AI step error', e); }
}

function endVs() {
  vsGameOver = true;
  if (animId) { cancelAnimationFrame(animId); animId = null; }
  const h = vsHumanScore, a = vsAiScore;
  let reason, cls;
  if      (h > a) { reason = `You win!  ${h} – ${a}`;  cls = 'win'; }
  else if (a > h) { reason = `AI wins!  ${h} – ${a}`;  cls = 'lose'; }
  else            { reason = `Tie!  ${h} – ${a}`;       cls = 'tie'; }
  $('vs-over-reason').textContent = reason;
  $('vs-over-human').textContent  = h;
  $('vs-over-ai').textContent     = a;
  showOver('vs-over', cls);
  try {
    const gt = selectedGridType() === 'custom' ? customSettings.gridBase : selectedGridType();
    py('stats_record', 'vs_ai', gt, h, vsGameSeed, (performance.now() - vsGameStart) / 1000, a);
    syncStats();
  } catch(e) { console.warn('stats_record failed', e); }
}

function setupVsInput() {
  const canvas = $('canvas-human');
  canvas.addEventListener('mousedown', e => {
    if (vsGameOver || vsHumanOver || vsPaused || anyOverlayOpen()) return;
    const cell = pixelToCell(canvas, e.clientX, e.clientY, VS_CELL, VS_GAP, DEFAULT_ROWS, DEFAULT_COLS);
    if (cell) { dragStart = cell; dragEnd = cell; }
  });
  canvas.addEventListener('mousemove', e => {
    if (!dragStart || vsGameOver || vsHumanOver || vsPaused) return;
    const cell = pixelToCell(canvas, e.clientX, e.clientY, VS_CELL, VS_GAP, DEFAULT_ROWS, DEFAULT_COLS);
    if (cell) dragEnd = cell;
  });
  canvas.addEventListener('mouseup', () => {
    if (!dragStart || vsGameOver || vsHumanOver || vsPaused) return;
    const bounds = selBounds(dragStart, dragEnd);
    if (bounds) {
      const [, noMoves] = py('vs_human_apply', ...bounds);
      if (noMoves) vsHumanOver = true;
    }
    dragStart = null; dragEnd = null;
  });
  canvas.addEventListener('mouseleave', () => { dragStart = null; dragEnd = null; });

  canvas.addEventListener('touchstart', e => {
    if (vsGameOver || vsHumanOver || vsPaused || anyOverlayOpen()) return;
    const t = e.touches[0];
    const cell = pixelToCell(canvas, t.clientX, t.clientY, VS_CELL, VS_GAP, DEFAULT_ROWS, DEFAULT_COLS);
    if (cell) { dragStart = cell; dragEnd = cell; }
    e.preventDefault();
  }, { passive: false });
  canvas.addEventListener('touchmove', e => {
    if (!dragStart || vsGameOver || vsHumanOver || vsPaused) return;
    const t = e.touches[0];
    const cell = pixelToCell(canvas, t.clientX, t.clientY, VS_CELL, VS_GAP, DEFAULT_ROWS, DEFAULT_COLS);
    if (cell) dragEnd = cell;
    e.preventDefault();
  }, { passive: false });
  canvas.addEventListener('touchend', e => {
    if (!dragStart || vsGameOver || vsHumanOver || vsPaused) return;
    const bounds = selBounds(dragStart, dragEnd);
    if (bounds) {
      const [, noMoves] = py('vs_human_apply', ...bounds);
      if (noMoves) vsHumanOver = true;
    }
    dragStart = null; dragEnd = null;
  });
  canvas.addEventListener('touchcancel', () => { dragStart = null; dragEnd = null; });

  $('vs-pause').onclick = () => {
    if (vsGameOver) return;
    if (vsPaused) { py('vs_resume'); vsPaused = false; $('vs-pause-icon').src = './assets/pause.circle.png'; $('vs-human-canvas-wrap').classList.remove('board-paused'); lastTs = null; }
    else          { py('vs_pause');  vsPaused = true;  $('vs-pause-icon').src = './assets/play.circle.png';  $('vs-human-canvas-wrap').classList.add('board-paused'); }
  };
  $('vs-restart').onclick  = () => {
    cancelAnimationFrame(animId);
    const gt = selectedGridType() === 'custom' ? customSettings.gridBase : selectedGridType();
    startVs(gt, null, true);
  };
  $('vs-back').onclick       = () => { cancelAnimationFrame(animId); showMenu(); };
  $('vs-over-again').onclick = () => $('vs-restart').onclick();
  $('vs-over-share').onclick = () => {
    const elapsed = Math.floor(DEFAULT_TIME - vsTimeRemaining);
    const text = `I scored ${vsHumanScore} on ShroomBox vs AI in ${elapsed}s\nTry beating me here! ${location.href}`;
    navigator.clipboard.writeText(text).then(() => {
      const btn = $('vs-over-share');
      btn.textContent = 'Copied!';
      setTimeout(() => { btn.textContent = 'Share'; }, 2000);
    });
  };
  $('vs-over-menu').onclick  = () => showMenu();
  $('vs-over-close').onclick = () => hideOver('vs-over');
}

// ── Watch AI ──────────────────────────────────────────────────────────────────
async function startWatch(gridType, seed = null, overlay = false) {
  if (overlay) {
    drawGridOverlay($('canvas-watch'));
  } else {
    setProgress(100, 'Generating grid…');
    showScreen('screen-loading');
  }
  await new Promise(r => setTimeout(r, 0));

  py('watch_init', gridType, seed);
  watchGrid = py('watch_grid');
  setGameUrl('demo', py('watch_seed'), gridType);
  watchScore = 0; watchTimeRemaining = DEFAULT_TIME; watchOver = false;
  watchGameStart = performance.now();
  lastWatchAiTs = performance.now() + 600;
  watchHighlight = null;

  setupCanvas($('canvas-watch'), DEFAULT_ROWS, DEFAULT_COLS, CELL, GAP);
  hideOver('watch-over');
  $('watch-score').textContent = '0';
  $('watch-timer').textContent = fmt(DEFAULT_TIME);
  updateTimerBar('watch-timerbar', DEFAULT_TIME, DEFAULT_TIME);

  showScreen('screen-watch');
  lastTs = null;
  if (animId) cancelAnimationFrame(animId);
  animId = requestAnimationFrame(watchLoop);
}

function watchLoop(ts) {
  animId = null;
  if (watchOver) return;

  const dt = lastTs === null ? 0 : (ts - lastTs) / 1000;
  lastTs = ts;

  const timedOut = py('watch_tick', dt);
  watchTimeRemaining = py('watch_time');
  watchScore = py('watch_score');

  if (ts >= lastWatchAiTs) {
    lastWatchAiTs = ts + AI_INTERVAL_MS;
    runWatchAiStep();
  }

  if (watchHighlight && ts > watchHighlight.until) watchHighlight = null;

  watchGrid = py('watch_grid');
  drawBoard($('canvas-watch'), watchGrid, DEFAULT_ROWS, DEFAULT_COLS, CELL, GAP, {
    aiSel: watchHighlight ? [watchHighlight.r1,watchHighlight.c1,watchHighlight.r2,watchHighlight.c2] : null,
  });

  $('watch-score').textContent = watchScore;
  $('watch-timer').textContent = fmt(watchTimeRemaining);
  updateTimerBar('watch-timerbar', watchTimeRemaining, DEFAULT_TIME);

  if (timedOut) { endWatch("Time's up!"); return; }

  animId = requestAnimationFrame(watchLoop);
}

async function runWatchAiStep() {
  try {
    const inputs = py('watch_inputs');
    const validMovesProxy = pyodide.globals.get('watch_valid_moves')();
    const validMoves = validMovesProxy.toJs();
    validMovesProxy.destroy();
    if (!validMoves || validMoves.length === 0) { endWatch('No more moves'); return; }
    const action = await onnxStep(inputs, validMoves);
    const move   = py('watch_decode', action);
    const [, noMoves] = py('watch_apply', ...move);
    watchHighlight = { r1:move[0], c1:move[1], r2:move[2], c2:move[3], until: performance.now() + 300 };
    if (noMoves) endWatch('No more moves');
  } catch(e) { console.error('Watch AI step error', e); }
}

let watchAutoRestartTimer = null;

function endWatch(reason) {
  watchOver = true;
  if (animId) { cancelAnimationFrame(animId); animId = null; }
  $('watch-over-score').textContent = watchScore;
  showOver('watch-over', '');
  clearTimeout(watchAutoRestartTimer);
  watchAutoRestartTimer = setTimeout(() => {
    if (watchOver) {
      cancelAnimationFrame(animId);
      const gt = selectedGridType() === 'custom' ? customSettings.gridBase : selectedGridType();
      startWatch(gt, null, true);
    }
  }, 5000);
}

function setupWatchInput() {
  $('watch-restart').onclick    = () => {
    cancelAnimationFrame(animId);
    const gt = selectedGridType() === 'custom' ? customSettings.gridBase : selectedGridType();
    startWatch(gt, null, true);
  };
  $('watch-back').onclick       = () => { clearTimeout(watchAutoRestartTimer); cancelAnimationFrame(animId); showMenu(); };
  $('watch-over-again').onclick = () => { clearTimeout(watchAutoRestartTimer); $('watch-restart').onclick(); };
  $('watch-over-menu').onclick  = () => { clearTimeout(watchAutoRestartTimer); showMenu(); };
  $('watch-over-close').onclick = () => { clearTimeout(watchAutoRestartTimer); hideOver('watch-over'); };
}

// ── Settings overlay ──────────────────────────────────────────────────────────
let waitingForBinding = null;

function updateVsAiBoardBtn() {
  $('setting-vs-ai-board').textContent = vsAiDefaultHidden ? 'HIDDEN' : 'SHOWN';
}

function openSettings() {
  waitingForBinding = null;
  updateKeyBtns();
  updateVsAiBoardBtn();
  $('settings-capture-hint').classList.add('hidden');
  openOverlay('overlay-settings');
}

function updateKeyBtns() {
  ['pause','restart','menu'].forEach(k => {
    const btn = $(`key-btn-${k}`);
    btn.textContent = keyCodeDisplay(keybinds[k]);
    btn.classList.remove('waiting');
  });
}

function setupSettingsOverlay() {
  document.querySelectorAll('[data-binding]').forEach(btn => {
    btn.addEventListener('click', () => {
      if (waitingForBinding === btn.dataset.binding) {
        waitingForBinding = null;
        btn.classList.remove('waiting');
        $('settings-capture-hint').classList.add('hidden');
        return;
      }
      // clear any existing wait
      document.querySelectorAll('.key-btn.waiting').forEach(b => b.classList.remove('waiting'));
      waitingForBinding = btn.dataset.binding;
      btn.textContent = '…';
      btn.classList.add('waiting');
      $('settings-capture-hint').classList.remove('hidden');
    });
  });

  $('setting-vs-ai-board').addEventListener('click', () => {
    vsAiDefaultHidden = !vsAiDefaultHidden;
    localStorage.setItem('vsAiDefaultHidden', vsAiDefaultHidden ? '1' : '0');
    updateVsAiBoardBtn();
  });
}

// ── Stats overlay ─────────────────────────────────────────────────────────────
let statsGridFilter = 'random';
let statsHistory = [];

function openStats() {
  $('stats-view-main').classList.remove('hidden');
  $('stats-view-history').classList.add('hidden');
  loadStatsOverlay();
  openOverlay('overlay-stats');
}

function loadStatsOverlay() {
  try {
    const s = JSON.parse(py('stats_summary_json'));
    renderStatsSummary(s);
  } catch(e) {
    $('stats-overlay-content').innerHTML = '<div class="stats-loading">Stats unavailable</div>';
  }
}

function renderStatsSummary(s) {
  const totalGames = s.total_games || 0;
  const timeStr = fmtTime(s.total_time || 0);
  const score     = statsGridFilter === 'random' ? s.random_best     : s.solvable_best;
  const seed      = statsGridFilter === 'random' ? s.random_best_seed: s.solvable_best_seed;
  const bestTime  = statsGridFilter === 'random' ? s.random_best_time: s.solvable_best_time;

  const scoreStr = score != null ? String(score) : '—';
  const seedStr = seed != null ? `<span class="seed-copy-btn">Seed: ${seed}</span>` : '';

  $('stats-overlay-content').innerHTML = `
    <div class="stats-ov-section">
      <div class="stats-ov-row">
        <span class="stats-ov-label">Games Played</span>
        <span class="stats-ov-val">${totalGames || '—'}</span>
      </div>
      <div class="stats-ov-row">
        <span class="stats-ov-label">Time Played</span>
        <span class="stats-ov-val">${totalGames ? timeStr : '—'}</span>
      </div>
    </div>
    <div class="stats-ov-divider"></div>
    <div class="stats-ov-section">
      <div class="stats-ov-row">
        <span class="stats-ov-label">VS AI Record</span>
        <span class="stats-ov-val">${totalGames ? `${s.vs_wins}W &nbsp;${s.vs_losses}L &nbsp;${s.vs_ties}T` : '—'}</span>
      </div>
    </div>
    <div class="stats-ov-divider"></div>
    <div class="stats-ov-section">
      <div class="stats-highscore-row">
        <span class="stats-ov-label">Highscore</span>
        <div class="stats-filter-pills">
          <button class="stats-filter-btn ${statsGridFilter==='random'?'active':''}" data-filter="random">Random</button>
          <button class="stats-filter-btn ${statsGridFilter==='solvable'?'active':''}" data-filter="solvable">Solvable</button>
        </div>
        <span class="stats-ov-val">${scoreStr}${bestTime != null ? `<span class="stats-time"> • ${Math.round(bestTime)}s</span>` : ''}</span>
      </div>
      <div class="stats-ov-seed">${seedStr || '—'}</div>
    </div>`;

  // filter buttons
  $('stats-overlay-content').querySelectorAll('[data-filter]').forEach(btn => {
    btn.addEventListener('click', () => {
      statsGridFilter = btn.dataset.filter;
      loadStatsOverlay();
    });
  });

}

function openStatsHistory() {
  statsHistory = JSON.parse(py('stats_history_json'));
  renderHistory();
  $('stats-view-main').classList.add('hidden');
  $('stats-view-history').classList.remove('hidden');
}

function renderHistory() {
  const list = $('stats-history-list');
  const MODE = { single_player:'Single', vs_ai:'VS AI', watch_ai:'Watch', custom:'Custom' };
  list.innerHTML = statsHistory.slice(0, 50).map((g, i) => {
    const mode  = MODE[g.gamemode] ?? g.gamemode;
    const grid  = g.grid_type ? (g.grid_type[0].toUpperCase() + g.grid_type.slice(1)) : '—';
    const opp   = g.opp_score != null ? String(g.opp_score) : '—';
    const seed  = g.seed != null ? String(g.seed) : '—';
    return `<div class="history-row">
      <span>${mode}</span><span>${grid}</span><span>${g.self_score}</span>
      <span class="history-opp">${opp}</span><span class="history-seed">${seed}</span>
    </div>`;
  }).join('');

}

function setupStatsOverlay() {
  $('btn-stats-history').addEventListener('click', openStatsHistory);
  $('btn-stats-back').addEventListener('click', () => {
    $('stats-view-history').classList.add('hidden');
    $('stats-view-main').classList.remove('hidden');
    loadStatsOverlay();
  });
}

// ── Custom overlay ────────────────────────────────────────────────────────────
function openCustom() {
  // populate form from current customSettings
  $('custom-cols').value = customSettings.cols;
  $('custom-rows').value = customSettings.rows;
  $('custom-time').value = customSettings.timeLimit;
  $('custom-seed').value = customSettings.seed ?? '';
  $('custom-grid-seg').querySelectorAll('.custom-seg-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.val === customSettings.gridBase);
  });
  openOverlay('overlay-custom');
}

function readCustomForm() {
  const cols  = Math.max(5,  Math.min(30,  parseInt($('custom-cols').value) || 17));
  const rows  = Math.max(3,  Math.min(20,  parseInt($('custom-rows').value) || 10));
  const time  = Math.max(10, Math.min(3600,parseInt($('custom-time').value) || 120));
  const seedV = parseInt($('custom-seed').value);
  const seed  = isNaN(seedV) ? null : seedV;
  const base  = $('custom-grid-seg').querySelector('.custom-seg-btn.active')?.dataset.val ?? 'random';
  return { cols, rows, timeLimit: time, seed, gridBase: base };
}

function setupCustomOverlay() {
  $('custom-grid-seg').addEventListener('click', e => {
    const btn = e.target.closest('.custom-seg-btn');
    if (!btn) return;
    $('custom-grid-seg').querySelectorAll('.custom-seg-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
  });
  $('custom-reset').addEventListener('click', () => {
    customSettings = { ...CUSTOM_DEFAULTS };
    $('custom-cols').value = customSettings.cols;
    $('custom-rows').value = customSettings.rows;
    $('custom-time').value = customSettings.timeLimit;
    $('custom-seed').value = '';
    $('custom-grid-seg').querySelectorAll('.custom-seg-btn').forEach(b => {
      b.classList.toggle('active', b.dataset.val === customSettings.gridBase);
    });
  });
  $('custom-confirm').addEventListener('click', () => {
    customSettings = readCustomForm();
    closeOverlay('overlay-custom');
  });
  $('custom-close').addEventListener('click', () => closeOverlay('overlay-custom'));
  // backdrop doesn't auto-close for custom (to avoid accidental dismiss)
  $('overlay-custom').querySelector('.overlay-backdrop').addEventListener('click', () => closeOverlay('overlay-custom'));
}

// ── Pill selector ─────────────────────────────────────────────────────────────
function updatePill() {
  const gt = selectedGridType();
  const labels = { random: 'Random', solvable: 'Solvable', custom: 'Custom' };
  $('grid-type-text').textContent = labels[gt];
  $('pill-gear').classList.toggle('hidden', gt !== 'custom');
  // disable vs AI for custom (AI requires 10×17)
  $('btn-vs').disabled = (gt === 'custom');
}

function setupMenuInput() {
  $('grid-prev').addEventListener('click', () => {
    gridTypeIdx = (gridTypeIdx - 1 + GRID_TYPES.length) % GRID_TYPES.length;
    updatePill();
  });
  $('grid-next').addEventListener('click', () => {
    gridTypeIdx = (gridTypeIdx + 1) % GRID_TYPES.length;
    updatePill();
  });
  $('pill-gear').addEventListener('click', e => {
    e.stopPropagation();
    openCustom();
  });

  $('btn-play').onclick = () => {
    if (selectedGridType() === 'custom') {
      startPlay(customSettings.gridBase, { ...customSettings, isCustom: true });
    } else {
      startPlay(selectedGridType());
    }
  };
  $('btn-vs').onclick = () => {
    const gt = selectedGridType() === 'custom' ? customSettings.gridBase : selectedGridType();
    startVs(gt);
  };
  $('vs-toggle-ai-board').onclick = () => {
    if (window.matchMedia('(max-width: 700px)').matches) {
      vsMobilePovAi = !vsMobilePovAi;
      const humanWrap = $('vs-human-canvas-wrap').closest('.board-wrap');
      const aiWrap = $('vs-ai-board-wrap').closest('.board-wrap');
      humanWrap.classList.toggle('pov-hidden', vsMobilePovAi);
      aiWrap.classList.toggle('pov-hidden', !vsMobilePovAi);
      $('vs-toggle-ai-icon').src = vsMobilePovAi ? './assets/eye.png' : './assets/eye.slash.png';
      $('vs-toggle-ai-board').title = vsMobilePovAi ? 'Switch to your board' : 'Switch to AI board';
    } else {
      const wrap = $('vs-ai-board-wrap');
      const covered = wrap.classList.toggle('board-covered');
      $('vs-toggle-ai-icon').src = covered ? './assets/eye.slash.png' : './assets/eye.png';
      $('vs-toggle-ai-board').title = covered ? 'Show AI board' : 'Hide AI board';
    }
  };
  $('btn-watch').onclick = () => {
    const gt = selectedGridType() === 'custom' ? customSettings.gridBase : selectedGridType();
    startWatch(gt);
  };

  // overlay open buttons
  $('btn-settings-overlay').onclick = openSettings;
  $('btn-stats-overlay').onclick    = openStats;
  $('btn-help').onclick             = () => openOverlay('overlay-help');
  $('play-settings').onclick        = openSettings;
  $('vs-settings').onclick          = openSettings;
  $('btn-dark-mode').onclick        = () => applyTheme(!darkMode);

  // close by backdrop or × button
  document.querySelectorAll('[data-close]').forEach(el => {
    el.addEventListener('click', () => closeOverlay(el.dataset.close));
  });
}

// ── Menu ──────────────────────────────────────────────────────────────────────
async function showMenu() {
  dragStart = null; dragEnd = null;
  closeAllOverlays();
  clearGameUrl();
  showScreen('screen-menu');
  updatePill();
}


// ── Global keyboard handler ───────────────────────────────────────────────────
function setupKeyboard() {
  document.addEventListener('keydown', e => {
    const tag = e.target.tagName;
    if (tag === 'INPUT' || tag === 'TEXTAREA') return;

    // Settings binding capture
    if (waitingForBinding) {
      if (e.code !== 'Escape') {
        keybinds[waitingForBinding] = e.code;
        saveSettings();
        updateKeyBtns();
      }
      waitingForBinding = null;
      document.querySelectorAll('.key-btn.waiting').forEach(b => b.classList.remove('waiting'));
      $('settings-capture-hint').classList.add('hidden');
      e.preventDefault();
      return;
    }

    // Close overlay with Escape
    if (e.code === 'Escape' && anyOverlayOpen()) {
      closeAllOverlays();
      e.preventDefault();
      return;
    }

    if (anyOverlayOpen()) return;

    // Game shortcuts
    const screen = document.querySelector('.screen.active')?.id;
    const k = e.code;

    if (screen === 'screen-play') {
      if (k === keybinds.pause)   { $('play-pause').click();   e.preventDefault(); }
      else if (k === keybinds.restart) { $('play-restart').click(); e.preventDefault(); }
      else if (k === keybinds.menu)    { $('play-back').click();    e.preventDefault(); }
    } else if (screen === 'screen-vs') {
      if (k === keybinds.pause)   { $('vs-pause').click();   e.preventDefault(); }
      else if (k === keybinds.restart) { $('vs-restart').click(); e.preventDefault(); }
      else if (k === keybinds.menu)    { $('vs-back').click();    e.preventDefault(); }
    } else if (screen === 'screen-watch') {
      if (k === keybinds.restart) { $('watch-restart').click(); e.preventDefault(); }
      else if (k === keybinds.menu)    { $('watch-back').click();    e.preventDefault(); }
    }
  });
}

// ── Entry point ───────────────────────────────────────────────────────────────
async function init() {
  loadSettings();
  applyTheme(darkMode);
  updateKeyBtns();

  showScreen('screen-loading');
  setupMenuInput();
  setupPlayInput();
  setupVsInput();
  setupWatchInput();
  setupSettingsOverlay();
  setupStatsOverlay();
  setupCustomOverlay();
  setupKeyboard();

  try {
    await initPyodide();
    const params   = new URLSearchParams(location.search);
    const urlMode  = params.get('mode');
    const urlSeed  = params.get('seed');
    const urlGrid  = params.get('grid') || 'random';
    const seed     = urlSeed !== null ? parseInt(urlSeed) : null;
    if (urlMode === 'single' || urlMode === 'vs') {
      await startPlay(urlGrid, { seed, isCustom: true });
    } else if (urlMode === 'demo') {
      await startWatch(urlGrid, seed);
    } else {
      await showMenu();
    }
  } catch (e) {
    $('loading-status').textContent = 'Failed to load: ' + e.message;
    console.error(e);
  }
}

init();
