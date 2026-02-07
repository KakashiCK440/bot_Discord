import discord
from discord.ext import commands, tasks
import os
from dotenv import load_dotenv
from aiohttp import web
import asyncio
import logging
from datetime import datetime, timedelta
import pytz
import json
from pathlib import Path
from collections import defaultdict
import time

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
        `/setlanguage <language>` - Set server language (Admin)
        """,
        "system_commands": "🔧 System Commands",
        "system_commands_desc": """
        `/synccommands` - Force sync slash commands (Admin)
        `/help` - Show this help message
        """,
        "war_schedule": "📅 War Schedule",
        "poll_day": "Poll Day",
        "saturday_war": "Saturday War",
        "sunday_war": "Sunday War",
        "reminder": "Reminder",
        "hours_before": "hours before each war",
        "times_local": "Times shown in your local timezone",
        "footer_local": "All times are shown in your local timezone!",
        
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
        
        # Registration confirmations
        "registered_saturday": "✅ You're registered for **Saturday's war**!",
        "registered_sunday": "✅ You're registered for **Sunday's war**!",
        "registered_both": "✅ You're registered for **both Saturday and Sunday wars**!",
        "registered_not_playing": "✅ You're marked as **not playing** this weekend.",
        
        # War List
        "war_list_title": "⚔️ War Participant Lists ⚔️",
        "no_players": "No players signed up yet",
        "footer_builds": "Times shown in your local timezone • Players without builds should use /postbuilds",
        
        # Build System
        "select_build_title": "⚔️ Select Your Build ⚔️",
        "select_build_desc": """Choose your role and weapons for wars!

**Steps:**
1️⃣ Select your build type (DPS/Tank/Healer)
2️⃣ Choose 1-2 weapons
3️⃣ Your roles will be automatically assigned!""",
        "dps": "DPS",
        "tank": "Tank",
        "healer": "Healer",
        "dps_desc": "Damage dealers with offensive weapons",
        "tank_desc": "Defensive role with protective weapons",
        "healer_desc": "Support role with healing weapons",
        "select_weapons": "Select Your {build} Weapons",
        "choose_weapons": "Choose 1-2 weapons for your {build} build:",
        "choose_build": "Choose your build...",
        "choose_1_2_weapons": "Choose 1-2 weapons...",
        "build_configured": "✅ Build Configured!",
        "build_set": "Your build has been set:",
        "build_type": "Build Type",
        "weapons": "Weapons",
        "no_weapons": "No weapons selected",
        "use_resetbuild": "Use /resetbuild to change your build",
        "use_mybuild": "Use /mybuild to view your current build",
        
        # My Build
        "your_build": "⚔️ Your Build",
        "no_build_selected": "❌ You haven't selected a build yet! Use `/postbuilds` to choose your build.",
        
        # Reset Build
        "build_reset": "✅ Your build has been reset! Use `/postbuilds` to select a new build.",
        
        # War Config
        "war_config_title": "⚙️ War Configuration",
        "poll_schedule": "📅 Poll Schedule",
        "day": "Day",
        "time": "Time",
        "war_times": "⚔️ War Times",
        "saturday": "Saturday",
        "sunday": "Sunday",
        "reminders": "🔔 Reminders",
        "war_channel": "📢 War Channel",
        "not_configured": "❌ Not configured",
        "channel_not_found": "⚠️ Channel not found!",
        "language": "🌐 Language",
        "use_setwar": "Use /setwar to change settings",
        
        # War Reminder
        "war_reminder_title": "⚔️ {day} War Reminder! ⚔️",
        "war_starts_in": "War starts in **{hours} hours** at {time}!",
        "warriors_ready": "**{count} warriors** are ready for battle!",
        "use_warlist_reminder": "Use /warlist to see who's participating",
        "test_reminder_sent": "✅ Test {day} reminder sent to {channel}!",
        
        # Errors
        "error_occurred": "❌ An error occurred. Please try again.",
        "permission_denied": "❌ You need Administrator permissions to use this command!",
        "cooldown_wait": "⏳ Please wait {seconds} seconds before using this command again.",
        "war_channel_not_configured": "❌ War channel not configured! Use `/setwar setting:war_channel value:#channel` first.",
        "channel_deleted": "❌ War channel not found! It may have been deleted. Please set a new channel with `/setwar setting:war_channel`",
        "missing_permissions": "❌ I'm missing permissions in {channel}: {perms}",
        "no_permission_roles": "❌ I don't have permission to create roles!",
        "no_permission_remove": "❌ I don't have permission to remove roles!",
        "no_permission_assign": "❌ I don't have permission to assign roles!",
        "invalid_day_param": "❌ Invalid day! Use 'saturday' or 'sunday'",
        
        # Success messages
        "poll_posted": "✅ War poll posted in {channel}!",
        "setting_updated": "✅ {setting} set to **{value}**",
        "commands_synced": "✅ Commands synced! Wait 2-5 minutes, then restart Discord to see new commands.",
        "roles_created": "✅ **Created {count} roles:**",
        "roles_existed": "ℹ️ **{count} roles already existed**",
        "language_set": "✅ Server language set to **{language}**!",
        
        # Settings
        "invalid_day": "❌ Invalid day! Use: Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, or Sunday",
        "invalid_time": "❌ Invalid time format! Use HH:MM (e.g., 15:00 for 3 PM)",
        "invalid_number": "❌ Invalid number! Use a number between 0 and 24",
        "invalid_channel": "❌ Invalid channel! Please mention a channel like #war-channel",
        "invalid_language": "❌ Invalid language! Use: english or arabic",
        
        # Days
        "monday": "Monday",
        "tuesday": "Tuesday",
        "wednesday": "Wednesday",
        "thursday": "Thursday",
        "friday": "Friday",
        "at": "at",
    },
    "ar": {
        # Commands
        "help_title": "🤖 مساعدة أوامر البوت",
        "help_desc": "إليك كل ما يمكنني فعله!",
        "build_commands": "⚔️ أوامر البيلد",
        "build_commands_desc": """
        `/postbuilds` - نشر قائمة اختيار البيلد
        `/mybuild` - عرض البيلد الخاص بك
        `/resetbuild` - إعادة تعيين وتغيير البيلد
        `/createroles` - إنشاء جميع أدوار البيلد والأسلحة (مسؤول)
        """,
        "war_commands": "🗡️ أوامر الحرب",
        "war_commands_desc": """
        `/warpoll` - نشر استطلاع المشاركة في الحرب (مسؤول)
        `/warlist [day]` - عرض من يلعب (اختياري: saturday/sunday)
        `/setwar <setting> <value>` - تكوين إعدادات الحرب (مسؤول)
        `/warconfig` - عرض تكوين الحرب الحالي
        `/testreminder <day>` - اختبار تذكير الحرب (مسؤول)
        `/setlanguage <language>` - تعيين لغة السيرفر (مسؤول)
        """,
        "system_commands": "🔧 أوامر النظام",
        "system_commands_desc": """
        `/synccommands` - فرض مزامنة الأوامر (مسؤول)
        `/help` - عرض رسالة المساعدة هذه
        """,
        "war_schedule": "📅 جدول الحرب",
        "poll_day": "يوم الاستطلاع",
        "saturday_war": "حرب السبت",
        "sunday_war": "حرب الأحد",
        "reminder": "التذكير",
        "hours_before": "ساعات قبل كل حرب",
        "times_local": "الأوقات معروضة بتوقيتك المحلي",
        "footer_local": "جميع الأوقات معروضة بتوقيتك المحلي!",
        
        # War Poll
        "war_poll_title": "⚔️ استطلاع حرب نهاية الأسبوع ⚔️",
        "war_poll_desc": "صوت على الحرب/الحروب التي ستشارك فيها في نهاية الأسبوع!",
        "saturday_only": "السبت فقط",
        "sunday_only": "الأحد فقط",
        "both_days": "كلا اليومين",
        "not_playing": "لن ألعب",
        "players": "لاعب",
        "total_saturday": "المجموع للسبت",
        "total_sunday": "المجموع للأحد",
        "sat_sun_players": "لاعبو السبت + كلا اليومين",
        "sun_both_players": "لاعبو الأحد + كلا اليومين",
        "click_button": "انقر على الزر",
        "use_warlist": "استخدم /warlist لرؤية قوائم اللاعبين التفصيلية مع بيلداتهم",
        
        # Registration confirmations
        "registered_saturday": "✅ تم تسجيلك لحرب **السبت**!",
        "registered_sunday": "✅ تم تسجيلك لحرب **الأحد**!",
        "registered_both": "✅ تم تسجيلك **لحربي السبت والأحد**!",
        "registered_not_playing": "✅ تم تحديدك **كغير لاعب** في نهاية الأسبوع.",
        
        # War List
        "war_list_title": "⚔️ قوائم المشاركين في الحرب ⚔️",
        "no_players": "لا يوجد لاعبون مسجلون بعد",
        "footer_builds": "الأوقات معروضة بتوقيتك المحلي • يجب على اللاعبين بدون بيلد استخدام /postbuilds",
        
        # Build System
        "select_build_title": "⚔️ اختر البيلد الخاص بك ⚔️",
        "select_build_desc": """اختر دورك وأسلحتك للحروب!

