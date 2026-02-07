import discord
from discord.ext import commands, tasks
import os
from dotenv import load_dotenv
from aiohttp import web
import asyncio
import logging
from datetime import datetime, timedelta
import pytz
from pathlib import Path
from database import Database

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# -----------------------------
# Discord API Safety (Rate Limits)
# -----------------------------
_API_LOCK = asyncio.Lock()
_MODAL_COOLDOWN: dict[tuple[int | None, int], float] = {}

def _retry_after_from_http_exception(e: discord.HTTPException, default: float = 5.0) -> float:
    """Best-effort retry-after extraction for 429s."""
    ra = getattr(e, "retry_after", None)
    if ra is not None:
        try:
            return float(ra)
        except Exception:
            pass

    try:
        resp = getattr(e, "response", None)
        if resp is not None:
            hdr = resp.headers.get("Retry-After")
            if hdr:
                return float(hdr)
    except Exception:
        pass

    return float(default)

async def _discord_call(coro_factory, *, retries: int = 2):
    """Run a Discord API call with a global lock and basic 429 backoff."""
    for attempt in range(retries + 1):
        try:
            async with _API_LOCK:
                return await coro_factory()
        except discord.HTTPException as e:
            if getattr(e, "status", None) == 429:
                wait = _retry_after_from_http_exception(e, default=5.0)
                logger.warning(f"⏳ Hit Discord rate limit (429). Sleeping {wait:.2f}s then retrying...")
                await asyncio.sleep(wait)
                continue
            raise

async def safe_send_message(interaction: discord.Interaction, *args, **kwargs):
    """Send a message safely (uses followup if already responded) + 429 handling."""
    async def _send():
        if hasattr(interaction, "response") and not interaction.response.is_done():
            return await safe_send_message(interaction, *args, **kwargs)
        return await interaction.followup.send(*args, **kwargs)
    return await _discord_call(_send)

async def safe_send_modal(interaction: discord.Interaction, modal: discord.ui.Modal, *, cooldown_seconds: float = 3.0):
    """Open a modal with basic cooldown + 429 handling."""
    key = (interaction.guild_id, interaction.user.id)
    now = asyncio.get_event_loop().time()
    last = _MODAL_COOLDOWN.get(key, 0.0)

    # Prevent rapid repeated clicks from hammering the API
    if now - last < cooldown_seconds:
        return await safe_send_message(interaction, "⏳ Please wait a moment, then try again.", ephemeral=True)

    _MODAL_COOLDOWN[key] = now

    async def _send():
        # Modals must be the initial response
        if interaction.response.is_done():
            return await interaction.followup.send("⚠️ Please click the button again.", ephemeral=True)
        return await safe_send_modal(interaction, modal)

    return await _discord_call(_send)

async def safe_message_edit(message: discord.Message, *args, **kwargs):
    """Edit a message with 429 handling."""
    return await _discord_call(lambda: message.edit(*args, **kwargs))


# -----------------------------
# Database Initialization
# -----------------------------
DATA_DIR = Path("./data")
DATA_DIR.mkdir(exist_ok=True)
DB_FILE = DATA_DIR / "bot_data.db"

# Initialize database
db = Database(str(DB_FILE))
logger.info(f"✅ Database initialized at {DB_FILE}")

# -----------------------------
# Language System
# -----------------------------
LANGUAGES = {
    "en": {
        # Commands
        "help_title": "🤖 Bot Commands Help",
        "help_desc": "Here's everything I can do!",
        "build_commands": "⚔️ Build Commands",
        "build_commands_desc": """
        `/postbuilds` - Post build selection menu
        `/mybuild` - View your current build
        `/resetbuild` - Reset and change your build
        `/createroles` - Create all build and weapon roles (Admin)
        """,
        "war_commands": "🗡️ War Commands",
        "war_commands_desc": """
        `/warpoll` - Post war participation poll (Admin)
        `/warlist [day]` - Show who's playing (optional: saturday/sunday)
        `/setwar <setting> <value>` - Configure war settings (Admin)
        `/warconfig` - View current war configuration
        `/testreminder <day>` - Test war reminder (Admin)
        `/resetwar <confirm>` - Reset current week's war data (Admin)
        `/resetallwar <confirm>` - Reset ALL war data (Admin)
        `/setlanguage <language>` - Set server language (Admin)
        """,
        "profile_commands": "👤 Profile Commands",
        "profile_commands_desc": """
        `/setupprofile` - Guided profile setup (recommended)
        `/setprofile` - Quick profile update
        `/profile [user]` - View player profile
        `/updatestats` - Update your mastery points or level
        `/leaderboard [type] [limit]` - View server leaderboard
        """,
        "system_commands": "🔧 System Commands",
        "system_commands_desc": """
        `/synccommands` - Force sync slash commands (Admin)
        `/help` - Show this help message
        """,
        
        # War Poll
        "war_poll_title": "⚔️ Weekend War Poll ⚔️",
        "war_poll_desc": "Vote for which war(s) you'll participate in this weekend!",
        "saturday_only": "Saturday Only",
        "sunday_only": "Sunday Only",
        "both_days": "Both Days",
        "not_playing": "Not Playing",
        "players": "players",
        "total_saturday": "Total for Saturday",
        "total_sunday": "Total for Sunday",
        "sat_sun_players": "Saturday + Both Days players",
        "sun_both_players": "Sunday + Both Days players",
        "click_button": "Click button",
        "use_warlist": "Use /warlist to see detailed player lists with their builds",
        "times_local": "Times shown in your local timezone",
        
        # Registration confirmations
        "registered_saturday": "✅ You're registered for **Saturday's war**!",
        "registered_sunday": "✅ You're registered for **Sunday's war**!",
        "registered_both": "✅ You're registered for **both Saturday and Sunday wars**!",
        "registered_not_playing": "✅ You're marked as **not playing** this weekend.",
        
        # War List
        "war_list_title": "⚔️ War Participant Lists ⚔️",
        "no_players": "No players signed up yet",
        "footer_builds": "Times shown in your local timezone • Players without builds should use /postbuilds",
        
        # Misc
        "saturday": "Saturday",
        "sunday": "Sunday",
        "language_set": "✅ Server language set to **{language}**!",
        "commands_synced": "✅ Commands synced successfully!",
        
        # Build Selection
        "select_build": "Select your build type",
        "select_weapons": "Select your weapons (1-2)",
        "build_set": "✅ Build set successfully!",
        "weapons_set": "✅ Weapons selected successfully!",
        "reset_build": "Are you sure you want to reset your build?",
        
        # Profile
        "profile_title": "👤 Player Profile",
        "in_game_name": "In-Game Name",
        "level": "Level",
        "mastery_points": "Mastery Points",
        "rank": "Server Rank",
        "build_type": "Build Type",
        "weapons": "Weapons",
        "no_profile": "No profile found. Use `/setupprofile` to create one!",
    },
    "ar": {
        # Commands
        "help_title": "🤖 أوامر البوت",
        "help_desc": "إليك كل ما يمكنني فعله!",
        "build_commands": "⚔️ أوامر البناء",
        "build_commands_desc": """
        `/postbuilds` - نشر قائمة اختيار البناء
        `/mybuild` - عرض بنائك الحالي
        `/resetbuild` - إعادة تعيين وتغيير بنائك
        `/createroles` - إنشاء جميع أدوار البناء والأسلحة (مشرف)
        """,
        "war_commands": "🗡️ أوامر الحرب",
        "war_commands_desc": """
        `/warpoll` - نشر استطلاع المشاركة في الحرب (مشرف)
        `/warlist [day]` - إظهار من يلعب (اختياري: السبت/الأحد)
        `/setwar <setting> <value>` - تكوين إعدادات الحرب (مشرف)
        `/warconfig` - عرض تكوين الحرب الحالي
        `/testreminder <day>` - اختبار تذكير الحرب (مشرف)
        `/resetwar <confirm>` - إعادة تعيين بيانات الحرب للأسبوع الحالي (مشرف)
        `/resetallwar <confirm>` - إعادة تعيين جميع بيانات الحرب (مشرف)
        `/setlanguage <language>` - تعيين لغة الخادم (مشرف)
        """,
        "profile_commands": "👤 أوامر الملف الشخصي",
        "profile_commands_desc": """
        `/setupprofile` - إعداد الملف الشخصي الموجه (موصى به)
        `/setprofile` - تحديث سريع للملف الشخصي
        `/profile [user]` - عرض ملف اللاعب الشخصي
        `/updatestats` - تحديث نقاط الإتقان أو المستوى
        `/leaderboard [type] [limit]` - عرض لوحة الصدارة للخادم
        """,
        "system_commands": "🔧 أوامر النظام",
        "system_commands_desc": """
        `/synccommands` - فرض مزامنة الأوامر المائلة (مشرف)
        `/help` - إظهار رسالة المساعدة هذه
        """,
        
        # War Poll
        "war_poll_title": "⚔️ استطلاع حرب نهاية الأسبوع ⚔️",
        "war_poll_desc": "صوت لأي حرب (حروب) ستشارك فيها في نهاية هذا الأسبوع!",
        "saturday_only": "السبت فقط",
        "sunday_only": "الأحد فقط",
        "both_days": "كلا اليومين",
        "not_playing": "لن ألعب",
        "players": "لاعبين",
        "total_saturday": "المجموع للسبت",
        "total_sunday": "المجموع للأحد",
        "sat_sun_players": "لاعبو السبت + كلا اليومين",
        "sun_both_players": "لاعبو الأحد + كلا اليومين",
        "click_button": "انقر على الزر",
        "use_warlist": "استخدم /warlist لرؤية قوائم اللاعبين التفصيلية مع بناءاتهم",
        "times_local": "الأوقات معروضة بالتوقيت المحلي الخاص بك",
        
        # Registration confirmations
        "registered_saturday": "✅ لقد سجلت لـ **حرب السبت**!",
        "registered_sunday": "✅ لقد سجلت لـ **حرب الأحد**!",
        "registered_both": "✅ لقد سجلت لـ **كل من حروب السبت والأحد**!",
        "registered_not_playing": "✅ تم وضع علامة عليك على أنك **لن تلعب** في نهاية هذا الأسبوع.",
        
        # War List
        "war_list_title": "⚔️ قوائم المشاركين في الحرب ⚔️",
        "no_players": "لم يسجل أي لاعبين بعد",
        "footer_builds": "الأوقات معروضة بالتوقيت المحلي الخاص بك • يجب على اللاعبين بدون بناءات استخدام /postbuilds",
        
        # Misc
        "saturday": "السبت",
        "sunday": "الأحد",
        "language_set": "✅ تم تعيين لغة الخادم إلى **{language}**!",
        "commands_synced": "✅ تمت مزامنة الأوامر بنجاح!",
        
        # Build Selection
        "select_build": "اختر نوع البناء الخاص بك",
        "select_weapons": "اختر أسلحتك (1-2)",
        "build_set": "✅ تم تعيين البناء بنجاح!",
        "weapons_set": "✅ تم اختيار الأسلحة بنجاح!",
        "reset_build": "هل أنت متأكد من أنك تريد إعادة تعيين بنائك؟",
        
        # Profile
        "profile_title": "👤 ملف اللاعب الشخصي",
        "in_game_name": "الاسم في اللعبة",
        "level": "المستوى",
        "mastery_points": "نقاط الإتقان",
        "rank": "الترتيب في الخادم",
        "build_type": "نوع البناء",
        "weapons": "الأسلحة",
        "no_profile": "لم يتم العثور على ملف شخصي. استخدم `/setupprofile` لإنشاء واحد!",
    }
}

