import base64

import pytest

from util.Chat.tools.providers.local import LocalToolProvider
from util.Chat.tools.types import ToolExecutionContext
from util.Media import AssetStore
from util.Media.adapter import normalize_tool_result, resolve_tool_arguments


@pytest.mark.asyncio
async def test_resolve_tool_arguments_for_local_materializes_asset_to_data_uri(tmp_path):
    store = AssetStore(base_dir=str(tmp_path))
    ref = await store.put_bytes(b"image-bytes", "image/png", kind="image", filename="sample.png")

    resolved = await resolve_tool_arguments(
        {"image": {"asset_id": ref.asset_id, "kind": ref.kind, "mime_type": ref.mime_type, "filename": ref.filename}},
        store,
        "local",
    )

    assert isinstance(resolved["image"], str)
    assert resolved["image"].startswith("data:image/png;base64,")


@pytest.mark.asyncio
async def test_resolve_tool_arguments_for_mcp_materializes_asset_to_data_uri(tmp_path):
    store = AssetStore(base_dir=str(tmp_path))
    ref = await store.put_bytes(b"image-bytes", "image/png", kind="image", filename="sample.png")

    resolved = await resolve_tool_arguments({"image": {"asset_id": ref.asset_id}}, store, "mcp")

    assert isinstance(resolved["image"], str)
    assert resolved["image"].startswith("data:image/png;base64,")
    encoded = base64.b64encode(b"image-bytes").decode("utf-8")
    assert encoded in resolved["image"]


@pytest.mark.asyncio
async def test_resolve_tool_arguments_resolves_string_asset_ids(tmp_path):
    store = AssetStore(base_dir=str(tmp_path))
    ref = await store.put_bytes(b"image-bytes", "image/png", kind="image", filename="sample.png")

    # Local: should materialize to Data URI
    resolved_local = await resolve_tool_arguments({"image": ref.asset_id}, store, "local")
    assert isinstance(resolved_local["image"], str)
    assert resolved_local["image"].startswith("data:image/png;base64,")

    # MCP: should materialize to Data URI
    resolved_mcp = await resolve_tool_arguments({"image": ref.asset_id}, store, "mcp")
    assert isinstance(resolved_mcp["image"], str)
    assert resolved_mcp["image"].startswith("data:image/png;base64,")


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
        # image is now a Data URI string
        assert image.startswith("data:image/png;base64,")
        header, data = image.split(",", 1)
        raw_bytes = base64.b64decode(data)
        assert raw_bytes == b"input-bytes"
        
        return {
            "data": raw_bytes[::-1],
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
