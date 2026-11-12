import argparse
import json
import sys
from pathlib import Path

# Ensure backend/ is on sys.path so `app.*` imports resolve when invoked from repo root
BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from data.generator.engine import run_generation  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AUMVERITY Deterministic Synthetic Wealth Dataset Generator"
    )
    parser.add_argument(
        "--profile",
        choices=["demo", "large"],
        default="demo",
        help="Dataset scale profile (default: demo)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=10753,
        help="Deterministic NumPy random seed (default: 10753)",
    )
    args = parser.parse_args()

    summary = run_generation(profile_name=args.profile, seed=args.seed)
    print(
        json.dumps(
            {
                "run_id": str(summary.run_id),
                "profile": summary.profile,
                "seed": summary.seed,
                "baseline_date": summary.baseline_date.isoformat(),
                "duration_seconds": summary.duration_seconds,
                "row_counts": summary.row_counts,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
