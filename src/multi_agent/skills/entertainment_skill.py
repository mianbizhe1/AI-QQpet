"""
娱乐推荐技能 - 搜索热点娱乐内容并推荐给主人
"""

import random
from typing import Dict, Any, List, Optional

from ..skill_registry import Skill, SkillResult, SkillCategory


class EntertainmentSkill(Skill):
    """娱乐推荐技能"""

    name = "entertainment_recommend"
    description = "搜索当前热点娱乐内容（综艺、剧集、明星八卦）并推荐给主人"
    category = SkillCategory.ENTERTAINMENT
    agent_type = "entertainment"
    aliases = ["娱乐推荐", "综艺推荐", "追剧", "热点娱乐"]

    parameters = [
        {"name": "category", "type": "string", "description": "内容分类", "default": "all"},
        {"name": "user_id", "type": "string", "description": "用户ID", "default": "default"},
    ]

    # 热点娱乐话题库（实际项目中应调用外部API）
    HOT_ENTERTAINMENT = {
        "variety_show": [
            "《奔跑吧》新一期太好笑了！",
            "《奇葩说》又有神仙打架的辩论了~",
            "《向往的生活》更新啦，慢生活治愈人心",
            "《创造营》小哥哥们舞台燃爆了！",
            "《脱口秀大会》笑点密集，根本停不下来~",
        ],
        "drama": [
            "《庆余年2》终于开播了！",
            "《繁花》王家卫执导，画面绝美",
            "《长相思》虐恋升级，太上头了！",
            "《狂飙》后再无爆款？不，还有这些...",
            "《墨雨云间》复仇爽剧，太解气了！",
        ],
        "celebrity": [
            "某顶流塌房？粉丝心碎了一地...",
            "某对明星夫妻离婚了，娱乐圈又一对",
            "某男神官宣恋情，女粉集体失恋",
            "某女演员新剧造型美出新高度",
            "某小鲜肉演技炸裂，路转粉了！",
        ],
        "hot_topic": [
            "某综艺新梗刷屏，太魔性了！",
            "某明星这个月上了8次热搜",
            "短视频平台又被某神曲刷屏了",
            "某部电影票房破10亿，口碑两极分化",
            "某选秀节目黑幕曝光，粉丝抗议",
        ],
    }

    def execute(
        self,
        category: str = "all",
        user_id: str = "default",
    ) -> SkillResult:
        """
        执行娱乐推荐

        1. 获取主人的娱乐偏好
        2. 搜索当前热点
        3. 匹配并推荐
        """
        try:
            # 导入memory模块获取主人偏好
            from memory import get_memory_api

            memory_api = get_memory_api()
            profile = memory_api.get_master_profile(user_id)

            # 根据分类或偏好推荐
            if category == "all":
                selected_category = self._select_category(profile)
            else:
                selected_category = category

            # 获取热点内容
            hot_content = self._get_hot_content(selected_category)

            # 构建推荐消息
            recommendation = self._build_recommendation(
                hot_content,
                selected_category,
                profile,
            )

            return SkillResult(
                success=True,
                content=recommendation,
                data={
                    "category": selected_category,
                    "user_id": user_id,
                    "preferences": profile.get("entertainment", {}),
                },
            )

        except ImportError:
            # memory模块不可用，使用默认推荐
            return self._fallback_recommendation(category)
        except Exception as e:
            return SkillResult(
                success=False,
                content="",
                error=f"娱乐推荐失败: {str(e)}",
            )

    def _select_category(self, profile: Dict[str, Any]) -> str:
        """根据主人偏好选择分类"""
        entertainment = profile.get("entertainment", {})

        # 从偏好中选择一个分类
        if entertainment:
            prefs = list(entertainment.keys())
            if prefs:
                return random.choice(prefs)

        # 默认随机选择
        categories = list(self.HOT_ENTERTAINMENT.keys())
        return random.choice(categories)

    def _get_hot_content(self, category: str) -> List[str]:
        """获取热点内容"""
        if category == "all":
            # 合并所有分类
            all_content = []
            for contents in self.HOT_ENTERTAINMENT.values():
                all_content.extend(contents)
            return random.sample(all_content, min(3, len(all_content)))
        else:
            return self.HOT_ENTERTAINMENT.get(category, [])

    def _build_recommendation(
        self,
        hot_content: List[str],
        category: str,
        profile: Dict[str, Any],
    ) -> str:
        """构建推荐消息"""
        if not hot_content:
            return "嘿嘿~暂时没有找到合适的推荐，要不主人告诉我你想看什么？"

        nickname = profile.get("nickname") or "主人"

        lines = [f"*{nickname}~ 小Q发现了一些有趣的娱乐内容哦：*\n"]

        for i, content in enumerate(hot_content[:3], 1):
            lines.append(f"{i}. {content}")

        lines.append("\n主人想了解哪个呀~")

        return "\n".join(lines)

    def _fallback_recommendation(self, category: str) -> SkillResult:
        """降级推荐（memory模块不可用时）"""
        hot_content = self._get_hot_content(category)

        if not hot_content:
            return SkillResult(
                success=True,
                content="嘿嘿~小Q还没来得及看热点呢，主人想聊什么呀？",
            )

        content = random.choice(hot_content)

        return SkillResult(
            success=True,
            content=f"主人~ 小Q发现了一个有趣的话题：\n\n{content}\n\n主人感兴趣吗~",
            data={"category": category},
        )


class EntertainmentUpdateSkill(Skill):
    """热点话题更新技能 - 定时任务用"""

    name = "entertainment_update"
    description = "更新主人的热点话题列表"
    category = SkillCategory.ENTERTAINMENT
    agent_type = "system"

    parameters = [
        {"name": "user_id", "type": "string", "description": "用户ID", "default": "default"},
    ]

    def execute(self, user_id: str = "default") -> SkillResult:
        """更新热点话题"""
        try:
            from memory import get_memory_api

            memory_api = get_memory_api()

            # 随机选择几个热点话题更新
            import random
            all_topics = []
            for contents in EntertainmentSkill.HOT_ENTERTAINMENT.values():
                all_topics.extend(contents)

            new_topics = random.sample(all_topics, min(3, len(all_topics)))

            # 更新主人画像
            profile = memory_api.update_hot_topics(new_topics, user_id)

            return SkillResult(
                success=True,
                content=f"已更新热点话题: {', '.join(new_topics)}",
                data={"hot_topics": new_topics},
            )

        except ImportError:
            return SkillResult(
                success=False,
                content="",
                error="memory模块不可用",
            )
        except Exception as e:
            return SkillResult(
                success=False,
                content="",
                error=f"更新热点话题失败: {str(e)}",
            )
