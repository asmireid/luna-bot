import json
import logging
import base64
import mimetypes
from typing import Optional

from util.Chat.tools import chat_tools


@chat_tools.register(
    name="paint_list_workflows",
    description="Lists all available image generation workflows (JSON files). Use this to browse what's available, then call paint_get_details for any workflow you want to use.",
    parameters={"type": "object", "properties": {}},
)
def paint_list_workflows(ctx) -> str:
    paint_cog = ctx.bot.get_cog('Paint')
    if not paint_cog or not hasattr(paint_cog, 'backend'):
        return "Paint system is not initialized."
    
    workflows = paint_cog.backend.list_workflows()
    if not workflows:
        return "No workflows found in the comfyui_workflows folder."
        
    return f"Available workflows: {', '.join(workflows)}"


@chat_tools.register(
    name="paint_get_details",
    description=(
        "Inspect a specific generation workflow in detail. Returns: the workflow's notes/instructions "
        "(model recommendations, prompt style guidance), customizable variables with their default values, "
        "output media types, and input file slots for image-to-image/video workflows. "
        "Call this before using 'paint' with a workflow you haven't inspected yet."
    ),
    parameters={
        "type": "object",
        "properties": {
            "workflow": {
                "type": "string",
                "description": "The name of the workflow file to inspect (e.g., 'SDXL_example.json'). If omitted, uses the currently active default workflow."
            }
        }
    },
)
def paint_get_details(ctx, workflow: Optional[str] = None) -> str:
    paint_cog = ctx.bot.get_cog('Paint')
    if not paint_cog or not hasattr(paint_cog, 'backend'):
        return "Paint system is not initialized."
    
    try:
        details = paint_cog.backend.get_details(workflow=workflow)
        lines = [f"**Workflow details for '{workflow or 'default'}':**"]

        notes = details.get("notes", "")
        if notes:
            lines.append(f"\n📝 **Notes:**\n{notes}")

        variables = details.get("variables", {})
        if variables:
            lines.append(f"\n🎛️ **Variables:**\n```json\n{json.dumps(variables, indent=2)}\n```")
        else:
            lines.append("\n🎛️ **Variables:** (none — this workflow has no [VAR] nodes)")

        output_types = details.get("output_types", {})
        if output_types:
            lines.append(f"\n📤 **Output types:**\n```json\n{json.dumps(output_types, indent=2)}\n```")

        input_slots = details.get("input_slots", {})
        if input_slots:
            lines.append(f"\n📥 **Input file slots:**\n```json\n{json.dumps(input_slots, indent=2)}\n```")

        return "\n".join(lines)
    except Exception as e:
        return f"Error getting workflow details for '{workflow}': {str(e)}"


@chat_tools.register(
    name="paint",
    description=(
        "Generates an image or video using a prompt and optional workflow variables. "
        "The tool returns the generated file(s) which will be automatically attached to your response. "
        "You can specify a 'workflow' to change the style, and pass 'variables' to customize the generation process. "
        "To modify an existing image (Image-to-Image), provide the asset ID in the 'image' parameter."
    ),
    parameters={
        "type": "object",
        "properties": {
            "prompt": {"type": "string", "description": "The positive prompt describing what you want to see."},
            "negative_prompt": {"type": "string", "description": "What you want to avoid in the generation."},
            "workflow": {"type": "string", "description": "The workflow file to use (e.g., 'Anime.json'). Call paint_list_workflows to browse, then paint_get_details for that workflow's variables and notes."},
            "image": {"type": "string", "description": "Optional asset ID of an image to use as input for Image-to-Image (e.g., 'img_8a2f123')."},
            "variables": {
                "type": "object",
                "description": "Custom variables for the workflow (e.g., {'Width': 1024, 'Height': 1024, 'Seed': 12345}). See paint_get_details for available keys and notes for a specific workflow.",
                "additionalProperties": True
            }
        },
        "required": ["prompt"]
    },
)
async def paint_tool(ctx, prompt: str, negative_prompt: Optional[str] = None, workflow: Optional[str] = None, variables: Optional[dict] = None, image: Optional[str] = None) -> list:
    paint_cog = ctx.bot.get_cog('Paint')
    if not paint_cog or not hasattr(paint_cog, 'backend'):
        raise RuntimeError("Paint system is not initialized.")

    kwargs = (variables or {}).copy()
    if workflow:
        kwargs['workflow'] = workflow
    
    # Handle input image (resolved by the system to a Data URI)
    if image:
        if image.startswith("data:"):
            try:
                header, data = image.split(",", 1)
                file_data = base64.b64decode(data)
                mime_type = header.split(";")[0].split(":")[1]
                ext = mimetypes.guess_extension(mime_type) or ".png"
                
                kwargs['input_files'] = [{
                    'filename': f"input_image{ext}",
                    'data': file_data,
                    'content_type': mime_type
                }]
            except Exception as e:
                logging.error(f"Failed to process input image: {e}")
        else:
            logging.warning(f"Image parameter was not resolved to a Data URI: {image[:50]}...")
    
    # Optional: add default timeout if not provided in variables
    if 'timeout' not in kwargs:
        kwargs['timeout'] = 600

    results = await paint_cog.backend.paint(prompt, negative_prompt=negative_prompt, **kwargs)
    
    if not results:
        return "No images were generated. Check the prompt or workflow variables."
        
    return results

