from __future__ import annotations
import time
import re
try:
    import httpx
except ImportError:
    httpx = None
try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

# ---------------------------------------------------------------------------
# TTLCache -- simple in-memory TTL cache
# ---------------------------------------------------------------------------

class TTLCache:
    """Simple dict-based TTL cache. Not thread-safe (tools run sequentially)."""

    def __init__(self, ttl: int = 900):
        self._ttl = ttl
        self._store: dict[str, tuple[float, object]] = {}

    def get(self, key: str) -> object | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        expiry, value = entry
        if time.time() < expiry:
            return value
        del self._store[key]
        return None

    def set(self, key: str, value: object, ttl: int | None = None):
        ttl = ttl if ttl is not None else self._ttl
        self._store[key] = (time.time() + ttl, value)

    def clear(self):
        self._store.clear()

# Module-level cache instances (15-min TTL for web content)
_fetch_cache = TTLCache(ttl=900)
_search_cache = TTLCache(ttl=900)

# ---------------------------------------------------------------------------
# retry_request -- exponential-backoff HTTP retry
# ---------------------------------------------------------------------------

_RETRY_STATUSES = {429, 502, 503, 504}
_MAX_RETRIES = 3


def retry_request(method: str, url: str, max_retries: int = _MAX_RETRIES, **kwargs):
    """HTTP request with exponential-backoff retry on transient errors."""
    if httpx is None:
        raise RuntimeError('httpx is required for web requests')

    last_error = None
    for attempt in range(max_retries):
        try:
            resp = httpx.request(method, url, **kwargs)
            if resp.status_code in _RETRY_STATUSES and attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            resp.raise_for_status()
            return resp
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.RemoteProtocolError) as e:
            last_error = e
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise
    raise last_error  # pragma: no cover

# ---------------------------------------------------------------------------
# html_to_markdown -- BS4-based HTML→Markdown converter
# ---------------------------------------------------------------------------

def _node_to_md(node) -> str:
    """Recursively convert a BS4 node (Tag or NavigableString) to Markdown."""
    # -- text node --
    if isinstance(node, str):
        return str(node)

    # -- non-element guard --
    if not hasattr(node, 'name') or node.name is None:
        return ''.join(_node_to_md(c) for c in node.children) if hasattr(node, 'children') else ''

    tag = node.name

    # Elements to skip entirely
    if tag in ('script', 'style', 'nav', 'footer', 'header', 'aside', 'head',
               'noscript', 'iframe', 'form', 'button', 'input', 'select',
               'textarea', 'label', 'fieldset', 'legend'):
        return ''

    # Process children recursively
    child_md = ''.join(_node_to_md(c) for c in node.children)

    # -- headings --
    if tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
        level = int(tag[1])
        return f'{"#" * level} {child_md.strip()}\n\n'

    # -- paragraphs --
    if tag == 'p':
        return f'{child_md.strip()}\n\n'

    # -- block containers --
    if tag in ('div', 'section', 'article', 'main', 'figure', 'figcaption',
               'details', 'summary', 'dialog'):
        return f'{child_md}\n'

    # -- line break & horizontal rule --
    if tag == 'br':
        return '\n'
    if tag == 'hr':
        return '---\n\n'

    # -- inline formatting --
    if tag in ('strong', 'b'):
        return f'**{child_md}**'
    if tag in ('em', 'i'):
        return f'*{child_md}*'
    if tag in ('u', 'ins'):
        return f'<u>{child_md}</u>'
    if tag in ('del', 's', 'strike'):
        return f'~~{child_md}~~'

    # -- inline code --
    if tag == 'code':
        if node.parent and node.parent.name == 'pre':
            return child_md
        return f'`{child_md}`'

    # -- code block --
    if tag == 'pre':
        code_text = child_md.strip()
        lang = ''
        code_el = node.find('code')
        if code_el and code_el.get('class'):
            m = re.search(r'language-(\w+)', ' '.join(code_el.get('class')))
            if m:
                lang = m.group(1)
        return f'```{lang}\n{code_text}\n```\n\n'

    # -- links --
    if tag == 'a':
        href = node.get('href', '')
        text = child_md.strip() or href
        if href and not href.startswith('#'):
            return f'[{text}]({href})'
        return text

    # -- images --
    if tag == 'img':
        src = node.get('src', '')
        alt = node.get('alt', '')
        return f'![{alt}]({src})' if src else ''

    # -- list items --
    if tag == 'li':
        parent_tag = node.parent.name if node.parent else 'ul'
        marker = '1.' if parent_tag == 'ol' else '-'
        return f'{marker} {child_md.strip()}\n'

    # -- list containers --
    if tag in ('ul', 'ol'):
        return f'{child_md}\n'

    # -- blockquote --
    if tag == 'blockquote':
        quoted = '\n'.join(f'> {line}' for line in child_md.strip().split('\n'))
        return f'{quoted}\n\n'

    # -- tables --
    if tag == 'table':
        return _convert_table(node)

    # -- span / unknown -- pass through children --
    return child_md


