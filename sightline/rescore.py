"""Recompute outlook scores from the saved data, without fetching anything.

Use after changing weights or thresholds in config.py:

    python -m sightline.rescore
"""

from __future__ import annotations

import json

from . import config, outlook
from .build import OUT, log


def main() -> None:
    data = json.loads(OUT.read_text(encoding="utf-8"))
    data["weights"] = config.WEIGHTS
    for c in data["countries"]:
        c["outlook"] = outlook.score(c)
        o = c["outlook"]
        log(f"  {c['name']:<15} {o['label']:<12} {o['score']:+4d}  ({o['coverage']})")
    OUT.write_text(json.dumps(data, indent=1), encoding="utf-8")
    log(f"rescored {OUT}")


if __name__ == "__main__":
    main()
