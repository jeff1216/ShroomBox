"""
Drop-in replacement for MaskablePPO.predict() using an exported ONNX policy.

Usage:
    from fruitbox.onnx_agent import OnnxAgent
    agent = OnnxAgent("web_assets/fruitbox_policy.onnx")
    action, _ = agent.predict(obs, action_masks=masks, deterministic=True)

The interface mirrors sb3_contrib.MaskablePPO so callers in vs.py / ai_watch.py
need no changes beyond swapping the constructor.
"""

import numpy as np

try:
    import onnxruntime as ort
except ImportError as exc:
    raise ImportError(
        "onnxruntime is required for OnnxAgent — run: uv sync --group web"
    ) from exc


class OnnxAgent:
    """Runs the exported ONNX policy; same predict() interface as MaskablePPO."""

    def __init__(self, model_path: str) -> None:
        self._sess = ort.InferenceSession(
            model_path, providers=["CPUExecutionProvider"]
        )
        # derive flat grid size from the session's declared input shape
        grid_shape = self._sess.get_inputs()[0].shape  # [batch, n]
        self._n = int(grid_shape[1])

    def predict(
        self,
        obs: dict,
        action_masks: "np.ndarray | None" = None,
        deterministic: bool = True,  # noqa: ARG002 — always greedy; kept for API compat
    ) -> "tuple[np.int64, None]":
        grid_in  = obs["grid"].astype(np.float32).reshape(1, self._n)
        score_in = obs["score"].astype(np.float32).reshape(1, 1)

        logits = self._sess.run(
            ["logits"], {"grid": grid_in, "score": score_in}
        )[0][0]  # shape: (n_actions,)

        if action_masks is not None:
            logits[~action_masks] = -1e9

        return np.int64(np.argmax(logits)), None
