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
        guild_id = interaction.guild_id
        user_id = interaction.user.id
        await interaction.response.defer()
        
        participants = await self.db.async_run(get_war_participants, self.db, guild_id)
        
        saturday_players = participants["saturday_players"] | participants["both_days_players"]
        sunday_players = participants["sunday_players"] | participants["both_days_players"]
        
        # Get war times
        config = await self.db.async_run(get_war_config, self.db, guild_id)
        guild_timezone = config.get("timezone", "Africa/Cairo")
        
        # Helper function to get player details organized by build
        def get_player_details_by_build(player_ids):
            if not player_ids:
                return None, {}
            
            builds = {"DPS": [], "Tank": [], "Healer": [], "Unknown": []}
            
            for pid in player_ids:
                player = self.db.get_player(pid, guild_id)
                if player:
                    name = player.get('in_game_name', f'<@{pid}>')
                    build = player.get('build_type', 'Unknown')
                    weapons = self.db.get_player_weapons(pid, guild_id)
                    
                    # Format weapons with icons
                    weapon_str = ""
                    if weapons:
                        weapon_icons = [f"{WEAPON_ICONS.get(w, '⚔️')}" for w in weapons[:2]]
                        weapon_str = " " + "".join(weapon_icons)
                    
                    builds.get(build, builds["Unknown"]).append(f"{name}{weapon_str}")
                else:
                    builds["Unknown"].append(f"<@{pid}>")
            
            # Count by build
            counts = {
                "DPS": len(builds["DPS"]),
                "Tank": len(builds["Tank"]),
                "Healer": len(builds["Healer"]),
                "Unknown": len(builds["Unknown"])
            }
            
            return counts, builds
        
        # Helper to format player list — hard-capped at Discord's 1024-char field limit
        FIELD_LIMIT = 1024

        def format_player_list(builds, counts, total):
            lines = []

            # Build summary line (e.g. "⚔ 5 DPS • 🛡 2 Tank")
            summary_parts = []
            if counts["DPS"] > 0:
                summary_parts.append(f"{BUILD_ICONS['DPS']} **{counts['DPS']} DPS**")
            if counts["Tank"] > 0:
                summary_parts.append(f"{BUILD_ICONS['Tank']} **{counts['Tank']} Tank**")
            if counts["Healer"] > 0:
                summary_parts.append(f"{BUILD_ICONS['Healer']} **{counts['Healer']} Healer**")
            if summary_parts:
                lines.append(" • ".join(summary_parts))
                lines.append("")

            # Iterate builds, adding lines until we approach the character limit
            max_per_build = 15
            char_budget = FIELD_LIMIT - 50  # leave 50 chars for the overflow notice
            current_len = sum(len(l) + 1 for l in lines)  # +1 for newline
            overflow = 0

            for build_type in ["DPS", "Tank", "Healer", "Unknown"]:
                if not builds[build_type]:
                    continue
                icon = BUILD_ICONS.get(build_type, "❓")
                header = f"**{icon} {build_type}:**"

                # Always try to fit the header
                if current_len + len(header) + 1 > char_budget:
                    overflow += len(builds[build_type])
                    continue

                lines.append(header)
                current_len += len(header) + 1

                shown = 0
                for player in builds[build_type][:max_per_build]:
                    entry = f"• {player}"
                    if current_len + len(entry) + 1 > char_budget:
                        overflow += len(builds[build_type]) - shown
                        break
                    lines.append(entry)
                    current_len += len(entry) + 1
                    shown += 1

                remaining = len(builds[build_type]) - max_per_build
                if remaining > 0:
                    note = f"_... and {remaining} more {build_type}_"
                    if current_len + len(note) + 1 <= FIELD_LIMIT:
                        lines.append(note)
                        current_len += len(note) + 1

                lines.append("")
                current_len += 1

            result = "\n".join(lines) if lines else get_text(self.db, LANGUAGES, guild_id, "no_players", user_id)

            # Final safety: if still over limit (e.g. from summary alone), hard truncate
            if len(result) > FIELD_LIMIT:
                result = result[:FIELD_LIMIT - 20] + "\n_... (truncated)_"

            if overflow > 0:
                notice = f"\n_+{overflow} more players not shown_"
                if len(result) + len(notice) <= FIELD_LIMIT:
                    result += notice

            return result
        
        # Create embed
        embed = discord.Embed(
            title=get_text(self.db, LANGUAGES, guild_id, "war_list_title", user_id),
            color=discord.Color.orange()
        )
        
        if day is None or day.value == "saturday":
            # Calculate Saturday timestamp
            now = datetime.now(pytz.timezone(guild_timezone))
            current_weekday = now.weekday()
            if current_weekday < 5:
                days_to_saturday = 5 - current_weekday
            elif current_weekday == 5:
                days_to_saturday = 0
            else:
                days_to_saturday = 6
            
            saturday_time = get_discord_timestamp(
                config["saturday_war"]["hour"],
                config["saturday_war"]["minute"],
                days_to_saturday,
                guild_timezone
            )
            
            counts, builds = get_player_details_by_build(saturday_players)
            
            if counts:
                sat_header = f"{get_text(self.db, LANGUAGES, guild_id, 'total_saturday', user_id)}: **{len(saturday_players)}**\n\n"
                sat_body = format_player_list(builds, counts, len(saturday_players))
                # Ensure header + body fits in 1024 chars
                if len(sat_header) + len(sat_body) > FIELD_LIMIT:
                    sat_body = sat_body[:FIELD_LIMIT - len(sat_header) - 20] + "\n_... (truncated)_"
                embed.add_field(
                    name=f"📅 {get_text(self.db, LANGUAGES, guild_id, 'saturday', user_id)} - {saturday_time}",
                    value=sat_header + sat_body,
                    inline=False
                )
            else:
                embed.add_field(
                    name=f"📅 {get_text(self.db, LANGUAGES, guild_id, 'saturday', user_id)} - {saturday_time}",
                    value=f"{get_text(self.db, LANGUAGES, guild_id, 'total_saturday', user_id)}: **0**\n\n{get_text(self.db, LANGUAGES, guild_id, 'no_players', user_id)}",
                    inline=False
                )
        
        if day is None or day.value == "sunday":
            # Calculate Sunday timestamp
            now = datetime.now(pytz.timezone(guild_timezone))
            current_weekday = now.weekday()
            if current_weekday < 6:
                days_to_sunday = 6 - current_weekday
            elif current_weekday == 6:
                days_to_sunday = 0
            else:
                days_to_sunday = 7
            
            sunday_time = get_discord_timestamp(
                config["sunday_war"]["hour"],
                config["sunday_war"]["minute"],
                days_to_sunday,
                guild_timezone
            )
            
            counts, builds = get_player_details_by_build(sunday_players)
            
            if counts:
                sun_header = f"{get_text(self.db, LANGUAGES, guild_id, 'total_sunday', user_id)}: **{len(sunday_players)}**\n\n"
                sun_body = format_player_list(builds, counts, len(sunday_players))
                # Ensure header + body fits in 1024 chars
                if len(sun_header) + len(sun_body) > FIELD_LIMIT:
                    sun_body = sun_body[:FIELD_LIMIT - len(sun_header) - 20] + "\n_... (truncated)_"
                embed.add_field(
                    name=f"📅 {get_text(self.db, LANGUAGES, guild_id, 'sunday', user_id)} - {sunday_time}",
                    value=sun_header + sun_body,
                    inline=False
                )
            else:
                embed.add_field(
                    name=f"📅 {get_text(self.db, LANGUAGES, guild_id, 'sunday', user_id)} - {sunday_time}",
                    value=f"{get_text(self.db, LANGUAGES, guild_id, 'total_sunday', user_id)}: **0**\n\n{get_text(self.db, LANGUAGES, guild_id, 'no_players', user_id)}",
                    inline=False
                )
        
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
        """Handle war poll vote with rate-limit retry logic"""
        guild_id = interaction.guild_id
        user_id = interaction.user.id
        
        # Defer immediately with retry in case of 429 right on the defer itself
        for attempt in range(3):
            try:
                await interaction.response.defer(ephemeral=True)
                break
            except discord.HTTPException as e:
                if e.status == 429 and attempt < 2:
                    retry_after = float(getattr(e, 'retry_after', 5))
                    await asyncio.sleep(retry_after)
                else:
                    # Can't defer - interaction probably already expired or hard failure
                    return
        
        # Check if user has a profile first
        player = await self.db.async_run(self.db.get_player, user_id, guild_id)
        if not player:
            await interaction.followup.send(
                get_text(self.db, LANGUAGES, guild_id, "err_no_profile_war", user_id),
                ephemeral=True
            )
            return
        
        # Get current poll week
        from utils.war_helpers import get_current_poll_week
        poll_week = get_current_poll_week()
        
        # Get user's previous vote (if any)
        participants_by_type = await self.db.async_run(self.db.get_war_participants_by_type, guild_id, poll_week)
        previous_choice = None
        for participation_type, player_list in participants_by_type.items():
            for p in player_list:
                if p.get("user_id") == user_id:
                    previous_choice = participation_type
                    break
            if previous_choice:
                break
        
        # Set new participation
        set_war_participation(self.db, guild_id, user_id, choice)
        
        # Build feedback message based on previous and new choice
        if choice == "saturday":
            new_choice_text = get_text(self.db, LANGUAGES, guild_id, "saturday", user_id)
        elif choice == "sunday":
            new_choice_text = get_text(self.db, LANGUAGES, guild_id, "sunday", user_id)
        elif choice == "both":
            new_choice_text = get_text(self.db, LANGUAGES, guild_id, "both_days", user_id)
        else:  # none
            new_choice_text = get_text(self.db, LANGUAGES, guild_id, "not_playing", user_id)
        
        # Format previous choice text
        prev_choice_text = None
        if previous_choice:
            if previous_choice == "saturday":
                prev_choice_text = get_text(self.db, LANGUAGES, guild_id, "saturday", user_id)
            elif previous_choice == "sunday":
                prev_choice_text = get_text(self.db, LANGUAGES, guild_id, "sunday", user_id)
            elif previous_choice == "both":
                prev_choice_text = get_text(self.db, LANGUAGES, guild_id, "both_days", user_id)
            else:  # not_playing
                prev_choice_text = get_text(self.db, LANGUAGES, guild_id, "not_playing", user_id)
        
        # Send confirmation with previous selection if applicable
        if previous_choice and previous_choice != choice:
            # User changed their vote
            if choice == "none":
                message = f"✅ {get_text(self.db, LANGUAGES, guild_id, 'removed_from_war', user_id)}\n\n**{get_text(self.db, LANGUAGES, guild_id, 'previously', user_id)}:** {prev_choice_text}"
            else:
                message = f"✅ {get_text(self.db, LANGUAGES, guild_id, 'vote_updated', user_id)}\n\n**{get_text(self.db, LANGUAGES, guild_id, 'previously', user_id)}:** {prev_choice_text} → **{get_text(self.db, LANGUAGES, guild_id, 'now', user_id)}:** {new_choice_text}"
        elif previous_choice == choice:
            # User clicked the same choice again
            message = f"ℹ️ {get_text(self.db, LANGUAGES, guild_id, 'already_registered', user_id)}: **{new_choice_text}**"
        else:
            # First time voting
            if choice == "saturday":
                message = get_text(self.db, LANGUAGES, guild_id, "registered_saturday", user_id)
            elif choice == "sunday":
                message = get_text(self.db, LANGUAGES, guild_id, "registered_sunday", user_id)
            elif choice == "both":
                message = get_text(self.db, LANGUAGES, guild_id, "registered_both", user_id)
            else:  # none
                message = get_text(self.db, LANGUAGES, guild_id, "registered_not_playing", user_id)
        
        # Send followup with retry on 429
        for attempt in range(3):
            try:
                await interaction.followup.send(message, ephemeral=True)
                break
            except discord.HTTPException as e:
                if e.status == 429 and attempt < 2:
                    retry_after = float(getattr(e, 'retry_after', 5))
                    await asyncio.sleep(retry_after)
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
