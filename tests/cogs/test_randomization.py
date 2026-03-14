import pytest
import discord
from cogs.randomization import Randomization
from unittest.mock import mock_open

@pytest.mark.asyncio
async def test_genshin_command(mock_bot, mock_ctx, mocker):
    mocker.patch('random.choice', return_value='原神怎么你了 🤬')
    cog = Randomization(mock_bot)
    
    await cog.genshin(cog, mock_ctx)
    
    mock_ctx.reply.assert_called_once()
    args, kwargs = mock_ctx.reply.call_args
    assert '原神怎么你了 🤬' in kwargs.get('embed').description

@pytest.mark.asyncio
async def test_choose_command(mock_bot, mock_ctx, mocker):
    mocker.patch('random.choice', return_value='A')
    cog = Randomization(mock_bot)
    
    await cog.choose(cog, mock_ctx, "A", "B", "C")
    
    mock_ctx.reply.assert_called_once()
    args, kwargs = mock_ctx.reply.call_args
    assert 'A' in kwargs.get('embed').description

@pytest.mark.asyncio
async def test_magic_eightball_command(mock_bot, mock_ctx, mocker):
    m_open = mock_open(read_data="Yes\nNo\nMaybe\n")
    mocker.patch('cogs.randomization.open', m_open)
    mocker.patch('random.choice', return_value='Yes\n')
    cog = Randomization(mock_bot)
    
    await cog.magic_eightball(cog, mock_ctx, question="Am I good?")
    
    mock_ctx.reply.assert_called_once()
    args, kwargs = mock_ctx.reply.call_args
    embed = kwargs.get('embed')
    assert embed.fields[0].value == 'Yes\n'

@pytest.mark.asyncio
async def test_roll_command(mock_bot, mock_ctx, mocker):
    mocker.patch('random.randint', side_effect=[1, 2, 3])
    cog = Randomization(mock_bot)
    
    await cog.roll(cog, mock_ctx, cmd="3d6+2")
    
    mock_ctx.reply.assert_called_once()
    args, kwargs = mock_ctx.reply.call_args
    embed = kwargs.get('embed')
    # sum = 1+2+3 = 6. total = 6 + 2 = 8
    assert "total = 6 + 2 = 8" in embed.fields[0].value

@pytest.mark.asyncio
async def test_joke_command(mock_bot, mock_ctx, mocker):
    m_open = mock_open(read_data="Q<>A\n")
    mocker.patch('cogs.randomization.open', m_open)
    mocker.patch('random.choice', return_value='Q<>A\n')
    cog = Randomization(mock_bot)
    
    await cog.joke(cog, mock_ctx)
    
    mock_ctx.reply.assert_called_once()
    args, kwargs = mock_ctx.reply.call_args
    embed = kwargs.get('embed')
    assert embed.description == 'Q'
    assert embed.fields[0].value == 'A'

@pytest.mark.asyncio
async def test_add_joke_command(mock_bot, mock_ctx, mocker):
    m_open = mock_open()
    mocker.patch('cogs.randomization.open', m_open)
    cog = Randomization(mock_bot)
    
    # Mock Config().display_confirmation
    mock_conf = mocker.patch('cogs.randomization.Config').return_value
    mock_conf.display_confirmation = True
    
    await cog.add_joke(cog, mock_ctx, joke="Setup | Punchline")
    
    m_open.assert_called_once_with("cogs/jokes.txt", "a", encoding='utf-8')
    m_open().write.assert_called_once_with("Setup<>Punchline\n")
    
    mock_ctx.reply.assert_called_once()
