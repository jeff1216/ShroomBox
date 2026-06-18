import sys
import time

ROWS = 10
COLS = 17
TIMEOUT = 45

_start    = time.time()
_cache    = set()
_moves    = []
_best     = {'score': 0, 'moves': [], 'grid': None}
_timed_out = False


def _hash(grid):
    h = 0
    for row in grid:
        for v in row:
            h = h * 33 + v + 1
    return h % (1 << 64)


def _print_solution(sol):
    parts = [f"({m[1]},{m[2]},{m[3]},{m[4]})" for m in sol['moves']]
    print(f"{sol['score']}: {' -> '.join(parts)}")


def _search(grid, score):
    global _best, _timed_out

    if _timed_out:
        return
    if time.time() - _start > TIMEOUT:
        _timed_out = True
        return

    h = _hash(grid)
    if h in _cache:
        return
    _cache.add(h)

    if score > _best['score']:
        _best = {'score': score, 'moves': list(_moves), 'grid': [r[:] for r in grid]}

    # column prefix sums: csum[r][c] = sum of grid[0..r-1][c]
    csum = [[0] * COLS for _ in range(ROWS + 1)]
    for r in range(ROWS):
        for c in range(COLS):
            csum[r + 1][c] = csum[r][c] + grid[r][c]

    INF = 256
    top4 = [(INF, 0, 0, 0, 0)] * 4

    for r0 in range(ROWS):
        for r1 in range(r0, ROWS):
            s  = 0
            c1 = -1
            for c0 in range(COLS):
                # extend right until sum >= 10
                while c1 < COLS - 1 and s < 10:
                    c1 += 1
                    s += csum[r1 + 1][c1] - csum[r0][c1]

                if s == 10:
                    cleared = sum(
                        grid[r][c] != 0
                        for r in range(r0, r1 + 1)
                        for c in range(c0, c1 + 1)
                    )
                    mv = (cleared, r0, c0, r1, c1)
                    # keep top 4 by fewest cells cleared (ascending)
                    if   cleared < top4[0][0]: top4 = [mv, top4[0], top4[1], top4[2]]
                    elif cleared < top4[1][0]: top4 = [top4[0], mv, top4[1], top4[2]]
                    elif cleared < top4[2][0]: top4 = [top4[0], top4[1], mv, top4[2]]
                    elif cleared < top4[3][0]: top4 = [top4[0], top4[1], top4[2], mv]

                # shrink left
                s -= csum[r1 + 1][c0] - csum[r0][c0]

    for m in top4:
        if m[0] == INF:
            break
        cleared, r0, c0, r1, c1 = m

        ngrid = [r[:] for r in grid]
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                ngrid[r][c] = 0

        _moves.append(m)
        _search(ngrid, score + cleared)
        _moves.pop()


def solve(grid):
    """Solve a 10×17 grid (values 1-9, 0 for cleared). Returns the best solution found."""
    global _cache, _moves, _best, _start, _timed_out
    _cache     = set()
    _moves     = []
    _best      = {'score': 0, 'moves': [], 'grid': None}
    _start     = time.time()
    _timed_out = False
    _search([list(row) for row in grid], 0)
    elapsed = time.time() - _start
    return _best, elapsed


def main():
    grid = []
    for line in sys.stdin:
        row = list(map(int, line.split()))
        if row:
            grid.append(row)
        if len(grid) == ROWS:
            break

    sol, elapsed = solve(grid)
    _print_solution(sol)
    print(f"Time elapsed: {elapsed:.3f}s")


if __name__ == "__main__":
    main()

