import sqlite3
import uuid
import os
import sys
from dataclasses import dataclass


def _stats_db_path() -> str:
    if getattr(sys, "frozen", False):
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        data_dir = os.path.join(base, "FruitBox")
        os.makedirs(data_dir, exist_ok=True)
        return os.path.join(data_dir, "fruitbox_stats.db")
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "fruitbox_stats.db")


_PATH = _stats_db_path()


@dataclass(frozen=True, slots=True)
class GameInfo:
    gamemode:     str
    grid_type:    str
    self_score:   int
    seed:         int
    time_elapsed: float
    opp_score:    int | None = None


def _connect():
    conn = sqlite3.connect(_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS game_history (
            game_id      TEXT PRIMARY KEY,
            gamemode     TEXT,
            grid_type    TEXT,
            self_score   INTEGER,
            opp_score    INTEGER,
            time_elapsed REAL,
            seed         INTEGER
        )
    """)
    conn.commit()
    return conn


def record(info: GameInfo):
    game_id = str(uuid.uuid4())
    with _connect() as conn:
        conn.execute(
            "INSERT INTO game_history VALUES (?, ?, ?, ?, ?, ?, ?)",
            (game_id, info.gamemode, info.grid_type, info.self_score,
             info.opp_score, round(info.time_elapsed), info.seed),
        )
    return game_id


def get_summary():
    with _connect() as conn:
        totals = conn.execute("""
            SELECT COUNT(*) AS total_games, COALESCE(SUM(time_elapsed), 0) AS total_time
            FROM game_history
        """).fetchone()
        vs = conn.execute("""
            SELECT
                COALESCE(SUM(CASE WHEN self_score > opp_score THEN 1 ELSE 0 END), 0) AS wins,
                COALESCE(SUM(CASE WHEN self_score < opp_score THEN 1 ELSE 0 END), 0) AS losses,
                COALESCE(SUM(CASE WHEN self_score = opp_score THEN 1 ELSE 0 END), 0) AS ties
            FROM game_history WHERE gamemode = 'vs_ai'
        """).fetchone()
        random_best = conn.execute("""
            SELECT self_score, seed FROM game_history
            WHERE grid_type = 'random' AND gamemode IN ('single_player', 'vs_ai')
            ORDER BY self_score DESC LIMIT 1
        """).fetchone()
        solvable_best = conn.execute("""
            SELECT self_score, seed FROM game_history
            WHERE grid_type = 'solvable' AND gamemode IN ('single_player', 'vs_ai')
            ORDER BY self_score DESC LIMIT 1
        """).fetchone()
    return {
        "total_games":       totals["total_games"],
        "total_time":        int(totals["total_time"]),
        "vs_wins":           vs["wins"],
        "vs_losses":         vs["losses"],
        "vs_ties":           vs["ties"],
        "random_best":       random_best["self_score"] if random_best else None,
        "random_best_seed":  random_best["seed"]       if random_best else None,
        "solvable_best":     solvable_best["self_score"] if solvable_best else None,
        "solvable_best_seed":solvable_best["seed"]       if solvable_best else None,
    }


def get_vs_stats():
    with _connect() as conn:
        row = conn.execute("""
            SELECT
                SUM(CASE WHEN self_score > opp_score THEN 1 ELSE 0 END) AS wins,
                SUM(CASE WHEN self_score < opp_score THEN 1 ELSE 0 END) AS losses,
                SUM(CASE WHEN self_score = opp_score THEN 1 ELSE 0 END) AS ties
            FROM game_history
            WHERE gamemode = 'vs_ai'
        """).fetchone()
    return {"wins": row["wins"] or 0, "losses": row["losses"] or 0, "ties": row["ties"] or 0}


def get_history():
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM game_history ORDER BY rowid DESC").fetchall()
    return [dict(r) for r in rows]
