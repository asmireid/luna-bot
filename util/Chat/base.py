import os
import warnings
from abc import ABC, abstractmethod
from typing import List, Dict, Optional

class ChatBackend(ABC):
    def __init__(self, context_limit: int, system_prompt: str = None):
        self.context_limit = context_limit
        self.system_prompt = self._load_system_prompt(system_prompt)
        self.context: List[Dict[str, str]] = []

    def _load_system_prompt(self, prompt: Optional[str]) -> Optional[str]:
        if not prompt:
            return None
        if os.path.isfile(prompt):
            try:
                with open(prompt, 'r', encoding='utf-8') as f:
                    return f.read()
            except Exception as e:
                warnings.warn(
                    f"Could not read system prompt file '{prompt}'. Using it as a raw string instead. ({e})",
                    category=RuntimeWarning,
                    stacklevel=2,
                )
        return prompt

    @abstractmethod
    async def generate_reply(self, message: str, **kwargs) -> str:
        """Generates a reply based on the message and internal context."""
        pass

    def add_context(self, role: str, content: str, name: str):
        self.context.append({'role': role, 'content': content, 'name': name})
        if len(self.context) > self.context_limit:
            self.context.pop(0)

    def reset_context(self):
        self.context = []
