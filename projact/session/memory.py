import re
import yaml
from datetime import datetime
from pathlib import Path
FRONTMATTER_RE = re.compile('^---\\s*\\n(.*?)\\n---\\s*\\n?', re.DOTALL)

class MemoryManager:

    def __init__(self, memory_dir: Path):
        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self.memory_dir / 'MEMORY.md'

    def load_index(self) -> str:
        if self._index_path.exists():
            return self._index_path.read_text(encoding='utf-8', errors='replace')
        return ''

    def add_to_index(self, title: str, filename: str, hook: str):
        lines = self.load_index().splitlines()
        entry = f'- [{title}]({filename}) — {hook}'
        if entry not in lines:
            lines.append(entry)
        self._index_path.write_text('\n'.join(lines).strip() + '\n', encoding='utf-8')

    def remove_from_index(self, filename: str):
        lines = self.load_index().splitlines()
        filtered = [l for l in lines if f']({filename})' not in l]
        self._index_path.write_text('\n'.join(filtered).strip() + '\n', encoding='utf-8')

    def save(self, name: str, description: str, content: str, memory_type: str='project'):
        date_str = datetime.now().strftime('%Y%m%d')
        slug = name.lower().replace(' ', '_').replace('/', '_')
        filename = f'{date_str}_{slug}.md'
        filepath = self.memory_dir / filename
        frontmatter = {'name': name, 'description': description, 'type': memory_type}
        yaml_str = yaml.dump(frontmatter, allow_unicode=True, sort_keys=False).strip()
        filepath.write_text(f'---\n{yaml_str}\n---\n\n{content}\n', encoding='utf-8')
        return filename

    def load(self, filename: str) -> dict | None:
        filepath = self.memory_dir / filename
        if not filepath.exists():
            return None
        try:
            text = filepath.read_text(encoding='utf-8', errors='replace')
        except Exception:
            return None
        fm = {}
        body = text
        match = FRONTMATTER_RE.match(text)
        if match:
            try:
                fm = yaml.safe_load(match.group(1)) or {}
            except yaml.YAMLError:
                pass
            body = text[match.end():].strip()
        return {'name': fm.get('name', ''), 'description': fm.get('description', ''), 'type': fm.get('type', 'project'), 'content': body}

    def delete(self, filename: str) -> bool:
        filepath = self.memory_dir / filename
        if filepath.exists():
            filepath.unlink()
            return True
        return False

    def list_files(self) -> list[Path]:
        return sorted([p for p in self.memory_dir.glob('*.md') if p.name != 'MEMORY.md'], reverse=True)

    def load_all(self) -> list[dict]:
        results = []
        for f in self.list_files():
            mem = self.load(f.name)
            if mem:
                mem['_filename'] = f.name
                results.append(mem)
        return results

    def build_context_block(self) -> str:
        index = self.load_index()
        if not index.strip():
            return ''
        lines = [index.strip()]
        recent = self.list_files()[:5]
        for f in recent:
            mem = self.load(f.name)
            if mem:
                snippet = mem['content'][:300]
                lines.append(f'\n<!-- {f.name} -->\n{snippet}')
        return '\n'.join(lines)
