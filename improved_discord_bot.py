import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
from aiohttp import web
import asyncio
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

intents = discord.Intents.default()
intents.members = True
intents.message_content = True  # Enable message content intent

bot = commands.Bot(command_prefix="!", intents=intents)

# -----------------------------
# Web Server for Health Checks
# -----------------------------
async def health_check(request):
    """Simple health check endpoint for Koyeb"""
    return web.Response(text="OK", status=200)

async def start_web_server():
    """Start the web server for health checks"""
    app = web.Application()
    app.router.add_get('/', health_check)
    app.router.add_get('/health', health_check)
    
    port = int(os.getenv('PORT', 8000))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logger.info(f"🌐 Web server started on port {port}")
    return runner

# -----------------------------
# Build and Weapon Data
# -----------------------------
BUILDS = {
    "DPS": [
        "Strategic Sword",
        "Heaven Spear",
        "Nameless Sword",
        "Nameless Spear",
        "Twinblade",
        "Mortal Rope",
        "Vernal Umbrella",
        "Inkwell Fan"
    ],
    "Tank": [
        "Thunder Blade",
        "StormBreaker Spear"
    ],
    "Healer": [
        "Panacea Fan",
        "Soulshade Umbrella"
    ]
}

# Build emojis
dps_emoji = discord.PartialEmoji(name="DPS", id=1469039402113306747)
tank_emoji = discord.PartialEmoji(name="Tank", id=1469039369829748901)
healer_emoji = discord.PartialEmoji(name="Healer", id=1469039348656898158)

# Weapon emojis
WEAPON_EMOJIS = {
    "Strategic Sword": discord.PartialEmoji(name="StrategicSword", id=1468707686907642110),
    "Heaven Spear": discord.PartialEmoji(name="Heavenspear", id=1468707949517078539),
    "Nameless Sword": discord.PartialEmoji(name="NamelessSword", id=1468707969574113411),
    "Nameless Spear": discord.PartialEmoji(name="Namelessspear", id=1468707652212232333),
    "Twinblade": discord.PartialEmoji(name="Twinblade", id=1468707797263978601),
    "Mortal Rope": discord.PartialEmoji(name="MortalRobe", id=1468707859389878332),
    "Vernal Umbrella": discord.PartialEmoji(name="VernalUmbrella", id=1468707906009436272),
    "Inkwell Fan": discord.PartialEmoji(name="inkwellfan", id=1468707817379729605),
    "Thunder Blade": discord.PartialEmoji(name="thunderblade", id=1468707839240311006),
    "StormBreaker Spear": discord.PartialEmoji(name="StormBreakerspear", id=1468707928272797767),
    "Panacea Fan": discord.PartialEmoji(name="Panaveafan", id=1468707753156415601),
    "Soulshade Umbrella": discord.PartialEmoji(name="SoulshadeUmbrella", id=1468707729177706637),
}

# -----------------------------
# Reset / Keep Buttons
# -----------------------------
class ConfirmationButtons(discord.ui.View):
    def __init__(self, member: discord.Member):
        super().__init__(timeout=300)  # 5 minute timeout
        self.member = member
        self.add_item(ResetButton(member))
        self.add_item(KeepButton())

class ResetButton(discord.ui.Button):
    def __init__(self, member: discord.Member):
        super().__init__(style=discord.ButtonStyle.danger, label="Reset / Choose Again")
        self.member = member

    async def callback(self, interaction: discord.Interaction):
        # Security check
        if interaction.user.id != self.member.id:
            await interaction.response.send_message(
                "❌ You can only reset your own roles!",
                ephemeral=True
            )
            return

        # Remove all build/weapon roles
        removed_roles = []
        for role in self.member.roles:
            if any(role.name.startswith(f"{b} •") for b in BUILDS):
                try:
                    await self.member.remove_roles(role)
                    removed_roles.append(role.name)
                except discord.Forbidden:
                    await interaction.response.send_message(
                        "❌ I don't have permission to remove roles!",
                        ephemeral=True
                    )
                    return

        # Edit the message to show build selection again
        await interaction.response.edit_message(
            content=f"✅ Your roles have been reset. Choose your new build:",
            view=BuildSelectView()
        )

