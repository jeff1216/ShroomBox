import os
import shutil
import sys
import time
import urllib.error
import urllib.request

from huggingface_hub import hf_hub_download
from huggingface_hub.utils import HfHubHTTPError


def is_onnx(path: str) -> bool:
    with open(path, "rb") as handle:
        return handle.read(4) == b"\x08\x00" or handle.read(0) == b""


def validate_onnx(path: str) -> None:
    with open(path, "rb") as handle:
        header = handle.read(8)
    if len(header) < 4:
        raise ValueError(f"{path} is too small to be an ONNX model")


def download_direct(url: str, dest: str) -> None:
    print(f"Trying direct download: {url}")
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "fruitbox-ci/1.0"},
    )
    with urllib.request.urlopen(request, timeout=300) as response:
        data = response.read()
    if len(data) < 1024:
        raise ValueError("response is too small to be an ONNX model")
    with open(dest, "wb") as handle:
        handle.write(data)


def download_from_hf(repo: str, revision: str, filename: str, token: str | None) -> str:
    print(f"Downloading {filename} from Hugging Face ({repo}@{revision})")
    last_error: Exception | None = None
    for attempt in range(5):
        try:
            return hf_hub_download(
                repo_id=repo,
                filename=filename,
                revision=revision,
                token=token,
            )
        except HfHubHTTPError as exc:
            last_error = exc
            status = exc.response.status_code if exc.response is not None else None
            if status == 429 and attempt < 4:
                wait = 15 * (2**attempt)
                print(f"Hugging Face rate limited (429), retrying in {wait}s...")
                time.sleep(wait)
                continue
            raise
    raise last_error  # type: ignore[misc]


def fallback_sources(filename: str) -> list[str]:
    sources: list[str] = []

    mirror = os.environ.get("FRUITBOX_MODEL_MIRROR_URL")
    if mirror:
        sources.append(mirror)

    gh_repo = os.environ.get("GITHUB_REPOSITORY")
    if gh_repo:
        sources.append(
            f"https://github.com/{gh_repo}/releases/latest/download/{filename}"
        )

    hf_repo = os.environ.get("HF_MODEL_REPO")
    hf_revision = os.environ.get("HF_MODEL_REVISION")
    if hf_repo and hf_revision:
        sources.append(
            f"https://huggingface.co/{hf_repo}/resolve/{hf_revision}/{filename}"
        )

    return sources


def main() -> None:
    repo = os.environ["HF_MODEL_REPO"]
    revision = os.environ["HF_MODEL_REVISION"]
    filename = os.environ.get("HF_ONNX_FILE", "fruitbox_policy.onnx")
    token = os.environ.get("HF_TOKEN") or None
    dest = os.path.join(os.getcwd(), filename)

    if os.path.isfile(dest) and os.path.getsize(dest) > 1024:
        print(f"Using existing {filename} ({os.path.getsize(dest)} bytes)")
        return

    errors: list[str] = []

    try:
        cached_path = download_from_hf(repo, revision, filename, token)
        shutil.copy2(cached_path, dest)
        validate_onnx(dest)
        print(f"Downloaded {filename} from Hugging Face ({os.path.getsize(dest)} bytes)")
        return
    except Exception as exc:
        errors.append(f"Hugging Face: {exc}")

    for url in fallback_sources(filename):
        try:
            download_direct(url, dest)
            validate_onnx(dest)
            print(f"Downloaded {filename} from fallback ({os.path.getsize(dest)} bytes)")
            return
        except (urllib.error.URLError, urllib.error.HTTPError, ValueError) as exc:
            errors.append(f"{url}: {exc}")

    print("All ONNX download sources failed:", file=sys.stderr)
    for error in errors:
        print(f"  - {error}", file=sys.stderr)
    raise SystemExit(1)


if __name__ == "__main__":
    main()
