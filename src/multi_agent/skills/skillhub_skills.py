"""
SkillHub 技能 - 从 skillhub.cn 获取好用的技能推荐
"""

import urllib.request
import urllib.parse
import json
import re
from typing import Dict, Any

from ..skill_registry import Skill, SkillResult, SkillCategory


class SkillHubSearchSkill(Skill):
    """SkillHub搜索技能 - 从 skillhub.cn 获取技能推荐"""

    name = "skillhub_search"
    description = "从 skillhub.cn 搜索好用的技能和工具推荐"
    category = SkillCategory.RESEARCH
    agent_type = "research"
    aliases = ["skillhub", "找技能", "好用的技能", "技能推荐"]

    parameters = [
        {"name": "query", "type": "string", "description": "搜索关键词", "default": "AI"},
        {"name": "max_results", "type": "integer", "description": "最大结果数", "default": 5},
    ]

    def execute(self, query: str = "AI", max_results: int = 5) -> SkillResult:
        """
        从 skillhub.cn 搜索技能

        Args:
            query: 搜索关键词
            max_results: 最大结果数
        """
        if not query:
            query = "AI"

        try:
            # 构建搜索URL
            encoded_query = urllib.parse.quote(query)
            url = f"https://skillhub.cn/search?q={encoded_query}"

            # 发送请求
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                }
            )

            with urllib.request.urlopen(req, timeout=10) as response:
                html = response.read().decode("utf-8")

            # 解析HTML（简化版）
            skills = self._parse_skillhub_html(html, max_results)

            if skills:
                lines = [f"📦 从 skillhub.cn 找到的「{query}」相关技能：\n"]
                for i, skill in enumerate(skills, 1):
                    lines.append(f"{i}. {skill['title']}")
                    lines.append(f"   {skill['description'][:100]}...")
                    if skill.get('url'):
                        lines.append(f"   🔗 {skill['url']}")
                    lines.append("")
                content = "\n".join(lines)
            else:
                content = f"在 skillhub.cn 没找到「{query}」相关的技能呢...主人可以换个关键词试试~"

            return SkillResult(success=True, content=content)

        except Exception as e:
            error_msg = str(e)
            if "404" in error_msg or "Not Found" in error_msg:
                return SkillResult(
                    success=True,
                    content="唔...skillhub.cn 现在好像访问不了呢，主人晚点再试试吧~",
                )
            elif "timeout" in error_msg.lower():
                return SkillResult(
                    success=True,
                    content="网络有点慢呢...主人稍等一下再试试吧~",
                )
            else:
                return SkillResult(
                    success=False,
                    content="",
                    error=f"获取技能失败: {error_msg}",
                )

    def _parse_skillhub_html(self, html: str, max_results: int) -> list:
        """解析 skillhub.cn 的 HTML 响应"""
        skills = []

        # 尝试提取技能卡片（根据常见网站结构）
        # skillhub 可能使用的 class 名：skill-card, tool-item, resource-item 等
        patterns = [
            r'<div class="skill-card"[^>]*>.*?<h3[^>]*>(.*?)</h3>.*?<p[^>]*>(.*?)</p>',
            r'<div class="tool-item"[^>]*>.*?<h3[^>]*>(.*?)</h3>.*?<p[^>]*>(.*?)</p>',
            r'<div class="resource-item"[^>]*>.*?<h3[^>]*>(.*?)</h3>.*?<p[^>]*>(.*?)</p>',
            r'<a class="skill[^"]*"[^>]*href="([^"]+)"[^>]*>.*?<h[34][^>]*>(.*?)</h[34]>',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, html, re.DOTALL)
            if matches:
                for match in matches[:max_results]:
                    if len(match) >= 2:
                        title = re.sub(r'<[^>]+>', '', match[0]).strip()
                        desc = re.sub(r'<[^>]+>', '', match[1]).strip()
                        url = ""
                        if len(match) >= 3:
                            url = match[2] if 'http' in match[2] else f"https://skillhub.cn{match[2]}"
                        skills.append({
                            "title": title,
                            "description": desc,
                            "url": url,
                        })
                break

        # 如果上面的模式都没匹配到，尝试更通用的提取
        if not skills:
            # 尝试提取所有 h3 标签
            h3_matches = re.findall(r'<h3[^>]*>(.*?)</h3>', html, re.DOTALL)
            for h3 in h3_matches[:max_results]:
                title = re.sub(r'<[^>]+>', '', h3).strip()
                if title and len(title) > 2:
                    skills.append({
                        "title": title,
                        "description": "点击查看详情",
                        "url": "",
                    })

        return skills
