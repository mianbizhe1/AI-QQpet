"""
研究类技能
搜索论文、新闻等
"""

import html
import json
import re
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any, Dict, List

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


class WeiboHotSearchSkill(Skill):
    """后台抓取微博热搜榜，不打扰前台浏览器。"""

    name = "weibo_hot_search"
    description = "后台抓取微博热搜前十条，不影响当前浏览器"
    category = SkillCategory.RESEARCH
    agent_type = "system"
    aliases = ["微博热搜", "热搜榜", "微博榜单", "微博前十"]

    parameters = [
        {"name": "max_results", "type": "integer", "description": "抓取条数", "default": 10},
        {"name": "user_id", "type": "string", "description": "用户ID", "default": "default"},
    ]

    _HOT_SEARCH_URL = "https://s.weibo.com/top/summary"
    _HOT_SEARCH_API_URL = "https://weibo.com/ajax/side/hotSearch"
    _WEIBO_SEARCH_URL = "https://s.weibo.com/weibo"
    _REQUEST_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        ),
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": "https://weibo.com/",
    }

    def execute(
        self,
        max_results: int = 10,
        user_id: str = "default",
        browser: str = "Google Chrome",
        wait_seconds: float = 3.5,
    ) -> SkillResult:
        if max_results <= 0:
            return SkillResult(success=False, content="", error="max_results 必须大于 0")

        try:
            items, fetch_mode = self._fetch_items(max_results)
        except Exception as e:
            return SkillResult(success=False, content="", error=f"抓取微博热搜失败: {e}")

        if not items:
            return SkillResult(success=False, content="", error="未抓取到微博热搜条目")

        self._update_hot_topics(items, user_id)

        fetched_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        hottest = items[0]
        content = self._build_gossip_message(hottest)
        summary = self._build_hot_summary(hottest)

        return SkillResult(
            success=True,
            content=content,
            data={
                "items": items,
                "top_item": hottest,
                "top_summary": summary,
                "signature": "|".join(item["title"] for item in items),
                "fetched_at": fetched_at,
                "source_url": self._HOT_SEARCH_URL,
                "fetch_mode": fetch_mode,
            },
        )

    def _build_gossip_message(self, item: Dict[str, str]) -> str:
        llm_message = self._generate_gossip_with_llm(item)
        if llm_message:
            return llm_message

        return self._build_gossip_fallback(item)

    def _build_hot_summary(self, item: Dict[str, str]) -> str:
        title = item.get("title", "").strip()
        if not title:
            return ""

        try:
            page_html = self._fetch_search_html(title)
            excerpt = self._extract_summary_from_search_html(page_html)
        except Exception as e:
            print(f"[WeiboSummary] 抓取搜索结果失败: {e}")
            excerpt = ""

        llm_summary = self._generate_summary_with_llm(item, excerpt)
        if llm_summary:
            return llm_summary

        if excerpt:
            return self._build_summary_from_excerpt(title, excerpt)

        return self._build_summary_fallback(item)

    def _generate_gossip_with_llm(self, item: Dict[str, str]) -> str:
        try:
            from ai_llm import Message, get_llm_client

            llm = get_llm_client()
            if not llm.is_configured():
                return ""

            title = item.get("title", "").strip()
            label = item.get("label", "").strip()
            href = item.get("href", "").strip()
            rank = item.get("rank", "1")

            system_prompt = (
                "你是QQ企鹅小Q。"
                "请把微博热搜榜一改写成一句自然、爱八卦、轻松的中文聊天句子。"
                "要求：1. 只输出一句成品，不要解释。"
                "2. 不要每次都用固定开头。"
                "3. 像宠物在和主人随口聊八卦，但不要太油。"
                "4. 不要编造事实，只能基于给定词条本身。"
                "5. 不要使用项目符号、引号块、emoji。"
                "6. 最长不超过38个中文字符。"
            )
            prompt = (
                f"微博热搜榜一词条：{title}\n"
                f"标签：{label or '无'}\n"
                f"排名：{rank}\n"
                f"链接：{href or '无'}\n"
                "请直接生成一句小Q会对主人说的话。"
            )
            response = llm.chat(
                [Message(role="user", content=prompt)],
                system_prompt=system_prompt,
                temperature=0.9,
                max_tokens=800,
            )
            content = (response.content or "").strip()
            # 移除 <think>...</think> 思考标签
            content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()

            print(f"[WeiboGossip] 清理后内容: {content}")
            return content.replace("\n", " ").strip(" \t\r\n\"'")
        except Exception as e:
            print(f"[WeiboGossip] LLM调用失败: {e}")
            return ""

    def _generate_summary_with_llm(self, item: Dict[str, str], excerpt: str) -> str:
        if not excerpt:
            return ""

        try:
            from ai_llm import Message, get_llm_client

            llm = get_llm_client()
            if not llm.is_configured():
                return ""

            title = item.get("title", "").strip()
            label = item.get("label", "").strip()
            rank = item.get("rank", "1")

            system_prompt = (
                "你是QQ企鹅小Q。"
                "请根据微博热搜词条和搜索结果摘要，用一句中文讲清楚到底发生了什么。"
                "要求：1. 只输出一句成品，不要解释。"
                "2. 必须基于提供材料，不要编造。"
                "3. 像小企鹅在替主人总结，但以信息清楚为主，不要太浮夸。"
                "4. 最长不超过55个中文字符。"
            )
            prompt = (
                f"微博热搜词条：{title}\n"
                f"标签：{label or '无'}\n"
                f"排名：{rank}\n"
                f"搜索结果摘要：{excerpt}\n"
                "请总结成一句“这条热搜到底发生了什么”。"
            )
            response = llm.chat(
                [Message(role="user", content=prompt)],
                system_prompt=system_prompt,
                temperature=0.4,
                max_tokens=800,
            )
            content = (response.content or "").strip()
            content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
            return content.replace("\n", " ").strip(" \t\r\n\"'")
        except Exception as e:
            print(f"[WeiboSummary] LLM调用失败: {e}")
            return ""

    def _build_gossip_fallback(self, item: Dict[str, str]) -> str:
        title = item.get("title", "").strip()
        label = item.get("label", "").strip()
        label_text = f"（{label}）" if label else ""
        subject = f"“{title}”{label_text}"
        templates = [
            f"欸，微博榜一居然冲到 {subject} 了，你说这事是不是又要吵一阵子？",
            f"我刚瞄了一眼热搜，挂在最上面的就是 {subject}，感觉讨论度有点夸张。",
            f"今天微博最顶上那条是 {subject}，这名字一看就很像有后续的样子。",
            f"最新那口瓜先递给你，微博现在排第一的是 {subject}，要不要顺手聊聊看？",
            f"我这边刚刷到，微博最热的话题已经变成 {subject} 了，空气里都有点八卦味。",
        ]
        index = sum(ord(ch) for ch in f"{title}|{label}") % len(templates)
        return templates[index]

    def _build_summary_from_excerpt(self, title: str, excerpt: str) -> str:
        text = excerpt.strip("，。；： ")
        if not text:
            return self._build_summary_fallback({"title": title})

        if title and title not in text[:24]:
            text = f"{title}这事大概是：{text}"

        text = re.sub(r"\s+", " ", text).strip()
        if len(text) > 58:
            text = text[:57].rstrip("，。；： ") + "。"
        elif text[-1] not in "。！？":
            text += "。"
        return text

    def _build_summary_fallback(self, item: Dict[str, str]) -> str:
        title = item.get("title", "").strip()
        label = item.get("label", "").strip()
        if label:
            return f"我只确认到这条热搜是“{title}”，还没抓到更完整的来龙去脉。"
        return f"我先看到热搜词条是“{title}”，但还没补到它具体发生了什么。"

    def _fetch_search_html(self, keyword: str) -> str:
        query = urllib.parse.quote(keyword)
        url = f"{self._WEIBO_SEARCH_URL}?q={query}"
        req = urllib.request.Request(url, headers=self._REQUEST_HEADERS)
        with urllib.request.urlopen(req, timeout=10) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, errors="ignore")

    def _extract_summary_from_search_html(self, page_html: str) -> str:
        patterns = [
            r'<p[^>]+node-type="feed_list_content[^"]*"[^>]*>(.*?)</p>',
            r'<p[^>]+class="txt"[^>]*>(.*?)</p>',
            r'<div[^>]+class="card-feed"[^>]*>(.*?)</div>',
        ]
        for pattern in patterns:
            matches = re.findall(pattern, page_html, re.DOTALL | re.IGNORECASE)
            for raw in matches:
                text = self._clean_html_text(raw)
                text = re.sub(r"全文$|收起d?$", "", text).strip()
                if len(text) >= 18:
                    return text
        return ""

    def _fetch_items(self, max_results: int) -> tuple[List[Dict[str, str]], str]:
        errors: List[str] = []

        try:
            api_items = self._fetch_items_from_api(max_results)
            if api_items:
                return api_items, "ajax_api"
            errors.append("ajax_api 返回空列表")
        except Exception as e:
            errors.append(f"ajax_api: {e}")

        try:
            html_text = self._fetch_page_html()
            html_items = self._extract_items_from_html(html_text, max_results)
            if html_items:
                return html_items, "html"
            errors.append("html 返回空列表")
        except Exception as e:
            errors.append(f"html: {e}")

        raise RuntimeError("; ".join(errors) if errors else "未知抓取错误")

    def _fetch_items_from_api(self, max_results: int) -> List[Dict[str, str]]:
        req = urllib.request.Request(self._HOT_SEARCH_API_URL, headers=self._REQUEST_HEADERS)
        with urllib.request.urlopen(req, timeout=10) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            payload = json.loads(response.read().decode(charset, errors="ignore"))

        realtime = payload.get("data", {}).get("realtime") or payload.get("realtime") or []
        items: List[Dict[str, str]] = []

        for entry in realtime:
            if len(items) >= max_results:
                break

            title = (
                entry.get("word")
                or entry.get("note")
                or entry.get("title")
                or ""
            ).strip()
            if not title:
                continue

            label = (
                entry.get("label_name")
                or entry.get("icon_desc")
                or entry.get("flag_desc")
                or ""
            ).strip()
            href = (
                entry.get("word_scheme")
                or entry.get("scheme")
                or entry.get("raw_scheme")
                or ""
            ).strip()
            if href.startswith("//"):
                href = f"https:{href}"
            elif href.startswith("/"):
                href = urllib.parse.urljoin(self._HOT_SEARCH_URL, href)
            elif href and not href.startswith("http"):
                href = urllib.parse.urljoin(self._HOT_SEARCH_URL, href)

            rank = str(entry.get("rank") or len(items) + 1)
            items.append({
                "rank": rank,
                "title": title,
                "label": label,
                "href": href,
            })

        return items

    def _fetch_page_html(self) -> str:
        req = urllib.request.Request(self._HOT_SEARCH_URL, headers=self._REQUEST_HEADERS)
        with urllib.request.urlopen(req, timeout=10) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, errors="ignore")

    def _extract_items_from_html(self, page_html: str, max_results: int) -> List[Dict[str, str]]:
        items: List[Dict[str, str]] = []

        table_match = re.search(
            r'<table[^>]*>\s*<tbody>(.*?)</tbody>\s*</table>',
            page_html,
            re.DOTALL | re.IGNORECASE,
        )
        tbody_html = table_match.group(1) if table_match else page_html

        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", tbody_html, re.DOTALL | re.IGNORECASE)
        for row_html in rows:
            if len(items) >= max_results:
                break

            row_text = self._clean_html_text(row_html)
            if not row_text:
                continue

            link_match = re.search(
                r'<a[^>]+href="(?P<href>[^"]+)"[^>]*>(?P<title>.*?)</a>',
                row_html,
                re.DOTALL | re.IGNORECASE,
            )
            if not link_match:
                continue

            title = self._clean_html_text(link_match.group("title"))
            if not title or title in {"更多热搜", "查看完整热搜榜"}:
                continue

            rank_match = re.search(
                r'<td[^>]*class="td-01"[^>]*>\s*(?P<rank>\d+)\s*</td>',
                row_html,
                re.DOTALL | re.IGNORECASE,
            )
            label_match = re.search(
                r'<td[^>]*class="td-03"[^>]*>.*?(?:<span[^>]*>|<a[^>]*>)(?P<label>.*?)(?:</span>|</a>)',
                row_html,
                re.DOTALL | re.IGNORECASE,
            )

            href = html.unescape(link_match.group("href")).strip()
            if href.startswith("/"):
                href = urllib.parse.urljoin(self._HOT_SEARCH_URL, href)

            items.append({
                "rank": rank_match.group("rank") if rank_match else str(len(items) + 1),
                "title": title,
                "label": self._clean_html_text(label_match.group("label")) if label_match else "",
                "href": href,
            })

        return items

    def _clean_html_text(self, raw: str) -> str:
        text = re.sub(r"<[^>]+>", " ", raw or "")
        text = html.unescape(text)
        return re.sub(r"\s+", " ", text).strip()

    def _update_hot_topics(self, items: List[Dict[str, str]], user_id: str) -> None:
        try:
            from memory import get_memory_api

            memory_api = get_memory_api()
            topics = [item["title"] for item in items[:5] if item.get("title")]
            if topics:
                memory_api.update_hot_topics(topics, user_id)
        except Exception:
            # 热搜写入记忆失败不影响主流程
            return