def get_language(guild_id: int) -> str:
    """Get guild language from database"""
    settings = db.get_server_settings(guild_id)
    return settings.get('language', 'en')

def get_text(guild_id: int, key: str) -> str:
    """Get translated text for a guild"""
    lang = get_language(guild_id)
    return LANGUAGES.get(lang, LANGUAGES['en']).get(key, key)

# -----------------------------
# War System Database Helpers
# -----------------------------
def get_current_poll_week() -> str:
    """Get current poll week identifier (e.g., '2024-W01')"""
    return datetime.now().strftime("%Y-W%U")

def get_war_participants(guild_id: int) -> dict:
    """Get war participants for current poll week"""
    poll_week = get_current_poll_week()
    
    return {
        "saturday_players": set(db.get_war_participants(guild_id, poll_week, "saturday")),
        "sunday_players": set(db.get_war_participants(guild_id, poll_week, "sunday")),
        "both_days_players": set(db.get_war_participants(guild_id, poll_week, "both")),
        "not_playing": set(db.get_war_participants(guild_id, poll_week, "none"))
    }

def set_war_participation(guild_id: int, user_id: int, day_choice: str):
    """Set player's war participation choice"""
    poll_week = get_current_poll_week()
    
    # Set participation (this automatically replaces any existing participation)
    if day_choice in ["saturday", "sunday", "both", "none"]:
        db.set_war_participation(user_id, guild_id, poll_week, day_choice)

def get_war_config(guild_id: int) -> dict:
    """Get war configuration for a guild"""
    settings = db.get_server_settings(guild_id)
    
    return {
        "poll_day": settings.get('poll_day', 'Friday'),
        "poll_time": {
            "hour": int(settings.get('poll_time_hour', 15)),
            "minute": int(settings.get('poll_time_minute', 0))
        },
        "saturday_war": {
            "hour": int(settings.get('saturday_war_hour', 22)),
            "minute": int(settings.get('saturday_war_minute', 30))
        },
        "sunday_war": {
            "hour": int(settings.get('sunday_war_hour', 22)),
            "minute": int(settings.get('sunday_war_minute', 30))
        },
        "reminder_hours": int(settings.get('reminder_hours_before', 2)),
        "war_channel_id": settings.get('war_channel_id'),
        "timezone": settings.get('timezone', 'Africa/Cairo'),
    }

def update_war_setting(guild_id: int, setting: str, value):
    """Update a war configuration setting in database"""
    return db.update_server_setting(guild_id, setting, value)

# -----------------------------
# Build System Data with Icons
# -----------------------------
WEAPON_ICONS = {
    # DPS Weapons
    "Strategic Sword": "<:StrategicSword:1468707686907642110>",
    "Heaven Spear": "<:Heavenspear:1468707949517078539>",
    "Nameless Sword": "<:NamelessSword:1468707969574113411>",
    "Nameless Spear": "<:Namelessspear:1468707652212232333>",
    "Twinblade": "<:Twinblade:1468707797263978601>",
    "Mortal Rope": "<:MortalRobe:1468707859389878332>",
    "Vernal Umbrella": "<:VernalUmbrella:1468707906009436272>",
    "Inkwell Fan": "<:inkwellfan:1468707817379729605>",
    
    # Tank Weapons
    "Thunder Blade": "<:thunderblade:1468707839240311006>",
    "StormBreaker Spear": "<:StormBreakerspear:1468707928272797767>",
    
    # Healer Weapons
    "Panacea Fan": "<:Panaveafan:1468707753156415601>",
    "Soulshade Umbrella": "<:SoulshadeUmbrella:1468707729177706637>",
}

BUILD_ICONS = {
    "DPS": "<:Dps:1469039402113306747>",
    "Tank": "<:Tank:1469039369829748901>",
    "Healer": "<:Healer:1469039348656898158>",
}

BUILDS = {
    "DPS": {
        "emoji": BUILD_ICONS["DPS"],
        "weapons": [
            "Strategic Sword",
            "Heaven Spear",
            "Nameless Sword",
            "Nameless Spear",
            "Twinblade",
            "Mortal Rope",
            "Vernal Umbrella",
            "Inkwell Fan"
        ]
    },
    "Tank": {
        "emoji": BUILD_ICONS["Tank"],
        "weapons": [
            "Thunder Blade",
            "StormBreaker Spear"
        ]
    },
    "Healer": {
        "emoji": BUILD_ICONS["Healer"],
        "weapons": [
            "Panacea Fan",
            "Soulshade Umbrella"
        ]
    }
}

# -----------------------------
# Utility Functions
# -----------------------------
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

# -----------------------------
# Web Server for Health Checks
# -----------------------------
async def handle_health(request):
    """Health check endpoint"""
    return web.Response(text="Bot is running!")

async def start_web_server():
    """Start web server for health checks"""
    app = web.Application()
    app.router.add_get('/', handle_health)
    app.router.add_get('/health', handle_health)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.getenv('PORT', 8081))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    logger.info(f"✅ Web server started on port {port}")
    return runner

# -----------------------------
# Discord UI Components - NEW DROPDOWN VERSION
# -----------------------------
class BuildSelectView(discord.ui.View):
    """View with dropdown to select build type"""
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.select(
        placeholder="Select your build type...",
        custom_id="build_select",
        options=[
            discord.SelectOption(
                label="DPS",
                description="Damage dealer - High damage output",
                emoji=BUILD_ICONS["DPS"],
                value="DPS"
            ),
            discord.SelectOption(
                label="Tank",
                description="Defender - High survivability",
                emoji=BUILD_ICONS["Tank"],
                value="Tank"
            ),
            discord.SelectOption(
                label="Healer",
                description="Support - Heal and buff allies",
                emoji=BUILD_ICONS["Healer"],
                value="Healer"
            ),
        ]
    )
    async def build_select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        """Handle build selection"""
        guild_id = interaction.guild_id
        user_id = interaction.user.id
        build_type = select.values[0]
        
        # Get guild and member for role management
        guild = interaction.guild
        member = interaction.user
        
        # Get current player data to check for old roles
        player = db.get_player(user_id, guild_id)
        old_weapons = db.get_player_weapons(user_id, guild_id)
        
        # Remove old build roles (all builds)
        for build_name in ["DPS", "Tank", "Healer"]:
            role = discord.utils.get(guild.roles, name=build_name)
            if role and role in member.roles:
                await member.remove_roles(role)
        
        # Remove old weapon roles
        for old_weapon in old_weapons:
            weapon_role = discord.utils.get(guild.roles, name=old_weapon)
            if weapon_role and weapon_role in member.roles:
                await member.remove_roles(weapon_role)
        
        if not player:
            # Create basic profile if doesn't exist
            db.create_or_update_player(
                user_id, guild_id,
                interaction.user.name,  # Default name
                0,  # Default mastery
                1,  # Default level
                build_type
            )
        else:
            # Update build type
            db.create_or_update_player(
                user_id, guild_id,
                player['in_game_name'],
                player['mastery_points'],
                player['level'],
                build_type
            )
        
        # Clear previous weapons from database
        db.set_player_weapons(user_id, guild_id, [])
        
        # Show weapon selection
        weapon_view = WeaponSelectView(build_type)
        
        await safe_send_message(interaction, 
            f"{BUILDS[build_type]['emoji']} **Build selected: {build_type}**\n\n"
            f"Now select your weapons (you can select 1-2 weapons):",
            view=weapon_view,
            ephemeral=True
        )