def _convert_table(el) -> str:
    rows = el.find_all('tr')
    if not rows:
        return ''
    lines = []
    for i, tr in enumerate(rows):
        cells = tr.find_all(['th', 'td'])
        cell_texts = [c.get_text(strip=True) for c in cells]
        lines.append('| ' + ' | '.join(cell_texts) + ' |')
        if i == 0 and tr.find('th'):
            lines.append('| ' + ' | '.join('---' for _ in cells) + ' |')
    return '\n'.join(lines) + '\n\n'


def html_to_markdown(html: str) -> str:
    """Convert HTML to Markdown, preserving structure for LLM consumption."""
    if BeautifulSoup is None:
        text = re.sub('<[^>]+>', '', html)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    soup = BeautifulSoup(html, 'html.parser')

    for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
        tag.decompose()

    body = soup.body if soup.body else soup
    md = _node_to_md(body)

    # Normalise whitespace
    md = re.sub(r'\n{3,}', '\n\n', md)
    return md.strip()

# ---------------------------------------------------------------------------
# robots.txt check
# ---------------------------------------------------------------------------

_robots_cache: dict[str, tuple[float, str | None]] = {}
_ROBOTS_TTL = 3600


def check_robots_txt(url: str, user_agent: str = 'TUDOU_Agent') -> bool:
    """Check robots.txt before fetching *url*. Returns True if allowed.

    Caches robots.txt per domain for 1 hour. Fail-open: if robots.txt
    cannot be fetched the URL is assumed allowed.
    """
    import urllib.parse
    parsed = urllib.parse.urlparse(url)
    domain = f'{parsed.scheme}://{parsed.netloc}'
    path = parsed.path or '/'

    # --- cache lookup ---
    entry = _robots_cache.get(domain)
    if entry is not None:
        expiry, content = entry
        if time.time() < expiry:
            if content is None:
                return True
            return _is_path_allowed(content, path, user_agent)
        del _robots_cache[domain]

    # --- fetch robots.txt ---
    robots_url = f'{domain}/robots.txt'
    content = None
    try:
        resp = httpx.get(robots_url, timeout=5, follow_redirects=True,
                         headers={'User-Agent': user_agent})
        if resp.status_code == 200:
            content = resp.text
    except Exception:
        content = None

    _robots_cache[domain] = (time.time() + _ROBOTS_TTL, content)
    if content is None:
        return True
    return _is_path_allowed(content, path, user_agent)


def _is_path_allowed(robots_content: str, path: str, user_agent: str) -> bool:
    """Parse robots.txt and decide whether *path* is allowed."""
    lines = robots_content.splitlines()
    current_agent = None
    rules: list[tuple[str, str]] = []  # (directive, value)

    for raw in lines:
        line = raw.split('#', 1)[0].strip()
        if not line:
            continue
        parts = line.split(':', 1)
        if len(parts) != 2:
            continue
        directive = parts[0].strip().lower()
        value = parts[1].strip()

        if directive == 'user-agent':
            current_agent = value.lower()
        elif current_agent and directive in ('disallow', 'allow'):
            if current_agent == '*' or current_agent == user_agent.lower():
                rules.append((directive, value))

    # Standard: last matching rule wins. Empty value means "everything".
    allowed = True
    for directive, rule_path in rules:
        if not rule_path:
            # robots.txt spec: empty Disallow = allow all; empty Allow = nothing
            allowed = (directive == 'disallow')
        elif path.startswith(rule_path):
            allowed = (directive == 'allow')
    return allowed
