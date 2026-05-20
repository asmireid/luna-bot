import json
import logging
import base64
import mimetypes
from typing import Optional

from util.Chat.tools import chat_tools


@chat_tools.register(
    name="paint_list_workflows",
    description="Lists all available image generation workflows (JSON files). Use this to see what styles or techniques are available.",
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
    name="paint_list_variables",
    description="Lists customizable variables for a specific workflow. Use this to find out what parameters (like 'Width', 'Height', 'Steps', 'Seed', etc.) can be adjusted for a given workflow.",
    parameters={
        "type": "object",
        "properties": {
            "workflow": {
                "type": "string",
                "description": "The name of the workflow file to inspect (e.g., 'SDXL_ImageGen.json'). If omitted, uses the currently active default workflow."
            }
        }
    },
)
def paint_list_variables(ctx, workflow: Optional[str] = None) -> str:
    paint_cog = ctx.bot.get_cog('Paint')
    if not paint_cog or not hasattr(paint_cog, 'backend'):
        return "Paint system is not initialized."
    
    try:
        variables = paint_cog.backend.get_variables(workflow=workflow)
        if not variables:
            return f"No customizable variables ([VAR] tags) found in the workflow '{workflow or 'default'}'. You can still use 'paint' with just a prompt."
        
        return f"Variables for '{workflow or 'default'}':\n{json.dumps(variables, indent=2)}"
    except Exception as e:
        return f"Error listing variables for workflow '{workflow}': {str(e)}"


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
            "workflow": {"type": "string", "description": "The workflow file to use (e.g., 'Anime.json'). See paint_list_workflows for options."},
            "image": {"type": "string", "description": "Optional asset ID of an image to use as input for Image-to-Image (e.g., 'img_8a2f123')."},
            "variables": {
                "type": "object",
                "description": "Custom variables for the workflow (e.g., {'Width': 1024, 'Height': 1024, 'Seed': 12345}). See paint_list_variables for available keys in a specific workflow.",
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

