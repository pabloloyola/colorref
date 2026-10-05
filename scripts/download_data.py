#!/usr/bin/env python3
"""Restore ColorRef data from the pinned Hugging Face dataset snapshot."""

from __future__ import annotations

import argparse
from pathlib import Path

from huggingface_hub import snapshot_download

DEFAULT_REPO = "paablo111/colorref-data"
DEFAULT_REVISION = "9270f1bee4fe28ed79109bd09efc3bb5f2add925"

SMOKE_PATTERNS = [
    "eval_subsets/debug_400.parquet",
    "eval_subsets/debug_400_summary.md",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download the immutable ColorRef dataset snapshot."
    )
    parser.add_argument(
        "--profile",
        choices=("smoke", "full"),
        default="smoke",
        help="smoke downloads only debug_400; full restores all archived data.",
    )
    parser.add_argument("--repo-id", default=DEFAULT_REPO)
    parser.add_argument("--revision", default=DEFAULT_REVISION)
    parser.add_argument("--output-dir", type=Path, default=Path("data"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    allow_patterns = SMOKE_PATTERNS if args.profile == "smoke" else None
    print(
        f"Downloading {args.repo_id}@{args.revision} "
        f"({args.profile}) into {args.output_dir}/"
    )

    try:
        snapshot_download(
            repo_id=args.repo_id,
            repo_type="dataset",
            revision=args.revision,
            local_dir=args.output_dir,
            allow_patterns=allow_patterns,
        )
    except Exception as exc:
        raise SystemExit(
            "Data download failed. Confirm that you can access the private "
            "dataset and run 'hf auth login' (or set HF_TOKEN).\n"
            f"Original error: {exc}"
        ) from exc

    required = [args.output_dir / "eval_subsets" / "debug_400.parquet"]
    missing = [path for path in required if not path.is_file()]
    if missing:
        formatted = "\n".join(f"- {path}" for path in missing)
        raise SystemExit(f"Download completed but required files are missing:\n{formatted}")

    print("ColorRef data are ready.")


if __name__ == "__main__":
    main()
