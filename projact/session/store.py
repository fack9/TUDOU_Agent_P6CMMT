import json
import sqlite3
import time
from pathlib import Path
from typing import Any

class SessionStore:

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute('\n                CREATE TABLE IF NOT EXISTS conversations (\n                    id TEXT PRIMARY KEY,\n                    created_at REAL,\n                    model TEXT,\n                    summary TEXT\n                )\n            ')
            conn.execute('\n                CREATE TABLE IF NOT EXISTS messages (\n                    id INTEGER PRIMARY KEY AUTOINCREMENT,\n                    conv_id TEXT,\n                    role TEXT,\n                    content TEXT,\n                    timestamp REAL,\n                    FOREIGN KEY (conv_id) REFERENCES conversations(id)\n                )\n            ')
            conn.execute('\n                CREATE TABLE IF NOT EXISTS checkpoints (\n                    id INTEGER PRIMARY KEY AUTOINCREMENT,\n                    conv_id TEXT,\n                    iteration INTEGER,\n                    messages_json TEXT,\n                    timestamp REAL\n                )\n            ')
            conn.commit()

    def save_checkpoint(self, conv_id: str, iteration: int, messages: list[dict]):
        """Save a recoverable checkpoint snapshot of the conversation state."""
        data = json.dumps(messages, ensure_ascii=False)
        with sqlite3.connect(str(self.db_path)) as conn:
            # Keep only the last 3 checkpoints per conversation
            conn.execute(
                'DELETE FROM checkpoints WHERE conv_id = ? AND id NOT IN '
                '(SELECT id FROM checkpoints WHERE conv_id = ? ORDER BY id DESC LIMIT 2)',
                (conv_id, conv_id))
            conn.execute(
                'INSERT INTO checkpoints (conv_id, iteration, messages_json, timestamp) '
                'VALUES (?, ?, ?, ?)',
                (conv_id, iteration, data, time.time()))
            conn.commit()

    def load_checkpoint(self, conv_id: str) -> tuple[int, list[dict]] | None:
        """Load the most recent checkpoint for a conversation. Returns (iteration, messages) or None."""
        with sqlite3.connect(str(self.db_path)) as conn:
            row = conn.execute(
                'SELECT iteration, messages_json FROM checkpoints WHERE conv_id = ? '
                'ORDER BY id DESC LIMIT 1', (conv_id,)
            ).fetchone()
        if row:
            return (row[0], json.loads(row[1]))
        return None

    def delete_checkpoints(self, conv_id: str):
        """Remove all checkpoints for a conversation (after successful completion or abandon)."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute('DELETE FROM checkpoints WHERE conv_id = ?', (conv_id,))
            conn.commit()

    def save_message(self, conv_id: str, role: str, content: str):
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute('INSERT INTO messages (conv_id, role, content, timestamp) VALUES (?, ?, ?, ?)', (conv_id, role, content, time.time()))
            conn.commit()

    def load_messages(self, conv_id: str) -> list[dict]:
        with sqlite3.connect(str(self.db_path)) as conn:
            rows = conn.execute('SELECT role, content FROM messages WHERE conv_id = ? ORDER BY id', (conv_id,)).fetchall()
        return [{'role': r, 'content': c} for r, c in rows]

    def get_conversations(self) -> list[dict]:
        with sqlite3.connect(str(self.db_path)) as conn:
            rows = conn.execute('SELECT id, created_at, model, summary FROM conversations ORDER BY created_at DESC').fetchall()
        return [{'id': r[0], 'created_at': r[1], 'model': r[2], 'summary': r[3]} for r in rows]

    def create_conversation(self, conv_id: str, model: str='') -> str:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute('INSERT OR IGNORE INTO conversations (id, created_at, model) VALUES (?, ?, ?)', (conv_id, time.time(), model))
            conn.commit()
        return conv_id

    def update_summary(self, conv_id: str, summary: str):
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute('UPDATE conversations SET summary = ? WHERE id = ?', (summary, conv_id))
            conn.commit()

    def delete_all_conversations(self):
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute('DELETE FROM messages')
            conn.execute('DELETE FROM conversations')
            conn.commit()

    def delete_conversation(self, conv_id: str):
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute('DELETE FROM messages WHERE conv_id = ?', (conv_id,))
            conn.execute('DELETE FROM conversations WHERE id = ?', (conv_id,))
            conn.commit()
