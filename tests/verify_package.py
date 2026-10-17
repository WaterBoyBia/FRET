"""Run the frozen application with conda and Python paths removed."""

import argparse
import os
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", required=True, type=Path)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    environment = {key: value for key, value in os.environ.items()
                   if not key.upper().startswith(("CONDA", "PYTHON", "_CE_"))}
    windows = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    environment["PATH"] = os.pathsep.join([str(windows / "System32"), str(windows)])
    environment["MPLCONFIGDIR"] = str(output / "matplotlib-cache")
    environment["TEMP"] = str(output)
    environment["TMP"] = str(output)
    result_path = output / "smoke_result.txt"
    previous = result_path.stat().st_mtime_ns if result_path.exists() else 0
    subprocess.run([str(args.exe.resolve()), str(args.input.resolve()), "--smoke-test", str(output)],
                   env=environment, cwd=output, timeout=120, check=True)
    assert result_path.exists() and result_path.stat().st_mtime_ns != previous, "No new smoke result"
    result = result_path.read_text(encoding="utf-8")
    assert "PASS" in result and "Frozen: True" in result, result
    for suffix in ("png", "svg", "pdf"):
        assert (output / f"smoke_chart.{suffix}").stat().st_size > 1000, f"Missing {suffix} export"
    print("Packaged application passed with conda/Python removed from PATH.")
    print(result)


if __name__ == "__main__":
    main()
