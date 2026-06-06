from __future__ import annotations
import json
import re
from enum import Enum, auto
from dataclasses import dataclass, field


class ContentType(Enum):
    JSON = auto()
    CODE = auto()
    LOG = auto()
    HTML = auto()
    TEXT = auto()


@dataclass
class ContentMeta:
    content_type: ContentType
    lines: int = 0
    depth: int = 0  # JSON nesting depth
    keys: list[str] = field(default_factory=list)  # JSON top-level keys
    has_timestamps: bool = False
    code_lines_ratio: float = 0.0


# ---------------------------------------------------------------------------
# ContentDetector
# ---------------------------------------------------------------------------

class ContentDetector:

    _LOG_PATTERNS = [
        re.compile(r'\b(ERROR|FATAL|CRITICAL)\b', re.I),
        re.compile(r'\b(WARN|WARNING)\b', re.I),
        re.compile(r'\b(INFO|DEBUG|TRACE)\b', re.I),
        re.compile(r'\b\d{4}[-/]\d{2}[-/]\d{2}\b'),  # 2024-01-15
        re.compile(r'\b\d{2}:\d{2}:\d{2}\b'),           # 14:30:00
        re.compile(r'^\s*at\s+\S+\(.*?:\d+\)'),          # stack trace lines
        re.compile(r'^\s*File\s+".*?",\s+line\s+\d+'),   # Python traceback
        re.compile(r'Traceback\s*\(most recent call last\)'),
    ]

    _CODE_KEYWORDS = re.compile(
        r'\b(def|class|import|from|return|if|else|elif|for|while|try|except|finally|'
        r'with|as|yield|async|await|lambda|function|const|let|var|export|require|'
        r'public|private|protected|static|void|int|string|fn|pub|use|mod|impl|struct|enum|'
        r'trait|type|interface|extends|implements|package)\b'
    )

    _HTML_TAGS = re.compile(r'</?[a-z][a-z0-9]*(?:\s[^>]*)?>', re.I)

    @classmethod
    def detect(cls, text: str) -> tuple[ContentType, ContentMeta]:
        text_stripped = text.strip()
        if not text_stripped:
            return ContentType.TEXT, ContentMeta(ContentType.TEXT)

        lines = text_stripped.split('\n')
        meta = ContentMeta(content_type=ContentType.TEXT, lines=len(lines))

        # --- 1. JSON ---
        json_meta = cls._try_detect_json(text_stripped)
        if json_meta:
            return ContentType.JSON, json_meta

        # --- 2. HTML ---
        tag_count = len(cls._HTML_TAGS.findall(text_stripped))
        if tag_count >= 3 and tag_count > len(lines) * 0.3:
            return ContentType.HTML, meta

        # --- 3. LOG ---
        log_score = cls._log_score(text_stripped, lines)
        if log_score >= 2:
            meta.has_timestamps = True
            return ContentType.LOG, meta

        # --- 4. CODE ---
        code_ratio = cls._code_ratio(text_stripped, lines)
        meta.code_lines_ratio = code_ratio
        if code_ratio > 0.15 and len(lines) >= 5:
            return ContentType.CODE, meta

        return ContentType.TEXT, meta

    @classmethod
    def _try_detect_json(cls, text: str) -> ContentMeta | None:
        if not (text.startswith('{') or text.startswith('[')):
            return None
        try:
            obj = json.loads(text)
            meta = ContentMeta(content_type=ContentType.JSON, lines=text.count('\n') + 1)
            meta.depth = cls._json_depth(obj)
            if isinstance(obj, dict):
                meta.keys = list(obj.keys())[:20]
            return meta
        except (json.JSONDecodeError, ValueError):
            return None

    @classmethod
    def _json_depth(cls, obj, current=0) -> int:
        if isinstance(obj, dict):
            if not obj:
                return current
            return max((cls._json_depth(v, current + 1) for v in obj.values()), default=current)
        if isinstance(obj, list):
            if not obj:
                return current
            return max((cls._json_depth(v, current + 1) for v in obj), default=current)
        return current

    @classmethod
    def _log_score(cls, text: str, lines: list[str]) -> int:
        score = 0
        sample = text[:5000]
        for pattern in cls._LOG_PATTERNS:
            if pattern.search(sample):
                score += 1
        if len(lines) >= 3:
            line_lengths = [len(line) for line in lines[:50]]
            if line_lengths:
                avg_len = sum(line_lengths) / len(line_lengths)
                if 40 < avg_len < 250:
                    score += 1
        return score

    @classmethod
    def _code_ratio(cls, text: str, lines: list[str]) -> float:
        non_empty = [l for l in lines[:200] if l.strip()]
        if not non_empty:
            return 0.0
        keyword_hits = len(cls._CODE_KEYWORDS.findall(text[:10000]))
        return keyword_hits / len(non_empty)


