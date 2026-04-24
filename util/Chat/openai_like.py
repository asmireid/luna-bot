import asyncio
import base64
import json
from typing import List, Dict, Optional, Tuple, Any
from openai import AsyncOpenAI
from .base import ChatBackend

class OpenAILikeBackend(ChatBackend):
    def __init__(self, api_key: str,
                context_limit: int,
                base_url: str,
                model: str,
                context_keep: int = 2,
                system_prompt: str = None,
                summarize_prompt: str = None,
                jailbreak_prompt: str = None,
                bot_name: str = "Luna"):
        super().__init__(context_limit, context_keep=context_keep, system_prompt=system_prompt, summarize_prompt=summarize_prompt, jailbreak_prompt=jailbreak_prompt, bot_name=bot_name)
        # Assuming this is standard async OpenAI usage for async context
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    async def _generate_reply(self, context: Optional[List[Dict[str, Any]]] = None, **kwargs) -> Any:
        messages = []
        system_instruction = self.system_prompt
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        
        if self.memory:
            messages.append({"role": "system", "content": f"Memory: {self.memory}"})

        ctx = context if context is not None else self.context
        asset_store = kwargs.get("asset_store")
        for msg in ctx:
            role = msg['role']
            
            if role == 'tool_call':
                if msg.get('raw'):
                    messages.append(msg['raw'])
                else:
                    # Fallback if no raw message (e.g. older history)
                    # OpenAI requires a tool_call_id, so this might fail if not present.
                    messages.append({
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [{
                            "id": "call_fallback",
                            "type": "function",
                            "function": {
                                "name": msg['name'],
                                "arguments": msg['content']
                            }
                        }]
                    })
                    
            elif role == 'tool_result':
                # OpenAI uses 'tool' role for results and requires the matching tool_call_id
                # We expect the tool_call_id to be stored in the 'name' field for this specific role 
                # (or we can extract it if we pass it properly)
                messages.append({
                    "role": "tool",
                    "tool_call_id": msg['raw']['tool_calls'][0]['id'], # We will store the ID in 'name' during tool_result in extract
                    "content": msg['content']
                })
                
            else:
                openai_role = 'assistant' if role == 'model' else 'user'
                text_content = f"[User: {msg['name']}]\n{msg['content']}" if openai_role == 'user' else msg['content']
                files = await self.resolve_context_files(msg, asset_store)

                if files:
                    content_parts = [{"type": "text", "text": text_content}]
                    for file_info in files:
                        content_type = file_info.get('content_type') or "application/octet-stream"
                        if content_type.startswith("image/") and file_info.get('data') is not None:
                            b64_data = base64.b64encode(file_info['data']).decode('utf-8')
                            content_parts.append({
                                "type": "image_url",
                                "image_url": {"url": f"data:{content_type};base64,{b64_data}"}
                            })
                        else:
                            filename = file_info.get('filename') or file_info.get('asset_id') or "file"
                            content_parts.append({
                                "type": "text",
                                "text": f"[Attached file: {filename} ({content_type})]"
                            })
                    messages.append({'role': openai_role, 'content': content_parts})
                else:
                    messages.append({'role': openai_role, 'content': text_content})
        
        if self.jailbreak_prompt:
            messages.append({"role": "system", "content": self.jailbreak_prompt})

        # Format tools for OpenAI
        tool_schemas = kwargs.get("tools")
        openai_tools = None
        if tool_schemas:
            openai_tools = [
                {
                    "type": "function",
                    "function": schema
                } for schema in tool_schemas
            ]

        # Use the async client directly since we instantiated AsyncOpenAI
        resp = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=kwargs.get("max_new_tokens"),
            temperature=kwargs.get("temperature"),
            top_p=kwargs.get("top_p"),
            tools=openai_tools
        )

        return resp

    def _is_tool_call(self, reply_obj: Any) -> bool:
        message = reply_obj.choices[0].message
        return bool(getattr(message, "tool_calls", None))

    def _extract_tool_info(self, reply_obj: Any) -> Tuple[str, dict, Any]:
        message = reply_obj.choices[0].message
        tool_call = message.tool_calls[0]
        
        name = tool_call.function.name
        try:
            args = json.loads(tool_call.function.arguments)
        except Exception:
            args = {}
            
        # The raw part needs to be the exact dictionary representation of the assistant's message
        raw_msg = message.model_dump()
        # print(raw_msg)
        # # Ensure we don't pass back nulls that might upset the API
        # if "function_call" in raw_msg and raw_msg["function_call"] is None:
        #     del raw_msg["function_call"]
        
        return name, args, raw_msg

    def _extract_text(self, reply_obj: Any) -> str:
        text = reply_obj.choices[0].message.content
        return text or ""
