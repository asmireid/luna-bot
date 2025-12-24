import asyncio
from openai import OpenAI
from .base import ChatBackend

class OpenAILikeBackend(ChatBackend):
    def __init__(self, api_key: str,
                context_limit: int,
                base_url: str,
                model: str,
                system_prompt: str = None,
                bot_name: str = "Luna"):
        super().__init__(context_limit, system_prompt=system_prompt)
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.bot_name = bot_name

    async def generate_reply(self, message: str, **kwargs) -> str:
        author_name = kwargs.get("author_name", "User")
        self.add_context('user', message, author_name)
        # print(self.context[-1])

        messages = []
        system_instruction = self.system_prompt
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        
        for msg in self.context:
            content = {
                'role': msg['role'],
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

        self.add_context('assistant', reply, self.bot_name)
        return reply
