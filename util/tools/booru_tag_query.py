"""
Danbooru tag query tool for verifying and finding related anime-style tags.
No authentication required.
"""

import logging
import re
import aiohttp

from util.Chat.tools import chat_tools

USER_AGENT = "LunaBot/1.0 (tag-query-tool)"
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=15)
MAX_TAGS_PER_QUERY = 10  # limit how many input tags to process at once


def _split_tags(raw: str) -> list[str]:
    """Split comma/space separated tags, strip, deduplicate, keep order."""
    tags = re.split(r"[,\s]+", raw.strip())
    seen = set()
    result = []
    for t in tags:
        t = t.strip().lower().replace(" ", "_")
        if t and t not in seen:
            seen.add(t)
            result.append(t)
    return result[:MAX_TAGS_PER_QUERY]


async def _fetch_json(session: aiohttp.ClientSession, url: str, params: dict) -> dict:
    """Fetch JSON from a URL with params, with error handling."""
    headers = {"User-Agent": USER_AGENT}
    async with session.get(url, params=params, headers=headers, timeout=REQUEST_TIMEOUT) as resp:
        if resp.status == 403:
            raise RuntimeError(f"Access denied (Cloudflare block). Try again later.")
        if resp.status == 401:
            raise RuntimeError(f"Authentication required for this API.")
        if resp.status != 200:
            text = await resp.text()
            raise RuntimeError(f"HTTP {resp.status}: {text[:200]}")
        return await resp.json()


async def _danbooru_related(session: aiohttp.ClientSession, tag: str, k: int) -> list[str]:
    """Get tags that frequently co-occur with the given tag (Danbooru)."""
    url = "https://danbooru.donmai.us/related_tag.json"
    data = await _fetch_json(session, url, {"query": tag})
    related = data.get("related_tags", [])
    # Skip the first entry (it's the queried tag itself with similarity=1.0)
    results = []
    for entry in related[1:]:
        tag_info = entry.get("tag", {})
        name = tag_info.get("name", "")
        if name:
            freq = entry.get("frequency", 0)
            results.append(f"{name} (co-occurrence: {freq:.1%})")
        if len(results) >= k:
            break
    return results


async def _danbooru_search(session: aiohttp.ClientSession, tag: str, k: int) -> list[str]:
    """Search for tags matching a pattern (autocomplete-style)."""
    url = "https://danbooru.donmai.us/tags.json"
    params = {
        "search[name_or_alias_matches]": f"{tag}*",
        "search[order]": "count",
        "limit": k,
    }
    data = await _fetch_json(session, url, params)
    results = []
    if isinstance(data, list):
        for t in data:
            name = t.get("name", "")
            count = t.get("post_count", 0)
            if name:
                results.append(f"{name} ({count:,} posts)")
    return results


@chat_tools.register(
    name="booru_tag_query",
    description=(
        "Query Danbooru for tags related to the provided search terms. "
        "Returns up to K similar or matching tags for each input tag. "
        "Use this to verify tags exist, find canonical tag names, or discover co-occurring tags "
        "when building prompts for anime-style image generation models trained on Danbooru datasets. "
        "The 'related' mode finds frequently co-occurring tags. The 'search' mode does a prefix/autocomplete lookup."
    ),
    parameters={
        "type": "object",
        "properties": {
            "tags": {
                "type": "string",
                "description": "One or more tags to query, separated by commas or spaces (e.g., 'blonde_hair, blue_eyes' or 'blonde_hair blue_eyes'). Max 10 tags per call."
            },
            "mode": {
                "type": "string",
                "enum": ["related", "search"],
                "default": "related",
                "description": "'related' finds frequently co-occurring tags. 'search' does a prefix/autocomplete lookup to verify tag names exist."
            },
            "k": {
                "type": "integer",
                "default": 5,
                "description": "Max number of similar/related tags to return per input tag (1-10)."
            }
        },
        "required": ["tags"]
    },
)
async def booru_tag_query(ctx, tags: str, mode: str = "related", k: int = 5) -> str:
    k = max(1, min(k, 10))
    input_tags = _split_tags(tags)
    if not input_tags:
        return "No valid tags provided. Try something like 'blonde_hair, blue_eyes'."

    async with aiohttp.ClientSession() as session:
        lines = [f"**Danbooru tag results ({mode} mode, k={k}):**"]
        total = 0
        for tag in input_tags:
            try:
                if mode == "related":
                    results = await _danbooru_related(session, tag, k)
                else:
                    results = await _danbooru_search(session, tag, k)

                if results:
                    lines.append(f"  **{tag}**:")
                    for r in results:
                        lines.append(f"    - {r}")
                    total += 1
                else:
                    lines.append(f"  **{tag}**: no results found (tag may not exist or is uncommon)")

            except Exception as e:
                logging.error(f"booru_tag_query error for '{tag}': {e}", exc_info=True)
                lines.append(f"  **{tag}**: error - {e}")

        if total == 0:
            lines.append("No matching tags found for any query. Try different tags or a different mode.")

        return "\n".join(lines)
