from __future__ import annotations

from io import BytesIO

from PIL import Image

from util.tools.count_image_pixels import count_image_pixels


def test_count_image_pixels_returns_dimensions_and_total():
    image = Image.new("RGB", (3, 4), color="red")
    buffer = BytesIO()
    image.save(buffer, format="PNG")

    result = count_image_pixels(
        {
            "data": buffer.getvalue(),
            "mime_type": "image/png",
            "filename": "tiny.png",
        }
    )

    assert result == "tiny.png is 3x4, for a total of 12 pixels."
