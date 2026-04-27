from types import SimpleNamespace
from uuid import uuid4

import src.ai_agent.tool_agent as tool_agent_module
from src.ai_agent.tool_agent import ToolAgent
from src.ai_server import QQPETHandler
from src.memory.database import Database
from src.memory.long_term_memory import LongTermMemory
from src.memory.memory_learner import MemoryLearner
from src.memory.memory_recall import MemoryRecall


class _FakeStatus:
    def __init__(self):
        self.inventory = SimpleNamespace(food=[], commodity=[], medicine=[])

    def to_status_dict(self):
        return {"name": "小Q"}


def test_ai_server_tool_agent_path_passes_recent_memory_and_still_saves_episode():
    handler = QQPETHandler.__new__(QQPETHandler)
    handler.client = SimpleNamespace(
        get_status=lambda: _FakeStatus(),
        get_personality=lambda: {"warmth": 0.6},
    )

    captured = {}

    def fake_run_tool_agent_chat(**kwargs):
        captured["recent_memory"] = kwargs["recent_memory"]
        return {"response": "我记得你昨天说过这个~", "tool_calls": [], "success": True}

    def fake_save_to_memory(**kwargs):
        captured["saved_dialogue"] = kwargs["dialogue"]
        captured["saved_event"] = kwargs["event"]

    handler._run_tool_agent_chat = fake_run_tool_agent_chat
    handler._normalize_decision = lambda decision, fallback: decision
    handler._fallback_decision = lambda event, status: {"action": "none", "action_args": {}, "dialogue": "", "priority": 0}
    handler._llm_decide = lambda **kwargs: {"action": "none", "action_args": {}, "dialogue": "fallback", "priority": 0}
    handler._save_to_memory = fake_save_to_memory

    payload = {
        "event": "chat",
        "message": "还记得我昨天提的剧吗",
        "user_context": {},
        "recent_memory": [{"content": "昨天聊到《三体》"}],
    }
    result = handler._build_ai_response(payload)

    assert captured["recent_memory"] == payload["recent_memory"]
    assert captured["saved_event"] == "chat"
    assert captured["saved_dialogue"] == "我记得你昨天说过这个~"
    assert result["agent"] == "tool_agent"


def test_tool_agent_merges_recent_dialogue_with_profile_context():
    captured = {}

    class FakeLLMClient:
        config = SimpleNamespace(model="gpt-4o", base_url="https://example.com")

        def chat(self, messages, temperature=None, max_tokens=None):
            captured["messages"] = messages
            return SimpleNamespace(content="陪你继续聊这个呀")

    class FakeMemoryAPI:
        def get_master_profile(self, user_id):
            return {
                "interests": ["科幻"],
                "entertainment": {"variety_shows": ["脱口秀大会"]},
                "hot_topics": ["三体"],
            }

        def recall_memories(self, context, user_id, limit=3):
            return {"memories": []}

        def learn_from_conversation(self, messages, pet_name, user_id):
            return {}

    agent = ToolAgent.__new__(ToolAgent)
    agent.config_path = "test"
    agent.llm_client = FakeLLMClient()
    agent.vision_analyzer = None
    agent.life_album_store = None
    agent.tools = []
    agent.max_turns = 1
    agent._build_system_prompt = lambda has_screenshot=False: "system"
    agent._extract_and_execute_tool = lambda content: None
    agent._extract_response = lambda content: content
    agent._record_life_album = lambda **kwargs: None

    original_memory_available = tool_agent_module.MEMORY_AVAILABLE
    original_get_memory_api = tool_agent_module.get_memory_api
    tool_agent_module.MEMORY_AVAILABLE = True
    tool_agent_module.get_memory_api = lambda config_path=None: FakeMemoryAPI()
    try:
        result = agent.chat(
            "还想继续聊三体",
            {
                "user_id": "u1",
                "recent_memory": [{"content": "昨天你推荐了《三体》"}],
                "pet_status": {},
                "personality": {},
            },
        )
    finally:
        tool_agent_module.MEMORY_AVAILABLE = original_memory_available
        tool_agent_module.get_memory_api = original_get_memory_api

    assert result["response"] == "陪你继续聊这个呀"
    user_content = captured["messages"][1].content
    joined_text = "\n".join(part["text"] for part in user_content if part.get("type") == "text")
    assert "【最近对话】" in joined_text
    assert "昨天你推荐了《三体》" in joined_text
    assert "主人兴趣: 科幻" in joined_text
    assert "主人喜欢的综艺: 脱口秀大会" in joined_text


def test_memory_recall_updates_access_for_selected_memories():
    recall = MemoryRecall.__new__(MemoryRecall)
    recall._llm_client = None

    updated_ids = []
    memory = SimpleNamespace(
        id=7,
        content="三体相关记忆",
        importance=0.9,
        tags=[],
        access_count=0,
        created_at=None,
        to_dict=lambda: {
            "id": 7,
            "content": "三体相关记忆",
            "importance": 0.9,
            "tags": [],
            "access_count": 0,
            "created_at": None,
        },
    )

    recall.profile_manager = SimpleNamespace(
        get_profile=lambda user_id: SimpleNamespace(hot_topics=[], interests=[])
    )
    recall.memory_manager = SimpleNamespace(
        search_memories=lambda keyword, user_id, limit=10: [memory],
        get_important=lambda user_id, limit=5, threshold=0.7: [],
        get_by_category=lambda category, user_id, limit=5: [],
        update_access=lambda memory_id, user_id: updated_ids.append((memory_id, user_id)),
    )
    recall._get_llm_client = lambda: SimpleNamespace(is_configured=lambda: False)

    results = recall.recall_relevant({"current_topic": "三体"}, user_id="u1", limit=3)

    assert len(results) == 1
    assert updated_ids == [(7, "u1")]


def test_long_term_memory_deduplicates_by_canonical_key(tmp_path):
    db_path = tmp_path / f"memory-{uuid4().hex}.db"
    db = Database.get_instance(str(db_path))
    memory_manager = LongTermMemory(db)

    first = memory_manager.add_memory(
        memory_type="fact",
        content="主人喜欢三体",
        source="conversation",
        importance=0.6,
        category="entertainment",
        user_id="u1",
    )
    second = memory_manager.add_memory(
        memory_type="fact",
        content="主人 喜欢 三体！",
        source="conversation",
        importance=0.9,
        category="entertainment",
        user_id="u1",
    )

    memories = memory_manager.get_memories(user_id="u1")
    assert first.id == second.id
    assert len(memories) == 1
    assert memories[0].importance == 0.9
    assert memories[0].canonical_key


def test_memory_learner_writes_lineage_to_memory_and_preference(tmp_path):
    db_path = tmp_path / f"memory-{uuid4().hex}.db"
    db = Database.get_instance(str(db_path))
    learner = MemoryLearner(db=db)
    learner._save_learning_result(
        SimpleNamespace(
            interests=[],
            entertainment={},
            hot_topics=[],
            new_memories=["主人在做 iOS 开发"],
            preferences={"favorite_topic": "科幻"},
        ),
        user_id="u1",
        source_episode_id=42,
    )

    memory_manager = LongTermMemory(db)
    memories = memory_manager.get_memories(user_id="u1")
    preferences = memory_manager.get_preferences(user_id="u1")

    assert memories[0].source_episode_id == 42
    assert memories[0].canonical_key
    assert preferences[0]["source_episode_id"] == 42
    assert preferences[0]["canonical_key"] == "topic:favorite_topic"
