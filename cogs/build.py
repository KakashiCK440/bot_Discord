"""
Build commands cog for Discord bot.
Handles build selection, viewing builds, and role creation.
"""

import discord
from discord.ext import commands
from discord import app_commands
from config import BUILDS, BUILD_ICONS, WEAPON_ICONS
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
    
    @app_commands.command(name="postbuilds", description="Post build selection menu (Admin)")
    @app_commands.checks.has_permissions(administrator=True)
    async def postbuilds(self, interaction: discord.Interaction):
        """Post build selection menu (embed in your language)"""
        # Defer immediately to avoid timeout
        await interaction.response.defer(ephemeral=True)
        
        guild_id = interaction.guild_id
        uid = interaction.user.id
        
        embed = discord.Embed(
            title=get_text(self.db, LANGUAGES, guild_id, "postbuilds_title", uid),
            description=(
                f"{get_text(self.db, LANGUAGES, guild_id, 'postbuilds_desc', uid)}\n\n"
                f"{get_text(self.db, LANGUAGES, guild_id, 'postbuilds_includes', uid)}\n"
                f"• {get_text(self.db, LANGUAGES, guild_id, 'postbuilds_ign', uid)}\n"
                f"• {get_text(self.db, LANGUAGES, guild_id, 'postbuilds_level_mp', uid)}\n"
                f"• {get_text(self.db, LANGUAGES, guild_id, 'postbuilds_build_weapons', uid)}\n\n"
                f"{get_text(self.db, LANGUAGES, guild_id, 'postbuilds_available', uid)}\n"
                f"{BUILD_ICONS['DPS']} **DPS** - {get_text(self.db, LANGUAGES, guild_id, 'postbuilds_dps_desc', uid)}\n"
                f"{BUILD_ICONS['Tank']} **Tank** - {get_text(self.db, LANGUAGES, guild_id, 'postbuilds_tank_desc', uid)}\n"
                f"{BUILD_ICONS['Healer']} **Healer** - {get_text(self.db, LANGUAGES, guild_id, 'postbuilds_healer_desc', uid)}"
            ),
            color=discord.Color.gold()
        )
        
        for build_name, build_data in BUILDS.items():
            weapons_with_icons = [
                f"{WEAPON_ICONS.get(w, '⚔️')} {w}"
                for w in build_data["weapons"]
            ]
            embed.add_field(
                name=f"{build_data['emoji']} {build_name} {get_text(self.db, LANGUAGES, guild_id, 'weapons', uid)}",
                value="\n".join(weapons_with_icons) if len(weapons_with_icons) <= 10 else ", ".join([w.split()[-1] for w in weapons_with_icons]),
                inline=False
            )
        
        embed.set_footer(text=get_text(self.db, LANGUAGES, guild_id, "postbuilds_footer", uid))
        
        view = ProfileSetupButton(guild_id, self.db, LANGUAGES)
        
        await interaction.channel.send(
            content="@everyone",
            embed=embed,
            view=view
        )
        
        await interaction.followup.send(
            get_text(self.db, LANGUAGES, guild_id, "postbuilds_posted", uid),
            ephemeral=True
        )
    
    @app_commands.command(name="mybuild", description="View your current build")
    async def mybuild(self, interaction: discord.Interaction):
        """Show user's current build"""
        guild_id = interaction.guild_id
        user_id = interaction.user.id
        
        # Get player from database
        player = self.db.get_player(user_id, guild_id)
        
        if not player:
            await interaction.response.send_message(
                get_text(self.db, LANGUAGES, guild_id, "no_profile", user_id),
                ephemeral=True
            )
            return
        
        weapons = self.db.get_player_weapons(user_id, guild_id)
        build_type = player.get('build_type', 'DPS')
        build_icon = BUILDS.get(build_type, {}).get('emoji', '⚔️')
        weapons_display = "\n".join([
            f"{WEAPON_ICONS.get(w, '⚔️')} {w}" for w in weapons
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
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="resetbuild", description="Reset and change your build")
    async def resetbuild(self, interaction: discord.Interaction):
        """Reset user's build"""
        guild_id = interaction.guild_id
        user_id = interaction.user.id
        
        # Get current build
        player = self.db.get_player(user_id, guild_id)
        
        if not player:
            await interaction.response.send_message(
                "❌ You don't have a build to reset!",
                ephemeral=True
            )
            return
        
        # Remove all build and weapon roles using helper function
        from utils.helpers import remove_all_build_roles
        guild = interaction.guild
        member = interaction.user
        
        success, removed_count = await remove_all_build_roles(member, guild)
        
        # Clear weapons from database
        self.db.set_player_weapons(user_id, guild_id, [])
        
        # Show build selection
        build_view = BuildSelectView(self.db, LANGUAGES)
        
        await interaction.response.send_message(
            get_text(self.db, LANGUAGES, guild_id, "build_reset", user_id) + "\n\n" + get_text(self.db, LANGUAGES, guild_id, "now_select_build", user_id),
            view=build_view,
            ephemeral=True
        )
    
    @app_commands.command(name="createroles", description="Create all build and weapon roles (Admin only)")
    @app_commands.checks.has_permissions(administrator=True)
    async def createroles(self, interaction: discord.Interaction):
        """Create all build and weapon roles"""
        # Defer immediately since this can take time
        await interaction.response.defer(ephemeral=True)
        
        guild = interaction.guild
        created_roles = []
        
        # Create build roles
        for build_name, build_data in BUILDS.items():
            role_name = f"{build_data['emoji']} {build_name}"
            existing_role = discord.utils.get(guild.roles, name=role_name)
            if not existing_role:
                try:
                    role = await guild.create_role(
                        name=role_name,
                        color=discord.Color.orange(),
                        mentionable=True
                    )
                    created_roles.append(role_name)
                except Exception as e:
                    logger.error(f"Failed to create role {role_name}: {e}")
        
        # Create weapon roles
        for weapon_name, weapon_emoji in WEAPON_ICONS.items():
            role_name = f"{weapon_emoji} {weapon_name}"
            existing_role = discord.utils.get(guild.roles, name=role_name)
            if not existing_role:
                try:
                    role = await guild.create_role(
                        name=role_name,
                        color=discord.Color.blue(),
                        mentionable=True
                    )
                    created_roles.append(role_name)
                except Exception as e:
                    logger.error(f"Failed to create role {role_name}: {e}")
        
        if created_roles:
            result = f"✅ Created {len(created_roles)} roles:\n" + "\n".join(f"• {r}" for r in created_roles)
        else:
            result = "ℹ️ All roles already exist!"
        
        await interaction.followup.send(result, ephemeral=True)


async def setup(bot):
    """Setup function to add cog to bot"""
    from database import Database
    db = Database("data/bot_data.db")
    await bot.add_cog(BuildCog(bot, db))
