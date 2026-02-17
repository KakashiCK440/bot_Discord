"""
Configuration and constants for the Discord bot.
Contains build types, weapon icons, and other static configuration.
"""

# Build System Icons
BUILD_ICONS = {
    "DPS": "<:Dps:1469039402113306747>",
    "Tank": "<:Tank:1469039369829748901>",
    "Healer": "<:Healer:1469039348656898158>",
}

# Weapon Icons
WEAPON_ICONS = {
    # DPS Weapons
    "Strategic Sword": "<:StrategicSword:1468707686907642110>",
    "Heaven Spear": "<:Heavenspear:1468707949517078539>",
    "Nameless Sword": "<:NamelessSword:1468707969574113411>",
    "Nameless Spear": "<:Namelessspear:1468707652212232333>",
    "Twinblade": "<:Twinblade:1468707797263978601>",
    "Mortal Rope": "<:MortalRobe:1468707859389878332>",
    "Vernal Umbrella": "<:VernalUmbrella:1468707906009436272>",
    "Inkwell Fan": "<:inkwellfan:1468707817379729605>",
    
    # Tank Weapons
    "Thunder Blade": "<:thunderblade:1468707839240311006>",
    "StormBreaker Spear": "<:StormBreakerspear:1468707928272797767>",
    
    # Healer Weapons
    "Panacea Fan": "<:Panaveafan:1468707753156415601>",
    "Soulshade Umbrella": "<:SoulshadeUmbrella:1468707729177706637>",
}

# Build Types and Associated Weapons
BUILDS = {
    "DPS": {
        "emoji": BUILD_ICONS["DPS"],
        "weapons": [
            "Strategic Sword",
            "Heaven Spear",
            "Nameless Sword",
            "Nameless Spear",
            "Twinblade",
            "Mortal Rope",
            "Vernal Umbrella",
            "Inkwell Fan"
        ]
    },
    "Tank": {
        "emoji": BUILD_ICONS["Tank"],
        "weapons": [
            "Thunder Blade",
            "StormBreaker Spear"
        ]
    },
    "Healer": {
        "emoji": BUILD_ICONS["Healer"],
        "weapons": [
            "Panacea Fan",
            "Soulshade Umbrella"
        ]
    }
}
