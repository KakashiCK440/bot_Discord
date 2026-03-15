"""
Profile setup views for Discord bot.
Handles language selection, profile setup button, and complete profile modal.
"""

import discord
from config import get_builds_config
from utils.helpers import get_text, update_member_nickname
from locales import LANGUAGES


class LanguageSelectView(discord.ui.View):
    """Let user choose English or Arabic before continuing to profile setup."""
    def __init__(self, guild_id: int, db, LANGUAGES):
        super().__init__(timeout=60)
        self.guild_id = guild_id
        self.db = db
        self.LANGUAGES = LANGUAGES
        
        # Add language dropdown
        self.add_item(LanguageDropdown(guild_id, db, LANGUAGES))


class LanguageDropdown(discord.ui.Select):
    """Dropdown for language selection"""
    def __init__(self, guild_id: int, db, LANGUAGES):
        self.guild_id = guild_id
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
        try:
            guild_id = interaction.guild_id
            user_id = interaction.user.id
            lang = self.values[0]
            
            # Save language preference BEFORE sending modal (fast DB call)
            self.db.set_user_language(user_id, guild_id, lang)
            
            # Send modal IMMEDIATELY - no extra edit call needed
            modal = CompleteProfileModal(guild_id, user_id, self.db, self.LANGUAGES)
            await interaction.response.send_modal(modal)
            
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Error in language selection: {e}", exc_info=True)
            try:
                await interaction.response.send_message(
                    "❌ An error occurred. Please try again later.",
                    ephemeral=True
                )
            except:
                pass


class ProfileSetupButton(discord.ui.View):
    """Single button: first time shows language choice, then profile form (label uses guild language when guild_id given)"""
    def __init__(self, guild_id: int = None, db=None, LANGUAGES=None):
        super().__init__(timeout=None)
        self.db = db
        self.LANGUAGES = LANGUAGES
        self.guild_id = guild_id
        label = get_text(db, LANGUAGES, guild_id, "setup_profile_btn") if guild_id is not None else LANGUAGES["en"].get("setup_profile_btn", "📝 Setup Your Profile")
        btn = discord.ui.Button(
            label=label,
            style=discord.ButtonStyle.primary,
            custom_id="setup_profile_button",
            emoji="🎮"
        )
        btn.callback = self._setup_callback
        self.add_item(btn)
    
    async def _setup_callback(self, interaction: discord.Interaction):
        try:
            guild_id = interaction.guild_id
            user_id = interaction.user.id
            prompt = get_text(self.db, self.LANGUAGES, guild_id, "choose_language_prompt", user_id)
            await interaction.response.send_message(
                f"**{get_text(self.db, self.LANGUAGES, guild_id, 'choose_language', user_id)}**\n\n{prompt}",
                view=LanguageSelectView(guild_id, self.db, self.LANGUAGES),
                ephemeral=True
            )
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Error in profile setup: {e}", exc_info=True)
            try:
                await interaction.response.send_message(
                    "❌ An error occurred. Please try again later.",
                    ephemeral=True
                )
            except:
                pass



class CompleteProfileModal(discord.ui.Modal):
    """Modal for completing profile setup with all fields"""
    def __init__(self, guild_id: int, user_id: int, db, LANGUAGES):
        self.guild_id = guild_id
        self.user_id = user_id
        self.db = db
        self.LANGUAGES = LANGUAGES
        
        # Use hardcoded bilingual text to avoid database queries during init
        super().__init__(title="Profile Setup | إعداد الملف الشخصي")
        self.add_item(discord.ui.TextInput(
            label="In-Game Name | الاسم في اللعبة",
            placeholder="Your in-game name | اسمك في اللعبة",
            required=True,
            max_length=50
        ))
        self.add_item(discord.ui.TextInput(
            label="Level | المستوى",
            placeholder="e.g., 60 | مثال: 60",
            required=True,
            max_length=3
        ))
        self.add_item(discord.ui.TextInput(
            label="Mastery Points | نقاط الإتقان",
            placeholder="e.g., 50000 | مثال: 50000",
            required=True,
            max_length=10
        ))
    
    async def on_submit(self, interaction: discord.Interaction):
        # Import BuildSelectView here to avoid circular imports
        from views.build_views import BuildSelectView
        
        guild_id = interaction.guild_id
        user_id = interaction.user.id
        children = self.children
        ign_value = children[0].value
        level_value = children[1].value
        mastery_value = children[2].value
        
        try:
            level_val = int(level_value)
            if level_val < 1 or level_val > 100:
                await interaction.response.send_message(
                    get_text(self.db, self.LANGUAGES, guild_id, "err_level_range", user_id),
                    ephemeral=True
                )
                return
            
            mastery_val = int(mastery_value.replace(",", "").replace(" ", ""))
            if mastery_val < 0:
                await interaction.response.send_message(
                    get_text(self.db, self.LANGUAGES, guild_id, "err_mastery_positive", user_id),
                    ephemeral=True
                )
                return
            
            # Default to first build in DB (or 'DPS' if none)
            builds = get_builds_config(self.db)
            default_build = next(iter(builds), "DPS")
            self.db.create_or_update_player(
                user_id, guild_id,
                ign_value,
                mastery_val,
                level_val,
                default_build
            )
            
            member = interaction.user
            nickname_success, nickname_msg = await update_member_nickname(member, ign_value)
            
            build_view = BuildSelectView(self.db, self.LANGUAGES)
            
            # Send build selection directly without showing profile created message
            # This keeps the chat clean
            build_msg = get_text(self.db, self.LANGUAGES, guild_id, 'now_select_build', user_id)
            await interaction.response.send_message(
                build_msg,
                view=BuildSelectView(self.db, self.LANGUAGES, guild_id),
                ephemeral=True
            )
            
            # Note: The language selection message is ephemeral and will auto-delete
            # after the user interacts with the modal. No need to manually delete it.
            # The profile existence check in /setupprofile prevents re-running setup.
        except ValueError:
            await interaction.response.send_message(
                get_text(self.db, self.LANGUAGES, guild_id, "err_invalid_numbers", user_id),
                ephemeral=True
            )
