"""
Helper utility functions for the Discord bot.
Includes localization, timestamp generation, and Discord-specific utilities.
"""

import discord
import pytz
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


def get_language(db, guild_id: int) -> str:
    """Get guild (server) language from database"""
    settings = db.get_server_settings(guild_id)
    return settings.get('language', 'en')


def get_user_language(db, user_id: int, guild_id: int) -> str:
    """Get user's language for this guild. Returns 'en' if not set."""
    if guild_id is None or user_id is None:
        return 'en'
    return db.get_user_language(user_id, guild_id)


def get_text(db, LANGUAGES: dict, guild_id: int, key: str, user_id: int = None, _cache: dict = None) -> str:
    """
    Get translated text. If user_id is given: use that user's choice if they set one, 
    else server default. Else use server language.
    
    Args:
        db: Database instance
        LANGUAGES: Language dictionary
        guild_id: Guild ID
        key: Translation key
        user_id: Optional user ID for user-specific language
        _cache: Optional cache dict for request-level caching (pass {} to enable)
    
    Returns:
        Translated text string
    """
    if guild_id is None:
        return LANGUAGES['en'].get(key, key)
    
    # Use cache if provided
    cache_key = f"{guild_id}_{user_id}"
    if _cache is not None and cache_key in _cache:
        lang = _cache[cache_key]
    else:
        # Determine language
        if user_id and db.has_user_chosen_language(user_id, guild_id):
            lang = db.get_user_language(user_id, guild_id)
        else:
            lang = get_language(db, guild_id)
        
        # Store in cache if provided
        if _cache is not None:
            _cache[cache_key] = lang
    
    return LANGUAGES.get(lang, LANGUAGES['en']).get(key, key)


async def update_member_nickname(member: discord.Member, new_name: str) -> tuple[bool, str]:
    """
    Update a member's server nickname to match their in-game name.
    Returns (success: bool, message: str)
    """
    try:
        # Limit name to 32 characters (Discord limit)
        nickname = new_name[:32] if len(new_name) > 32 else new_name
        
        # Try to change nickname
        await member.edit(nick=nickname)
        return True, f"Server nickname updated to: **{nickname}**"
    except discord.Forbidden:
        # Bot doesn't have permission or trying to change server owner
        return False, "⚠️ Couldn't update server nickname (missing permissions)"
    except discord.HTTPException as e:
        # Other Discord API error
        return False, f"⚠️ Couldn't update server nickname: {str(e)}"
    except Exception as e:
        # Unexpected error
        logger.error(f"Error updating nickname: {e}")
        return False, "⚠️ Error updating server nickname"


def get_discord_timestamp(hour: int, minute: int, days_ahead: int = 0, timezone_str: str = "Africa/Cairo") -> str:
    """
    Get Discord timestamp for a specific time.
    Discord automatically displays this in each user's local timezone.
    
    Args:
        hour: Hour in 24-hour format (0-23)
        minute: Minute (0-59)
        days_ahead: Number of days in the future (0 for today)
        timezone_str: Timezone string (e.g., 'Africa/Cairo', 'UTC')
    
    Returns:
        Discord timestamp string like <t:1234567890:t> which Discord renders in user's timezone
    """
    tz = pytz.timezone(timezone_str)
    now = datetime.now(tz)
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    target = target + timedelta(days=days_ahead)
    unix_timestamp = int(target.timestamp())
    # Format options:
    # :t = short time (e.g., 16:20)
    # :T = long time (e.g., 16:20:30)
    # :d = short date (e.g., 20/04/2021)
    # :D = long date (e.g., 20 April 2021)
    # :f = short date/time (e.g., 20 April 2021 16:20)
    # :F = long date/time (e.g., Tuesday, 20 April 2021 16:20)
    # :R = relative time (e.g., 2 months ago)
    return f"<t:{unix_timestamp}:t>"


def get_next_war_timestamps():
    """Get Discord timestamps for next Saturday and Sunday wars"""
    # This will be called per-guild with their specific war times
    # For now, using default times
    saturday_time = get_discord_timestamp(22, 30, 0 if datetime.now().weekday() == 5 else 1)
    sunday_time = get_discord_timestamp(22, 30, 0 if datetime.now().weekday() == 6 else 1)
    return saturday_time, sunday_time


async def validate_war_channel(channel_id: int, guild: discord.Guild) -> tuple:
    """Validate that war channel exists and bot has permissions"""
    if not channel_id:
        return False, "Channel not configured"
    
    channel = guild.get_channel(channel_id)
    if not channel:
        return False, "Channel not found"
    
    permissions = channel.permissions_for(guild.me)
    required = ["send_messages", "embed_links", "mention_everyone"]
    missing = [perm for perm in required if not getattr(permissions, perm)]
    
    if missing:
        return False, f"Missing permissions: {', '.join(missing)}"
    
    return True, "OK"


async def remove_all_build_roles(member: discord.Member, guild: discord.Guild):
    """
    Remove all build and weapon roles from a member.
    
    Args:
        member: Discord member to remove roles from
        guild: Discord guild
        
    Returns:
        tuple: (success: bool, removed_count: int)
    """
    from config import BUILDS, WEAPON_ICONS
    
    removed_count = 0
    
    try:
        # Remove build roles (DPS, Tank, Healer)
        for build_name in BUILDS.keys():
            role = discord.utils.get(guild.roles, name=build_name)
            if role and role in member.roles:
                try:
                    await member.remove_roles(role)
                    removed_count += 1
                except:
                    pass  # Role might not exist or no permissions
        
        # Remove weapon roles
        for weapon_name in WEAPON_ICONS.keys():
            weapon_role = discord.utils.get(guild.roles, name=weapon_name)
            if weapon_role and weapon_role in member.roles:
                try:
                    await member.remove_roles(weapon_role)
                    removed_count += 1
                except:
                    pass  # Role might not exist or no permissions
        
        return True, removed_count
    except Exception as e:
        logger.error(f"Error removing build roles from {member.id}: {e}")
        return False, removed_count