**الخطوات:**
1️⃣ اختر نوع البيلد (DPS/Tank/Healer)
2️⃣ اختر 1-2 سلاح
3️⃣ سيتم تعيين أدوارك تلقائيًا!""",
        "dps": "DPS",
        "tank": "Tank",
        "healer": "Healer",
        "dps_desc": "موزعو الضرر بأسلحة هجومية",
        "tank_desc": "دور دفاعي بأسلحة حماية",
        "healer_desc": "دور دعم بأسلحة شفاء",
        "select_weapons": "اختر أسلحة {build}",
        "choose_weapons": "اختر 1-2 سلاح لبيلد {build}:",
        "choose_build": "اختر البيلد الخاص بك...",
        "choose_1_2_weapons": "اختر 1-2 سلاح...",
        "build_configured": "✅ تم تكوين البيلد!",
        "build_set": "تم تعيين البيلد الخاص بك:",
        "build_type": "نوع البيلد",
        "weapons": "الأسلحة",
        "no_weapons": "لم يتم اختيار أسلحة",
        "use_resetbuild": "استخدم /resetbuild لتغيير البيلد",
        "use_mybuild": "استخدم /mybuild لعرض البيلد الحالي",
        
        # My Build
        "your_build": "⚔️ البيلد الخاص بك",
        "no_build_selected": "❌ لم تختر بيلد بعد! استخدم `/postbuilds` لاختيار البيلد.",
        
        # Reset Build
        "build_reset": "✅ تم إعادة تعيين البيلد! استخدم `/postbuilds` لاختيار بيلد جديد.",
        
        # War Config
        "war_config_title": "⚙️ تكوين الحرب",
        "poll_schedule": "📅 جدول الاستطلاع",
        "day": "اليوم",
        "time": "الوقت",
        "war_times": "⚔️ أوقات الحرب",
        "saturday": "السبت",
        "sunday": "الأحد",
        "reminders": "🔔 التذكيرات",
        "war_channel": "📢 قناة الحرب",
        "not_configured": "❌ غير مكون",
        "channel_not_found": "⚠️ القناة غير موجودة!",
        "language": "🌐 اللغة",
        "use_setwar": "استخدم /setwar لتغيير الإعدادات",
        
        # War Reminder
        "war_reminder_title": "⚔️ تذكير بحرب {day}! ⚔️",
        "war_starts_in": "تبدأ الحرب في **{hours} ساعة** في {time}!",
        "warriors_ready": "**{count} محارب** جاهزون للمعركة!",
        "use_warlist_reminder": "استخدم /warlist لرؤية من يشارك",
        "test_reminder_sent": "✅ تم إرسال تذكير اختباري لـ {day} إلى {channel}!",
        
        # Errors
        "error_occurred": "❌ حدث خطأ. الرجاء المحاولة مرة أخرى.",
        "permission_denied": "❌ تحتاج إلى صلاحيات المسؤول لاستخدام هذا الأمر!",
        "cooldown_wait": "⏳ الرجاء الانتظار {seconds} ثانية قبل استخدام هذا الأمر مرة أخرى.",
        "war_channel_not_configured": "❌ قناة الحرب غير مكونة! استخدم `/setwar setting:war_channel value:#channel` أولاً.",
        "channel_deleted": "❌ قناة الحرب غير موجودة! ربما تم حذفها. الرجاء تعيين قناة جديدة باستخدام `/setwar setting:war_channel`",
        "missing_permissions": "❌ أنا أفتقد الصلاحيات في {channel}: {perms}",
        "no_permission_roles": "❌ ليس لدي إذن لإنشاء الأدوار!",
        "no_permission_remove": "❌ ليس لدي إذن لإزالة الأدوار!",
        "no_permission_assign": "❌ ليس لدي إذن لتعيين الأدوار!",
        "invalid_day_param": "❌ يوم غير صحيح! استخدم 'saturday' أو 'sunday'",
        
        # Success messages
        "poll_posted": "✅ تم نشر استطلاع الحرب في {channel}!",
        "setting_updated": "✅ تم تعيين {setting} إلى **{value}**",
        "commands_synced": "✅ تمت مزامنة الأوامر! انتظر 2-5 دقائق، ثم أعد تشغيل Discord لرؤية الأوامر الجديدة.",
        "roles_created": "✅ **تم إنشاء {count} دور:**",
        "roles_existed": "ℹ️ **{count} دور موجود بالفعل**",
        "language_set": "✅ تم تعيين لغة السيرفر إلى **{language}**!",
        
        # Settings
        "invalid_day": "❌ يوم غير صحيح! استخدم: Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, أو Sunday",
        "invalid_time": "❌ تنسيق وقت غير صحيح! استخدم HH:MM (مثل: 15:00 لـ 3 PM)",
        "invalid_number": "❌ رقم غير صحيح! استخدم رقمًا بين 0 و 24",
        "invalid_channel": "❌ قناة غير صحيحة! الرجاء ذكر قناة مثل #war-channel",
        "invalid_language": "❌ لغة غير صحيحة! استخدم: english أو arabic",
        
        # Days
        "monday": "الإثنين",
        "tuesday": "الثلاثاء",
        "wednesday": "الأربعاء",
        "thursday": "الخميس",
        "friday": "الجمعة",
        "at": "في",
    }
}

# Storage paths
DATA_DIR = Path("/mnt/user-data/uploads")
LANGUAGE_FILE = DATA_DIR / "language_data.json"
WAR_DATA_FILE = DATA_DIR / "war_poll_data.json"

# Initialize language storage
server_languages = {}
if LANGUAGE_FILE.exists():
    try:
        with open(LANGUAGE_FILE, 'r', encoding='utf-8') as f:
            server_languages = json.load(f)
            # Convert string keys to integers
            server_languages = {int(k): v for k, v in server_languages.items()}
    except Exception as e:
        logger.error(f"Error loading language data: {e}")

def save_language_data():
    """Save language preferences to file"""
    try:
        # Convert integer keys to strings for JSON
        data = {str(k): v for k, v in server_languages.items()}
        with open(LANGUAGE_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error saving language data: {e}")

def get_language(guild_id: int) -> str:
    """Get language for a server (default: en)"""
    return server_languages.get(guild_id, "en")

def get_text(guild_id: int, key: str, **kwargs) -> str:
    """Get translated text for a server"""
    lang = get_language(guild_id)
    text = LANGUAGES.get(lang, LANGUAGES["en"]).get(key, LANGUAGES["en"].get(key, key))
    
    # Format with kwargs if provided
    if kwargs:
        try:
            text = text.format(**kwargs)
        except KeyError:
            pass
    
    return text

# -----------------------------
# War Poll Data Structure
# -----------------------------
war_poll_data = {
    "message_id": None,
    "saturday_players": set(),
    "sunday_players": set(),
    "both_days_players": set(),
    "not_playing": set(),
}

# War Configuration with defaults
WAR_CONFIG = {
    "poll_day": "Friday",  # Day to post the poll
    "poll_time": {"hour": 15, "minute": 0},  # 3:00 PM
    "saturday_war": {"hour": 22, "minute": 30},  # 10:30 PM
    "sunday_war": {"hour": 22, "minute": 30},  # 10:30 PM
    "reminder_hours_before": 2,  # Remind 2 hours before
    "war_channel_id": None,
    "timezone": "Africa/Cairo",  # Bot timezone (not shown to users)
}

def save_data():
    """Save war poll data to file"""
    try:
        data = {
            "message_id": war_poll_data["message_id"],
            "saturday_players": list(war_poll_data["saturday_players"]),
            "sunday_players": list(war_poll_data["sunday_players"]),
            "both_days_players": list(war_poll_data["both_days_players"]),
            "not_playing": list(war_poll_data["not_playing"]),
            "config": WAR_CONFIG
        }
        with open(WAR_DATA_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving war data: {e}")

def load_data():
    """Load war poll data from file"""
    global WAR_CONFIG
    try:
        if WAR_DATA_FILE.exists():
            with open(WAR_DATA_FILE, 'r') as f:
                data = json.load(f)
                war_poll_data["message_id"] = data.get("message_id")
                war_poll_data["saturday_players"] = set(data.get("saturday_players", []))
                war_poll_data["sunday_players"] = set(data.get("sunday_players", []))
                war_poll_data["both_days_players"] = set(data.get("both_days_players", []))
                war_poll_data["not_playing"] = set(data.get("not_playing", []))
                
                # Load config
                if "config" in data:
                    WAR_CONFIG.update(data["config"])
                    
            logger.info("✅ War data loaded")
    except Exception as e:
        logger.error(f"Error loading war data: {e}")

# Load data on startup
load_data()

# -----------------------------
# Build System Data
# -----------------------------
BUILDS = {
    "DPS": {
        "weapons": [
            "Strategic Sword", "Heaven Spear", "Nameless Sword",
            "Nameless Spear", "Twinblade", "Mortal Rope",
            "Vernal Umbrella", "Inkwell Fan"
        ]
    },
    "Tank": {
        "weapons": [
            "Thunder Blade", "StormBreaker Spear"
        ]
    },
    "Healer": {
        "weapons": [
            "Panacea Fan", "Soulshade Umbrella"
        ]
    }
}

# Emoji mappings for builds and weapons
EMOJIS = {
    # Build types
    "DPS": "<:Dps:1469039402113306747>",
    "Tank": "<:Tank:1469039369829748901>",
    "Healer": "<:Healer:1469039348656898158>",
    
    # Weapons
    "Strategic Sword": "<:StrategicSword:1468707686907642110>",
    "Heaven Spear": "<:Heavenspear:1468707949517078539>",
    "Nameless Sword": "<:NamelessSword:1468707969574113411>",
    "Nameless Spear": "<:Namelessspear:1468707652212232333>",
    "Twinblade": "<:Twinblade:1468707797263978601>",
    "Mortal Rope": "<:MortalRobe:1468707859389878332>",
    "Vernal Umbrella": "<:VernalUmbrella:1468707906009436272>",
    "Inkwell Fan": "<:inkwellfan:1468707817379729605>",
    "Thunder Blade": "<:thunderblade:1468707839240311006>",
    "StormBreaker Spear": "<:StormBreakerspear:1468707928272797767>",
    "Panacea Fan": "<:Panaveafan:1468707753156415601>",
    "Soulshade Umbrella": "<:SoulshadeUmbrella:1468707729177706637>"
}

# User builds storage
user_builds = defaultdict(lambda: {"build": None, "weapons": []})

# -----------------------------
# Helper Functions
# -----------------------------
def get_discord_timestamp(hour: int, minute: int, days_from_now: int = 0) -> str:
    """Generate Discord timestamp that shows in user's local time"""
    tz = pytz.timezone(WAR_CONFIG["timezone"])
    now = datetime.now(tz)
    
    # Calculate target datetime
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    target += timedelta(days=days_from_now)
    
    # Convert to Unix timestamp
    unix_time = int(target.timestamp())
    
    # Return Discord timestamp format (shows in user's local time)
    return f"<t:{unix_time}:t>"

