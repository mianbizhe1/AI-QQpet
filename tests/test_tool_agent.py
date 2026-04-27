"""测试 ToolAgent 的上下文状态归一化。"""

from src.ai_agent.tool_agent import ToolAgent


def make_agent() -> ToolAgent:
    """跳过 __init__，只测试纯数据处理逻辑。"""
    return ToolAgent.__new__(ToolAgent)


def test_normalize_pet_status_flat_shape():
    agent = make_agent()

    normalized = agent._normalize_pet_status(
        {
            "name": "小Q",
            "level": 12,
            "growth": 3456,
            "hunger": 500,
            "hunger_max": 3100,
            "clean": 2800,
            "clean_max": 3100,
            "health": 5,
            "mood": 120,
            "mood_max": 1000,
            "yb": 888,
            "intel": 66,
            "charm": 77,
            "strong": 88,
            "is_hungry": True,
        }
    )

    assert normalized["name"] == "小Q"
    assert normalized["yb"] == 888
    assert normalized["level"] == 12
    assert normalized["hunger_max"] == 3100
    assert normalized["is_hungry"] is True


def test_normalize_pet_status_nested_shape():
    agent = make_agent()

    normalized = agent._normalize_pet_status(
        {
            "info": {
                "name": "小Q",
                "growth": 4321,
                "hunger": 700,
                "clean": 2600,
                "health": 4,
                "mood": 99,
                "yb": 123,
                "intel": 12,
                "charm": 23,
                "strong": 34,
            },
            "maxInfo": {
                "level": 15,
                "hunger": 4500,
                "clean": 4500,
                "mood": 1000,
            },
            "active_option": {
                "ill": {"name": "感冒"},
            },
            "is_sick": True,
        }
    )

    assert normalized["level"] == 15
    assert normalized["yb"] == 123
    assert normalized["ill"] == {"name": "感冒"}
    assert normalized["is_sick"] is True
