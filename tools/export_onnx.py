"""
Export the trained MaskablePPO policy to ONNX for use in the web build.

Usage:
    uv run --extra cpu python tools/export_onnx.py
    uv run --extra cpu python tools/export_onnx.py --model fruitbox_ppo_final --out web_assets/fruitbox_policy.onnx

Output: web_assets/fruitbox_policy.onnx

The exported model takes two inputs:
    grid  : float32[batch, rows*cols]   -- grid values as float (-1 or 1-9)
    score : float32[batch, 1]           -- current score

And returns:
    logits : float32[batch, rows*cols*rows*cols]  -- raw action logits (pre-mask)

Apply the action mask and argmax in the caller:
    logits[~mask] = -inf
    action = argmax(logits)
"""

import argparse
import os
import sys

import numpy as np
import torch
import torch.nn as nn

# allow running from project root: uv run --extra cpu python tools/export_onnx.py
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from sb3_contrib import MaskablePPO
from sb3_contrib.common.wrappers import ActionMasker

from fruitbox.env import FruitBoxEnv


# ── wrapper ───────────────────────────────────────────────────────────────────

class _PolicyWrapper(nn.Module):
    """
    Accepts two flat float32 tensors instead of a SB3 obs dict.
    Runs only the policy head (not the value head).
    """
    def __init__(self, policy):
        super().__init__()
        self.features_extractor = policy.features_extractor
        self.mlp_extractor       = policy.mlp_extractor
        self.action_net          = policy.action_net

    def forward(self, grid: torch.Tensor, score: torch.Tensor) -> torch.Tensor:
        obs      = {"grid": grid, "score": score}
        features = self.features_extractor(obs)
        latent_pi, _ = self.mlp_extractor(features)
        return self.action_net(latent_pi)


# ── export ────────────────────────────────────────────────────────────────────

def export(model_path: str, output_path: str) -> None:
    print(f"Loading model from '{model_path}' ...")
    model = MaskablePPO.load(model_path, device="cpu")
    model.policy.eval()

    wrapper = _PolicyWrapper(model.policy)
    wrapper.eval()

    rows, cols = 10, 17
    n = rows * cols  # 170

    dummy_grid  = torch.zeros(1, n, dtype=torch.float32)
    dummy_score = torch.zeros(1, 1, dtype=torch.float32)

    # dry-run to catch shape errors before writing the file
    with torch.no_grad():
        test_out = wrapper(dummy_grid, dummy_score)
    print(f"Policy output shape: {tuple(test_out.shape)}  (expected [1, {n * n}])")

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    print(f"Exporting to '{output_path}' ...")
    torch.onnx.export(
        wrapper,
        (dummy_grid, dummy_score),
        output_path,
        input_names=["grid", "score"],
        output_names=["logits"],
        dynamic_axes={
            "grid":   {0: "batch"},
            "score":  {0: "batch"},
            "logits": {0: "batch"},
        },
        opset_version=17,
        dynamo=False,  # use TorchScript exporter — avoids onnxscript / emoji logger
    )

    size_mb = os.path.getsize(output_path) / 1_000_000
    print(f"Exported — {size_mb:.1f} MB")


# ── validate ──────────────────────────────────────────────────────────────────

def validate(model_path: str, output_path: str, n_games: int = 10) -> None:
    try:
        import onnxruntime as ort
    except ImportError:
        print("onnxruntime not installed — skipping validation (uv sync --group web)")
        return

    print(f"\nValidating against SB3 on {n_games} random board states ...")

    model = MaskablePPO.load(model_path, device="cpu")
    sess  = ort.InferenceSession(output_path, providers=["CPUExecutionProvider"])

    def mask_fn(env):
        return env.action_masks()

    env   = ActionMasker(FruitBoxEnv(), mask_fn)
    rows, cols = env.env.rows, env.env.cols
    n     = rows * cols
    match = 0

    for i in range(n_games):
        obs, _ = env.reset()
        done   = False
        steps  = 0

        while not done:
            masks = env.env.action_masks()

            # SB3 prediction
            sb3_action, _ = model.predict(obs, action_masks=masks, deterministic=True)

            # ONNX prediction
            grid_in  = obs["grid"].astype(np.float32).reshape(1, n)
            score_in = obs["score"].astype(np.float32).reshape(1, 1)
            logits   = sess.run(["logits"], {"grid": grid_in, "score": score_in})[0][0]
            logits[~masks] = -1e9
            onnx_action = int(np.argmax(logits))

            ok = int(sb3_action) == onnx_action
            match += ok
            steps += 1

            if not ok:
                print(f"  game {i} step {steps}: SB3={int(sb3_action)}  ONNX={onnx_action}  MISMATCH")

            obs, _, terminated, truncated, _ = env.step(int(sb3_action))
            done = terminated or truncated

        print(f"  game {i+1}: {steps} steps")

    total = match  # not meaningful across games, just track mismatches
    print("Validation complete — any MISMATCH lines above indicate export issues.")


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Export MaskablePPO policy to ONNX")
    parser.add_argument("--model", default="fruitbox_ppo_final",
                        help="Path to saved model (zip or directory)")
    parser.add_argument("--out",   default="web_assets/fruitbox_policy.onnx",
                        help="Output .onnx path")
    parser.add_argument("--no-validate", action="store_true",
                        help="Skip validation step")
    args = parser.parse_args()

    export(args.model, args.out)

    if not args.no_validate:
        validate(args.model, args.out)


if __name__ == "__main__":
    main()
