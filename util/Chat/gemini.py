import asyncio
import json
import requests

from typing import List, Dict, Optional, Tuple, Any
from google import genai
from google.genai import types
from .base import ChatBackend

class GeminiBackend(ChatBackend):
    def __init__(self, api_key: str,
                context_limit: int,
                context_keep: int = 2,
                proxy_url: str = None,
                model: str = "gemini-3-flash-preview",
                system_prompt: str = None,
                summarize_prompt: str = None,
                jailbreak_prompt: str = None,
                bot_name: str = "Luna"):
        super().__init__(context_limit, context_keep=context_keep, system_prompt=system_prompt, summarize_prompt=summarize_prompt, jailbreak_prompt=jailbreak_prompt, bot_name=bot_name)
        
        http_options = None
        if proxy_url:
            # Ensure the API key is passed correctly when using a proxy.
            # Many proxies expect the 'key' query parameter (standard Gemini API)
            # or 'Authorization: Bearer' (common for OpenAI-compatible bridges).
            headers = {}
            client_args = {}
            if api_key:
                headers['Authorization'] = f'Bearer {api_key}'
                client_args['params'] = {'key': api_key}
            
            http_options = types.HttpOptions(
                base_url=proxy_url,
                headers=headers,
                client_args=client_args
            )

        self.client = genai.Client(api_key=api_key, http_options=http_options)
        self.model = model

    async def _generate_reply(self, context: Optional[List[Dict[str, Any]]] = None, use_system_prompt:bool = True, **kwargs) -> Any:
        # Construct prompt from context
        full_prompt = []
        system_instruction = self.system_prompt
                
        # Add memory
        if self.memory:
            memory = {
                'role': 'model',
                'parts': [types.Part.from_text(text=f"Memory: {self.memory}")]
            }
            full_prompt.append(memory)

        ctx = context if context is not None else self.context
        asset_store = kwargs.get("asset_store")
        for msg in ctx:
            role = msg['role']
            
            if role == 'tool_call':
                if msg.get('raw'):
                    # Use the exact funciton call part stored in history
                    part = msg['raw']
                else:
                    # We shouldn't get here!
                    try:
                        args = json.loads(msg['content'])
                    except Exception:
                        args = {}
                    part = types.Part.from_function_call(name=msg['name'], args=args)
                content = {'role': 'model', 'parts': [part]}
                
            elif role == 'tool_result':
                part = types.Part.from_function_response(name=msg['name'], response={"result": msg['content']})
                content = {'role': 'user', 'parts': [part]}
                
            else:
                gemini_role = 'model' if role == 'model' else 'user'
                prefix = f"[User: {msg['name']}]\n" if gemini_role == 'user' else ""
                part = types.Part.from_text(text=f"{prefix}{msg['content']}")
                content = {'role': gemini_role, 'parts': [part]}

                files = await self.resolve_context_files(msg, asset_store)
                for file_info in files:
                    content_type = file_info.get('content_type') or "application/octet-stream"
                    if content_type.startswith("image/") and file_info.get('data') is not None:
                        content['parts'].append(
                            types.Part.from_bytes(
                                data=file_info['data'],
                                mime_type=content_type,
                            )
                        )
                    else:
                        filename = file_info.get('filename') or file_info.get('asset_id') or "file"
                        content['parts'].append(
                            types.Part.from_text(text=f"[Attached file: {filename} ({content_type})]")
                        )
            full_prompt.append(content)

        # Add jailbreak prompt
        if self.jailbreak_prompt:
            jb = {
                'role': "model",
                'parts': [types.Part.from_text(text=self.jailbreak_prompt)]
            }
            full_prompt.append(jb)

        loop = asyncio.get_running_loop()
        
        # Format tools for Google GenAI
        tool_schemas = kwargs.get("tools")
        genai_tools = [{"function_declarations": tool_schemas}] if tool_schemas else None

        config_kwargs = {
            "top_k": kwargs.get("top_k"),
            "top_p": kwargs.get("top_p"),
            "temperature": kwargs.get("temperature"),
            "max_output_tokens": kwargs.get("max_new_tokens"),
            "tools": genai_tools
        }
        if use_system_prompt and system_instruction:
            config_kwargs["system_instruction"] = system_instruction
            
        config = genai.types.GenerateContentConfig(**config_kwargs)

        # Run synchronous SDK call in executor
        response = await loop.run_in_executor(
            None,
            lambda: self.client.models.generate_content(model=self.model, contents=full_prompt, config=config)
        )
        
        return response

    def _is_tool_call(self, reply_obj: Any) -> bool:
        return bool(reply_obj.function_calls)

    def _extract_tool_info(self, reply_obj: Any) -> Tuple[str, dict, Any]:
        for part in reply_obj.candidates[0].content.parts:
            if part.function_call:
                fc = part.function_call
                args = fc.args if isinstance(fc.args, dict) else dict(fc.args)
                return fc.name, args, part
        return "", {}, None

    def _extract_text(self, reply_obj: Any) -> str:
        return reply_obj.text or ""
