import asyncio
import sqlite3
import json
import os
from typing import List, Dict, Any, Optional
from utilities import EnhancedJSONEncoder

class ChatStorage:
    def __init__(self, db_path: str = "data/chat_history.db"):
        self.db_path = db_path
        # Ensure parent directory exists
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        self._init_db()
        self._executor = None  # lazy thread pool for writes

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role TEXT NOT NULL,
                    content TEXT,
                    name TEXT,
                    files_json TEXT,
                    raw_json TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)

    async def save_message(self, role: str, content: str, name: str, files: List = None, raw: Any = None):
        files_json = json.dumps(files, cls=EnhancedJSONEncoder) if files else None
        raw_json = None
        try:
            if raw:
                raw_json = json.dumps(raw, cls=EnhancedJSONEncoder)
        except:
            pass

        return await asyncio.to_thread(
            self._save_message_sync, role, content, name, files_json, raw_json
        )

    def _save_message_sync(self, role: str, content: str, name: str, files_json: str | None, raw_json: str | None):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO messages (role, content, name, files_json, raw_json) VALUES (?, ?, ?, ?, ?)",
                (role, content, name, files_json, raw_json)
            )

    def load_context(self, limit: int) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT role, content, name, files_json, raw_json FROM messages ORDER BY id DESC LIMIT ?",
                (limit,)
            )
            rows = cursor.fetchall()
            
            context = []
            for row in reversed(rows):
                msg = {
                    'role': row['role'],
                    'content': row['content'],
                    'name': row['name'],
                    'files': json.loads(row['files_json']) if row['files_json'] else [],
                    'raw': json.loads(row['raw_json']) if row['raw_json'] else None
                }
                context.append(msg)
            return context

    async def clear_context(self, keep: Optional[int] = None):
        return await asyncio.to_thread(self._clear_context_sync, keep)

    def _clear_context_sync(self, keep: Optional[int] = None):
        with sqlite3.connect(self.db_path) as conn:
            if keep:
                conn.execute(
                    "DELETE FROM messages WHERE id NOT IN (SELECT id FROM messages ORDER BY id DESC LIMIT ?)",
                    (keep,)
                )
            else:
                conn.execute("DELETE FROM messages")

    async def set_memory(self, memory: str):
        return await asyncio.to_thread(self._set_memory_sync, memory)

    def _set_memory_sync(self, memory: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO metadata (key, value) VALUES ('memory', ?)",
                (memory,)
            )

    def get_memory(self) -> str:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT value FROM metadata WHERE key = 'memory'")
            row = cursor.fetchone()
            return row[0] if row else ""
