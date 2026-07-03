#!/usr/bin/env python3
"""One-time download of pyannote diarization model for offline use."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

# Disable Xet before huggingface_hub is imported (avoids hash parse errors on some setups).
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")

# Compatible with whisperx 3.3.2 + pyannote.audio 3.3.x
# community-1 requires pyannote 4.x (whisperx 3.8+)
DEFAULT_MODEL_ID = "pyannote/speaker-diarization-3.1"
DEFAULT_OUTPUT = Path("models/pyannote-speaker-diarization-3.1")


def download_with_git_lfs(token: str, output: Path, model_id: str) -> None:
    if shutil.which("git") is None:
        raise RuntimeError("git is required. Install: sudo apt install git git-lfs")

    subprocess.run(["git", "lfs", "install"], check=True)

    if output.exists():
        print(f"Removing existing directory: {output}")
        shutil.rmtree(output)

    output.parent.mkdir(parents=True, exist_ok=True)
    clone_url = f"https://user:{token}@huggingface.co/{model_id}"
    subprocess.run(
        ["git", "clone", clone_url, str(output)],
        check=True,
    )


def download_with_hub(token: str, output: Path, model_id: str) -> None:
    from huggingface_hub import snapshot_download

    if output.exists():
        print(f"Removing incomplete directory: {output}")
        shutil.rmtree(output)

    snapshot_download(
        repo_id=model_id,
        local_dir=str(output),
        token=token,
    )


def verify_download(output: Path) -> None:
    config = output / "config.yaml"
    if not config.is_file():
        raise RuntimeError(
            f"Download looks incomplete: {config} not found. "
            "Remove the folder and try again with --method git"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Download pyannote diarization model")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output directory (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL_ID,
        help=f"HuggingFace model id (default: {DEFAULT_MODEL_ID})",
    )
    parser.add_argument(
        "--method",
        choices=["hub", "git", "auto"],
        default="auto",
        help="Download method (default: auto = hub, fallback to git)",
    )
    args = parser.parse_args()

    token = os.environ.get("HF_TOKEN")
    if not token:
        print(
            "Set HF_TOKEN environment variable.\n"
            "1. Accept licenses:\n"
            "   https://huggingface.co/pyannote/speaker-diarization-3.1\n"
            "   https://huggingface.co/pyannote/segmentation-3.0\n"
            "2. Create token: https://huggingface.co/settings/tokens\n"
            "\nExample:\n"
            '  export HF_TOKEN="hf_xxx"\n'
            "  python scripts/download_models.py",
            file=sys.stderr,
        )
        return 1

    print(f"Downloading {args.model} -> {args.output}")
    print("HF_HUB_DISABLE_XET=1 (legacy HTTP download)")

    methods: list[str]
    if args.method == "auto":
        methods = ["hub", "git"]
    else:
        methods = [args.method]

    last_error: Exception | None = None
    for method in methods:
        try:
            if method == "git":
                print("Using git lfs...")
                download_with_git_lfs(token, args.output, args.model)
            else:
                print("Using huggingface_hub...")
                download_with_hub(token, args.output, args.model)
            verify_download(args.output)
            print("Done. Set DIARIZATION_MODEL_PATH in .env if you used a custom path.")
            return 0
        except Exception as exc:
            last_error = exc
            print(f"{method} download failed: {exc}", file=sys.stderr)
            if args.output.exists():
                shutil.rmtree(args.output)
            if len(methods) > 1 and method != methods[-1]:
                print("Trying fallback method...")

    print(
        "\nAll download methods failed.\n"
        "Try manually:\n"
        f'  export HF_TOKEN="hf_xxx"\n'
        f"  git lfs install\n"
        f"  git clone https://user:$HF_TOKEN@huggingface.co/{DEFAULT_MODEL_ID} {DEFAULT_OUTPUT}",
        file=sys.stderr,
    )
    if last_error:
        raise last_error
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
