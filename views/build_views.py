"""
Build selection views for Discord bot.
Handles build type selection and weapon selection UI components.
All builds and weapons are read live from the database.
"""

import discord
import logging
from config import get_builds_config, get_weapon_icon
from utils.helpers import get_text, update_member_nickname

logger = logging.getLogger(__name__)


class BuildSelectView(discord.ui.View):
    """View with dropdown to select build type (built dynamically from DB)."""

    def __init__(self, db, LANGUAGES, guild_id=None):
        super().__init__(timeout=None)
        self.db = db
        self.LANGUAGES = LANGUAGES
        self.stored_guild_id = guild_id

        # Build options dynamically from DB
        builds = get_builds_config(db)
        options = []
        for build_name, build_data in builds.items():
            emoji_str = build_data.get("emoji", "⚔️")
            description = build_data.get("description", f"{build_name} build")[:100]
            # Parse custom emoji if it's in <:name:id> format
            partial = _parse_emoji(emoji_str)
            options.append(
                discord.SelectOption(
                    label=build_name,
                    description=description,
                    emoji=partial,
                    value=build_name
                )
            )

        select = discord.ui.Select(
            placeholder="Select your build type...",
            custom_id="build_select",
            min_values=1,
            max_values=1,
            options=options or [discord.SelectOption(label="No builds configured", value="none")]
        )
        select.callback = self.build_select_callback
        self.add_item(select)

    async def build_select_callback(self, interaction: discord.Interaction, select: discord.ui.Select = None):
        """Handle build selection"""
        try:
            await interaction.response.defer(ephemeral=True)

            # select might be passed explicitly or found from data
            build_name = interaction.data["values"][0]
            if build_name == "none":
                await interaction.followup.send("❌ No builds are configured yet. Ask an admin to run `/addbuild`.", ephemeral=True)
                return

            user_id = interaction.user.id
            guild_id = interaction.guild_id or self.stored_guild_id

            if not guild_id:
                await interaction.followup.send("❌ Could not determine server. Please try again.", ephemeral=True)
                return

            guild = interaction.guild or interaction.client.get_guild(guild_id)
            if not guild:
                await interaction.followup.send("❌ Could not find server. Please contact an admin.", ephemeral=True)
                return

            # Update database
            player = self.db.get_player(user_id, guild_id)
            if player:
                success = self.db.create_or_update_player(
                    user_id, guild_id,
                    player['in_game_name'],
                    player['mastery_points'],
                    player['level'],
                    build_name
                )
                if not success:
                    await interaction.followup.send("❌ Failed to update build. Please try again later.", ephemeral=True)
                    return
            else:
                await interaction.followup.send("❌ Please set up your profile first using `/setupprofile`.", ephemeral=True)
                return

            # Assign role
            member = guild.get_member(user_id)
            if not member:
                await interaction.followup.send("❌ Could not find you in the server.", ephemeral=True)
                return

            # Remove old build/weapon roles
            from utils.helpers import remove_all_build_roles
            await remove_all_build_roles(member, guild, self.db)

            # Add new build role (try both "BuildName" and "emoji BuildName" formats)
            builds = get_builds_config(self.db)
            build_emoji = builds.get(build_name, {}).get("emoji", "")
            role = (
                discord.utils.get(guild.roles, name=build_name)
                or discord.utils.get(guild.roles, name=f"{build_emoji} {build_name}")
            )
            if role:
                try:
                    await member.add_roles(role)
                except discord.Forbidden:
                    pass

            # Clear previous weapons from database
            self.db.set_player_weapons(user_id, guild_id, [])

            # Disable the dropdown
            for item in self.children:
                item.disabled = True
            try:
                await interaction.edit_original_response(
                    content=f"✅ Build selected: **{build_emoji} {build_name}**",
                    view=self
                )
            except Exception:
                pass

            # Show weapon selection
            weapon_view = WeaponSelectView(build_name, guild_id, user_id, self.db, self.LANGUAGES)
            await interaction.followup.send(
                get_text(self.db, self.LANGUAGES, guild_id, 'now_select_weapons', user_id),
                view=weapon_view,
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error in build selection: {e}", exc_info=True)
            try:
                if interaction.response.is_done():
                    await interaction.followup.send("❌ An error occurred while selecting your build. Please try again later.", ephemeral=True)
                else:
                    await interaction.response.send_message("❌ An error occurred while selecting your build. Please try again later.", ephemeral=True)
            except Exception:
                pass


class WeaponSelectView(discord.ui.View):
    """View with dropdown to select weapons (max 2). Reads weapons from DB."""

    def __init__(self, build_type: str, guild_id: int, user_id: int = None, db=None, LANGUAGES=None):
        super().__init__(timeout=180)
        self.build_type = build_type
        self.guild_id = guild_id
        self.user_id = user_id
        self.db = db
        self.LANGUAGES = LANGUAGES

        # Load weapons from DB
        weapons_rows = db.get_weapons(build_type) if db else []
        options = []
        for w in weapons_rows[:25]:
            name = w["name"]
            icon = w.get("emoji") or get_weapon_icon(db, name)
            options.append(
                discord.SelectOption(label=name, emoji=_parse_emoji(icon), value=name)
            )

        if not options:
            options = [discord.SelectOption(label="No weapons configured", value="none")]

        select = discord.ui.Select(
            placeholder=get_text(db, LANGUAGES, guild_id, "select_weapons", user_id),
            min_values=1,
            max_values=min(2, len(options)),
            options=options,
            custom_id=f"weapon_select_{build_type}"
        )
        select.callback = self.weapon_select_callback
        self.add_item(select)

    async def weapon_select_callback(self, interaction: discord.Interaction):
        """Handle weapon selection"""
        try:
            await interaction.response.defer(ephemeral=True)

            weapons = interaction.data['values']
            if "none" in weapons:
                await interaction.followup.send("❌ No weapons are configured yet. Ask an admin to run `/addweapon`.", ephemeral=True)
                return

            user_id = interaction.user.id
            guild_id = self.guild_id

            guild = interaction.guild or interaction.client.get_guild(guild_id)
            if not guild:
                await interaction.followup.send("❌ Could not find server. Please contact an admin.", ephemeral=True)
                return

            member = guild.get_member(user_id)
            if not member:
                await interaction.followup.send("❌ Could not find you in the server.", ephemeral=True)
                return

            # Get current weapons before updating
            old_weapons = self.db.get_player_weapons(user_id, guild_id)

            # Save weapons to database
            success = self.db.set_player_weapons(user_id, guild_id, weapons)
            if not success:
                await interaction.followup.send("❌ Failed to save weapons. Please try again later.", ephemeral=True)
                return

            player = self.db.get_player(user_id, guild_id)

            # Load all known build names from DB for role removal
            from utils.helpers import remove_all_build_roles
            await remove_all_build_roles(member, guild, self.db)

            # Re-add current build role
            builds = get_builds_config(self.db)
            build_emoji = builds.get(self.build_type, {}).get("emoji", "")
            build_role = (
                discord.utils.get(guild.roles, name=self.build_type)
                or discord.utils.get(guild.roles, name=f"{build_emoji} {self.build_type}")
            )
            if build_role:
                try:
                    await member.add_roles(build_role)
                except discord.Forbidden:
                    pass

            # Add new weapon roles
            for weapon in weapons:
                w_row = self.db.get_weapon_by_name(weapon) or {}
                w_emoji = w_row.get("emoji", "")
                weapon_role = (
                    discord.utils.get(guild.roles, name=weapon)
                    or discord.utils.get(guild.roles, name=f"{w_emoji} {weapon}")
                )
                if weapon_role:
                    try:
                        await member.add_roles(weapon_role)
                    except discord.Forbidden:
                        pass

            # Update nickname
            if player and player.get('in_game_name'):
                try:
                    await update_member_nickname(member, player['in_game_name'])
                except Exception:
                    pass

            # Disable dropdown
            for item in self.children:
                item.disabled = True

            # Build weapons display
            weapons_display = "\n".join([
                f"{get_weapon_icon(self.db, w)} {w}" for w in weapons
            ])

            try:
                await interaction.edit_original_response(
                    content=f"✅ Weapons selected:\n{weapons_display}",
                    view=self
                )
            except Exception:
                pass

            await interaction.followup.send(
                f"🎉 **Profile setup complete!**\n\n"
                f"Your build: **{build_emoji} {self.build_type}**\n"
                f"Your weapons:\n{weapons_display}",
                ephemeral=True
            )

        except Exception as e:
            logger.error(f"Error in weapon selection: {e}", exc_info=True)
            try:
                await interaction.followup.send("❌ An error occurred. Please try again.", ephemeral=True)
            except Exception:
                pass


# ── Utility ──────────────────────────────────────────────────────────────────

def _parse_emoji(emoji_str: str):
    """
    Convert a '<:name:id>' string to a PartialEmoji,
    or return the string as-is for unicode emoji fallback.
    Returns None if empty.
    """
    if not emoji_str:
        return None
    if emoji_str.startswith("<:") and emoji_str.endswith(">"):
        # <:name:id>
        inner = emoji_str[2:-1]
        parts = inner.split(":")
        if len(parts) == 2:
            try:
                return discord.PartialEmoji(name=parts[0], id=int(parts[1]))
            except (ValueError, IndexError):
                pass
    if emoji_str.startswith("<a:") and emoji_str.endswith(">"):
        # <a:name:id> animated
        inner = emoji_str[3:-1]
        parts = inner.split(":")
        if len(parts) == 2:
            try:
                return discord.PartialEmoji(name=parts[0], id=int(parts[1]), animated=True)
            except (ValueError, IndexError):
                pass
    # Return as plain unicode emoji string (discord.py accepts str for unicode emoji)
    return emoji_str if emoji_str else None
