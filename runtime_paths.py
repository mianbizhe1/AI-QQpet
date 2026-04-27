"""
运行时路径工具。

这是给顶层入口和打包产物使用的独立版本，避免通过 `src` 包间接导入时
触发 `src/__init__.py`，造成循环导入。
"""

from __future__ import annotations

import os
import re
import shutil
import sys
from pathlib import Path
from typing import Iterable, List

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


APP_NAME = "qq-pet-macos"
BACKEND_DIRNAME = "ai-backend"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def bundled_root() -> Path:
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parent


def app_support_root() -> Path:
    override = os.environ.get("QQPET_APP_DATA_DIR", "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / "Library" / "Application Support" / APP_NAME / BACKEND_DIRNAME


def ensure_runtime_layout() -> Path:
    root = app_support_root()
    try:
        root.mkdir(parents=True, exist_ok=True)
        (root / "data").mkdir(parents=True, exist_ok=True)
        return root
    except PermissionError:
        fallback = Path.cwd() / ".runtime" / APP_NAME / BACKEND_DIRNAME
        fallback.mkdir(parents=True, exist_ok=True)
        (fallback / "data").mkdir(parents=True, exist_ok=True)
        return fallback


def data_dir() -> Path:
    return ensure_runtime_layout() / "data"


def memory_db_path() -> Path:
    return data_dir() / "memory.db"


def scheduler_db_path() -> Path:
    return data_dir() / "scheduler.db"


def life_album_dir() -> Path:
    return data_dir() / "life_album"


def bundled_llm_config_path() -> Path:
    candidates = [
        bundled_root() / "config.yaml",
        bundled_root() / "src" / "ai_llm" / "config.yaml",
        bundled_root() / "ai_llm" / "config.yaml",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def first_llm_config_candidate(candidates: Iterable[Path]) -> Path | None:
    for candidate in candidates:
        if not candidate.exists():
            continue
        if has_llm_section(candidate):
            return candidate
    return None


def has_llm_section(path: Path) -> bool:
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return False

    if yaml is not None:
        try:
            data = yaml.safe_load(content) or {}
            return isinstance(data, dict) and isinstance(data.get("llm"), dict)
        except Exception:
            pass

    return re.search(r"(^|\n)llm:\s*(\n|$)", content) is not None


def backfill_llm_config(target: Path, source_candidates: Iterable[Path]) -> None:
    if yaml is None:
        return

    try:
        target_data = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    except Exception:
        return

    target_llm = target_data.get("llm")
    if not isinstance(target_llm, dict):
        target_llm = {}
        target_data["llm"] = target_llm

    needs_api_key = not bool(target_llm.get("api_key"))
    needs_base_url = not bool(target_llm.get("base_url"))
    needs_model = not bool(target_llm.get("model"))

    if not (needs_api_key or needs_base_url or needs_model):
        return

    for candidate in source_candidates:
        if not candidate.exists() or candidate.resolve() == target.resolve():
            continue
        try:
            source_data = yaml.safe_load(candidate.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        source_llm = source_data.get("llm")
        if not isinstance(source_llm, dict):
            continue

        changed = False
        if needs_api_key and source_llm.get("api_key"):
            target_llm["api_key"] = source_llm.get("api_key")
            needs_api_key = False
            changed = True
        if needs_base_url and source_llm.get("base_url"):
            target_llm["base_url"] = source_llm.get("base_url")
            needs_base_url = False
            changed = True
        if needs_model and source_llm.get("model"):
            target_llm["model"] = source_llm.get("model")
            needs_model = False
            changed = True

        if changed:
            target.write_text(
                yaml.safe_dump(target_data, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )

        if not (needs_api_key or needs_base_url or needs_model):
            return


def llm_config_path() -> Path:
    root = ensure_runtime_layout()
    target = root / "config.yaml"
    source_candidates = [
        bundled_root() / "config.yaml",
        bundled_root() / "src" / "ai_llm" / "config.yaml",
        bundled_root() / "ai_llm" / "config.yaml",
        Path.cwd() / "config.yaml",
    ]

    if not target.exists():
        seed_source = first_llm_config_candidate(source_candidates)
        if seed_source:
            shutil.copy2(seed_source, target)
    else:
        backfill_llm_config(target, source_candidates)
    return target


def bundled_env_path() -> Path:
    candidates = [
        bundled_root() / ".env",
        bundled_root() / "env.bundle",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def runtime_env_path() -> Path:
    root = ensure_runtime_layout()
    target = root / ".env"
    if not target.exists():
        for candidate in [bundled_env_path(), Path.cwd() / ".env", Path.cwd() / "env.bundle"]:
            if candidate.exists():
                shutil.copy2(candidate, target)
                break
    return target


def env_candidates() -> List[Path]:
    root = ensure_runtime_layout()
    runtime_env_path()
    candidates = [
        root / ".env",
        root / "env.bundle",
        bundled_root() / ".env",
        bundled_root() / "env.bundle",
        Path.cwd() / ".env",
        Path.cwd() / "env.bundle",
    ]

    seen = set()
    unique: List[Path] = []
    for candidate in candidates:
        candidate = candidate.resolve() if candidate.exists() else candidate
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique


def existing_paths(paths: Iterable[Path]) -> List[Path]:
    return [path for path in paths if path.exists()]
