import pytest
import discord
from cogs.set_config import SetConfig

@pytest.mark.asyncio
async def test_get_command(mock_bot, mock_ctx, mock_config, mocker):
    mock_config.test_option = "test_value"
    mock_config.is_sensitive.return_value = False
    
    cog = SetConfig(mock_bot)
    await cog.get(cog, mock_ctx, option="test_option")
    
    mock_ctx.reply.assert_called_once()
    args, kwargs = mock_ctx.reply.call_args
    embed = kwargs.get('embed')
    assert embed is not None
    assert embed.fields[0].name == "test_option"
    assert embed.fields[0].value == "test_value"

@pytest.mark.asyncio
async def test_set_command_basic(mock_bot, mock_ctx, mock_config, mocker):
    mock_config.test_option = "old_value"
    mock_config.is_sensitive.return_value = False
    
    # Mock _reload_chat_backend_if_needed and _reload_paint_backend_if_needed
    mocker.patch('cogs.set_config._reload_chat_backend_if_needed')
    mocker.patch('cogs.set_config._reload_paint_backend_if_needed')
    
    cog = SetConfig(mock_bot)
    await cog.set(cog, mock_ctx, option="test_option", value="new_value")
    
    assert mock_config.test_option == "new_value"
    mock_ctx.reply.assert_called_once()

@pytest.mark.asyncio
async def test_set_command_sensitive(mock_bot, mock_ctx, mock_config, mocker):
    mock_config.secret = "password"
    mock_config.is_sensitive.side_effect = lambda x: x == "secret"
    
    cog = SetConfig(mock_bot)
    await cog.set(cog, mock_ctx, option="secret", value="new_password")
    
    assert mock_config.secret == "password" # Should not change
    mock_ctx.reply.assert_called_once()
    assert "sensitive information" in mock_ctx.reply.call_args[0][0]

@pytest.mark.asyncio
async def test_list_config_command(mock_bot, mock_ctx, mock_config, mocker):
    # Setup some properties on mock_config type to simulate Config properties
    type(mock_config).prop1 = property(lambda x: "val1")
    type(mock_config).prop2 = property(lambda x: "val2")
    # Also need them to be in dir(mock_config) for the test to find them
    # But for MagicMock, we might need to mock dir() or just ensure they are visible
    mocker.patch('cogs.set_config.dir', return_value=['prop1', 'prop2'])
    mock_config.is_sensitive.return_value = False
    
    cog = SetConfig(mock_bot)
    await cog.list_config(cog, mock_ctx)
    
    mock_ctx.reply.assert_called_once()
