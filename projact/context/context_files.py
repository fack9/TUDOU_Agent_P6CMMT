from pathlib import Path

def load_context_files(working_dir: Path) -> str:
    parts = []
    seen = set()
    for parent in [working_dir.resolve(), *working_dir.resolve().parents]:
        context_file = parent / 'TUDOU.md'
        if context_file.exists() and str(context_file) not in seen:
            seen.add(str(context_file))
            content = _read_file(context_file)
            if content:
                parts.append(f'<!-- {context_file} -->\n{content}')
    return '\n\n'.join(parts)

def load_memory_context(memory_dir: Path | None=None) -> str:
    if memory_dir is None or not memory_dir.exists():
        return ''
    try:
        from session.memory import MemoryManager
        mm = MemoryManager(memory_dir)
        return mm.build_context_block()
    except Exception:
        return ''

def _read_file(path: Path, max_chars: int=50000) -> str:
    try:
        text = path.read_text(encoding='utf-8', errors='replace')
        if len(text) > max_chars:
            text = text[:max_chars] + f'\n... [truncated {len(text) - max_chars} chars]'
        return text
    except Exception:
        return ''