def get_next_war_timestamps():
    """Get Discord timestamps for next Saturday and Sunday wars"""
    tz = pytz.timezone(WAR_CONFIG["timezone"])
    now = datetime.now(tz)
    
    # Calculate days until next Saturday (5) and Sunday (6)
    days_until_saturday = (5 - now.weekday()) % 7
    days_until_sunday = (6 - now.weekday()) % 7
    
    # If it's Saturday/Sunday and past war time, get next week
    if days_until_saturday == 0 and now.hour >= WAR_CONFIG["saturday_war"]["hour"]:
        days_until_saturday = 7
    if days_until_sunday == 0 and now.hour >= WAR_CONFIG["sunday_war"]["hour"]:
        days_until_sunday = 7
    
    saturday_timestamp = get_discord_timestamp(
        WAR_CONFIG["saturday_war"]["hour"],
        WAR_CONFIG["saturday_war"]["minute"],
        days_until_saturday
    )
    
    sunday_timestamp = get_discord_timestamp(
        WAR_CONFIG["sunday_war"]["hour"],
        WAR_CONFIG["sunday_war"]["minute"],
        days_until_sunday
    )
    
    return saturday_timestamp, sunday_timestamp

async def validate_war_channel(channel_id: int, guild: discord.Guild) -> tuple[bool, str]:
    """Validate war channel exists and bot has permissions"""
    channel = guild.get_channel(channel_id)
    if not channel:
        return False, "channel_deleted"
    
    permissions = channel.permissions_for(guild.me)
    required_perms = []
    
    if not permissions.send_messages:
        required_perms.append("Send Messages")
    if not permissions.embed_links:
        required_perms.append("Embed Links")
    
    if required_perms:
        return False, f"missing_permissions: {', '.join(required_perms)}"
    
    return True, ""

