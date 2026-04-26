from ddgs import DDGS
from util.Chat.tools import chat_tools
import logging

@chat_tools.register(
    name="web_search",
    description="Search the web for real-time information, facts, images, or videos. Returns a list of results with titles and links.",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string", 
                "description": "The search query to look up."
            },
            "type": {
                "type": "string", 
                "enum": ["text", "images", "videos", "news"], 
                "default": "text",
                "description": "The type of search to perform. Use 'text' for general facts, 'images' for pictures, 'videos' for clips, and 'news' for current events."
            },
            "max_results": {
                "type": "integer",
                "default": 5,
                "description": "The maximum number of results to return (default 5, max 10)."
            }
        },
        "required": ["query"]
    }
)
async def web_search(query: str, type: str = "text", max_results: int = 5):
    """
    Performs a web search using the DDGS (Dux Distributed Global Search) library.
    Returns a formatted string of results suitable for an LLM to process.
    """
    max_results = min(max_results, 10)  # Cap results to avoid context bloat
    
    try:
        results = []
        with DDGS() as ddgs:
            if type == "images":
                # Returns: [{'title': ..., 'image': ..., 'thumbnail': ..., 'url': ..., 'height': ..., 'width': ..., 'source': ...}, ...]
                raw_results = ddgs.images(query, max_results=max_results)
                for r in raw_results:
                    results.append(f"Image: {r.get('title')} - Link: {r.get('image')} (Source: {r.get('url')})")
            
            elif type == "videos":
                # Returns: [{'content': ..., 'description': ..., 'duration': ..., 'embed_html': ..., 'embed_url': ..., 'images': ..., 'provider': ..., 'published': ..., 'publisher': ..., 'title': ..., 'uploader': ..., 'url': ...}, ...]
                raw_results = ddgs.videos(query, max_results=max_results)
                for r in raw_results:
                    results.append(f"Video: {r.get('title')} - Link: {r.get('url')} (Duration: {r.get('duration')})")
            
            elif type == "news":
                # Returns: [{'date': ..., 'title': ..., 'body': ..., 'url': ..., 'image': ..., 'source': ...}, ...]
                raw_results = ddgs.news(query, max_results=max_results)
                for r in raw_results:
                    results.append(f"News: {r.get('title')} ({r.get('date')}) - {r.get('body')} - Link: {r.get('url')}")
            
            else: # default text
                # Returns: [{'title': ..., 'href': ..., 'body': ...}, ...]
                raw_results = ddgs.text(query, max_results=max_results)
                for r in raw_results:
                    results.append(f"Result: {r.get('title')} - {r.get('body')} - Link: {r.get('href')}")

        if not results:
            return f"No {type} results found for '{query}'."

        return "\n".join(results)

    except Exception as e:
        logging.error(f"Web search error: {e}", exc_info=True)
        return f"Error performing web search: {str(e)}"
