'use strict';

// ── Constants ─────────────────────────────────────────────────────────────────
const ROWS = 10, COLS = 17, N = ROWS * COLS;
const CELL = 46, GAP = 2, STEP = CELL + GAP;       // single / watch
const VS_CELL = 36, VS_GAP = 2, VS_STEP = VS_CELL + VS_GAP; // vs mode
const TIME_LIMIT = 120;
const AI_INTERVAL_MS = 480;
const ONNX_URL = './fruitbox_policy.onnx';

// Dark-theme colours matching the desktop app
const C = {
  bg:          '#161614',
  cellBg:      '#262522',
  cellBorder:  '#3a3834',
  cleared:     '#1e1e1b',
  text:        '#dcdad4',
  textDim:     '#82807a',
  selFill:     'rgba(80,150,230,0.23)',
  selBorder:   '#5096e6',
  validFill:   'rgba(29,158,117,0.25)',
  validBorder: '#1d9e75',
  badFill:     'rgba(226,75,74,0.23)',
  badBorder:   '#c84646',
  aiSel:       'rgba(180,100,240,0.35)',
  aiBorder:    '#b064f0',
};

// ── State ─────────────────────────────────────────────────────────────────────
let pyodide = null, onnxSession = null, opfsMount = null;
let selectedGridType = 'random';

// per-mode game state
let playGrid = null, playScore = 0, playTimeRemaining = 0;
let playGameOver = false, playTimedOut = false;
let playGameSeed = null, playGameStart = 0;
let playPaused = false;

let vsHumanGrid = null, vsAiGrid = null;
let vsHumanScore = 0, vsAiScore = 0, vsTimeRemaining = 0;
let vsHumanOver = false, vsAiOver = false, vsGameOver = false;
let vsGameSeed = null, vsGameStart = 0, vsPaused = false;
let lastAiMoveTs = 0, aiHighlight = null; // {r1,c1,r2,c2,until}

let watchGrid = null, watchScore = 0, watchTimeRemaining = 0;
let watchOver = false, watchGameStart = 0;
let lastWatchAiTs = 0, watchHighlight = null;

// drag selection
let dragStart = null, dragEnd = null;

// animation
let animId = null, lastTs = null;

// ── DOM helpers ───────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);
const showScreen = id => {
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
  $(id).classList.add('active');
};
const setProgress = (pct, msg) => {
  $('progress-fill').style.width = pct + '%';
  $('loading-status').textContent = msg;
};
const fmt = secs => {
  const m = Math.floor(secs / 60), s = Math.floor(secs % 60);
  return `${m}:${String(s).padStart(2, '0')}`;
};
const showOver = (id, cls) => {
  const el = $(id);
  el.classList.add('show');
  const card = el.querySelector('.over-card');
  card.className = 'over-card ' + (cls || '');
};
const hideOver = id => $(id).classList.remove('show');

// ── Python helpers string ─────────────────────────────────────────────────────
const PYTHON_HELPERS = `
import sys
import numpy as np
from fruitbox_core.game import FruitBoxGame
from fruitbox_core.env import FruitBoxEnv
import fruitbox_core.stats as _stats

_play = None
_vs_human = None
_vs_env = None
_watch_env = None

# ── single player ─────────────────────────────────────────────────────────────
def play_init(grid_type, seed=None):
    global _play
    _play = FruitBoxGame(grid_type=grid_type)
    _play.reset(None if seed is None else int(seed))

def play_grid():    return _play.grid.flatten().tolist()
def play_tick(dt):  return bool(_play.tick(float(dt)))
def play_score():   return int(_play.score)
def play_time():    return float(_play.time_remaining)
def play_seed():    return int(_play.seed)
def play_elapsed(): return float(_play.elapsed)
def play_paused():  return bool(_play.paused)
def play_pause():   _play.pause()
def play_resume():  _play.resume()

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
    return {
        'grid':  obs['grid'].astype(np.float32).tolist(),
        'score': float(obs['score'][0]),
    }

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
    return {
        'grid':  obs['grid'].astype(np.float32).tolist(),
        'score': float(obs['score'][0]),
    }

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

def stats_summary():
    return dict(_stats.get_summary())
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
    // Patch stats path to OPFS location
    await pyodide.runPythonAsync(`
