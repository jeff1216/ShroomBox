"""
ONNX inference via onnxruntime-web JS library (pyodide bridge).
Used in WASM builds where the native onnxruntime C extension is unavailable.

Requires the host page to define:
    window._ort_tensor = (type, data, dims) => new ort.Tensor(type, data, dims);
(see index.html)
"""

import numpy as np


class JsOnnxAgent:
    """
    Drop-in for OnnxAgent using onnxruntime-web (JS) via pyodide bridge.
    Must be constructed via `await JsOnnxAgent.create(url)`.
    """

    def __init__(self, session, n_grid: int) -> None:
        self._session = session  # ort.InferenceSession JS proxy
        self._n = n_grid

    @classmethod
    async def create(cls, model_url: str, n_grid: int = 170) -> "JsOnnxAgent":
        """Async factory — fetches and loads the ONNX model via onnxruntime-web."""
        import js
        session = await js.ort.InferenceSession.create(model_url)
        return cls(session, n_grid)

    async def predict_async(
        self,
        obs: dict,
        action_masks: "np.ndarray | None" = None,
        deterministic: bool = True,
    ) -> "tuple[np.int64, None]":
        import js
        import pyodide.ffi as ffi

        grid_js  = ffi.to_js(obs["grid"].astype(np.float32))   # → JS Float32Array
        score_js = ffi.to_js(obs["score"].astype(np.float32))  # → JS Float32Array

        grid_tensor  = js._ort_tensor("float32", grid_js,  ffi.to_js([1, self._n]))
        score_tensor = js._ort_tensor("float32", score_js, ffi.to_js([1, 1]))

        feeds = ffi.to_js(
            {"grid": grid_tensor, "score": score_tensor},
            dict_converter=js.Object.fromEntries,
        )

        results = await self._session.run(feeds)
        logits = np.asarray(results.logits.data.to_py(), dtype=np.float32)

        if action_masks is not None:
            logits[~action_masks] = -1e9

        return np.int64(np.argmax(logits)), None

    def predict(self, obs, action_masks=None, deterministic=True):
        raise RuntimeError("JsOnnxAgent is async-only — use predict_async() in the web build")
