"""
浏览器搜索工具 - 让企鹅能搜索信息
"""

import subprocess
import urllib.parse
from .base import Tool, ToolResult


class BrowserSearchTool(Tool):
    """浏览器搜索工具"""

    name = "browser_search"
    description = "使用浏览器搜索信息。返回搜索结果摘要。可以搜索天气、新闻、资讯等。"
    
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "搜索关键词或问题"
            },
            "reasoning": {
                "type": "string", 
                "description": "为什么进行这次搜索，帮助理解搜索目的"
            }
        },
        "required": ["query"]
    }

    def execute(self, **kwargs) -> ToolResult:
        query = kwargs.get('query', '')
        reasoning = kwargs.get('reasoning', '')
        
        if not query:
            return ToolResult(
                success=False,
                content="",
                error="搜索关键词不能为空"
            )

        try:
            # 构建搜索URL（使用DuckDuckGo，避免广告）
            encoded_query = urllib.parse.quote(query)
            search_url = f"https://duckduckgo.com/?q={encoded_query}"
            
            # 尝试用默认浏览器打开（可选）
            # subprocess.run(['open', search_url], capture_output=True)
            
            # 尝试获取搜索结果（简单抓取）
            results = self._fetch_search_results(query)
            
            if results:
                return ToolResult(
                    success=True,
                    content=f"关于「{query}」的搜索结果：\n\n{results}\n\n搜索链接: {search_url}",
                    metadata={
                        'query': query,
                        'url': search_url,
                        'reasoning': reasoning,
                    }
                )
            else:
                return ToolResult(
                    success=True,
                    content=f"已准备好搜索「{query}」，搜索结果可通过链接查看: {search_url}",
                    metadata={
                        'query': query,
                        'url': search_url,
                    }
                )

        except Exception as e:
            return ToolResult(
                success=False,
                content="",
                error=f"搜索失败: {str(e)}"
            )

    def _fetch_search_results(self, query: str) -> str:
        """尝试抓取搜索结果（简化版）"""
        try:
            import urllib.request
            import json
            
            # 使用DuckDuckGo Instant Answer API
            encoded_query = urllib.parse.quote(query)
            url = f"https://api.duckduckgo.com/?q={encoded_query}&format=json&no_html=1"
            
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode('utf-8'))
            
            results = []
            
            # 提取AbstractText
            if data.get('AbstractText'):
                results.append(f"📌 {data['AbstractText']}")
            
            # 提取RelatedTopics
            if data.get('RelatedTopics'):
                for topic in data['RelatedTopics'][:3]:
                    if topic.get('Text'):
                        results.append(f"• {topic['Text'][:200]}")
            
            # 提取答案
            if data.get('Answer'):
                results.insert(0, f"💡 {data['Answer']}")
            
            return '\n'.join(results) if results else ""

        except Exception:
            return ""
