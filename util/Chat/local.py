import aiohttp
from typing import List, Dict, Optional
from .base import ChatBackend

class LocalBackend(ChatBackend):
    def __init__(self, api_url: str,
                context_limit: int,
                system_prompt: str = None,
                bot_name: str = "Luna"):
        super().__init__(context_limit, system_prompt=system_prompt)
        self.api_url = api_url
        self.bot_name = bot_name

    async def _generate_reply(self, context: Optional[List[Dict[str, str]]] = None, **kwargs) -> str:
        # author_name = kwargs.get('author_name', 'User')
        # self.add_context('user', message, author_name)

        system_instruction = self.system_prompt

        api_context = []
        if system_instruction:
            cleaned_sys_prompt = (system_instruction
                                .replace("{{char}}", self.bot_name)
                                .replace("{{user}}", author_name))
            api_context.append({'role': 'system', 'content': cleaned_sys_prompt})

        ctx = context if context is not None else self.context
        for msg in ctx:
            content = {
                'role': msg['role'],
                'content': f"from {msg['name']}: {msg['content']}"
            }
            api_context.append(content)
        
        params = kwargs.get('params', {})
        payload = params.copy()
        payload['context'] = api_context
        
        async with aiohttp.ClientSession() as session:
            async with session.post(self.api_url, json=payload) as response:
                if response.status == 200:
                    response_data = await response.json()
                    reply = response_data['response']
                    # self.add_context('assistant', reply, self.bot_name)
                    return reply
                else:
                    raise Exception(f"Error fetching chat response. Status code: {response.status}")