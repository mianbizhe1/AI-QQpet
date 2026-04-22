"""
生活相册存储与聚合
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class LifeAlbumRecord:
    record_id: str
    timestamp: str
    day: str
    week: str
    month: str
    screenshot_path: str
    screenshot_filename: str
    vision_summary: str
    llm_response: str
    event: str
    user_message: str
    frontmost_app: str
    frontmost_window: str
    tool_calls: List[str]
    pet_name: str
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "timestamp": self.timestamp,
            "day": self.day,
            "week": self.week,
            "month": self.month,
            "screenshot_path": self.screenshot_path,
            "screenshot_filename": self.screenshot_filename,
            "vision_summary": self.vision_summary,
            "llm_response": self.llm_response,
            "event": self.event,
            "user_message": self.user_message,
            "frontmost_app": self.frontmost_app,
            "frontmost_window": self.frontmost_window,
            "tool_calls": self.tool_calls,
            "pet_name": self.pet_name,
            "metadata": self.metadata,
        }


class LifeAlbumStore:
    def __init__(self, root_dir: str | Path):
        self.root_dir = Path(root_dir)
        self.records_dir = self.root_dir / "records"
        self.images_dir = self.root_dir / "images"
        self.records_dir.mkdir(parents=True, exist_ok=True)
        self.images_dir.mkdir(parents=True, exist_ok=True)

    def record_capture(
        self,
        *,
        screenshot_path: str,
        vision_summary: Optional[str],
        llm_response: Optional[str],
        event: str = "chat",
        user_message: str = "",
        frontmost_app: str = "",
        frontmost_window: str = "",
        tool_calls: Optional[List[str]] = None,
        pet_name: str = "小Q",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        now = datetime.now()
        day_key = now.strftime("%Y-%m-%d")
        week_key = f"{now.isocalendar().year}-W{now.isocalendar().week:02d}"
        month_key = now.strftime("%Y-%m")
        record_id = now.strftime("%Y%m%d_%H%M%S_%f")

        day_dir = self.records_dir / month_key / week_key
        day_dir.mkdir(parents=True, exist_ok=True)
        day_file = day_dir / f"{day_key}.jsonl"

        copied_image_path = self._copy_screenshot(
            source_path=screenshot_path,
            month_key=month_key,
            week_key=week_key,
            day_key=day_key,
            record_id=record_id,
        )

        record = LifeAlbumRecord(
            record_id=record_id,
            timestamp=now.isoformat(),
            day=day_key,
            week=week_key,
            month=month_key,
            screenshot_path=str(copied_image_path) if copied_image_path else str(screenshot_path or ""),
            screenshot_filename=Path(screenshot_path or "").name,
            vision_summary=(vision_summary or "").strip(),
            llm_response=(llm_response or "").strip(),
            event=event,
            user_message=(user_message or "").strip(),
            frontmost_app=(frontmost_app or "").strip(),
            frontmost_window=(frontmost_window or "").strip(),
            tool_calls=tool_calls or [],
            pet_name=pet_name or "小Q",
            metadata=metadata or {},
        )

        with day_file.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")

        return {
            "record": record.to_dict(),
            "storage": {
                "day_file": str(day_file),
                "day": day_key,
                "week": week_key,
                "month": month_key,
            },
        }

    def get_records(self, granularity: str, period: Optional[str] = None, limit: int = 50) -> Dict[str, Any]:
        granularity = (granularity or "day").lower()
        records = self._read_all_records()
        records.sort(key=lambda item: item.get("timestamp", ""), reverse=True)

        if granularity == "capture":
            if period:
                records = [item for item in records if item.get("record_id") == period]
            else:
                records = records[:1]
        elif granularity == "day":
            target = period or datetime.now().strftime("%Y-%m-%d")
            records = [item for item in records if item.get("day") == target]
        elif granularity == "week":
            target = period or self._current_week_key()
            records = [item for item in records if item.get("week") == target]
        elif granularity == "month":
            target = period or datetime.now().strftime("%Y-%m")
            records = [item for item in records if item.get("month") == target]
        else:
            raise ValueError(f"不支持的 granularity: {granularity}")

        if granularity != "capture":
            records = records[:limit]

        summary = self._build_summary(granularity, period, records)
        album_path = str(self._album_output_path(granularity, period, records))
        return {
            "granularity": granularity,
            "period": period or summary.get("period", ""),
            "count": len(records),
            "records": records,
            "summary": summary,
            "album_output_path": album_path,
        }

    def _read_all_records(self) -> List[Dict[str, Any]]:
        records: List[Dict[str, Any]] = []
        for path in sorted(self.records_dir.rglob("*.jsonl")):
            try:
                with path.open("r", encoding="utf-8") as file:
                    for line in file:
                        line = line.strip()
                        if not line:
                            continue
                        records.append(json.loads(line))
            except Exception:
                continue
        return records

    def _build_summary(self, granularity: str, period: Optional[str], records: List[Dict[str, Any]]) -> Dict[str, Any]:
        if records:
            first = records[-1]
            last = records[0]
            actual_period = period or first.get(granularity if granularity != "capture" else "record_id", "")
            highlights = []
            for item in records[:6]:
                text = item.get("vision_summary") or item.get("llm_response") or item.get("user_message") or ""
                text = " ".join(str(text).split())[:80]
                if text:
                    highlights.append(text)
        else:
            first = {}
            last = {}
            actual_period = period or ""
            highlights = []

        return {
            "period": actual_period,
            "from": first.get("timestamp", ""),
            "to": last.get("timestamp", ""),
            "highlights": highlights,
        }

    def _album_output_path(self, granularity: str, period: Optional[str], records: List[Dict[str, Any]]) -> Path:
        if granularity == "capture":
            record_id = period or (records[0].get("record_id") if records else "latest")
            date_key = (records[0].get("day") if records else datetime.now().strftime("%Y-%m-%d"))
            month_key = date_key[:7]
            week_key = (records[0].get("week") if records else self._current_week_key())
            folder = self.root_dir / "albums" / month_key / week_key / date_key
            folder.mkdir(parents=True, exist_ok=True)
            return folder / f"capture-{record_id}.jpeg"

        if granularity == "day":
            day_key = period or (records[0].get("day") if records else datetime.now().strftime("%Y-%m-%d"))
            month_key = day_key[:7]
            week_key = (records[0].get("week") if records else self._current_week_key())
            folder = self.root_dir / "albums" / month_key / week_key / day_key
            folder.mkdir(parents=True, exist_ok=True)
            return folder / f"daily-{day_key}.jpeg"

        if granularity == "week":
            week_key = period or (records[0].get("week") if records else self._current_week_key())
            month_key = (records[0].get("month") if records else datetime.now().strftime("%Y-%m"))
            folder = self.root_dir / "albums" / month_key / week_key
            folder.mkdir(parents=True, exist_ok=True)
            return folder / f"weekly-{week_key}.jpeg"

        month_key = period or (records[0].get("month") if records else datetime.now().strftime("%Y-%m"))
        folder = self.root_dir / "albums" / month_key
        folder.mkdir(parents=True, exist_ok=True)
        return folder / f"monthly-{month_key}.jpeg"

    def _copy_screenshot(
        self,
        *,
        source_path: str,
        month_key: str,
        week_key: str,
        day_key: str,
        record_id: str,
    ) -> Optional[Path]:
        if not source_path:
            return None

        source = Path(source_path)
        if not source.exists():
            return None

        target_dir = self.images_dir / month_key / week_key / day_key
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / f"{record_id}{source.suffix or '.png'}"

        try:
            shutil.copy2(source, target_path)
            return target_path
        except Exception:
            return None

    def _current_week_key(self) -> str:
        now = datetime.now()
        return f"{now.isocalendar().year}-W{now.isocalendar().week:02d}"
