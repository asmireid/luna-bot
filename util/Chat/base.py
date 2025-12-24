import os
from abc import ABC, abstractmethod
from typing import List, Dict, Optional

class ChatBackend(ABC):
    def __init__(self, system_prompt: str = None):
        self._system_prompt = self._load_system_prompt(system_prompt)
        self.context: List[Dict[str, str]] = []
        if self._system_prompt:
            self.add_context('system', self._system_prompt)

    def _load_system_prompt(self, prompt: Optional[str]) -> Optional[str]:
        if not prompt:
            return None
        
        if os.path.isfile(prompt):
            try:
                with open(prompt, 'r', encoding='utf-8') as f:
                    return f.read()
            except Exception as e:
                print(f"Warning: Could not read system prompt file '{prompt}'. Using it as a raw string. Error: {e}")
        
        return prompt

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
        if self._system_prompt:
            self.add_context('system', self._system_prompt)