class WeaponSelectView(discord.ui.View):
    """View with dropdown to select weapons (max 2)"""
    def __init__(self, build_type: str):
        super().__init__(timeout=180)  # 3 minute timeout
        self.build_type = build_type
        
        # Create options based on build type
        weapons = BUILDS[build_type]["weapons"]
        options = []
        
        for weapon in weapons[:25]:  # Discord limit is 25 options
            icon = WEAPON_ICONS.get(weapon, "⚔️")
            options.append(
                discord.SelectOption(
                    label=weapon,
                    emoji=icon,
                    value=weapon
                )
            )
        
        # Add select menu
        select = discord.ui.Select(
            placeholder="Select your weapons (1-2)...",
            min_values=1,
            max_values=min(2, len(options)),  # Allow 1-2 selections
            options=options,
            custom_id=f"weapon_select_{build_type}"
        )
        select.callback = self.weapon_select_callback
        self.add_item(select)
    
    async def weapon_select_callback(self, interaction: discord.Interaction):
        """Handle weapon selection"""
        guild_id = interaction.guild_id
        user_id = interaction.user.id
        weapons = interaction.data['values']
        
        # Get current weapons before updating
        old_weapons = db.get_player_weapons(user_id, guild_id)
        
        # Save weapons to database
        db.set_player_weapons(user_id, guild_id, weapons)
        
        # Get player profile
        player = db.get_player(user_id, guild_id)
        
        # Assign roles
        guild = interaction.guild
        member = interaction.user
        
        # Remove old build roles
        for build_name in ["DPS", "Tank", "Healer"]:
            role = discord.utils.get(guild.roles, name=build_name)
            if role and role in member.roles:
                await member.remove_roles(role)
        
        # Remove old weapon roles
        for old_weapon in old_weapons:
            weapon_role = discord.utils.get(guild.roles, name=old_weapon)
            if weapon_role and weapon_role in member.roles:
                await member.remove_roles(weapon_role)
        
        # Add new build role
        build_role = discord.utils.get(guild.roles, name=self.build_type)
        if build_role:
            await member.add_roles(build_role)
        
        # Add weapon roles
        for weapon in weapons:
            weapon_role = discord.utils.get(guild.roles, name=weapon)
            if weapon_role:
                await member.add_roles(weapon_role)
        
        # Format weapons with icons
        weapons_display = "\n".join([
            f"{WEAPON_ICONS.get(w, '⚔️')} {w}" for w in weapons
        ])
        
        await safe_send_message(interaction, 
            f"✅ **Profile Updated!**\n\n"
            f"{BUILDS[self.build_type]['emoji']} **Build:** {self.build_type}\n"
            f"**Weapons:**\n{weapons_display}\n\n"
            f"Roles have been assigned!",
            ephemeral=True
        )


class ProfileSetupButton(discord.ui.View):
    """Single button that opens complete profile form"""
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(
        label="📝 Setup Your Profile",
        style=discord.ButtonStyle.primary,
        custom_id="setup_profile_button",
        emoji="🎮"
    )
    async def setup_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open the complete profile setup form"""
        modal = CompleteProfileModal()
        await safe_send_modal(interaction, modal)


class CompleteProfileModal(discord.ui.Modal, title="🎮 Complete Profile Setup"):
    """All-in-one profile setup modal"""
    
    # Text fields
    ign = discord.ui.TextInput(
        label="In-Game Name",
        placeholder="Enter your character name...",
        required=True,
        max_length=50
    )
    
    level = discord.ui.TextInput(
        label="Level (1-100)",
        placeholder="Enter your level...",
        required=True,
        max_length=3
    )
    
    mastery = discord.ui.TextInput(
        label="Mastery Points",
        placeholder="Enter your mastery/power points...",
        required=True,
        max_length=10
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        """Process the form and show build selection"""
        guild_id = interaction.guild_id
        user_id = interaction.user.id
        
        try:
            # Validate level
            level_val = int(self.level.value)
            if level_val < 1 or level_val > 100:
                await safe_send_message(interaction, 
                    "❌ Level must be between 1 and 100!",
                    ephemeral=True
                )
                return
            
            # Validate mastery
            mastery_val = int(self.mastery.value.replace(",", "").replace(" ", ""))
            if mastery_val < 0:
                await safe_send_message(interaction, 
                    "❌ Mastery points must be positive!",
                    ephemeral=True
                )
                return
            
            # Save basic profile (build will be set after selection)
            db.create_or_update_player(
                user_id, guild_id,
                self.ign.value,
                mastery_val,
                level_val,
                "DPS"  # Default, will be updated
            )
            
            # Update Discord nickname to match in-game name
            member = interaction.user
            nickname_success, nickname_msg = await update_member_nickname(member, self.ign.value)
            
            # Show build selection
            build_view = BuildSelectView()
            
            # Build response message
            response_msg = (
                f"✅ **Basic profile created!**\n\n"
                f"📝 **Name:** {self.ign.value}\n"
                f"⭐ **Level:** {level_val}\n"
                f"⚡ **Mastery:** {mastery_val:,}\n"
            )
            
            # Add nickname status
            if nickname_success:
                response_msg += f"🏷️ {nickname_msg}\n"
            else:
                response_msg += f"{nickname_msg}\n"
            
            response_msg += "\nNow select your build type:"
            
            await safe_send_message(interaction, 
                response_msg,
                view=build_view,
                ephemeral=True
            )
            
        except ValueError:
            await safe_send_message(interaction, 
                "❌ Please enter valid numbers for level and mastery!",
                ephemeral=True
            )


class WarPollButtons(discord.ui.View):
    """Buttons for war poll"""
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(
        label="Saturday Only",
        style=discord.ButtonStyle.primary,
        custom_id="war_saturday",
        emoji="📅"
    )
    async def saturday_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Register for Saturday only"""
        guild_id = interaction.guild_id
        user_id = interaction.user.id
        
        set_war_participation(guild_id, user_id, "saturday")
        
        await safe_send_message(interaction, 
            get_text(guild_id, "registered_saturday"),
            ephemeral=True
        )
        
        # Update poll message
        await self.update_poll_message(interaction)
    
    @discord.ui.button(
        label="Sunday Only",
        style=discord.ButtonStyle.primary,
        custom_id="war_sunday",
        emoji="📅"
    )
    async def sunday_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Register for Sunday only"""
        guild_id = interaction.guild_id
        user_id = interaction.user.id
        
        set_war_participation(guild_id, user_id, "sunday")
        
        await safe_send_message(interaction, 
            get_text(guild_id, "registered_sunday"),
            ephemeral=True
        )
        
        await self.update_poll_message(interaction)
    
    @discord.ui.button(
        label="Both Days",
        style=discord.ButtonStyle.success,
        custom_id="war_both",
        emoji="⚔️"
    )
    async def both_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Register for both days"""
        guild_id = interaction.guild_id
        user_id = interaction.user.id
        
        set_war_participation(guild_id, user_id, "both")
        
        await safe_send_message(interaction, 
            get_text(guild_id, "registered_both"),
            ephemeral=True
        )
        
        await self.update_poll_message(interaction)
    
    @discord.ui.button(
        label="Not Playing",
        style=discord.ButtonStyle.secondary,
        custom_id="war_none",
        emoji="❌"
    )
    async def none_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Register as not playing"""
        guild_id = interaction.guild_id
        user_id = interaction.user.id
        
        set_war_participation(guild_id, user_id, "none")
        
        await safe_send_message(interaction, 
            get_text(guild_id, "registered_not_playing"),
            ephemeral=True
        )
        
        await self.update_poll_message(interaction)
    
    async def update_poll_message(self, interaction: discord.Interaction):
        """Update the poll message with current counts"""
        guild_id = interaction.guild_id
        participants = get_war_participants(guild_id)
        
        saturday_count = len(participants["saturday_players"])
        sunday_count = len(participants["sunday_players"])
        both_count = len(participants["both_days_players"])
        none_count = len(participants["not_playing"])
        
        saturday_total = saturday_count + both_count
        sunday_total = sunday_count + both_count
        
        # Get war times
        config = get_war_config(guild_id)
        saturday_time = get_discord_timestamp(
            config["saturday_war"]["hour"],
            config["saturday_war"]["minute"],
            0 if datetime.now().weekday() == 5 else 1
        )
        sunday_time = get_discord_timestamp(
            config["sunday_war"]["hour"],
            config["sunday_war"]["minute"],
            0 if datetime.now().weekday() == 6 else 1
        )
        
        embed = discord.Embed(
            title=get_text(guild_id, "war_poll_title"),
            description=f"{get_text(guild_id, 'war_poll_desc')}\n\n"
                        f"🗓️ **{get_text(guild_id, 'saturday')}: {saturday_time}**\n"
                        f"🗓️ **{get_text(guild_id, 'sunday')}: {sunday_time}**\n\n"
                        f"*{get_text(guild_id, 'times_local')}*",
            color=discord.Color.red(),
            timestamp=datetime.now()
        )
        
        embed.add_field(
            name=f"📅 {get_text(guild_id, 'saturday_only')} ({saturday_count} {get_text(guild_id, 'players')})",
            value=get_text(guild_id, 'click_button'),
            inline=True
        )
        embed.add_field(
            name=f"📅 {get_text(guild_id, 'sunday_only')} ({sunday_count} {get_text(guild_id, 'players')})",
            value=get_text(guild_id, 'click_button'),
            inline=True
        )
        embed.add_field(
            name=f"⚔️ {get_text(guild_id, 'both_days')} ({both_count} {get_text(guild_id, 'players')})",
            value=get_text(guild_id, 'click_button'),
            inline=True
        )
        embed.add_field(
            name=f"📊 {get_text(guild_id, 'total_saturday')}: {saturday_total}",
            value=get_text(guild_id, 'sat_sun_players'),
            inline=True
        )
        embed.add_field(
            name=f"📊 {get_text(guild_id, 'total_sunday')}: {sunday_total}",
            value=get_text(guild_id, 'sun_both_players'),
            inline=True
        )
        embed.add_field(
            name=f"❌ {get_text(guild_id, 'not_playing')} ({none_count} {get_text(guild_id, 'players')})",
            value=get_text(guild_id, 'click_button'),
            inline=True
        )
        
        embed.set_footer(text=f"{get_text(guild_id, 'use_warlist')}")
        
        try:
            await safe_message_edit(interaction.message, embed=embed)
        except:
            pass  # Message might be deleted

# -----------------------------
# Slash Commands
# -----------------------------

@bot.tree.command(name="help", description="Show all available commands")
async def help_command(interaction: discord.Interaction):
    """Display help message"""
    guild_id = interaction.guild_id
    
    embed = discord.Embed(
        title=get_text(guild_id, "help_title"),
        description=get_text(guild_id, "help_desc"),
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name=get_text(guild_id, "build_commands"),
        value=get_text(guild_id, "build_commands_desc"),
        inline=False
    )
    
    embed.add_field(
        name=get_text(guild_id, "war_commands"),
        value=get_text(guild_id, "war_commands_desc"),
        inline=False
    )
    
    embed.add_field(
        name=get_text(guild_id, "profile_commands"),
        value=get_text(guild_id, "profile_commands_desc"),
        inline=False
    )
    
    embed.add_field(
        name=get_text(guild_id, "system_commands"),
        value=get_text(guild_id, "system_commands_desc"),
        inline=False
    )
    
    await safe_send_message(interaction, embed=embed)


@bot.tree.command(name="postbuilds", description="Post build selection menu (Admin)")
@discord.app_commands.checks.has_permissions(administrator=True)
async def postbuilds(interaction: discord.Interaction):
    """Post build selection menu"""
    guild_id = interaction.guild_id
    
    embed = discord.Embed(
        title="🎮 Build & Weapon Selection",
        description=(
            "Click the button below to set up your complete profile!\n\n"
            "**This includes:**\n"
            "• In-Game Name\n"
            "• Level & Mastery Points\n"
            "• Build Type (DPS/Tank/Healer)\n"
            "• Weapons (select 1-2)\n\n"
            "**Available Builds:**\n"
            f"{BUILD_ICONS['DPS']} **DPS** - High damage output\n"
            f"{BUILD_ICONS['Tank']} **Tank** - High survivability\n"
            f"{BUILD_ICONS['Healer']} **Healer** - Support & healing"
        ),
        color=discord.Color.gold()
    )
    
    # Add weapon lists
    for build_name, build_data in BUILDS.items():
        weapons_with_icons = [
            f"{WEAPON_ICONS.get(w, '⚔️')} {w}" 
            for w in build_data["weapons"]
        ]
        embed.add_field(
            name=f"{build_data['emoji']} {build_name} Weapons",
            value="\n".join(weapons_with_icons) if len(weapons_with_icons) <= 10 else ", ".join([w.split()[-1] for w in weapons_with_icons]),
            inline=False
        )
    
    embed.set_footer(text="Complete your profile in one easy form!")
    
    view = ProfileSetupButton()
    
    await interaction.channel.send(
        content="@everyone",
        embed=embed,
        view=view
    )
    
    await safe_send_message(interaction, 
        "✅ Profile setup message posted!",
        ephemeral=True
    )


@bot.tree.command(name="mybuild", description="View your current build")
async def mybuild(interaction: discord.Interaction):
    """Show user's current build"""
    guild_id = interaction.guild_id
    user_id = interaction.user.id
    
    # Get player from database
    player = db.get_player(user_id, guild_id)
    
    if not player:
        await safe_send_message(interaction, 
            "❌ You don't have a build set yet! Use `/postbuilds` to select one.",
            ephemeral=True
        )
        return
    
    # Get weapons
    weapons = db.get_player_weapons(user_id, guild_id)
    
    build_type = player.get('build_type', 'DPS')
    build_icon = BUILDS.get(build_type, {}).get('emoji', '⚔️')
    
    weapons_display = "\n".join([
        f"{WEAPON_ICONS.get(w, '⚔️')} {w}" for w in weapons
    ]) if weapons else "No weapons selected"
    
    embed = discord.Embed(
        title=f"{build_icon} Your Build",
        description=f"**Build Type:** {build_type}\n\n**Weapons:**\n{weapons_display}",
        color=discord.Color.green()
    )
    
    # Add profile stats if available
    if player.get('in_game_name'):
        embed.add_field(
            name="📝 Profile Info",
            value=(
                f"**Name:** {player['in_game_name']}\n"
                f"**Level:** {player['level']}\n"
                f"**Mastery:** {player['mastery_points']:,}"
            ),
            inline=False
        )
    
    await safe_send_message(interaction, embed=embed, ephemeral=True)


