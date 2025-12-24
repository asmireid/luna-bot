import asyncio
from google import genai
from .base import ChatBackend

class GeminiBackend(ChatBackend):
    def __init__(self, api_key: str,
                context_limit: int,
                proxy_url: str = None,
                model: str = "gemini-3-flash-preview",
                system_prompt: str = None,
                bot_name: str = "Luna"):
        super().__init__(context_limit, system_prompt=system_prompt)
        http_options = {'base_url': proxy_url} if proxy_url else None
        self.client = genai.Client(api_key=api_key, http_options=http_options)
        self.model = model
        self.bot_name = bot_name

    async def generate_reply(self, message: str, **kwargs) -> str:
        author_name = kwargs.get('author_name', 'User')
        self.add_context('user', message, author_name)

        # Construct prompt from context
        full_prompt = []
        system_instruction = self.system_prompt
        
        for msg in self.context:
            content = {
                'role': msg['role'],
                'parts': [{"text": f"from {msg['name']}: {msg['content']}"}]
            }
            full_prompt.append(content)
        
        loop = asyncio.get_running_loop()
        
        config = genai.types.GenerateContentConfig(system_instruction=system_instruction) if system_instruction else None

        # Run synchronous SDK call in executor
        response = await loop.run_in_executor(
            None,
            lambda: self.client.models.generate_content(model=self.model, contents=full_prompt, config=config)
        )
        
        reply = response.text
        self.add_context('model', reply, self.bot_name)
        return reply
