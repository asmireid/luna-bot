import os
import json
import asyncio
import warnings
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Tuple, Any

from util.Chat.tools import chat_tools

class ChatBackend(ABC):
    def __init__(self,
                context_limit: int,
                context_keep: int = 2,
                system_prompt: str = None,
                summarize_prompt: str = None,
                jailbreak_prompt: str = None,
                bot_name: str = "Luna"):
        self.context_limit = context_limit
        self.context_keep = context_keep
        self.system_prompt, self.summarize_prompt, self.jailbreak_prompt = self._load_prompts(system_prompt, summarize_prompt, jailbreak_prompt)
        self.memory = ""
        self.context: List[Dict[str, Any]] = []
        self.bot_name = bot_name

    def _load_prompt(self, prompt: str, kind: str) -> str:
        if prompt and os.path.isfile(prompt):
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
        summarize_prompt: Optional[str] = None,
        jailbreak_prompt: Optional[str] = None
    ) -> Tuple[str, str, str]:
        raw = {
            "system": system_prompt,
            "summarize": summarize_prompt,
            "jailbreak": jailbreak_prompt,
        }

        loaded = {}
        for kind, value in raw.items():
            loaded[kind] = self._load_prompt(value, kind)

        return loaded["system"], loaded["summarize"], loaded["jailbreak"]

    @abstractmethod
    async def _generate_reply(self, context: Optional[List[Dict[str, Any]]] = None, use_system_prompt: bool = True, **kwargs) -> Any:
        """Generates a reply based on the message and internal context."""
        pass

    @abstractmethod
    def _is_tool_call(self, reply_obj: Any) -> bool:
        pass

    @abstractmethod
    def _extract_tool_info(self, reply_obj: Any) -> Tuple[str, dict, Any]:
        pass

    @abstractmethod
    def _extract_text(self, reply_obj: Any) -> str:
        pass

    async def chat_stream(self, message: str, **kwargs):
        """
        An async generator that yields status updates, tool executions, and finally the text response.
        """
        tools_schema = chat_tools.get_schemas()

        print(f"Chat: received message: {message}")
        author_name = kwargs.get('author_name', 'User')
        images = kwargs.get('images', [])
        await self.add_context('user', message, author_name, images=images)
        
        timeout = kwargs.get('timeout')

        while True:
            yield {"type": "status", "content": "Generating response..."}
            
            if timeout:
                try:
                    reply_obj = await asyncio.wait_for(self._generate_reply(tools=tools_schema, **kwargs), timeout=timeout)
                except asyncio.TimeoutError:
                    print(f"Chat: Backend timeout after {timeout}s; retrying once...")
                    reply_obj = await asyncio.wait_for(self._generate_reply(tools=tools_schema, **kwargs), timeout=timeout)
            else:
                reply_obj = await self._generate_reply(tools=tools_schema, **kwargs)

            if self._is_tool_call(reply_obj):
                tool_name, tool_args, raw_part = self._extract_tool_info(reply_obj)
                
                yield {"type": "tool_start", "tool_name": tool_name, "args": tool_args}
                
                # Record model's intent to call a tool
                await self.add_context('tool_call', json.dumps(tool_args), tool_name, raw=raw_part)

                # Execute the tool, passing kwargs (which may contain the Discord ctx)
                result = await chat_tools.execute_tool(tool_name, tool_args, context_kwargs=kwargs)
                
                # Record the tool's result
                await self.add_context('tool_result', str(result), tool_name)
                
                yield {"type": "tool_end", "tool_name": tool_name, "result": result}
            else:
                reply_text = self._extract_text(reply_obj)
                await self.add_context('model', reply_text, self.bot_name)
                yield {"type": "final", "content": reply_text}
                break

    async def chat(self, message: str, **kwargs) -> str:
        """Backward compatibility for backends that don't stream to the UI."""
        reply_text = ""
        async for update in self.chat_stream(message, **kwargs):
            if update["type"] == "final":
                reply_text = update["content"]
        return reply_text
    
    async def summarize(self, context: Optional[List[Dict[str, Any]]] = None, **kwargs) -> str:
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

    async def add_context(self, role: str, content: str, name: str, images:list = None, raw: Any = None):
        if images is None:
            images = []
        print(f"Chat: adding context ({role}, {name}): {content[:50]}...")
        self.context.append({'role': role, 'content': content, 'name': name, 'images': images, 'raw': raw})
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