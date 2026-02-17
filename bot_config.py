"""
Bot configuration settings.
Contains runtime configuration for tasks, timeouts, and other settings.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# Task intervals (in minutes)
WAR_POLL_CHECK_INTERVAL = int(os.getenv("WAR_POLL_CHECK_INTERVAL", "5"))  # 5 min default
WAR_REMINDER_CHECK_INTERVAL = int(os.getenv("WAR_REMINDER_CHECK_INTERVAL", "5"))  # 5 min default
CLEANUP_INTERVAL_HOURS = int(os.getenv("CLEANUP_INTERVAL_HOURS", "24"))  # 24 hours default

# Cleanup settings
CLEANUP_OLDER_THAN_WEEKS = int(os.getenv("CLEANUP_OLDER_THAN_WEEKS", "4"))  # 4 weeks default

# View timeouts (in seconds, None = no timeout)
WEAPON_SELECT_TIMEOUT = 180  # 3 minutes for weapon selection
LANGUAGE_SELECT_TIMEOUT = 60  # 1 minute for language selection

# Web server
WEB_SERVER_PORT = int(os.getenv("PORT", "8080"))

# Discord token
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
