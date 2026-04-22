from pathlib import Path

from src.ai_agent.life_album import LifeAlbumStore


def test_record_capture_groups_into_day_file_and_week_folder(tmp_path: Path):
    store = LifeAlbumStore(tmp_path / "life_album")
    screenshot = tmp_path / "screen.png"
    screenshot.write_bytes(b"fake-png")

    result = store.record_capture(
        screenshot_path=str(screenshot),
        vision_summary="主人正在写代码",
        llm_response="小Q觉得主人在给我做新功能",
        event="vision_watch",
        user_message="这是定时观察",
        frontmost_app="JoyDesk",
        frontmost_window="Claude Code",
        tool_calls=["tool-result"],
    )

    day_file = Path(result["storage"]["day_file"])
    assert day_file.exists()
    assert day_file.parent.name == result["storage"]["week"]
    assert day_file.name == f'{result["storage"]["day"]}.jsonl'

    payload = store.get_records("day", result["storage"]["day"])
    assert payload["count"] == 1
    assert payload["records"][0]["vision_summary"] == "主人正在写代码"
    assert payload["records"][0]["llm_response"] == "小Q觉得主人在给我做新功能"


def test_album_output_path_respects_granularity(tmp_path: Path):
    store = LifeAlbumStore(tmp_path / "life_album")
    screenshot = tmp_path / "screen.png"
    screenshot.write_bytes(b"fake-png")
    result = store.record_capture(
        screenshot_path=str(screenshot),
        vision_summary="主人正在整理记忆",
        llm_response="今天像在做相册系统",
    )

    day = result["storage"]["day"]
    week = result["storage"]["week"]
    month = result["storage"]["month"]

    day_payload = store.get_records("day", day)
    week_payload = store.get_records("week", week)
    month_payload = store.get_records("month", month)

    assert day_payload["album_output_path"].endswith(f"/{month}/{week}/{day}/daily-{day}.jpeg")
    assert week_payload["album_output_path"].endswith(f"/{month}/{week}/weekly-{week}.jpeg")
    assert month_payload["album_output_path"].endswith(f"/{month}/monthly-{month}.jpeg")
