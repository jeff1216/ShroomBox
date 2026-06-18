import numpy as np

try:
    import gymnasium as gym
    from gymnasium import spaces
    _GymBase = gym.Env
except ImportError:
    # WASM fallback: gymnasium not yet installed (micropip installs it at runtime)
    _GymBase = object

    class spaces:
        class Discrete:
            def __init__(self, n): self.n = n
        class Box:
            def __init__(self, **kw): pass
        class Dict:
            def __init__(self, d): pass

from .game import FruitBoxGame


class FruitBoxEnv(_GymBase):
    """
    Observation : Dict
        grid  : (rows*cols,) int8, values -1 (cleared) or 1-9
        score : (1,)         float32

    Action      : Discrete(rows * cols * rows * cols)
        Encodes (r1, c1, r2, c2) as a flat index.
        Call action_masks() to get a boolean mask of valid actions.

    Reward      : number of fruits cleared by the move (0 for invalid).

    Termination : no valid moves remain.
    Truncation  : time runs out (each step consumes dt_per_step seconds).
    """

    metadata = {"render_modes": []}

    def __init__(self, rows=10, cols=17, dt_per_step=1.0, grid_type="solvable"):
        super().__init__()
        self.rows = rows
        self.cols = cols
        self.dt_per_step = dt_per_step
        self.game = FruitBoxGame(rows, cols, grid_type=grid_type)

        n = rows * cols
        self.action_space = spaces.Discrete(n * n)

        self.observation_space = spaces.Dict({
            "grid":  spaces.Box(low=-1, high=9, shape=(n,), dtype=np.int8),
            "score": spaces.Box(low=0, high=np.inf, shape=(1,), dtype=np.float32),
        })

    # ── action encoding ───────────────────────────────────────────────

    def _encode(self, r1, c1, r2, c2):
        n = self.rows * self.cols
        return (r1 * self.cols + c1) * n + (r2 * self.cols + c2)

    def _decode(self, action):
        n = self.rows * self.cols
        r1c1, r2c2 = divmod(int(action), n)
        r1, c1 = divmod(r1c1, self.cols)
        r2, c2 = divmod(r2c2, self.cols)
        return r1, c1, r2, c2

    # ── helpers ───────────────────────────────────────────────────────

    def _obs(self):
        return {
            "grid":  self.game.grid.flatten().astype(np.int8),
            "score": np.array([self.game.score], dtype=np.float32),
        }

    def action_masks(self):
        """Boolean mask of length action_space.n; True = valid action."""
        mask = np.zeros(self.action_space.n, dtype=bool)
        for move in self.game.get_valid_moves():
            mask[self._encode(*move)] = True
        return mask

    # ── gym API ───────────────────────────────────────────────────────

    def reset(self, seed=None, options=None):  # noqa: ARG002
        if _GymBase is not object:
            super().reset(seed=seed)
        self.game.reset()
        return self._obs(), {}

    def step(self, action):
        r1, c1, r2, c2 = self._decode(action)
        points, no_moves = self.game.apply_move(r1, c1, r2, c2)
        timed_out = self.game.tick(self.dt_per_step)

        done = no_moves or timed_out
        step_reward = (1.0 / float(points)) if points > 0 else 0.0
        terminal_bonus = float(self.game.score) if done else 0.0
        return self._obs(), step_reward + terminal_bonus, no_moves, timed_out, {}
