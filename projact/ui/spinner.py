import math
import sys
import time
import threading

class TUDOU_spinner:
    FRAMES = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
    DOTS = ['.  ', '.. ', '...', '...']
    MESSAGES = ['The agent is thinking for your questions...', 'The agent is analyzing for your questions...', 'The agent is processing for your questions...', 'The agent is generating for your questions...', 'The agent is reasoning for your questions...', 'The agent is computing for your questions...']
    MESSAGE_INTERVAL = 2.5

    def __init__(self, message: str='Thinking', style: str='dots', color: bool=True):
        self._base_message = message
        self.frames = self.DOTS if style == 'dots' else self.FRAMES
        self._color = color
        self._running = False
        self._thread: threading.Thread | None = None
        self._start_time = 0.0

    def start(self):
        self._running = True
        self._start_time = time.time()
        self._thread = threading.Thread(target=self._animate, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=0.5)
        if self._color:
            sys.stdout.write('\r\x1b[0K')
        else:
            sys.stdout.write('\r' + ' ' * 60 + '\r')
        sys.stdout.flush()

    @staticmethod
    def _wave_color(text: str, t: float) -> str:
        parts = []
        for i, ch in enumerate(text):
            if ch == ' ':
                parts.append(ch)
                continue
            phase = i * 0.45 + t * 2.8
            ratio = (math.sin(phase) + 1.0) / 2.0
            r = 0
            g = int(255 * ratio)
            b = int(255 * (1.0 - ratio) + 255 * ratio)
            parts.append(f'\x1b[38;2;{r};{g};{b}m{ch}')
        parts.append('\x1b[0m')
        return ''.join(parts)

    def _animate(self):
        idx = 0
        while self._running:
            elapsed = time.time() - self._start_time
            elapsed_int = int(elapsed)
            msg_idx = int(elapsed / self.MESSAGE_INTERVAL) % len(self.MESSAGES)
            message = self.MESSAGES[msg_idx]
            frame = self.frames[idx % len(self.frames)]
            display = f'  {frame} {message} (doing for {elapsed_int}s)  '
            if self._color:
                display = self._wave_color(display, elapsed)
            sys.stdout.write(f'\r{display}')
            sys.stdout.flush()
            idx += 1
            time.sleep(0.1)
