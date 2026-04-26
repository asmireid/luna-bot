import pytest

from util.Media import AssetStore


@pytest.mark.asyncio
async def test_put_bytes_keeps_small_asset_in_memory(tmp_path):
    store = AssetStore(base_dir=str(tmp_path), memory_limit_bytes=32)

    ref = await store.put_bytes(
        b"small-image",
        "image/png",
        filename="sample.png",
        source="discord",
    )

    asset = await store.get(ref.asset_id)
    assert asset is not None
    assert asset.data == b"small-image"
    assert asset.path is None
    assert asset.ref.filename == "sample.png"
    assert asset.ref.source == "discord"


@pytest.mark.asyncio
async def test_put_bytes_spills_large_asset_to_disk(tmp_path):
    store = AssetStore(base_dir=str(tmp_path), memory_limit_bytes=4)

    ref = await store.put_bytes(
        b"abcdef",
        "image/png",
        filename="large.png",
    )

    asset = await store.get(ref.asset_id)
    assert asset is not None
    assert asset.data is None
    assert asset.path is not None
    assert await store.resolve_bytes(ref.asset_id) == b"abcdef"


@pytest.mark.asyncio
async def test_resolve_path_materializes_in_memory_asset(tmp_path):
    store = AssetStore(base_dir=str(tmp_path), memory_limit_bytes=64)

    ref = await store.put_bytes(
        b"materialize-me",
        "image/jpeg",
        filename="photo.jpg",
    )

    path = await store.resolve_path(ref.asset_id)
    assert path.endswith(".jpg")
    assert await store.resolve_bytes(ref.asset_id) == b"materialize-me"


@pytest.mark.asyncio
async def test_prune_respects_references_and_pins(tmp_path):
    store = AssetStore(base_dir=str(tmp_path), default_ttl_seconds=0)

    kept_ref = await store.put_bytes(b"keep", "image/png", filename="keep.png")
    pinned_ref = await store.put_bytes(b"pin", "image/png", filename="pin.png")
    stale_ref = await store.put_bytes(b"drop", "image/png", filename="drop.png")

    await store.pin(pinned_ref.asset_id)
    deleted = await store.prune(referenced_asset_ids={kept_ref.asset_id}, older_than_seconds=0)

    assert stale_ref.asset_id in deleted
    assert kept_ref.asset_id not in deleted
    assert pinned_ref.asset_id not in deleted
    assert await store.contains(kept_ref.asset_id)
    assert await store.contains(pinned_ref.asset_id)
    assert not await store.contains(stale_ref.asset_id)
