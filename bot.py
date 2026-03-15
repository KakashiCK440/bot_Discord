"""
Main bot entry point for Discord bot.
Loads all cogs and starts the bot with background tasks.
"""

import discord
from discord.ext import commands, tasks
import os
from dotenv import load_dotenv
from aiohttp import web
import logging
from datetime import datetime, timedelta
import pytz
from pathlib import Path
import asyncio
from database import Database
from locales import LANGUAGES
from bot_config import (
    WAR_POLL_CHECK_INTERVAL,
    WAR_REMINDER_CHECK_INTERVAL,
    CLEANUP_INTERVAL_HOURS,
    CLEANUP_OLDER_THAN_WEEKS,
    WEB_SERVER_PORT,
    DISCORD_TOKEN
)
from utils.war_helpers import get_current_poll_week, get_war_config, DAY_MAP
from utils.helpers import get_discord_timestamp

# Configure logging
logging.basicConfig(
    level=logging.WARNING,  # Changed from INFO to WARNING for better performance
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Bot intents
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

# Create bot instance
bot = commands.Bot(command_prefix="!", intents=intents)

# Database initialization
DATA_DIR = Path("./data")
DATA_DIR.mkdir(exist_ok=True)
DB_FILE = DATA_DIR / "bot_data.db"

# Initialize database
db = Database(str(DB_FILE))
logger.info(f"✅ Database initialized at {DB_FILE}")


async def guild_only_interaction(interaction: discord.Interaction) -> bool:
    """Require slash commands to be used in a guild (not DMs)."""
    if interaction.guild_id is None:
        await interaction.response.send_message(
            LANGUAGES['en'].get('dm_only', 'This command can only be used in a server.'),
            ephemeral=True
        )
        return False
    return True


bot.tree.interaction_check = guild_only_interaction


# ==================== ERROR HANDLERS ====================

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
    """Global error handler for application commands"""
    logger.error(f"Command error in {interaction.command.name if interaction.command else 'unknown'}: {error}", exc_info=error)
    
    # Send user-friendly error message
    error_message = "❌ Something went wrong while processing your command. Please try again later."
    
    # Customize message for specific errors
    if isinstance(error, discord.app_commands.CommandOnCooldown):
        error_message = f"⏳ This command is on cooldown. Try again in {error.retry_after:.1f} seconds."
    elif isinstance(error, discord.app_commands.MissingPermissions):
        error_message = "❌ You don't have permission to use this command."
    elif isinstance(error, discord.app_commands.BotMissingPermissions):
        error_message = "❌ I don't have the necessary permissions to execute this command."
    elif isinstance(error, discord.app_commands.CheckFailure):
        error_message = "❌ You don't have permission to use this command."
    
    try:
        if interaction.response.is_done():
            await interaction.followup.send(error_message, ephemeral=True)
        else:
            await interaction.response.send_message(error_message, ephemeral=True)
    except Exception as e:
        logger.error(f"Failed to send error message: {e}")


# ==================== OWNER-ONLY COMMANDS ====================

@bot.command(name="leaveguild", hidden=True)
@commands.is_owner()
async def leave_guild(ctx, guild_id: int):
    """Owner-only: force the bot to leave a guild by its ID."""
    guild = bot.get_guild(guild_id)
    if guild is None:
        await ctx.send(f"❌ I'm not in a guild with ID `{guild_id}`.")
        return
    await guild.leave()
    await ctx.send(f"✅ Left guild **{guild.name}** (`{guild_id}`).")


# ==================== BOT EVENTS ====================

@bot.event
async def on_ready():
    """Bot ready event"""
    logger.info(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")
    logger.info(f"✅ Connected to {len(bot.guilds)} guilds")
    
    # Re-register persistent views
    await register_persistent_views()
    
    # Sync commands
    # Guild-copy = instant, Global = up to 1 hour to propagate
    try:
        # 1. Copy global commands into every connected guild → shows up instantly
        for guild in bot.guilds:
            bot.tree.copy_global_to(guild=guild)
            await bot.tree.sync(guild=guild)
        # 2. Also do global sync for guilds the bot joins later
        synced = await bot.tree.sync()
        logger.info(f"✅ Synced {len(synced)} command(s) globally + instant-synced to {len(bot.guilds)} guild(s)")
    except Exception as e:
        logger.error(f"❌ Failed to sync commands: {e}")
    
    # Start background tasks
    if not check_war_poll_schedule.is_running():
        check_war_poll_schedule.start()
        logger.info("✅ Started war poll scheduler task")
    
    if not check_war_reminders.is_running():
        check_war_reminders.start()
        logger.info("✅ Started war reminders task")
    
    if not cleanup_old_data.is_running():
        cleanup_old_data.start()
        logger.info("✅ Started cleanup task")
    
    # Start web server for health checks
    asyncio.create_task(start_web_server())
    
    logger.info("✅ Bot is ready!")


async def register_persistent_views():
    """Register all persistent views that should survive bot restarts"""
    from views.profile_views import ProfileSetupButton
    from views.join_views import JoinRequestButton, AdminApprovalView
    from views.build_views import BuildSelectView
    
    # Register war poll views (both single-event and all-event variants)
    # Pass empty events list — the view uses custom_id matching, guild_id resolved from interaction
    from cogs.war import WarPollAllView, WarPollSingleView
    bot.add_view(WarPollAllView(guild_id=None, db=db, events=[]))
    
    # Register profile setup button (LANGUAGES first, then db)
    bot.add_view(ProfileSetupButton(LANGUAGES=LANGUAGES, db=db))
    
    # Register join request button
    bot.add_view(JoinRequestButton(db, LANGUAGES))
    
    # Register admin approval view (for join requests)
    bot.add_view(AdminApprovalView(None, None, None, db, LANGUAGES))

    # Register build select view
    bot.add_view(BuildSelectView(db, LANGUAGES))
    
    logger.info("✅ Persistent views registered")


@bot.event
async def on_guild_join(guild):
    """Handle bot joining a new guild"""
    logger.info(f"✅ Joined new guild: {guild.name} (ID: {guild.id})")


@bot.event
async def on_guild_remove(guild):
    """Handle bot leaving a guild"""
    logger.info(f"❌ Left guild: {guild.name} (ID: {guild.id})")


# ==================== BACKGROUND TASKS ====================

async def post_war_poll_to_channel(channel: discord.TextChannel, guild_id: int, config: dict):
    """Build and send the war poll embed + buttons to the given channel."""
    from cogs.war import WarPollView
    from utils.helpers import get_discord_timestamp
    from locales import LANGUAGES

    guild_timezone = config.get("timezone", "Africa/Cairo")
    import pytz
    now = datetime.now(pytz.timezone(guild_timezone))
    current_weekday = now.weekday()

    # Days until next Saturday (5)
    days_to_saturday = (5 - current_weekday) % 7 or 7 if current_weekday != 5 else 0
    days_to_sunday = (6 - current_weekday) % 7 or 7 if current_weekday != 6 else 0

    saturday_time = get_discord_timestamp(
        config["saturday_war"]["hour"],
        config["saturday_war"]["minute"],
        days_to_saturday,
        guild_timezone
    )
    sunday_time = get_discord_timestamp(
        config["sunday_war"]["hour"],
        config["sunday_war"]["minute"],
        days_to_sunday,
        guild_timezone
    )

    # Build embed using English as default for auto-posts
    # (guild language will apply for buttons via get_text per user)
    lang = db.get_server_settings(guild_id).get('language', 'en')
    L = LANGUAGES.get(lang, LANGUAGES['en'])

    embed = discord.Embed(
        title=L.get("war_poll_title", "⚔️ War Poll"),
        description=L.get("war_poll_desc", "Vote for which day(s) you'll participate in war!"),
        color=discord.Color.red()
    )
    embed.add_field(
        name=f"📅 {L.get('saturday', 'Saturday')}",
        value=f"⏰ {saturday_time}",
        inline=True
    )
    embed.add_field(
        name=f"📅 {L.get('sunday', 'Sunday')}",
        value=f"⏰ {sunday_time}",
        inline=True
    )
    embed.add_field(
        name="ℹ️",
        value=L.get("use_warlist", "Use /warlist to see who signed up"),
        inline=False
    )
    embed.set_footer(text=L.get("times_local", "Times shown in your local timezone"))

    view = WarPollView(guild_id, db)
    await channel.send(embed=embed, view=view)


@tasks.loop(minutes=WAR_POLL_CHECK_INTERVAL)
async def check_war_poll_schedule():
    """Check if it's time to post war polls"""
    try:
        now_utc = datetime.now(pytz.UTC)

        for guild in bot.guilds:
            try:
                config = get_war_config(db, guild.id)
                channel_id = config.get("war_channel_id")

                if not channel_id:
                    continue

                # Get guild timezone
                tz = pytz.timezone(config.get("timezone", "Africa/Cairo"))
                now_local = now_utc.astimezone(tz)

                # Check if it's poll day and time
                poll_day = config.get("poll_day", "Friday")
                poll_hour = config["poll_time"]["hour"]
                poll_minute = config["poll_time"]["minute"]

                # Map day names to weekday numbers
                day_map = {
                    "Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3,
                    "Friday": 4, "Saturday": 5, "Sunday": 6
                }

                if now_local.weekday() == day_map.get(poll_day, 4):
                    if now_local.hour == poll_hour and now_local.minute == poll_minute:
                        poll_week = get_current_poll_week()
                        if not db.was_event_sent(guild.id, "war_poll", poll_week):
                            channel = guild.get_channel(channel_id)
                            if channel:
                                logger.info(f"📅 Auto-posting war poll for {guild.name}")
                                await post_war_poll_to_channel(channel, guild.id, config)
                                db.mark_event_sent(guild.id, "war_poll", poll_week)

            except Exception as e:
                logger.error(f"Error checking war poll for guild {guild.id}: {e}")

    except Exception as e:
        logger.error(f"Error in war poll scheduler: {e}")



@tasks.loop(minutes=WAR_REMINDER_CHECK_INTERVAL)
async def check_war_reminders():
    """Check if it's time to send war reminders — loops over all active war events in DB"""
    try:
        now_utc = datetime.now(pytz.UTC)

        for guild in bot.guilds:
            try:
                config = get_war_config(db, guild.id)
                channel_id = config.get("war_channel_id")
                if not channel_id:
                    continue

                tz_name = config.get("timezone", "Africa/Cairo")
                tz = pytz.timezone(tz_name)
                now_local = now_utc.astimezone(tz)
                reminder_hours = config.get("reminder_hours", 2)
                window_secs = 60 * WAR_REMINDER_CHECK_INTERVAL
                poll_week = get_current_poll_week()

                # Fetch all active war events for this guild
                events = db.get_war_events(guild.id, active_only=True)

                for event in events:
                    event_name = event["name"]
                    event_wd = DAY_MAP.get(event["day_of_week"], 5)

                    # Only check on the correct weekday
                    if now_local.weekday() != event_wd:
                        continue

                    war_time = now_local.replace(
                        hour=event["war_hour"],
                        minute=event["war_minute"],
                        second=0, microsecond=0
                    )
                    remind_at = war_time - timedelta(hours=reminder_hours)

                    if abs((now_local - remind_at).total_seconds()) >= window_secs:
                        continue

                    # Use a slug-safe event key to avoid duplicate reminders
                    event_key = f"evt_reminder_{event_name.replace(' ', '_')}"
                    if db.was_event_sent(guild.id, event_key, poll_week):
                        continue

                    channel = guild.get_channel(channel_id)
                    if not channel:
                        continue

                    # Fetch players who voted "playing" for this event
                    votes = db.get_war_votes(guild.id, event_name, poll_week)
                    playing_ids = [v["user_id"] for v in votes if v["playing"]]

                    embed = discord.Embed(
                        title=f"⚔️ {event_name} — War Reminder!",
                        description=(
                            f"📅 **{event['day_of_week']}** at "
                            f"**{event['war_hour']:02d}:{event['war_minute']:02d}** ({tz_name})\n\n"
                            f"⏰ War starts in **{reminder_hours} hour(s)**!"
                        ),
                        color=discord.Color.red()
                    )

                    if playing_ids:
                        mentions = " ".join(f"<@{pid}>" for pid in playing_ids)
                        embed.add_field(
                            name=f"✅ Signed Up ({len(playing_ids)})",
                            value=mentions[:1020],
                            inline=False
                        )
                    else:
                        embed.add_field(
                            name="⚠️ No sign-ups yet",
                            value="Nobody has voted for this war. Use `/warpoll` to post a poll!",
                            inline=False
                        )

                    try:
                        await channel.send(embed=embed)
                        db.mark_event_sent(guild.id, event_key, poll_week)
                        logger.info(f"⚔️ Reminder sent for '{event_name}' in {guild.name}")
                    except Exception as e:
                        logger.error(f"Failed to send reminder for {event_name} in {guild.name}: {e}")

            except Exception as e:
                logger.error(f"Error checking war reminders for guild {guild.id}: {e}")

    except Exception as e:
        logger.error(f"Error in war reminder task: {e}")


@tasks.loop(hours=CLEANUP_INTERVAL_HOURS)
async def cleanup_old_data():
    """Clean up old event data from database"""
    try:
        logger.info("🧹 Running cleanup task...")
        
        # Calculate cutoff date
        cutoff_date = datetime.now() - timedelta(weeks=CLEANUP_OLDER_THAN_WEEKS)
        
        # Clean up old events for all guilds
        for guild in bot.guilds:
            try:
                db.clear_old_events(guild.id, cutoff_date)
            except Exception as e:
                logger.error(f"Error cleaning up data for guild {guild.id}: {e}")
        
        logger.info("✅ Cleanup task completed")
    
    except Exception as e:
        logger.error(f"Error in cleanup task: {e}")


# ==================== WEB SERVER FOR HEALTH CHECKS ====================

async def health_check(request):
    """Health check endpoint"""
    return web.Response(text="OK", status=200)


async def start_web_server():
    """Start web server for health checks (for hosting platforms)"""
    app = web.Application()
    app.router.add_get("/", health_check)
    app.router.add_get("/health", health_check)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    site = web.TCPSite(runner, "0.0.0.0", WEB_SERVER_PORT)
    
    try:
        await site.start()
        logger.info(f"✅ Web server started on port {WEB_SERVER_PORT}")
    except Exception as e:
        logger.error(f"❌ Failed to start web server: {e}")


# ==================== LOAD COGS ====================

async def load_cogs():
    """Load all cog modules"""
    cogs = [
        "cogs.admin",
        "cogs.build",
        "cogs.profile",
        "cogs.war",
        "cogs.join"
    ]
    
    for cog in cogs:
        try:
            await bot.load_extension(cog)
            logger.info(f"✅ Loaded {cog}")
        except Exception as e:
            logger.error(f"❌ Failed to load {cog}: {e}")


# ==================== MAIN ENTRY POINT ====================

async def main():
    """Main entry point"""
    async with bot:
        # Load all cogs
        await load_cogs()
        
        # Start the bot
        if not DISCORD_TOKEN:
            logger.error("❌ DISCORD_TOKEN not found in environment variables!")
            return
        
        await bot.start(DISCORD_TOKEN)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Bot stopped by user")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
