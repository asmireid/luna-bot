import asyncio
import io
import json
import requests

from typing import List, Dict, Optional, Tuple, Any
from PIL import Image
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

    # ------------------------------------------------------------------
    # payload helpers
    # ------------------------------------------------------------------
    _MAX_WIRE_BYTES = 10 * 1024 * 1024   # 10 MiB — safe for most proxies
    _BASE64_RATIO = 4.0 / 3.0            # raw → base64 inflates by ~33 %
    _JPEG_QUALITY = 85
    _MIN_COMPRESS_BYTES = 50 * 1024      # skip tiny images

    @staticmethod
    def _compress_for_wire(data: bytes, mime_type: str) -> tuple[bytes, str]:
        """Re-encode *data* as JPEG to shrink wire payload.  No-op for
        JPEGs and images below ``_MIN_COMPRESS_BYTES``."""
        if len(data) < GeminiBackend._MIN_COMPRESS_BYTES:
            return data, mime_type
        if mime_type and mime_type.split("/")[-1].lower() in ("jpeg", "jpg"):
            return data, mime_type
        try:
            img = Image.open(io.BytesIO(data))
            if img.mode in ("RGBA", "LA", "P"):
                img = img.convert("RGB")
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=GeminiBackend._JPEG_QUALITY)
            result = buf.getvalue()
            if len(result) < len(data):
                return result, "image/jpeg"
        except Exception:
            pass
        return data, mime_type

    @staticmethod
    def _estimate_text_wire(
        system_prompt: str | None,
        memory: str | None,
        jailbreak_prompt: str | None,
        entries: list[dict[str, Any]],
        tool_schemas: list[dict] | None,
    ) -> int:
        """Conservative estimate of how many bytes the text/JSON parts
        of the request will consume on the wire."""
        est = 0
        est += len(system_prompt or "")
        est += len(memory or "")
        est += len(jailbreak_prompt or "")
        for e in entries:
            est += len(e.get("text", ""))
            est += len(e.get("name", ""))
            est += 150  # JSON structure overhead per entry
        if tool_schemas:
            est += len(json.dumps(tool_schemas))
        est += 4096  # fixed overhead: field names, brackets, config, labels
        return est

    async def _generate_reply(self, context: Optional[List[Dict[str, Any]]] = None, use_system_prompt:bool = True, **kwargs) -> Any:
        asset_store = kwargs.get("asset_store")
        entries = await self.resolve_context_entries(context, asset_store)

        # ------------------------------------------------------------------
        # Step 1 – compress all candidate images to JPEG so we push fewer
        #          bytes through the proxy / Gemini REST API.
        # ------------------------------------------------------------------
        for e in entries:
            for img in e.get("images", []):
                data = img.get("data", b"")
                if data:
                    compressed, new_mime = self._compress_for_wire(data, img.get("mime_type", ""))
                    img["data"] = compressed
                    img["mime_type"] = new_mime

        # ------------------------------------------------------------------
        # Step 2 – estimate how much of the wire budget text will eat.
        #          Remaining budget is available for (base64-encoded) images.
        # ------------------------------------------------------------------
        tool_schemas = kwargs.get("tools")
        text_wire = self._estimate_text_wire(
            self.system_prompt, self.memory, self.jailbreak_prompt,
            entries, tool_schemas,
        )
        image_wire_budget = max(0, self._MAX_WIRE_BYTES - text_wire)

        # ------------------------------------------------------------------
        # Step 3 – walk backwards (newest first) and select images that fit
        #          in the remaining wire budget, accounting for base64 bloat.
        # ------------------------------------------------------------------
        keep_img_keys: set[tuple[int, int]] = set()
        wire_spent = 0
        total_raw_bytes = 0

        for i in range(len(entries) - 1, -1, -1):
            e = entries[i]
            if e["role"] not in ("tool_result", "user") or not e.get("images"):
                continue
            for j, img in enumerate(e["images"]):
                raw = len(img.get("data", b""))
                if raw == 0:
                    continue
                wire = int(raw * self._BASE64_RATIO)
                if wire_spent + wire <= image_wire_budget:
                    keep_img_keys.add((i, j))
                    wire_spent += wire
                    total_raw_bytes += raw
                else:
                    break
            if wire_spent >= image_wire_budget:
                break

        # ------------------------------------------------------------------
        # Step 4 – build the full prompt (same structure; uses keep_img_keys)
        # ------------------------------------------------------------------
        full_prompt: list[dict[str, Any]] = []

        if self.memory:
            full_prompt.append({
                "role": "model",
                "parts": [types.Part.from_text(text=f"Memory: {self.memory}")],
            })

        for i, e in enumerate(entries):
            role = e["role"]

            if role == "tool_call":
                part = e["raw"] if e.get("raw") else self._fallback_tool_call_part(e)
                full_prompt.append({"role": "model", "parts": [part]})

            elif role == "tool_result":
                parts: list[Any] = [
                    types.Part.from_function_response(name=e["name"], response={"result": e["text"]})
                ]
                for j, img in enumerate(e["images"]):
                    raw = len(img.get("data", b""))
                    if (i, j) in keep_img_keys:
                        parts.append(types.Part.from_bytes(data=img["data"], mime_type=img["mime_type"]))
                    else:
                        label = f"[Tool output image ({raw // 1024} KB — omitted; budget exhausted)]"
                        parts.append(types.Part.from_text(text=label))
                full_prompt.append({"role": "user", "parts": parts})

            elif role == "model":
                if e.get("raw"):
                    raw = e["raw"]
                    parts = raw if isinstance(raw, list) else [raw]
                    # strip thought parts to reduce payload size
                    parts = [p for p in parts if not getattr(p, 'thought', False)]
                else:
                    parts = [types.Part.from_text(text=e["text"])]
                if parts:
                    full_prompt.append({"role": "model", "parts": parts})

            else:  # user
                parts = [types.Part.from_text(text=f"[User: {e['name']}]\n{e['text']}")]
                for f in e["other_files"]:
                    label = f"[Attached file: {f['filename']}; asset_id={f['asset_id']}; mime_type={f['mime_type']}]"
                    parts.append(types.Part.from_text(text=label))
                for j, img in enumerate(e["images"]):
                    raw = len(img.get("data", b""))
                    if (i, j) in keep_img_keys:
                        parts.append(types.Part.from_bytes(data=img["data"], mime_type=img["mime_type"]))
                    else:
                        label = f"[Attached image ({raw // 1024} KB — omitted; budget exhausted)]"
                        parts.append(types.Part.from_text(text=label))
                full_prompt.append({"role": "user", "parts": parts})

        # ------------------------------------------------------------------
        # logging
        # ------------------------------------------------------------------
        print(
            f"Chat: {len(keep_img_keys)} images ({total_raw_bytes // 1024} KB raw, "
            f"{wire_spent // 1024} KB wire), "
            f"~{text_wire // 1024} KB text → "
            f"~{(text_wire + wire_spent) // 1024} KB total "
            f"(budget {self._MAX_WIRE_BYTES // (1024 * 1024)} MB)"
        )

        if self.jailbreak_prompt:
            full_prompt.append({
                "role": "model",
                "parts": [types.Part.from_text(text=self.jailbreak_prompt)],
            })

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
        text = reply_obj.text or ""

        # Surface safety-filter / empty-candidate information so operators
        # can distinguish "character chose silence" from "content blocked".
        if not text:
            if reply_obj.prompt_feedback:
                fb = reply_obj.prompt_feedback
                if getattr(fb, 'block_reason', None):
                    print(f"Chat: SAFETY BLOCK — reason={fb.block_reason}")
            if reply_obj.candidates:
                c = reply_obj.candidates[0]
                reason = getattr(c, 'finish_reason', None)
                if reason:
                    print(f"Chat: finish_reason={reason}")
                if not getattr(c, 'content', None) or not getattr(c.content, 'parts', None):
                    print("Chat: candidate has no content/parts — likely safety block")

        return text

    def _extract_raw(self, reply_obj: Any) -> Any:
        # Return all parts of the first candidate to preserve thoughts, text, and media
        if reply_obj.candidates and reply_obj.candidates[0].content:
            return reply_obj.candidates[0].content.parts
        return None
