import base64
from io import BytesIO

from PIL import Image

from util.tools.count_image_pixels import count_image_pixels


def test_count_image_pixels_returns_dimensions_and_total():
    image = Image.new("RGB", (3, 4), color="red")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    data = buffer.getvalue()
    b64_data = base64.b64encode(data).decode("utf-8")
    data_uri = f"data:image/png;base64,{b64_data}"

    result = count_image_pixels(data_uri)

    assert result == "Image is 3x4, for a total of 12 pixels."
