from abc import ABC, abstractmethod
from typing import List, Dict

class ChatBackend(ABC):
    def __init__(self):
        self.context: List[Dict[str, str]] = []

    @abstractmethod
    async def generate_reply(self, message: str, **kwargs) -> str:
        """Generates a reply based on the message and internal context."""
        pass

    def add_context(self, role: str, content: str):
        self.context.append({'role': role, 'content': content})
        if len(self.context) > 20:
            self.context.pop(0)

    def reset_context(self):
        self.context = []