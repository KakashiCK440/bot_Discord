"""
War commands cog for Discord bot.
Handles war polls, participant lists, configuration, and reminders.
"""

import asyncio
import discord
from discord.ext import commands
from discord import app_commands
import pytz
from datetime import datetime
from config import BUILDS, BUILD_ICONS, WEAPON_ICONS
from utils.helpers import get_text, get_discord_timestamp
from utils.war_helpers import (
    get_current_poll_week,
    get_war_participants,
    set_war_participation,
    get_war_config,
    update_war_setting
)
from locales import LANGUAGES


class WarCog(commands.Cog):
    """War-related commands for managing war participation and configuration"""
    
    def __init__(self, bot, db):
        self.bot = bot
        self.db = db
    
    @app_commands.command(name="warpoll", description="Post war participation poll (Admin)")
    @app_commands.checks.has_permissions(administrator=True)
    async def warpoll(self, interaction: discord.Interaction):
        """Post war poll (embed in your language)"""
        guild_id = interaction.guild_id
        uid = interaction.user.id
        await interaction.response.defer(ephemeral=True)
        config = await self.db.async_run(get_war_config, self.db, guild_id)
        
        channel_id = config.get("war_channel_id")
        if not channel_id:
            await interaction.followup.send(
                get_text(self.db, LANGUAGES, guild_id, "err_war_channel_not_set", uid),
                ephemeral=True
            )
            return
        
        channel = interaction.guild.get_channel(channel_id)
        if not channel:
            await interaction.followup.send(
                get_text(self.db, LANGUAGES, guild_id, "err_war_channel_not_found", uid),
                ephemeral=True
            )
            return
        
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
            title=get_text(self.db, LANGUAGES, guild_id, "war_poll_title", uid),
            description=get_text(self.db, LANGUAGES, guild_id, "war_poll_desc", uid),
            color=discord.Color.red()
        )
        
        embed.add_field(
            name=f"📅 {get_text(self.db, LANGUAGES, guild_id, 'saturday', uid)}",
            value=f"⏰ {saturday_time}",
            inline=True
        )
        
        embed.add_field(
            name=f"📅 {get_text(self.db, LANGUAGES, guild_id, 'sunday', uid)}",
            value=f"⏰ {sunday_time}",
            inline=True
        )
        
        embed.add_field(
            name="ℹ️",
            value=get_text(self.db, LANGUAGES, guild_id, "use_warlist", uid),
            inline=False
        )
        
        embed.set_footer(text=get_text(self.db, LANGUAGES, guild_id, "times_local", uid))
        
        # Create buttons
        view = WarPollView(guild_id, self.db)
        
        await channel.send(embed=embed, view=view)
        
        await interaction.followup.send(
            get_text(self.db, LANGUAGES, guild_id, "war_poll_posted", uid),
            ephemeral=True
        )
    
    @app_commands.command(name="warlist", description="Show war participant lists")
    @app_commands.describe(day="Filter by day (optional)")
    @app_commands.choices(day=[
        app_commands.Choice(name="Saturday", value="saturday"),
        app_commands.Choice(name="Sunday", value="sunday")
    ])
    async def warlist(self, interaction: discord.Interaction, day: app_commands.Choice[str] = None):
        """Show war participants with detailed build and weapon information"""
        from collections import namedtuple
        _EmbedField = namedtuple("_EmbedField", ["name", "value", "inline"])
        guild_id = interaction.guild_id
        user_id = interaction.user.id
        await interaction.response.defer()

        # Run all blocking DB work in a thread so the event loop stays free
        # (prevents defer() on concurrent calls from expiring)
        def fetch_all_data():
            participants = get_war_participants(self.db, guild_id)
            config = get_war_config(self.db, guild_id)
            saturday_ids = participants["saturday_players"] | participants["both_days_players"]
            sunday_ids   = participants["sunday_players"]   | participants["both_days_players"]

            def build_detail(player_ids):
                build_data = {"DPS": [], "Tank": [], "Healer": [], "Unknown": []}
                for pid in player_ids:
                    player  = self.db.get_player(pid, guild_id)
                    weapons = self.db.get_player_weapons(pid, guild_id) or []
                    if player:
                        name  = player.get("in_game_name", f"<@{pid}>")
                        build = player.get("build_type", "Unknown")
                        icons = "".join(WEAPON_ICONS.get(w, "⚔️") for w in weapons[:2])
                        entry = f"{name} {icons}".strip()
                    else:
                        build = "Unknown"
                        entry = f"<@{pid}>"
                    build_data.get(build, build_data["Unknown"]).append(entry)
                return build_data

            return config, saturday_ids, sunday_ids, build_detail(saturday_ids), build_detail(sunday_ids)

        config, saturday_players, sunday_players, sat_builds, sun_builds = \
            await self.db.async_run(fetch_all_data)

        guild_timezone = config.get("timezone", "Africa/Cairo")
        FIELD_LIMIT = 1024

        def format_build_fields(build_type_name, players_list):
            """Chunk a build-type player list into ≤1024-char embed fields."""
            if not players_list:
                return []
            icon   = BUILD_ICONS.get(build_type_name, "❓")
            base   = f"{icon} {build_type_name} ({len(players_list)})"
            chunk, chunk_len, part, out = [], 0, 1, []
            for entry in players_list:
                line = f"• {entry}"
                if chunk_len + len(line) + 1 > FIELD_LIMIT and chunk:
                    out.append(_EmbedField(
                        name=base if part == 1 else f"{icon} {build_type_name} (cont. {part})",
                        value="\n".join(chunk), inline=True
                    ))
                    part += 1; chunk = [line]; chunk_len = len(line) + 1
                else:
                    chunk.append(line); chunk_len += len(line) + 1
            if chunk:
                out.append(_EmbedField(
                    name=base if part == 1 else f"{icon} {build_type_name} (cont. {part})",
                    value="\n".join(chunk), inline=True
                ))
            return out

        def add_day(embed, day_label, time_str, total_label, player_ids, builds):
            total = len(player_ids)
            summary = " • ".join(
                f"{BUILD_ICONS.get(bt, '❓')} **{len(builds[bt])} {bt}**"
                for bt in ("DPS", "Tank", "Healer", "Unknown") if builds[bt]
            )
            embed.add_field(
                name=f"📅 {day_label} — {time_str}",
                value=f"{total_label}: **{total}**" + (f"\n{summary}" if summary else ""),
                inline=False
            )
            if total:
                for bt in ("DPS", "Tank", "Healer", "Unknown"):
                    for f in format_build_fields(bt, builds[bt]):
                        embed.add_field(name=f.name, value=f.value, inline=f.inline)
            else:
                embed.add_field(
                    name=get_text(self.db, LANGUAGES, guild_id, "no_players", user_id),
                    value="\u200b", inline=False
                )

        embed = discord.Embed(
            title=get_text(self.db, LANGUAGES, guild_id, "war_list_title", user_id),
            color=discord.Color.orange()
        )

        if day is None or day.value == "saturday":
            now = datetime.now(pytz.timezone(guild_timezone))
            wd  = now.weekday()
            sat_delta = 5 - wd if wd < 5 else (0 if wd == 5 else 6)
            saturday_time = get_discord_timestamp(
                config["saturday_war"]["hour"], config["saturday_war"]["minute"],
                sat_delta, guild_timezone
            )
            add_day(embed,
                get_text(self.db, LANGUAGES, guild_id, "saturday", user_id), saturday_time,
                get_text(self.db, LANGUAGES, guild_id, "total_saturday", user_id),
                saturday_players, sat_builds)

        if day is None or day.value == "sunday":
            now = datetime.now(pytz.timezone(guild_timezone))
            wd  = now.weekday()
            sun_delta = 6 - wd if wd < 6 else (0 if wd == 6 else 7)
            sunday_time = get_discord_timestamp(
                config["sunday_war"]["hour"], config["sunday_war"]["minute"],
                sun_delta, guild_timezone
            )
            add_day(embed,
                get_text(self.db, LANGUAGES, guild_id, "sunday", user_id), sunday_time,
                get_text(self.db, LANGUAGES, guild_id, "total_sunday", user_id),
                sunday_players, sun_builds)

        embed.set_footer(text=get_text(self.db, LANGUAGES, guild_id, "footer_builds", user_id))
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="setwar", description="Configure war settings (Admin)")
    @app_commands.describe(
        setting="Setting to configure",
        value="New value for the setting"
    )
    @app_commands.choices(setting=[
        app_commands.Choice(name="War Channel", value="war_channel_id"),
        app_commands.Choice(name="Saturday War Hour", value="saturday_war_hour"),
        app_commands.Choice(name="Saturday War Minute", value="saturday_war_minute"),
        app_commands.Choice(name="Sunday War Hour", value="sunday_war_hour"),
        app_commands.Choice(name="Sunday War Minute", value="sunday_war_minute"),
        app_commands.Choice(name="Reminder Hours Before", value="reminder_hours_before"),
        app_commands.Choice(name="Timezone", value="timezone")
    ])
    @app_commands.checks.has_permissions(administrator=True)
    async def setwar(self, interaction: discord.Interaction, setting: app_commands.Choice[str], value: str):
        """Configure war settings"""
        guild_id = interaction.guild_id
        user_id = interaction.user.id
        
        setting_key = setting.value
        
        # Parse value based on setting type
        if setting_key == "war_channel_id":
            # Extract channel ID from mention or use raw ID
            if value.startswith("<#") and value.endswith(">"):
                channel_id = int(value[2:-1])
            else:
                try:
                    channel_id = int(value)
                except ValueError:
                    await interaction.response.send_message("❌ Invalid channel ID", ephemeral=True)
                    return
            
            # Verify channel exists
            channel = interaction.guild.get_channel(channel_id)
            if not channel:
                await interaction.response.send_message("❌ Channel not found", ephemeral=True)
                return
            
            update_war_setting(self.db, guild_id, setting_key, channel_id)
            display_value = f"<#{channel_id}>"
        
        elif setting_key in ["saturday_war_hour", "sunday_war_hour"]:
            try:
                hour = int(value)
                if hour < 0 or hour > 23:
                    await interaction.response.send_message("❌ Hour must be between 0 and 23", ephemeral=True)
                    return
                update_war_setting(self.db, guild_id, setting_key, hour)
                display_value = f"{hour}:00"
            except ValueError:
                await interaction.response.send_message("❌ Invalid hour", ephemeral=True)
                return
        
        elif setting_key in ["saturday_war_minute", "sunday_war_minute"]:
            try:
                minute = int(value)
                if minute < 0 or minute > 59:
                    await interaction.response.send_message("❌ Minute must be between 0 and 59", ephemeral=True)
                    return
                update_war_setting(self.db, guild_id, setting_key, minute)
                display_value = f":{minute:02d}"
            except ValueError:
                await interaction.response.send_message("❌ Invalid minute", ephemeral=True)
                return
        
        elif setting_key == "reminder_hours_before":
            try:
                hours = int(value)
                if hours < 0 or hours > 48:
                    await interaction.response.send_message("❌ Hours must be between 0 and 48", ephemeral=True)
                    return
                update_war_setting(self.db, guild_id, setting_key, hours)
                display_value = f"{hours} hours"
            except ValueError:
                await interaction.response.send_message("❌ Invalid hours", ephemeral=True)
                return
        
        elif setting_key == "timezone":
            # Validate timezone
            try:
                pytz.timezone(value)
                update_war_setting(self.db, guild_id, setting_key, value)
                display_value = value
            except pytz.exceptions.UnknownTimeZoneError:
                await interaction.response.send_message("❌ Invalid timezone", ephemeral=True)
                return
        else:
            update_war_setting(self.db, guild_id, setting_key, value)
            display_value = value
        
        await interaction.response.send_message(
            get_text(self.db, LANGUAGES, guild_id, "setting_updated", user_id).format(
                setting=setting.name,
                value=display_value
            ),
            ephemeral=True
        )
    
    @app_commands.command(name="warconfig", description="View current war configuration")
    async def warconfig(self, interaction: discord.Interaction):
        """View war configuration"""
        guild_id = interaction.guild_id
        user_id = interaction.user.id
        
        config = get_war_config(self.db, guild_id)
        
        embed = discord.Embed(
            title="⚙️ War Configuration",
            color=discord.Color.blue()
        )
        
        # War channel
        channel_id = config.get("war_channel_id")
        if channel_id:
            embed.add_field(
                name="📢 War Channel",
                value=f"<#{channel_id}>",
                inline=False
            )
        else:
            embed.add_field(
                name="📢 War Channel",
                value="Not set",
                inline=False
            )
        
        # War times
        saturday_time = f"{config['saturday_war']['hour']:02d}:{config['saturday_war']['minute']:02d}"
        sunday_time = f"{config['sunday_war']['hour']:02d}:{config['sunday_war']['minute']:02d}"
        
        embed.add_field(
            name="⏰ Saturday War Time",
            value=saturday_time,
            inline=True
        )
        
        embed.add_field(
            name="⏰ Sunday War Time",
            value=sunday_time,
            inline=True
        )
        
        # Reminder
        embed.add_field(
            name="⏰ Reminder",
            value=f"{config['reminder_hours']} hours before",
            inline=True
        )
        
        # Timezone
        embed.add_field(
            name="🌍 Timezone",
            value=config.get("timezone", "Africa/Cairo"),
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="testreminder", description="Test war reminder (Admin)")
    @app_commands.describe(day="Day to test reminder for")
    @app_commands.choices(day=[
        app_commands.Choice(name="Saturday", value="saturday"),
        app_commands.Choice(name="Sunday", value="sunday")
    ])
    @app_commands.checks.has_permissions(administrator=True)
    async def testreminder(self, interaction: discord.Interaction, day: app_commands.Choice[str]):
        """Test war reminder"""
        guild_id = interaction.guild_id
        user_id = interaction.user.id
        
        config = get_war_config(self.db, guild_id)
        channel_id = config.get("war_channel_id")
        
        if not channel_id:
            await interaction.response.send_message(
                get_text(self.db, LANGUAGES, guild_id, "err_war_channel_not_set", user_id),
                ephemeral=True
            )
            return
        
        channel = interaction.guild.get_channel(channel_id)
        if not channel:
            await interaction.response.send_message(
                get_text(self.db, LANGUAGES, guild_id, "err_war_channel_not_found", user_id),
                ephemeral=True
            )
            return
        
        # Send test reminder
        day_name = get_text(self.db, LANGUAGES, guild_id, day.value, user_id)
        
        embed = discord.Embed(
            title=f"⚔️ {day_name} War Reminder (TEST)",
            description=f"This is a test reminder for {day_name}'s war!",
            color=discord.Color.red()
        )
        
        await channel.send(embed=embed)
        
        await interaction.response.send_message(
            get_text(self.db, LANGUAGES, guild_id, "test_reminder_sent", user_id).format(channel=channel.mention),
            ephemeral=True
        )
    
    @app_commands.command(name="resetwar", description="🔄 Reset current week's war data (Admin)")
    @app_commands.describe(confirm="Type 'confirm' to reset")
    @app_commands.checks.has_permissions(administrator=True)
    async def resetwar(self, interaction: discord.Interaction, confirm: str):
        """Reset current week's war data"""
        guild_id = interaction.guild_id
        
        if confirm.lower() != "confirm":
            await interaction.response.send_message(
                "❌ Please type 'confirm' to reset war data",
                ephemeral=True
            )
            return
        
        poll_week = get_current_poll_week()
        self.db.clear_war_participants(guild_id, poll_week)
        
        await interaction.response.send_message(
            "✅ Current week's war data has been reset!",
            ephemeral=True
        )
    
    @app_commands.command(name="resetallwar", description="🔄 Reset ALL war data including old weeks (Admin)")
    @app_commands.describe(confirm="Type 'CONFIRM ALL' to reset everything")
    @app_commands.checks.has_permissions(administrator=True)
    async def resetallwar(self, interaction: discord.Interaction, confirm: str):
        """Reset ALL war data"""
        guild_id = interaction.guild_id
        
        if confirm != "CONFIRM ALL":
            await interaction.response.send_message(
                "❌ Please type 'CONFIRM ALL' (exactly) to reset all war data",
                ephemeral=True
            )
            return
        
        self.db.clear_all_war_participants(guild_id)
        
        await interaction.response.send_message(
            "✅ ALL war data has been reset!",
            ephemeral=True
        )