@bot.tree.command(name="resetbuild", description="Reset and change your build")
async def resetbuild(interaction: discord.Interaction):
    """Reset user's build"""
    guild_id = interaction.guild_id
    user_id = interaction.user.id
    
    # Get current build
    player = db.get_player(user_id, guild_id)
    
    if not player:
        await safe_send_message(interaction, 
            "❌ You don't have a build to reset!",
            ephemeral=True
        )
        return
    
    # Remove all build roles
    guild = interaction.guild
    member = interaction.user
    
    for build_name in ["DPS", "Tank", "Healer"]:
        role = discord.utils.get(guild.roles, name=build_name)
        if role and role in member.roles:
            await member.remove_roles(role)
    
    # Remove weapon roles
    weapons = db.get_player_weapons(user_id, guild_id)
    for weapon in weapons:
        weapon_role = discord.utils.get(guild.roles, name=weapon)
        if weapon_role and weapon_role in member.roles:
            await member.remove_roles(weapon_role)
    
    # Clear weapons from database
    db.set_player_weapons(user_id, guild_id, [])
    
    # Show build selection
    build_view = BuildSelectView()
    
    await safe_send_message(interaction, 
        "✅ **Build reset!**\n\nSelect your new build type:",
        view=build_view,
        ephemeral=True
    )


@bot.tree.command(name="createroles", description="Create all build and weapon roles (Admin)")
@discord.app_commands.checks.has_permissions(administrator=True)
async def createroles(interaction: discord.Interaction):
    """Create all necessary roles"""
    guild = interaction.guild
    created = []
    existing = []
    
    # Create build roles
    for build_name in ["DPS", "Tank", "Healer"]:
        role = discord.utils.get(guild.roles, name=build_name)
        if not role:
            await guild.create_role(name=build_name)
            created.append(build_name)
        else:
            existing.append(build_name)
    
    # Create weapon roles
    all_weapons = set()
    for build_data in BUILDS.values():
        all_weapons.update(build_data["weapons"])
    
    for weapon in all_weapons:
        role = discord.utils.get(guild.roles, name=weapon)
        if not role:
            await guild.create_role(name=weapon)
            created.append(weapon)
        else:
            existing.append(weapon)
    
    result = f"✅ **Roles Created:** {len(created)}\n"
    if created:
        result += f"Created: {', '.join(created[:10])}"
        if len(created) > 10:
            result += f" ... and {len(created) - 10} more"
    
    if existing:
        result += f"\n\n**Already Existed:** {len(existing)}"
    
    await safe_send_message(interaction, result, ephemeral=True)


# Profile Commands
@bot.tree.command(name="setupprofile", description="Set up your complete profile (guided)")
async def setupprofile(interaction: discord.Interaction):
    """Start guided profile setup"""
    modal = CompleteProfileModal()
    await safe_send_modal(interaction, modal)


@bot.tree.command(name="setprofile", description="Quick profile update")
@discord.app_commands.describe(
    in_game_name="Your character name in the game",
    mastery_points="Your total mastery/power points",
    level="Your character level (1-100)"
)
async def setprofile(
    interaction: discord.Interaction,
    in_game_name: str,
    mastery_points: int,
    level: int
):
    """Set or update player profile"""
    guild_id = interaction.guild_id
    user_id = interaction.user.id
    
    # Validate
    if level < 1 or level > 100:
        await safe_send_message(interaction, 
            "❌ Level must be between 1 and 100!",
            ephemeral=True
        )
        return
    
    if mastery_points < 0:
        await safe_send_message(interaction, 
            "❌ Mastery points must be positive!",
            ephemeral=True
        )
        return
    
    # Get existing profile
    player = db.get_player(user_id, guild_id)
    build_type = player.get('build_type', 'DPS') if player else 'DPS'
    
    # Save profile
    db.create_or_update_player(
        user_id, guild_id,
        in_game_name,
        mastery_points,
        level,
        build_type
    )
    
    # Update Discord nickname to match in-game name
    member = interaction.user
    nickname_success, nickname_msg = await update_member_nickname(member, in_game_name)
    
    # Calculate rank
    all_players_dict = db.get_all_players(guild_id)
    all_players = list(all_players_dict.values())
    sorted_players = sorted(all_players, key=lambda p: p['mastery_points'], reverse=True)
    rank = next((i+1 for i, p in enumerate(sorted_players) if p['user_id'] == user_id), 0)
    
    embed = discord.Embed(
        title="✅ Profile Updated!",
        description=(
            f"**In-Game Name:** {in_game_name}\n"
            f"**Level:** {level}\n"
            f"**Mastery Points:** {mastery_points:,}\n"
            f"**Server Rank:** #{rank}"
        ),
        color=discord.Color.green()
    )
    
    if player:
        weapons = db.get_player_weapons(user_id, guild_id)
        if weapons:
            weapons_display = "\n".join([
                f"{WEAPON_ICONS.get(w, '⚔️')} {w}" for w in weapons
            ])
            embed.add_field(
                name=f"{BUILDS[build_type]['emoji']} Current Build",
                value=f"**{build_type}**\n{weapons_display}",
                inline=False
            )
    
    # Add nickname update status to footer
    if nickname_success:
        embed.set_footer(text=f"✅ {nickname_msg}")
    else:
        embed.set_footer(text=nickname_msg)
    
    await safe_send_message(interaction, embed=embed)


@bot.tree.command(name="profile", description="View player profile")
@discord.app_commands.describe(user="The user to view (optional, defaults to yourself)")
async def profile(interaction: discord.Interaction, user: discord.User = None):
    """View player profile"""
    guild_id = interaction.guild_id
    target_user = user or interaction.user
    user_id = target_user.id
    
    # Get player from database
    player = db.get_player(user_id, guild_id)
    
    if not player:
        await safe_send_message(interaction, 
            get_text(guild_id, "no_profile"),
            ephemeral=True
        )
        return
    
    # Get weapons
    weapons = db.get_player_weapons(user_id, guild_id)
    
    # Calculate rank
    all_players_dict = db.get_all_players(guild_id)
    all_players = list(all_players_dict.values())
    sorted_players = sorted(all_players, key=lambda p: p['mastery_points'], reverse=True)
    rank = next((i+1 for i, p in enumerate(sorted_players) if p['user_id'] == user_id), 0)
    
    build_type = player.get('build_type', 'DPS')
    build_icon = BUILDS.get(build_type, {}).get('emoji', '⚔️')
    
    embed = discord.Embed(
        title=f"👤 {player['in_game_name']}",
        description=f"Profile for {target_user.mention}",
        color=discord.Color.blue()
    )
    
    embed.set_thumbnail(url=target_user.display_avatar.url)
    
    embed.add_field(
        name="📊 Stats",
        value=(
            f"**Level:** {player['level']}\n"
            f"**Mastery:** {player['mastery_points']:,}\n"
            f"**Rank:** #{rank}"
        ),
        inline=True
    )
    
    weapons_display = "\n".join([
        f"{WEAPON_ICONS.get(w, '⚔️')} {w}" for w in weapons
    ]) if weapons else "Not set"
    
    embed.add_field(
        name=f"{build_icon} Build",
        value=f"**{build_type}**\n\n{weapons_display}",
        inline=True
    )
    
    await safe_send_message(interaction, embed=embed)


