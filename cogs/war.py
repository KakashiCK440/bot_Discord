"""
War commands cog for Discord bot.
Handles war polls, participant lists, configuration, and reminders.
All war events are stored in the database — fully flexible, any day/time.
"""

import asyncio
import discord
from discord.ext import commands
from discord import app_commands
import pytz
from datetime import datetime, timedelta
from config import get_builds_config, get_weapon_icon
from utils.helpers import get_text, get_discord_timestamp
from utils.war_helpers import (
    get_current_poll_week,
    get_war_config,
    update_war_setting,
    DAY_MAP,
)
from locales import LANGUAGES

import logging
logger = logging.getLogger(__name__)

# ── Helpers ────────────────────────────────────────────────────────────────────

DAYS_OF_WEEK = [
    "Monday", "Tuesday", "Wednesday", "Thursday",
    "Friday", "Saturday", "Sunday"
]


def _days_until(target_weekday: int, from_weekday: int) -> int:
    """Return the number of days from 'from_weekday' until the next 'target_weekday' (0 = today)."""
    delta = (target_weekday - from_weekday) % 7
    return delta


def _event_timestamp(event: dict, guild_timezone: str) -> str:
    """Return a Discord relative timestamp for the next occurrence of a war event."""
    day_name = event["day_of_week"]
    target_wd = DAY_MAP.get(day_name, 5)
    now = datetime.now(pytz.timezone(guild_timezone))
    days_ahead = _days_until(target_wd, now.weekday())
    return get_discord_timestamp(event["war_hour"], event["war_minute"], days_ahead, guild_timezone)


# ══════════════════════════════════════════════════════════════════════════════
# Poll Views
# ══════════════════════════════════════════════════════════════════════════════

class WarPollSingleView(discord.ui.View):
    """Two-button poll for a single war event: ✅ Playing / ❌ Not Playing."""

    def __init__(self, guild_id: int, db, event_name: str):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        self.db = db
        self.event_name = event_name

        safe = event_name.replace(" ", "_")[:40]
        playing_btn = discord.ui.Button(
            label="✅ Playing",
            style=discord.ButtonStyle.success,
            custom_id=f"wev_play_{safe}"
        )
        not_playing_btn = discord.ui.Button(
            label="❌ Not Playing",
            style=discord.ButtonStyle.danger,
            custom_id=f"wev_skip_{safe}"
        )
        playing_btn.callback = self._playing_callback
        not_playing_btn.callback = self._not_playing_callback
        self.add_item(playing_btn)
        self.add_item(not_playing_btn)

    async def _playing_callback(self, interaction: discord.Interaction):
        await self._handle(interaction, playing=True)

    async def _not_playing_callback(self, interaction: discord.Interaction):
        await self._handle(interaction, playing=False)

    async def _handle(self, interaction: discord.Interaction, playing: bool):
        for attempt in range(3):
            try:
                await interaction.response.defer(ephemeral=True)
                break
            except discord.HTTPException as e:
                if e.status == 429 and attempt < 2:
                    await asyncio.sleep(float(getattr(e, "retry_after", 5)))
                else:
                    return

        guild_id = interaction.guild_id
        user_id = interaction.user.id

        def db_work():
            player = self.db.get_player(user_id, guild_id)
            if not player:
                return None, None
            poll_week = get_current_poll_week()
            prev = self.db.get_user_war_vote(guild_id, user_id, self.event_name, poll_week)
            self.db.set_war_vote(guild_id, user_id, self.event_name, poll_week, playing)
            return player, prev

        player, prev = await self.db.async_run(db_work)

        if player is None:
            await interaction.followup.send(
                get_text(self.db, LANGUAGES, guild_id, "err_no_profile_war", user_id),
                ephemeral=True
            )
            return

        event_label = f"**{self.event_name}**"
        if playing:
            if prev is True:
                msg = f"ℹ️ You're already registered as **Playing** for {event_label}."
            else:
                msg = f"✅ Registered as **Playing** for {event_label}!"
        else:
            if prev is False:
                msg = f"ℹ️ You're already registered as **Not Playing** for {event_label}."
            else:
                msg = f"❌ Registered as **Not Playing** for {event_label}."
                if prev is True:
                    msg += f"\n*(Changed from Playing)*"

        for attempt in range(3):
            try:
                await interaction.followup.send(msg, ephemeral=True)
                break
            except discord.HTTPException as e:
                if e.status == 429 and attempt < 2:
                    await asyncio.sleep(float(getattr(e, "retry_after", 5)))
                else:
                    break


