from __future__ import annotations
from .base import BaseTool, ToolResult
from .web_utils import _fetch_cache, retry_request, html_to_markdown, check_robots_txt
try:
    import httpx
except ImportError:
    httpx = None

class WebFetchTool(BaseTool):
    name = 'WebFetch'
    description = 'Fetch content from a URL and return readable Markdown. When extract=true (AssistLLM mode), uses a secondary model to extract/refine content based on the prompt.'
    parameters = {'type': 'object', 'properties': {'url': {'type': 'string', 'description': 'The URL to fetch content from'}, 'prompt': {'type': 'string', 'description': 'What to extract from the page. Only used when extract=true.'}, 'extract': {'type': 'boolean', 'description': 'Enable AssistLLM extraction: use a secondary model to extract/refine content based on prompt. Requires web_fetch extraction config. Default false.'}}, 'required': ['url']}
    permission_level = 'safe'
    is_read_only = True

    _HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36', 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8', 'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8', 'Accept-Encoding': 'gzip, deflate, br', 'Cache-Control': 'no-cache', 'DNT': '1'}

    def __init__(self, timeout: int=30, max_chars: int=100000, llm_client=None, extraction_model: str | None=None, extraction_api_key: str | None=None, extraction_base_url: str | None=None):
        self._timeout = timeout
        self._max_chars = max_chars
        self._llm = llm_client
        self._extraction_model = extraction_model
        self._extraction_api_key = extraction_api_key
        self._extraction_base_url = extraction_base_url

    def _has_extraction_llm(self) -> bool:
        return bool(self._llm or (self._extraction_api_key and self._extraction_base_url))

    def execute(self, url: str, prompt: str | None=None, extract: bool=False, on_output=None) -> ToolResult:
        if httpx is None:
            return ToolResult(success=False, output='', error='httpx is required for web fetch')

        # --- fetch raw content (with cache) ---
        if on_output:
            on_output(f'Fetching {url}...')
        raw_content = self._fetch_raw(url)
        if raw_content is None:
            return ToolResult(success=False, output='', error=f'Fetch failed: {url}')
        if raw_content[0] == '__BLOCKED__':
            return ToolResult(success=False, output='',
                              error=f'Blocked by robots.txt: {url}')

        content, final_url, status_code, content_type, cache_hit = raw_content

        if on_output:
            if cache_hit:
                on_output(f'  (cached) {status_code} {content_type}')
            else:
                on_output(f'  {status_code} {content_type} | {len(content)} chars')

        # --- AssistLLM extraction ---
        if extract:
            if not self._has_extraction_llm():
                return ToolResult(success=False, output='',
                                  error='AssistLLM extraction is not available: web_fetch extraction model is not configured. Set tools.web_fetch.extraction_model and extraction_api_key in config.yaml.')
            if not prompt:
                return ToolResult(success=False, output='',
                                  error='extract=true requires a prompt describing what to extract.')
            if on_output:
                on_output(f'  Extracting with LLM...')
            try:
                extracted = self._extract_with_llm(content, prompt)
            except Exception as e:
                return ToolResult(success=False, output='', error=f'AssistLLM extraction failed: {e}')
            return ToolResult(success=True, output=extracted,
                              metadata={'url': final_url, 'status_code': status_code,
                                        'content_type': content_type, 'chars': len(extracted),
                                        'extracted': True, 'prompt': prompt})

        # --- default: return raw markdown (prompt is ignored) ---
        return ToolResult(success=True, output=content,
                          metadata={'url': final_url, 'status_code': status_code,
                                    'content_type': content_type, 'chars': len(content),
                                    'cache_hit': cache_hit})

    def _fetch_raw(self, url: str) -> tuple:
        """Fetch + cache raw markdown content. Returns (content, url, status, content_type, cache_hit)."""
        cache_key = f'u:{url}'
        cached = _fetch_cache.get(cache_key)
        if cached is not None:
            return cached + (True,)

        if not check_robots_txt(url):
            return ('__BLOCKED__', url, 0, '', False)

        try:
            resp = retry_request('GET', url, timeout=self._timeout,
                                 follow_redirects=True, headers=self._HEADERS)
        except Exception:
            return None

        content_type = resp.headers.get('content-type', '')
        final_url = str(resp.url)
        status_code = resp.status_code

        if 'text/html' in content_type:
            text = html_to_markdown(resp.text)
        else:
            text = resp.text

        char_count = len(text)
        if char_count > self._max_chars:
            truncated = f'\n\n... [truncated {char_count - self._max_chars} chars]'
            text = text[:self._max_chars] + truncated

        output = text.strip() or '(empty response)'
        _fetch_cache.set(cache_key, (output, final_url, status_code, content_type))
        return (output, final_url, status_code, content_type, False)

    def _extract_with_llm(self, content: str, prompt: str) -> str:
        system_msg = (
            'You are a precise information extraction tool. '
            'Extract exactly what the user asks for from the provided web page content. '
            'Return only the extracted information — no extra commentary, no markdown framing. '
            'If the requested information is not found in the content, say so clearly.'
        )
        user_msg = f'## Web Page Content\n\n{content[:50000]}\n\n## Extraction Instruction\n\n{prompt}'

        messages = [
            {'role': 'system', 'content': system_msg},
            {'role': 'user', 'content': user_msg},
        ]

        if self._extraction_api_key and self._extraction_base_url:
            return self._extract_via_httpx(messages)

        response = self._llm.complete(messages=messages, model=self._extraction_model)
        return response.content.strip()

    def _extract_via_httpx(self, messages: list[dict]) -> str:
        model = self._extraction_model or 'deepseek-chat'
        url = self._extraction_base_url.rstrip('/') + '/chat/completions'
        resp = httpx.post(
            url,
            json={'model': model, 'messages': messages, 'temperature': 0.1},
            headers={
                'Authorization': f'Bearer {self._extraction_api_key}',
                'Content-Type': 'application/json',
            },
            timeout=self._timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        return data['choices'][0]['message']['content'].strip()
