import os
import json
import asyncio
import warnings
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Tuple, Any

from util.Chat.tools import chat_tools
from util.Media.types import AssetRef
from util.Chat.storage import ChatStorage

class ChatBackend(ABC):
    def __init__(self,
                context_limit: int,
                context_keep: int = 2,
                system_prompt: str = None,
                summarize_prompt: str = None,
                jailbreak_prompt: str = None,
                bot_name: str = "Luna",
                db_path: str = "chat_history.db"):
        self.context_limit = context_limit
        self.context_keep = context_keep
        self.system_prompt, self.summarize_prompt, self.jailbreak_prompt = self._load_prompts(system_prompt, summarize_prompt, jailbreak_prompt)
        self.bot_name = bot_name
        self.storage = ChatStorage(db_path)
        
        # Sync initial state from DB
        self.memory = self.storage.get_memory()
        self.context = self.storage.load_context(self.context_limit)

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
        """
        Sends the current context to the specific LLM API and returns the raw API response object.
        
        This method must handle:
        - Constructing the final prompt from the `context` history (which includes standard messages and tool calls/results).
        - Formatting and passing `kwargs.get('tools')` to the underlying API.
        - Making the actual network request or local inference call.
        
        :param context: The conversation history to send. If None, uses `self.context`.
        :param use_system_prompt: Whether to prepend the system prompt to the context.
        :param kwargs: Additional API configuration parameters (e.g., temperature, max_new_tokens, tools).
        :return: The raw response object directly from the LLM provider's client.
        """
        pass

    @abstractmethod
    def _is_tool_call(self, reply_obj: Any) -> bool:
        """
        Determines if the raw API response object represents a request to call a tool.
        
        :param reply_obj: The raw response object returned by `_generate_reply`.
        :return: True if the model wants to call a tool, False if it just returned text.
        """
        pass

    @abstractmethod
    def _extract_tool_info(self, reply_obj: Any) -> Tuple[str, dict, Any]:
        """
        Extracts tool execution details from a raw API response object that requested a tool call.
        
        :param reply_obj: The raw response object returned by `_generate_reply`.
        :return: A tuple containing:
                 1. (str) The name of the tool/function to call.
                 2. (dict) The arguments to pass to the tool.
                 3. (Any) The raw, unmodified message/part object representing the tool call intent. 
                    This is crucial to preserve provider-specific IDs (like OpenAI's tool_call_id) 
                    or signatures (like Gemini's thought_signature) so they can be injected 
                    back into the context history for the next loop iteration.
        """
        pass

    @abstractmethod
    def _extract_text(self, reply_obj: Any) -> str:
        """
        Extracts the final text content from a raw API response object.
        
        This is called when `_is_tool_call` returns False, signifying the model has finished 
        its thought process and provided a standard conversational reply.
        
        :param reply_obj: The raw response object returned by `_generate_reply`.
        :return: The string text to send back to the user.
        """
        pass

    @abstractmethod
    def _extract_raw(self, reply_obj: Any) -> Any:
        """
        Extracts the raw message/part object from a raw API response object.
        
        :param reply_obj: The raw response object returned by `_generate_reply`.
        :return: The raw message object.
        """
        pass

    async def chat_stream(self, message: str, **kwargs):
        """
        An async generator that yields status updates, tool executions, and finally the text response.
        """
        await chat_tools.ensure_ready()
        tools_schema = chat_tools.get_schemas()

        print(f"Chat: received message: {message}")
        author_name = kwargs.get('author_name', 'User')
        files = kwargs.get('files')
        if files is None:
            files = kwargs.get('images', [])
        await self.add_context('user', message, author_name, files=files)
        
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
                result_text = result.as_text()
                
                # Record the tool's result
                await self.add_context('tool_result', result_text, tool_name, files=result.files, raw=raw_part)
                
                yield {"type": "tool_end", "tool_name": tool_name, "result": result_text, "files": result.files}
            else:
                reply_text = self._extract_text(reply_obj)
                raw_part = self._extract_raw(reply_obj)
                await self.add_context('model', reply_text, self.bot_name, raw=raw_part)
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
        self.storage.set_memory(reply)
        print(f"Chat: summary updated: {self.memory}")

        return reply

    async def add_context(self, role: str, content: str, name: str, files:list = None, raw: Any = None):
        if files is None:
            files = []
        print(f"Chat: adding context ({role}, {name}): {content[:50]}...")
        
        # Save to DB
        self.storage.save_message(role, content, name, files=files, raw=raw)
        
        # Update in-memory cache
        self.context.append({'role': role, 'content': content, 'name': name, 'files': files, 'raw': raw})
        
        if len(self.context) > self.context_limit:
            print("Chat: context limit reached.")
            
            # Snapshot the context to summarize and clear the main context
            context_to_summarize = self.context[:]
            self.reset_context(self.context_keep)

            asyncio.create_task(self.summarize(context_to_summarize))

    async def resolve_context_files(self, msg: Dict[str, Any], asset_store: Any | None = None) -> List[Dict[str, Any]]:
        resolved = []
        files = msg.get('files')
        if files is None:
            files = msg.get('images', [])

        for item in files:
            if isinstance(item, AssetRef):
                if asset_store is None:
                    resolved.append({
                        'asset_id': item.asset_id,
                        'filename': item.filename,
                        'content_type': item.mime_type,
                        'kind': item.kind,
                    })
                    continue
                data = await asset_store.resolve_bytes(item.asset_id)
                resolved.append({
                    'asset_id': item.asset_id,
                    'filename': item.filename,
                    'content_type': item.mime_type,
                    'kind': item.kind,
                    'data': data,
                })
                continue

            normalized = dict(item)
            asset_id = normalized.get('asset_id')
            if asset_id and 'data' not in normalized and asset_store is not None:
                normalized['data'] = await asset_store.resolve_bytes(asset_id)
            normalized.setdefault('kind', 'image' if str(normalized.get('content_type', '')).startswith('image/') else 'file')
            resolved.append(normalized)

        return resolved
    
    def pop_context(self, index: int = 0):
        self.context.pop(index)

    def reset_context(self, keep=None):
        self.storage.clear_context(keep=keep)
        if not keep:
            self.context = []
        else:
            self.context = self.context[-keep:]
    
    def reset_memory(self):
        self.memory = ''
        self.storage.set_memory('')
