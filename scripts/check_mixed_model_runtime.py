#!/usr/bin/env python3
"""Probe optional mixed-effects runtimes without installing or mutating them."""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import sys
from pathlib import Path


def probe() -> dict[str, object]:
    python_packages = {
        "numpy": bool(importlib.util.find_spec("numpy")),
        "pandas": bool(importlib.util.find_spec("pandas")),
        "statsmodels": bool(importlib.util.find_spec("statsmodels")),
    }
    executables = {name: shutil.which(name) for name in ["Rscript", "matlab", "octave"]}
    available = []
    if python_packages["statsmodels"]:
        available.append("python_statsmodels")
    if executables["Rscript"]:
        available.append("Rscript")
    if executables["matlab"]:
        available.append("MATLAB")
    if executables["octave"]:
        available.append("Octave")
    return {
        "status": "runtime_available" if available else "blocked_mixed_model_runtime_unavailable",
        "python": sys.executable,
        "python_packages": python_packages,
        "executables": executables,
        "available_backends": available,
        "interpretation": "Availability only; fitting still requires a ready manifest, model review, convergence checks and pre-specified contrasts.",
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv[1:])
    result = probe()
    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
