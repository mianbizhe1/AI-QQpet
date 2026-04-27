#!/usr/bin/env python3
"""
构建可随 Electron 分发的 Python sidecar。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
BUILD_DIR = ROOT / ".build" / "python-backend"
VENV_DIR = BUILD_DIR / "venv"
DIST_DIR = ROOT / ".build" / "electron-backend-dist"
SPEC_DIR = BUILD_DIR / "spec"
WORK_DIR = BUILD_DIR / "work"
ENTRY_FILE = ROOT / "src" / "backend_entry.py"
BUNDLED_ENV_ALIAS = BUILD_DIR / "env.bundle"


def pyinstaller_data_arg(source: Path, target: str) -> str:
    separator = ";" if os.name == "nt" else ":"
    return f"{source}{separator}{target}"


def venv_python() -> Path:
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def ensure_venv() -> None:
    if venv_python().exists():
        return

    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, "-m", "venv", str(VENV_DIR)], check=True)


def install_build_deps() -> None:
    python = str(venv_python())
    subprocess.run([python, "-m", "pip", "install", "--upgrade", "pip"], check=True)
    subprocess.run(
        [python, "-m", "pip", "install", "-r", str(ROOT / "requirements.txt"), "pyinstaller>=6.0"],
        check=True,
    )


def clean_dist() -> None:
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    SPEC_DIR.mkdir(parents=True, exist_ok=True)
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    if BUNDLED_ENV_ALIAS.exists():
        BUNDLED_ENV_ALIAS.unlink()


def build() -> None:
    python = str(venv_python())
    command = build_pyinstaller_command(python)
    subprocess.run(command, check=True)


def build_pyinstaller_command(python: str) -> list[str]:
    command = [
        python,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--name",
        "qqpet-ai-server",
        "--onedir",
        "--distpath",
        str(DIST_DIR),
        "--workpath",
        str(WORK_DIR),
        "--specpath",
        str(SPEC_DIR),
        "--paths",
        str(ROOT / "src"),
        "--add-data",
        pyinstaller_data_arg(ROOT / "src" / "ai_llm" / "config.yaml", "src/ai_llm"),
    ]
    if (ROOT / "config.yaml").exists():
        command.extend([
            "--add-data",
            pyinstaller_data_arg(ROOT / "config.yaml", "."),
        ])
    if (ROOT / ".env").exists():
        shutil.copy2(ROOT / ".env", BUNDLED_ENV_ALIAS)
        command.extend([
            "--add-data",
            pyinstaller_data_arg(ROOT / ".env", "."),
            "--add-data",
            pyinstaller_data_arg(BUNDLED_ENV_ALIAS, "."),
        ])
    command.append(str(ENTRY_FILE))
    return command


def main() -> None:
    ensure_venv()
    install_build_deps()
    clean_dist()
    build()
    print(f"[build_python_backend] backend ready: {DIST_DIR}")


if __name__ == "__main__":
    main()
