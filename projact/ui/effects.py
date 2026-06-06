import sys
import random
import time
_COLORS: dict[str, str] = {'black': '\x1b[30m', 'red': '\x1b[31m', 'green': '\x1b[32m', 'yellow': '\x1b[33m', 'blue': '\x1b[34m', 'magenta': '\x1b[35m', 'cyan': '\x1b[36m', 'white': '\x1b[37m', 'bright_black': '\x1b[90m', 'bright_red': '\x1b[91m', 'bright_green': '\x1b[92m', 'bright_yellow': '\x1b[93m', 'bright_blue': '\x1b[94m', 'bright_magenta': '\x1b[95m', 'bright_cyan': '\x1b[96m', 'bright_white': '\x1b[97m', 'reset': '\x1b[0m'}

def typewriter2(text: str, char_time: float=0.0023, glitch_chars: int=1, scramble_color: str='bright_red', char_color: str='bright_green'):
    symbols = list(' ')
    scramble_code = _COLORS.get(scramble_color, _COLORS['bright_red'])
    char_code = _COLORS.get(char_color, _COLORS['bright_green'])
    reset_code = _COLORS['reset']
    glitch_time = char_time / (glitch_chars + 1)
    for char in text:
        for _ in range(glitch_chars):
            r = random.choice(symbols)
            sys.stdout.write(scramble_code + r + reset_code)
            sys.stdout.flush()
            time.sleep(glitch_time)
            sys.stdout.write('\x08')
            sys.stdout.flush()
        sys.stdout.write(char_code + char + reset_code)
        sys.stdout.flush()
        time.sleep(glitch_time)
    print()