# -----------------------------
# Build Selection Views
# -----------------------------
class BuildSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.select(
        placeholder="Choose your build...",
        custom_id="build_select",
        options=[
            discord.SelectOption(
                label="DPS",
                description="Damage dealers with offensive weapons",
                emoji=discord.PartialEmoji.from_str(EMOJIS["DPS"])
            ),
            discord.SelectOption(
                label="Tank",
                description="Defensive role with protective weapons",
                emoji=discord.PartialEmoji.from_str(EMOJIS["Tank"])
            ),
            discord.SelectOption(
                label="Healer",
                description="Support role with healing weapons",
                emoji=discord.PartialEmoji.from_str(EMOJIS["Healer"])
            )
        ]
    )
    async def select_build(self, interaction: discord.Interaction, select: discord.ui.Select):
        build_type = select.values[0]
        guild_id = interaction.guild_id
        
        # Create weapon selection view
        view = WeaponSelectView(build_type)
        
        embed = discord.Embed(
            title=get_text(guild_id, "select_weapons", build=build_type),
            description=get_text(guild_id, "choose_weapons", build=build_type),
            color=discord.Color.blue()
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class WeaponSelectView(discord.ui.View):
    def __init__(self, build_type: str):
        super().__init__(timeout=180)
        self.build_type = build_type
        
        # Add weapon select menu
        weapons = BUILDS[build_type]["weapons"]
        options = [
            discord.SelectOption(
                label=weapon, 
                value=weapon,
                emoji=discord.PartialEmoji.from_str(EMOJIS[weapon])
            )
            for weapon in weapons
        ]
        
        select = discord.ui.Select(
            placeholder="Choose 1-2 weapons...",
            options=options,
            min_values=1,
            max_values=min(2, len(weapons)),
            custom_id=f"weapon_select_{build_type}"
        )
        select.callback = self.select_weapons
        self.add_item(select)
    
    async def select_weapons(self, interaction: discord.Interaction):
        # CRITICAL: Defer immediately to avoid timeout errors
        await interaction.response.defer(ephemeral=True)
        
        selected_weapons = interaction.data["values"]
        user_id = interaction.user.id
        guild_id = interaction.guild_id
        
        try:
            # Save build
            user_builds[user_id] = {
                "build": self.build_type,
                "weapons": selected_weapons
            }
            
            guild = interaction.guild
            roles_to_add = []
            
            # Remove old build roles and weapon roles
            for existing_role in interaction.user.roles:
                # Remove old build type roles
                if existing_role.name in ["DPS", "Tank", "Healer"]:
                    try:
                        await interaction.user.remove_roles(existing_role)
                    except:
                        pass
                # Remove old weapon roles
                all_weapons = []
                for build_data in BUILDS.values():
                    all_weapons.extend(build_data["weapons"])
                if existing_role.name in all_weapons:
                    try:
                        await interaction.user.remove_roles(existing_role)
                    except:
                        pass
                # Remove old combined roles (cleanup)
                if "(" in existing_role.name and ")" in existing_role.name:
                    try:
                        await interaction.user.remove_roles(existing_role)
                    except:
                        pass
            
            # 1. Get base build type role (should exist from /createroles)
            build_role = discord.utils.get(guild.roles, name=self.build_type)
            if not build_role:
                await interaction.followup.send(
                    f"❌ **{self.build_type}** role not found! Please ask an admin to run `/createroles` first.",
                    ephemeral=True
                )
                return
            roles_to_add.append(build_role)
            
            # 2. Get weapon roles (should exist from /createroles)
            for weapon in selected_weapons:
                weapon_role = discord.utils.get(guild.roles, name=weapon)
                if not weapon_role:
                    await interaction.followup.send(
                        f"❌ **{weapon}** role not found! Please ask an admin to run `/createroles` first.",
                        ephemeral=True
                    )
                    return
                roles_to_add.append(weapon_role)
            
            # Assign all roles
            try:
                await interaction.user.add_roles(*roles_to_add)
            except discord.Forbidden:
                await interaction.followup.send(
                    get_text(guild_id, "no_permission_assign"),
                    ephemeral=True
                )
                return
            except discord.errors.DiscordServerError:
                # Handle 503 errors gracefully
                await interaction.followup.send(
                    "⚠️ Discord's servers are experiencing issues. Please try selecting your weapons again in a moment.",
                    ephemeral=True
                )
                return
            
            # Confirmation
            embed = discord.Embed(
                title=get_text(guild_id, "build_configured"),
                description=get_text(guild_id, "build_set"),
                color=discord.Color.green()
            )
            embed.add_field(
                name=get_text(guild_id, "build_type"),
                value=f"{EMOJIS[self.build_type]} {self.build_type}",
                inline=False
            )
            
            # Format weapons with emojis
            weapon_display = "\n".join([f"{EMOJIS[weapon]} {weapon}" for weapon in selected_weapons])
            embed.add_field(
                name=get_text(guild_id, "weapons"),
                value=weapon_display,
                inline=False
            )
            
            # Show assigned roles with emojis
            role_display = []
            for role in roles_to_add:
                emoji = EMOJIS.get(role.name, "•")
                role_display.append(f"{emoji} {role.name}")
            
            embed.add_field(
                name="✅ Roles Assigned",
                value="\n".join(role_display),
                inline=False
            )
            
            embed.set_footer(text=get_text(guild_id, "use_resetbuild"))
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            # Catch any other unexpected errors
            logger.error(f"Error in select_weapons: {e}")
            try:
                await interaction.followup.send(
                    get_text(guild_id, "error_occurred"),
                    ephemeral=True
                )
            except:
                pass

# -----------------------------
# War Poll Buttons
# -----------------------------
class WarPollButtons(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    async def update_poll_embed(self, interaction: discord.Interaction):
        """Update the poll embed with current counts"""
        guild_id = interaction.guild_id
        
        sat_count = len(war_poll_data["saturday_players"])
        sun_count = len(war_poll_data["sunday_players"])
        both_count = len(war_poll_data["both_days_players"])
        not_playing_count = len(war_poll_data["not_playing"])
        
        total_saturday = sat_count + both_count
        total_sunday = sun_count + both_count
        
        # Get Discord timestamps
        saturday_time, sunday_time = get_next_war_timestamps()
        
        embed = discord.Embed(
            title=get_text(guild_id, "war_poll_title"),
            description=f"{get_text(guild_id, 'war_poll_desc')}\n\n"
                        f"🗓️ **{get_text(guild_id, 'saturday_war')}**: {saturday_time}\n"
                        f"🗓️ **{get_text(guild_id, 'sunday_war')}**: {sunday_time}\n\n"
                        f"*{get_text(guild_id, 'times_local')}*",
            color=discord.Color.red(),
            timestamp=datetime.now()
        )
        
        embed.add_field(
            name=f"📅 {get_text(guild_id, 'saturday_only')} ({sat_count} {get_text(guild_id, 'players')})",
            value=f"{get_text(guild_id, 'click_button')}",
            inline=True
        )
        embed.add_field(
            name=f"📅 {get_text(guild_id, 'sunday_only')} ({sun_count} {get_text(guild_id, 'players')})",
            value=f"{get_text(guild_id, 'click_button')}",
            inline=True
        )
        embed.add_field(
            name=f"⚔️ {get_text(guild_id, 'both_days')} ({both_count} {get_text(guild_id, 'players')})",
            value=f"{get_text(guild_id, 'click_button')}",
            inline=True
        )
        embed.add_field(
            name=f"📊 {get_text(guild_id, 'total_saturday')}: {total_saturday}",
            value=get_text(guild_id, "sat_sun_players"),
            inline=True
        )
        embed.add_field(
            name=f"📊 {get_text(guild_id, 'total_sunday')}: {total_sunday}",
            value=get_text(guild_id, "sun_both_players"),
            inline=True
        )
        embed.add_field(
            name=f"❌ {get_text(guild_id, 'not_playing')} ({not_playing_count} {get_text(guild_id, 'players')})",
            value=f"{get_text(guild_id, 'click_button')}",
            inline=True
        )
        
        embed.set_footer(text=get_text(guild_id, "use_warlist"))
        
        await interaction.message.edit(embed=embed)
    
    @discord.ui.button(label="Saturday Only", style=discord.ButtonStyle.primary, custom_id="saturday_only", emoji="📅")
    async def saturday_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        guild_id = interaction.guild_id
        
        # Remove from all other lists
        war_poll_data["sunday_players"].discard(user_id)
        war_poll_data["both_days_players"].discard(user_id)
        war_poll_data["not_playing"].discard(user_id)
        
        # Add to Saturday
        war_poll_data["saturday_players"].add(user_id)
        
        save_data()
        await self.update_poll_embed(interaction)
        await interaction.response.send_message(
            get_text(guild_id, "registered_saturday"),
            ephemeral=True
        )
    
    @discord.ui.button(label="Sunday Only", style=discord.ButtonStyle.primary, custom_id="sunday_only", emoji="📅")
    async def sunday_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        guild_id = interaction.guild_id
        
        # Remove from all other lists
        war_poll_data["saturday_players"].discard(user_id)
        war_poll_data["both_days_players"].discard(user_id)
        war_poll_data["not_playing"].discard(user_id)
        
        # Add to Sunday
        war_poll_data["sunday_players"].add(user_id)
        
        save_data()
        await self.update_poll_embed(interaction)
        await interaction.response.send_message(
            get_text(guild_id, "registered_sunday"),
            ephemeral=True
        )
    
    @discord.ui.button(label="Both Days", style=discord.ButtonStyle.success, custom_id="both_days", emoji="⚔️")
    async def both_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        guild_id = interaction.guild_id
        
        # Remove from all other lists
        war_poll_data["saturday_players"].discard(user_id)
        war_poll_data["sunday_players"].discard(user_id)
        war_poll_data["not_playing"].discard(user_id)
        
        # Add to both days
        war_poll_data["both_days_players"].add(user_id)
        
        save_data()
        await self.update_poll_embed(interaction)
        await interaction.response.send_message(
            get_text(guild_id, "registered_both"),
            ephemeral=True
        )
    
    @discord.ui.button(label="Not Playing", style=discord.ButtonStyle.danger, custom_id="not_playing", emoji="❌")
    async def not_playing_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        guild_id = interaction.guild_id
        
        # Remove from all other lists
        war_poll_data["saturday_players"].discard(user_id)
        war_poll_data["sunday_players"].discard(user_id)
        war_poll_data["both_days_players"].discard(user_id)
        
        # Add to not playing
        war_poll_data["not_playing"].add(user_id)
        
        save_data()
        await self.update_poll_embed(interaction)
        await interaction.response.send_message(
            get_text(guild_id, "registered_not_playing"),
            ephemeral=True
        )

# -----------------------------
# Slash Commands
# -----------------------------

@bot.tree.command(name="help", description="Show all available commands")
async def help_command(interaction: discord.Interaction):
    """Display help information"""
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
        name=get_text(guild_id, "system_commands"),
        value=get_text(guild_id, "system_commands_desc"),
        inline=False
    )
    
    # Add war schedule info
    saturday_time, sunday_time = get_next_war_timestamps()
    poll_day = get_text(guild_id, WAR_CONFIG["poll_day"].lower())
    poll_time_str = f"{WAR_CONFIG['poll_time']['hour']:02d}:{WAR_CONFIG['poll_time']['minute']:02d}"
    
    schedule_text = f"**{get_text(guild_id, 'poll_day')}**: {poll_day} {get_text(guild_id, 'at')} {poll_time_str}\n"
    schedule_text += f"**{get_text(guild_id, 'saturday_war')}**: {saturday_time}\n"
    schedule_text += f"**{get_text(guild_id, 'sunday_war')}**: {sunday_time}\n"
    schedule_text += f"**{get_text(guild_id, 'reminder')}**: {WAR_CONFIG['reminder_hours_before']} {get_text(guild_id, 'hours_before')}"
    
    embed.add_field(
        name=get_text(guild_id, "war_schedule"),
        value=schedule_text,
        inline=False
    )
    
    embed.set_footer(text=get_text(guild_id, "footer_local"))
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="postbuilds", description="Post build selection menu (Admin only)")
@discord.app_commands.checks.has_permissions(administrator=True)
async def postbuilds(interaction: discord.Interaction):
    """Post the build selection menu"""
    guild_id = interaction.guild_id
    
    embed = discord.Embed(
        title=get_text(guild_id, "select_build_title"),
        description=get_text(guild_id, "select_build_desc"),
        color=discord.Color.blue()
    )
    
    view = BuildSelectView()
    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(name="mybuild", description="View your current build")
