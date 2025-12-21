import aiohttp
from .base import ChatBackend

class LocalBackend(ChatBackend):
    def __init__(self, api_url: str, system_prompt: str, bot_name: str):
        super().__init__()
        self.api_url = api_url
        self.system_prompt = system_prompt
        self.bot_name = bot_name

    async def generate_reply(self, message: str, **kwargs) -> str:
        author_name = kwargs.get('author_name', 'User')
        self.add_context(author_name, message)
        
        cleaned_sys_prompt = self.system_prompt.replace("{{char}}", self.bot_name).replace("{{user}}", author_name)
        # Prepend system prompt to the context sent to API
        api_context = [{'role': 'system', 'content': cleaned_sys_prompt}] + self.context
        
        params = kwargs.get('params', {})
        payload = params.copy()
        payload['context'] = api_context
        
        async with aiohttp.ClientSession() as session:
            async with session.post(self.api_url, json=payload) as response:
                if response.status == 200:
                    response_data = await response.json()
                    reply = response_data['response']
                    self.add_context(self.bot_name, reply)
                    return reply
                else:
                    raise Exception(f"Error fetching chat response. Status code: {response.status}")