class WarPollView(discord.ui.View):
    """View for war poll buttons"""
    
    def __init__(self, guild_id: int, db):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        self.db = db
    
    @discord.ui.button(label="Saturday Only", style=discord.ButtonStyle.primary, custom_id="war_saturday", emoji="📅")
    async def saturday_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_vote(interaction, "saturday")
    
    @discord.ui.button(label="Sunday Only", style=discord.ButtonStyle.primary, custom_id="war_sunday", emoji="📅")
    async def sunday_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_vote(interaction, "sunday")
    
    @discord.ui.button(label="Both Days", style=discord.ButtonStyle.success, custom_id="war_both", emoji="✅")
    async def both_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_vote(interaction, "both")
    
    @discord.ui.button(label="Not Playing", style=discord.ButtonStyle.secondary, custom_id="war_none", emoji="❌")
    async def none_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_vote(interaction, "none")
    
    async def _handle_vote(self, interaction: discord.Interaction, choice: str):
        """Handle war poll vote - all DB work in a thread to keep the event loop free"""
        guild_id = interaction.guild_id
        user_id = interaction.user.id

        # Defer immediately - must fire within 3 seconds
        for attempt in range(3):
            try:
                await interaction.response.defer(ephemeral=True)
                break
            except discord.HTTPException as e:
                if e.status == 429 and attempt < 2:
                    await asyncio.sleep(float(getattr(e, 'retry_after', 5)))
                else:
                    return  # Interaction expired or hard failure

        # Run ALL DB work in one thread - never block the event loop
        def do_db_work():
            from utils.war_helpers import get_current_poll_week
            # 1. Check profile
            player = self.db.get_player(user_id, guild_id)
            if not player:
                return None, None

            # 2. Get previous vote
            poll_week = get_current_poll_week()
            participants_by_type = self.db.get_war_participants_by_type(guild_id, poll_week)
            previous_choice = None
            for ptype, plist in participants_by_type.items():
                for p in plist:
                    if p.get("user_id") == user_id:
                        previous_choice = ptype
                        break
                if previous_choice:
                    break

            # 3. Save new vote
            set_war_participation(self.db, guild_id, user_id, choice)
            return player, previous_choice

        player, previous_choice = await self.db.async_run(do_db_work)

        if player is None:
            await interaction.followup.send(
                get_text(self.db, LANGUAGES, guild_id, "err_no_profile_war", user_id),
                ephemeral=True
            )
            return

        # Build confirmation message (pure Python, no DB calls)
        def choice_label(c):
            key_map = {"saturday": "saturday", "sunday": "sunday", "both": "both_days", "none": "not_playing"}
            return get_text(self.db, LANGUAGES, guild_id, key_map.get(c, "not_playing"), user_id)

        new_label  = choice_label(choice)
        prev_label = choice_label(previous_choice) if previous_choice else None

        if previous_choice and previous_choice != choice:
            if choice == "none":
                message = (
                    f"✅ {get_text(self.db, LANGUAGES, guild_id, 'removed_from_war', user_id)}\n\n"
                    f"**{get_text(self.db, LANGUAGES, guild_id, 'previously', user_id)}:** {prev_label}"
                )
            else:
                message = (
                    f"✅ {get_text(self.db, LANGUAGES, guild_id, 'vote_updated', user_id)}\n\n"
                    f"**{get_text(self.db, LANGUAGES, guild_id, 'previously', user_id)}:** {prev_label} → "
                    f"**{get_text(self.db, LANGUAGES, guild_id, 'now', user_id)}:** {new_label}"
                )
        elif previous_choice == choice:
            message = f"ℹ️ {get_text(self.db, LANGUAGES, guild_id, 'already_registered', user_id)}: **{new_label}**"
        else:
            key_map = {
                "saturday": "registered_saturday",
                "sunday":   "registered_sunday",
                "both":     "registered_both",
                "none":     "registered_not_playing",
            }
            message = get_text(self.db, LANGUAGES, guild_id, key_map.get(choice, "registered_not_playing"), user_id)

        # Send confirmation with 429 retry
        for attempt in range(3):
            try:
                await interaction.followup.send(message, ephemeral=True)
                break
            except discord.HTTPException as e:
                if e.status == 429 and attempt < 2:
                    await asyncio.sleep(float(getattr(e, 'retry_after', 5)))
                else:
                    import logging
                    logging.getLogger(__name__).warning(
                        f"Failed to send war vote confirmation to {user_id} after retries: {e}"
                    )
                    break

    # ── /setpollschedule ───────────────────────────────────────────────────────
    @app_commands.command(
        name="setpollschedule",
        description="Set the day and time for the automatic war poll (Admin)"
    )
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        day="Day the poll is posted each week",
        hour="Hour to post (0-23, 24-hour format)",
        minute="Minute to post (0-59)"
    )
    @app_commands.choices(day=[
        app_commands.Choice(name="Monday",    value="Monday"),
        app_commands.Choice(name="Tuesday",   value="Tuesday"),
        app_commands.Choice(name="Wednesday", value="Wednesday"),
        app_commands.Choice(name="Thursday",  value="Thursday"),
        app_commands.Choice(name="Friday",    value="Friday"),
        app_commands.Choice(name="Saturday",  value="Saturday"),
        app_commands.Choice(name="Sunday",    value="Sunday"),
    ])
    async def setpollschedule(
        self,
        interaction: discord.Interaction,
        day: app_commands.Choice[str] = None,
        hour: int = None,
        minute: int = None
    ):
        """Set or view the automatic war poll schedule"""
        guild_id = interaction.guild_id
        uid = interaction.user.id
        await interaction.response.defer(ephemeral=True)

        # If nothing provided, show current schedule
        if day is None and hour is None and minute is None:
            config = await self.db.async_run(get_war_config, self.db, guild_id)
            current_day = config.get("poll_day", "Friday")
            current_hour = config["poll_time"]["hour"]
            current_minute = config["poll_time"]["minute"]
            tz = config.get("timezone", "Africa/Cairo")

            embed = discord.Embed(
                title="📅 War Poll Schedule",
                description=(
                    f"**Day:** {current_day}\n"
                    f"**Time:** {current_hour:02d}:{current_minute:02d} ({tz})\n\n"
                    f"Use `/setpollschedule day hour minute` to change it."
                ),
                color=discord.Color.blue()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Validate inputs
        if hour is not None and not (0 <= hour <= 23):
            await interaction.followup.send("❌ Hour must be between 0 and 23.", ephemeral=True)
            return
        if minute is not None and not (0 <= minute <= 59):
            await interaction.followup.send("❌ Minute must be between 0 and 59.", ephemeral=True)
            return

        # Apply changes
        changes = []
        if day is not None:
            await self.db.async_run(update_war_setting, self.db, guild_id, "poll_day", day.value)
            changes.append(f"**Day:** {day.value}")
        if hour is not None:
            await self.db.async_run(update_war_setting, self.db, guild_id, "poll_time_hour", hour)
            changes.append(f"**Hour:** {hour:02d}")
        if minute is not None:
            await self.db.async_run(update_war_setting, self.db, guild_id, "poll_time_minute", minute)
            changes.append(f"**Minute:** {minute:02d}")

        config = await self.db.async_run(get_war_config, self.db, guild_id)
        new_day    = config.get("poll_day", "Friday")
        new_hour   = config["poll_time"]["hour"]
        new_minute = config["poll_time"]["minute"]
        tz         = config.get("timezone", "Africa/Cairo")

        embed = discord.Embed(
            title="✅ Poll Schedule Updated",
            description="\n".join(changes),
            color=discord.Color.green()
        )
        embed.add_field(
            name="📋 New Schedule",
            value=f"Every **{new_day}** at **{new_hour:02d}:{new_minute:02d}** ({tz})",
            inline=False
        )
        embed.set_footer(text="The poll will be posted automatically at this time each week.")
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    """Setup function to add cog to bot"""
    from database import Database
    db = Database("data/bot_data.db")
    await bot.add_cog(WarCog(bot, db))
