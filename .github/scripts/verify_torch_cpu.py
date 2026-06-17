"""Fail CI if a CUDA/GPU torch build is installed."""
import glob
import os
import sys

import torch

version = torch.__version__
if "+cpu" not in version and torch.version.cuda:
    print(f"ERROR: expected CPU torch, got {version} (cuda={torch.version.cuda})", file=sys.stderr)
    sys.exit(1)

torch_dir = os.path.dirname(torch.__file__)
cuda_libs = glob.glob(os.path.join(torch_dir, "lib", "libtorch_cuda*"))
cuda_libs += glob.glob(os.path.join(torch_dir, "lib", "*cudnn*"))
cuda_libs = [p for p in cuda_libs if os.path.isfile(p) and os.path.getsize(p) > 1024 * 1024]
if cuda_libs:
    print("ERROR: CUDA torch libraries found:", file=sys.stderr)
    for path in cuda_libs:
        print(f"  {path} ({os.path.getsize(path) / 1024 / 1024:.1f} MB)", file=sys.stderr)
    sys.exit(1)

libcpu = os.path.join(torch_dir, "lib", "libtorch_cpu.so")
if not os.path.isfile(libcpu):
    # Windows uses .dll; just verify no cuda
    print(f"OK: torch {version} (no CUDA libs)")

total = sum(
    os.path.getsize(os.path.join(root, name))
    for root, _, names in os.walk(torch_dir)
    for name in names
    if os.path.isfile(os.path.join(root, name))
)
print(f"OK: torch {version}, package size {total / 1024 / 1024:.0f} MB")
