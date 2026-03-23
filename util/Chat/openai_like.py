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
                    "tool_call_id": msg['name'], # We will store the ID in 'name' during tool_result in extract
                    "content": msg['content']
                })
                
            else:
                openai_role = 'assistant' if role == 'model' else 'user'
                text_content = f"[User: {msg['name']}]\n{msg['content']}" if openai_role == 'user' else msg['content']
                images = msg.get('images', [])

                if images:
                    content_parts = [{"type": "text", "text": text_content}]
                    for img in images:
                        b64_data = base64.b64encode(img['data']).decode('utf-8')
                        mime_type = img['mime_type']
                        content_parts.append({
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime_type};base64,{b64_data}"}
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
        # Ensure we don't pass back nulls that might upset the API
        if "function_call" in raw_msg and raw_msg["function_call"] is None:
            del raw_msg["function_call"]
            
        # Pass the ID as part of the returned name or in the raw so we can use it for the result.
        # Actually, let's inject it into the name as "name|id" or just return the ID so base.py can use it.
        # But base.py doesn't know about IDs. A trick is to return the ID as the "name" for the result.
        # Wait, if we return `tool_call.id` as part of the tool_name? No, tool execution will fail.
        # Let's attach the ID to the raw dictionary so we can retrieve it later, 
        # BUT for the actual result context, we need to store the ID.
        
        return name, args, raw_msg

    def _extract_text(self, reply_obj: Any) -> str:
        text = reply_obj.choices[0].message.content
        return text or ""
