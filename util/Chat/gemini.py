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
                bot_name: str = "Luna",
                db_path: str = "data/chat_history.db"):
        super().__init__(context_limit, context_keep=context_keep, system_prompt=system_prompt, summarize_prompt=summarize_prompt, jailbreak_prompt=jailbreak_prompt, bot_name=bot_name, db_path=db_path)
        
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
        asset_store = kwargs.get("asset_store")
        entries = await self.resolve_context_entries(context, asset_store)

        full_prompt: list[dict[str, Any]] = []

        if self.memory:
            full_prompt.append({
                "role": "model",
                "parts": [types.Part.from_text(text=f"Memory: {self.memory}")],
            })

        for e in entries:
            role = e["role"]

            if role == "tool_call":
                part = e["raw"] if e.get("raw") else self._fallback_tool_call_part(e)
                full_prompt.append({"role": "model", "parts": [part]})

            elif role == "tool_result":
                parts: list[Any] = [
                    types.Part.from_function_response(name=e["name"], response={"result": e["text"]})
                ]
                for img in e["images"]:
                    parts.append(types.Part.from_bytes(data=img["data"], mime_type=img["mime_type"]))
                full_prompt.append({"role": "user", "parts": parts})

            elif role == "model":
                if e.get("raw"):
                    raw = e["raw"]
                    parts = raw if isinstance(raw, list) else [raw]
                else:
                    parts = [types.Part.from_text(text=e["text"])]
                full_prompt.append({"role": "model", "parts": parts})

            else:  # user
                parts = [types.Part.from_text(text=f"[User: {e['name']}]\n{e['text']}")]
                for f in e["other_files"]:
                    label = f"[Attached file: {f['filename']}; asset_id={f['asset_id']}; mime_type={f['mime_type']}]"
                    parts.append(types.Part.from_text(text=label))
                for img in e["images"]:
                    parts.append(types.Part.from_bytes(data=img["data"], mime_type=img["mime_type"]))
                full_prompt.append({"role": "user", "parts": parts})

        if self.jailbreak_prompt:
            full_prompt.append({
                "role": "model",
                "parts": [types.Part.from_text(text=self.jailbreak_prompt)],
            })

        tool_schemas = kwargs.get("tools")
        genai_tools = [{"function_declarations": tool_schemas}] if tool_schemas else None

        config_kwargs = {
            "top_k": kwargs.get("top_k"),
            "top_p": kwargs.get("top_p"),
            "temperature": kwargs.get("temperature"),
            "max_output_tokens": kwargs.get("max_new_tokens"),
            "tools": genai_tools,
        }
        if use_system_prompt and self.system_prompt:
            config_kwargs["system_instruction"] = self.system_prompt

        config = genai.types.GenerateContentConfig(**config_kwargs)

        # print(full_prompt)
        return await self.client.aio.models.generate_content(
            model=self.model, contents=full_prompt, config=config
        )

    @staticmethod
    def _fallback_tool_call_part(msg: dict[str, Any]) -> Any:
        try:
            args = json.loads(msg["content"])
        except Exception:
            args = {}
        return types.Part.from_function_call(name=msg["name"], args=args)

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

    def _extract_raw(self, reply_obj: Any) -> Any:
        # Return all parts of the first candidate to preserve thoughts, text, and media
        if reply_obj.candidates and reply_obj.candidates[0].content:
            return reply_obj.candidates[0].content.parts
        return None
