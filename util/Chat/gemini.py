import asyncio
import requests

from typing import List, Dict, Optional
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
                bot_name: str = "Luna"):
        super().__init__(context_limit, context_keep=context_keep, system_prompt=system_prompt, summarize_prompt=summarize_prompt, bot_name=bot_name)
        http_options = {'base_url': proxy_url} if proxy_url else None
        self.client = genai.Client(api_key=api_key, http_options=http_options)
        self.model = model

    async def _generate_reply(self, context: Optional[List[Dict[str, str]]] = None, use_system_prompt:bool = True, **kwargs) -> str:
        # Construct prompt from context
        full_prompt = []
        system_instruction = self.system_prompt
        
        ctx = context if context is not None else self.context
        for msg in ctx:
            content = {
                'role': msg['role'],
                'parts': [types.Part(text=f"from {msg['name']}: {msg['content']}")]
            }

            images = msg.get('images', [])
            for image in images:
                content['parts'].append(
                    types.Part.from_bytes(
                            data=image['data'],
                            mime_type=image['mime_type'],
                        ),
                )
            full_prompt.append(content)

            print(content)
        
        # Add memory
        if self.memory:
            memory = {
                'role': 'model',
                'parts': [{"text":f"Memory: {self.memory}"}]
            }
            full_prompt.append(memory)
        

        loop = asyncio.get_running_loop()
        config = genai.types.GenerateContentConfig(system_instruction=system_instruction) if use_system_prompt and system_instruction else None

        # Run synchronous SDK call in executor
        response = await loop.run_in_executor(
            None,
            lambda: self.client.models.generate_content(model=self.model, contents=full_prompt, config=config)
        )
        
        reply = response.text
        return reply
