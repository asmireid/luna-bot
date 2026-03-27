import asyncio
import httpx
from config.config import Config

async def main():
    c = Config()
    url = f"{c.gemini_proxy_url}/v1beta/models/{c.model}:generateContent"
    headers = {"x-goog-api-key": str(c.gemini_api_key)}
    
    print(f"DEBUG: Requesting {url}")
    print(f"DEBUG: Headers: {headers}")
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, headers=headers, json={"contents": [{"parts": [{"text": "hi"}]}]})
            print(f"DEBUG: Status Code: {resp.status_code}")
            print(f"DEBUG: Response Text: {resp.text}")
        except Exception as e:
            print(f"DEBUG: Error: {e}")
    
if __name__ == "__main__":
    asyncio.run(main())
