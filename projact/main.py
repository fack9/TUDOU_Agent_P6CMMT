import sys
import argparse
import random
import time
from utils.constants import VERSION

def typewriter2(text, char_time=0.2, glitch_chars=4, scramble_color='bright_red', char_color='bright_green'):
    COLORS = {'black': '\x1b[30m', 'red': '\x1b[31m', 'green': '\x1b[32m', 'yellow': '\x1b[33m', 'blue': '\x1b[34m', 'magenta': '\x1b[35m', 'cyan': '\x1b[36m', 'white': '\x1b[37m', 'bright_black': '\x1b[90m', 'bright_red': '\x1b[91m', 'bright_green': '\x1b[92m', 'bright_yellow': '\x1b[93m', 'bright_blue': '\x1b[94m', 'bright_magenta': '\x1b[95m', 'bright_cyan': '\x1b[96m', 'bright_white': '\x1b[97m', 'reset': '\x1b[0m', 'bg_red': '\x1b[41m', 'bg_green': '\x1b[42m', 'bg_yellow': '\x1b[43m', 'bg_blue': '\x1b[44m', 'bg_magenta': '\x1b[45m', 'bg_cyan': '\x1b[46m', 'bg_white': '\x1b[47m'}
    scramble_code = COLORS.get(scramble_color, COLORS['bright_red'])
    char_code = COLORS.get(char_color, COLORS['bright_green'])
    reset_code = COLORS['reset']
    symbols = list(' ')
    glitch_time = char_time / (glitch_chars + 1)
    for char in text:
        for i in range(glitch_chars):
            random_char = random.choice(symbols)
            sys.stdout.write(scramble_code + random_char + reset_code)
            sys.stdout.flush()
            time.sleep(glitch_time)
            sys.stdout.write('\x08')
            sys.stdout.flush()
        sys.stdout.write(char_code + char + reset_code)
        sys.stdout.flush()
        time.sleep(glitch_time)
    print()

def parse_args():
    parser = argparse.ArgumentParser(description='TUDOU Agent — CLI AI Agent')
    parser.add_argument('--model', '-m', help='Model to use (e.g., claude-sonnet-4-6, gpt-4o)')
    parser.add_argument('--permission-mode', choices=['plan', 'default', 'auto'], help='Permission mode')
    parser.add_argument('--version', '-v', action='store_true', help='Show version and exit')
    parser.add_argument('--prompt', '-p', help='Single prompt mode (non-interactive)')
    return parser.parse_args()

def main():
    args = parse_args()
    if args.version:
        print(f'TUDOU Agent v{VERSION}')
        return
    cli_overrides = {}
    if args.model:
        cli_overrides['model'] = args.model
    if args.permission_mode:
        cli_overrides['permission_mode'] = args.permission_mode
    from cli import TUDOU_CLI
    cli = TUDOU_CLI(cli_overrides if cli_overrides else None)
    if args.prompt:
        cli._process_input(args.prompt)
    else:
        cli.run()
if __name__ == '__main__':
    main()
