"""
Build selection views for Discord bot.
Handles build type selection and weapon selection UI components.
"""

import discord
from config import BUILDS, BUILD_ICONS, WEAPON_ICONS
from utils.helpers import get_text, update_member_nickname


class BuildSelectView(discord.ui.View):
    """View with dropdown to select build type"""
    def __init__(self, db, LANGUAGES, guild_id=None):
        super().__init__(timeout=None)
        self.db = db
        self.LANGUAGES = LANGUAGES
        self.stored_guild_id = guild_id  # For DM interactions
    
    @discord.ui.select(
        placeholder="Select your build type...",
        custom_id="build_select",
        options=[
            discord.SelectOption(
                label="DPS",
                description="Damage dealer - High damage output",
                emoji=BUILD_ICONS["DPS"],
                value="DPS"
            ),
            discord.SelectOption(
                label="Tank",
                description="Defender - High survivability",
                emoji=BUILD_ICONS["Tank"],
                value="Tank"
            ),
            discord.SelectOption(
                label="Healer",
                description="Support - Heal and buff allies",
                emoji=BUILD_ICONS["Healer"],
                value="Healer"
            ),
        ]
    )
    async def build_select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        """Handle build selection"""
        try:
            await interaction.response.defer(ephemeral=True)
            
            build_name = select.values[0]
            user_id = interaction.user.id
            
            # Use stored guild_id if interaction is in DM
            guild_id = interaction.guild_id or self.stored_guild_id
            
            # Check if we have a guild_id
            if not guild_id:
                await interaction.followup.send(
                    "❌ Could not determine server. Please try again.",
                    ephemeral=True
                )
                return
            
            # Get guild object
            guild = interaction.guild
            if not guild:
                # Try to get guild from bot (for DM interactions)
                guild = interaction.client.get_guild(guild_id)
                if not guild:
                    await interaction.followup.send(
                        "❌ Could not find server. Please contact an admin.",
                        ephemeral=True
                    )
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
                    await interaction.followup.send(
                        "❌ Failed to update build. Please try again later.",
                        ephemeral=True
                    )
                    return
            else:
                await interaction.followup.send(
                    "❌ Please set up your profile first using `/setupprofile`.",
                    ephemeral=True
                )
                return
            
            # Assign role
            member = guild.get_member(user_id)
            if not member:
                # User might have left the server
                await interaction.followup.send(
                    "❌ Could not find you in the server.",
                    ephemeral=True
                )
                return
            
            # Remove old build roles and weapon roles
            from utils.helpers import remove_all_build_roles
            success, removed_count = await remove_all_build_roles(member, guild)
            
            # Add new build role
            role = discord.utils.get(guild.roles, name=build_name)
            if role:
                try:
                    await member.add_roles(role)
                except discord.Forbidden:
                    # Bot doesn't have permission, log or ignore
                    pass
            
            # Clear previous weapons from database
            self.db.set_player_weapons(user_id, guild_id, [])
            
            # Disable the dropdown to prevent re-selection
            for item in self.children:
                item.disabled = True
            
            # Edit the message to show selection
            try:
                await interaction.edit_original_response(
                    content=f"✅ Build selected: **{BUILDS[build_name]['emoji']} {build_name}**",
                    view=self
                )
            except:
                pass
            
            # Show weapon selection
            weapon_view = WeaponSelectView(build_name, guild_id, user_id, self.db, self.LANGUAGES)
            
            # Use followup since we deferred
            await interaction.followup.send(
                f"{get_text(self.db, self.LANGUAGES, guild_id, 'now_select_weapons', user_id)}",
                view=weapon_view,
                ephemeral=True
            )
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Error in build selection: {e}", exc_info=True)
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(
                        "❌ An error occurred while selecting your build. Please try again later.",
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        "❌ An error occurred while selecting your build. Please try again later.",
                        ephemeral=True
                    )
            except:
                pass