async def mybuild(interaction: discord.Interaction):
    """Show user's current build"""
    user_id = interaction.user.id
    guild_id = interaction.guild_id
    
    if user_id not in user_builds or not user_builds[user_id]["build"]:
        await interaction.response.send_message(
            get_text(guild_id, "no_build_selected"),
            ephemeral=True
        )
        return
    
    build_data = user_builds[user_id]
    
    embed = discord.Embed(
        title=get_text(guild_id, "your_build"),
        color=discord.Color.blue()
    )
    
    # Add build type with emoji
    build_type = build_data["build"]
    embed.add_field(
        name=get_text(guild_id, "build_type"),
        value=f"{EMOJIS[build_type]} {build_type}",
        inline=False
    )
    
    # Add weapons with emojis
    if build_data["weapons"]:
        weapon_display = "\n".join([f"{EMOJIS[weapon]} {weapon}" for weapon in build_data["weapons"]])
        embed.add_field(
            name=get_text(guild_id, "weapons"),
            value=weapon_display,
            inline=False
        )
    else:
        embed.add_field(
            name=get_text(guild_id, "weapons"),
            value=get_text(guild_id, "no_weapons"),
            inline=False
        )
    
    embed.set_footer(text=get_text(guild_id, "use_resetbuild"))
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="resetbuild", description="Reset your build and select a new one")
async def resetbuild(interaction: discord.Interaction):
    """Reset user's build"""
    user_id = interaction.user.id
    guild_id = interaction.guild_id
    
    # Remove build data
    if user_id in user_builds:
        del user_builds[user_id]
    
    # Get all possible weapons for removal
    all_weapons = []
    for build_data in BUILDS.values():
        all_weapons.extend(build_data["weapons"])
    
    # Remove build roles, weapon roles, and combined roles
    for role in interaction.user.roles:
        # Remove build type roles
        if role.name in ["DPS", "Tank", "Healer"]:
            try:
                await interaction.user.remove_roles(role)
            except:
                pass
        # Remove individual weapon roles
        elif role.name in all_weapons:
            try:
                await interaction.user.remove_roles(role)
            except:
                pass
        # Remove any combined roles (cleanup)
        elif "(" in role.name and ")" in role.name:
            try:
                await interaction.user.remove_roles(role)
            except:
                pass
    
    await interaction.response.send_message(
        get_text(guild_id, "build_reset"),
        ephemeral=True
    )

@bot.tree.command(name="createroles", description="Create all build and weapon roles (Admin only)")
@discord.app_commands.checks.has_permissions(administrator=True)
async def createroles(interaction: discord.Interaction):
    """Create all build type and weapon roles at once"""
    guild_id = interaction.guild_id
    await interaction.response.defer(ephemeral=True)
    
    guild = interaction.guild
    created_roles = []
    existing_roles = []
    
    # Create the 3 base build type roles
    base_builds = ["DPS", "Tank", "Healer"]
    
    for build_type in base_builds:
        if not discord.utils.get(guild.roles, name=build_type):
            try:
                role = await guild.create_role(name=build_type, mentionable=True)
                created_roles.append(f"**{build_type}** (Build Type)")
            except discord.Forbidden:
                await interaction.followup.send(
                    get_text(guild_id, "no_permission_roles"),
                    ephemeral=True
                )
                return
        else:
            existing_roles.append(f"**{build_type}** (Build Type)")
    
    # Create ALL weapon roles from all builds
    all_weapons = []
    for build_data in BUILDS.values():
        all_weapons.extend(build_data["weapons"])
    
    for weapon in all_weapons:
        if not discord.utils.get(guild.roles, name=weapon):
            try:
                role = await guild.create_role(name=weapon, mentionable=True)
                created_roles.append(weapon)
            except discord.Forbidden:
                await interaction.followup.send(
                    get_text(guild_id, "no_permission_roles"),
                    ephemeral=True
                )
                return
        else:
            existing_roles.append(weapon)
    
    # Build response message
    embed = discord.Embed(
        title="✅ Role Setup Complete!",
        description="All build and weapon roles have been processed.",
        color=discord.Color.green()
    )
    
    if created_roles:
        embed.add_field(
            name=f"✅ Created {len(created_roles)} Roles",
            value="\n".join([f"• {role}" for role in created_roles]),
            inline=False
        )
    
    if existing_roles:
        embed.add_field(
            name=f"ℹ️ {len(existing_roles)} Roles Already Existed",
            value="\n".join([f"• {role}" for role in existing_roles]),
            inline=False
        )
    
    embed.add_field(
        name="📊 Summary",
        value=f"**Total Roles:** {len(created_roles) + len(existing_roles)}\n"
              f"• 3 Build Types (DPS, Tank, Healer)\n"
              f"• {len(all_weapons)} Weapon Roles",
        inline=False
    )
    
    embed.set_footer(text="Players can now use /postbuilds to select their builds!")
    
    await interaction.followup.send(embed=embed, ephemeral=True)

