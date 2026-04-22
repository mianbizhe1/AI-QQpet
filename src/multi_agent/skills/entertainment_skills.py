"""
娱乐类技能
笑话、故事等
"""

import random
from typing import Dict, Any

from ..skill_registry import Skill, SkillResult, SkillCategory


class JokeSkill(Skill):
    """笑话技能"""

    name = "joke"
    description = "给主人讲一个有趣的笑话"
    category = SkillCategory.ENTERTAINMENT
    agent_type = "entertainment"
    aliases = ["笑话", "讲笑话", "搞笑", "逗我笑"]

    parameters = [
        {"name": "category", "type": "string", "description": "笑话分类", "default": "random"},
    ]

    # 笑话库
    JOKES = [
        {
            "q": "为什么企鹅从不迷路？",
            "a": "因为它有GPS（Global Positioning System）—— Global Penguin System！",
        },
        {
            "q": "小企鹅问妈妈：妈妈，为什么我没有翅膀？",
            "a": "妈妈说：因为你已经是一只鸟了呀，只是航空公司不让你飞而已~",
        },
        {
            "q": "为什么QQ企鹅不吃冰块？",
            "a": "因为它已经是冷血动物了，再吃就变成冰企鹅啦！",
        },
        {
            "q": "程序员给老婆打电话：下班带一斤包子回来。",
            "a": "老婆回：好的，要肉的还是菜的？程序员说：都行。回家一看，全是包子。",
        },
        {
            "q": "为什么程序员分不清万圣节和圣诞节？",
            "a": "因为 Oct 31 = Dec 25（Octal 31 = Decimal 25）！",
        },
        {
            "q": "一只蝴蝶在花丛中飞来飞去，",
            "a": "它说：嗡嗡嗡~（蝴蝶：我不是蜜蜂，我只是路过打个招呼~）",
        },
        {
            "q": "企鹅宝宝问爸爸：爸爸，我是北极熊吗？",
            "a": "爸爸说：不是，你是企鹅。宝宝又问：那我是熊猫吗？爸爸说：也不是。宝宝急了：那我到底是什么？爸爸说：你是我的宝贝呀！",
        },
    ]

    def execute(self, category: str = "random") -> SkillResult:
        """讲笑话"""
        joke = random.choice(self.JOKES)

        content = f"嘿嘿~主人想听笑话吗？\n\n"
        content += f"🤡 {joke['q']}\n\n"
        content += f"答：{joke['a']}\n\n"
        content += f"主人觉得好笑吗~"

        return SkillResult(success=True, content=content)


class StorySkill(Skill):
    """故事技能"""

    name = "story"
    description = "给主人讲一个简短的小故事"
    category = SkillCategory.ENTERTAINMENT
    agent_type = "entertainment"
    aliases = ["故事", "讲故事", "讲个故事"]

    parameters = [
        {"name": "theme", "type": "string", "description": "故事主题"},
    ]

    # 故事库
    STORIES = [
        {
            "title": "小企鹅的第一次下海",
            "content": """从前有一只叫小Q的小企鹅，它一直很害怕大海。

有一天，它的好朋友海鸥告诉它："小Q，海水其实很温暖的！"

小Q鼓起勇气，第一次把脚伸进海里。哇，真的不冷呢！

从此，小Q爱上了游泳，还交了很多海底的朋友。

故事告诉我们：勇敢迈出第一步，你会发现世界没有想象中那么可怕~""",
        },
        {
            "title": "星星和月亮的对话",
            "content": """今晚的星星特别亮。

小星星问月亮："月亮姐姐，你为什么每天晚上都出来呀？"

月亮笑着说："因为我要照亮小朋友回家的路呀~"

小星星说："那我可以和你一起吗？"

月亮说："当然可以呀，我们一起守护主人~"

每天晚上，它们都在天上闪烁着光芒，守护着地上的每一个梦想。""",
        },
        {
            "title": "小Q学飞",
            "content": """小企鹅小Q看着天空中的鸟儿，心想：要是我也能飞就好了。

它试着挥动翅膀，但怎么也飞不起来。

"也许我永远也飞不起来了吧..."小Q有点难过。

这时候，企鹅妈妈过来说："小Q，虽然我们不能飞，但我们可以游泳呀！来，我教你~"

小Q发现，在水里游泳的感觉，其实和飞一样自由！

原来，每个人都有自己的天赋呀~""",
        },
    ]

    def execute(self, theme: str = "") -> SkillResult:
        """讲故事"""
        # 根据主题筛选
        if theme:
            matching_stories = [s for s in self.STORIES if theme in s["title"]]
            if matching_stories:
                story = random.choice(matching_stories)
            else:
                story = random.choice(self.STORIES)
        else:
            story = random.choice(self.STORIES)

        content = f"📖 {story['title']}\n\n"
        content += story["content"]
        content += f"\n\n主人喜欢这个故事吗~"

        return SkillResult(success=True, content=content)


class WeatherSkill(Skill):
    """天气查询技能"""

    name = "weather"
    description = "查询当前天气情况"
    category = SkillCategory.ENTERTAINMENT
    agent_type = "entertainment"
    aliases = ["天气", "查天气", "今天天气"]

    parameters = [
        {"name": "city", "type": "string", "description": "城市名称"},
    ]

    def execute(self, city: str = "") -> SkillResult:
        """查天气"""
        # 简化实现，实际项目中应该调用天气API
        import datetime

        hour = datetime.datetime.now().hour
        if 6 <= hour < 12:
            time_of_day = "早上"
        elif 12 <= hour < 18:
            time_of_day = "下午"
        else:
            time_of_day = "晚上"

        content = f"{time_of_day}好呀主人~小Q暂时还不会看天气预报呢..."

        return SkillResult(success=True, content=content)
