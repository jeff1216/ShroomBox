import os

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
ONNX_PATH = os.path.join(_PROJECT_ROOT, "web_assets", "fruitbox_policy.onnx")
ONNX_URL  = "fruitbox_policy.onnx"  # relative URL when served by pygbag
GRID_N    = 170                      # standard 10×17 grid flat size


def is_wasm() -> bool:
    """True when running inside pyodide (pygbag WASM build)."""
    try:
        import js  # only available in pyodide  # noqa: F401
        return True
    except ImportError:
        return False
