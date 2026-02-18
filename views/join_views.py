"""
Join request views and modals for guild join system.
Handles language selection, join request modal, and admin approval buttons.
"""

import discord
from discord import ui
from database import Database
from config import BUILDS, BUILD_ICONS
from utils.helpers import get_text
import logging

logger = logging.getLogger(__name__)


class JoinRequestButton(ui.View):
    """Persistent button for requesting to join the guild"""
    
    def __init__(self, db: Database, LANGUAGES: dict):
        super().__init__(timeout=None)
        self.db = db
        self.LANGUAGES = LANGUAGES
        
        # Add button with custom_id for persistence
        btn = ui.Button(
            label="طلب الانضمام للنقابة",  # "Request to Join Guild" in Arabic
            style=discord.ButtonStyle.primary,
            emoji="🎮",
            custom_id="join_request_button"
        )
        btn.callback = self._request_callback
        self.add_item(btn)
    
    async def _request_callback(self, interaction: discord.Interaction):
        """Handle join request button click"""
        try:
            guild_id = interaction.guild_id
            user_id = interaction.user.id
            
            # Send modal FIRST to avoid timeout (must respond within 3 seconds)
            modal = JoinRequestModal(guild_id, user_id, "ar", self.db, self.LANGUAGES)  # Default to Arabic
            await interaction.response.send_modal(modal)
            
        except Exception as e:
            logger.error(f"Error in join request button: {e}", exc_info=True)
            try:
                await interaction.response.send_message(
                    "❌ حدث خطأ. يرجى المحاولة مرة أخرى لاحقاً.",  # "An error occurred. Please try again later."
                    ephemeral=True
                )
            except:
                pass


class LanguageSelectView(ui.View):
    """Language selection for join requests"""
    
    def __init__(self, guild_id: int, user_id: int, db: Database, LANGUAGES: dict):
        super().__init__(timeout=60)
        self.guild_id = guild_id
        self.user_id = user_id
        self.db = db
        self.LANGUAGES = LANGUAGES
        
        # Add language dropdown
        self.add_item(JoinLanguageDropdown(guild_id, user_id, db, LANGUAGES))