@bot.tree.command(name="warpoll", description="Post war participation poll (Admin only)")
@discord.app_commands.checks.has_permissions(administrator=True)
async def warpoll(interaction: discord.Interaction):
    """Manually post war poll"""
    guild_id = interaction.guild_id
    
    if not WAR_CONFIG["war_channel_id"]:
        await interaction.response.send_message(
            get_text(guild_id, "war_channel_not_configured"),
            ephemeral=True
        )
        return
    
    channel = interaction.guild.get_channel(WAR_CONFIG["war_channel_id"])
    if not channel:
        await interaction.response.send_message(
            get_text(guild_id, "channel_deleted"),
            ephemeral=True
        )
        return
    
    # Validate channel permissions
    is_valid, error_msg = await validate_war_channel(WAR_CONFIG["war_channel_id"], interaction.guild)
    if not is_valid:
        await interaction.response.send_message(
            get_text(guild_id, error_msg),
            ephemeral=True
        )
        return
    
    await interaction.response.defer(ephemeral=True)
    
    # Reset poll data
    war_poll_data["saturday_players"].clear()
    war_poll_data["sunday_players"].clear()
    war_poll_data["both_days_players"].clear()
    war_poll_data["not_playing"].clear()
    save_data()
    
    # Get Discord timestamps
    saturday_time, sunday_time = get_next_war_timestamps()
    
    embed = discord.Embed(
        title=get_text(guild_id, "war_poll_title"),
        description=f"{get_text(guild_id, 'war_poll_desc')}\n\n"
                    f"🗓️ **{get_text(guild_id, 'saturday_war')}**: {saturday_time}\n"
                    f"🗓️ **{get_text(guild_id, 'sunday_war')}**: {sunday_time}\n\n"
                    f"*{get_text(guild_id, 'times_local')}*",
        color=discord.Color.red(),
        timestamp=datetime.now()
    )
    
    embed.add_field(
        name=f"📅 {get_text(guild_id, 'saturday_only')} (0 {get_text(guild_id, 'players')})",
        value=f"{get_text(guild_id, 'click_button')}",
        inline=True
    )
    embed.add_field(
        name=f"📅 {get_text(guild_id, 'sunday_only')} (0 {get_text(guild_id, 'players')})",
        value=f"{get_text(guild_id, 'click_button')}",
        inline=True
    )
    embed.add_field(
        name=f"⚔️ {get_text(guild_id, 'both_days')} (0 {get_text(guild_id, 'players')})",
        value=f"{get_text(guild_id, 'click_button')}",
        inline=True
    )
    embed.add_field(
        name=f"📊 {get_text(guild_id, 'total_saturday')}: 0",
        value=get_text(guild_id, "sat_sun_players"),
        inline=True
    )
    embed.add_field(
        name=f"📊 {get_text(guild_id, 'total_sunday')}: 0",
        value=get_text(guild_id, "sun_both_players"),
        inline=True
    )
    embed.add_field(
        name=f"❌ {get_text(guild_id, 'not_playing')} (0 {get_text(guild_id, 'players')})",
        value=f"{get_text(guild_id, 'click_button')}",
        inline=True
    )
    
    embed.set_footer(text=get_text(guild_id, "use_warlist"))
    
    message = await channel.send(embed=embed, view=WarPollButtons())
    war_poll_data["message_id"] = message.id
    save_data()
    
    await interaction.followup.send(
        get_text(guild_id, "poll_posted", channel=channel.mention),
        ephemeral=True
    )

