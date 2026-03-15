"""
Build commands cog for Discord bot.
Handles build selection, viewing builds, and role creation.
All build/weapon data is read live from the database.
"""

import discord
from discord.ext import commands
from discord import app_commands
from config import get_builds_config, get_weapon_icon
from utils.helpers import get_text
from locales import LANGUAGES
from views.build_views import BuildSelectView
from views.profile_views import ProfileSetupButton
import logging

logger = logging.getLogger(__name__)


class BuildCog(commands.Cog):
    """Build-related commands for managing player builds and weapons"""

    def __init__(self, bot, db):
        self.bot = bot
        self.db = db

    # ──────────────────────────────────────────────────────────────
    # Public commands
    # ──────────────────────────────────────────────────────────────

    @app_commands.command(name="postbuilds", description="Post build selection menu (Admin)")
    @app_commands.checks.has_permissions(administrator=True)
    async def postbuilds(self, interaction: discord.Interaction):
        """Post build selection menu (embed in your language)"""
        await interaction.response.defer(ephemeral=True)

        guild_id = interaction.guild_id
        uid = interaction.user.id
        builds = get_builds_config(self.db)

        embed = discord.Embed(
            title=get_text(self.db, LANGUAGES, guild_id, "postbuilds_title", uid),
            description=(
                f"{get_text(self.db, LANGUAGES, guild_id, 'postbuilds_desc', uid)}\n\n"
                f"{get_text(self.db, LANGUAGES, guild_id, 'postbuilds_includes', uid)}\n"
                f"• {get_text(self.db, LANGUAGES, guild_id, 'postbuilds_ign', uid)}\n"
                f"• {get_text(self.db, LANGUAGES, guild_id, 'postbuilds_level_mp', uid)}\n"
                f"• {get_text(self.db, LANGUAGES, guild_id, 'postbuilds_build_weapons', uid)}\n\n"
                f"{get_text(self.db, LANGUAGES, guild_id, 'postbuilds_available', uid)}\n"
                + "\n".join(
                    f"{b['emoji']} **{n}** - {b.get('description', '')}"
                    for n, b in builds.items()
                )
            ),
            color=discord.Color.gold()
        )

        for build_name, build_data in builds.items():
            weapons_rows = self.db.get_weapons(build_name)
            weapons_with_icons = [
                f"{get_weapon_icon(self.db, w['name'])} {w['name']}" for w in weapons_rows
            ]
            embed.add_field(
                name=f"{build_data['emoji']} {build_name} {get_text(self.db, LANGUAGES, guild_id, 'weapons', uid)}",
                value="\n".join(weapons_with_icons) or "—",
                inline=False
            )

        embed.set_footer(text=get_text(self.db, LANGUAGES, guild_id, "postbuilds_footer", uid))
        view = ProfileSetupButton(guild_id, self.db, LANGUAGES)

        await interaction.channel.send(content="@everyone", embed=embed, view=view)
        await interaction.followup.send(
            get_text(self.db, LANGUAGES, guild_id, "postbuilds_posted", uid),
            ephemeral=True
        )

    @app_commands.command(name="mybuild", description="View your current build")
    async def mybuild(self, interaction: discord.Interaction):
        """Show user's current build"""
        guild_id = interaction.guild_id
        user_id = interaction.user.id
        await interaction.response.defer(ephemeral=True)

        player = self.db.get_player(user_id, guild_id)
        if not player:
            await interaction.followup.send(
                get_text(self.db, LANGUAGES, guild_id, "no_profile", user_id), ephemeral=True
            )
            return

        weapons = self.db.get_player_weapons(user_id, guild_id)
        build_type = player.get('build_type', 'DPS')
        builds = get_builds_config(self.db)
        build_icon = builds.get(build_type, {}).get('emoji', '⚔️')
        weapons_display = "\n".join([
            f"{get_weapon_icon(self.db, w)} {w}" for w in weapons
        ]) if weapons else get_text(self.db, LANGUAGES, guild_id, "no_weapons", user_id)

        embed = discord.Embed(
            title=f"{build_icon} Your Build",
            description=f"**{get_text(self.db, LANGUAGES, guild_id, 'build_type', user_id)}:** {build_type}\n\n**{get_text(self.db, LANGUAGES, guild_id, 'weapons', user_id)}:**\n{weapons_display}",
            color=discord.Color.green()
        )
        if player.get('in_game_name'):
            embed.add_field(
                name=f"📝 {get_text(self.db, LANGUAGES, guild_id, 'in_game_name', user_id)}",
                value=(
                    f"**{get_text(self.db, LANGUAGES, guild_id, 'label_name', user_id)}:** {player['in_game_name']}\n"
                    f"**{get_text(self.db, LANGUAGES, guild_id, 'level', user_id)}:** {player['level']}\n"
                    f"**{get_text(self.db, LANGUAGES, guild_id, 'mastery_points', user_id)}:** {player['mastery_points']:,}"
                ),
                inline=False
            )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="resetbuild", description="Reset and change your build")
    async def resetbuild(self, interaction: discord.Interaction):
        """Reset user's build"""
        guild_id = interaction.guild_id
        user_id = interaction.user.id
        await interaction.response.defer(ephemeral=True)

        player = self.db.get_player(user_id, guild_id)
        if not player:
            await interaction.followup.send("❌ You don't have a build to reset!", ephemeral=True)
            return

        from utils.helpers import remove_all_build_roles
        guild = interaction.guild
        member = interaction.user
        await remove_all_build_roles(member, guild, self.db)
        self.db.set_player_weapons(user_id, guild_id, [])

        build_view = BuildSelectView(self.db, LANGUAGES)
        await interaction.followup.send(
            get_text(self.db, LANGUAGES, guild_id, "build_reset", user_id)
            + "\n\n"
            + get_text(self.db, LANGUAGES, guild_id, "now_select_build", user_id),
            view=build_view,
            ephemeral=True
        )

    @app_commands.command(name="createroles", description="Create all build and weapon roles from DB (Admin)")
    @app_commands.checks.has_permissions(administrator=True)
    async def createroles(self, interaction: discord.Interaction):
        """Create all build and weapon roles from database"""
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        created_roles = []

        builds = get_builds_config(self.db)
        for build_name, build_data in builds.items():
            emoji = build_data.get("emoji", "")
            for role_name in [build_name, f"{emoji} {build_name}".strip()]:
                if not discord.utils.get(guild.roles, name=role_name):
                    try:
                        await guild.create_role(name=role_name, color=discord.Color.orange(), mentionable=True)
                        created_roles.append(role_name)
                        break  # only create one variant
                    except Exception as e:
                        logger.error(f"Failed to create role {role_name}: {e}")

        all_weapons = self.db.get_all_weapons()
        for w in all_weapons:
            w_name = w["name"]
            w_emoji = w.get("emoji", "")
            for role_name in [w_name, f"{w_emoji} {w_name}".strip()]:
                if not discord.utils.get(guild.roles, name=role_name):
                    try:
                        await guild.create_role(name=role_name, color=discord.Color.blue(), mentionable=True)
                        created_roles.append(role_name)
                        break
                    except Exception as e:
                        logger.error(f"Failed to create role {role_name}: {e}")

        result = (
            f"✅ Created **{len(created_roles)}** roles:\n" + "\n".join(f"• {r}" for r in created_roles)
            if created_roles else "ℹ️ All roles already exist!"
        )
        await interaction.followup.send(result, ephemeral=True)

    # ──────────────────────────────────────────────────────────────
    # Admin: Manage builds & weapons
    # ──────────────────────────────────────────────────────────────

    @app_commands.command(name="listbuilds", description="List all builds and their weapons (from DB)")
    @app_commands.checks.has_permissions(administrator=True)
    async def listbuilds(self, interaction: discord.Interaction):
        """Display the full live build & weapon catalogue from the database."""
        await interaction.response.defer(ephemeral=True)
        builds = get_builds_config(self.db)
        if not builds:
            await interaction.followup.send("⚠️ No builds in the database. Use `/addbuild` to add one.", ephemeral=True)
            return

        embed = discord.Embed(title="📋 Build Catalogue (from Database)", color=discord.Color.blurple())
        for build_name, build_data in builds.items():
            weapons_rows = self.db.get_weapons(build_name)
            weapon_lines = [f"{w['emoji']} {w['name']}" for w in weapons_rows] or ["—"]
            embed.add_field(
                name=f"{build_data['emoji']} {build_name} — {build_data.get('description', '')}",
                value="\n".join(weapon_lines),
                inline=False
            )
        embed.set_footer(text="Use /addbuild /addweapon /removebuild /removeweapon to manage")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="addbuild", description="Add a new build type to the database (Admin)")
    @app_commands.describe(
        name="Build name (e.g. 'Support')",
        emoji="Build emoji (custom <:name:id> or unicode ⚡)",
        description="Short description shown in the dropdown"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def addbuild(self, interaction: discord.Interaction, name: str, emoji: str, description: str = ""):
        """Add a new build type"""
        await interaction.response.defer(ephemeral=True)
        success = self.db.add_build(name.strip(), emoji.strip(), description.strip())
        if success:
            await interaction.followup.send(
                f"✅ Build **{emoji} {name}** added to the database.\n"
                f"Players will see it in `/setupprofile` immediately. "
                f"Run `/createroles` to create its Discord role.",
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                f"❌ Failed to add build **{name}**. It may already exist.", ephemeral=True
            )

    @app_commands.command(name="removebuild", description="Remove a build type from the database (Admin)")
    @app_commands.describe(name="Build name to remove")
    @app_commands.checks.has_permissions(administrator=True)
    async def removebuild(self, interaction: discord.Interaction, name: str):
        """Remove a build type (also removes its weapons via CASCADE)"""
        await interaction.response.defer(ephemeral=True)
        success = self.db.remove_build(name.strip())
        if success:
            await interaction.followup.send(
                f"✅ Build **{name}** and all its weapons have been removed from the database.", ephemeral=True
            )
        else:
            await interaction.followup.send(
                f"❌ Build **{name}** not found in the database.", ephemeral=True
            )

    @app_commands.command(name="addweapon", description="Add a new weapon to a build in the database (Admin)")
    @app_commands.describe(
        name="Weapon name (e.g. 'Fire Staff')",
        emoji="Weapon emoji (custom <:name:id> or unicode 🔥)",
        build="Build this weapon belongs to (e.g. 'Support')"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def addweapon(self, interaction: discord.Interaction, name: str, emoji: str, build: str):
        """Add a new weapon to a build"""
        await interaction.response.defer(ephemeral=True)
        # Verify build exists
        builds = get_builds_config(self.db)
        if build.strip() not in builds:
            build_list = ", ".join(builds.keys()) or "none"
            await interaction.followup.send(
                f"❌ Build **{build}** not found. Available builds: {build_list}", ephemeral=True
            )
            return
        success = self.db.add_weapon(name.strip(), emoji.strip(), build.strip())
        if success:
            await interaction.followup.send(
                f"✅ Weapon **{emoji} {name}** added to **{build}**.\n"
                f"Players will see it in the weapon selection immediately. "
                f"Run `/createroles` to create its Discord role.",
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                f"❌ Failed to add weapon **{name}**. It may already exist.", ephemeral=True
            )

    @app_commands.command(name="removeweapon", description="Remove a weapon from the database (Admin)")
    @app_commands.describe(name="Weapon name to remove")
    @app_commands.checks.has_permissions(administrator=True)
    async def removeweapon(self, interaction: discord.Interaction, name: str):
        """Remove a weapon"""
        await interaction.response.defer(ephemeral=True)
        success = self.db.remove_weapon(name.strip())
        if success:
            await interaction.followup.send(
                f"✅ Weapon **{name}** removed from the database.", ephemeral=True
            )
        else:
            await interaction.followup.send(
                f"❌ Weapon **{name}** not found in the database.", ephemeral=True
            )


async def setup(bot):
    """Setup function to add cog to bot"""
    from database import Database
    db = Database("data/bot_data.db")
    await bot.add_cog(BuildCog(bot, db))