class KeepButton(discord.ui.Button):
    def __init__(self):
        super().__init__(style=discord.ButtonStyle.secondary, label="Keep Roles")

    async def callback(self, interaction: discord.Interaction):
        # Just edit the current message to remove buttons
        await interaction.response.edit_message(
            content="✅ Your roles have been saved!",
            view=None
        )

# -----------------------------
# Weapon Selection
# -----------------------------
class WeaponSelect(discord.ui.Select):
    def __init__(self, build, member: discord.Member):
        self.build = build
        self.member = member
        options = []

        current_roles = [role for role in member.roles if role.name.startswith(f"{build} •")]
        max_reached = len(current_roles) >= 2

        for w in BUILDS[build]:
            emoji = WEAPON_EMOJIS.get(w)
            options.append(discord.SelectOption(label=w, emoji=emoji) if emoji else discord.SelectOption(label=w))

        super().__init__(
            placeholder=f"{build} weapons (choose up to 2)",
            options=options,
            min_values=1,  # Changed from 0 to 1 - must select at least 1
            max_values=2 if not max_reached else 0,
            disabled=max_reached
        )

    async def callback(self, interaction: discord.Interaction):
        # Security check
        if interaction.user.id != self.member.id:
            await interaction.response.send_message(
                "❌ You can only select weapons for yourself!",
                ephemeral=True
            )
            return

        member = self.member
        guild = interaction.guild

        current_roles = [role for role in member.roles if role.name.startswith(f"{self.build} •")]
        
        if len(current_roles) >= 2:
            await interaction.response.send_message(
                "⚠️ You already have 2 weapon roles. Please reset to choose again.",
                ephemeral=True
            )
            return

        # Remove old roles from this build
        for role in current_roles:
            try:
                await member.remove_roles(role)
            except discord.Forbidden:
                await interaction.response.send_message(
                    "❌ I don't have permission to manage roles!",
                    ephemeral=True
                )
                return

        # Add new roles
        added_roles = []
        missing_roles = []
        for weapon in self.values:
            role_name = f"{self.build} • {weapon}"
            role = discord.utils.get(guild.roles, name=role_name)
            if role:
                try:
                    await member.add_roles(role)
                    added_roles.append(role_name)
                except discord.Forbidden:
                    await interaction.response.send_message(
                        "❌ I don't have permission to assign roles!",
                        ephemeral=True
                    )
                    return
            else:
                missing_roles.append(role_name)

        # If user selected 2 weapons, show final confirmation
        if len(self.values) == 2:
            # Build response message
            msg = f"✅ Your roles have been updated:\n" + "\n".join(f"• {r}" for r in added_roles)
            if missing_roles:
                msg += f"\n\n⚠️ **Warning:** These roles don't exist on the server:\n" + "\n".join(f"• {r}" for r in missing_roles)

            # Edit the message to show confirmation
            await interaction.response.edit_message(
                content=msg,
                view=ConfirmationButtons(member)
            )
        else:
            # User selected only 1 weapon, show option to select 2nd or finish
            await interaction.response.edit_message(
                content=f"✅ Selected **{self.values[0]}**.\nYou can:\n• Select another weapon from the menu below, or\n• Click 'Finish Selection' to continue with 1 weapon.",
                view=WeaponSelectViewWithFinish(self.build, member, added_roles)
            )

class WeaponSelectView(discord.ui.View):
    def __init__(self, build, member: discord.Member):
        super().__init__(timeout=300)  # 5 minute timeout
        self.add_item(WeaponSelect(build, member))

class WeaponSelectViewWithFinish(discord.ui.View):
    def __init__(self, build, member: discord.Member, added_roles: list):
        super().__init__(timeout=300)
        self.build = build
        self.member = member
        self.added_roles = added_roles
        self.add_item(WeaponSelect(build, member))
        self.add_item(FinishButton(member, added_roles))

