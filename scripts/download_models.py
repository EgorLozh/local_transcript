#!/usr/bin/env python3
"""One-time download of pyannote diarization model for offline use."""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


MODEL_ID = "pyannote/speaker-diarization-community-1"
DEFAULT_OUTPUT = Path("models/pyannote-speaker-diarization-community-1")


def download_with_git_lfs(token: str, output: Path) -> None:
    if shutil.which("git") is None:
        raise RuntimeError("git is required. Install git and git-lfs.")

    subprocess.run(["git", "lfs", "install"], check=True)

    if output.exists():
        print(f"Removing existing directory: {output}")
        shutil.rmtree(output)

    output.parent.mkdir(parents=True, exist_ok=True)
    clone_url = f"https://user:{token}@huggingface.co/{MODEL_ID}"
    subprocess.run(
        ["git", "clone", clone_url, str(output)],
        check=True,
    )


def download_with_hub(token: str, output: Path) -> None:
    from huggingface_hub import snapshot_download

    snapshot_download(
        repo_id=MODEL_ID,
        local_dir=str(output),
        token=token,
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
        "--method",
        choices=["hub", "git"],
        default="hub",
        help="Download method (default: hub)",
    )
    args = parser.parse_args()

    token = os.environ.get("HF_TOKEN")
    if not token:
        print(
            "Set HF_TOKEN environment variable.\n"
            "1. Accept license: https://huggingface.co/pyannote/speaker-diarization-community-1\n"
            "2. Create token: https://huggingface.co/settings/tokens",
            file=sys.stderr,
        )
        return 1

    print(f"Downloading {MODEL_ID} -> {args.output}")
    if args.method == "git":
        download_with_git_lfs(token, args.output)
    else:
        try:
            download_with_hub(token, args.output)
        except ImportError:
            print("huggingface_hub not installed, falling back to git lfs")
            download_with_git_lfs(token, args.output)

    print("Done. Set DIARIZATION_MODEL_PATH in .env if you used a custom path.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
