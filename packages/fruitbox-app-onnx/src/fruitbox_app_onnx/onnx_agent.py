"""
Drop-in replacement for MaskablePPO.predict() using an exported ONNX policy.
"""

import numpy as np


class OnnxAgent:
    """Runs the exported ONNX policy; same predict() interface as MaskablePPO."""

    def __init__(self, model_path: str) -> None:
        try:
            import onnxruntime as ort
        except ImportError as exc:
            raise ImportError(
                "onnxruntime is required for OnnxAgent"
            ) from exc
        self._sess = ort.InferenceSession(
            model_path, providers=["CPUExecutionProvider"]
        )
        grid_shape = self._sess.get_inputs()[0].shape
        self._n = int(grid_shape[1])

    def predict(
        self,
        obs: dict,
        action_masks: "np.ndarray | None" = None,
        deterministic: bool = True,
    ) -> "tuple[np.int64, None]":
        grid_in  = obs["grid"].astype(np.float32).reshape(1, self._n)
        score_in = obs["score"].astype(np.float32).reshape(1, 1)

        logits = self._sess.run(
            ["logits"], {"grid": grid_in, "score": score_in}
        )[0][0]

        if action_masks is not None:
            logits[~action_masks] = -1e9

        return np.int64(np.argmax(logits)), None

    async def predict_async(
        self,
        obs: dict,
        action_masks: "np.ndarray | None" = None,
        deterministic: bool = True,
    ) -> "tuple[np.int64, None]":
        return self.predict(obs, action_masks=action_masks, deterministic=deterministic)