class FinishButton(discord.ui.Button):
    def __init__(self, member: discord.Member, added_roles: list):
        super().__init__(style=discord.ButtonStyle.success, label="Finish Selection")
        self.member = member
        self.added_roles = added_roles

    async def callback(self, interaction: discord.Interaction):
        # Security check
        if interaction.user.id != self.member.id:
            await interaction.response.send_message(
                "❌ You can only finish your own selection!",
                ephemeral=True
            )
            return

        # Build response message with current roles
        msg = f"✅ Your roles have been updated:\n" + "\n".join(f"• {r}" for r in self.added_roles)

        # Edit the message to show confirmation
        await interaction.response.edit_message(
            content=msg,
            view=ConfirmationButtons(self.member)
        )


# -----------------------------
# Build Selection
# -----------------------------
class BuildSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="DPS", emoji=dps_emoji, description="Damage dealer build"),
            discord.SelectOption(label="Tank", emoji=tank_emoji, description="Tank/defender build"),
            discord.SelectOption(label="Healer", emoji=healer_emoji, description="Support/healer build"),
        ]
        super().__init__(placeholder="Choose your build", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        # Check if user already has a build
        existing_build_roles = [role for role in interaction.user.roles if any(role.name.startswith(f"{b} •") for b in BUILDS)]
        if existing_build_roles:
            await interaction.response.send_message(
                "⚠️ You already have a build selected. Please use `/resetbuild` before choosing a new build.",
                ephemeral=True
            )
            return

        build = self.values[0]
        view = WeaponSelectView(build, member=interaction.user)
        
        # Edit the message instead of deleting (ephemeral messages can't be deleted)
        await interaction.response.edit_message(
            content=f"Choose 1-2 weapons for **{build}**:",
            view=view
        )

class BuildSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # Persistent view
        self.add_item(BuildSelect())

# -----------------------------
# Slash Commands
# -----------------------------
@bot.tree.command(name="postbuilds", description="Post the build selection menu (Admin only)")
@discord.app_commands.checks.has_permissions(administrator=True)
async def postbuilds(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🎮 Choose Your Build",
        description="Select your build and weapons below!\nYou can choose up to 2 weapons per build.",
        color=discord.Color.blue()
    )
    embed.add_field(name="DPS", value="High damage output", inline=True)
    embed.add_field(name="Tank", value="Defensive powerhouse", inline=True)
    embed.add_field(name="Healer", value="Support your team", inline=True)
    embed.set_footer(text="Use /resetbuild to change your selection")
    
    await interaction.response.send_message(
        embed=embed,
        view=BuildSelectView()
    )

@bot.tree.command(name="resetbuild", description="Reset your build and weapon roles")
async def resetbuild(interaction: discord.Interaction):
    member = interaction.user
    removed_roles = []
    
    for role in member.roles:
        if any(role.name.startswith(f"{b} •") for b in BUILDS):
            try:
                await member.remove_roles(role)
                removed_roles.append(role.name)
            except discord.Forbidden:
                await interaction.response.send_message(
                    "❌ I don't have permission to remove roles!",
                    ephemeral=True
                )
                return

    if removed_roles:
        await interaction.response.send_message(
            content=f"✅ Your roles have been reset:\n" + "\n".join(f"• {r}" for r in removed_roles) + "\n\nChoose your new build:",
            ephemeral=True,
            view=BuildSelectView()
        )
    else:
        await interaction.response.send_message(
            "ℹ️ You don't have any build roles to reset.",
            ephemeral=True
        )

@bot.tree.command(name="mybuild", description="Show your current build and weapons")
async def mybuild(interaction: discord.Interaction):
    member = interaction.user
    build_roles = [role for role in member.roles if any(role.name.startswith(f"{b} •") for b in BUILDS)]
    
    if not build_roles:
        await interaction.response.send_message(
            "ℹ️ You don't have any build selected yet. Use the build selection menu to choose one!",
            ephemeral=True
        )
        return

    # Organize roles by build
    builds_dict = {}
    for role in build_roles:
        for build in BUILDS:
            if role.name.startswith(f"{build} •"):
                if build not in builds_dict:
                    builds_dict[build] = []
                weapon = role.name.replace(f"{build} • ", "")
                builds_dict[build].append(weapon)

    embed = discord.Embed(
        title=f"🎮 {member.display_name}'s Build",
        color=discord.Color.green()
    )
    
    for build, weapons in builds_dict.items():
        emoji_str = ""
        if build == "DPS":
            emoji_str = str(dps_emoji)
        elif build == "Tank":
            emoji_str = str(tank_emoji)
        elif build == "Healer":
            emoji_str = str(healer_emoji)
        
        embed.add_field(
            name=f"{emoji_str} {build}",
            value="\n".join(f"• {w}" for w in weapons),
            inline=False
        )
    
    embed.set_footer(text="Use /resetbuild to change your selection")
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="createroles", description="Create all build and weapon roles (Admin only)")
@discord.app_commands.checks.has_permissions(administrator=True)
async def createroles(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    
    guild = interaction.guild
    created = []
    existing = []
    
    for build, weapons in BUILDS.items():
        for weapon in weapons:
            role_name = f"{build} • {weapon}"
            role = discord.utils.get(guild.roles, name=role_name)
            
            if not role:
                try:
                    # Create role with color based on build
                    color = discord.Color.red() if build == "DPS" else \
                            discord.Color.blue() if build == "Tank" else \
                            discord.Color.green()
                    
                    await guild.create_role(name=role_name, color=color)
                    created.append(role_name)
                except discord.Forbidden:
                    await interaction.followup.send(
                        "❌ I don't have permission to create roles!",
                        ephemeral=True
                    )
                    return
            else:
                existing.append(role_name)
    
    msg = ""
    if created:
        msg += f"✅ **Created {len(created)} roles:**\n" + "\n".join(f"• {r}" for r in created[:10])
        if len(created) > 10:
            msg += f"\n...and {len(created) - 10} more"
    
    if existing:
        msg += f"\n\nℹ️ **{len(existing)} roles already existed**"
    
    await interaction.followup.send(msg, ephemeral=True)

@bot.event
async def on_ready():
    await bot.tree.sync()
    logger.info(f"✅ Logged in as {bot.user}")
    logger.info(f"📊 Serving {len(bot.guilds)} guild(s)")
    logger.info(f"🔧 Commands synced!")

# Error handling
@postbuilds.error
@createroles.error
async def admin_error(interaction: discord.Interaction, error):
    if isinstance(error, discord.app_commands.errors.MissingPermissions):
        await interaction.response.send_message(
            "❌ You need Administrator permissions to use this command!",
            ephemeral=True
        )

# -----------------------------
# Main startup with web server
# -----------------------------
async def main():
    """Start both the web server and the Discord bot"""
    # Start web server first
    web_runner = await start_web_server()
    
    # Use environment variable for token
    TOKEN = os.getenv('DISCORD_BOT_TOKEN')
    if not TOKEN:
        logger.error("❌ ERROR: DISCORD_BOT_TOKEN not found in environment variables!")
        logger.error("Please set DISCORD_BOT_TOKEN in your environment")
        return
    
    try:
        # Start the bot with exponential backoff for rate limits
        async with bot:
            await bot.start(TOKEN)
    except discord.errors.HTTPException as e:
        if e.status == 429:  # Rate limited
            retry_after = e.response.headers.get('Retry-After', 60)
            logger.warning(f"⏳ Rate limited. Waiting {retry_after} seconds before retrying...")
            await asyncio.sleep(float(retry_after))
            async with bot:
                await bot.start(TOKEN)
        else:
            raise
    finally:
        await web_runner.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