@bot.tree.command(name="updatestats", description="Update your mastery points or level")
@discord.app_commands.describe(
    mastery_points="Your new mastery points (optional)",
    level="Your new level (optional)"
)
async def updatestats(
    interaction: discord.Interaction,
    mastery_points: int = None,
    level: int = None
):
    """Quick update for mastery/level"""
    guild_id = interaction.guild_id
    user_id = interaction.user.id
    
    player = db.get_player(user_id, guild_id)
    
    if not player:
        await safe_send_message(interaction, 
            "❌ You don't have a profile! Use `/setprofile` first.",
            ephemeral=True
        )
        return
    
    # Validate
    if level is not None and (level < 1 or level > 100):
        await safe_send_message(interaction, 
            "❌ Level must be between 1 and 100!",
            ephemeral=True
        )
        return
    
    if mastery_points is not None and mastery_points < 0:
        await safe_send_message(interaction, 
            "❌ Mastery points must be positive!",
            ephemeral=True
        )
        return
    
    # Update
    new_mastery = mastery_points if mastery_points is not None else player['mastery_points']
    new_level = level if level is not None else player['level']
    
    db.create_or_update_player(
        user_id, guild_id,
        player['in_game_name'],
        new_mastery,
        new_level,
        player['build_type']
    )
    
    # Calculate new rank
    all_players_dict = db.get_all_players(guild_id)
    all_players = list(all_players_dict.values())
    sorted_players = sorted(all_players, key=lambda p: p['mastery_points'], reverse=True)
    rank = next((i+1 for i, p in enumerate(sorted_players) if p['user_id'] == user_id), 0)
    
    await safe_send_message(interaction, 
        f"✅ **Stats Updated!**\n\n"
        f"**Level:** {new_level}\n"
        f"**Mastery:** {new_mastery:,}\n"
        f"**Rank:** #{rank}"
    )


@bot.tree.command(name="changename", description="Change your in-game name and server nickname")
@discord.app_commands.describe(new_name="Your new in-game name")
async def changename(interaction: discord.Interaction, new_name: str):
    """Change player's in-game name and update server nickname"""
    guild_id = interaction.guild_id
    user_id = interaction.user.id
    
    # Check if player has a profile
    player = db.get_player(user_id, guild_id)
    
    if not player:
        await safe_send_message(interaction, 
            "❌ You don't have a profile! Use `/setupprofile` first.",
            ephemeral=True
        )
        return
    
    # Validate name length
    if len(new_name) < 1:
        await safe_send_message(interaction, 
            "❌ Name cannot be empty!",
            ephemeral=True
        )
        return
    
    # Store old name for confirmation message
    old_name = player['in_game_name']
    
    # Update in database
    db.create_or_update_player(
        user_id, guild_id,
        new_name,
        player['mastery_points'],
        player['level'],
        player['build_type']
    )
    
    # Try to update server nickname
    member = interaction.user
    nickname_success, nickname_msg = await update_member_nickname(member, new_name)
    
    # Create response
    embed = discord.Embed(
        title="✅ Name Changed!",
        description=f"**Old Name:** {old_name}\n**New Name:** {new_name}",
        color=discord.Color.green()
    )
    
    # Add nickname update status
    if nickname_success:
        embed.set_footer(text=f"✅ {nickname_msg}")
    else:
        embed.set_footer(text=nickname_msg)
    
    await safe_send_message(interaction, embed=embed)


@bot.tree.command(name="leaderboard", description="View server leaderboard")
@discord.app_commands.describe(
    sort_by="Sort by mastery points or level",
    limit="Number of players to show"
)
@discord.app_commands.choices(
    sort_by=[
        discord.app_commands.Choice(name="Mastery Points", value="mastery"),
        discord.app_commands.Choice(name="Level", value="level")
    ],
    limit=[
        discord.app_commands.Choice(name="Top 10", value=10),
        discord.app_commands.Choice(name="Top 25", value=25),
        discord.app_commands.Choice(name="Top 50", value=50),
        discord.app_commands.Choice(name="Top 100", value=100)
    ]
)
async def leaderboard(
    interaction: discord.Interaction,
    sort_by: str = "mastery",
    limit: int = 10
):
    """Display server leaderboard"""
    guild_id = interaction.guild_id
    guild = interaction.guild
    
    # Get all players - returns dict keyed by user_id
    all_players_dict = db.get_all_players(guild_id)
    
    if not all_players_dict:
        await safe_send_message(interaction, 
            "❌ No players have profiles yet!",
            ephemeral=True
        )
        return
    
    # Convert dict to list of player objects
    all_players = list(all_players_dict.values())
    
    # Sort
    if sort_by == "level":
        sorted_players = sorted(all_players, key=lambda p: (p['level'], p['mastery_points']), reverse=True)
        sort_label = "Level"
    else:
        sorted_players = sorted(all_players, key=lambda p: p['mastery_points'], reverse=True)
        sort_label = "Mastery Points"
    
    # Limit
    top_players = sorted_players[:limit]
    
    embed = discord.Embed(
        title=f"🏆 Server Leaderboard",
        description=f"Top {len(top_players)} Players by {sort_label}",
        color=discord.Color.gold()
    )
    
    leaderboard_text = []
    
    for i, player in enumerate(top_players, 1):
        # Get user
        user = guild.get_member(player['user_id'])
        if not user:
            continue
        
        # Medal for top 3
        if i == 1:
            medal = "🥇"
        elif i == 2:
            medal = "🥈"
        elif i == 3:
            medal = "🥉"
        else:
            medal = f"**{i}.**"
        
        build_icon = BUILDS.get(player.get('build_type', 'DPS'), {}).get('emoji', '⚔️')
        
        player_line = (
            f"{medal} {player['in_game_name']} {build_icon}\n"
            f"    ⚡ {player['mastery_points']:,} MP • Lv.{player['level']}"
        )
        
        leaderboard_text.append(player_line)
    
    embed.description += "\n\n" + "\n\n".join(leaderboard_text)
    
    # Show user's rank if not in top
    user_id = interaction.user.id
    user_rank = next((i+1 for i, p in enumerate(sorted_players) if p['user_id'] == user_id), None)
    
    if user_rank and user_rank > limit:
        user_player = next((p for p in sorted_players if p['user_id'] == user_id), None)
        if user_player:
            embed.set_footer(
                text=f"Your rank: #{user_rank} • {user_player['mastery_points']:,} MP • Lv.{user_player['level']}"
            )
    
    await safe_send_message(interaction, embed=embed)


# War Commands
@bot.tree.command(name="warpoll", description="Post war participation poll (Admin)")
@discord.app_commands.checks.has_permissions(administrator=True)
async def warpoll(interaction: discord.Interaction):
    """Post war poll"""
    guild_id = interaction.guild_id
    config = get_war_config(guild_id)
    
    # Validate channel
    channel_id = config.get("war_channel_id")
    if not channel_id:
        await safe_send_message(interaction, 
            "❌ War channel not configured! Use `/setwar setting:war_channel value:#channel`",
            ephemeral=True
        )
        return
    
    channel = interaction.guild.get_channel(channel_id)
    if not channel:
        await safe_send_message(interaction, 
            "❌ Configured war channel not found!",
            ephemeral=True
        )
        return
    
    # Get war times with guild's timezone
    guild_timezone = config.get("timezone", "Africa/Cairo")
    
    # Calculate days ahead for Saturday and Sunday
    now = datetime.now(pytz.timezone(guild_timezone))
    current_weekday = now.weekday()  # 0=Monday, 5=Saturday, 6=Sunday
    
    # Days until next Saturday (5)
    if current_weekday < 5:
        days_to_saturday = 5 - current_weekday
    elif current_weekday == 5:
        days_to_saturday = 0  # Today is Saturday
    else:  # Sunday
        days_to_saturday = 6  # Next Saturday
    
    # Days until next Sunday (6)
    if current_weekday < 6:
        days_to_sunday = 6 - current_weekday
    elif current_weekday == 6:
        days_to_sunday = 0  # Today is Sunday
    else:  # Should never happen but just in case
        days_to_sunday = 7
    
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
    
    embed = discord.Embed(
        title=get_text(guild_id, "war_poll_title"),
        description=f"{get_text(guild_id, 'war_poll_desc')}\n\n"
                    f"🗓️ **{get_text(guild_id, 'saturday')}: {saturday_time}**\n"
                    f"🗓️ **{get_text(guild_id, 'sunday')}: {sunday_time}**\n\n"
                    f"*{get_text(guild_id, 'times_local')}*",
        color=discord.Color.red(),
        timestamp=datetime.now()
    )
    
    embed.add_field(
        name=f"📅 {get_text(guild_id, 'saturday_only')} (0 {get_text(guild_id, 'players')})",
        value=get_text(guild_id, 'click_button'),
        inline=True
    )
    embed.add_field(
        name=f"📅 {get_text(guild_id, 'sunday_only')} (0 {get_text(guild_id, 'players')})",
        value=get_text(guild_id, 'click_button'),
        inline=True
    )
    embed.add_field(
        name=f"⚔️ {get_text(guild_id, 'both_days')} (0 {get_text(guild_id, 'players')})",
        value=get_text(guild_id, 'click_button'),
        inline=True
    )
    embed.add_field(
        name=f"📊 {get_text(guild_id, 'total_saturday')}: 0",
        value=get_text(guild_id, 'sat_sun_players'),
        inline=True
    )
    embed.add_field(
        name=f"📊 {get_text(guild_id, 'total_sunday')}: 0",
        value=get_text(guild_id, 'sun_both_players'),
        inline=True
    )
    embed.add_field(
        name=f"❌ {get_text(guild_id, 'not_playing')} (0 {get_text(guild_id, 'players')})",
        value=get_text(guild_id, 'click_button'),
        inline=True
    )
    
    embed.set_footer(text=f"{get_text(guild_id, 'use_warlist')}")
    
    view = WarPollButtons()
    
    await channel.send(
        content="@everyone",
        embed=embed,
        view=view
    )
    
    await safe_send_message(interaction, 
        "✅ War poll posted!",
        ephemeral=True
    )


