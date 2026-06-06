from __future__ import annotations
from .base import BaseTool, ToolResult
from .web_utils import _fetch_cache, html_to_markdown


class BrowserFetchTool(BaseTool):
    name = 'BrowserFetch'
    description = 'Fetch JavaScript-rendered pages using headless Chromium (Playwright). Use for SPA / dynamic sites where WebFetch returns empty or incomplete content. Returns Markdown.'
    parameters = {'type': 'object', 'properties': {'url': {'type': 'string', 'description': 'The URL to fetch content from'}, 'prompt': {'type': 'string', 'description': 'Optional instruction for what to extract from the page'}, 'wait_selector': {'type': 'string', 'description': 'CSS selector to wait for before extracting (e.g. ".repo-list", "article"). Helps with slow-loading SPAs.'}}, 'required': ['url']}
    permission_level = 'safe'
    is_read_only = True

    def __init__(self, timeout: int = 30, max_chars: int = 100000):
        self._timeout = timeout
        self._max_chars = max_chars

    def execute(self, url: str, prompt: str | None = None, wait_selector: str | None = None) -> ToolResult:
        try:
            from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
        except ImportError:
            return ToolResult(success=False, output='',
                              error='playwright is not installed. Run: pip install playwright && playwright install chromium')

        # --- cache ---
        cache_key = f'b:{url}'
        cached = _fetch_cache.get(cache_key)
        if cached is not None:
            content, final_url = cached
            return ToolResult(success=True, output=content,
                              metadata={'url': final_url, 'chars': len(content), 'cache_hit': True})

        # --- browser fetch ---
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                try:
                    context = browser.new_context(
                        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                        viewport={'width': 1280, 'height': 720},
                    )
                    page = context.new_page()
                    page.goto(url, wait_until='networkidle', timeout=self._timeout * 1000)

                    if wait_selector:
                        page.wait_for_selector(wait_selector, timeout=10000)

                    final_url = page.url
                    html = page.content()
                finally:
                    context.close()
                    browser.close()
        except PlaywrightTimeout:
            return ToolResult(success=False, output='',
                              error=f'Timed out waiting for page to load: {url}')
        except Exception as e:
            return ToolResult(success=False, output='',
                              error=f'Browser fetch failed: {e}')

        # --- convert ---
        text = html_to_markdown(html)
        char_count = len(text)
        if char_count > self._max_chars:
            text = text[:self._max_chars] + f'\n\n... [truncated {char_count - self._max_chars} chars]'

        output = text.strip() or '(empty response)'

        # --- cache ---
        _fetch_cache.set(cache_key, (output, final_url))

        return ToolResult(success=True, output=output,
                          metadata={'url': final_url, 'chars': len(output)})
