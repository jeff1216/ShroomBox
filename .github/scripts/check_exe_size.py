"""Fail CI if a built executable exceeds the size budget."""
import os
import sys

LIMIT_MB = 700
paths = sys.argv[1:] or ["dist/fruitbox.exe", "dist/fruitbox-onnx.exe"]

failed = False
for path in paths:
    if not os.path.isfile(path):
        print(f"WARNING: missing {path}", file=sys.stderr)
        continue
    size_mb = os.path.getsize(path) / 1024 / 1024
    status = "OK" if size_mb <= LIMIT_MB else "FAIL"
    print(f"{status}: {path} = {size_mb:.1f} MB (limit {LIMIT_MB} MB)")
    if size_mb > LIMIT_MB:
        failed = True

if failed:
    sys.exit(1)
