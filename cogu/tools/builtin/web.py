import json
from urllib.request import urlopen, Request
from urllib.parse import urlencode, quote_plus
from urllib.error import URLError

from cogu.tools.base import FunctionTool, ToolRegistry, ToolCapability


def _web_search(query: str, num: int = 10) -> str:
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        req = Request(url, headers=headers)
        with urlopen(req, timeout=15) as resp:
            from html.parser import HTMLParser

            class ResultParser(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.results = []
                    self.current = {}
                    self.in_result = False
                    self.in_link = False
                    self.in_snippet = False
                    self.capture = ""

                def handle_starttag(self, tag, attrs):
                    a = dict(attrs)
                    if tag == "a" and "result__a" in a.get("class", ""):
                        self.in_result = True
                        self.in_link = True
                        self.current = {"title": "", "url": "", "snippet": ""}
                    elif tag == "a" and "result__snippet" in a.get("class", ""):
                        self.in_snippet = True

                def handle_data(self, data):
                    if self.in_link:
                        self.current["title"] += data
                    if self.in_snippet:
                        self.current["snippet"] += data

                def handle_endtag(self, tag):
                    if tag == "a" and self.in_link:
                        self.in_link = False
                    if tag == "a" and self.in_snippet:
                        self.in_snippet = False
                        self.results.append(self.current)
                        self.current = {}

            html = resp.read().decode("utf-8", errors="replace")
            parser = ResultParser()
            parser.feed(html)
            lines = []
            for i, r in enumerate(parser.results[:num], 1):
                lines.append(f"{i}. {r['title'].strip()}\n   {r['snippet'].strip()}")
            if not lines:
                return f"No results found for: {query}"
            return "\n\n".join(lines)
    except Exception as e:
        return f"Search error: {e}"


def _web_fetch(url: str, extract_text: bool = True) -> str:
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        req = Request(url, headers=headers)
        with urlopen(req, timeout=30) as resp:
            content = resp.read().decode("utf-8", errors="replace")
            if extract_text:
                import re
                content = re.sub(r"<script[^>]*>.*?</script>", "", content, flags=re.DOTALL)
                content = re.sub(r"<style[^>]*>.*?</style>", "", content, flags=re.DOTALL)
                content = re.sub(r"<[^>]+>", " ", content)
                content = re.sub(r"\s+", " ", content).strip()
            if len(content) > 8000:
                content = content[:8000] + "\n\n[truncated]"
            return content
    except URLError as e:
        return f"Fetch error: {e}"
    except Exception as e:
        return f"Error: {e}"


def register_web_tools(registry: ToolRegistry):
    registry.register(FunctionTool(_web_search, name="web_search", description="Search the web using DuckDuckGo. Returns top results with title and snippet.").with_capability(ToolCapability.NETWORK).with_group("web"))
    registry.register(FunctionTool(_web_fetch, name="web_fetch", description="Fetch and extract text content from a URL.").with_capability(ToolCapability.NETWORK).with_group("web"))
