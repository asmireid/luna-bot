import pytest
import discord
from cogs.calculator import Calc

@pytest.mark.asyncio
async def test_calculator_command(mock_bot, mock_ctx):
    cog = Calc(mock_bot)
    
    await cog.calculator(cog, mock_ctx, expression="2 + 2")
    
    mock_ctx.reply.assert_called_once()
    args, kwargs = mock_ctx.reply.call_args
    embed = kwargs.get('embed')
    assert isinstance(embed, discord.Embed)
    assert "2 + 2 = 4" in embed.description

@pytest.mark.asyncio
async def test_calculator_command_invalid(mock_bot, mock_ctx):
    cog = Calc(mock_bot)
    
    await cog.calculator(cog, mock_ctx, expression="invalid")
    
    mock_ctx.reply.assert_called_once()
    assert mock_ctx.reply.call_args[0][0] == "'invalid' is not a valid expression..."

@pytest.mark.asyncio
async def test_represent_command_decimal(mock_bot, mock_ctx):
    cog = Calc(mock_bot)
    
    await cog.represent(cog, mock_ctx, num="10")
    
    mock_ctx.reply.assert_called_once()
    args, kwargs = mock_ctx.reply.call_args
    embed = kwargs.get('embed')
    assert "10 = 0b1010 = 0o12 = 0xa" in embed.description

@pytest.mark.asyncio
async def test_represent_command_hex(mock_bot, mock_ctx):
    cog = Calc(mock_bot)
    
    await cog.represent(cog, mock_ctx, num="0xa")
    
    mock_ctx.reply.assert_called_once()
    args, kwargs = mock_ctx.reply.call_args
    embed = kwargs.get('embed')
    assert "10 = 0b1010 = 0o12 = 0xa" in embed.description
