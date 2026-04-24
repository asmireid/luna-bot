from __future__ import annotations

from io import BytesIO

from PIL import Image

from util.Chat.tools import chat_tools


@chat_tools.register(
    name="count_image_pixels",
    description=(
        "Counts the total number of pixels in an input image. "
        "Use this when the user asks about image size, dimensions, resolution, or total pixels. "
        "Pass the input file or image in the `image` argument."
    ),
    parameters={
        "type": "object",
        "properties": {
            "image": {
                "type": "object",
                "description": (
                    "The input image file to inspect. "
                    "For attached files, pass the available image/file reference for this image here."
                ),
                "properties": {
                    "asset_id": {
                        "type": "string",
                        "description": "The asset id for the input image file.",
                    },
                    "filename": {
                        "type": "string",
                        "description": "Optional original filename for the image.",
                    },
                },
                "required": ["asset_id"],
            },
        },
        "required": ["image"],
    },
)
def count_image_pixels(image: dict) -> str:
    image_bytes = image.get("data")
    if image_bytes is None:
        raise ValueError("Missing image data.")

    with Image.open(BytesIO(image_bytes)) as img:
        width, height = img.size

    total_pixels = width * height
    filename = image.get("filename") or "image"
    return f"{filename} is {width}x{height}, for a total of {total_pixels} pixels."
