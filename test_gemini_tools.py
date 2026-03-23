import asyncio
from google import genai
from google.genai import types
from config.config import Config
import json

async def main():
    c = Config()
    client = genai.Client(api_key=c.gemini_api_key, http_options={'base_url': c.gemini_proxy_url} if c.gemini_proxy_url else None)
    
    tool = {
        "function_declarations": [
            {
                "name": "get_server_time",
                "description": "Gets the server's current local time."
            }
        ]
    }
    
    response = client.models.generate_content(
        model=c.model,
        contents="What time is it on the server?",
        config=types.GenerateContentConfig(tools=[tool], temperature=0)
    )
    
    print(response.candidates[0].content.parts[0].model_dump_json(indent=2))
    
if __name__ == "__main__":
    asyncio.run(main())
