"""
Localization module for Discord bot.
Loads translations from locales.json for easy editing.
"""

import json
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Load languages from JSON file
LOCALES_FILE = Path(__file__).parent / "locales.json"

try:
    with open(LOCALES_FILE, 'r', encoding='utf-8') as f:
        LANGUAGES = json.load(f)
    logger.info(f"✅ Loaded {len(LANGUAGES)} language(s) from {LOCALES_FILE}")
except FileNotFoundError:
    # Fallback to minimal English if JSON file is missing
    logger.warning(f"⚠️ {LOCALES_FILE} not found, using minimal English fallback")
    LANGUAGES = {
        "en": {
            "dm_only": "This command can only be used in a server.",
            "help_title": "Bot Commands",
            "help_desc": "Available commands for this bot"
        }
    }
except json.JSONDecodeError as e:
    logger.error(f"❌ Error loading {LOCALES_FILE}: {e}")
    LANGUAGES = {"en": {}}
