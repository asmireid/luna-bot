import os
import asyncio
import warnings
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Tuple

class ChatBackend(ABC):
    def __init__(self,
                context_limit: int,
                context_keep: int = 2,
                system_prompt: str = None,
                summarize_prompt: str = None,
                bot_name: str = "Luna"):
        self.context_limit = context_limit
        self.context_keep = context_keep
        self.system_prompt, self.summarize_prompt = self._load_prompts(system_prompt, summarize_prompt)
        self.memory = ""
        self.context: List[Dict[str, str]] = []
        self.bot_name = bot_name

    def _load_prompt(self, prompt: str, kind: str) -> str:
        if os.path.isfile(prompt):
            try:
                with open(prompt, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception as e:
                warnings.warn(
                    f"Could not read {kind} prompt file '{prompt}'. Using it as a raw string instead. ({e})",
                    category=RuntimeWarning,
                    stacklevel=2,
                )
        return prompt

    def _load_prompts(
        self,
        system_prompt: Optional[str] = None,
        summarize_prompt: Optional[str] = None
    ) -> Tuple[str, str]:
        raw = {
            "system": system_prompt,
            "summarize": summarize_prompt,
        }

        loaded = {}
        for kind, value in raw.items():
            loaded[kind] = self._load_prompt(value, kind)

        return loaded["system"], loaded["summarize"]

    @abstractmethod
    async def _generate_reply(self, context: Optional[List[Dict[str, str]]] = None, use_system_prompt: bool = True, **kwargs) -> str:
        """Generates a reply based on the message and internal context."""
        pass
    
    async def chat(self, message: str, **kwargs) -> str:
        # print(f"Chat: received message: {message}")
        author_name = kwargs.get('author_name', 'User')
        images = kwargs.get('images', [])
        await self.add_context('user', message, author_name,images=images)
        
        reply = await self._generate_reply(**kwargs)

        await self.add_context('model', reply, self.bot_name)
        return reply
    
    async def summarize(self, context: Optional[List[Dict[str, str]]] = None, **kwargs) -> str:
        print("Chat: summarizing...")
        if context is None:
            context = self.context

        # Create a temporary context for summarization to avoid modifying the main context
        temp_context = context.copy()
        temp_context.append({'role': 'user', 'content': self.summarize_prompt, 'name': "system"})

        reply = await self._generate_reply(context=temp_context, use_system_prompt=False, **kwargs)
        
        self.memory = reply
        print(f"Chat: summary updated: {self.memory}")

        return reply

    async def add_context(self, role: str, content: str, name: str, images:list = []):
        # print(f"Chat: adding context ({role}, {name}): {content[:50]}...")
        self.context.append({'role': role, 'content': content, 'name': name, 'images': images})
        if len(self.context) > self.context_limit:
            print("Chat: context limit reached.")
            
            # Snapshot the context to summarize and clear the main context
            context_to_summarize = self.context[:]
            self.reset_context(self.context_keep)

            asyncio.create_task(self.summarize(context_to_summarize))
    
    def pop_context(self, index: int = 0):
        self.context.pop(index)

    def reset_context(self, keep=None):
        if not keep:
            self.context = []
        else:
            self.context = self.context[-keep:]
    
    def reset_memory(self):
        self.memory = ''