import asyncio
from typing import List, Dict, Optional
from openai import OpenAI
from .base import ChatBackend

class OpenAILikeBackend(ChatBackend):
    def __init__(self, api_key: str,
                context_limit: int,
                base_url: str,
                model: str,
                context_keep: int = 2,
                system_prompt: str = None,
                summarize_prompt: str = None,
                bot_name: str = "Luna"):
        super().__init__(context_limit, context_keep=context_keep, system_prompt=system_prompt, summarize_prompt=summarize_prompt, bot_name=bot_name)
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    async def _generate_reply(self, context: Optional[List[Dict[str, str]]] = None, **kwargs) -> str:
        messages = []
        system_instruction = self.system_prompt
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        
        ctx = context if context is not None else self.context
        for msg in ctx:
            role = msg['role']
            if role == 'model':
                role = 'assistant'
            content = {
                'role': role,
                'content': f"from {msg['name']}: {msg['content']}"
            }
            messages.append(content)
        # print(messages)

        max_new_tokens = kwargs.get("max_new_tokens")

        loop = asyncio.get_running_loop()
        resp = await loop.run_in_executor(
            None,
            lambda: self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_new_tokens,
            )
        )
        reply = resp.choices[0].message.content.strip()

        return reply
