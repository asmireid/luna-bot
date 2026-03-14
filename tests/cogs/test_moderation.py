import pytest
import discord
from cogs.moderation import Moderation
from unittest.mock import MagicMock, AsyncMock
import datetime

@pytest.fixture
def mock_member(mocker):
    member = mocker.MagicMock(spec=discord.Member)
    member.id = 12345
    member.name = "TestMember"
    member.display_name = "TestNick"
    member.mention = "<@12345>"
    member.status = discord.Status.online
    member.created_at = datetime.datetime(2020, 1, 1)
    member.joined_at = datetime.datetime(2021, 1, 1)
    member.avatar = mocker.MagicMock()
    member.avatar.url = "http://avatar.url"
    
    role = mocker.MagicMock(spec=discord.Role)
    role.mention = "@everyone"
    member.roles = [role]
    member.top_role = role
    member.bot = False
    return member

@pytest.mark.asyncio
async def test_userinfo_command(mock_bot, mock_ctx, mock_member):
    cog = Moderation(mock_bot)
    
    await cog.userinfo(cog, mock_ctx, member=mock_member)
    
    mock_ctx.reply.assert_called_once()
    args, kwargs = mock_ctx.reply.call_args
    embed = kwargs.get('embed')
    assert "User info on <@12345>" in embed.description
    assert any(field.name == 'ID' and str(field.value) == '12345' for field in embed.fields)

@pytest.mark.asyncio
async def test_serverinfo_command(mock_bot, mock_ctx, mocker):
    guild = mocker.MagicMock(spec=discord.Guild)
    guild.name = "Test Guild"
    guild.id = 67890
    guild.member_count = 100
    guild.text_channels = [mocker.MagicMock()]
    guild.voice_channels = [mocker.MagicMock()]
    guild.owner = mocker.MagicMock(spec=discord.Member)
    guild.owner.mention = "<@owner>"
    guild.description = "A test guild"
    guild.created_at = datetime.datetime(2019, 1, 1)
    guild.icon = mocker.MagicMock()
    
    role = mocker.MagicMock(spec=discord.Role)
    role.mention = "@everyone"
    guild.roles = [role]
    
    mock_ctx.guild = guild
    cog = Moderation(mock_bot)
    
    await cog.serverinfo(cog, mock_ctx)
    
    mock_ctx.reply.assert_called_once()
    args, kwargs = mock_ctx.reply.call_args
    embed = kwargs.get('embed')
    assert "Server info on Test Guild" in embed.description

@pytest.mark.asyncio
async def test_clear_command(mock_bot, mock_ctx, mocker):
    mock_ctx.channel.purge = AsyncMock()
    cog = Moderation(mock_bot)
    
    # Mock Config().display_confirmation
    mock_conf = mocker.patch('cogs.moderation.Config').return_value
    mock_conf.display_confirmation = True
    
    await cog.clear(cog, mock_ctx, count=5)
    
    mock_ctx.channel.purge.assert_called_once()
    assert mock_ctx.channel.purge.call_args[1]['limit'] == 6
    mock_ctx.reply.assert_called_once()

@pytest.mark.asyncio
async def test_kick_command(mock_bot, mock_ctx, mock_member, mocker):
    mock_ctx.guild.kick = AsyncMock()
    cog = Moderation(mock_bot)
    
    mock_conf = mocker.patch('cogs.moderation.Config').return_value
    mock_conf.display_confirmation = True
    
    await cog.kick(cog, mock_ctx, member=mock_member, mod_reason="Spam")
    
    mock_ctx.guild.kick.assert_called_once_with(mock_member)
    mock_ctx.reply.assert_called_once()
    args, kwargs = mock_ctx.reply.call_args
    assert "has been kicked" in kwargs.get('embed').description

@pytest.mark.asyncio
async def test_ban_command(mock_bot, mock_ctx, mock_member, mocker):
    mock_ctx.guild.ban = AsyncMock()
    cog = Moderation(mock_bot)
    
    mock_conf = mocker.patch('cogs.moderation.Config').return_value
    mock_conf.display_confirmation = True
    
    await cog.ban(cog, mock_ctx, member=mock_member, mod_reason="Rules")
    
    mock_ctx.guild.ban.assert_called_once_with(mock_member)
    mock_ctx.reply.assert_called_once()
    args, kwargs = mock_ctx.reply.call_args
    assert "has been banned" in kwargs.get('embed').description

@pytest.mark.asyncio
async def test_unban_command(mock_bot, mock_ctx, mocker):
    mock_ctx.guild.unban = AsyncMock()
    cog = Moderation(mock_bot)
    
    mock_conf = mocker.patch('cogs.moderation.Config').return_value
    mock_conf.display_confirmation = True
    
    await cog.unban(cog, mock_ctx, user_id="12345")
    
    mock_ctx.guild.unban.assert_called_once()
    mock_ctx.reply.assert_called_once()
