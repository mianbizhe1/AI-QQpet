from src.multi_agent.skills.research_skills import WeiboHotSearchSkill


def test_weibo_hot_search_skill_prefers_ajax_api(monkeypatch):
    import src.multi_agent.skills.research_skills as skill_module

    updated = {}

    class _FakeMemoryAPI:
        def update_hot_topics(self, topics, user_id):
            updated["topics"] = topics
            updated["user_id"] = user_id

    monkeypatch.setattr(skill_module, "datetime", type("FakeDatetime", (), {
        "now": staticmethod(lambda: __import__("datetime").datetime(2026, 4, 27, 12, 0, 0))
    }))
    monkeypatch.setattr(WeiboHotSearchSkill, "_fetch_items_from_api", lambda self, max_results: [
        {"rank": "1", "title": "热搜一", "label": "热", "href": "https://example.com/1"},
        {"rank": "2", "title": "热搜二", "label": "", "href": "https://example.com/2"},
        {"rank": "3", "title": "热搜三", "label": "新", "href": "https://example.com/3"},
    ][:max_results])
    monkeypatch.setattr(WeiboHotSearchSkill, "_generate_gossip_with_llm", lambda self, item: "这条热搜一挂榜首，讨论得还挺凶。")
    monkeypatch.setattr(WeiboHotSearchSkill, "_build_hot_summary", lambda self, item: "热搜一是在说某件事突然冲上榜首，大家都在集中讨论。")
    monkeypatch.setattr(WeiboHotSearchSkill, "_fetch_page_html", lambda self: (_ for _ in ()).throw(AssertionError("html fallback should not run")))
    monkeypatch.setitem(__import__("sys").modules, "memory", type("FakeMemory", (), {
        "get_memory_api": lambda: _FakeMemoryAPI(),
    }))

    skill = WeiboHotSearchSkill()
    result = skill.execute(max_results=3, user_id="u1")

    assert result.success is True
    assert result.content == "这条热搜一挂榜首，讨论得还挺凶。"
    assert result.data["top_item"]["title"] == "热搜一"
    assert result.data["top_summary"] == "热搜一是在说某件事突然冲上榜首，大家都在集中讨论。"
    assert result.data["fetch_mode"] == "ajax_api"
    assert updated == {"topics": ["热搜一", "热搜二", "热搜三"], "user_id": "u1"}


def test_weibo_hot_search_skill_falls_back_when_llm_unavailable(monkeypatch):
    import src.multi_agent.skills.research_skills as skill_module

    updated = {}
    sample_html = """
    <html>
      <body>
        <table>
          <tbody>
            <tr>
              <td class="td-01">1</td>
              <td class="td-02"><a href="/weibo?q=%23%E7%83%AD%E6%90%9C%E4%B8%80%23">热搜一</a></td>
              <td class="td-03"><span>热</span></td>
            </tr>
            <tr>
              <td class="td-01">2</td>
              <td class="td-02"><a href="/weibo?q=%23%E7%83%AD%E6%90%9C%E4%BA%8C%23">热搜二</a></td>
              <td class="td-03"></td>
            </tr>
            <tr>
              <td class="td-01">3</td>
              <td class="td-02"><a href="/weibo?q=%23%E7%83%AD%E6%90%9C%E4%B8%89%23">热搜三</a></td>
              <td class="td-03"><span>新</span></td>
            </tr>
          </tbody>
        </table>
      </body>
    </html>
    """.strip()

    class _FakeMemoryAPI:
        def update_hot_topics(self, topics, user_id):
            updated["topics"] = topics
            updated["user_id"] = user_id

    monkeypatch.setattr(skill_module, "datetime", type("FakeDatetime", (), {
        "now": staticmethod(lambda: __import__("datetime").datetime(2026, 4, 27, 12, 0, 0))
    }))
    monkeypatch.setattr(WeiboHotSearchSkill, "_fetch_items_from_api", lambda self, max_results: [])
    monkeypatch.setattr(WeiboHotSearchSkill, "_fetch_page_html", lambda self: sample_html)
    monkeypatch.setattr(WeiboHotSearchSkill, "_generate_gossip_with_llm", lambda self, item: "")
    monkeypatch.setattr(WeiboHotSearchSkill, "_build_hot_summary", lambda self, item: "热搜一是在讲一件新爆出来的事，所以讨论度一下子很高。")
    monkeypatch.setitem(__import__("sys").modules, "memory", type("FakeMemory", (), {
        "get_memory_api": lambda: _FakeMemoryAPI(),
    }))

    skill = WeiboHotSearchSkill()
    result = skill.execute(max_results=3, user_id="u1")

    assert result.success is True
    assert "热搜一" in result.content
    assert result.data["top_item"]["title"] == "热搜一"
    assert result.data["top_summary"] == "热搜一是在讲一件新爆出来的事，所以讨论度一下子很高。"
    assert result.data["signature"] == "热搜一|热搜二|热搜三"
    assert result.data["fetch_mode"] == "http"
    assert updated == {"topics": ["热搜一", "热搜二", "热搜三"], "user_id": "u1"}


def test_weibo_hot_search_summary_fallback_mentions_missing_context():
    skill = WeiboHotSearchSkill()

    summary = skill._build_summary_fallback({"title": "热搜一", "label": ""})

    assert "热搜一" in summary
    assert "具体发生了什么" in summary