class JoinLanguageDropdown(ui.Select):
    """Dropdown for language selection in join requests"""
    def __init__(self, guild_id: int, user_id: int, db: Database, LANGUAGES: dict):
        self.guild_id = guild_id
        self.user_id = user_id
        self.db = db
        self.LANGUAGES = LANGUAGES
        
        options = [
            discord.SelectOption(
                label="English",
                value="en",
                emoji="🇬🇧",
                description="Select English language"
            ),
            discord.SelectOption(
                label="العربية",
                value="ar",
                emoji="🇸🇦",
                description="اختر اللغة العربية"
            )
        ]
        
        super().__init__(
            placeholder="Choose your language / اختر لغتك",
            min_values=1,
            max_values=1,
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        """Show the join request modal in selected language"""
        try:
            language = self.values[0]
            
            # Set user language preference
            self.db.set_user_language(self.user_id, self.guild_id, language)
            
            # Send modal first
            modal = JoinRequestModal(self.guild_id, self.user_id, language, self.db, self.LANGUAGES)
            await interaction.response.send_modal(modal)
            
            # After modal is sent, disable dropdown and edit message
            import asyncio
            
            async def update_message():
                # Small delay to ensure modal is sent
                await asyncio.sleep(0.5)
                
                # Disable dropdown after selection
                self.disabled = True
                
                # Edit message to show selection
                lang_name = "English" if language == "en" else "العربية"
                try:
                    await interaction.message.edit(
                        content=f"✅ Language selected: **{lang_name}**\n\n_Please fill out the join request form that just appeared._",
                        view=self.view
                    )
                except Exception as e:
                    logger.error(f"Failed to edit join language message: {e}")
            
            # Run the update in background
            asyncio.create_task(update_message())
        except Exception as e:
            logger.error(f"Error showing join modal: {e}", exc_info=True)
            try:
                await interaction.response.send_message(
                    "❌ An error occurred. Please try again later.",
                    ephemeral=True
                )
            except:
                pass


class JoinRequestModal(ui.Modal):
    """Modal for collecting join request information"""
    
    def __init__(self, guild_id: int, user_id: int, language: str, db: Database, LANGUAGES: dict):
        self.guild_id = guild_id
        self.user_id = user_id
        self.language = language
        self.db = db
        self.LANGUAGES = LANGUAGES
        
        # Use hardcoded bilingual text to avoid database queries during init
        super().__init__(title="Join Request | طلب الانضمام")
        
        # Add input fields
        self.name_input = ui.TextInput(
            label="In-Game Name | الاسم في اللعبة",
            placeholder="Your in-game name" if language == "en" else "اسمك في اللعبة",
            required=True,
            max_length=50
        )
        self.add_item(self.name_input)
        
        self.level_input = ui.TextInput(
            label="Level | المستوى",
            placeholder="e.g., 60" if language == "en" else "مثال: 60",
            required=True,
            max_length=3
        )
        self.add_item(self.level_input)
        
        self.power_input = ui.TextInput(
            label="Power | القوة",
            placeholder="e.g., 50000" if language == "en" else "مثال: 50000",
            required=True,
            max_length=10
        )
        self.add_item(self.power_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle modal submission"""
        try:
            # Parse inputs
            in_game_name = self.name_input.value.strip()
            
            try:
                level = int(self.level_input.value.strip())
                power = int(self.power_input.value.strip())
            except ValueError:
                error_msg = get_text(self.db, self.LANGUAGES, self.guild_id, "join_invalid_numbers", self.user_id)
                await interaction.response.send_message(error_msg, ephemeral=True)
                return
            
            # Get join settings
            settings = self.db.get_join_settings(self.guild_id)
            if not settings:
                error_msg = get_text(self.db, self.LANGUAGES, self.guild_id, "join_not_setup", self.user_id)
                await interaction.response.send_message(error_msg, ephemeral=True)
                return
            
            min_power = settings["min_power_requirement"]
            admin_channel_id = settings["approval_channel_id"]
            
            # Check power requirement
            if power < min_power:
                # Auto-reject
                request_id = self.db.create_join_request(
                    self.user_id, self.guild_id, self.language,
                    in_game_name, level, power
                )
                if request_id:
                    self.db.update_join_request_status(
                        request_id, "auto_rejected", None
                    )
                
                reject_msg = get_text(self.db, self.LANGUAGES, self.guild_id, "join_rejected_power", self.user_id)
                reject_msg = reject_msg.format(min_power=min_power)
                await interaction.response.send_message(reject_msg, ephemeral=True)
                return
            
            # Power meets requirement - send to admin review
            guild = interaction.guild
            admin_channel = guild.get_channel(admin_channel_id)
            
            if not admin_channel:
                error_msg = get_text(self.db, self.LANGUAGES, self.guild_id, "join_channel_error", self.user_id)
                await interaction.response.send_message(error_msg, ephemeral=True)
                return
            
            # Create admin review embed
            embed = discord.Embed(
                title="🎮 New Join Request",
                color=discord.Color.green(),
                description=f"**User:** <@{self.user_id}>\n**Language:** {self.language.upper()}"
            )
            embed.add_field(name="In-Game Name", value=in_game_name, inline=True)
            embed.add_field(name="Level", value=str(level), inline=True)
            embed.add_field(name="Power", value=f"{power:,}", inline=True)
            embed.add_field(name="Requirement", value=f"✅ {min_power:,} (MEETS)", inline=False)
            embed.set_footer(text=f"User ID: {self.user_id}")
            
            # Send to admin channel with approval buttons
            view = AdminApprovalView(self.user_id, self.guild_id, self.language, self.db, self.LANGUAGES)
            admin_message = await admin_channel.send(embed=embed, view=view)
            
            # Create join request in database
            request_id = self.db.create_join_request(
                self.user_id, self.guild_id, self.language,
                in_game_name, level, power, admin_message.id
            )
            
            # Store request_id in view for later use
            view.request_id = request_id
            
            # Confirm to user
            success_msg = get_text(self.db, self.LANGUAGES, self.guild_id, "join_submitted", self.user_id)
            await interaction.response.send_message(success_msg, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error in join request submission: {e}", exc_info=True)
            try:
                await interaction.response.send_message(
                    "❌ An error occurred. Please try again later.",
                    ephemeral=True
                )
            except:
                pass


class AdminApprovalView(ui.View):
    """Admin buttons for approving/rejecting join requests"""
    
    def __init__(self, user_id: int, guild_id: int, language: str, db: Database, LANGUAGES: dict):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.guild_id = guild_id
        self.language = language
        self.db = db
        self.LANGUAGES = LANGUAGES
        self.request_id = None  # Will be set after creation
    
    @ui.button(label="✅ Approve", style=discord.ButtonStyle.success, custom_id="approve_join")
    async def approve_button(self, interaction: discord.Interaction, button: ui.Button):
        """Handle approval"""
        try:
            # Update join request status and create profile
            if self.request_id:
                self.db.update_join_request_status(self.request_id, "approved", interaction.user.id)
                
                # Get request data to create profile
                with self.db.get_connection() as conn:
                    from psycopg2.extras import RealDictCursor
                    cursor = conn.cursor(cursor_factory=RealDictCursor)
                    cursor.execute("""
                        SELECT in_game_name, level, power 
                        FROM join_requests 
                        WHERE id = %s
                    """, (self.request_id,))
                    request_data = cursor.fetchone()
                
                
                if request_data:
                    # Create basic profile with join request data
                    
                    success = self.db.create_or_update_player(
                        self.user_id,
                        self.guild_id,
                        request_data['in_game_name'],
                        request_data['power'],  # Use power as mastery_points
                        request_data['level'],
                        "DPS"  # Default build, user will change it
                    )
                    
                    # Assign 'AK | Member' role to the user
                    try:
                        guild = interaction.guild
                        member = guild.get_member(self.user_id)
                        
                        if member:
                            # Find the 'AK | Member' role
                            member_role = discord.utils.get(guild.roles, name="AK | Member")
                            
                            if member_role:
                                await member.add_roles(member_role, reason="Join request approved")
                            else:
                                logger.warning(f"'AK | Member' role not found in guild {self.guild_id}")
                        else:
                            logger.warning(f"Member {self.user_id} not found in guild {self.guild_id}")
                    except Exception as e:
                        logger.error(f"Error assigning role to user {self.user_id}: {e}", exc_info=True)
                    
                else:
                    logger.error(f"No request data found for request_id {self.request_id}")
            
            # Update embed
            embed = interaction.message.embeds[0]
            embed.color = discord.Color.green()
            embed.add_field(
                name="Status",
                value=f"✅ Approved by <@{interaction.user.id}>",
                inline=False
            )
            
            # Disable buttons
            for item in self.children:
                item.disabled = True
            
            await interaction.response.edit_message(embed=embed, view=self)
            
            # Get the join settings to find the build setup channel
            settings = self.db.get_join_settings(self.guild_id)
            build_setup_channel_id = settings.get('build_setup_channel_id') if settings else None
            join_channel_id = settings.get('join_channel_id') if settings else None
            
            # Send DM to user directing them to build setup
            guild = interaction.guild
            member = guild.get_member(self.user_id)
            
            if member:
                approval_msg = get_text(self.db, self.LANGUAGES, self.guild_id, "join_approved", self.user_id)
                
                # Use build_setup_channel if set, otherwise fall back to join channel
                channel_id = build_setup_channel_id or join_channel_id
                if channel_id:
                    channel = guild.get_channel(channel_id)
                    if channel:
                        channel_mention = channel.mention
                    else:
                        channel_mention = "#build-setup"
                else:
                    channel_mention = "#build-setup"
                
                # Send DM to user
                try:
                    await member.send(
                        f"🎉 **{approval_msg}**\n\n"
                        f"Please go to {channel_mention} and click the **'Setup Profile'** button to complete your profile setup!"
                    )
                except discord.Forbidden:
                    # Can't DM user, mention them in admin channel instead
                    await interaction.channel.send(
                        f"🎉 {member.mention} **{approval_msg}**\n\n"
                        f"Please go to {channel_mention} and click the **'Setup Profile'** button to complete your profile setup!"
                    )
                    logger.warning(f"Could not DM user {self.user_id}, sent message in channel instead")
            
        except Exception as e:
            logger.error(f"Error in approval: {e}", exc_info=True)
    
    @ui.button(label="❌ Reject", style=discord.ButtonStyle.danger, custom_id="reject_join")
    async def reject_button(self, interaction: discord.Interaction, button: ui.Button):
        """Handle rejection"""
        try:
            # Show modal for rejection reason
            modal = RejectionReasonModal(
                self.user_id, self.guild_id, self.language,
                self.request_id, self.db, self.LANGUAGES
            )
            await interaction.response.send_modal(modal)
            
        except Exception as e:
            logger.error(f"Error in rejection: {e}", exc_info=True)


class RejectionReasonModal(ui.Modal):
    """Modal for entering rejection reason"""
    
    def __init__(self, user_id: int, guild_id: int, language: str, request_id: int, db: Database, LANGUAGES: dict):
        super().__init__(title="Rejection Reason")
        self.user_id = user_id
        self.guild_id = guild_id
        self.language = language
        self.request_id = request_id
        self.db = db
        self.LANGUAGES = LANGUAGES
        
        self.reason_input = ui.TextInput(
            label="Reason for rejection",
            placeholder="e.g., Not active enough, doesn't meet requirements",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=500
        )
        self.add_item(self.reason_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle rejection reason submission"""
        try:
            reason = self.reason_input.value.strip()
            
            # Update request status
            if self.request_id:
                self.db.update_join_request_status(self.request_id, "rejected", interaction.user.id, reason)
            
            # Update embed
            embed = interaction.message.embeds[0]
            embed.color = discord.Color.red()
            embed.add_field(
                name="Status",
                value=f"❌ Rejected by <@{interaction.user.id}>",
                inline=False
            )
            embed.add_field(name="Reason", value=reason, inline=False)
            
            # Disable buttons
            view = AdminApprovalView(self.user_id, self.guild_id, self.language, self.db, self.LANGUAGES)
            for item in view.children:
                item.disabled = True
            
            await interaction.response.edit_message(embed=embed, view=view)
            
            # Notify user
            guild = interaction.guild
            member = guild.get_member(self.user_id)
            
            if member:
                reject_msg = get_text(self.db, self.LANGUAGES, self.guild_id, "join_rejected_admin", self.user_id)
                reject_msg = reject_msg.format(reason=reason)
                
                try:
                    await member.send(reject_msg)
                except discord.Forbidden:
                    logger.warning(f"Could not DM user {self.user_id} for rejection notification")
            
        except Exception as e:
            logger.error(f"Error in rejection reason submission: {e}", exc_info=True)
