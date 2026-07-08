import base64
import mimetypes
from pathlib import Path
from .base import BaseTool, ToolResult

IMAGE_EXTENSIONS = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
                    '.gif': 'image/gif', '.webp': 'image/webp', '.bmp': 'image/bmp'}
PDF_EXTENSION = '.pdf'
MAX_IMAGE_BYTES = 20 * 1024 * 1024  # 20MB


class ReadTool(BaseTool):
    name = 'Read'
    description = (
        'Read a file from the local filesystem. Returns file contents with line numbers '
        '(cat -n format) for text files. Supports images (PNG/JPG/GIF/WebP/BMP) and PDFs. '
        'Use offset and limit for reading large text files in chunks.'
    )
    parameters = {
        'type': 'object',
        'properties': {
            'file_path': {'type': 'string', 'description': 'Absolute path to the file to read'},
            'offset': {'type': 'integer', 'description': 'Line number to start reading from (1-based)'},
            'limit': {'type': 'integer', 'description': 'Maximum number of lines to read'},
        },
        'required': ['file_path'],
    }
    permission_level = 'safe'
    is_read_only = True

    def __init__(self, max_lines: int = 2000, workdir: str = '.'):
        self._max_lines = max_lines
        self._workdir = Path(workdir).resolve()

    def execute(self, file_path: str, offset: int | None = None, limit: int | None = None,
                on_output=None) -> ToolResult:
        path = Path(file_path)
        if not path.is_absolute():
            path = self._workdir / path
        path = path.resolve()
        if not path.exists():
            return ToolResult(success=False, output='', error=f'File not found: {path}')
        if path.is_dir():
            return ToolResult(success=False, output='', error=f'Path is a directory: {path}')

        suffix = path.suffix.lower()

        # Image handling
        if suffix in IMAGE_EXTENSIONS:
            return self._read_image(path, suffix)

        # PDF handling
        if suffix == PDF_EXTENSION:
            return self._read_pdf(path)

        # Text file (default)
        return self._read_text(path, offset, limit, on_output)

    def _read_image(self, path: Path, suffix: str) -> ToolResult:
        try:
            file_bytes = path.read_bytes()
        except Exception as e:
            return ToolResult(success=False, output='', error=str(e))

        if len(file_bytes) > MAX_IMAGE_BYTES:
            return ToolResult(
                success=False, output='',
                error=f'Image too large: {len(file_bytes)} bytes (max {MAX_IMAGE_BYTES})'
            )

        media_type = IMAGE_EXTENSIONS[suffix]
        b64 = base64.b64encode(file_bytes).decode('ascii')
        size_kb = len(file_bytes) / 1024
        info = f'[Image: {path.name} | {media_type} | {size_kb:.1f} KB | {len(file_bytes)} bytes]'
        return ToolResult(
            success=True,
            output=info,
            metadata={'file_type': 'image', 'media_type': media_type,
                       'size_bytes': len(file_bytes), 'path': str(path)},
            images=[{'media_type': media_type, 'base64': b64}],
        )

    def _read_pdf(self, path: Path) -> ToolResult:
        try:
            from pypdf import PdfReader
        except ImportError:
            return ToolResult(
                success=False, output='',
                error='PDF reading requires pypdf. Install with: pip install pypdf'
            )

        try:
            reader = PdfReader(str(path))
            pages = []
            total_chars = 0
            max_chars = 100000
            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                if text:
                    pages.append(f'--- Page {i + 1} ---\n{text}')
                    total_chars += len(text)
                    if total_chars > max_chars:
                        pages.append(f'\n... [truncated, {len(reader.pages) - i - 1} pages remaining]')
                        break
            output = '\n\n'.join(pages) if pages else '(no text extracted from PDF)'
            return ToolResult(
                success=True,
                output=output,
                metadata={'file_type': 'pdf', 'pages': len(reader.pages),
                           'path': str(path), 'total_chars': total_chars},
            )
        except Exception as e:
            return ToolResult(success=False, output='', error=f'PDF read error: {e}')

    def _read_text(self, path: Path, offset: int | None, limit: int | None,
                   on_output) -> ToolResult:
        try:
            text = path.read_text(encoding='utf-8', errors='replace')
        except Exception as e:
            return ToolResult(success=False, output='', error=str(e))

        lines = text.split('\n')
        total_lines = len(lines)
        start = offset - 1 if offset else 0
        end = start + limit if limit else len(lines) if offset else self._max_lines
        selected = lines[start:end]
        if not selected:
            return ToolResult(
                success=True, output='(empty selection or file)',
                metadata={'lines': 0, 'total_lines': total_lines}
            )

        max_line = min(end, total_lines)
        width = len(str(max_line))
        output_lines = []
        for i, line in enumerate(selected):
            formatted = f'{i + start + 1:>{width}}\t{line}'
            output_lines.append(formatted)
            if on_output and total_lines > 50:
                on_output(formatted)

        output = '\n'.join(output_lines)
        truncated = ''
        if end < total_lines:
            remaining = total_lines - end
            truncated = f'\n... [truncated {remaining} lines]'

        return ToolResult(
            success=True,
            output=output + truncated,
            metadata={
                'lines': len(selected), 'total_lines': total_lines,
                'start_line': start + 1, 'end_line': min(end, total_lines),
                'path': str(path),
            },
        )
