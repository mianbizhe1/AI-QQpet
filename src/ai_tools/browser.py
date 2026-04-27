"""
浏览器工具
"""

import json
import subprocess
import time
import urllib.parse
from datetime import datetime
from pathlib import Path

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
            encoded_query = urllib.parse.quote(query)
            search_url = f"https://duckduckgo.com/?q={encoded_query}"
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

            encoded_query = urllib.parse.quote(query)
            url = f"https://api.duckduckgo.com/?q={encoded_query}&format=json&no_html=1"

            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode('utf-8'))

            results = []

            if data.get('AbstractText'):
                results.append(f"📌 {data['AbstractText']}")

            if data.get('RelatedTopics'):
                for topic in data['RelatedTopics'][:3]:
                    if topic.get('Text'):
                        results.append(f"• {topic['Text'][:200]}")

            if data.get('Answer'):
                results.insert(0, f"💡 {data['Answer']}")

            return '\n'.join(results) if results else ""

        except Exception:
            return ""


class BrowserTool(Tool):
    """浏览器页面操作工具"""

    name = "browser"
    description = (
        "控制 macOS 浏览器页面，支持 navigate、click、type、scroll、screenshot。"
        "默认使用 Google Chrome，也支持 Safari。"
    )

    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["navigate", "click", "type", "scroll", "screenshot"],
                "description": "要执行的浏览器操作"
            },
            "browser": {
                "type": "string",
                "description": "浏览器名称，默认 Google Chrome，可选 Safari"
            },
            "url": {
                "type": "string",
                "description": "navigate 时要打开的网址"
            },
            "selector": {
                "type": "string",
                "description": "click/type/scroll 时使用的 CSS 选择器"
            },
            "text": {
                "type": "string",
                "description": "type 时输入的文本，或 click 时用于匹配元素文本"
            },
            "x": {
                "type": "number",
                "description": "click 时的视口横坐标"
            },
            "y": {
                "type": "number",
                "description": "click 时的视口纵坐标"
            },
            "index": {
                "type": "integer",
                "description": "匹配多个元素时点击第几个，默认 0"
            },
            "clear": {
                "type": "boolean",
                "description": "type 前是否清空原值，默认 true"
            },
            "submit": {
                "type": "boolean",
                "description": "type 后是否模拟回车提交，默认 false"
            },
            "amount": {
                "type": "number",
                "description": "scroll 的滚动像素，默认 600"
            },
            "direction": {
                "type": "string",
                "enum": ["up", "down", "left", "right"],
                "description": "scroll 方向，默认 down"
            },
            "wait_seconds": {
                "type": "number",
                "description": "navigate 后等待页面加载的秒数，默认 1.5"
            },
            "description": {
                "type": "string",
                "description": "screenshot 的说明"
            }
        },
        "required": ["action"]
    }

    def __init__(self):
        super().__init__()
        self.screen_dir = Path("./screen")
        self.screen_dir.mkdir(exist_ok=True)
        self.supported_browsers = {
            "google chrome": "Google Chrome",
            "chrome": "Google Chrome",
            "safari": "Safari",
        }

    def execute(self, action: str, browser: str = "Google Chrome", **kwargs) -> ToolResult:
        if not action:
            return ToolResult(success=False, content="", error="action 不能为空")

        browser_name = self._normalize_browser(browser)
        if not browser_name:
            return ToolResult(success=False, content="", error=f"不支持的浏览器: {browser}")

        try:
            if action == "navigate":
                return self._navigate(browser_name, kwargs.get("url", ""), kwargs.get("wait_seconds", 1.5))
            if action == "click":
                return self._click(browser_name, **kwargs)
            if action == "type":
                return self._type(browser_name, **kwargs)
            if action == "scroll":
                return self._scroll(browser_name, **kwargs)
            if action == "screenshot":
                return self._screenshot(browser_name, kwargs.get("description", ""))
            return ToolResult(success=False, content="", error=f"未知 action: {action}")
        except Exception as e:
            return ToolResult(success=False, content="", error=f"浏览器操作失败: {str(e)}")

    def _navigate(self, browser: str, url: str, wait_seconds: float) -> ToolResult:
        if not url:
            return ToolResult(success=False, content="", error="navigate 需要 url")

        script = self._browser_script(
            browser,
            chrome_lines=[
                "activate",
                "if (count of windows) = 0 then make new window",
                f"set URL of active tab of front window to {self._as_string(url)}",
            ],
            safari_lines=[
                "activate",
                "if (count of documents) = 0 then make new document",
                f"set URL of front document to {self._as_string(url)}",
            ],
        )
        self._run_osascript(script, timeout=10)

        time.sleep(max(0, float(wait_seconds or 0)))
        page = self._get_page_state(browser)
        return ToolResult(
            success=True,
            content=f"已在 {browser} 打开 {url}",
            metadata=page,
        )

    def _click(self, browser: str, selector: str = "", text: str = "", x=None, y=None, index: int = 0, **kwargs) -> ToolResult:
        if selector:
            js = f"""
(() => {{
  const selector = {json.dumps(selector)};
  const textNeedle = {json.dumps(text or "")};
  const index = {int(index or 0)};
  const nodes = Array.from(document.querySelectorAll(selector));
  const filtered = textNeedle
    ? nodes.filter((node) => (node.innerText || node.textContent || "").includes(textNeedle))
    : nodes;
  const target = filtered[index];
  if (!target) {{
    return JSON.stringify({{ok:false,error:"element_not_found",matches:filtered.length}});
  }}
  target.scrollIntoView({{block:"center", inline:"center"}});
  target.click();
  return JSON.stringify({{
    ok:true,
    tag: target.tagName,
    text: (target.innerText || target.textContent || "").trim().slice(0, 120),
    href: target.href || null
  }});
}})()
""".strip()
        elif x is not None and y is not None:
            js = f"""
(() => {{
  const x = {float(x)};
  const y = {float(y)};
  const target = document.elementFromPoint(x, y);
  if (!target) {{
    return JSON.stringify({{ok:false,error:"element_not_found"}});
  }}
  target.click();
  return JSON.stringify({{
    ok:true,
    tag: target.tagName,
    text: (target.innerText || target.textContent || "").trim().slice(0, 120)
  }});
}})()
""".strip()
        else:
            return ToolResult(success=False, content="", error="click 需要 selector，或同时提供 x/y")

        result = self._run_browser_js(browser, js)
        payload = self._parse_browser_payload(result)
        if not payload.get("ok"):
            return ToolResult(success=False, content="", error=f"点击失败: {payload.get('error', 'unknown')}")

        return ToolResult(
            success=True,
            content=f"已点击元素: {payload.get('tag', 'unknown')}",
            metadata=payload,
        )

    def _type(self, browser: str, selector: str = "", text: str = "", clear: bool = True, submit: bool = False, **kwargs) -> ToolResult:
        if not selector:
            return ToolResult(success=False, content="", error="type 需要 selector")

        js = f"""
(() => {{
  const selector = {json.dumps(selector)};
  const value = {json.dumps(text or "")};
  const shouldClear = {str(bool(clear)).lower()};
  const shouldSubmit = {str(bool(submit)).lower()};
  const target = document.querySelector(selector);
  if (!target) {{
    return JSON.stringify({{ok:false,error:"element_not_found"}});
  }}
  target.scrollIntoView({{block:"center", inline:"center"}});
  target.focus();
  if ("value" in target) {{
    if (shouldClear) target.value = "";
    target.value = shouldClear ? value : `${{target.value}}${{value}}`;
  }} else if (target.isContentEditable) {{
    if (shouldClear) target.textContent = "";
    target.textContent = shouldClear ? value : `${{target.textContent || ""}}${{value}}`;
  }} else {{
    return JSON.stringify({{ok:false,error:"element_not_typable"}});
  }}
  target.dispatchEvent(new Event("input", {{ bubbles: true }}));
  target.dispatchEvent(new Event("change", {{ bubbles: true }}));
  if (shouldSubmit) {{
    target.dispatchEvent(new KeyboardEvent("keydown", {{ key: "Enter", bubbles: true }}));
    target.dispatchEvent(new KeyboardEvent("keyup", {{ key: "Enter", bubbles: true }}));
    if (target.form) target.form.requestSubmit();
  }}
  return JSON.stringify({{
    ok:true,
    tag: target.tagName,
    valueLength: ("value" in target ? target.value.length : (target.textContent || "").length)
  }});
}})()
""".strip()

        result = self._run_browser_js(browser, js)
        payload = self._parse_browser_payload(result)
        if not payload.get("ok"):
            return ToolResult(success=False, content="", error=f"输入失败: {payload.get('error', 'unknown')}")

        return ToolResult(
            success=True,
            content=f"已向 {selector} 输入文本",
            metadata=payload,
        )

    def _scroll(self, browser: str, selector: str = "", amount: float = 600, direction: str = "down", **kwargs) -> ToolResult:
        amount_value = float(amount or 600)
        dx = 0
        dy = 0
        if direction == "up":
            dy = -amount_value
        elif direction == "down":
            dy = amount_value
        elif direction == "left":
            dx = -amount_value
        elif direction == "right":
            dx = amount_value
        else:
            return ToolResult(success=False, content="", error=f"不支持的滚动方向: {direction}")

        js = f"""
(() => {{
  const selector = {json.dumps(selector or "")};
  const dx = {dx};
  const dy = {dy};
  const target = selector ? document.querySelector(selector) : window;
  if (!target) {{
    return JSON.stringify({{ok:false,error:"element_not_found"}});
  }}
  if (target === window) {{
    window.scrollBy({{ left: dx, top: dy, behavior: "smooth" }});
    return JSON.stringify({{ok:true,target:"window",scrollX:window.scrollX,scrollY:window.scrollY}});
  }}
  target.scrollBy({{ left: dx, top: dy, behavior: "smooth" }});
  return JSON.stringify({{
    ok:true,
    target: selector,
    scrollLeft: target.scrollLeft,
    scrollTop: target.scrollTop
  }});
}})()
""".strip()

        result = self._run_browser_js(browser, js)
        payload = self._parse_browser_payload(result)
        if not payload.get("ok"):
            return ToolResult(success=False, content="", error=f"滚动失败: {payload.get('error', 'unknown')}")

        return ToolResult(
            success=True,
            content=f"已在 {browser} 中滚动 {direction}",
            metadata=payload,
        )

    def _screenshot(self, browser: str, description: str) -> ToolResult:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"browser_{timestamp}.png"
        save_path = self.screen_dir / filename

        bounds_text = self._run_osascript(
            self._browser_script(
                browser,
                chrome_lines=[
                    "activate",
                    "set b to bounds of front window",
                    "return (item 1 of b as text) & \",\" & (item 2 of b as text) & \",\" & (item 3 of b as text) & \",\" & (item 4 of b as text)",
                ],
                safari_lines=[
                    "activate",
                    "set b to bounds of front window",
                    "return (item 1 of b as text) & \",\" & (item 2 of b as text) & \",\" & (item 3 of b as text) & \",\" & (item 4 of b as text)",
                ],
            ),
            timeout=10,
        )

        left, top, right, bottom = [int(part.strip()) for part in bounds_text.split(",")]
        width = max(1, right - left)
        height = max(1, bottom - top)

        capture = subprocess.run(
            ["screencapture", "-x", "-R", f"{left},{top},{width},{height}", str(save_path)],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if capture.returncode != 0 or not save_path.exists():
            return ToolResult(success=False, content="", error="浏览器截图失败")

        return ToolResult(
            success=True,
            content=f"浏览器截图已保存到 {save_path}",
            metadata={
                "browser": browser,
                "filepath": str(save_path),
                "description": description,
                "bounds": {
                    "left": left,
                    "top": top,
                    "width": width,
                    "height": height,
                },
            },
        )

    def _get_page_state(self, browser: str) -> dict:
        js = """
(() => JSON.stringify({
  ok: true,
  title: document.title || "",
  url: location.href || "",
  readyState: document.readyState || ""
}))()
""".strip()
        result = self._run_browser_js(browser, js)
        return self._parse_browser_payload(result)

    def _run_browser_js(self, browser: str, js: str) -> str:
        single_line_js = " ".join(line.strip() for line in js.splitlines() if line.strip())
        script = self._browser_script(
            browser,
            chrome_lines=[
                f"execute active tab of front window javascript {self._as_string(single_line_js)}",
            ],
            safari_lines=[
                f"do JavaScript {self._as_string(single_line_js)} in front document",
            ],
        )
        return self._run_osascript(script, timeout=20)

    def _browser_script(self, browser: str, chrome_lines: list[str], safari_lines: list[str]) -> str:
        body = chrome_lines if browser == "Google Chrome" else safari_lines
        script_lines = [f'tell application "{browser}"'] + body + ["end tell"]
        return "\n".join(script_lines)

    def _run_osascript(self, script: str, timeout: int = 10) -> str:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            message = result.stderr.strip() or result.stdout.strip() or "AppleScript 执行失败"
            raise RuntimeError(message)
        return (result.stdout or "").strip()

    def _normalize_browser(self, browser: str) -> str | None:
        if not browser:
            return "Google Chrome"
        return self.supported_browsers.get(browser.strip().lower())

    def _parse_browser_payload(self, raw: str) -> dict:
        if not raw:
            return {"ok": True}
        try:
            payload = json.loads(raw)
            if isinstance(payload, dict):
                return payload
        except json.JSONDecodeError:
            pass
        return {"ok": True, "raw": raw}

    def _as_string(self, value: str) -> str:
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
