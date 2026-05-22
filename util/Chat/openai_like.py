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
                bot_name: str = "Luna",
                db_path: str = "chat_history.db"):
        super().__init__(context_limit, context_keep=context_keep, system_prompt=system_prompt, summarize_prompt=summarize_prompt, jailbreak_prompt=jailbreak_prompt, bot_name=bot_name, db_path=db_path)
        # Assuming this is standard async OpenAI usage for async context
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    async def _generate_reply(self, context: Optional[List[Dict[str, Any]]] = None, **kwargs) -> Any:
        asset_store = kwargs.get("asset_store")
        entries = await self.resolve_context_entries(context, asset_store)

        messages: list[dict[str, Any]] = []

        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        if self.memory:
            messages.append({"role": "system", "content": f"Memory: {self.memory}"})

        for e in entries:
            role = e["role"]

            if role == "tool_call":
                raw = e.get("raw")
                if isinstance(raw, dict) and raw.get("tool_calls"):
                    messages.append(raw)
                else:
                    messages.append({
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [{
                            "id": "call_fallback",
                            "type": "function",
                            "function": {"name": e["name"], "arguments": e["text"]},
                        }],
                    })

            elif role == "tool_result":
                raw = e.get("raw")
                tool_call_id = "call_fallback"
                if isinstance(raw, dict) and raw.get("tool_calls"):
                    tool_call_id = raw["tool_calls"][0]["id"]

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": e["text"],
                })

                # OpenAI tool-role messages can't carry images; emit a user follow-up
                if e["images"]:
                    image_parts: list[dict[str, Any]] = [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{img['mime_type']};base64,{base64.b64encode(img['data']).decode('utf-8')}"},
                        }
                        for img in e["images"]
                    ]
                    messages.append({
                        "role": "user",
                        "content": [{"type": "text", "text": "Visual output from the tool:"}] + image_parts,
                    })

            elif role == "model":
                if isinstance(e.get("raw"), dict):
                    messages.append(e["raw"])
                else:
                    messages.append({"role": "assistant", "content": e["text"]})

            else:  # user
                text = f"[User: {e['name']}]\n{e['text']}"
                if e["images"] or e["other_files"]:
                    parts: list[dict[str, Any]] = [{"type": "text", "text": text}]
                    for f in e["other_files"]:
                        parts.append({
                            "type": "text",
                            "text": f"[Attached file: {f['filename']}; asset_id={f['asset_id']}; mime_type={f['mime_type']}]",
                        })
                    for img in e["images"]:
                        parts.append({
                            "type": "image_url",
                            "image_url": {"url": f"data:{img['mime_type']};base64,{base64.b64encode(img['data']).decode('utf-8')}"},
                        })
                    messages.append({"role": "user", "content": parts})
                else:
                    messages.append({"role": "user", "content": text})

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
        raw_response = await self.client.chat.completions.with_raw_response.create(
            model=self.model,
            messages=messages,
            max_tokens=kwargs.get("max_new_tokens"),
            temperature=kwargs.get("temperature"),
            top_p=kwargs.get("top_p"),
            tools=openai_tools
        )
        
        # Capture raw text BEFORE parsing to ensure we have it for reasoning_content extraction
        raw_text = raw_response.text
        raw_json = {}
        try:
            raw_json = json.loads(raw_text)
        except Exception:
            raw_json = {}

        parsed = raw_response.parse()
        
        return {
            "parsed": parsed,
            "raw_json": raw_json,
        }

    def _is_tool_call(self, reply_obj: Any) -> bool:
        message = reply_obj["parsed"].choices[0].message
        return bool(getattr(message, "tool_calls", None))

    def _extract_tool_info(self, reply_obj: Any) -> Tuple[str, dict, Any]:
        message = reply_obj["parsed"].choices[0].message
        tool_call = message.tool_calls[0]
        
        name = tool_call.function.name
        try:
            args = json.loads(tool_call.function.arguments)
        except Exception:
            args = {}
            
        raw_msg = self._extract_raw(reply_obj)
        
        return name, args, raw_msg

    def _extract_text(self, reply_obj: Any) -> str:
        text = reply_obj["parsed"].choices[0].message.content
        return text or ""

    def _extract_raw(self, reply_obj: Any) -> Any:
        message = reply_obj["parsed"].choices[0].message
        
        # Try to get the message from raw_json to preserve non-standard fields like reasoning_content
        raw_msg = (
            reply_obj.get("raw_json", {})
            .get("choices", [{}])[0]
            .get("message")
        )
        
        if not raw_msg:
            # Fallback to model_dump and manually add reasoning_content if it exists as an attribute
            raw_msg = message.model_dump()
            if hasattr(message, "reasoning_content") and message.reasoning_content:
                raw_msg["reasoning_content"] = message.reasoning_content
            # Some providers might use 'thought'
            if hasattr(message, "thought") and message.thought:
                raw_msg["thought"] = message.thought
        
        # Ensure content is present (even if None) as required by some APIs
        if "content" not in raw_msg:
            raw_msg["content"] = message.content

        return raw_msg