class WeaponSelectView(discord.ui.View):
    """View with dropdown to select weapons (max 2). Uses user language for placeholder and messages."""
    def __init__(self, build_type: str, guild_id: int, user_id: int = None, db=None, LANGUAGES=None):
        super().__init__(timeout=180)
        self.build_type = build_type
        self.guild_id = guild_id
        self.user_id = user_id
        self.db = db
        self.LANGUAGES = LANGUAGES
        
        weapons = BUILDS[build_type]["weapons"]
        options = []
        for weapon in weapons[:25]:
            icon = WEAPON_ICONS.get(weapon, "⚔️")
            options.append(
                discord.SelectOption(label=weapon, emoji=icon, value=weapon)
            )
        
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
            user_id = interaction.user.id
            guild_id = self.guild_id
            
            # Get guild object (handle DM interactions)
            guild = interaction.guild
            if not guild:
                # Try to get guild from bot (for DM interactions)
                guild = interaction.client.get_guild(guild_id)
                if not guild:
                    await interaction.followup.send(
                        "❌ Could not find server. Please contact an admin.",
                        ephemeral=True
                    )
                    return
            
            # Get member
            member = guild.get_member(user_id)
            if not member:
                await interaction.followup.send(
                    "❌ Could not find you in the server.",
                    ephemeral=True
                )
                return
            
            # Get current weapons before updating
            old_weapons = self.db.get_player_weapons(user_id, guild_id)
            
            # Save weapons to database
            success = self.db.set_player_weapons(user_id, guild_id, weapons)
            if not success:
                await interaction.followup.send(
                    "❌ Failed to save weapons. Please try again later.",
                    ephemeral=True
                )
                return
            
            # Get player profile
            player = self.db.get_player(user_id, guild_id)
            
            # Remove old build roles
            for build_name in ["DPS", "Tank", "Healer"]:
                role = discord.utils.get(guild.roles, name=build_name)
                if role and role in member.roles:
                    try:
                        await member.remove_roles(role)
                    except discord.Forbidden:
                        pass  # Bot doesn't have permission
            
            # Remove old weapon roles
            for old_weapon in old_weapons:
                weapon_role = discord.utils.get(guild.roles, name=old_weapon)
                if weapon_role and weapon_role in member.roles:
                    try:
                        await member.remove_roles(weapon_role)
                    except discord.Forbidden:
                        pass
            
            # Add current build role
            build_role = discord.utils.get(guild.roles, name=self.build_type)
            if build_role:
                try:
                    await member.add_roles(build_role)
                except discord.Forbidden:
                    pass
            
            # Add new weapon roles
            for weapon in weapons:
                weapon_role = discord.utils.get(guild.roles, name=weapon)
                if weapon_role:
                    try:
                        await member.add_roles(weapon_role)
                    except discord.Forbidden:
                        pass
            
            # Update nickname
            if player and player.get('in_game_name'):
                try:
                    await update_member_nickname(member, player['in_game_name'])
                except:
                    pass  # Nickname update failed, not critical
            
            # Disable the dropdown to prevent re-selection
            for item in self.children:
                item.disabled = True
            
            # Prepare weapons display
            weapons_display = "\n".join([
                f"{WEAPON_ICONS.get(w, '⚔️')} {w}" for w in weapons
            ])
            
            # Edit the message to show selection
            try:
                await interaction.edit_original_response(
                    content=f"✅ Weapons selected:\n{weapons_display}",
                    view=self
                )
            except:
                pass
            
            # Send final success message
            await interaction.followup.send(
                f"🎉 **{get_text(self.db, self.LANGUAGES, guild_id, 'profile_setup_complete', user_id) if get_text(self.db, self.LANGUAGES, guild_id, 'profile_setup_complete', user_id) != 'profile_setup_complete' else 'Profile setup complete!'}**\n\n"
                f"Your build: **{BUILDS[self.build_type]['emoji']} {self.build_type}**\n"
                f"Your weapons:\n{weapons_display}",
                ephemeral=True
            )
            
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Error in weapon selection: {e}", exc_info=True)
            try:
                await interaction.followup.send(
                    "❌ An error occurred. Please try again.",
                    ephemeral=True
                )
            except:
                pass
