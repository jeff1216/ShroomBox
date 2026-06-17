import os
import glob
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from tensorboard.backend.event_processing.event_accumulator import EventAccumulator

LOG_DIR     = "logs"
TB_DIR      = os.path.join(LOG_DIR, "tensorboard")
MONITOR_CSV = os.path.join(LOG_DIR, "monitor.monitor.csv")

METRICS = [
    ("train/policy_gradient_loss", "Policy loss"),
    ("train/value_loss",           "Value loss"),
    ("train/entropy_loss",         "Entropy loss"),
    ("rollout/ep_rew_mean",        "Mean episode reward"),
]


def load_tb_scalar(event_dir, tag):
    ea = EventAccumulator(event_dir, size_guidance={"scalars": 0})
    ea.Reload()
    if tag not in ea.Tags().get("scalars", []):
        return None, None
    events = ea.Scalars(tag)
    steps  = [e.step        for e in events]
    values = [e.value       for e in events]
    return steps, values


def load_monitor(path):
    df = pd.read_csv(path, comment="#", header=0)
    df.columns = ["reward", "ep_len", "time"]
    df = df.apply(pd.to_numeric, errors="coerce").dropna()
    df["episode"] = range(1, len(df) + 1)
    return df


def collect_runs(tb_dir):
    """Merge all MaskablePPO_* runs into one continuous series per tag."""
    run_dirs = sorted(glob.glob(os.path.join(tb_dir, "MaskablePPO_*")))
    merged   = {tag: ([], []) for tag, _ in METRICS}

    step_offset = 0
    for run_dir in run_dirs:
        ea = EventAccumulator(run_dir, size_guidance={"scalars": 0})
        ea.Reload()
        available = set(ea.Tags().get("scalars", []))
        run_max_step = 0

        for tag, _ in METRICS:
            if tag not in available:
                continue
            events = ea.Scalars(tag)
            steps  = [e.step + step_offset for e in events]
            values = [e.value              for e in events]
            merged[tag][0].extend(steps)
            merged[tag][1].extend(values)
            if steps:
                run_max_step = max(run_max_step, max(e.step for e in events))

        step_offset += run_max_step

    return merged


def main():
    data = collect_runs(TB_DIR)

    n_loss = sum(1 for tag, _ in METRICS if data[tag][0])
    has_monitor = os.path.exists(MONITOR_CSV)
    n_plots = n_loss + (1 if has_monitor else 0)

    if n_plots == 0:
        print("No data found in", TB_DIR)
        return

    fig, axes = plt.subplots(n_plots, 1, figsize=(12, 3.5 * n_plots), constrained_layout=True)
    if n_plots == 1:
        axes = [axes]

    fig.suptitle("Training Metrics", fontsize=14, fontweight="bold")

    ax_idx = 0
    for tag, label in METRICS:
        steps, values = data[tag]
        if not steps:
            continue
        ax = axes[ax_idx]
        ax.plot(steps, values, linewidth=1.2)
        ax.set_title(label)
        ax.set_xlabel("Timestep")
        ax.xaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{int(x):,}"))
        ax.grid(True, alpha=0.3)
        ax_idx += 1

    if has_monitor:
        df  = load_monitor(MONITOR_CSV)
        ax  = axes[ax_idx]
        ax.plot(df["episode"], df["reward"], alpha=0.4, linewidth=0.8, label="Episode reward")
        # rolling mean
        window = max(1, len(df) // 20)
        ax.plot(df["episode"], df["reward"].rolling(window, min_periods=1).mean(),
                linewidth=1.8, label=f"Rolling mean ({window} eps)")
        ax.set_title("Episode reward (monitor)")
        ax.set_xlabel("Episode")
        ax.legend()
        ax.grid(True, alpha=0.3)

    plt.savefig("training_metrics.png", dpi=150)
    print("Saved training_metrics.png")
    plt.show()


if __name__ == "__main__":
    main()
