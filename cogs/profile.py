"""
Profile commands cog for Discord bot.
Handles player profile creation, viewing, updating, and management.
"""

import discord
from discord.ext import commands
from discord import app_commands
from config import BUILDS, BUILD_ICONS, WEAPON_ICONS
from utils.helpers import get_text, update_member_nickname
from locales import LANGUAGES
from views.profile_views import LanguageSelectView


class ProfileCog(commands.Cog):
    """Profile-related commands for managing player profiles"""
    
    def __init__(self, bot, db):
        self.bot = bot
        self.db = db
    
    @app_commands.command(name="setupprofile", description="Set up your complete profile (guided)")
    async def setupprofile(self, interaction: discord.Interaction):
        """Start guided profile setup (always shows language choice first)"""
        guild_id = interaction.guild_id
        user_id = interaction.user.id
        
        # Check if user already has a COMPLETE profile (with weapons set)
        # This allows users from approved join requests to complete their setup
        existing_player = self.db.get_player(user_id, guild_id)
        if existing_player:
            # Check if they have weapons - if they do, profile is complete
            weapons = self.db.get_player_weapons(user_id, guild_id)
            if weapons and len(weapons) > 0:
                await interaction.response.send_message(
                    "✅ You already have a complete profile! Use `/profile` to view it or `/resetbuild` to change your build.",
                    ephemeral=True
                )
                return
            # If they have a profile but no weapons, let them continue (join request users)
        
        prompt = get_text(self.db, LANGUAGES, guild_id, "choose_language_prompt", user_id)
        await interaction.response.send_message(
            f"**{get_text(self.db, LANGUAGES, guild_id, 'choose_language', user_id)}**\n\n{prompt}",
            view=LanguageSelectView(guild_id, self.db, LANGUAGES),
            ephemeral=True
        )
    
    @app_commands.command(name="setprofile", description="Quick profile update")
    @app_commands.describe(
        in_game_name="Your character name in the game",
        mastery_points="Your total mastery/power points",
        level="Your character level (1-100)"
    )
    async def setprofile(
        self,
        interaction: discord.Interaction,
        in_game_name: str,
        mastery_points: int,
        level: int
    ):
        """Set or update player profile"""
        guild_id = interaction.guild_id
        user_id = interaction.user.id
        
        if level < 1 or level > 100:
            await interaction.response.send_message(
                get_text(self.db, LANGUAGES, guild_id, "err_level_range", user_id),
                ephemeral=True
            )
            return
        
        if mastery_points < 0:
            await interaction.response.send_message(
                get_text(self.db, LANGUAGES, guild_id, "err_mastery_positive", user_id),
                ephemeral=True
            )
            return
        
        player = self.db.get_player(user_id, guild_id)
        build_type = player.get('build_type', 'DPS') if player else 'DPS'
        
        self.db.create_or_update_player(
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
        all_players = self.db.get_all_players(guild_id)
        sorted_players = sorted(all_players, key=lambda p: p['mastery_points'], reverse=True)
        rank = next((i+1 for i, p in enumerate(sorted_players) if p['user_id'] == user_id), 0)
        
        embed = discord.Embed(
            title=get_text(self.db, LANGUAGES, guild_id, "profile_updated", user_id),
            description=(
                f"**{get_text(self.db, LANGUAGES, guild_id, 'in_game_name', user_id)}:** {in_game_name}\n"
                f"**{get_text(self.db, LANGUAGES, guild_id, 'level', user_id)}:** {level}\n"
                f"**{get_text(self.db, LANGUAGES, guild_id, 'mastery_points', user_id)}:** {mastery_points:,}\n"
                f"**{get_text(self.db, LANGUAGES, guild_id, 'rank', user_id)}:** #{rank}"
            ),
            color=discord.Color.green()
        )
        
        if player:
            weapons = self.db.get_player_weapons(user_id, guild_id)
            if weapons:
                weapons_display = "\n".join([
                    f"{WEAPON_ICONS.get(w, '⚔️')} {w}" for w in weapons
                ])
                embed.add_field(
                    name=f"{BUILDS[build_type]['emoji']} {get_text(self.db, LANGUAGES, guild_id, 'build_type', user_id)}",
                    value=f"**{build_type}**\n{weapons_display}",
                    inline=False
                )
        
        if nickname_success:
            embed.set_footer(text=f"✅ {nickname_msg}")
        else:
            embed.set_footer(text=nickname_msg)
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="profile", description="View player profile")
    @app_commands.describe(user="The user to view (optional, defaults to yourself)")
    async def profile(self, interaction: discord.Interaction, user: discord.User = None):
        """View player profile (in your language)"""
        guild_id = interaction.guild_id
        viewer_id = interaction.user.id
        target_user = user or interaction.user
        target_id = target_user.id
        
        player = self.db.get_player(target_id, guild_id)
        
        if not player:
            await interaction.response.send_message(
                get_text(self.db, LANGUAGES, guild_id, "no_profile", viewer_id),
                ephemeral=True
            )
            return
        
        # Calculate rank
        all_players = self.db.get_all_players(guild_id)
        sorted_players = sorted(all_players, key=lambda p: p['mastery_points'], reverse=True)
        rank = next((i+1 for i, p in enumerate(sorted_players) if p['user_id'] == target_id), 0)
        
        build_type = player.get('build_type', 'Not set')
        build_icon = BUILDS.get(build_type, {}).get('emoji', '⚔️')
        
        embed = discord.Embed(
            title=f"{get_text(self.db, LANGUAGES, guild_id, 'profile_title', viewer_id)}",
            color=discord.Color.blue()
        )
        
        embed.set_author(name=target_user.display_name, icon_url=target_user.display_avatar.url)
        
        embed.add_field(
            name=f"📝 {get_text(self.db, LANGUAGES, guild_id, 'in_game_name', viewer_id)}",
            value=player.get('in_game_name', get_text(self.db, LANGUAGES, guild_id, 'not_set', viewer_id)),
            inline=True
        )
        
        embed.add_field(
            name=f"⭐ {get_text(self.db, LANGUAGES, guild_id, 'level', viewer_id)}",
            value=str(player.get('level', 1)),
            inline=True
        )
        
        embed.add_field(
            name=f"⚡ {get_text(self.db, LANGUAGES, guild_id, 'mastery_points', viewer_id)}",
            value=f"{player.get('mastery_points', 0):,}",
            inline=True
        )
        
        embed.add_field(
            name=f"🏆 {get_text(self.db, LANGUAGES, guild_id, 'rank', viewer_id)}",
            value=f"#{rank}",
            inline=True
        )
        
        # Build and weapons
        weapons = self.db.get_player_weapons(target_id, guild_id)
        weapons_display = "\n".join([
            f"{WEAPON_ICONS.get(w, '⚔️')} {w}" for w in weapons
        ]) if weapons else get_text(self.db, LANGUAGES, guild_id, "no_weapons", viewer_id)
        
        embed.add_field(
            name=f"{build_icon} {get_text(self.db, LANGUAGES, guild_id, 'build_type', viewer_id)}",
            value=f"**{build_type}**",
            inline=False
        )
        
        embed.add_field(
            name=f"⚔️ {get_text(self.db, LANGUAGES, guild_id, 'weapons', viewer_id)}",
            value=weapons_display,
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="updatestats", description="Update your mastery points or level")
    @app_commands.describe(
        mastery_points="Your new mastery points (optional)",
        level="Your new level (optional, 1-100)"
    )
    async def updatestats(
        self,
        interaction: discord.Interaction,
        mastery_points: int = None,
        level: int = None
    ):
        """Update player stats"""
        guild_id = interaction.guild_id
        user_id = interaction.user.id
        
        player = self.db.get_player(user_id, guild_id)
        
        if not player:
            await interaction.response.send_message(
                get_text(self.db, LANGUAGES, guild_id, "no_profile", user_id),
                ephemeral=True
            )
            return
        
        if level is not None and (level < 1 or level > 100):
            await interaction.response.send_message(
                get_text(self.db, LANGUAGES, guild_id, "err_level_range", user_id),
                ephemeral=True
            )
            return
        
        if mastery_points is not None and mastery_points < 0:
            await interaction.response.send_message(
                get_text(self.db, LANGUAGES, guild_id, "err_mastery_positive", user_id),
                ephemeral=True
            )
            return
        
        new_mastery = mastery_points if mastery_points is not None else player['mastery_points']
        new_level = level if level is not None else player['level']
        
        self.db.create_or_update_player(
            user_id, guild_id,
            player['in_game_name'],
            new_mastery,
            new_level,
            player['build_type']
        )
        
        # Calculate new rank
        all_players = self.db.get_all_players(guild_id)
        sorted_players = sorted(all_players, key=lambda p: p['mastery_points'], reverse=True)
        rank = next((i+1 for i, p in enumerate(sorted_players) if p['user_id'] == user_id), 0)
        
        embed = discord.Embed(
            title=get_text(self.db, LANGUAGES, guild_id, "stats_updated", user_id),
            description=(
                f"**{get_text(self.db, LANGUAGES, guild_id, 'level', user_id)}:** {new_level}\n"
                f"**{get_text(self.db, LANGUAGES, guild_id, 'mastery_points', user_id)}:** {new_mastery:,}\n"
                f"**{get_text(self.db, LANGUAGES, guild_id, 'rank', user_id)}:** #{rank}"
            ),
            color=discord.Color.green()
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="changename", description="Change your in-game name and server nickname")
    @app_commands.describe(new_name="Your new in-game name")
    async def changename(self, interaction: discord.Interaction, new_name: str):
        """Change player's in-game name"""
        guild_id = interaction.guild_id
        user_id = interaction.user.id
        
        player = self.db.get_player(user_id, guild_id)
        
        if not player:
            await interaction.response.send_message(
                get_text(self.db, LANGUAGES, guild_id, "no_profile", user_id),
                ephemeral=True
            )
            return
        
        self.db.create_or_update_player(
            user_id, guild_id,
            new_name,
            player['mastery_points'],
            player['level'],
            player['build_type']
        )
        
        # Update Discord nickname
        member = interaction.user
        nickname_success, nickname_msg = await update_member_nickname(member, new_name)
        
        embed = discord.Embed(
            title=get_text(self.db, LANGUAGES, guild_id, "name_changed", user_id),
            description=f"**{get_text(self.db, LANGUAGES, guild_id, 'in_game_name', user_id)}:** {new_name}",
            color=discord.Color.green()
        )
        
        if nickname_success:
            embed.set_footer(text=f"✅ {nickname_msg}")
        else:
            embed.set_footer(text=nickname_msg)
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="mylanguage", description="Set or view your preferred language (English/Arabic)")
    @app_commands.describe(language="Language to set (optional)")
    @app_commands.choices(language=[
        app_commands.Choice(name="English", value="en"),
        app_commands.Choice(name="العربية (Arabic)", value="ar")
    ])
    async def mylanguage(self, interaction: discord.Interaction, language: app_commands.Choice[str] = None):
        """Set or view user's language preference"""
        guild_id = interaction.guild_id
        user_id = interaction.user.id
        
        if language:
            # Set language
            self.db.set_user_language(user_id, guild_id, language.value)
            await interaction.response.send_message(
                get_text(self.db, LANGUAGES, guild_id, "mylanguage_set", user_id).format(lang=language.name),
                ephemeral=True
            )
        else:
            # View current language
            current_lang = self.db.get_user_language(user_id, guild_id)
            lang_name = "English" if current_lang == "en" else "العربية (Arabic)"
            
            embed = discord.Embed(
                title=get_text(self.db, LANGUAGES, guild_id, "mylanguage_title", user_id),
                description=get_text(self.db, LANGUAGES, guild_id, "mylanguage_current", user_id).format(lang=lang_name),
                color=discord.Color.blue()
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="deleteprofile", description="Delete a player's profile (Admin)")
    @app_commands.describe(user="The user whose profile to delete")
    @app_commands.checks.has_permissions(administrator=True)
    async def deleteprofile(self, interaction: discord.Interaction, user: discord.User):
        """Delete a player's profile completely (admin only)"""
        guild_id = interaction.guild_id
        viewer_id = interaction.user.id
        target_id = user.id
        
        player = self.db.get_player(target_id, guild_id)
        
        if not player:
            await interaction.response.send_message(
                get_text(self.db, LANGUAGES, guild_id, "deleteprofile_no_profile", viewer_id),
                ephemeral=True
            )
            return
        
        # Get player name for confirmation message
        player_name = player.get('in_game_name', user.display_name)
        
        # Remove all build and weapon roles from the user
        from utils.helpers import remove_all_build_roles
        guild = interaction.guild
        member = guild.get_member(target_id)
        
        removed_roles_count = 0
        if member:
            success, removed_roles_count = await remove_all_build_roles(member, guild)
        
        # Delete the player profile
        deleted = self.db.delete_player(target_id, guild_id)
        
        if deleted:
            await interaction.response.send_message(
                f"✅ {get_text(self.db, LANGUAGES, guild_id, 'profile_deleted', viewer_id).format(name=player_name)}\n\n"
                f"**Roles removed:** {removed_roles_count}",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "❌ Failed to delete profile.",
                ephemeral=True
            )
    
    @app_commands.command(name="leaderboard", description="View server leaderboard")
    @app_commands.describe(
        type="Sort by mastery or level",
        limit="Number of players to show (default: 10)"
    )
    @app_commands.choices(type=[
        app_commands.Choice(name="Mastery Points", value="mastery"),
        app_commands.Choice(name="Level", value="level")
    ])
    async def leaderboard(
        self,
        interaction: discord.Interaction,
        type: app_commands.Choice[str] = None,
        limit: int = 10
    ):
        """View server leaderboard"""
        guild_id = interaction.guild_id
        user_id = interaction.user.id
        
        sort_by = type.value if type else "mastery"
        limit = max(1, min(limit, 25))  # Clamp between 1 and 25
        
        all_players = self.db.get_all_players(guild_id)
        
        if not all_players:
            await interaction.response.send_message(
                get_text(self.db, LANGUAGES, guild_id, "no_players_leaderboard", user_id),
                ephemeral=True
            )
            return
        
        # Sort players
        if sort_by == "level":
            sorted_players = sorted(all_players, key=lambda p: (p['level'], p['mastery_points']), reverse=True)
            title = f"🏆 Leaderboard - Top {limit} by Level"
        else:
            sorted_players = sorted(all_players, key=lambda p: p['mastery_points'], reverse=True)
            title = f"🏆 Leaderboard - Top {limit} by Mastery"
        
        # Build leaderboard
        leaderboard_text = []
        for i, player in enumerate(sorted_players[:limit], 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            name = player.get('in_game_name', 'Unknown')
            level = player.get('level', 1)
            mastery = player.get('mastery_points', 0)
            
            leaderboard_text.append(
                f"{medal} **{name}** - Lvl {level} | {mastery:,} MP"
            )
        
        embed = discord.Embed(
            title=title,
            description="\n".join(leaderboard_text),
            color=discord.Color.gold()
        )
        
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    """Setup function to add cog to bot"""
    from database import Database
    db = Database("data/bot_data.db")
    await bot.add_cog(ProfileCog(bot, db))
