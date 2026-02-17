"""
War system helper functions.
Handles war participation tracking, configuration, and database operations.
"""

from datetime import datetime


def get_current_poll_week() -> str:
    """Get current poll week identifier (e.g., '2024-W01')"""
    return datetime.now().strftime("%Y-W%U")


def get_war_participants(db, guild_id: int, poll_week: str = None) -> dict:
    """Get all war participants organized by day from database"""
    if poll_week is None:
        poll_week = get_current_poll_week()

    # Get participants from database
    participants_by_type = db.get_war_participants_by_type(guild_id, poll_week)

    return {
        "saturday_players": set(participants_by_type["saturday"]),
        "sunday_players": set(participants_by_type["sunday"]),
        "both_days_players": set(participants_by_type["both"]),
        "not_playing": set(participants_by_type["not_playing"])
    }


def set_war_participation(db, guild_id: int, user_id: int, day_choice: str):
    """Set player's war participation choice"""
    poll_week = get_current_poll_week()
    
    # Set participation (this automatically replaces any existing participation)
    if day_choice in ["saturday", "sunday", "both", "none"]:
        # Store as "not_playing" in DB to match get_war_participants_by_type
        stored = "not_playing" if day_choice == "none" else day_choice
        db.set_war_participation(user_id, guild_id, poll_week, stored)


def get_war_config(db, guild_id: int) -> dict:
    """Get war configuration for a guild"""
    settings = db.get_server_settings(guild_id)
    
    return {
        "poll_day": settings.get('poll_day', 'Friday'),
        "poll_time": {
            "hour": int(settings.get('poll_time_hour', 15)),
            "minute": int(settings.get('poll_time_minute', 0))
        },
        "saturday_war": {
            "hour": int(settings.get('saturday_war_hour', 22)),
            "minute": int(settings.get('saturday_war_minute', 30))
        },
        "sunday_war": {
            "hour": int(settings.get('sunday_war_hour', 22)),
            "minute": int(settings.get('sunday_war_minute', 30))
        },
        "reminder_hours": int(settings.get('reminder_hours_before', 2)),
        "war_channel_id": settings.get('war_channel_id'),
        "timezone": settings.get('timezone', 'Africa/Cairo'),
    }


def update_war_setting(db, guild_id: int, setting: str, value):
    """Update a war configuration setting in database"""
    return db.update_server_setting(guild_id, setting, value)