class WarPollAllView(discord.ui.View):
    """Dynamic view that adds Playing/Not Playing buttons for every active war event."""

    def __init__(self, guild_id: int, db, events: list):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        self.db = db

        for event in events:
            name = event["name"]
            safe = name.replace(" ", "_")[:30]

            play_btn = discord.ui.Button(
                label=f"✅ {name}",
                style=discord.ButtonStyle.success,
                custom_id=f"weva_play_{safe}",
                row=None  # Discord auto-assigns rows (max 5)
            )
            skip_btn = discord.ui.Button(
                label=f"❌ {name}",
                style=discord.ButtonStyle.danger,
                custom_id=f"weva_skip_{safe}",
            )
            # Bind using closures
            play_btn.callback = self._make_callback(name, playing=True)
            skip_btn.callback = self._make_callback(name, playing=False)
            self.add_item(play_btn)
            self.add_item(skip_btn)

    def _make_callback(self, event_name: str, playing: bool):
        async def callback(interaction: discord.Interaction):
            for attempt in range(3):
                try:
                    await interaction.response.defer(ephemeral=True)
                    break
                except discord.HTTPException as e:
                    if e.status == 429 and attempt < 2:
                        await asyncio.sleep(float(getattr(e, "retry_after", 5)))
                    else:
                        return

            guild_id = interaction.guild_id
            user_id = interaction.user.id

            def db_work():
                player = self.db.get_player(user_id, guild_id)
                if not player:
                    return None, None
                poll_week = get_current_poll_week()
                prev = self.db.get_user_war_vote(guild_id, user_id, event_name, poll_week)
                self.db.set_war_vote(guild_id, user_id, event_name, poll_week, playing)
                return player, prev

            player, prev = await self.db.async_run(db_work)

            if player is None:
                await interaction.followup.send(
                    get_text(self.db, LANGUAGES, guild_id, "err_no_profile_war", user_id),
                    ephemeral=True
                )
                return

            event_label = f"**{event_name}**"
            if playing:
                msg = f"✅ Registered as **Playing** for {event_label}!" if prev is not True else f"ℹ️ Already registered as **Playing** for {event_label}."
            else:
                msg = f"❌ Registered as **Not Playing** for {event_label}."
                if prev is True:
                    msg += " *(Changed from Playing)*"

            for attempt in range(3):
                try:
                    await interaction.followup.send(msg, ephemeral=True)
                    break
                except discord.HTTPException as e:
                    if e.status == 429 and attempt < 2:
                        await asyncio.sleep(float(getattr(e, "retry_after", 5)))
                    else:
                        break

        return callback


# Backward-compatible alias used by bot.py persistent view registration
WarPollView = WarPollAllView


# ══════════════════════════════════════════════════════════════════════════════
# Cog
# ══════════════════════════════════════════════════════════════════════════════