@bot.tree.command(name="warlist", description="Show war participant lists")
@discord.app_commands.describe(day="Which day to show (optional)")
@discord.app_commands.choices(day=[
    discord.app_commands.Choice(name="Saturday", value="saturday"),
    discord.app_commands.Choice(name="Sunday", value="sunday")
])
async def warlist(interaction: discord.Interaction, day: str = None):
    """Show war participants"""
    guild_id = interaction.guild_id
    guild = interaction.guild
    
    participants = get_war_participants(guild_id)
    
    # Determine which days to show
    if day == "saturday":
        days_to_show = [("saturday", "Saturday")]
    elif day == "sunday":
        days_to_show = [("sunday", "Sunday")]
    else:
        days_to_show = [("saturday", "Saturday"), ("sunday", "Sunday")]
    
    embed = discord.Embed(
        title=get_text(guild_id, "war_list_title"),
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    
    for day_key, day_name in days_to_show:
        # Get participants for this day
        if day_key == "saturday":
            player_ids = participants["saturday_players"] | participants["both_days_players"]
        else:
            player_ids = participants["sunday_players"] | participants["both_days_players"]
        
        if not player_ids:
            embed.add_field(
                name=f"📅 {day_name} ({get_text(guild_id, 'no_players')})",
                value=get_text(guild_id, 'no_players'),
                inline=False
            )
            continue
        
        # Group by build type
        build_groups = {"DPS": [], "Tank": [], "Healer": []}
        
        for user_id in player_ids:
            user = guild.get_member(user_id)
            if not user:
                continue
            
            player = db.get_player(user_id, guild_id)
            
            if not player:
                # No profile
                build_groups["DPS"].append(f"• {user.mention} (No profile)")
                continue
            
            build_type = player.get('build_type', 'DPS')
            weapons = db.get_player_weapons(user_id, guild_id)
            
            weapons_str = ", ".join([
                f"{WEAPON_ICONS.get(w, '⚔️')} {w}" for w in weapons
            ]) if weapons else "No weapons"
            
            player_line = (
                f"• **{player['in_game_name']}** ({user.mention}) | "
                f"Lv.{player['level']} • ⚡ {player['mastery_points']:,} MP\n"
                f"    └ {weapons_str}"
            )
            
            build_groups[build_type].append(player_line)
        
        # Create field for this day
        day_text = f"📅 **{day_name}** ({len(player_ids)} players)\n\n"
        
        for build_name in ["DPS", "Tank", "Healer"]:
            if build_groups[build_name]:
                build_icon = BUILDS[build_name]["emoji"]
                day_text += f"{build_icon} **{build_name}** ({len(build_groups[build_name])})\n"
                day_text += "\n".join(build_groups[build_name])
                day_text += "\n\n"
        
        # Discord field limit is 1024
        if len(day_text) > 1024:
            day_text = day_text[:1020] + "..."
        
        embed.add_field(
            name=f"🗓️ {day_name}",
            value=day_text,
            inline=False
        )
    
    embed.set_footer(text=get_text(guild_id, "footer_builds"))
    
    await safe_send_message(interaction, embed=embed)


@bot.tree.command(name="setwar", description="Configure war settings (Admin)")
@discord.app_commands.checks.has_permissions(administrator=True)
@discord.app_commands.describe(
    setting="The setting to change",
    value="The new value"
)
@discord.app_commands.choices(setting=[
    discord.app_commands.Choice(name="Poll Day", value="poll_day"),
    discord.app_commands.Choice(name="Poll Time (HH:MM)", value="poll_time"),
    discord.app_commands.Choice(name="Saturday War Time (HH:MM)", value="saturday_time"),
    discord.app_commands.Choice(name="Sunday War Time (HH:MM)", value="sunday_time"),
    discord.app_commands.Choice(name="Reminder Hours Before", value="reminder_hours"),
    discord.app_commands.Choice(name="War Channel", value="war_channel"),
    discord.app_commands.Choice(name="Timezone", value="timezone")
])
async def setwar(interaction: discord.Interaction, setting: str, value: str):
    """Configure war settings"""
    guild_id = interaction.guild_id
    
    # Validate and save
    if setting == "war_channel":
        # Parse channel mention
        channel_id = value.replace("<#", "").replace(">", "")
        try:
            channel_id = int(channel_id)
            channel = interaction.guild.get_channel(channel_id)
            if not channel:
                await safe_send_message(interaction, 
                    "❌ Channel not found!",
                    ephemeral=True
                )
                return
            update_war_setting(guild_id, "war_channel_id", channel_id)
        except ValueError:
            await safe_send_message(interaction, 
                "❌ Invalid channel! Mention the channel like #war-channel",
                ephemeral=True
            )
            return
    
    elif setting in ["poll_time", "saturday_time", "sunday_time"]:
        # Validate time format
        if ":" not in value:
            await safe_send_message(interaction, 
                "❌ Invalid time format! Use HH:MM (e.g., 15:00)",
                ephemeral=True
            )
            return
        
        try:
            hour, minute = value.split(":")
            hour = int(hour)
            minute = int(minute)
            if hour < 0 or hour > 23 or minute < 0 or minute > 59:
                raise ValueError
        except ValueError:
            await safe_send_message(interaction, 
                "❌ Invalid time! Use 24-hour format (e.g., 15:00 for 3 PM)",
                ephemeral=True
            )
            return
        
        # Map setting to correct database columns
        if setting == "poll_time":
            db.update_server_setting(guild_id, 'poll_time_hour', hour)
            db.update_server_setting(guild_id, 'poll_time_minute', minute)
        elif setting == "saturday_time":
            db.update_server_setting(guild_id, 'saturday_war_hour', hour)
            db.update_server_setting(guild_id, 'saturday_war_minute', minute)
        elif setting == "sunday_time":
            db.update_server_setting(guild_id, 'sunday_war_hour', hour)
            db.update_server_setting(guild_id, 'sunday_war_minute', minute)
    
    elif setting == "reminder_hours":
        try:
            hours = int(value)
            if hours < 0 or hours > 24:
                raise ValueError
            db.update_server_setting(guild_id, 'reminder_hours_before', hours)
        except ValueError:
            await safe_send_message(interaction, 
                "❌ Invalid hours! Must be between 0 and 24",
                ephemeral=True
            )
            return
    
    elif setting == "poll_day":
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        if value.title() not in days:
            await safe_send_message(interaction, 
                f"❌ Invalid day! Choose from: {', '.join(days)}",
                ephemeral=True
            )
            return
        db.update_server_setting(guild_id, setting, value.title())
    
    elif setting == "timezone":
        # Validate timezone
        try:
            pytz.timezone(value)
            db.update_server_setting(guild_id, 'timezone', value)
        except pytz.exceptions.UnknownTimeZoneError:
            await safe_send_message(interaction, 
                f"❌ Invalid timezone! Examples: Africa/Cairo, Europe/London, America/New_York, Asia/Dubai\n"
                f"See full list: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones",
                ephemeral=True
            )
            return
    
    else:
        db.update_server_setting(guild_id, setting, value)
    
    await safe_send_message(interaction, 
        f"✅ Setting **{setting}** updated to **{value}**!",
        ephemeral=True
    )


@bot.tree.command(name="warconfig", description="View current war configuration")
async def warconfig(interaction: discord.Interaction):
    """Show war configuration"""
    guild_id = interaction.guild_id
    config = get_war_config(guild_id)
    
    channel_id = config.get("war_channel_id")
    channel_mention = f"<#{channel_id}>" if channel_id else "Not set"
    
    embed = discord.Embed(
        title="⚙️ War Configuration",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="📅 Poll Schedule",
        value=(
            f"**Day:** {config['poll_day']}\n"
            f"**Time:** {config['poll_time']['hour']:02d}:{config['poll_time']['minute']:02d}"
        ),
        inline=True
    )
    
    embed.add_field(
        name="⚔️ War Times",
        value=(
            f"**Saturday:** {config['saturday_war']['hour']:02d}:{config['saturday_war']['minute']:02d}\n"
            f"**Sunday:** {config['sunday_war']['hour']:02d}:{config['sunday_war']['minute']:02d}"
        ),
        inline=True
    )
    
    embed.add_field(
        name="🔔 Reminders",
        value=f"**{config['reminder_hours']} hours before war**",
        inline=True
    )
    
    embed.add_field(
        name="📺 Channel",
        value=channel_mention,
        inline=False
    )
    
    embed.add_field(
        name="🌍 Timezone",
        value=f"**{config['timezone']}**\n*Times will be shown in each user's local timezone*",
        inline=False
    )
    
    embed.set_footer(text="Use /setwar to change settings")
    
    await safe_send_message(interaction, embed=embed)


@bot.tree.command(name="testreminder", description="Test war reminder (Admin)")
@discord.app_commands.checks.has_permissions(administrator=True)
@discord.app_commands.describe(day="Which day to test")
@discord.app_commands.choices(day=[
    discord.app_commands.Choice(name="Saturday", value="saturday"),
    discord.app_commands.Choice(name="Sunday", value="sunday")
])
async def testreminder(interaction: discord.Interaction, day: str):
    """Test war reminder"""
    guild_id = interaction.guild_id
    config = get_war_config(guild_id)
    
    channel_id = config.get("war_channel_id")
    if not channel_id:
        await safe_send_message(interaction, 
            "❌ War channel not configured!",
            ephemeral=True
        )
        return
    
    channel = interaction.guild.get_channel(channel_id)
    if not channel:
        await safe_send_message(interaction, 
            "❌ War channel not found!",
            ephemeral=True
        )
        return
    
    # Get participants
    participants = get_war_participants(guild_id)
    
    if day == "saturday":
        player_ids = participants["saturday_players"] | participants["both_days_players"]
        war_time = f"{config['saturday_war']['hour']:02d}:{config['saturday_war']['minute']:02d}"
    else:
        player_ids = participants["sunday_players"] | participants["both_days_players"]
        war_time = f"{config['sunday_war']['hour']:02d}:{config['sunday_war']['minute']:02d}"
    
    # Create mentions
    if player_ids:
        mentions = " ".join([f"<@{uid}>" for uid in player_ids])
    else:
        mentions = "@everyone"
    
    embed = discord.Embed(
        title=f"⚔️ {day.title()} War Reminder! ⚔️",
        description=(
            f"War starts in {config['reminder_hours']} hours at **{war_time}**!\n\n"
            f"**{len(player_ids)} warriors** are ready for battle!"
        ),
        color=discord.Color.red()
    )
    
    await channel.send(content=mentions, embed=embed)
    
    await safe_send_message(interaction, 
        f"✅ Test reminder sent to {channel.mention}!",
        ephemeral=True
    )


# System Commands
@bot.tree.command(name="setlanguage", description="Set server language (Admin)")
@discord.app_commands.checks.has_permissions(administrator=True)
@discord.app_commands.describe(language="The language to use")
@discord.app_commands.choices(language=[
    discord.app_commands.Choice(name="English", value="en"),
    discord.app_commands.Choice(name="Arabic", value="ar")
])
async def setlanguage(interaction: discord.Interaction, language: str):
    """Set server language"""
    guild_id = interaction.guild_id
    
    db.update_server_setting(guild_id, 'language', language)
    
    lang_name = "English" if language == "en" else "Arabic"
    
    await safe_send_message(interaction, 
        get_text(guild_id, "language_set").format(language=lang_name)
    )


@bot.tree.command(name="synccommands", description="Force sync slash commands (Admin)")
@discord.app_commands.checks.has_permissions(administrator=True)
async def synccommands(interaction: discord.Interaction):
    """Force command sync"""
    await interaction.response.defer(ephemeral=True)
    
    try:
        synced = await bot.tree.sync()
        await interaction.followup.send(
            f"{get_text(interaction.guild_id, 'commands_synced')}\n"
            f"Synced {len(synced)} commands.",
            ephemeral=True
        )
    except Exception as e:
        await interaction.followup.send(
            f"❌ Error syncing commands: {str(e)}",
            ephemeral=True
        )


@bot.tree.command(name="resetwar", description="🔄 Reset current week's war data (Admin)")
@discord.app_commands.describe(
    confirm="Type 'CONFIRM' to reset war data"
)
@discord.app_commands.checks.has_permissions(administrator=True)
async def reset_war(interaction: discord.Interaction, confirm: str):
    """Reset war participation data and tracking for current week"""
    
    # Require confirmation
    if confirm != "CONFIRM":
        embed = discord.Embed(
            title="⚠️ Reset War Data",
            description=(
                "This will clear:\n"
                "• All war participants (Saturday/Sunday/Both)\n"
                "• Poll tracking (allows new poll to be posted)\n"
                "• Reminder tracking (allows reminders to be sent again)\n\n"
                "**This action cannot be undone!**\n\n"
                "To confirm, use:\n"
                "`/resetwar confirm:CONFIRM`"
            ),
            color=discord.Color.orange()
        )
        await safe_send_message(interaction, embed=embed, ephemeral=True)
        return
    
    try:
        await interaction.response.defer(ephemeral=True)
        
        guild_id = interaction.guild_id
        poll_week = get_current_poll_week()
        
        # Clear war participants
        db.clear_war_participants(guild_id, poll_week)
        
        # Clear event tracking (polls and reminders)
        cursor = db.conn.cursor()
        cursor.execute("""
            DELETE FROM sent_events 
            WHERE guild_id = ? AND event_week = ?
        """, (guild_id, poll_week))
        db.conn.commit()
        
        embed = discord.Embed(
            title="✅ War Data Reset Complete",
            description=(
                "Successfully cleared:\n"
                "• ✅ All war participants\n"
                "• ✅ Poll tracking (new poll can be posted)\n"
                "• ✅ Reminder tracking (reminders can be sent)\n\n"
                "The war poll can now be posted again automatically or manually with `/warpoll`"
            ),
            color=discord.Color.green()
        )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        logger.info(f"🔄 Admin {interaction.user.name} reset war data for guild {interaction.guild.name}")
        
    except Exception as e:
        logger.error(f"Error resetting war data: {e}")
        await interaction.followup.send(
            f"❌ Error resetting war data: {str(e)}",
            ephemeral=True
        )


@bot.tree.command(name="resetallwar", description="🔄 Reset ALL war data including old weeks (Admin)")
@discord.app_commands.describe(
    confirm="Type 'CONFIRM' to reset ALL war data"
)
@discord.app_commands.checks.has_permissions(administrator=True)
async def reset_all_war(interaction: discord.Interaction, confirm: str):
    """Reset all war data across all weeks (complete reset)"""
    
    # Require confirmation
    if confirm != "CONFIRM":
        embed = discord.Embed(
            title="⚠️ Reset ALL War Data",
            description=(
                "This will clear:\n"
                "• All war participants from ALL weeks\n"
                "• All poll tracking from ALL weeks\n"
                "• All reminder tracking from ALL weeks\n\n"
                "**This is a complete wipe and cannot be undone!**\n\n"
                "To confirm, use:\n"
                "`/resetallwar confirm:CONFIRM`"
            ),
            color=discord.Color.red()
        )
        await safe_send_message(interaction, embed=embed, ephemeral=True)
        return
    
    try:
        await interaction.response.defer(ephemeral=True)
        
        guild_id = interaction.guild_id
        
        # Clear all war participants for this guild
        cursor = db.conn.cursor()
        cursor.execute("""
            DELETE FROM war_participants WHERE guild_id = ?
        """, (guild_id,))
        
        # Clear all event tracking for this guild
        cursor.execute("""
            DELETE FROM sent_events WHERE guild_id = ?
        """, (guild_id,))
        
        db.conn.commit()
        
        embed = discord.Embed(
            title="✅ Complete War Reset Done",
            description=(
                "Successfully cleared:\n"
                "• ✅ All war participants (all weeks)\n"
                "• ✅ All poll tracking (all weeks)\n"
                "• ✅ All reminder tracking (all weeks)\n\n"
                "Your war system is now completely reset!"
            ),
            color=discord.Color.green()
        )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        logger.info(f"🔄 Admin {interaction.user.name} did COMPLETE war reset for guild {interaction.guild.name}")
        
    except Exception as e:
        logger.error(f"Error resetting all war data: {e}")
        await interaction.followup.send(
            f"❌ Error resetting war data: {str(e)}",
            ephemeral=True
        )


# -----------------------------
# Scheduled Tasks
# -----------------------------
@tasks.loop(minutes=5)  # Changed to 5 minutes for easier testing
async def check_war_poll_schedule():
    """Check if it's time to post war poll"""
    try:
        for guild in bot.guilds:
            try:
                config = get_war_config(guild.id)
                guild_timezone = config["timezone"]
                
                # Get current time in guild's timezone
                now = datetime.now(pytz.timezone(guild_timezone))
                current_day = now.strftime("%A")
                current_hour = now.hour
                current_minute = now.minute
                
                logger.info(f"📊 Poll Check: {guild.name} | Now: {current_day} {current_hour:02d}:{current_minute:02d} | Target: {config['poll_day']} {config['poll_time']['hour']:02d}:{config['poll_time']['minute']:02d}")
                
                # Check if it's poll day and time
                if config["poll_day"] == current_day:
                    poll_hour = config["poll_time"]["hour"]
                    poll_minute = config["poll_time"]["minute"]
                    
                    # Check if within 5-minute window
                    time_diff = abs((poll_hour * 60 + poll_minute) - (current_hour * 60 + current_minute))
                    
                    if time_diff < 5:
                        # Check if already posted this week
                        poll_week = get_current_poll_week()
                        
                        # Check if poll was already posted this week
                        if not db.was_event_sent(guild.id, "war_poll", poll_week):
                            channel_id = config.get("war_channel_id")
                            if channel_id:
                                channel = guild.get_channel(channel_id)
                                if channel:
                                    logger.info(f"📊 Auto-posting war poll for guild {guild.name}")
                                    
                                    # Clear previous week's participants
                                    db.clear_war_participants(guild.id, poll_week)
                                    logger.info(f"🗑️ Cleared previous participants for new poll")
                                    
                                    # Calculate days ahead for Saturday/Sunday
                                    current_weekday = now.weekday()
                                    
                                    if current_weekday < 5:
                                        days_to_saturday = 5 - current_weekday
                                    elif current_weekday == 5:
                                        days_to_saturday = 0
                                    else:
                                        days_to_saturday = 6
                                    
                                    if current_weekday < 6:
                                        days_to_sunday = 6 - current_weekday
                                    elif current_weekday == 6:
                                        days_to_sunday = 0
                                    else:
                                        days_to_sunday = 7
                                    
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
                                    
                                    embed = discord.Embed(
                                        title=get_text(guild.id, "war_poll_title"),
                                        description=f"{get_text(guild.id, 'war_poll_desc')}\n\n"
                                                    f"🗓️ **{get_text(guild.id, 'saturday')}: {saturday_time}**\n"
                                                    f"🗓️ **{get_text(guild.id, 'sunday')}: {sunday_time}**\n\n"
                                                    f"*{get_text(guild.id, 'times_local')}*",
                                        color=discord.Color.red(),
                                        timestamp=datetime.now()
                                    )
                                    
                                    embed.add_field(
                                        name=f"📅 {get_text(guild.id, 'saturday_only')} (0 {get_text(guild.id, 'players')})",
                                        value=get_text(guild.id, 'click_button'),
                                        inline=True
                                    )
                                    embed.add_field(
                                        name=f"📅 {get_text(guild.id, 'sunday_only')} (0 {get_text(guild.id, 'players')})",
                                        value=get_text(guild.id, 'click_button'),
                                        inline=True
                                    )
                                    embed.add_field(
                                        name=f"⚔️ {get_text(guild.id, 'both_days')} (0 {get_text(guild.id, 'players')})",
                                        value=get_text(guild.id, 'click_button'),
                                        inline=True
                                    )
                                    embed.add_field(
                                        name=f"📊 {get_text(guild.id, 'total_saturday')}: 0",
                                        value=get_text(guild.id, 'sat_sun_players'),
                                        inline=True
                                    )
                                    embed.add_field(
                                        name=f"📊 {get_text(guild.id, 'total_sunday')}: 0",
                                        value=get_text(guild.id, 'sun_both_players'),
                                        inline=True
                                    )
                                    embed.add_field(
                                        name=f"❌ {get_text(guild.id, 'not_playing')} (0 {get_text(guild.id, 'players')})",
                                        value=get_text(guild.id, 'click_button'),
                                        inline=True
                                    )
                                    
                                    embed.set_footer(text=f"{get_text(guild.id, 'use_warlist')}")
                                    
                                    view = WarPollButtons()
                                    
                                    await channel.send(
                                        content="@everyone",
                                        embed=embed,
                                        view=view
                                    )
                                    
                                    # Mark poll as sent for this week
                                    db.mark_event_sent(guild.id, "war_poll", poll_week)
                                    logger.info(f"✅ Auto-posted war poll in {guild.name}")
                        else:
                            logger.info(f"⏭️ Poll already sent this week for {guild.name}")
                                    
            except Exception as e:
                logger.error(f"Error checking war poll for guild {guild.id}: {e}")
                
    except Exception as e:
        logger.error(f"Error in war poll scheduler: {e}")


@tasks.loop(minutes=5)  # Changed to 5 minutes for easier testing
async def check_war_reminders():
    """Check if it's time to send war reminders"""
    try:
        for guild in bot.guilds:
            try:
                config = get_war_config(guild.id)
                guild_timezone = config["timezone"]
                reminder_hours = config["reminder_hours"]
                
                # Get current time in guild's timezone
                now = datetime.now(pytz.timezone(guild_timezone))
                current_day = now.weekday()  # 0=Monday, 5=Saturday, 6=Sunday
                current_hour = now.hour
                current_minute = now.minute
                poll_week = get_current_poll_week()
                
                logger.info(f"⏰ Reminder Check: {guild.name} | Day: {current_day} (5=Sat, 6=Sun) | Time: {current_hour:02d}:{current_minute:02d}")
                
                # Check Saturday reminder
                if current_day == 5:  # Saturday
                    war_hour = config["saturday_war"]["hour"]
                    war_minute = config["saturday_war"]["minute"]
                    reminder_time = (war_hour * 60 + war_minute) - (reminder_hours * 60)
                    current_time = current_hour * 60 + current_minute
                    
                    logger.info(f"📅 Saturday Check | War: {war_hour:02d}:{war_minute:02d} | Reminder: {reminder_time//60:02d}:{reminder_time%60:02d} | Current: {current_hour:02d}:{current_minute:02d} | Diff: {abs(current_time - reminder_time)} min")
                    
                    if abs(current_time - reminder_time) < 5:
                        # Check if reminder already sent
                        if not db.was_event_sent(guild.id, "saturday_reminder", poll_week, "Saturday"):
                            # Send reminder
                            logger.info(f"⏰ Sending Saturday war reminder for guild {guild.name}")
                        
                        channel_id = config.get("war_channel_id")
                        if channel_id:
                            channel = guild.get_channel(channel_id)
                            if channel:
                                # Get participants for Saturday
                                participants = get_war_participants(guild.id)
                                player_ids = participants["saturday_players"] | participants["both_days_players"]
                                
                                if player_ids:
                                    mentions = " ".join([f"<@{user_id}>" for user_id in player_ids])
                                    
                                    war_time = get_discord_timestamp(
                                        war_hour,
                                        war_minute,
                                        0,  # Today
                                        guild_timezone
                                    )
                                    
                                    embed = discord.Embed(
                                        title="⚔️ Saturday War Reminder! ⚔️",
                                        description=(
                                            f"War starts in **{reminder_hours} hours** at {war_time}!\n\n"
                                            f"**{len(player_ids)} warriors** are ready for battle!\n\n"
                                            f"Get ready! ⚔️"
                                        ),
                                        color=discord.Color.red()
                                    )
                                    
                                    await channel.send(content=mentions, embed=embed)
                                    
                                    # Mark reminder as sent
                                    db.mark_event_sent(guild.id, "saturday_reminder", poll_week, "Saturday")
                                    logger.info(f"✅ Sent Saturday reminder to {len(player_ids)} players")
                        else:
                            logger.info(f"⏭️ Saturday reminder already sent for {guild.name}")
                
                # Check Sunday reminder
                elif current_day == 6:  # Sunday
                    war_hour = config["sunday_war"]["hour"]
                    war_minute = config["sunday_war"]["minute"]
                    reminder_time = (war_hour * 60 + war_minute) - (reminder_hours * 60)
                    current_time = current_hour * 60 + current_minute
                    
                    logger.info(f"📅 Sunday Check | War: {war_hour:02d}:{war_minute:02d} | Reminder: {reminder_time//60:02d}:{reminder_time%60:02d} | Current: {current_hour:02d}:{current_minute:02d} | Diff: {abs(current_time - reminder_time)} min")
                    
                    if abs(current_time - reminder_time) < 5:
                        # Check if reminder already sent
                        if not db.was_event_sent(guild.id, "sunday_reminder", poll_week, "Sunday"):
                            # Send reminder
                            logger.info(f"⏰ Sending Sunday war reminder for guild {guild.name}")
                        
                        channel_id = config.get("war_channel_id")
                        if channel_id:
                            channel = guild.get_channel(channel_id)
                            if channel:
                                # Get participants for Sunday
                                participants = get_war_participants(guild.id)
                                player_ids = participants["sunday_players"] | participants["both_days_players"]
                                
                                if player_ids:
                                    mentions = " ".join([f"<@{user_id}>" for user_id in player_ids])
                                    
                                    war_time = get_discord_timestamp(
                                        war_hour,
                                        war_minute,
                                        0,  # Today
                                        guild_timezone
                                    )
                                    
                                    embed = discord.Embed(
                                        title="⚔️ Sunday War Reminder! ⚔️",
                                        description=(
                                            f"War starts in **{reminder_hours} hours** at {war_time}!\n\n"
                                            f"**{len(player_ids)} warriors** are ready for battle!\n\n"
                                            f"Get ready! ⚔️"
                                        ),
                                        color=discord.Color.red()
                                    )
                                    
                                    await channel.send(content=mentions, embed=embed)
                                    
                                    # Mark reminder as sent
                                    db.mark_event_sent(guild.id, "sunday_reminder", poll_week, "Sunday")
                                    logger.info(f"✅ Sent Sunday reminder to {len(player_ids)} players")
                        else:
                            logger.info(f"⏭️ Sunday reminder already sent for {guild.name}")
                        
            except Exception as e:
                logger.error(f"Error checking war reminders for guild {guild.id}: {e}")
                
    except Exception as e:
        logger.error(f"Error in war reminder scheduler: {e}")


@tasks.loop(hours=24)
async def cleanup_old_data():
    """Clean up old tracking data daily"""
    try:
        db.clear_old_events(older_than_weeks=4)
        logger.info("🧹 Cleaned up old event tracking data")
    except Exception as e:
        logger.error(f"Error cleaning old data: {e}")


# -----------------------------
# Bot Events
# -----------------------------
@bot.event
async def on_ready():
    """Bot ready event"""
    logger.info(f"✅ Logged in as {bot.user}")
    logger.info(f"📊 Serving {len(bot.guilds)} guild(s)")
    
    # Sync commands
    try:
        synced = await bot.tree.sync()
        logger.info(f"🔧 Commands synced! ({len(synced)} commands)")
    except Exception as e:
        logger.error(f"Failed to sync commands: {e}")
    
    # Start scheduled tasks
    check_war_poll_schedule.start()
    check_war_reminders.start()
    cleanup_old_data.start()
    logger.info("⚔️ War scheduler running")
    
    # Start web server
    await start_web_server()
    
    logger.info("💾 Database ready at data/bot_data.db")


@bot.event
async def on_interaction(interaction: discord.Interaction):
    """Handle persistent view interactions"""
    try:
        if interaction.type == discord.InteractionType.component:
            custom_id = interaction.data.get("custom_id", "")
            
            # Handle war poll buttons - let the views handle them
            if custom_id.startswith("war_"):
                # These are handled by WarPollButtons view callbacks
                pass
            
            # Handle build select
            elif custom_id == "build_select":
                # Handled by BuildSelectView
                pass
            
            # Handle profile setup button
            elif custom_id == "setup_profile_button":
                # Handled by ProfileSetupButton
                pass
                
    except Exception as e:
        logger.error(f"Error handling interaction: {e}")


# -----------------------------
# Run Bot
# -----------------------------
if __name__ == "__main__":
    # Get token
    token = os.getenv('DISCORD_BOT_TOKEN')
    if not token:
        logger.error("❌ DISCORD_BOT_TOKEN not found in environment variables!")
        exit(1)
    
    # Run bot
    try:
        bot.run(token)
    except Exception as e:
        logger.error(f"❌ Failed to start bot: {e}")
