"""
Build the Fruit Box HTML5 web app.

Usage:
    uv run python tools/build_web.py          # build to dist/web/
    uv run python tools/build_web.py --serve  # build + local preview at localhost:8000
"""
import argparse
import os
import shutil

ROOT     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB_SRC  = os.path.join(ROOT, "web")
OUT_DIR  = os.path.join(ROOT, "dist", "web")
ONNX_SRC = os.path.join(ROOT, "web_assets", "fruitbox_policy.onnx")
CORE_SRC   = os.path.join(ROOT, "packages", "fruitbox-core", "src", "fruitbox_core")
ASSETS_SRC = os.path.join(ROOT, "packages", "fruitbox-pygame", "src", "fruitbox_pygame", "assets")

HF_REPO      = "Fungster/fruitbox-ppo"
HF_ONNX_FILE = "fruitbox_policy.onnx"


def _ensure_onnx():
    if os.path.isfile(ONNX_SRC):
        return
    print(f"ONNX model not found at {ONNX_SRC}, downloading from Hugging Face…")
    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        raise SystemExit("huggingface_hub is required: uv pip install huggingface_hub")
    try:
        cached = hf_hub_download(HF_REPO, HF_ONNX_FILE,
                                 token=os.environ.get("HF_TOKEN") or None)
    except Exception as exc:
        raise SystemExit(f"Failed to download ONNX model: {exc}")
    os.makedirs(os.path.dirname(ONNX_SRC), exist_ok=True)
    shutil.copy2(cached, ONNX_SRC)
    print(f"Downloaded to {ONNX_SRC} ({os.path.getsize(ONNX_SRC):,} bytes)")


def build():
    _ensure_onnx()

    if os.path.isdir(OUT_DIR):
        shutil.rmtree(OUT_DIR)
    os.makedirs(OUT_DIR)

    # Copy static web assets
    for f in ("index.html", "style.css", "app.js", "coi-serviceworker.js", "favicon.svg"):
        shutil.copy2(os.path.join(WEB_SRC, f), os.path.join(OUT_DIR, f))
        print(f"  Copied {f}")

    # Copy fruitbox_core Python source (loaded by Pyodide at runtime)
    core_dest = os.path.join(OUT_DIR, "fruitbox_core")
    shutil.copytree(CORE_SRC, core_dest,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    print(f"  Copied fruitbox_core/ ({len(os.listdir(core_dest))} files)")

    # Copy icon assets
    assets_dest = os.path.join(OUT_DIR, "assets")
    os.makedirs(assets_dest, exist_ok=True)
    n_icons = 0
    for fname in os.listdir(ASSETS_SRC):
        if fname.endswith('.png'):
            shutil.copy2(os.path.join(ASSETS_SRC, fname), os.path.join(assets_dest, fname))
            n_icons += 1
    print(f"  Copied assets/ ({n_icons} icons)")

    # Copy ONNX model
    shutil.copy2(ONNX_SRC, os.path.join(OUT_DIR, "fruitbox_policy.onnx"))
    print(f"  Copied fruitbox_policy.onnx ({os.path.getsize(ONNX_SRC):,} bytes)")

    print(f"\nBuild complete: {OUT_DIR}")


def serve():
    import http.server
    import socketserver

    os.chdir(OUT_DIR)
    PORT = 8000
    print(f"Serving at http://localhost:{PORT}/  (Ctrl+C to stop)")
    with socketserver.TCPServer(("", PORT), http.server.SimpleHTTPRequestHandler) as httpd:
        httpd.serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--serve", action="store_true")
    args = parser.parse_args()
    build()
    if args.serve:
        serve()
