"""
Configuration and constants for the Discord bot.
Contains build types, weapon icons, and other static configuration.
These dicts are the SEED defaults — at runtime the bot reads from the database.
"""

# Build System Icons (seed defaults)
BUILD_ICONS = {
    "DPS": "<:emoji_1:1472992992791887964>",
    "Tank": "<:emoji_3:1472993077772947529>",
    "Healer": "<:emoji_2:1472993038644023460>",
}

# Weapon Icons (seed defaults)
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

# Build Types and Associated Weapons (seed defaults)
BUILDS = {
    "DPS": {
        "emoji": BUILD_ICONS["DPS"],
        "description": "Damage dealer - High damage output",
        "weapons": [
            "Strategic Sword", "Heaven Spear", "Nameless Sword", "Nameless Spear",
            "Twinblade", "Mortal Rope", "Vernal Umbrella", "Inkwell Fan"
        ]
    },
    "Tank": {
        "emoji": BUILD_ICONS["Tank"],
        "description": "Defender - High survivability",
        "weapons": ["Thunder Blade", "StormBreaker Spear"]
    },
    "Healer": {
        "emoji": BUILD_ICONS["Healer"],
        "description": "Support - Heal and buff allies",
        "weapons": ["Panacea Fan", "Soulshade Umbrella"]
    }
}


# ── Runtime helpers (DB-first, fallback to hardcoded seed) ────────────────────

def get_builds_config(db) -> dict:
    """
    Return a BUILDS-shaped dict read live from the database.
    Falls back to the hardcoded BUILDS dict if the DB tables are empty or unavailable.

    Shape:
        {
          "DPS": {"emoji": "...", "description": "...", "weapons": ["Sword", ...]},
          ...
        }
    """
    try:
        builds_rows = db.get_builds()
        if not builds_rows:
            return BUILDS
        result = {}
        for b in builds_rows:
            name = b["name"]
            weapons_rows = db.get_weapons(name)
            result[name] = {
                "emoji": b["emoji"],
                "description": b.get("description", ""),
                "weapons": [w["name"] for w in weapons_rows],
            }
        return result
    except Exception:
        return BUILDS


def get_weapon_icon(db, weapon_name: str) -> str:
    """Return the emoji for a weapon. DB-first, then hardcoded fallback."""
    try:
        row = db.get_weapon_by_name(weapon_name)
        if row:
            return row["emoji"]
    except Exception:
        pass
    return WEAPON_ICONS.get(weapon_name, "⚔️")
