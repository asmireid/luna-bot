import os
import asyncio
import warnings
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Tuple

class ChatBackend(ABC):
    def __init__(self, context_limit: int, context_keep: int = 2,system_prompt: str = None, summarize_prompt: str = None):
        self.context_limit = context_limit
        self.context_keep = context_keep
        self.system_prompt, self.summarize_prompt = self._load_prompts(system_prompt, summarize_prompt)
        self.memory = ""
        self.context: List[Dict[str, str]] = []

    def _load_prompts(self, system_prompt: Optional[str], summarize_prompt: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
        if not system_prompt:
            system_prompt = "You are a helpful assistant."
        if not summarize_prompt:
            summarize_prompt = "Summarize all previous events in 100 token."

        if os.path.isfile(system_prompt):
            try:
                with open(system_prompt, 'r', encoding='utf-8') as f:
                    system_prompt = f.read()
            except Exception as e:
                warnings.warn(
                    f"Could not read system prompt file '{system_prompt}'. Using it as a raw string instead. ({e})",
                    category=RuntimeWarning,
                    stacklevel=2,
                )

        if os.path.isfile(summarize_prompt):
            try:
                with open(summarize_prompt, 'r', encoding='utf-8') as f:
                    summarize_prompt = f.read()
            except Exception as e:
                warnings.warn(
                    f"Could not read summarize prompt file '{summarize_prompt}'. Using it as a raw string instead. ({e})",
                    category=RuntimeWarning,
                    stacklevel=2,
                )
    
        return system_prompt, summarize_prompt


    @abstractmethod
    async def _generate_reply(self, context: Optional[List[Dict[str, str]]] = None, use_system_prompt: bool = True, 
**kwargs) -> str:
        """Generates a reply based on the message and internal context."""
        pass
    
    async def chat(self, message: str, **kwargs) -> str:
        print(f"Chat: Received message: {message}")
        author_name = kwargs.get('author_name', 'User')
        await self.add_context('user', message, author_name)
        
        reply = await self._generate_reply(**kwargs)
        print(f"Chat: Generated reply: {reply}")

        await self.add_context('model', reply, self.bot_name, background=True)
        return reply
    
    async def summarize(self, context: Optional[List[Dict[str, str]]] = None, **kwargs) -> str:
        print("Chat: Summarizing...")
        if context is None:
            context = self.context

        # Create a temporary context for summarization to avoid modifying the main context
        temp_context = context.copy()
        temp_context.append({'role': 'user', 'content': self.summarize_prompt, 'name': "system"})

        reply = await self._generate_reply(context=temp_context, use_system_prompt=False, **kwargs)
        
        self.memory = reply
        print(f"Chat: Summary updated: {self.memory}")
    
        return reply

    async def add_context(self, role: str, content: str, name: str, background: bool = False):
        print(f"Chat: Adding context ({role}, {name}): {content[:50]}...")
        self.context.append({'role': role, 'content': content, 'name': name})
        if len(self.context) > self.context_limit:
            print("Chat: Context limit reached.")
            
            # Snapshot the context to summarize and clear the main context
            context_to_summarize = self.context[:]
            self.reset_context()
            
            if background:
                asyncio.create_task(self.summarize(context_to_summarize))
            else:
                await self.summarize(context_to_summarize)
    
    def pop_context(self, index: int = 0):
        self.context.pop(index)

    def reset_context(self, keep=0):
        self.context = self.context[-keep:]