class WarCog(commands.Cog):
    """War-related commands for managing war participation and configuration"""

    def __init__(self, bot, db):
        self.bot = bot
        self.db = db

    # ── /warpoll ──────────────────────────────────────────────────────────────

    @app_commands.command(name="warpoll", description="Post war participation poll (Admin)")
    @app_commands.describe(
        event="War event name, or leave empty to post all active events in one poll"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def warpoll(self, interaction: discord.Interaction, event: str = None):
        """Post war poll for a specific event or all active events"""
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

        guild_tz = config.get("timezone", "Africa/Cairo")
        active_events = self.db.get_war_events(guild_id, active_only=True)

        if not active_events:
            await interaction.followup.send(
                "⚠️ No active war events found. Use `/addwar` to create one.", ephemeral=True
            )
            return

        if event:
            # Single-event poll
            ev = next((e for e in active_events if e["name"].lower() == event.lower()), None)
            if not ev:
                names = ", ".join(e["name"] for e in active_events)
                await interaction.followup.send(
                    f"❌ Event **{event}** not found. Active events: {names}", ephemeral=True
                )
                return

            ts = _event_timestamp(ev, guild_tz)
            embed = discord.Embed(
                title=f"⚔️ War Poll — {ev['name']}",
                description=(
                    f"📅 **Day:** {ev['day_of_week']}\n"
                    f"⏰ **Time:** {ts}\n\n"
                    f"Will you be playing? Press a button below!"
                ),
                color=discord.Color.red()
            )
            embed.set_footer(text="Your vote can be changed at any time.")
            view = WarPollSingleView(guild_id, self.db, ev["name"])
            await channel.send(embed=embed, view=view)

        else:
            # All-events poll
            embed = discord.Embed(
                title=get_text(self.db, LANGUAGES, guild_id, "war_poll_title", uid),
                description=get_text(self.db, LANGUAGES, guild_id, "war_poll_desc", uid),
                color=discord.Color.red()
            )
            for ev in active_events:
                ts = _event_timestamp(ev, guild_tz)
                embed.add_field(
                    name=f"⚔️ {ev['name']}",
                    value=f"📅 {ev['day_of_week']}  ⏰ {ts}",
                    inline=False
                )
            embed.add_field(
                name="ℹ️",
                value=get_text(self.db, LANGUAGES, guild_id, "use_warlist", uid),
                inline=False
            )
            embed.set_footer(text=get_text(self.db, LANGUAGES, guild_id, "times_local", uid))

            if len(active_events) <= 12:  # 2 buttons per event × 12 = 24 (Discord max 25)
                view = WarPollAllView(guild_id, self.db, active_events)
                await channel.send(embed=embed, view=view)
            else:
                await channel.send(embed=embed)
                # Post individual polls for each event
                for ev in active_events:
                    ev_embed = discord.Embed(
                        title=f"⚔️ {ev['name']} — {ev['day_of_week']}",
                        color=discord.Color.red()
                    )
                    ev_view = WarPollSingleView(guild_id, self.db, ev["name"])
                    await channel.send(embed=ev_embed, view=ev_view)

        await interaction.followup.send("✅ War poll posted!", ephemeral=True)

    # ── /warlist ──────────────────────────────────────────────────────────────

    @app_commands.command(name="warlist", description="Show war participant lists")
    @app_commands.describe(event="Filter by event name (optional)")
    async def warlist(self, interaction: discord.Interaction, event: str = None):
        """Show war participants with build info per event"""
        from collections import namedtuple
        _EmbedField = namedtuple("_EmbedField", ["name", "value", "inline"])

        guild_id = interaction.guild_id
        user_id = interaction.user.id
        await interaction.response.defer()

        poll_week = get_current_poll_week()
        config = get_war_config(self.db, guild_id)
        guild_tz = config.get("timezone", "Africa/Cairo")

        all_events = self.db.get_war_events(guild_id, active_only=False)
        if event:
            all_events = [e for e in all_events if e["name"].lower() == event.lower()]

        if not all_events:
            await interaction.followup.send("⚠️ No war events found.", ephemeral=True)
            return

        builds_config = get_builds_config(self.db)
        build_names = list(builds_config.keys())
        FIELD_LIMIT = 1024

        def format_build_fields(build_type_name, players_list):
            if not players_list:
                return []
            icon = builds_config.get(build_type_name, {}).get("emoji", "❓")
            base = f"{icon} {build_type_name} ({len(players_list)})"
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

        embed = discord.Embed(
            title=get_text(self.db, LANGUAGES, guild_id, "war_list_title", user_id),
            color=discord.Color.orange()
        )

        for ev in all_events:
            votes = self.db.get_war_votes(guild_id, ev["name"], poll_week)
            playing_ids = [v["user_id"] for v in votes if v["playing"]]
            total = len(playing_ids)

            # Build breakdown
            build_data = {bn: [] for bn in build_names}
            build_data["Unknown"] = []
            for pid in playing_ids:
                player = self.db.get_player(pid, guild_id)
                weapons = self.db.get_player_weapons(pid, guild_id) or []
                if player:
                    name_str = player.get("in_game_name", f"<@{pid}>")
                    build = player.get("build_type", "Unknown")
                    icons = "".join(get_weapon_icon(self.db, w) for w in weapons[:2])
                    entry = f"{name_str} {icons}".strip()
                else:
                    build = "Unknown"
                    entry = f"<@{pid}>"
                (build_data.get(build) or build_data["Unknown"]).append(entry)

            ts = _event_timestamp(ev, guild_tz)
            status_icon = "✅" if ev["active"] else "⏸️"
            summary = " • ".join(
                f"{builds_config.get(bt, {}).get('emoji', '❓')} **{len(build_data[bt])} {bt}**"
                for bt in build_names if build_data.get(bt)
            )
            embed.add_field(
                name=f"{status_icon} {ev['name']} — {ev['day_of_week']} {ts}",
                value=f"**Playing: {total}**" + (f"\n{summary}" if summary else ""),
                inline=False
            )
            if total:
                for bt in build_names + ["Unknown"]:
                    for f in format_build_fields(bt, build_data.get(bt, [])):
                        embed.add_field(name=f.name, value=f.value, inline=f.inline)
            else:
                embed.add_field(
                    name=get_text(self.db, LANGUAGES, guild_id, "no_players", user_id),
                    value="\u200b", inline=False
                )

        embed.set_footer(text=get_text(self.db, LANGUAGES, guild_id, "footer_builds", user_id))
        await interaction.followup.send(embed=embed)

    # ── War Event Management ──────────────────────────────────────────────────

    @app_commands.command(name="listwars", description="List all war events (Admin)")
    @app_commands.checks.has_permissions(administrator=True)
    async def listwars(self, interaction: discord.Interaction):
        """Show all war events for this server"""
        guild_id = interaction.guild_id
        await interaction.response.defer(ephemeral=True)
        config = get_war_config(self.db, guild_id)
        guild_tz = config.get("timezone", "Africa/Cairo")

        events = self.db.get_war_events(guild_id)
        if not events:
            await interaction.followup.send(
                "⚠️ No war events yet. Use `/addwar` to create one.", ephemeral=True
            )
            return

        embed = discord.Embed(
            title="⚔️ War Events",
            description=f"Timezone: **{guild_tz}**",
            color=discord.Color.orange()
        )
        for ev in events:
            status = "✅ Active" if ev["active"] else "⏸️ Paused"
            ts = _event_timestamp(ev, guild_tz)
            embed.add_field(
                name=f"{'✅' if ev['active'] else '⏸️'} {ev['name']}",
                value=(
                    f"📅 **Day:** {ev['day_of_week']}\n"
                    f"⏰ **Time:** {ev['war_hour']:02d}:{ev['war_minute']:02d} — Next: {ts}\n"
                    f"**Status:** {status}"
                ),
                inline=True
            )
        embed.set_footer(text="Use /addwar /removewar /togglewar to manage")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="addwar", description="Add a new war event (Admin)")
    @app_commands.describe(
        name="Event name (e.g. 'Clan Battle')",
        day="Day of week",
        hour="War start hour (0-23)",
        minute="War start minute (0-59)"
    )
    @app_commands.choices(day=[
        app_commands.Choice(name=d, value=d) for d in DAYS_OF_WEEK
    ])
    @app_commands.checks.has_permissions(administrator=True)
    async def addwar(self, interaction: discord.Interaction,
                     name: str, day: app_commands.Choice[str],
                     hour: int, minute: int):
        """Add a new war event"""
        guild_id = interaction.guild_id
        await interaction.response.defer(ephemeral=True)

        if not (0 <= hour <= 23):
            await interaction.followup.send("❌ Hour must be 0–23.", ephemeral=True)
            return
        if not (0 <= minute <= 59):
            await interaction.followup.send("❌ Minute must be 0–59.", ephemeral=True)
            return

        success = self.db.add_war_event(guild_id, name.strip(), day.value, hour, minute)
        if success:
            config = get_war_config(self.db, guild_id)
            guild_tz = config.get("timezone", "Africa/Cairo")
            ev = {"day_of_week": day.value, "war_hour": hour, "war_minute": minute, "name": name}
            ts = _event_timestamp(ev, guild_tz)
            await interaction.followup.send(
                f"✅ War event **{name}** added!\n"
                f"📅 **{day.value}** at **{hour:02d}:{minute:02d}** — Next: {ts}\n\n"
                f"Use `/warpoll event:{name}` to post its poll.",
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                f"❌ Failed to add **{name}**. It may already exist.", ephemeral=True
            )

    @app_commands.command(name="removewar", description="Remove a war event permanently (Admin)")
    @app_commands.describe(name="Event name to remove")
    @app_commands.checks.has_permissions(administrator=True)
    async def removewar(self, interaction: discord.Interaction, name: str):
        """Remove a war event"""
        guild_id = interaction.guild_id
        await interaction.response.defer(ephemeral=True)
        success = self.db.remove_war_event(guild_id, name.strip())
        if success:
            await interaction.followup.send(f"✅ War event **{name}** removed.", ephemeral=True)
        else:
            await interaction.followup.send(f"❌ Event **{name}** not found.", ephemeral=True)

    @app_commands.command(name="togglewar", description="Enable or disable a war event (Admin)")
    @app_commands.describe(name="Event name to toggle")
    @app_commands.checks.has_permissions(administrator=True)
    async def togglewar(self, interaction: discord.Interaction, name: str):
        """Toggle active/paused state of a war event"""
        guild_id = interaction.guild_id
        await interaction.response.defer(ephemeral=True)
        new_state = self.db.toggle_war_event(guild_id, name.strip())
        if new_state is None:
            await interaction.followup.send(f"❌ Event **{name}** not found.", ephemeral=True)
        else:
            state_str = "✅ Active" if new_state else "⏸️ Paused"
            await interaction.followup.send(
                f"**{name}** is now **{state_str}**.", ephemeral=True
            )

    # ── /setwar ───────────────────────────────────────────────────────────────

    @app_commands.command(name="setwar", description="Configure war settings (Admin)")
    @app_commands.describe(setting="Setting to configure", value="New value")
    @app_commands.choices(setting=[
        app_commands.Choice(name="War Channel",           value="war_channel_id"),
        app_commands.Choice(name="Reminder Hours Before", value="reminder_hours_before"),
        app_commands.Choice(name="Timezone",              value="timezone"),
    ])
    @app_commands.checks.has_permissions(administrator=True)
    async def setwar(self, interaction: discord.Interaction,
                     setting: app_commands.Choice[str], value: str):
        """Configure global war settings"""
        guild_id = interaction.guild_id
        user_id = interaction.user.id
        key = setting.value

        if key == "war_channel_id":
            if value.startswith("<#") and value.endswith(">"):
                channel_id = int(value[2:-1])
            else:
                try:
                    channel_id = int(value)
                except ValueError:
                    await interaction.response.send_message("❌ Invalid channel ID", ephemeral=True)
                    return
            channel = interaction.guild.get_channel(channel_id)
            if not channel:
                await interaction.response.send_message("❌ Channel not found", ephemeral=True)
                return
            update_war_setting(self.db, guild_id, key, channel_id)
            display_value = f"<#{channel_id}>"

        elif key == "reminder_hours_before":
            try:
                hours = int(value)
                if not (0 <= hours <= 48):
                    await interaction.response.send_message("❌ Hours must be 0–48", ephemeral=True)
                    return
                update_war_setting(self.db, guild_id, key, hours)
                display_value = f"{hours} hours"
            except ValueError:
                await interaction.response.send_message("❌ Invalid number", ephemeral=True)
                return

        elif key == "timezone":
            try:
                pytz.timezone(value)
                update_war_setting(self.db, guild_id, key, value)
                display_value = value
            except pytz.exceptions.UnknownTimeZoneError:
                await interaction.response.send_message("❌ Invalid timezone", ephemeral=True)
                return
        else:
            update_war_setting(self.db, guild_id, key, value)
            display_value = value

        await interaction.response.send_message(
            get_text(self.db, LANGUAGES, guild_id, "setting_updated", user_id).format(
                setting=setting.name, value=display_value
            ),
            ephemeral=True
        )

    # ── /warconfig ────────────────────────────────────────────────────────────

    @app_commands.command(name="warconfig", description="View current war configuration")
    async def warconfig(self, interaction: discord.Interaction):
        """View war configuration and all events"""
        guild_id = interaction.guild_id
        await interaction.response.defer(ephemeral=True)
        config = get_war_config(self.db, guild_id)
        guild_tz = config.get("timezone", "Africa/Cairo")

        embed = discord.Embed(title="⚙️ War Configuration", color=discord.Color.blue())
        channel_id = config.get("war_channel_id")
        embed.add_field(
            name="📢 War Channel",
            value=f"<#{channel_id}>" if channel_id else "Not set",
            inline=False
        )
        embed.add_field(
            name="⏰ Reminder", value=f"{config.get('reminder_hours', 2)}h before war", inline=True
        )
        embed.add_field(name="🌍 Timezone", value=guild_tz, inline=True)

        events = self.db.get_war_events(guild_id)
        if events:
            embed.add_field(name="\u200b", value="**📋 War Events**", inline=False)
            for ev in events:
                status = "✅" if ev["active"] else "⏸️"
                embed.add_field(
                    name=f"{status} {ev['name']}",
                    value=f"{ev['day_of_week']} {ev['war_hour']:02d}:{ev['war_minute']:02d}",
                    inline=True
                )
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ── /warschedule ──────────────────────────────────────────────────────────

    @app_commands.command(name="warschedule", description="View full war & poll schedule (Admin)")
    @app_commands.checks.has_permissions(administrator=True)
    async def warschedule(self, interaction: discord.Interaction):
        """Show a full overview of all war-related schedule settings"""
        guild_id = interaction.guild_id
        await interaction.response.defer(ephemeral=True)
        config = await self.db.async_run(get_war_config, self.db, guild_id)
        tz = config.get("timezone", "Africa/Cairo")

        channel_id = config.get("war_channel_id")
        channel_str = f"<#{channel_id}>" if channel_id else "❌ Not set — use `/setwar War Channel`"
        poll_day = config.get("poll_day", "Friday")
        poll_h  = config["poll_time"]["hour"]
        poll_m  = config["poll_time"]["minute"]
        reminder = config.get("reminder_hours", 2)

        embed = discord.Embed(
            title="📅 Full War & Poll Schedule",
            description=f"All times in **{tz}**. Manage events with `/addwar` `/removewar` `/togglewar`.",
            color=discord.Color.blurple()
        )
        embed.add_field(name="📢 War Channel", value=channel_str, inline=False)
        embed.add_field(name="🗳️ Poll Posted", value=f"Every **{poll_day}** at **{poll_h:02d}:{poll_m:02d}**", inline=False)
        embed.add_field(name="🔔 Reminder", value=f"**{reminder}h** before each war", inline=False)

        events = self.db.get_war_events(guild_id)
        if events:
            embed.add_field(name="\u200b", value="**⚔️ War Events**", inline=False)
            for ev in events:
                ts = _event_timestamp(ev, tz)
                status = "✅" if ev["active"] else "⏸️"
                embed.add_field(
                    name=f"{status} {ev['name']}",
                    value=f"📅 {ev['day_of_week']}  ⏰ {ev['war_hour']:02d}:{ev['war_minute']:02d} — Next: {ts}",
                    inline=False
                )
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ── /setpollschedule ──────────────────────────────────────────────────────

    @app_commands.command(name="setpollschedule", description="Set the day and time for automatic war poll (Admin)")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        day="Day the poll is posted each week",
        hour="Hour to post (0-23)",
        minute="Minute to post (0-59)"
    )
    @app_commands.choices(day=[
        app_commands.Choice(name=d, value=d) for d in DAYS_OF_WEEK
    ])
    async def setpollschedule(self, interaction: discord.Interaction,
                               day: app_commands.Choice[str] = None,
                               hour: int = None, minute: int = None):
        """Set or view the automatic war poll schedule"""
        guild_id = interaction.guild_id
        uid = interaction.user.id
        await interaction.response.defer(ephemeral=True)

        if day is None and hour is None and minute is None:
            config = await self.db.async_run(get_war_config, self.db, guild_id)
            current_day  = config.get("poll_day", "Friday")
            current_hour = config["poll_time"]["hour"]
            current_min  = config["poll_time"]["minute"]
            tz = config.get("timezone", "Africa/Cairo")
            embed = discord.Embed(
                title="📅 War Poll Schedule",
                description=(
                    f"**Day:** {current_day}\n"
                    f"**Time:** {current_hour:02d}:{current_min:02d} ({tz})\n\n"
                    f"Use `/setpollschedule day hour minute` to change."
                ),
                color=discord.Color.blue()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        if hour is not None and not (0 <= hour <= 23):
            await interaction.followup.send("❌ Hour must be 0–23.", ephemeral=True)
            return
        if minute is not None and not (0 <= minute <= 59):
            await interaction.followup.send("❌ Minute must be 0–59.", ephemeral=True)
            return

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
        new_day  = config.get("poll_day", "Friday")
        new_h    = config["poll_time"]["hour"]
        new_m    = config["poll_time"]["minute"]
        tz       = config.get("timezone", "Africa/Cairo")

        embed = discord.Embed(
            title="✅ Poll Schedule Updated",
            description="\n".join(changes),
            color=discord.Color.green()
        )
        embed.add_field(
            name="📋 New Schedule",
            value=f"Every **{new_day}** at **{new_h:02d}:{new_m:02d}** ({tz})",
            inline=False
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ── /testreminder ─────────────────────────────────────────────────────────

    @app_commands.command(name="testreminder", description="Test war reminder for an event (Admin)")
    @app_commands.describe(name="War event name (leave empty to test first active event)")
    @app_commands.checks.has_permissions(administrator=True)
    async def testreminder(self, interaction: discord.Interaction, name: str = None):
        """Test war reminder"""
        guild_id = interaction.guild_id
        user_id = interaction.user.id
        await interaction.response.defer(ephemeral=True)

        config = get_war_config(self.db, guild_id)
        channel_id = config.get("war_channel_id")
        if not channel_id:
            await interaction.followup.send(
                get_text(self.db, LANGUAGES, guild_id, "err_war_channel_not_set", user_id),
                ephemeral=True
            )
            return

        channel = interaction.guild.get_channel(channel_id)
        if not channel:
            await interaction.followup.send(
                get_text(self.db, LANGUAGES, guild_id, "err_war_channel_not_found", user_id),
                ephemeral=True
            )
            return

        events = self.db.get_war_events(guild_id, active_only=True)
        if not events:
            await interaction.followup.send("⚠️ No active war events.", ephemeral=True)
            return

        if name:
            ev = next((e for e in events if e["name"].lower() == name.lower()), None)
            if not ev:
                await interaction.followup.send(f"❌ Event **{name}** not found.", ephemeral=True)
                return
        else:
            ev = events[0]

        poll_week = get_current_poll_week()
        votes = self.db.get_war_votes(guild_id, ev["name"], poll_week)
        playing_ids = [v["user_id"] for v in votes if v["playing"]]

        mentions = " ".join(f"<@{uid}>" for uid in playing_ids) if playing_ids else "@everyone (test)"

        embed = discord.Embed(
            title=f"⚔️ {ev['name']} War Reminder (TEST)",
            description=(
                f"📅 **{ev['day_of_week']}** at **{ev['war_hour']:02d}:{ev['war_minute']:02d}**\n\n"
                f"Get ready for war!"
            ),
            color=discord.Color.red()
        )
        embed.add_field(name="🗓️ Players", value=f"{len(playing_ids)} signed up", inline=True)
        embed.set_footer(text="⚠️ This is a TEST reminder")

        await channel.send(content=f"🔔 {mentions}", embed=embed)
        await interaction.followup.send(
            f"✅ Test reminder for **{ev['name']}** sent to {channel.mention}.", ephemeral=True
        )

    # ── /resetwar ─────────────────────────────────────────────────────────────

    @app_commands.command(name="resetwar", description="Reset current week's war data (Admin)")
    @app_commands.describe(confirm="Type 'confirm' to reset")
    @app_commands.checks.has_permissions(administrator=True)
    async def resetwar(self, interaction: discord.Interaction, confirm: str):
        """Reset current week's war data"""
        guild_id = interaction.guild_id
        if confirm.lower() != "confirm":
            await interaction.response.send_message("❌ Type 'confirm' to reset.", ephemeral=True)
            return

        poll_week = get_current_poll_week()
        events = self.db.get_war_events(guild_id)
        for ev in events:
            self.db.clear_war_event_votes(guild_id, ev["name"], poll_week)
        # Also clear old war_participants for backward compat
        self.db.clear_war_participants(guild_id, poll_week)

        await interaction.response.send_message(
            f"✅ War data for week **{poll_week}** has been reset!", ephemeral=True
        )

    @app_commands.command(name="resetallwar", description="Reset ALL war data (Admin)")
    @app_commands.describe(confirm="Type 'CONFIRM ALL'")
    @app_commands.checks.has_permissions(administrator=True)
    async def resetallwar(self, interaction: discord.Interaction, confirm: str):
        """Reset ALL war data"""
        guild_id = interaction.guild_id
        if confirm != "CONFIRM ALL":
            await interaction.response.send_message("❌ Type 'CONFIRM ALL' exactly.", ephemeral=True)
            return
        self.db.clear_all_war_participants(guild_id)
        await interaction.response.send_message("✅ ALL war data has been reset!", ephemeral=True)


async def setup(bot):
    """Setup function to add cog to bot"""
    from database import Database
    db = Database("data/bot_data.db")
    await bot.add_cog(WarCog(bot, db))