@bot.tree.command(name="warlist", description="Show war participant lists with builds")
@discord.app_commands.describe(day="Optional: Show only Saturday or Sunday participants")
@discord.app_commands.choices(day=[
    discord.app_commands.Choice(name="Saturday", value="saturday"),
    discord.app_commands.Choice(name="Sunday", value="sunday")
])
async def warlist(interaction: discord.Interaction, day: str = None):
    """Show detailed war participant lists"""
    guild_id = interaction.guild_id
    guild = interaction.guild
    
    embed = discord.Embed(
        title=get_text(guild_id, "war_list_title"),
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    
    # Get Discord timestamps
    saturday_time, sunday_time = get_next_war_timestamps()
    
    def format_player_list(player_ids: set) -> str:
        if not player_ids:
            return get_text(guild_id, "no_players")
        
        lines = []
        for user_id in player_ids:
            member = guild.get_member(user_id)
            if member:
                build_info = user_builds.get(user_id, {})
                build = build_info.get("build", "No build")
                weapons = build_info.get("weapons", [])
                
                # Format with emojis
                if build in EMOJIS:
                    build_display = f"{EMOJIS[build]} **{build}**"
                else:
                    build_display = f"**{build}**"
                
                if weapons:
                    weapons_display = ", ".join([f"{EMOJIS.get(w, '')} {w}" for w in weapons])
                else:
                    weapons_display = get_text(guild_id, "no_weapons")
                
                lines.append(f"• {member.display_name} - {build_display} ({weapons_display})")
        
        return "\n".join(lines) if lines else get_text(guild_id, "no_players")
    
    if not day or day == "saturday":
        saturday_participants = war_poll_data["saturday_players"].union(war_poll_data["both_days_players"])
        embed.add_field(
            name=f"📅 {get_text(guild_id, 'saturday_war')} ({len(saturday_participants)} {get_text(guild_id, 'players')}) - {saturday_time}",
            value=format_player_list(saturday_participants),
            inline=False
        )
    
    if not day or day == "sunday":
        sunday_participants = war_poll_data["sunday_players"].union(war_poll_data["both_days_players"])
        embed.add_field(
            name=f"📅 {get_text(guild_id, 'sunday_war')} ({len(sunday_participants)} {get_text(guild_id, 'players')}) - {sunday_time}",
            value=format_player_list(sunday_participants),
            inline=False
        )
    
    embed.set_footer(text=get_text(guild_id, "footer_builds"))
    
    await interaction.response.send_message(embed=embed, ephemeral=False)

@bot.tree.command(name="setwar", description="Configure war settings (Admin only)")
@discord.app_commands.describe(
    setting="Setting to configure",
    value="New value for the setting"
)
@discord.app_commands.choices(setting=[
    discord.app_commands.Choice(name="Poll Day", value="poll_day"),
    discord.app_commands.Choice(name="Poll Time (HH:MM)", value="poll_time"),
    discord.app_commands.Choice(name="Saturday War Time (HH:MM)", value="saturday_time"),
    discord.app_commands.Choice(name="Sunday War Time (HH:MM)", value="sunday_time"),
    discord.app_commands.Choice(name="Reminder Hours Before War", value="reminder_hours"),
    discord.app_commands.Choice(name="War Channel", value="war_channel"),
])
@discord.app_commands.checks.has_permissions(administrator=True)
async def setwar(interaction: discord.Interaction, setting: str, value: str):
    """Configure war settings"""
    guild_id = interaction.guild_id
    
    if setting == "poll_day":
        valid_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        if value.capitalize() not in valid_days:
            await interaction.response.send_message(
                get_text(guild_id, "invalid_day"),
                ephemeral=True
            )
            return
        WAR_CONFIG["poll_day"] = value.capitalize()
        
    elif setting == "poll_time":
        try:
            hour, minute = map(int, value.split(':'))
            if not (0 <= hour < 24 and 0 <= minute < 60):
                raise ValueError
            WAR_CONFIG["poll_time"] = {"hour": hour, "minute": minute}
        except:
            await interaction.response.send_message(
                get_text(guild_id, "invalid_time"),
                ephemeral=True
            )
            return
    
    elif setting == "saturday_time":
        try:
            hour, minute = map(int, value.split(':'))
            if not (0 <= hour < 24 and 0 <= minute < 60):
                raise ValueError
            WAR_CONFIG["saturday_war"] = {"hour": hour, "minute": minute}
        except:
            await interaction.response.send_message(
                get_text(guild_id, "invalid_time"),
                ephemeral=True
            )
            return
    
    elif setting == "sunday_time":
        try:
            hour, minute = map(int, value.split(':'))
            if not (0 <= hour < 24 and 0 <= minute < 60):
                raise ValueError
            WAR_CONFIG["sunday_war"] = {"hour": hour, "minute": minute}
        except:
            await interaction.response.send_message(
                get_text(guild_id, "invalid_time"),
                ephemeral=True
            )
            return
    
    elif setting == "reminder_hours":
        try:
            hours = int(value)
            if not (0 <= hours <= 24):
                raise ValueError
            WAR_CONFIG["reminder_hours_before"] = hours
        except:
            await interaction.response.send_message(
                get_text(guild_id, "invalid_number"),
                ephemeral=True
            )
            return
    
    elif setting == "war_channel":
        # Extract channel ID from mention
        if value.startswith("<#") and value.endswith(">"):
            channel_id = int(value[2:-1])
        else:
            await interaction.response.send_message(
                get_text(guild_id, "invalid_channel"),
                ephemeral=True
            )
            return
        
        # Validate channel
        is_valid, error_msg = await validate_war_channel(channel_id, interaction.guild)
        if not is_valid:
            await interaction.response.send_message(
                get_text(guild_id, error_msg),
                ephemeral=True
            )
            return
        
        WAR_CONFIG["war_channel_id"] = channel_id
        value = f"<#{channel_id}>"
    
    save_data()
    
    await interaction.response.send_message(
        get_text(guild_id, "setting_updated", setting=setting, value=value),
        ephemeral=True
    )

@bot.tree.command(name="warconfig", description="View current war configuration")
async def warconfig(interaction: discord.Interaction):
    """Show current war configuration"""
    guild_id = interaction.guild_id
    
    embed = discord.Embed(
        title=get_text(guild_id, "war_config_title"),
        color=discord.Color.blue()
    )
    
    # Poll schedule
    poll_day = get_text(guild_id, WAR_CONFIG["poll_day"].lower())
    poll_time = f"{WAR_CONFIG['poll_time']['hour']:02d}:{WAR_CONFIG['poll_time']['minute']:02d}"
    embed.add_field(
        name=get_text(guild_id, "poll_schedule"),
        value=f"**{get_text(guild_id, 'day')}**: {poll_day}\n"
              f"**{get_text(guild_id, 'time')}**: {poll_time}",
        inline=False
    )
    
    # War times with Discord timestamps
    saturday_time, sunday_time = get_next_war_timestamps()
    embed.add_field(
        name=get_text(guild_id, "war_times"),
        value=f"**{get_text(guild_id, 'saturday')}**: {saturday_time}\n"
              f"**{get_text(guild_id, 'sunday')}**: {sunday_time}",
        inline=False
    )
    
    # Reminders
    embed.add_field(
        name=get_text(guild_id, "reminders"),
        value=f"{WAR_CONFIG['reminder_hours_before']} {get_text(guild_id, 'hours_before')}",
        inline=False
    )
    
    # War channel
    if WAR_CONFIG["war_channel_id"]:
        channel = interaction.guild.get_channel(WAR_CONFIG["war_channel_id"])
        channel_text = channel.mention if channel else get_text(guild_id, "channel_not_found")
    else:
        channel_text = get_text(guild_id, "not_configured")
    
    embed.add_field(
        name=get_text(guild_id, "war_channel"),
        value=channel_text,
        inline=False
    )
    
    # Language
    lang = get_language(guild_id)
    lang_name = "English" if lang == "en" else "العربية"
    embed.add_field(
        name=get_text(guild_id, "language"),
        value=lang_name,
        inline=False
    )
    
    embed.set_footer(text=get_text(guild_id, "use_setwar"))
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="testreminder", description="Test war reminder (Admin only)")
@discord.app_commands.describe(day="Which day's reminder to test")
@discord.app_commands.choices(day=[
    discord.app_commands.Choice(name="Saturday", value="saturday"),
    discord.app_commands.Choice(name="Sunday", value="sunday")
])
@discord.app_commands.checks.has_permissions(administrator=True)
async def testreminder(interaction: discord.Interaction, day: str):
    """Test sending a war reminder"""
    guild_id = interaction.guild_id
    
    if not WAR_CONFIG["war_channel_id"]:
        await interaction.response.send_message(
            get_text(guild_id, "war_channel_not_configured"),
            ephemeral=True
        )
        return
    
    channel = interaction.guild.get_channel(WAR_CONFIG["war_channel_id"])
    if not channel:
        await interaction.response.send_message(
            get_text(guild_id, "channel_deleted"),
            ephemeral=True
        )
        return
    
    await interaction.response.defer(ephemeral=True)
    
    # Capitalize day name for display
    day_name = "Saturday" if day == "saturday" else "Sunday"
    
    # Send test reminder
    await send_war_reminder(day_name)
    
    await interaction.followup.send(
        get_text(guild_id, "test_reminder_sent", day=day_name, channel=channel.mention),
        ephemeral=True
    )

@bot.tree.command(name="synccommands", description="Force sync slash commands (Admin only)")
@discord.app_commands.checks.has_permissions(administrator=True)
async def synccommands(interaction: discord.Interaction):
    """Manually sync slash commands"""
    guild_id = interaction.guild_id
    await interaction.response.defer(ephemeral=True)
    
    try:
        await bot.tree.sync()
        await interaction.followup.send(
            get_text(guild_id, "commands_synced"),
            ephemeral=True
        )
    except Exception as e:
        await interaction.followup.send(
            f"{get_text(guild_id, 'error_occurred')}\n{str(e)}",
            ephemeral=True
        )

@bot.tree.command(name="setlanguage", description="Set server language (Admin only)")
@discord.app_commands.describe(language="Language to use")
@discord.app_commands.choices(language=[
    discord.app_commands.Choice(name="English", value="english"),
    discord.app_commands.Choice(name="العربية (Arabic)", value="arabic")
])
@discord.app_commands.checks.has_permissions(administrator=True)
async def setlanguage(interaction: discord.Interaction, language: str):
    """Set server language"""
    guild_id = interaction.guild_id
    
    lang_code = "en" if language == "english" else "ar"
    server_languages[guild_id] = lang_code
    save_language_data()
    
    lang_display = "English" if lang_code == "en" else "العربية"
    await interaction.response.send_message(
        get_text(guild_id, "language_set", language=lang_display),
        ephemeral=True
    )

# -----------------------------
# Health Check Web Server
# -----------------------------
async def health_check(request):
    return web.Response(text="OK", status=200)

