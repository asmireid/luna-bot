import base64

import pytest

from util.Chat.tools.providers.local import LocalToolProvider
from util.Chat.tools.types import ToolExecutionContext
from util.Media import AssetStore
from util.Media.adapter import normalize_tool_result, resolve_tool_arguments


@pytest.mark.asyncio
async def test_resolve_tool_arguments_for_local_materializes_asset_to_raw_bytes(tmp_path):
    store = AssetStore(base_dir=str(tmp_path))
    ref = await store.put_bytes(b"image-bytes", "image/png", kind="image", filename="sample.png")

    resolved = await resolve_tool_arguments(
        {"image": {"asset_id": ref.asset_id, "kind": ref.kind, "mime_type": ref.mime_type, "filename": ref.filename}},
        store,
        "local",
    )

    assert resolved["image"]["asset_id"] == ref.asset_id
    assert resolved["image"]["mime_type"] == "image/png"
    assert resolved["image"]["data"] == b"image-bytes"


@pytest.mark.asyncio
async def test_resolve_tool_arguments_for_mcp_materializes_asset_to_mcp_block(tmp_path):
    store = AssetStore(base_dir=str(tmp_path))
    ref = await store.put_bytes(b"image-bytes", "image/png", kind="image", filename="sample.png")

    resolved = await resolve_tool_arguments({"image": {"asset_id": ref.asset_id}}, store, "mcp")

    assert resolved["image"]["type"] == "image"
    assert resolved["image"]["mimeType"] == "image/png"
    assert base64.b64decode(resolved["image"]["data"]) == b"image-bytes"


@pytest.mark.asyncio
async def test_normalize_tool_result_stores_local_raw_media_dict(tmp_path):
    store = AssetStore(base_dir=str(tmp_path))

    result = await normalize_tool_result(
        {
            "data": b"output-bytes",
            "mime_type": "image/png",
            "filename": "output.png",
            "kind": "image",
        },
        asset_store=store,
        provider_id="local",
        tool_name="local-image_tool",
        source="local:image_tool",
    )

    assert result.ok is True
    assert len(result.files) == 1
    assert result.files[0].filename == "output.png"
    assert await store.resolve_bytes(result.files[0].asset_id) == b"output-bytes"


@pytest.mark.asyncio
async def test_local_provider_resolves_inputs_and_normalizes_raw_output(tmp_path):
    provider = LocalToolProvider()
    store = AssetStore(base_dir=str(tmp_path))

    @provider.register(name="invert_image", description="test", parameters=None)
    def invert_image(image):
        assert image["data"] == b"input-bytes"
        assert image["mime_type"] == "image/png"
        return {
            "data": image["data"][::-1],
            "mime_type": "image/png",
            "filename": "inverted.png",
            "kind": "image",
        }

    ref = await store.put_bytes(b"input-bytes", "image/png", kind="image", filename="input.png")
    ctx = ToolExecutionContext(asset_store=store)

    result = await provider.call_tool(
        "local-invert_image",
        {"image": {"asset_id": ref.asset_id, "kind": ref.kind, "mime_type": ref.mime_type, "filename": ref.filename}},
        ctx,
    )

    assert result.ok is True
    assert len(result.files) == 1
    assert result.files[0].filename == "inverted.png"
    assert await store.resolve_bytes(result.files[0].asset_id) == b"setyb-tupni"
