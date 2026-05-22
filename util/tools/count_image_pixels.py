import base64

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
                "type": "string",
                "description": (
                    "The asset id or data URI of the image to inspect. "
                    "Pass the image reference string here."
                ),
            },
        },
        "required": ["image"],
    },
)
def count_image_pixels(image: str) -> str:
    if image.startswith("data:"):
        try:
            # Format: data:image/png;base64,iVBOR...
            header, data = image.split(",", 1)
            image_bytes = base64.b64decode(data)
        except Exception as e:
            raise ValueError(f"Invalid Data URI: {e}")
    else:
        # Fallback if it's somehow just raw b64 or other string (though usually it will be Data URI now)
        try:
            image_bytes = base64.b64decode(image)
        except Exception:
            raise ValueError("Input must be a Data URI or base64 string.")

    with Image.open(BytesIO(image_bytes)) as img:
        width, height = img.size

    total_pixels = width * height
    return f"Image is {width}x{height}, for a total of {total_pixels} pixels."
