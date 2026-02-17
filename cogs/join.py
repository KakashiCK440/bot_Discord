"""
Join request admin commands.
Handles setup of join channels, power requirements, and viewing requests.
"""

import discord
from discord import app_commands
from discord.ext import commands
from database import Database
from locales import LANGUAGES
from utils.helpers import get_text
from views.join_views import JoinRequestButton
import logging

logger = logging.getLogger(__name__)


class JoinCog(commands.Cog):
    """Commands for managing guild join requests"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = Database("data/bot_data.db")
    
    @app_commands.command(name="setupjoin", description="Configure join request system (Admin)")
    @app_commands.describe(
        join_channel="Channel where join request button will be posted",
        admin_review_channel="Channel where admins review join requests",
        build_setup_channel="Channel where users set up their profile (optional)"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def setupjoin(
        self, 
        interaction: discord.Interaction, 
        join_channel: discord.TextChannel,
        admin_review_channel: discord.TextChannel,
        build_setup_channel: discord.TextChannel = None
    ):
        """Set up join request channels"""
        try:
            guild_id = interaction.guild_id
            
            # Store settings
            self.db.update_join_settings(
                guild_id,
                join_channel.id,
                admin_review_channel.id,
                build_setup_channel.id if build_setup_channel else join_channel.id  # Default to join channel
            )
            
            # Create welcome embed
            embed = discord.Embed(
                title="🎮 Welcome to Our Guild!",
                description="Click the button below to request to join our guild.",
                color=discord.Color.blue()
            )
            
            embed.add_field(
                name="Requirements:",
                value=(
                    "• Meet minimum power requirement\n"
                    "• Provide accurate information\n"
                    "• Be active and respectful"
                ),
                inline=False
            )
            
            embed.add_field(
                name="---",
                value=(
                    "مرحباً بك في نقابتنا!\n\n"
                    "اضغط على الزر أدناه لطلب الانضمام إلى نقابتنا.\n\n"
                    "**المتطلبات:**\n"
                    "• تحقيق الحد الأدنى من القوة المطلوبة\n"
                    "• تقديم معلومات دقيقة\n"
                    "• كن نشطاً ومحترماً"
                ),
                inline=False
            )
            
            embed.set_footer(text="Click the button below to get started!")
            
            # Send embed with button to join channel
            # from views.join_views import JoinRequestButton # This import is already at the top
            view = JoinRequestButton(self.db, LANGUAGES)
            welcome_msg = await join_channel.send(embed=embed, view=view)
            
            # Save welcome message ID
            self.db.set_welcome_message_id(guild_id, welcome_msg.id)
            
            # Confirm to admin
            build_channel_mention = build_setup_channel.mention if build_setup_channel else join_channel.mention
            await interaction.response.send_message(
                f"✅ Join system configured!\n\n"
                f"• Join requests: {join_channel.mention}\n"
                f"• Admin review: {admin_review_channel.mention}\n"
                f"• Build setup: {build_channel_mention}\n\n"
                f"Don't forget to set the minimum power requirement with `/setjoinrequirement`!",
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"Error in setupjoin: {e}", exc_info=True)
            await interaction.response.send_message(
                "❌ An error occurred. Please try again.",
                ephemeral=True
            )
    
    @app_commands.command(name="setjoinrequirement", description="Set minimum power requirement")
    @app_commands.describe(power="Minimum power required to join")
    @app_commands.checks.has_permissions(administrator=True)
    async def setjoinrequirement(self, interaction: discord.Interaction, power: int):
        """Set minimum power requirement for join requests"""
        try:
            guild_id = interaction.guild_id
            
            if power < 0:
                await interaction.response.send_message(
                    "❌ Power requirement must be a positive number.",
                    ephemeral=True
                )
                return
            
            success = self.db.set_min_power_requirement(guild_id, power)
            
            if success:
                await interaction.response.send_message(
                    f"✅ Minimum power requirement set to **{power:,}**",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "❌ Failed to update power requirement. Please try again.",
                    ephemeral=True
                )
                
        except Exception as e:
            logger.error(f"Error in setjoinrequirement: {e}", exc_info=True)
            await interaction.response.send_message(
                "❌ An error occurred. Please try again.",
                ephemeral=True
            )
    
    @app_commands.command(name="joinrequests", description="View pending join requests")
    @app_commands.checks.has_permissions(administrator=True)
    async def joinrequests(self, interaction: discord.Interaction):
        """View all pending join requests"""
        try:
            guild_id = interaction.guild_id
            
            requests = self.db.get_pending_join_requests(guild_id)
            
            if not requests:
                await interaction.response.send_message(
                    "📋 No pending join requests.",
                    ephemeral=True
                )
                return
            
            embed = discord.Embed(
                title="📋 Pending Join Requests",
                color=discord.Color.blue()
            )
            
            for req in requests[:10]:  # Show max 10
                user = self.bot.get_user(req["user_id"])
                user_mention = user.mention if user else f"<@{req['user_id']}>"
                
                embed.add_field(
                    name=f"{req['in_game_name']} ({req['language'].upper()})",
                    value=(
                        f"**User:** {user_mention}\n"
                        f"**Level:** {req['level']}\n"
                        f"**Power:** {req['power']:,}\n"
                        f"**Requested:** <t:{int(req['requested_at'].timestamp())}:R>"
                    ),
                    inline=False
                )
            
            if len(requests) > 10:
                embed.set_footer(text=f"Showing 10 of {len(requests)} requests")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error in joinrequests: {e}", exc_info=True)
            await interaction.response.send_message(
                "❌ An error occurred. Please try again.",
                ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(JoinCog(bot))
