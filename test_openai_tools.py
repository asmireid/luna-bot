import asyncio
from openai import AsyncOpenAI
from config.config import Config
import json

async def main():
    c = Config()
    client = AsyncOpenAI(api_key=c.openai_api_key)
    
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_server_time",
                "description": "Gets the server's current local time.",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        }
    ]
    
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "What time is it on the server?"}],
        tools=tools
    )
    
    print(response.choices[0].message.model_dump_json(indent=2))
    
if __name__ == "__main__":
    asyncio.run(main())
