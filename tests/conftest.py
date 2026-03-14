import pytest
import discord
from discord.ext import commands
import sys
import os

# Ensure the root directory is in the sys.path so we can import modules properly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

@pytest.fixture
def mock_bot(mocker):
    bot = mocker.MagicMock(spec=commands.Bot)
    bot.user = mocker.MagicMock(spec=discord.ClientUser)
    bot.user.name = "TestBot"
    bot.loop = mocker.MagicMock()
    return bot

@pytest.fixture
def mock_ctx(mocker, mock_bot):
    ctx = mocker.MagicMock(spec=commands.Context)
    ctx.bot = mock_bot
    ctx.message = mocker.MagicMock(spec=discord.Message)
    ctx.message.attachments = []
    
    ctx.author = mocker.MagicMock(spec=discord.Member)
    ctx.author.name = "TestUser"
    ctx.author.nick = "TestNick"
    
    ctx.send = mocker.AsyncMock()
    ctx.reply = mocker.AsyncMock()
    
    typing_context = mocker.AsyncMock()
    typing_context.__aenter__ = mocker.AsyncMock()
    typing_context.__aexit__ = mocker.AsyncMock()
    ctx.typing = mocker.MagicMock(return_value=typing_context)
    
    return ctx

@pytest.fixture(autouse=True)
def mock_config(mocker):
    # Mock the Config class
    mock_conf = mocker.MagicMock()
    mock_conf.chat_backend = "dummy"
    mock_conf.model = "dummy-model"
    mock_conf.temperature = 0.7
    mock_conf.top_p = 0.9
    mock_conf.top_k = 40
    mock_conf.max_new_tokens = 512
    mock_conf.timeout = 30
    mock_conf.bot_name = "Luna"
    
    # Utilities configurations
    mock_conf.delete_invocation = False
    mock_conf.delete_confirmation = False
    mock_conf.reply = True
    mock_conf.mention_author = False
    mock_conf.ephemeral = False
    mock_conf.embed_footer = "Test Footer"
    
    # Patch all the places Config is imported and instantiated
    mocker.patch('config.config.Config', return_value=mock_conf)
    mocker.patch('cogs.chat.Config', return_value=mock_conf)
    mocker.patch('cogs.set_config.Config', return_value=mock_conf)
    mocker.patch('cogs.ping.Config', return_value=mock_conf)
    mocker.patch('cogs.calculator.Config', return_value=mock_conf)
    mocker.patch('cogs.randomization.Config', return_value=mock_conf)
    mocker.patch('cogs.moderation.Config', return_value=mock_conf)
    mocker.patch('cogs.control.Config', return_value=mock_conf)
    mocker.patch('cogs.paint.Config', return_value=mock_conf)
    mocker.patch('cogs.voice.Config', return_value=mock_conf)
    mocker.patch('utilities.Config', return_value=mock_conf)
    
    return mock_conf