import fruitbox_core.stats as _s
_s._PATH = "/fruitbox/fruitbox_stats.db"
`);
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
  // /home/pyodide is already on sys.path in Pyodide
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

// ── py() helper ──────────────────────────────────────────────────────────────
// Call a Python function by name, returning a JS value (auto-converts PyProxy).
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
  const gridData   = new Float32Array(inputs.grid);
  const scoreData  = new Float32Array([inputs.score]);
  const gridTensor  = new ort.Tensor('float32', gridData,  [1, N]);
  const scoreTensor = new ort.Tensor('float32', scoreData, [1, 1]);

  const results = await onnxSession.run({ grid: gridTensor, score: scoreTensor });
  const logits  = results.logits.data; // Float32Array of length N*N

  // Build masked logit array — start all at -inf, unmask valid moves
  const masked = new Float32Array(N * N).fill(-1e9);
  for (const [r1, c1, r2, c2] of validMoves) {
    const a = (r1 * COLS + c1) * N + (r2 * COLS + c2);
    masked[a] = logits[a];
  }

  // Argmax
  let best = 0, bestVal = -Infinity;
  for (let i = 0; i < masked.length; i++) {
    if (masked[i] > bestVal) { bestVal = masked[i]; best = i; }
  }
  return best;
}

// ── Canvas rendering ──────────────────────────────────────────────────────────
function setupCanvas(canvas, cellSize, gap) {
  const step = cellSize + gap;
  const w = step * COLS - gap, h = step * ROWS - gap;
  canvas.width  = w;
  canvas.height = h;
  return { step, w, h };
}

function pixelToCell(canvas, px, py, cellSize, gap) {
  const step = cellSize + gap;
  const rect = canvas.getBoundingClientRect();
  const scaleX = canvas.width / rect.width;
  const scaleY = canvas.height / rect.height;
  const x = (px - rect.left) * scaleX;
  const y = (py - rect.top) * scaleY;
  const c = Math.floor(x / step), r = Math.floor(y / step);
  if (r >= 0 && r < ROWS && c >= 0 && c < COLS) return [r, c];
  return null;
}

function selBounds(a, b) {
  if (!a || !b) return null;
  return [Math.min(a[0],b[0]), Math.min(a[1],b[1]),
          Math.max(a[0],b[0]), Math.max(a[1],b[1])];
}

function drawBoard(canvas, grid, cellSize, gap, {
  drag    = null,  // [r1,c1,r2,c2] current drag selection
  validDrag = null, // true/false/null
  aiSel   = null,  // [r1,c1,r2,c2] AI's last move highlight
  paused  = false,
} = {}) {
  if (!grid) return;
  const ctx  = canvas.getContext('2d');
  const step = cellSize + gap;

  ctx.fillStyle = C.bg;
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  const fontSize = Math.floor(cellSize * 0.46);
  ctx.font = `600 ${fontSize}px system-ui, sans-serif`;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';

  for (let r = 0; r < ROWS; r++) {
    for (let c = 0; c < COLS; c++) {
      const v = grid[r * COLS + c];
      const x = c * step, y = r * step;

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

  // AI selection highlight
  if (aiSel) {
    const [r1,c1,r2,c2] = aiSel;
    const sx = c1 * step, sy = r1 * step;
    const sw = (c2 - c1) * step + cellSize, sh = (r2 - r1) * step + cellSize;
    ctx.fillStyle = C.aiSel;
    ctx.fillRect(sx, sy, sw, sh);
    ctx.strokeStyle = C.aiBorder;
    ctx.lineWidth = 2;
    ctx.strokeRect(sx + 1, sy + 1, sw - 2, sh - 2);
  }

  // Drag selection
  if (drag) {
    const [r1,c1,r2,c2] = drag;
    const sx = c1 * step, sy = r1 * step;
    const sw = (c2 - c1) * step + cellSize, sh = (r2 - r1) * step + cellSize;
    ctx.fillStyle   = validDrag === true  ? C.validFill
                    : validDrag === false ? C.badFill
                    : C.selFill;
    ctx.strokeStyle = validDrag === true  ? C.validBorder
                    : validDrag === false ? C.badBorder
                    : C.selBorder;
    ctx.fillRect(sx, sy, sw, sh);
    ctx.lineWidth = 2;
    ctx.strokeRect(sx + 1, sy + 1, sw - 2, sh - 2);
  }

  // Paused overlay
  if (paused) {
    ctx.fillStyle = 'rgba(0,0,0,0.45)';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = C.text;
    ctx.font = `700 ${cellSize}px system-ui, sans-serif`;
    ctx.fillText('PAUSED', canvas.width / 2, canvas.height / 2);
  }
}

// ── Timer bar helper ──────────────────────────────────────────────────────────
function updateTimerBar(barId, remaining) {
  const pct = Math.max(0, remaining / TIME_LIMIT * 100);
  const bar = $(barId);
  bar.style.width = pct + '%';
  bar.style.background =
    remaining > 30 ? 'var(--timer-ok)' :
    remaining > 10 ? 'var(--timer-warn)' : 'var(--timer-danger)';
}

// ── Single player ─────────────────────────────────────────────────────────────
function startPlay(gridType, seed) {
  py('play_init', gridType, seed ?? null);
  playGrid = py('play_grid');
  playScore = 0; playTimeRemaining = TIME_LIMIT;
  playGameOver = false; playTimedOut = false; playPaused = false;
  playGameSeed = py('play_seed');
  playGameStart = performance.now();
  dragStart = null; dragEnd = null;

  const canvas = $('canvas-play');
  setupCanvas(canvas, CELL, GAP);
  hideOver('play-over');
  $('play-score').textContent = '0';
  $('play-timer').textContent = fmt(TIME_LIMIT);
  updateTimerBar('play-timerbar', TIME_LIMIT);

  showScreen('screen-play');
  lastTs = null;
  if (animId) cancelAnimationFrame(animId);
  animId = requestAnimationFrame(playLoop);
}

function playLoop(ts) {
  animId = null;
  if (playGameOver) return;

  const dt = lastTs === null ? 0 : (ts - lastTs) / 1000;
  lastTs = ts;

  if (!playPaused) {
    const timedOut = py('play_tick', dt);
    playTimeRemaining = py('play_time');
    playScore = py('play_score');
    if (timedOut) { playTimedOut = true; endPlay('Time\'s up!'); return; }
  }

  playGrid = py('play_grid');

  const bounds = selBounds(dragStart, dragEnd);
  let isValid = null;
  if (bounds) isValid = py('play_validate', ...bounds);

  const canvas = $('canvas-play');
  drawBoard(canvas, playGrid, CELL, GAP, {
    drag: bounds, validDrag: isValid, paused: playPaused,
  });

  $('play-score').textContent = playScore;
  $('play-timer').textContent = fmt(playTimeRemaining);
  updateTimerBar('play-timerbar', playTimeRemaining);

  animId = requestAnimationFrame(playLoop);
}

function endPlay(reason) {
  playGameOver = true;
  if (animId) { cancelAnimationFrame(animId); animId = null; }

  $('play-over-reason').textContent = reason;
  $('play-over-score').textContent = playScore;
  showOver('play-over', '');

  try {
    py('stats_record', 'single_player', selectedGridType,
      playScore, playGameSeed, (performance.now() - playGameStart) / 1000);
    syncStats();
  } catch(e) { console.warn('stats_record failed', e); }
}

function setupPlayInput() {
  const canvas = $('canvas-play');
  canvas.addEventListener('mousedown', e => {
    if (playGameOver || playPaused) return;
    const cell = pixelToCell(canvas, e.clientX, e.clientY, CELL, GAP);
    if (cell) { dragStart = cell; dragEnd = cell; }
  });
  canvas.addEventListener('mousemove', e => {
    if (!dragStart || playGameOver || playPaused) return;
    const cell = pixelToCell(canvas, e.clientX, e.clientY, CELL, GAP);
    if (cell) dragEnd = cell;
  });
  canvas.addEventListener('mouseup', e => {
    if (!dragStart || playGameOver || playPaused) return;
    const bounds = selBounds(dragStart, dragEnd);
    if (bounds) {
      const [pts, noMoves] = py('play_apply', ...bounds);
      if (noMoves) { dragStart = null; dragEnd = null; endPlay('No more moves'); return; }
    }
    dragStart = null; dragEnd = null;
  });
  canvas.addEventListener('mouseleave', () => { dragStart = null; dragEnd = null; });

  $('play-pause').onclick = () => {
    if (playGameOver) return;
    if (playPaused) { py('play_resume'); playPaused = false; $('play-pause').textContent = '⏸'; lastTs = null; }
    else            { py('play_pause');  playPaused = true;  $('play-pause').textContent = '▶'; }
  };
  $('play-restart').onclick = () => { cancelAnimationFrame(animId); startPlay(selectedGridType); };
  $('play-back').onclick    = () => { cancelAnimationFrame(animId); showMenu(); };
  $('play-over-again').onclick = () => startPlay(selectedGridType);
  $('play-over-menu').onclick  = () => { showMenu(); };
}

// ── VS AI ─────────────────────────────────────────────────────────────────────
function startVs(gridType, seed) {
  py('vs_init', gridType, seed ?? null);
  vsHumanGrid = py('vs_human_grid');
  vsAiGrid    = py('vs_ai_grid');
  vsHumanScore = 0; vsAiScore = 0; vsTimeRemaining = TIME_LIMIT;
  vsHumanOver = false; vsAiOver = false; vsGameOver = false; vsPaused = false;
  vsGameSeed  = py('vs_seed');
  vsGameStart = performance.now();
  dragStart = null; dragEnd = null;
  lastAiMoveTs = performance.now() + 800; // brief delay before AI starts
  aiHighlight = null;

  const humanC = $('canvas-human');
  const aiC    = $('canvas-ai-board');
  setupCanvas(humanC, VS_CELL, VS_GAP);
  setupCanvas(aiC,    VS_CELL, VS_GAP);

  hideOver('vs-over');
  $('vs-human-score').textContent = '0';
  $('vs-ai-score').textContent = '0';
  $('vs-timer').textContent = fmt(TIME_LIMIT);
  updateTimerBar('vs-timerbar', TIME_LIMIT);

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

    // AI move
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

  const humanC = $('canvas-human');
  const aiC    = $('canvas-ai-board');
  drawBoard(humanC, vsHumanGrid, VS_CELL, VS_GAP, { drag: bounds, validDrag: isValid, paused: vsPaused });
  drawBoard(aiC,    vsAiGrid,    VS_CELL, VS_GAP, { aiSel: aiHighlight ? [aiHighlight.r1, aiHighlight.c1, aiHighlight.r2, aiHighlight.c2] : null });

  $('vs-human-score').textContent = vsHumanScore;
  $('vs-ai-score').textContent    = vsAiScore;
  $('vs-timer').textContent       = fmt(vsTimeRemaining);
  updateTimerBar('vs-timerbar', vsTimeRemaining);

  if ((vsHumanOver && vsAiOver) || vsTimeRemaining <= 0) {
    endVs(); return;
  }

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
    const move   = py('vs_ai_decode', action);
    const [, noMoves] = py('vs_ai_apply', ...move);
    aiHighlight = { r1: move[0], c1: move[1], r2: move[2], c2: move[3], until: performance.now() + 250 };
    if (noMoves) vsAiOver = true;
  } catch(e) { console.error('AI step error', e); }
}

function endVs() {
  vsGameOver = true;
  if (animId) { cancelAnimationFrame(animId); animId = null; }

  const h = vsHumanScore, a = vsAiScore;
  let reason, cls;
  if      (h > a) { reason = `You win!  ${h} – ${a}`; cls = 'win'; }
  else if (a > h) { reason = `AI wins!  ${h} – ${a}`; cls = 'lose'; }
  else            { reason = `Tie!  ${h} – ${a}`;      cls = 'tie'; }

  $('vs-over-reason').textContent  = reason;
  $('vs-over-human').textContent   = h;
  $('vs-over-ai').textContent      = a;
  showOver('vs-over', cls);

  try {
    py('stats_record', 'vs_ai', selectedGridType,
      h, vsGameSeed, (performance.now() - vsGameStart) / 1000, a);
    syncStats();
  } catch(e) { console.warn('stats_record failed', e); }
}

function setupVsInput() {
  const canvas = $('canvas-human');
  canvas.addEventListener('mousedown', e => {
    if (vsGameOver || vsHumanOver || vsPaused) return;
    const cell = pixelToCell(canvas, e.clientX, e.clientY, VS_CELL, VS_GAP);
    if (cell) { dragStart = cell; dragEnd = cell; }
  });
  canvas.addEventListener('mousemove', e => {
    if (!dragStart || vsGameOver || vsHumanOver || vsPaused) return;
    const cell = pixelToCell(canvas, e.clientX, e.clientY, VS_CELL, VS_GAP);
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

  $('vs-pause').onclick   = () => {
    if (vsGameOver) return;
    if (vsPaused) { py('vs_resume'); vsPaused = false; $('vs-pause').textContent = '⏸'; lastTs = null; }
    else          { py('vs_pause');  vsPaused = true;  $('vs-pause').textContent = '▶'; }
  };
  $('vs-restart').onclick  = () => { cancelAnimationFrame(animId); startVs(selectedGridType); };
  $('vs-back').onclick     = () => { cancelAnimationFrame(animId); showMenu(); };
  $('vs-over-again').onclick = () => startVs(selectedGridType);
  $('vs-over-menu').onclick  = () => showMenu();
}

// ── Watch AI ──────────────────────────────────────────────────────────────────
function startWatch(gridType, seed) {
  py('watch_init', gridType, seed ?? null);
  watchGrid = py('watch_grid');
  watchScore = 0; watchTimeRemaining = TIME_LIMIT; watchOver = false;
  watchGameStart = performance.now();
  lastWatchAiTs = performance.now() + 600;
  watchHighlight = null;

  const canvas = $('canvas-watch');
  setupCanvas(canvas, CELL, GAP);
  hideOver('watch-over');
  $('watch-score').textContent = '0';
  $('watch-timer').textContent = fmt(TIME_LIMIT);
  updateTimerBar('watch-timerbar', TIME_LIMIT);

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
  const canvas = $('canvas-watch');
  drawBoard(canvas, watchGrid, CELL, GAP, {
    aiSel: watchHighlight ? [watchHighlight.r1, watchHighlight.c1, watchHighlight.r2, watchHighlight.c2] : null,
  });

  $('watch-score').textContent = watchScore;
  $('watch-timer').textContent = fmt(watchTimeRemaining);
  updateTimerBar('watch-timerbar', watchTimeRemaining);

  if (timedOut) { endWatch('Time\'s up!'); return; }

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
    watchHighlight = { r1: move[0], c1: move[1], r2: move[2], c2: move[3], until: performance.now() + 300 };
    if (noMoves) { endWatch('No more moves'); }
  } catch(e) { console.error('Watch AI step error', e); }
}

function endWatch(reason) {
  watchOver = true;
  if (animId) { cancelAnimationFrame(animId); animId = null; }
  $('watch-over-score').textContent = watchScore;
  showOver('watch-over', '');
}

function setupWatchInput() {
  $('watch-restart').onclick    = () => { cancelAnimationFrame(animId); startWatch(selectedGridType); };
  $('watch-back').onclick       = () => { cancelAnimationFrame(animId); showMenu(); };
  $('watch-over-again').onclick = () => startWatch(selectedGridType);
  $('watch-over-menu').onclick  = () => showMenu();
}

// ── Menu ──────────────────────────────────────────────────────────────────────
async function showMenu() {
  dragStart = null; dragEnd = null;
  showScreen('screen-menu');
  await refreshStats();
}

async function refreshStats() {
  try {
    const s = py('stats_summary');
    if (!s) return;

    const totalGames = s.get ? s.get('total_games') : s.total_games;
    if (!totalGames) { $('stats-panel').innerHTML = '<div class="stats-loading">No games yet</div>'; return; }

    const get = k => (s.get ? s.get(k) : s[k]) ?? '—';
    const totalTime = Math.round(get('total_time'));
    const h = Math.floor(totalTime / 3600), m = Math.floor((totalTime % 3600) / 60);

    $('stats-panel').innerHTML = `
      <div class="stats-grid">
        <div class="stats-section">
          <div class="stats-section-title">Overall</div>
          <div class="stats-row"><span>Games played</span><span class="stats-val">${get('total_games')}</span></div>
          <div class="stats-row"><span>Time played</span><span class="stats-val">${h}h ${m}m</span></div>
        </div>
        <div class="stats-section">
          <div class="stats-section-title">vs AI</div>
          <div class="stats-row"><span>Wins</span><span class="stats-val">${get('vs_wins')}</span></div>
          <div class="stats-row"><span>Losses</span><span class="stats-val">${get('vs_losses')}</span></div>
          <div class="stats-row"><span>Ties</span><span class="stats-val">${get('vs_ties')}</span></div>
        </div>
        <div class="stats-section">
          <div class="stats-section-title">Best (Random)</div>
          <div class="stats-row"><span>Score</span><span class="stats-val">${get('random_best') ?? '—'}</span></div>
        </div>
        <div class="stats-section">
          <div class="stats-section-title">Best (Solvable)</div>
          <div class="stats-row"><span>Score</span><span class="stats-val">${get('solvable_best') ?? '—'}</span></div>
        </div>
      </div>`;
  } catch(e) {
    $('stats-panel').innerHTML = '<div class="stats-loading">Stats unavailable</div>';
  }
}

function setupMenuInput() {
  $('grid-toggle').addEventListener('click', e => {
    const btn = e.target.closest('.grid-btn');
    if (!btn) return;
    document.querySelectorAll('.grid-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    selectedGridType = btn.dataset.type;
  });
  $('btn-play').onclick  = () => startPlay(selectedGridType);
  $('btn-vs').onclick    = () => startVs(selectedGridType);
  $('btn-watch').onclick = () => startWatch(selectedGridType);
}

// ── Entry point ───────────────────────────────────────────────────────────────
async function init() {
  showScreen('screen-loading');
  setupMenuInput();
  setupPlayInput();
  setupVsInput();
  setupWatchInput();

  try {
    await initPyodide();
    await showMenu();
  } catch (e) {
    $('loading-status').textContent = 'Failed to load: ' + e.message;
    console.error(e);
  }
}

init();