# ---------------------------------------------------------------------------
# SmartCrusher — JSON intelligent compression
# ---------------------------------------------------------------------------

class SmartCrusher:
    """Compress JSON to fit within max_chars while preserving structural info."""

    MAX_DEPTH = 5
    MAX_LEAF_CHARS = 200
    MAX_ARRAY_HEAD = 3
    MAX_ARRAY_TAIL = 1

    @classmethod
    def crush(cls, json_str: str, max_chars: int) -> str:
        try:
            obj = json.loads(json_str)
        except (json.JSONDecodeError, ValueError):
            return json_str[:max_chars]

        crushed = cls._crush_value(obj, depth=0, budget=max_chars)
        result = json.dumps(crushed, ensure_ascii=False, indent=None)

        if len(result) > max_chars:
            result = result[:max_chars - 30] + '\n... [further truncated]'

        return result

    @classmethod
    def _crush_value(cls, value, depth: int, budget: int):
        if depth >= cls.MAX_DEPTH:
            return cls._leaf(value)

        if isinstance(value, dict):
            return cls._crush_dict(value, depth, budget)
        if isinstance(value, list):
            return cls._crush_list(value, depth, budget)
        if isinstance(value, str):
            if len(value) > cls.MAX_LEAF_CHARS:
                return value[:cls.MAX_LEAF_CHARS] + '... [truncated]'
            return value
        return value

    @classmethod
    def _crush_dict(cls, d: dict, depth: int, budget: int) -> dict:
        result = {}
        per_key_budget = max(20, budget // max(len(d), 1))
        for k, v in d.items():
            result[k] = cls._crush_value(v, depth + 1, per_key_budget)
        return result

    @classmethod
    def _crush_list(cls, lst: list, depth: int, budget: int) -> list:
        if len(lst) <= cls.MAX_ARRAY_HEAD + cls.MAX_ARRAY_TAIL + 1:
            return [cls._crush_value(v, depth + 1, budget // max(len(lst), 1)) for v in lst]

        per_item_budget = max(30, budget // (cls.MAX_ARRAY_HEAD + cls.MAX_ARRAY_TAIL + 1))

        # Detect homogeneous structure
        if lst and cls._items_same_shape(lst):
            return cls._crush_homogeneous_array(lst, depth, per_item_budget)

        head = [cls._crush_value(v, depth + 1, per_item_budget) for v in lst[:cls.MAX_ARRAY_HEAD]]
        tail = [cls._crush_value(v, depth + 1, per_item_budget) for v in lst[-cls.MAX_ARRAY_TAIL:]]
        skipped = len(lst) - cls.MAX_ARRAY_HEAD - cls.MAX_ARRAY_TAIL
        return head + [f'... [{skipped} more items] ...'] + tail

    @classmethod
    def _crush_homogeneous_array(cls, lst: list, depth: int, budget: int) -> list:
        """For arrays where every item has identical keys, collapse to template + samples."""
        if not isinstance(lst[0], dict):
            return cls._crush_list(lst, depth, budget)

        keys = list(lst[0].keys())
        samples_head = [cls._crush_value(v, depth + 1, budget // 4) for v in lst[:cls.MAX_ARRAY_HEAD]]
        samples_tail = [cls._crush_value(v, depth + 1, budget // 4) for v in lst[-cls.MAX_ARRAY_TAIL:]]
        skipped = len(lst) - cls.MAX_ARRAY_HEAD - cls.MAX_ARRAY_TAIL
        return [
            {'_shape': keys, '_total_items': len(lst)},
            *samples_head,
            f'... [{skipped} identical items] ...',
            *samples_tail,
        ]

    @classmethod
    def _items_same_shape(cls, lst: list) -> bool:
        if not lst or not isinstance(lst[0], dict):
            return False
        ref_keys = set(lst[0].keys())
        sample = lst[1:30]
        if not sample:
            return True
        return all(isinstance(item, dict) and set(item.keys()) == ref_keys for item in sample)

    @classmethod
    def _leaf(cls, value) -> str:
        s = str(value)
        if len(s) > cls.MAX_LEAF_CHARS:
            return s[:cls.MAX_LEAF_CHARS] + '...'
        return s


# ---------------------------------------------------------------------------
# Per-type compressors
# ---------------------------------------------------------------------------

def _compress_code(text: str, max_chars: int) -> str:
    lines = text.split('\n')
    if not lines:
        return text[:max_chars]

    keep = []
    others = []
    chars_used = 0

    # Pattern for lines that should be preserved
    important = re.compile(
        r'^\s*(import|from|export|require|#include|using|package|'
        r'def |class |async def |function |fn |pub |'
        r'@\w+|//|#|/\*|\*/|"""|\'\'\'|'
        r'const |let |var |type |interface |enum |impl |struct |trait )'
    )

    for line in lines:
        stripped = line.strip()
        if not stripped:
            keep.append(line)
            chars_used += len(line) + 1
        elif important.match(stripped):
            keep.append(line)
            chars_used += len(line) + 1
        else:
            others.append(line)

    # Fill remaining budget with sampled body lines
    remaining = max_chars - chars_used
    if remaining > 0 and others:
        step = max(1, len(others) // max(1, remaining // 60))
        for i in range(0, len(others), step):
            if chars_used >= max_chars:
                break
            line = others[i]
            keep.append(line)
            chars_used += len(line) + 1

    result = '\n'.join(keep)
    if len(result) > max_chars:
        result = result[:max_chars]
    return result


def _compress_log(text: str, max_chars: int) -> str:
    lines = text.split('\n')
    if not lines:
        return text[:max_chars]

    error_pattern = re.compile(r'\b(ERROR|FATAL|CRITICAL|SEVERE)\b', re.I)
    warn_pattern = re.compile(r'\b(WARN|WARNING)\b', re.I)

    errors = []
    warns = []
    infos = []
    others = []

    for line in lines:
        if error_pattern.search(line):
            errors.append(line)
        elif warn_pattern.search(line):
            warns.append(line)
        else:
            infos.append(line)

    # Build output with priority: errors > warns > info sample
    parts = []

    if errors:
        parts.append(f'--- {len(errors)} errors ---')
        parts.extend(errors)

    if warns:
        max_warns = min(len(warns), 20)
        parts.append(f'--- {len(warns)} warnings (showing {max_warns}) ---')
        parts.extend(warns[:max_warns])
        if len(warns) > max_warns:
            parts.append(f'... and {len(warns) - max_warns} more warnings')

    if infos:
        info_budget = max_chars - sum(len(p) + 1 for p in parts)
        if info_budget > 200:
            # Deduplicate similar lines
            deduped = _dedup_lines(infos, info_budget)
            parts.append(f'--- {len(infos)} info/debug lines ({len(deduped)} unique) ---')
            parts.extend(deduped)

    result = '\n'.join(parts)
    if len(result) > max_chars:
        result = result[:max_chars]
    return result


def _compress_text(text: str, max_chars: int) -> str:
    """Smart text truncation: keep intro + conclusion + distributed samples."""
    if len(text) <= max_chars:
        return text

    paragraphs = text.split('\n\n')
    if len(paragraphs) <= 2:
        head_size = int(max_chars * 0.6)
        tail_size = int(max_chars * 0.3)
        return text[:head_size] + '\n\n... [truncated] ...\n\n' + text[-tail_size:]

    # Keep first and last paragraphs, sample middle
    head_chars = int(max_chars * 0.4)
    tail_chars = int(max_chars * 0.3)
    middle_chars = max_chars - head_chars - tail_chars

    head = paragraphs[0][:head_chars]
    tail = paragraphs[-1][:tail_chars]

    # Sample middle paragraphs evenly
    middle = paragraphs[1:-1]
    result_parts = [head]
    if middle and middle_chars > 100:
        step = max(1, len(middle) // max(1, middle_chars // 200))
        sampled = []
        chars = 0
        for i in range(0, len(middle), step):
            chunk = middle[i][:200]
            if chars + len(chunk) > middle_chars:
                break
            sampled.append(chunk)
            chars += len(chunk) + 2
        if sampled:
            result_parts.append('[...]')
            result_parts.extend(sampled)

    result_parts.append('[...]')
    result_parts.append(tail)

    result = '\n\n'.join(result_parts)
    if len(result) > max_chars:
        result = result[:max_chars]
    return result


def _dedup_lines(lines: list[str], max_chars: int) -> list[str]:
    """Collapse near-duplicate lines, keeping unique ones."""
    seen: dict[str, int] = {}
    unique: list[str] = []
    for line in lines:
        # Normalize: strip numbers, timestamps
        normalized = re.sub(r'\d+', 'N', line).strip()
        if normalized in seen:
            seen[normalized] += 1
        else:
            seen[normalized] = 1
            unique.append(line)
            if sum(len(l) + 1 for l in unique) > max_chars:
                break

    # Annotate heavily-repeated patterns
    result = []
    for line in unique:
        normalized = re.sub(r'\d+', 'N', line).strip()
        count = seen.get(normalized, 1)
        if count > 1:
            result.append(f'{line}  [repeats {count}×]')
        else:
            result.append(line)

    return result


# ---------------------------------------------------------------------------
# Main router
# ---------------------------------------------------------------------------

def compress_content(content: str, max_chars: int, content_type: ContentType | None = None) -> str:
    """Content-aware compression: detect type, apply best strategy."""
    if len(content) <= max_chars:
        return content

    if content_type is None:
        content_type, _ = ContentDetector.detect(content)

    if content_type == ContentType.JSON:
        return SmartCrusher.crush(content, max_chars)
    elif content_type == ContentType.CODE:
        return _compress_code(content, max_chars)
    elif content_type == ContentType.LOG:
        return _compress_log(content, max_chars)
    elif content_type == ContentType.HTML:
        from tools.web_utils import html_to_markdown
        md = html_to_markdown(content)
        if len(md) > max_chars:
            return _compress_text(md, max_chars)
        return md
    else:
        return _compress_text(content, max_chars)


def content_snippet(content: str, max_len: int = 200) -> str:
    """Extract a representative snippet for summary prompts. Content-type aware."""
    if not content or not content.strip():
        return ''

    ct, _ = ContentDetector.detect(content)

    if ct == ContentType.JSON:
        return _json_snippet(content, max_len)
    elif ct == ContentType.CODE:
        return _code_snippet(content, max_len)
    elif ct == ContentType.LOG:
        return _log_snippet(content, max_len)
    else:
        return content[:max_len].replace('\n', ' ')


def _json_snippet(content: str, max_len: int) -> str:
    try:
        obj = json.loads(content)
        if isinstance(obj, dict):
            keys = list(obj.keys())[:10]
            return f'JSON object with keys: {keys}'[:max_len]
        if isinstance(obj, list):
            return f'JSON array of {len(obj)} items'[:max_len]
        return str(obj)[:max_len]
    except (json.JSONDecodeError, ValueError):
        return content[:max_len]


def _code_snippet(content: str, max_len: int) -> str:
    """Extract function/class signatures as snippet."""
    lines = content.split('\n')
    sigs = []
    for line in lines[:50]:
        stripped = line.strip()
        if re.match(r'^\s*(def |class |async def |function |fn |pub |import |export |const |let )', line):
            sigs.append(stripped[:120])
    if sigs:
        return '; '.join(sigs)[:max_len]
    return content[:max_len].replace('\n', ' ')


def _log_snippet(content: str, max_len: int) -> str:
    """Extract error lines as log snippet."""
    lines = content.split('\n')
    errors = [l.strip() for l in lines[:100] if re.search(r'\b(ERROR|FATAL|CRITICAL)\b', l, re.I)]
    if errors:
        return ' | '.join(e[:150] for e in errors[:3])[:max_len]
    return content[:max_len].replace('\n', ' ')
