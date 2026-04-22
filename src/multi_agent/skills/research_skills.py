"""
研究类技能
搜索论文、新闻等
"""

import urllib.request
import urllib.parse
import json
import re
from typing import Dict, Any

from ..skill_registry import Skill, SkillResult, SkillCategory


class AIPaperSearchSkill(Skill):
    """AI论文搜索技能 - 搜索arXiv上的AI论文"""

    name = "ai_paper_search"
    description = "搜索arXiv上的AI/ML论文，返回论文标题、作者、摘要和链接"
    category = SkillCategory.RESEARCH
    agent_type = "research"
    aliases = ["论文搜索", "搜论文", "AI论文", "找论文"]

    parameters = [
        {"name": "topic", "type": "string", "description": "搜索主题或关键词", "required": True},
        {"name": "max_results", "type": "integer", "description": "最大结果数", "default": 5},
        {"name": "category", "type": "string", "description": "arXiv分类，如 cs.AI, cs.LG, cs.CL", "default": "cs.AI"},
    ]

    def execute(self, topic: str, max_results: int = 5, category: str = "cs.AI") -> SkillResult:
        """
        搜索arXiv论文

        Args:
            topic: 搜索主题
            max_results: 最大结果数
            category: arXiv分类
        """
        if not topic:
            return SkillResult(success=False, content="", error="搜索主题不能为空")

        try:
            # 使用arXiv API
            query = urllib.parse.quote(f"all:{topic}")
            url = f"http://export.arxiv.org/api/query?search_query={query}&start=0&max_results={max_results}&sortBy=relevance"

            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as response:
                data = response.read().decode("utf-8")

            # 解析XML响应（简化版）
            papers = self._parse_arxiv_response(data)

            if papers:
                lines = [f"关于「{topic}」的arXiv论文：\n"]
                for i, paper in enumerate(papers, 1):
                    lines.append(f"{i}. {paper['title']}")
                    lines.append(f"   作者: {paper['authors']}")
                    lines.append(f"   摘要: {paper['summary'][:200]}...")
                    lines.append(f"   链接: {paper['id']}\n")
                content = "\n".join(lines)
            else:
                content = f"没有找到关于「{topic}」的论文呢..."

            return SkillResult(success=True, content=content)

        except Exception as e:
            return SkillResult(success=False, content="", error=f"搜索论文失败: {str(e)}")

    def _parse_arxiv_response(self, data: str) -> list:
        """解析arXiv API响应"""
        papers = []

        # 简单解析entry
        entries = re.findall(r"<entry>(.*?)</entry>", data, re.DOTALL)
        for entry in entries:
            title = re.search(r"<title>(.*?)</title>", entry, re.DOTALL)
            summary = re.search(r"<summary>(.*?)</summary>", entry, re.DOTALL)
            authors = re.findall(r"<name>(.*?)</name>", entry)
            id_match = re.search(r"<id>(.*?)</id>", entry)

            if title and summary:
                papers.append({
                    "title": title.group(1).replace("\n", " ").strip(),
                    "summary": summary.group(1).replace("\n", " ").strip(),
                    "authors": ", ".join(authors[:3]) + ("等" if len(authors) > 3 else ""),
                    "id": id_match.group(1) if id_match else "",
                })

        return papers


class NewsSearchSkill(Skill):
    """新闻搜索技能"""

    name = "news_search"
    description = "搜索最新新闻和资讯"
    category = SkillCategory.RESEARCH
    agent_type = "research"
    aliases = ["新闻", "搜新闻", "查新闻", "最新消息"]

    parameters = [
        {"name": "query", "type": "string", "description": "搜索关键词", "required": True},
        {"name": "max_results", "type": "integer", "description": "最大结果数", "default": 5},
    ]

    def execute(self, query: str, max_results: int = 5) -> SkillResult:
        """搜索新闻"""
        if not query:
            return SkillResult(success=False, content="", error="搜索关键词不能为空")

        try:
            # 使用DuckDuckGo News API
            encoded_query = urllib.parse.quote(query)
            url = f"https://api.duckduckgo.com/?q={encoded_query}&format=json&no_html=1&skip_disambig=1"

            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode("utf-8"))

            results = []

            # 提取RelatedTopics中的新闻
            if data.get("RelatedTopics"):
                for topic in data["RelatedTopics"][:max_results]:
                    if topic.get("Text"):
                        results.append(f"• {topic['Text'][:150]}")

            if data.get("AbstractText"):
                results.insert(0, f"📌 {data['AbstractText']}")

            if results:
                content = f"关于「{query}」的最新消息：\n\n" + "\n".join(results)
            else:
                content = f"没有找到关于「{query}」的新闻呢..."

            return SkillResult(success=True, content=content)

        except Exception as e:
            return SkillResult(success=False, content="", error=f"搜索新闻失败: {str(e)}")


class BrowserSearchSkill(Skill):
    """通用网页搜索（从ai_tools迁移）"""

    name = "browser_search"
    description = "使用浏览器搜索信息，可以搜索天气、资讯、百科等"
    category = SkillCategory.RESEARCH
    agent_type = "research"
    aliases = ["搜索", "搜一下", "查一下", "找一下", "帮我搜"]

    parameters = [
        {"name": "query", "type": "string", "description": "搜索关键词或问题", "required": True},
        {"name": "reasoning", "type": "string", "description": "搜索目的"},
    ]

    def execute(self, query: str, reasoning: str = "") -> SkillResult:
        """执行搜索"""
        if not query:
            return SkillResult(success=False, content="", error="搜索关键词不能为空")

        try:
            encoded_query = urllib.parse.quote(query)
            search_url = f"https://duckduckgo.com/?q={encoded_query}"

            # 使用DuckDuckGo Instant Answer API
            url = f"https://api.duckduckgo.com/?q={encoded_query}&format=json&no_html=1"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode("utf-8"))

            results = []

            if data.get("AbstractText"):
                results.append(f"📌 {data['AbstractText']}")

            if data.get("Answer"):
                results.insert(0, f"💡 {data['Answer']}")

            if data.get("RelatedTopics"):
                for topic in data["RelatedTopics"][:3]:
                    if topic.get("Text"):
                        results.append(f"• {topic['Text'][:200]}")

            if results:
                content = f"关于「{query}」：\n\n" + "\n".join(results) + f"\n\n🔗 查看更多: {search_url}"
            else:
                content = f"已准备好搜索「{query}」，结果可在链接查看: {search_url}"

            return SkillResult(success=True, content=content)

        except Exception as e:
            return SkillResult(success=False, content="", error=f"搜索失败: {str(e)}")
