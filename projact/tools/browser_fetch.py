from __future__ import annotations
import sys
from pathlib import Path
from .base import BaseTool, ToolResult
from .web_utils import _fetch_cache, html_to_markdown


def _find_bundled_chromium() -> str | None:
    """Find the bundled Chromium headless-shell executable."""
    exe_name = 'chrome-headless-shell.exe'
    search_dirs = []

    # PyInstaller bundle
    if getattr(sys, 'frozen', False):
        search_dirs.append(Path(sys._MEIPASS) / 'browser' / 'chrome-headless-shell-win64')

    # Source tree
    search_dirs.append(Path(__file__).resolve().parent.parent.parent / 'browser' / 'chrome-headless-shell-win64')

    for d in search_dirs:
        exe = d / exe_name
        if exe.exists():
            return str(exe)
    return None


class BrowserFetchTool(BaseTool):
    name = 'BrowserFetch'
    description = 'Fetch JavaScript-rendered pages using headless Chromium (Playwright). Use for SPA / dynamic sites where WebFetch returns empty or incomplete content. Returns Markdown.'
    parameters = {'type': 'object', 'properties': {'url': {'type': 'string', 'description': 'The URL to fetch content from'}, 'prompt': {'type': 'string', 'description': 'Optional instruction for what to extract from the page'}, 'wait_selector': {'type': 'string', 'description': 'CSS selector to wait for before extracting (e.g. ".repo-list", "article"). Helps with slow-loading SPAs.'}}, 'required': ['url']}
    permission_level = 'safe'
    is_read_only = True

    def __init__(self, timeout: int = 30, max_chars: int = 100000):
        self._timeout = timeout
        self._max_chars = max_chars

    def execute(self, url: str, prompt: str | None = None, wait_selector: str | None = None, on_output=None) -> ToolResult:
        try:
            from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
        except ImportError:
            return ToolResult(success=False, output='',
                              error='playwright is not installed. Run: pip install playwright')

        # --- cache ---
        cache_key = f'b:{url}'
        cached = _fetch_cache.get(cache_key)
        if cached is not None:
            content, final_url = cached
            if on_output:
                on_output(f'Browser fetch (cached): {url}')
            return ToolResult(success=True, output=content,
                              metadata={'url': final_url, 'chars': len(content), 'cache_hit': True})

        # --- browser fetch ---
        if on_output:
            on_output(f'Launching headless browser...')
        chromium_exe = _find_bundled_chromium()
        try:
            with sync_playwright() as p:
                launch_kwargs = {'headless': True}
                if chromium_exe:
                    launch_kwargs['executable_path'] = chromium_exe
                if on_output:
                    on_output(f'  Loading {url}...')
                browser = p.chromium.launch(**launch_kwargs)
                try:
                    context = browser.new_context(
                        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                        viewport={'width': 1280, 'height': 720},
                    )
                    page = context.new_page()
                    page.goto(url, wait_until='networkidle', timeout=self._timeout * 1000)

                    if wait_selector:
                        if on_output:
                            on_output(f'  Waiting for selector: {wait_selector}')
                        page.wait_for_selector(wait_selector, timeout=10000)

                    final_url = page.url
                    if on_output:
                        on_output(f'  Page loaded: {final_url} | Extracting content...')
                    html = page.content()
                finally:
                    context.close()
                    browser.close()
                    if on_output:
                        on_output(f'  Browser closed')
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
