"""
Admin commands cog for Discord bot.
Handles help, language settings, and command syncing.
"""

import discord
from discord.ext import commands
from discord import app_commands
from utils.helpers import get_text
from locales import LANGUAGES


class AdminCog(commands.Cog):
    """Administrative commands for bot management"""
    
    def __init__(self, bot, db):
        self.bot = bot
        self.db = db
    
    @app_commands.command(name="help", description="Show all available commands")
    async def help_command(self, interaction: discord.Interaction):
        """Display help message in your language"""
        guild_id = interaction.guild_id
        user_id = interaction.user.id
        
        embed = discord.Embed(
            title=get_text(self.db, LANGUAGES, guild_id, "help_title", user_id),
            description=get_text(self.db, LANGUAGES, guild_id, "help_desc", user_id),
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name=get_text(self.db, LANGUAGES, guild_id, "build_commands", user_id),
            value=get_text(self.db, LANGUAGES, guild_id, "build_commands_desc", user_id),
            inline=False
        )
        
        embed.add_field(
            name=get_text(self.db, LANGUAGES, guild_id, "war_commands", user_id),
            value=get_text(self.db, LANGUAGES, guild_id, "war_commands_desc", user_id),
            inline=False
        )
        
        embed.add_field(
            name=get_text(self.db, LANGUAGES, guild_id, "profile_commands", user_id),
            value=get_text(self.db, LANGUAGES, guild_id, "profile_commands_desc", user_id),
            inline=False
        )
        
        embed.add_field(
            name=get_text(self.db, LANGUAGES, guild_id, "system_commands", user_id),
            value=get_text(self.db, LANGUAGES, guild_id, "system_commands_desc", user_id),
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(
        name="setlanguage",
        description="Set default server language only (Admin). Does not change members' personal language."
    )
    @app_commands.describe(language="Language to set (en or ar)")
    @app_commands.choices(language=[
        app_commands.Choice(name="English", value="en"),
        app_commands.Choice(name="العربية (Arabic)", value="ar")
    ])
    @app_commands.checks.has_permissions(administrator=True)
    async def setlanguage(self, interaction: discord.Interaction, language: app_commands.Choice[str]):
        """Set server language (admin only)"""
        guild_id = interaction.guild_id
        user_id = interaction.user.id
        lang_code = language.value
        
        self.db.update_server_setting(guild_id, 'language', lang_code)
        
        await interaction.response.send_message(
            get_text(self.db, LANGUAGES, guild_id, "language_set", user_id).format(language=language.name),
            ephemeral=True
        )
    
    @app_commands.command(name="synccommands", description="Force sync slash commands (Admin)")
    @app_commands.checks.has_permissions(administrator=True)
    async def synccommands(self, interaction: discord.Interaction):
        """Force sync slash commands — guild sync is instant, global sync propagates over time"""
        guild_id = interaction.guild_id
        user_id = interaction.user.id
        
        await interaction.response.defer(ephemeral=True)
        
        # Guild sync: copies global commands to this guild immediately (instant)
        self.bot.tree.copy_global_to(guild=interaction.guild)
        guild_synced = await self.bot.tree.sync(guild=interaction.guild)
        
        # Global sync: registers commands globally (takes up to 1 hour to propagate)
        global_synced = await self.bot.tree.sync()
        
        await interaction.followup.send(
            f"✅ Synced **{len(guild_synced)}** commands to this server instantly.\n"
            f"🌐 Synced **{len(global_synced)}** global commands (may take up to 1 hour to appear everywhere).",
            ephemeral=True
        )

    @app_commands.command(name="clearalldata", description="⚠️ DELETE ALL player data from this server (Admin)")
    @app_commands.checks.has_permissions(administrator=True)
    async def clearalldata(self, interaction: discord.Interaction):
        """Clear all player data from the database for this server"""
        guild_id = interaction.guild_id
        
        # Confirmation view
        class ConfirmView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=30)
                self.value = None
            
            @discord.ui.button(label="✅ Yes, Delete Everything", style=discord.ButtonStyle.danger)
            async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
                self.value = True
                self.stop()
                await interaction.response.defer()
            
            @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary)
            async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
                self.value = False
                self.stop()
                await interaction.response.defer()
        
        view = ConfirmView()
        await interaction.response.send_message(
            "⚠️ **WARNING: This will permanently delete ALL player data for this server!**\n\n"
            "This includes:\n"
            "• All player profiles\n"
            "• All weapons\n"
            "• All war participation records\n"
            "• All language preferences\n"
            "• All join requests\n\n"
            "**This action cannot be undone!**\n\n"
            "Are you sure you want to continue?",
            view=view,
            ephemeral=True
        )
        
        await view.wait()
        
        if view.value is None:
            await interaction.followup.send("❌ Timed out. No data was deleted.", ephemeral=True)
            return
        
        if not view.value:
            await interaction.followup.send("✅ Cancelled. No data was deleted.", ephemeral=True)
            return
        
        # Delete all data and remove roles
        try:
            # First, remove all build/weapon roles from all members
            guild = interaction.guild
            removed_roles_count = 0
            members_affected = 0
            
            # Get all players to know who to remove roles from
            players = []
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT user_id FROM players WHERE guild_id = %s", (guild_id,))
                players = [row[0] for row in cursor.fetchall()]
            
            # Remove roles from each player
            from utils.helpers import remove_all_build_roles
            for user_id in players:
                member = guild.get_member(user_id)
                if member:
                    success, count = await remove_all_build_roles(member, guild)
                    if success and count > 0:
                        removed_roles_count += count
                        members_affected += 1
            
            # Now delete database records
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                # Delete all related data
                cursor.execute("DELETE FROM player_weapons WHERE guild_id = %s", (guild_id,))
                weapons_count = cursor.rowcount
                
                cursor.execute("DELETE FROM war_participants WHERE guild_id = %s", (guild_id,))
                war_count = cursor.rowcount
                
                cursor.execute("DELETE FROM user_language WHERE guild_id = %s", (guild_id,))
                lang_count = cursor.rowcount
                
                cursor.execute("DELETE FROM join_requests WHERE guild_id = %s", (guild_id,))
                join_count = cursor.rowcount
                
                cursor.execute("DELETE FROM players WHERE guild_id = %s", (guild_id,))
                player_count = cursor.rowcount
            
            await interaction.followup.send(
                f"✅ **All data deleted successfully!**\n\n"
                f"• Players: {player_count}\n"
                f"• Weapons: {weapons_count}\n"
                f"• War records: {war_count}\n"
                f"• Language prefs: {lang_count}\n"
                f"• Join requests: {join_count}\n"
                f"• Roles removed: {removed_roles_count} (from {members_affected} members)",
                ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(f"❌ Error deleting data: {e}", ephemeral=True)


async def setup(bot):
    """Setup function to add cog to bot"""
    from database import Database
    db = Database("data/bot_data.db")
    await bot.add_cog(AdminCog(bot, db))
