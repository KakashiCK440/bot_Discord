import logging
import os
from datetime import datetime
from typing import Optional, List, Dict, Tuple
import json
from contextlib import contextmanager

import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

# Whitelist of allowed server settings to prevent SQL injection
ALLOWED_SETTINGS = {
    'language', 'war_channel_id', 'poll_day', 'poll_time_hour', 'poll_time_minute',
    'saturday_war_hour', 'saturday_war_minute', 'sunday_war_hour', 'sunday_war_minute',
    'reminder_hours_before', 'timezone'
}


class Database:
    def __init__(self, db_path: str = None):
        """Initialize PostgreSQL database connection"""
        # Get DATABASE_URL from environment
        self.database_url = os.getenv('DATABASE_URL')
        
        if not self.database_url:
            raise ValueError(
                "DATABASE_URL environment variable is required. "
                "Please set it to your Neon PostgreSQL connection string."
            )
        
        self._init_postgres_pool()
        logger.info("🐘 Using PostgreSQL database")
        self.init_database()
    
    def _init_postgres_pool(self):
        """Initialize PostgreSQL connection pool"""
        try:
            self.connection_pool = psycopg2.pool.SimpleConnectionPool(
                1,  # minconn
                10,  # maxconn
                self.database_url
            )
            logger.info("✅ PostgreSQL connection pool created")
        except Exception as e:
            logger.error(f"Error creating PostgreSQL connection pool: {e}")
            raise
    
    @contextmanager
    def get_connection(self):
        """Get a connection from the pool"""
        conn = self.connection_pool.getconn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self.connection_pool.putconn(conn)
    
    def init_database(self):
        """Initialize database and create tables"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                self.create_tables_with_cursor(cursor)
            db_info = self.database_url.split('@')[1] if '@' in self.database_url else 'database'
            logger.info(f"✅ Database initialized: {db_info}")
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            raise
    
    def create_tables_with_cursor(self, cursor):
        """Create all necessary tables using PostgreSQL syntax"""
        
        # Players table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS players (
                user_id BIGINT,
                guild_id BIGINT,
                in_game_name TEXT,
                mastery_points INTEGER DEFAULT 0,
                level INTEGER DEFAULT 1,
                build_type TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, guild_id)
            )
        """)
        
        # Player weapons table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS player_weapons (
                user_id BIGINT,
                guild_id BIGINT,
                weapon_name TEXT,
                PRIMARY KEY (user_id, guild_id, weapon_name),
                FOREIGN KEY (user_id, guild_id) REFERENCES players(user_id, guild_id) ON DELETE CASCADE
            )
        """)
        
        # War participants table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS war_participants (
                user_id BIGINT,
                guild_id BIGINT,
                username TEXT,
                participation_status TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, guild_id)
            )
        """)
        
        # Join requests table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS join_requests (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                guild_id BIGINT,
                language TEXT DEFAULT 'ar',
                in_game_name TEXT,
                level INTEGER,
                power INTEGER,
                status TEXT DEFAULT 'pending',
                requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reviewed_by BIGINT,
                reviewed_at TIMESTAMP,
                rejection_reason TEXT,
                admin_message_id BIGINT
            )
        """)
        
        # User language preferences
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_language (
                user_id BIGINT,
                guild_id BIGINT,
                language TEXT DEFAULT 'ar',
                PRIMARY KEY (user_id, guild_id)
            )
        """)
        
        # Server settings
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS server_settings (
                guild_id BIGINT PRIMARY KEY,
                language TEXT DEFAULT 'ar',
                war_channel_id BIGINT,
                poll_day INTEGER DEFAULT 4,
                poll_time_hour INTEGER DEFAULT 20,
                poll_time_minute INTEGER DEFAULT 0,
                saturday_war_hour INTEGER DEFAULT 20,
                saturday_war_minute INTEGER DEFAULT 0,
                sunday_war_hour INTEGER DEFAULT 20,
                sunday_war_minute INTEGER DEFAULT 0,
                reminder_hours_before INTEGER DEFAULT 1,
                timezone TEXT DEFAULT 'Asia/Dubai'
            )
        """)
        
        # Server join settings
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS server_join_settings (
                guild_id BIGINT PRIMARY KEY,
                join_channel_id BIGINT NOT NULL,
                approval_channel_id BIGINT NOT NULL,
                min_power_requirement INTEGER DEFAULT 0,
                welcome_message_id BIGINT
            )
        """)
        
        # Sent events tracking
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sent_events (
                id SERIAL PRIMARY KEY,
                guild_id BIGINT,
                event_type TEXT,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        logger.info("✅ All tables created/verified")
    
    # ==================== PLAYER PROFILE OPERATIONS ====================
    
    def create_or_update_player(self, user_id: int, guild_id: int, 
                                in_game_name: str, mastery_points: int, 
                                level: int, build_type: str = None) -> bool:
        """Create or update player profile"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO players (user_id, guild_id, in_game_name, mastery_points, level, build_type, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT(user_id, guild_id) DO UPDATE SET
                        in_game_name = EXCLUDED.in_game_name,
                        mastery_points = EXCLUDED.mastery_points,
                        level = EXCLUDED.level,
                        build_type = COALESCE(EXCLUDED.build_type, players.build_type),
                        updated_at = CURRENT_TIMESTAMP
                """, (user_id, guild_id, in_game_name, mastery_points, level, build_type))
            return True
        except Exception as e:
            logger.error(f"Error creating/updating player: {e}")
            return False
    
    def get_player(self, user_id: int, guild_id: int) -> Optional[Dict]:
        """Get player profile"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor(cursor_factory=RealDictCursor)
                cursor.execute("""
                    SELECT * FROM players WHERE user_id = %s AND guild_id = %s
                """, (user_id, guild_id))
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error getting player: {e}")
            return None
    
    def get_all_players(self, guild_id: int) -> List[Dict]:
        """Get all players in a guild ordered by mastery points"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor(cursor_factory=RealDictCursor)
                cursor.execute("""
                    SELECT * FROM players 
                    WHERE guild_id = %s
                    ORDER BY mastery_points DESC
                """, (guild_id,))
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting all players: {e}")
            return []
    
    def update_player_build(self, user_id: int, guild_id: int, build_type: str) -> bool:
        """Update player's build type"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE players 
                    SET build_type = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = %s AND guild_id = %s
                """, (build_type, user_id, guild_id))
            return True
        except Exception as e:
            logger.error(f"Error updating player build: {e}")
            return False
    
    def delete_player(self, user_id: int, guild_id: int) -> bool:
        """Delete a player profile and all associated data"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                # Delete player (weapons will cascade)
                cursor.execute("""
                    DELETE FROM players WHERE user_id = %s AND guild_id = %s
                """, (user_id, guild_id))
                # Also delete from war participants
                cursor.execute("""
                    DELETE FROM war_participants WHERE user_id = %s AND guild_id = %s
                """, (user_id, guild_id))
                # Delete language preference
                cursor.execute("""
                    DELETE FROM user_language WHERE user_id = %s AND guild_id = %s
                """, (user_id, guild_id))
            return True
        except Exception as e:
            logger.error(f"Error deleting player: {e}")
            return False
    
    # ==================== WEAPON OPERATIONS ====================
    
    def add_weapon(self, user_id: int, guild_id: int, weapon_name: str) -> bool:
        """Add a weapon to player's inventory"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO player_weapons (user_id, guild_id, weapon_name)
                    VALUES (%s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, (user_id, guild_id, weapon_name))
            return True
        except Exception as e:
            logger.error(f"Error adding weapon: {e}")
            return False
    
    def get_player_weapons(self, user_id: int, guild_id: int) -> List[str]:
        """Get all weapons for a player"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT weapon_name FROM player_weapons 
                    WHERE user_id = %s AND guild_id = %s
                """, (user_id, guild_id))
                return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting player weapons: {e}")
            return []
    
    def set_player_weapons(self, user_id: int, guild_id: int, weapons: List[str]) -> bool:
        """Set weapons for a player (replaces existing weapons)"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                # Delete existing weapons
                cursor.execute("""
                    DELETE FROM player_weapons 
                    WHERE user_id = %s AND guild_id = %s
                """, (user_id, guild_id))
                
                # Insert new weapons
                for weapon in weapons:
                    cursor.execute("""
                        INSERT INTO player_weapons (user_id, guild_id, weapon_name)
                        VALUES (%s, %s, %s)
                    """, (user_id, guild_id, weapon))
            return True
        except Exception as e:
            logger.error(f"Error setting player weapons: {e}")
            return False
    
    def remove_weapon(self, user_id: int, guild_id: int, weapon_name: str) -> bool:
        """Remove a weapon from player's inventory"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    DELETE FROM player_weapons 
                    WHERE user_id = %s AND guild_id = %s AND weapon_name = %s
                """, (user_id, guild_id, weapon_name))
            return True
        except Exception as e:
            logger.error(f"Error removing weapon: {e}")
            return False
    
    # ==================== WAR OPERATIONS ====================
    
    def add_war_participant(self, user_id: int, guild_id: int, username: str, status: str) -> bool:
        """Add or update war participant"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO war_participants (user_id, guild_id, username, participation_status, timestamp)
                    VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT(user_id, guild_id) DO UPDATE SET
                        participation_status = EXCLUDED.participation_status,
                        timestamp = CURRENT_TIMESTAMP
                """, (user_id, guild_id, username, status))
            return True
        except Exception as e:
            logger.error(f"Error adding war participant: {e}")
            return False
    
    def get_war_participants(self, guild_id: int) -> List[Dict]:
        """Get all war participants for a guild"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor(cursor_factory=RealDictCursor)
                cursor.execute("""
                    SELECT * FROM war_participants 
                    WHERE guild_id = %s
                    ORDER BY timestamp DESC
                """, (guild_id,))
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting war participants: {e}")
            return []
    
    def get_war_participants_by_type(self, guild_id: int, poll_week: str = None) -> Dict:
        """Get war participants grouped by participation type"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor(cursor_factory=RealDictCursor)
                if poll_week:
                    cursor.execute("""
                        SELECT * FROM war_participants 
                        WHERE guild_id = %s AND poll_week = %s
                    """, (guild_id, poll_week))
                else:
                    cursor.execute("""
                        SELECT * FROM war_participants 
                        WHERE guild_id = %s
                    """, (guild_id,))
                rows = [dict(row) for row in cursor.fetchall()]
                result = {"saturday": [], "sunday": [], "both": [], "not_playing": []}
                for row in rows:
                    ptype = row.get("participation_type", "not_playing")
                    if ptype in result:
                        result[ptype].append(row)
                return result
        except Exception as e:
            logger.error(f"Error getting war participants by type: {e}")
            return {"saturday": [], "sunday": [], "both": [], "not_playing": []}
    
    def set_war_participation(self, user_id: int, guild_id: int, poll_week: str, participation_type: str) -> bool:
        """Set a user's war participation choice"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO war_participants (user_id, guild_id, poll_week, participation_type)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (user_id, guild_id, poll_week) DO UPDATE SET
                        participation_type = EXCLUDED.participation_type,
                        timestamp = CURRENT_TIMESTAMP
                """, (user_id, guild_id, poll_week, participation_type))
            return True
        except Exception as e:
            logger.error(f"Error setting war participation: {e}")
            return False
    
    def clear_war_participants(self, guild_id: int, poll_week: str) -> bool:
        """Clear war participants for a specific poll week"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    DELETE FROM war_participants 
                    WHERE guild_id = %s AND poll_week = %s
                """, (guild_id, poll_week))
            return True
        except Exception as e:
            logger.error(f"Error clearing war participants: {e}")
            return False
    
    def clear_all_war_participants(self, guild_id: int) -> bool:
        """Clear all war participants for a guild"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    DELETE FROM war_participants WHERE guild_id = %s
                """, (guild_id,))
            return True
        except Exception as e:
            logger.error(f"Error clearing all war participants: {e}")
            return False
    
    def was_event_sent(self, guild_id: int, event_type: str, poll_week: str, day: str = None) -> bool:
        """Check if an event notification was already sent"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                if day:
                    cursor.execute("""
                        SELECT 1 FROM sent_events 
                        WHERE guild_id = %s AND event_type = %s AND poll_week = %s AND day = %s
                    """, (guild_id, event_type, poll_week, day))
                else:
                    cursor.execute("""
                        SELECT 1 FROM sent_events 
                        WHERE guild_id = %s AND event_type = %s AND poll_week = %s
                    """, (guild_id, event_type, poll_week))
                return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"Error checking event sent: {e}")
            return False
    
    def mark_event_sent(self, guild_id: int, event_type: str, poll_week: str, day: str = None) -> bool:
        """Mark an event notification as sent"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO sent_events (guild_id, event_type, poll_week, day)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, (guild_id, event_type, poll_week, day))
            return True
        except Exception as e:
            logger.error(f"Error marking event sent: {e}")
            return False
    
    def reset_war_data(self, guild_id: int) -> bool:
        """Reset all war participation data for a guild"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    DELETE FROM war_participants WHERE guild_id = %s
                """, (guild_id,))
            return True
        except Exception as e:
            logger.error(f"Error resetting war data: {e}")
            return False
    
    # ==================== LANGUAGE OPERATIONS ====================
    
    def set_user_language(self, user_id: int, guild_id: int, language: str) -> bool:
        """Set user's language preference"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO user_language (user_id, guild_id, language)
                    VALUES (%s, %s, %s)
                    ON CONFLICT(user_id, guild_id) DO UPDATE SET
                        language = EXCLUDED.language
                """, (user_id, guild_id, language))
            return True
        except Exception as e:
            logger.error(f"Error setting user language: {e}")
            return False
    
    def get_user_language(self, user_id: int, guild_id: int) -> str:
        """Get user's language preference"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT language FROM user_language WHERE user_id = %s AND guild_id = %s
                """, (user_id, guild_id))
                row = cursor.fetchone()
                return row[0] if row else 'ar'
        except Exception as e:
            logger.error(f"Error getting user language: {e}")
            return 'ar'
    
    def has_language_preference(self, user_id: int, guild_id: int) -> bool:
        """Check if user has a language preference set"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT 1 FROM user_language WHERE user_id = %s AND guild_id = %s
                """, (user_id, guild_id))
                return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"Error checking user language: {e}")
            return False
    
    # Alias for backward compatibility
    def has_user_chosen_language(self, user_id: int, guild_id: int) -> bool:
        """Alias for has_language_preference (backward compatibility)"""
        return self.has_language_preference(user_id, guild_id)
    
    # ==================== SERVER SETTINGS OPERATIONS ====================
    
    def get_server_settings(self, guild_id: int) -> Dict:
        """Get server settings"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor(cursor_factory=RealDictCursor)
                cursor.execute("""
                    SELECT * FROM server_settings WHERE guild_id = %s
                """, (guild_id,))
                row = cursor.fetchone()
                
                if row:
                    return dict(row)
                else:
                    # Create default settings
                    cursor.execute("""
                        INSERT INTO server_settings (guild_id) VALUES (%s)
                    """, (guild_id,))
            # Recursively get the newly created settings
            return self.get_server_settings(guild_id)
        except Exception as e:
            logger.error(f"Error getting server settings: {e}")
            return {}
    
    def update_server_setting(self, guild_id: int, setting_name: str, value) -> bool:
        """Update a specific server setting"""
        if setting_name not in ALLOWED_SETTINGS:
            logger.error(f"Invalid setting name: {setting_name}")
            return False
        
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                # Ensure server settings exist
                cursor.execute("""
                    INSERT INTO server_settings (guild_id) 
                    VALUES (%s)
                    ON CONFLICT (guild_id) DO NOTHING
                """, (guild_id,))
                
                # Update the specific setting
                cursor.execute(f"""
                    UPDATE server_settings 
                    SET {setting_name} = %s
                    WHERE guild_id = %s
                """, (value, guild_id))
            return True
        except Exception as e:
            logger.error(f"Error updating server setting: {e}")
            return False
    
    # ==================== EVENT TRACKING OPERATIONS ====================
    
    def record_sent_event(self, guild_id: int, event_type: str) -> bool:
        """Record that an event was sent"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO sent_events (guild_id, event_type, sent_at)
                    VALUES (%s, %s, CURRENT_TIMESTAMP)
                """, (guild_id, event_type))
            return True
        except Exception as e:
            logger.error(f"Error recording sent event: {e}")
            return False
    
    def clear_old_events(self, guild_id: int, older_than_date: datetime) -> bool:
        """Clear old event tracking data for a specific guild"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    DELETE FROM sent_events 
                    WHERE guild_id = %s AND sent_at < %s
                """, (guild_id, older_than_date.strftime("%Y-%m-%d %H:%M:%S")))
            return True
        except Exception as e:
            logger.error(f"Error clearing old events for guild {guild_id}: {e}")
            return False
    
    # ==================== JOIN REQUEST OPERATIONS ====================
    
    def set_min_power_requirement(self, guild_id: int, power: int) -> bool:
        """Set the minimum power requirement for joining"""
        return self.update_join_settings(guild_id, min_power_requirement=power)
    
    def create_join_request(self, user_id: int, guild_id: int, language: str, 
                           in_game_name: str, level: int, power: int) -> Optional[int]:
        """Create a new join request"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO join_requests (user_id, guild_id, language, in_game_name, level, power)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (user_id, guild_id, language, in_game_name, level, power))
                return cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"Error creating join request: {e}")
            return None
    
    def get_join_request(self, request_id: int) -> Optional[Dict]:
        """Get a specific join request"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor(cursor_factory=RealDictCursor)
                cursor.execute("""
                    SELECT * FROM join_requests WHERE id = %s
                """, (request_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error getting join request: {e}")
            return None
    
    def get_pending_join_requests(self, guild_id: int) -> List[Dict]:
        """Get all pending join requests for a guild"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor(cursor_factory=RealDictCursor)
                cursor.execute("""
                    SELECT * FROM join_requests 
                    WHERE guild_id = %s AND status = 'pending'
                    ORDER BY requested_at DESC
                """, (guild_id,))
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting pending join requests: {e}")
            return []
    
    def update_join_request_status(self, request_id: int, status: str, reviewed_by: int) -> bool:
        """Update join request status"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE join_requests 
                    SET status = %s, reviewed_at = CURRENT_TIMESTAMP, reviewed_by = %s
                    WHERE id = %s
                """, (status, reviewed_by, request_id))
            return True
        except Exception as e:
            logger.error(f"Error updating join request status: {e}")
            return False
    
    def set_join_settings(self, guild_id: int, join_channel_id: int, 
                         approval_channel_id: int, min_power: int) -> bool:
        """Set or update join system settings"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO server_join_settings 
                    (guild_id, join_channel_id, approval_channel_id, min_power_requirement)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT(guild_id) DO UPDATE SET
                        join_channel_id = EXCLUDED.join_channel_id,
                        approval_channel_id = EXCLUDED.approval_channel_id,
                        min_power_requirement = EXCLUDED.min_power_requirement
                """, (guild_id, join_channel_id, approval_channel_id, min_power))
            return True
        except Exception as e:
            logger.error(f"Error updating join settings: {e}")
            return False
    
    def get_join_settings(self, guild_id: int) -> Optional[Dict]:
        """Get join system settings for a guild"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor(cursor_factory=RealDictCursor)
                cursor.execute("""
                    SELECT * FROM server_join_settings 
                    WHERE guild_id = %s
                """, (guild_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error getting join settings: {e}")
            return None
    
    def update_join_settings(self, guild_id: int, join_channel_id: int = None, 
                            admin_review_channel_id: int = None, build_setup_channel_id: int = None,
                            min_power_requirement: int = None) -> bool:
        """Update join system settings for a guild"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                # Check if settings exist
                cursor.execute("""
                    SELECT 1 FROM server_join_settings WHERE guild_id = %s
                """, (guild_id,))
                exists = cursor.fetchone() is not None
                
                if exists:
                    # Update existing settings
                    updates = []
                    params = []
                    if join_channel_id is not None:
                        updates.append("join_channel_id = %s")
                        params.append(join_channel_id)
                    if admin_review_channel_id is not None:
                        updates.append("admin_review_channel_id = %s")
                        params.append(admin_review_channel_id)
                    if build_setup_channel_id is not None:
                        updates.append("build_setup_channel_id = %s")
                        params.append(build_setup_channel_id)
                    if min_power_requirement is not None:
                        updates.append("min_power_requirement = %s")
                        params.append(min_power_requirement)
                    
                    if updates:
                        params.append(guild_id)
                        cursor.execute(f"""
                            UPDATE server_join_settings 
                            SET {', '.join(updates)}
                            WHERE guild_id = %s
                        """, params)
                else:
                    # Insert new settings
                    cursor.execute("""
                        INSERT INTO server_join_settings 
                        (guild_id, join_channel_id, admin_review_channel_id, build_setup_channel_id, min_power_requirement)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (guild_id, join_channel_id, admin_review_channel_id, build_setup_channel_id, min_power_requirement or 0))
            return True
        except Exception as e:
            logger.error(f"Error updating join settings: {e}")
            return False
    
    def set_welcome_message_id(self, guild_id: int, message_id: int) -> bool:
        """Set the welcome message ID for a guild"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE server_join_settings 
                    SET welcome_message_id = %s
                    WHERE guild_id = %s
                """, (message_id, guild_id))
            return True
        except Exception as e:
            logger.error(f"Error setting welcome message ID: {e}")
            return False
