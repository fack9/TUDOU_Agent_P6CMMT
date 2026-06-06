from __future__ import annotations
import re
from .base import BaseTool, ToolResult
from .web_utils import _search_cache, retry_request
try:
    import httpx
except ImportError:
    httpx = None
try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

class WebSearchTool(BaseTool):
    name = 'WebSearch'
    description = 'Search the web using Bing. Returns titles, URLs, and snippets for each result.'
    parameters = {'type': 'object', 'properties': {'query': {'type': 'string', 'description': 'The search query', 'minLength': 2}}, 'required': ['query']}
    permission_level = 'safe'
    is_read_only = True
    _HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36', 'Accept': 'text/html,application/xhtml+xml', 'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'}

    def __init__(self, timeout: int=20, max_results: int=10, bing_api_key: str | None=None):
        self._timeout = timeout
        self._max_results = max_results
        self._bing_api_key = bing_api_key

    def execute(self, query: str) -> ToolResult:
        if httpx is None:
            return ToolResult(success=False, output='', error='httpx is required for web search')

        # --- cache ---
        cache_key = f'q:{query}'
        cached = _search_cache.get(cache_key)
        if cached is not None:
            results = cached
            return ToolResult(success=True, output=self._format_results(results),
                              metadata={'count': len(results), 'query': query, 'cache_hit': True})

        results = []
        bs4_failed = False
        try:
            resp = retry_request('GET', 'https://www.bing.com/search',
                                 params={'q': query}, timeout=self._timeout,
                                 headers=self._HEADERS, follow_redirects=True)
            results = self._parse_results(resp.text)
            if not results:
                bs4_failed = True
        except Exception:
            bs4_failed = True

        if bs4_failed and self._bing_api_key:
            results = self._search_with_api(query)

        if not results:
            return ToolResult(success=True, output=f'No results found for: {query}',
                              metadata={'count': 0, 'query': query})

        _search_cache.set(cache_key, results)
        return ToolResult(success=True, output=self._format_results(results),
                          metadata={'count': len(results), 'query': query})

    def _search_with_api(self, query: str) -> list[dict]:
        try:
            resp = retry_request('GET', 'https://api.bing.microsoft.com/v7.0/search',
                                 params={'q': query, 'count': self._max_results,
                                         'mkt': 'zh-CN', 'textFormat': 'Raw'},
                                 headers={'Ocp-Apim-Subscription-Key': self._bing_api_key},
                                 timeout=self._timeout)
            data = resp.json()
            web_pages = data.get('webPages', {}).get('value', [])
            results = []
            for page in web_pages:
                title = page.get('name', '')
                url = page.get('url', '')
                snippet = page.get('snippet', '')
                if title and url:
                    results.append({'title': title, 'url': url, 'snippet': snippet})
                    if len(results) >= self._max_results:
                        break
            return results
        except Exception:
            return []

    @staticmethod
    def _format_results(results: list[dict]) -> str:
        return '\n\n'.join(
            f'**{r["title"]}**\n{r["snippet"]}\n{r["url"]}' for r in results
        )

    def _parse_results(self, html: str) -> list[dict]:
        if BeautifulSoup is not None:
            return self._parse_with_bs4(html)
        return self._parse_with_regex(html)

    def _parse_with_bs4(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, 'html.parser')
        results = []
        for item in soup.find_all('li', class_='b_algo'):
            title_elem = item.find('h2')
            link = title_elem.find('a') if title_elem else None
            if not link:
                continue
            url = link.get('href', '')
            title = link.get_text(strip=True)
            caption = item.find('div', class_='b_caption')
            p = caption.find('p') if caption else None
            snippet = p.get_text(strip=True) if p else ''
            if title and url:
                results.append({'title': title, 'url': url, 'snippet': snippet})
                if len(results) >= self._max_results:
                    break
        return results

    def _parse_with_regex(self, html: str) -> list[dict]:
        results = []
        html = re.sub('<script[^>]*>.*?</script>', '', html, flags=re.S | re.I)
        html = re.sub('<style[^>]*>.*?</style>', '', html, flags=re.S | re.I)
        blocks = re.findall('<li[^>]*class="[^"]*b_algo[^"]*"[^>]*>(.*?)</li>', html, re.S | re.I)
        for block in blocks:
            link_match = re.search('<h2[^>]*>.*?<a[^>]*href="(https?://[^"]+)"[^>]*>(.*?)</a>', block, re.S | re.I)
            if not link_match:
                continue
            url = link_match.group(1)
            title = re.sub('<[^>]+>', '', link_match.group(2)).strip()
            snippet_match = re.search('<p[^>]*>(.*?)</p>', block, re.S | re.I)
            snippet = ''
            if snippet_match:
                snippet = re.sub('<[^>]+>', '', snippet_match.group(1)).strip()
            if title and url:
                results.append({'title': title, 'url': url, 'snippet': snippet})
                if len(results) >= self._max_results:
                    break
        return results
