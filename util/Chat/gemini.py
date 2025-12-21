import asyncio
from google import genai
from .base import ChatBackend

class GeminiBackend(ChatBackend):
    def __init__(self, api_key: str, proxy_url: str = None, model: str = "gemini-3-flash-preview", bot_name: str = "Luna"):
        super().__init__()
        http_options = {'base_url': proxy_url} if proxy_url else None
        self.client = genai.Client(api_key=api_key, http_options=http_options)
        self.model = model
        self.bot_name = bot_name

    async def generate_reply(self, message: str, **kwargs) -> str:
        author_name = kwargs.get('author_name', 'User')
        self.add_context(author_name, message)

        # Construct prompt from context
        full_prompt = ""
        for msg in self.context:
            full_prompt += f"{msg['role']}: {msg['content']}\n"
        
        loop = asyncio.get_running_loop()
        # Run synchronous SDK call in executor
        response = await loop.run_in_executor(
            None,
            lambda: self.client.models.generate_content(model=self.model, contents=full_prompt)
        )
        
        reply = response.text
        self.add_context(self.bot_name, reply)
        return reply