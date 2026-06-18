import random
import numpy as np
from .grid import FruitBoxGrid


class FruitBoxGame:
    def __init__(self, rows=10, columns=17, time_limit=120, grid_type="random"):
        self.rows = rows
        self.columns = columns
        self.time_limit = time_limit
        self.grid_type = grid_type
        self.score = 0
        self.elapsed = 0.0
        self.paused = False
        self._grid_gen = FruitBoxGrid(rows, columns)
        self.grid = None
        self.seed = None

    _EXAMPLE_GRIDS = [
        #116
        [
            [9, 2, 2, 7, 6, 6, 1, 7, 1, 9, 7, 6, 9, 3, 8, 8, 3],
            [2, 2, 4, 8, 6, 9, 8, 4, 8, 3, 8, 1, 1, 2, 7, 4, 9],
            [8, 5, 1, 8, 9, 5, 5, 1, 7, 7, 5, 1, 3, 4, 6, 5, 1],
            [5, 2, 9, 2, 2, 1, 7, 5, 4, 5, 9, 5, 6, 4, 2, 9, 7],
            [4, 9, 6, 3, 6, 2, 3, 9, 2, 1, 2, 8, 8, 7, 9, 4, 7],
            [1, 9, 7, 2, 2, 2, 6, 2, 1, 2, 5, 6, 2, 5, 6, 7, 8],
            [8, 8, 4, 4, 9, 5, 7, 2, 3, 8, 2, 4, 8, 1, 4, 7, 3],
            [9, 4, 7, 2, 3, 7, 2, 8, 4, 6, 9, 8, 3, 8, 5, 2, 9],
            [4, 8, 1, 3, 9, 1, 6, 6, 6, 7, 2, 1, 4, 5, 2, 6, 2],
            [3, 7, 3, 8, 1, 2, 1, 8, 1, 8, 3, 3, 2, 3, 2, 7, 4],
        ],
        #104
        [
            [7, 8, 3, 8, 4, 4, 3, 1, 4, 5, 3, 2, 7, 7, 4, 6, 7],
            [6, 4, 3, 3, 3, 7, 1, 5, 1, 9, 2, 3, 4, 5, 5, 4, 6],
            [9, 7, 5, 5, 4, 2, 2, 9, 1, 9, 1, 1, 1, 7, 2, 2, 4],
            [3, 3, 7, 5, 5, 8, 9, 3, 6, 8, 5, 3, 5, 3, 2, 8, 7],
            [7, 3, 5, 8, 7, 8, 6, 3, 5, 6, 8, 9, 9, 9, 8, 5, 3],
            [5, 8, 3, 9, 9, 7, 6, 7, 3, 6, 9, 1, 6, 8, 3, 2, 5],
            [4, 9, 5, 7, 7, 5, 7, 8, 4, 4, 4, 2, 9, 8, 7, 3, 5],
            [8, 2, 1, 7, 9, 1, 7, 9, 6, 5, 4, 1, 3, 7, 6, 9, 6],
            [2, 3, 5, 6, 5, 6, 3, 9, 6, 6, 3, 6, 9, 7, 8, 8, 1],
            [1, 8, 5, 2, 2, 3, 1, 9, 3, 3, 3, 3, 7, 8, 7, 4, 8],
        ],
        #113
        [
            [5, 4, 3, 6, 7, 2, 3, 5, 1, 2, 8, 6, 2, 3, 8, 1, 7],
            [3, 8, 7, 5, 4, 6, 6, 1, 6, 5, 7, 5, 4, 3, 8, 8, 1],
            [7, 9, 9, 3, 1, 7, 1, 8, 9, 1, 8, 4, 9, 8, 7, 1, 7],
            [5, 4, 6, 3, 1, 3, 1, 5, 4, 7, 4, 1, 5, 8, 1, 1, 5],
            [3, 3, 4, 3, 8, 7, 6, 5, 8, 6, 3, 2, 8, 4, 6, 6, 6],
            [7, 2, 2, 8, 9, 9, 7, 7, 7, 7, 3, 9, 1, 2, 7, 2, 4],
            [4, 1, 1, 5, 7, 7, 9, 2, 3, 6, 9, 2, 7, 5, 7, 7, 1],
            [9, 6, 7, 1, 7, 9, 8, 7, 3, 2, 8, 9, 8, 6, 1, 6, 8],
            [1, 3, 9, 6, 4, 5, 5, 3, 4, 9, 4, 1, 9, 2, 6, 9, 1],
            [6, 9, 6, 3, 1, 5, 8, 2, 3, 5, 4, 2, 6, 4, 5, 3, 5],
        ],
    ]

    def reset(self, seed=None):
        self.seed = seed if seed is not None else random.randint(0, 2**31 - 1)
        self._grid_gen.rng = np.random.default_rng(self.seed)
        self.grid = self._grid_gen.generate(self.grid_type)
        self.score = 0
        self.elapsed = 0.0
        return self.grid.copy()

    def tick(self, dt):
        if not self.paused:
            self.elapsed += dt
        return self.elapsed >= self.time_limit

    def pause(self):
        self.paused = True

    def resume(self):
        self.paused = False

    def toggle_pause(self):
        self.paused = not self.paused

    @property
    def time_remaining(self):
        return max(0.0, self.time_limit - self.elapsed)

    def validate_move(self, r1, c1, r2, c2):
        total = 0
        for i in range(r1, r2 + 1):
            for j in range(c1, c2 + 1):
                if self.grid[i][j] == -1:
                    continue
                total += self.grid[i][j]
                if total > 10:
                    return False
        return total == 10

    def apply_move(self, r1, c1, r2, c2):
        if not self.validate_move(r1, c1, r2, c2):
            return 0, False

        points = 0
        for i in range(r1, r2 + 1):
            for j in range(c1, c2 + 1):
                if self.grid[i][j] != -1:
                    self.grid[i][j] = -1
                    points += 1

        self.score += points
        done = not self.has_valid_moves()
        return points, done

    def has_valid_moves(self):
        for r1 in range(self.rows):
            for c1 in range(self.columns):
                for r2 in range(r1, self.rows):
                    for c2 in range(c1, self.columns):
                        if self.validate_move(r1, c1, r2, c2):
                            return True
        return False

    def get_valid_moves(self):
        moves = []
        for r1 in range(self.rows):
            for c1 in range(self.columns):
                for r2 in range(r1, self.rows):
                    for c2 in range(c1, self.columns):
                        if self.validate_move(r1, c1, r2, c2):
                            moves.append((r1, c1, r2, c2))
        return moves