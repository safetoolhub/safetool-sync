# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Build SafeTool Sync using PyInstaller with platform-specific packaging.

Usage:
    python dev-tools/build.py              # Build for current platform
    python dev-tools/build.py --clean      # Clean build
    python dev-tools/build.py --debug      # Debug mode
"""
from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BUILD_DIR = PROJECT_ROOT / "build"
DIST_DIR = PROJECT_ROOT / "dist"


def clean() -> None:
    for d in [BUILD_DIR / "tmp", DIST_DIR]:
        if d.exists():
            shutil.rmtree(d)
            print(f"  Cleaned: {d}")


def build_pyinstaller(debug: bool = False) -> None:
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    DIST_DIR.mkdir(parents=True, exist_ok=True)

    sep = os.pathsep

    icon_file = PROJECT_ROOT / "assets" / ("icon.ico" if platform.system() == "Windows" else "icon.png")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "safetool-sync",
        "--noconfirm",
        "--windowed",
        "--icon", str(icon_file),
        "--add-data", f"{PROJECT_ROOT / 'i18n'}{sep}i18n",
        "--add-data", f"{PROJECT_ROOT / 'assets'}{sep}assets",
        "--distpath", str(DIST_DIR),
        "--workpath", str(BUILD_DIR / "tmp"),
    ]

    if debug:
        cmd.append("--debug=all")
        cmd.append("--log-level=DEBUG")
    else:
        cmd.append("--log-level=WARN")

    hidden_imports = [
        "PyQt6",
        "PyQt6.QtCore",
        "PyQt6.QtGui",
        "PyQt6.QtWidgets",
        "qtawesome",
        "psutil",
        "send2trash",
    ]
    for imp in hidden_imports:
        cmd.extend(["--hidden-import", imp])

    cmd.append(str(PROJECT_ROOT / "app.py"))

    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    if result.returncode != 0:
        print(f"PyInstaller failed with return code {result.returncode}")
        sys.exit(result.returncode)

    print(f"\nBuild complete! Output in {DIST_DIR}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build SafeTool Sync")
    parser.add_argument("--clean", action="store_true", help="Clean build artifacts before building")
    parser.add_argument("--debug", action="store_true", help="Build in debug mode")
    args = parser.parse_args()

    print("=== SafeTool Sync Build ===\n")
    print(f"Platform: {platform.system()} {platform.release()}")
    print(f"Python:   {sys.version}")
    print(f"Project:  {PROJECT_ROOT}\n")

    if args.clean:
        print("Cleaning...")
        clean()

    build_pyinstaller(debug=args.debug)