async def start_web_server():
    """Start a basic web server for health checks"""
    app = web.Application()
    app.router.add_get('/health', health_check)
    app.router.add_get('/', health_check)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.getenv('PORT', 8000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    logger.info(f"🌐 Web server started on port {port}")
    return runner

# -----------------------------
# Scheduled Tasks
# -----------------------------
@tasks.loop(minutes=1)
async def check_war_schedule():
    """Check if it's time to post poll or send reminders"""
    tz = pytz.timezone(WAR_CONFIG["timezone"])
    now = datetime.now(tz)
    
    # Check if it's time to post the weekly poll
    if (now.strftime("%A") == WAR_CONFIG["poll_day"] and
        now.hour == WAR_CONFIG["poll_time"]["hour"] and
        now.minute == WAR_CONFIG["poll_time"]["minute"]):
        await post_automatic_poll()
    
    # Check for Saturday reminder
    if (now.weekday() == 5 and  # Saturday
        now.hour == WAR_CONFIG["saturday_war"]["hour"] - WAR_CONFIG["reminder_hours_before"] and
        now.minute == WAR_CONFIG["saturday_war"]["minute"]):
        await send_war_reminder("Saturday")
    
    # Check for Sunday reminder
    if (now.weekday() == 6 and  # Sunday
        now.hour == WAR_CONFIG["sunday_war"]["hour"] - WAR_CONFIG["reminder_hours_before"] and
        now.minute == WAR_CONFIG["sunday_war"]["minute"]):
        await send_war_reminder("Sunday")

async def post_automatic_poll():
    """Post automatic weekly war poll"""
    if not WAR_CONFIG["war_channel_id"]:
        logger.warning("War channel not configured, skipping automatic poll")
        return
    
    try:
        channel = bot.get_channel(WAR_CONFIG["war_channel_id"])
        if not channel:
            logger.error(f"War channel {WAR_CONFIG['war_channel_id']} not found")
            return
        
        guild = channel.guild
        guild_id = guild.id
        
        # Validate channel still exists and has permissions
        is_valid, error_msg = await validate_war_channel(WAR_CONFIG["war_channel_id"], guild)
        if not is_valid:
            logger.error(f"War channel validation failed: {error_msg}")
            return
        
        # Reset poll data
        war_poll_data["saturday_players"].clear()
        war_poll_data["sunday_players"].clear()
        war_poll_data["both_days_players"].clear()
        war_poll_data["not_playing"].clear()
        save_data()
        
        # Get Discord timestamps
        saturday_time, sunday_time = get_next_war_timestamps()
        
        embed = discord.Embed(
            title=get_text(guild_id, "war_poll_title"),
            description=f"{get_text(guild_id, 'war_poll_desc')}\n\n"
                        f"🗓️ **{get_text(guild_id, 'saturday_war')}**: {saturday_time}\n"
                        f"🗓️ **{get_text(guild_id, 'sunday_war')}**: {sunday_time}\n\n"
                        f"*{get_text(guild_id, 'times_local')}*",
            color=discord.Color.red(),
            timestamp=datetime.now()
        )
        
        embed.add_field(
            name=f"📅 {get_text(guild_id, 'saturday_only')} (0 {get_text(guild_id, 'players')})", 
            value=f"{get_text(guild_id, 'click_button')}", 
            inline=True
        )
        embed.add_field(
            name=f"📅 {get_text(guild_id, 'sunday_only')} (0 {get_text(guild_id, 'players')})", 
            value=f"{get_text(guild_id, 'click_button')}", 
            inline=True
        )
        embed.add_field(
            name=f"⚔️ {get_text(guild_id, 'both_days')} (0 {get_text(guild_id, 'players')})", 
            value=f"{get_text(guild_id, 'click_button')}", 
            inline=True
        )
        embed.add_field(
            name=f"📊 {get_text(guild_id, 'total_saturday')}: 0", 
            value=get_text(guild_id, "sat_sun_players"), 
            inline=True
        )
        embed.add_field(
            name=f"📊 {get_text(guild_id, 'total_sunday')}: 0", 
            value=get_text(guild_id, "sun_both_players"), 
            inline=True
        )
        embed.add_field(
            name=f"❌ {get_text(guild_id, 'not_playing')} (0 {get_text(guild_id, 'players')})", 
            value=f"{get_text(guild_id, 'click_button')}", 
            inline=True
        )
        
        embed.set_footer(text=get_text(guild_id, "use_warlist"))
        
        message = await channel.send(embed=embed, view=WarPollButtons())
        war_poll_data["message_id"] = message.id
        save_data()
        
        logger.info("✅ Automatic war poll posted")
        
    except Exception as e:
        logger.error(f"Error posting automatic poll: {e}")

async def send_war_reminder(day: str):
    """Send war reminder with participant mentions"""
    if not WAR_CONFIG["war_channel_id"]:
        logger.warning("War channel not configured, skipping reminder")
        return
    
    try:
        channel = bot.get_channel(WAR_CONFIG["war_channel_id"])
        if not channel:
            logger.error(f"War channel {WAR_CONFIG['war_channel_id']} not found")
            return
        
        guild_id = channel.guild.id
        
        # Get participants for the day
        if day == "Saturday":
            participants = war_poll_data["saturday_players"].union(war_poll_data["both_days_players"])
            war_timestamp = get_discord_timestamp(
                WAR_CONFIG["saturday_war"]["hour"],
                WAR_CONFIG["saturday_war"]["minute"],
                0 if datetime.now(pytz.timezone(WAR_CONFIG["timezone"])).weekday() == 5 else 1
            )
        else:
            participants = war_poll_data["sunday_players"].union(war_poll_data["both_days_players"])
            war_timestamp = get_discord_timestamp(
                WAR_CONFIG["sunday_war"]["hour"],
                WAR_CONFIG["sunday_war"]["minute"],
                0 if datetime.now(pytz.timezone(WAR_CONFIG["timezone"])).weekday() == 6 else 1
            )
        
        # Create mentions string for all participants
        mentions = " ".join([f"<@{uid}>" for uid in participants])
        
        embed = discord.Embed(
            title=get_text(guild_id, "war_reminder_title", day=day),
            description=f"{get_text(guild_id, 'war_starts_in', hours=WAR_CONFIG['reminder_hours_before'], time=war_timestamp)}\n\n"
                        f"{get_text(guild_id, 'warriors_ready', count=len(participants))}\n\n"
                        f"*{get_text(guild_id, 'times_local')}*",
            color=discord.Color.orange(),
            timestamp=datetime.now()
        )
        
        embed.set_footer(text=get_text(guild_id, "use_warlist_reminder"))
        
        # Send with mentions - mention participants if any exist, otherwise ping everyone
        await channel.send(content=mentions if participants else "@everyone", embed=embed)
        
        logger.info(f"✅ {day} war reminder sent with {len(participants)} mentions")
        
    except Exception as e:
        logger.error(f"Error sending {day} reminder: {e}")

# -----------------------------
# Bot Events
# -----------------------------
@bot.event
async def on_ready():
    # Register persistent views
    bot.add_view(WarPollButtons())
    bot.add_view(BuildSelectView())
    
    await bot.tree.sync()
    
    # Start scheduled tasks
    if not check_war_schedule.is_running():
        check_war_schedule.start()
    
    logger.info(f"✅ Logged in as {bot.user}")
    logger.info(f"📊 Serving {len(bot.guilds)} guild(s)")
    logger.info(f"🔧 Commands synced!")
    logger.info(f"⚔️ War scheduler running")

# Error handling for permission errors
@postbuilds.error
@createroles.error
@warpoll.error
@setwar.error
@synccommands.error
@setlanguage.error
@testreminder.error
async def admin_error(interaction: discord.Interaction, error):
    """Handle permission errors for admin commands"""
    if isinstance(error, discord.app_commands.errors.MissingPermissions):
        try:
            await interaction.response.send_message(
                get_text(interaction.guild_id, "permission_denied"),
                ephemeral=True
            )
        except:
            pass

# -----------------------------
# Main startup
# -----------------------------
async def main():
    """Start both the web server and the Discord bot"""
    web_runner = await start_web_server()
    
    TOKEN = os.getenv('DISCORD_BOT_TOKEN')
    if not TOKEN:
        logger.error("❌ ERROR: DISCORD_BOT_TOKEN not found in environment variables!")
        logger.error("Please set DISCORD_BOT_TOKEN in your environment")
        return
    
    try:
        async with bot:
            await bot.start(TOKEN)
    except discord.errors.HTTPException as e:
        if e.status == 429:
            retry_after = e.response.headers.get('Retry-After', 60)
            logger.warning(f"⏳ Rate limited. Waiting {retry_after} seconds before retrying...")
            await asyncio.sleep(float(retry_after))
            async with bot:
                await bot.start(TOKEN)
        else:
            raise
    finally:
        await web_runner.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
