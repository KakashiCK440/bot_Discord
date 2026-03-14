"""
Configuration and constants for the Discord bot.
Contains build types, weapon icons, and other static configuration.
"""

# Build System Icons
BUILD_ICONS = {
    "DPS": "<:emoji_1:1472992992791887964>",
    "Tank": "<:emoji_3:1472993077772947529>",
    "Healer": "<:emoji_2:1472993038644023460>",
}

# Weapon Icons
WEAPON_ICONS = {
    # DPS Weapons
    "Strategic Sword": "<:emoji_4:1472993158307647488>",
    "Heaven Spear": "<:emoji_5:1472993239446458388>",
    "Nameless Sword": "<:emoji_6:1472993290327560405>",
    "Nameless Spear": "<:emoji_7:1472993541084151909>",
    "Twinblade": "<:emoji_8:1472993615323336714>",
    "Mortal Rope": "<:emoji_9:1472993657115246724>",
    "Vernal Umbrella": "<:emoji_11:1472993745891758152>",
    "Inkwell Fan": "<:emoji_10:1472993704288719019>",

    # Tank Weapons
    "Thunder Blade": "<:emoji_14:1473213215327387800>",
    "StormBreaker Spear": "<:emoji_15:1473213254816895119>",

    # Healer Weapons
    "Panacea Fan": "<:emoji_12:1472993793203634338>",
    "Soulshade Umbrella": "<:emoji_12:1472993825537654869>",
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
