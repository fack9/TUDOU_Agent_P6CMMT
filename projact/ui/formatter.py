import re
from pygments import highlight
from pygments.lexers import get_lexer_by_name, guess_lexer, TextLexer
from pygments.formatters import TerminalFormatter

class Formatter:

    @staticmethod
    def highlight_code(code: str, language: str='') -> str:
        try:
            lexer = get_lexer_by_name(language) if language else guess_lexer(code)
        except Exception:
            lexer = TextLexer()
        return highlight(code, lexer, TerminalFormatter())

    @staticmethod
    def extract_code_blocks(text: str) -> list[tuple[str, str]]:
        pattern = '```(\\w*)\\n(.*?)```'
        return re.findall(pattern, text, re.DOTALL)

    @staticmethod
    def truncate(text: str, max_lines: int=2000, max_chars: int=50000) -> str:
        lines = text.split('\n')
        truncated = False
        if len(lines) > max_lines:
            lines = lines[:max_lines]
            truncated = True
        result = '\n'.join(lines)
        if len(result) > max_chars:
            result = result[:max_chars]
            truncated = True
        if truncated:
            orig_chars = len(text)
            result += f'\n\n... [truncated {orig_chars - len(result)} characters]'
        return result

    @staticmethod
    def diff_lines(old: str, new: str) -> str:
        import difflib
        diff = difflib.unified_diff(old.splitlines(keepends=True), new.splitlines(keepends=True), fromfile='old', tofile='new', lineterm='')
        return '\n'.join(diff)
