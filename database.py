import sqlite3
import logging
import os
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Tuple
import json
from contextlib import contextmanager
from urllib.parse import urlparse

# Try to import PostgreSQL support
try:
    import psycopg2
    from psycopg2 import pool
    from psycopg2.extras import RealDictCursor
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False

logger = logging.getLogger(__name__)

# Whitelist of allowed server settings to prevent SQL injection
ALLOWED_SETTINGS = {
    'language', 'war_channel_id', 'poll_day', 'poll_time_hour', 'poll_time_minute',
    'saturday_war_hour', 'saturday_war_minute', 'sunday_war_hour', 'sunday_war_minute',
    'reminder_hours_before', 'timezone'
}

class CursorWrapper:
    """Wrapper for PostgreSQL cursor that automatically adapts ? to $1, $2, etc."""
    def __init__(self, cursor, database):
        self.cursor = cursor
        self.database = database
    
    def execute(self, sql, params=()):
        """Execute with automatic parameter adaptation"""
        # Ensure params is a tuple
        if params is None:
            params = ()
        elif not isinstance(params, (tuple, list)):
            params = (params,)
        
        adapted_sql, adapted_params = self.database._adapt_params(sql, params)
        
        # Debug logging
        if self.database.db_type == 'postgresql':
            logger.debug(f"Executing SQL with {len(adapted_params)} params")
            logger.debug(f"SQL: {adapted_sql[:100]}...")
            logger.debug(f"Params type: {type(adapted_params)}, Params: {adapted_params}")
        
        return self.cursor.execute(adapted_sql, adapted_params)
    
    def fetchone(self):
        return self.cursor.fetchone()
    
    def fetchall(self):
        return self.cursor.fetchall()
    
    @property
    def rowcount(self):
        return self.cursor.rowcount
    
    @property
    def lastrowid(self):
        return self.cursor.lastrowid
    
    def __getattr__(self, name):
        """Delegate all other attributes to the wrapped cursor"""
        return getattr(self.cursor, name)


class Database:
    def __init__(self, db_path: str = "bot_data.db"):
        """Initialize database connection"""
        # Check for DATABASE_URL environment variable (PostgreSQL)
        self.database_url = os.getenv('DATABASE_URL')
        
        if self.database_url:
            # Use PostgreSQL
            if not POSTGRES_AVAILABLE:
                raise ImportError(
                    "PostgreSQL support not available. Install psycopg2-binary: "
                    "pip install psycopg2-binary"
                )
            self.db_type = 'postgresql'
            self.db_path = None
            self._init_postgres_pool()
            logger.info("🐘 Using PostgreSQL database")
        else:
            # Use SQLite (local development)
            self.db_type = 'sqlite'
            self.db_path = db_path
            self.connection_pool = None
            logger.info(f"📁 Using SQLite database: {db_path}")
        
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
        """Get a database connection with automatic commit/rollback and cleanup"""
        if self.db_type == 'postgresql':
            conn = self.connection_pool.getconn()
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                self.connection_pool.putconn(conn)
        else:
            # SQLite
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()
    
    def _get_cursor(self, conn):
        """Get a cursor with appropriate row factory for the database type"""
        if self.db_type == 'postgresql':
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            # Wrap the cursor to automatically adapt parameters
            return CursorWrapper(cursor, self)
        else:
            return conn.cursor()
    
    def _adapt_sql(self, sql: str) -> str:
        """Adapt SQL syntax for the current database type"""
        if self.db_type == 'postgresql':
            # Replace SQLite-specific syntax with PostgreSQL equivalents
            sql = sql.replace('INTEGER PRIMARY KEY AUTOINCREMENT', 'SERIAL PRIMARY KEY')
            sql = sql.replace('AUTOINCREMENT', '')
            # Replace ? placeholders with $1, $2, etc. for PostgreSQL
            # This is handled in execute methods
            return sql
        return sql
    
    def _adapt_params(self, sql: str, params: tuple) -> tuple:
        """Adapt SQL parameters for the current database type"""
        if self.db_type == 'postgresql':
            # Convert ? placeholders to $1, $2, etc.
            # Use a more robust approach that handles strings correctly
            import re
            
            # Track position in params
            param_index = [0]
            
            def replace_placeholder(match):
                param_index[0] += 1
                return f'${param_index[0]}'
            
            # Replace ? with $1, $2, etc., but avoid replacing inside strings
            # This regex matches ? that are not inside single or double quotes
            adapted_sql = re.sub(r'\?', replace_placeholder, sql)
            
            return adapted_sql, params
        return sql, params
    
    def _execute(self, cursor, sql: str, params: tuple = ()):
        """Execute a query with automatic parameter adaptation"""
        adapted_sql, adapted_params = self._adapt_params(sql, params)
        return cursor.execute(adapted_sql, adapted_params)
    
    def init_database(self):
        """Initialize database and create tables"""
        try:
            with self.get_connection() as conn:
                cursor = self._get_cursor(conn)
                self.create_tables_with_cursor(cursor)
            db_info = self.database_url.split('@')[1] if self.database_url else self.db_path
            logger.info(f"✅ Database initialized: {db_info}")
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            raise
    
    def create_tables_with_cursor(self, cursor):
        """Create all necessary tables"""
        # Auto-increment syntax differs between SQLite and PostgreSQL
        autoincrement = '' if self.db_type == 'postgresql' else 'AUTOINCREMENT'
        serial_type = 'SERIAL' if self.db_type == 'postgresql' else 'INTEGER'
        
        # Players table
        cursor.execute(f"""
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
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS player_weapons (
                id {serial_type} PRIMARY KEY,
                user_id BIGINT,
                guild_id BIGINT,
                weapon_name TEXT,
                UNIQUE(user_id, guild_id, weapon_name)
            )
        """)
        
        # War participants table
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS war_participants (
                id {serial_type} PRIMARY KEY,
                user_id BIGINT,
                guild_id BIGINT,
                poll_week TEXT,
                participation_type TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, guild_id, poll_week)
            )
        """)
        
        # Server settings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS server_settings (
                guild_id BIGINT PRIMARY KEY,
                language TEXT DEFAULT 'en',
                war_channel_id BIGINT,
                poll_day TEXT DEFAULT 'Friday',
                poll_time_hour INTEGER DEFAULT 15,
                poll_time_minute INTEGER DEFAULT 0,
                saturday_war_hour INTEGER DEFAULT 22,
                saturday_war_minute INTEGER DEFAULT 30,
                sunday_war_hour INTEGER DEFAULT 22,
                sunday_war_minute INTEGER DEFAULT 30,
                reminder_hours_before INTEGER DEFAULT 2,
                timezone TEXT DEFAULT 'Africa/Cairo'
            )
        """)
        
        # Sent events tracking table
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS sent_events (
                id {serial_type} PRIMARY KEY,
                guild_id BIGINT,
                event_type TEXT,
                event_week TEXT,
                event_day TEXT,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(guild_id, event_type, event_week, event_day)
            )
        """)
        
        # Join requests table
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS join_requests (
                id {serial_type} PRIMARY KEY,
                user_id BIGINT NOT NULL,
                guild_id BIGINT NOT NULL,
                language TEXT DEFAULT 'en',
                in_game_name TEXT NOT NULL,
                level INTEGER NOT NULL,
                power INTEGER NOT NULL,
                status TEXT DEFAULT 'pending',
                requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reviewed_by BIGINT,
                reviewed_at TIMESTAMP,
                rejection_reason TEXT,
                admin_message_id BIGINT
            )
        """)
        
        # Server join settings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS server_join_settings (
                guild_id BIGINT PRIMARY KEY,
                join_channel_id BIGINT,
                admin_review_channel_id BIGINT,
                build_setup_channel_id BIGINT,
                min_power_requirement INTEGER DEFAULT 0,
                welcome_message_id BIGINT
            )
        """)
        
        # Per-user language preference (defaults to 'en' if not set)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_language (
                user_id BIGINT,
                guild_id BIGINT,
                language TEXT NOT NULL DEFAULT 'en',
                PRIMARY KEY (user_id, guild_id)
            )
        """)
        
        logger.info("✅ Database tables created")
    
    def create_tables(self):
        """Create all necessary tables - wrapper for backwards compatibility"""
        with self.get_connection() as conn:
            cursor = self._get_cursor(conn)
            self.create_tables_with_cursor(cursor)
    
    # ==================== PLAYER PROFILE OPERATIONS ====================
    
    def create_or_update_player(self, user_id: int, guild_id: int, 
                                in_game_name: str, mastery_points: int, 
                                level: int, build_type: str = None) -> bool:
        """Create or update player profile"""
        try:
            with self.get_connection() as conn:
                cursor = self._get_cursor(conn)
                cursor.execute("""
                    INSERT INTO players (user_id, guild_id, in_game_name, mastery_points, level, build_type, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(user_id, guild_id) DO UPDATE SET
                        in_game_name = excluded.in_game_name,
                        mastery_points = excluded.mastery_points,
                        level = excluded.level,
                        build_type = COALESCE(excluded.build_type, build_type),
                        updated_at = CURRENT_TIMESTAMP
                """, (user_id, guild_id, in_game_name, mastery_points, level, build_type))
                
                # Verify the insert
                cursor.execute("SELECT * FROM players WHERE user_id = ? AND guild_id = ?", (user_id, guild_id))
                result = cursor.fetchone()
                
            return result is not None
        except Exception as e:
            logger.error(f"Error creating/updating player: {e}", exc_info=True)
            return False
    
    def update_player_stats(self, user_id: int, guild_id: int, 
                           mastery_points: int = None, level: int = None) -> bool:
        """Update only player stats (mastery/level)"""
        try:
            updates = []
            params = []
            
            if mastery_points is not None:
                updates.append("mastery_points = ?")
                params.append(mastery_points)
            
            if level is not None:
                updates.append("level = ?")
                params.append(level)
            
            if not updates:
                return False
            
            updates.append("updated_at = CURRENT_TIMESTAMP")
            params.extend([user_id, guild_id])
            
            query = f"UPDATE players SET {', '.join(updates)} WHERE user_id = ? AND guild_id = ?"
            
            with self.get_connection() as conn:
                cursor = self._get_cursor(conn)
                cursor.execute(query, params)
                result = cursor.rowcount > 0
            return result
        except Exception as e:
            logger.error(f"Error updating player stats: {e}")
            return False
    
    def get_player(self, user_id: int, guild_id: int) -> Optional[Dict]:
        """Get player profile"""
        try:
            with self.get_connection() as conn:
                cursor = self._get_cursor(conn)
                cursor.execute("""
                    SELECT * FROM players WHERE user_id = ? AND guild_id = ?
                """, (user_id, guild_id))
                row = cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error getting player: {e}")
            return None
            
    def get_all_players(self, guild_id: int) -> Dict[int, Dict]:
        """Get all players for a guild as a dictionary keyed by user_id"""
        try:
            with self.get_connection() as conn:
                cursor = self._get_cursor(conn)
                cursor.execute("""
                    SELECT * FROM players WHERE guild_id = ?
                """, (guild_id,))
                rows = cursor.fetchall()
            return {row['user_id']: dict(row) for row in rows}
        except Exception as e:
            logger.error(f"Error getting all players: {e}")
            return {}
    
    def get_leaderboard(self, guild_id: int, order_by: str = "mastery_points", 
                       limit: int = 10) -> List[Dict]:
        """Get leaderboard rankings"""
        try:
            # Whitelist validation for ORDER BY
            if order_by not in ["mastery_points", "level"]:
                order_by = "mastery_points"
            
            with self.get_connection() as conn:
                cursor = self._get_cursor(conn)
                cursor.execute(f"""
                    SELECT user_id, in_game_name, mastery_points, level, build_type,
                           ROW_NUMBER() OVER (ORDER BY {order_by} DESC, in_game_name ASC) as rank
                    FROM players
                    WHERE guild_id = ? AND in_game_name IS NOT NULL
                    ORDER BY {order_by} DESC, in_game_name ASC
                    LIMIT ?
                """, (guild_id, limit))
                rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error getting leaderboard: {e}")
            return []
    
    def get_player_rank(self, user_id: int, guild_id: int, 
                       order_by: str = "mastery_points") -> Optional[int]:
        """Get player's rank in the server"""
        try:
            # Whitelist validation for ORDER BY
            if order_by not in ["mastery_points", "level"]:
                order_by = "mastery_points"
            
            with self.get_connection() as conn:
                cursor = self._get_cursor(conn)
                cursor.execute(f"""
                    SELECT rank FROM (
                        SELECT user_id,
                               ROW_NUMBER() OVER (ORDER BY {order_by} DESC, in_game_name ASC) as rank
                        FROM players
                        WHERE guild_id = ? AND in_game_name IS NOT NULL
                    )
                    WHERE user_id = ?
                """, (guild_id, user_id))
                row = cursor.fetchone()
            return row['rank'] if row else None
        except Exception as e:
            logger.error(f"Error getting player rank: {e}")
            return None
    
    def update_player_build(self, user_id: int, guild_id: int, build_type: str) -> bool:
        """Update player's build type"""
        try:
            with self.get_connection() as conn:
                cursor = self._get_cursor(conn)
                cursor.execute("""
                    UPDATE players SET build_type = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = ? AND guild_id = ?
                """, (build_type, user_id, guild_id))
                result = cursor.rowcount > 0
            return result
        except Exception as e:
            logger.error(f"Error updating player build: {e}")
            return False
    
    def delete_player(self, user_id: int, guild_id: int) -> bool:
        """Delete a player profile and all related data (weapons, war participation, language) for this guild"""
        try:
            with self.get_connection() as conn:
                cursor = self._get_cursor(conn)
                
                # Delete related data first
                cursor.execute("DELETE FROM player_weapons WHERE user_id = ? AND guild_id = ?", (user_id, guild_id))
                
                cursor.execute("DELETE FROM war_participants WHERE user_id = ? AND guild_id = ?", (user_id, guild_id))
                
                cursor.execute("DELETE FROM user_language WHERE user_id = ? AND guild_id = ?", (user_id, guild_id))
                
                # Delete join requests (so they can request again)
                cursor.execute("DELETE FROM join_requests WHERE user_id = ? AND guild_id = ?", (user_id, guild_id))
                
                # Delete player record
                cursor.execute("DELETE FROM players WHERE user_id = ? AND guild_id = ?", (user_id, guild_id))
                
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error deleting player: {e}", exc_info=True)
            return False
    
    # ==================== WEAPON OPERATIONS ====================
    
    def set_player_weapons(self, user_id: int, guild_id: int, weapons: List[str]) -> bool:
        """Set player's weapons (replaces existing)"""
        try:
            with self.get_connection() as conn:
                cursor = self._get_cursor(conn)
                
                # Delete existing weapons
                cursor.execute("""
                    DELETE FROM player_weapons WHERE user_id = ? AND guild_id = ?
                """, (user_id, guild_id))
                
                # Insert new weapons
                for weapon in weapons:
                    cursor.execute("""
                        INSERT INTO player_weapons (user_id, guild_id, weapon_name)
                        VALUES (?, ?, ?)
                    """, (user_id, guild_id, weapon))
            return True
        except Exception as e:
            logger.error(f"Error setting player weapons: {e}")
            return False
    
    def get_player_weapons(self, user_id: int, guild_id: int) -> List[str]:
        """Get player's weapons"""
        try:
            with self.get_connection() as conn:
                cursor = self._get_cursor(conn)
                cursor.execute("""
                    SELECT weapon_name FROM player_weapons
                    WHERE user_id = ? AND guild_id = ?
                """, (user_id, guild_id))
                weapons = [row['weapon_name'] for row in cursor.fetchall()]
            return weapons
        except Exception as e:
            logger.error(f"Error getting player weapons: {e}")
            return []
    
    def get_all_player_weapons(self, guild_id: int) -> Dict[int, List[str]]:
        """Get all players' weapons for a guild"""
        try:
            with self.get_connection() as conn:
                cursor = self._get_cursor(conn)
                cursor.execute("""
                    SELECT user_id, weapon_name FROM player_weapons
                    WHERE guild_id = ?
                """, (guild_id,))
                
                weapons_dict = {}
                for row in cursor.fetchall():
                    user_id = row['user_id']
                    if user_id not in weapons_dict:
                        weapons_dict[user_id] = []
                    weapons_dict[user_id].append(row['weapon_name'])
            return weapons_dict
        except Exception as e:
            logger.error(f"Error getting all player weapons: {e}")
            return {}
    
    # ==================== WAR OPERATIONS ====================
    
    def set_war_participation(self, user_id: int, guild_id: int, 
                             poll_week: str, participation_type: str) -> bool:
        """Set war participation for current week"""
        try:
            with self.get_connection() as conn:
                cursor = self._get_cursor(conn)
                
                # Delete existing participation for this week
                cursor.execute("""
                    DELETE FROM war_participants 
                    WHERE user_id = ? AND guild_id = ? AND poll_week = ?
                """, (user_id, guild_id, poll_week))
                
                # Insert new participation
                cursor.execute("""
                    INSERT INTO war_participants (user_id, guild_id, poll_week, participation_type)
                    VALUES (?, ?, ?, ?)
                """, (user_id, guild_id, poll_week, participation_type))
            return True
        except Exception as e:
            logger.error(f"Error setting war participation: {e}")
            return False
    
    def get_war_participants(self, guild_id: int, poll_week: str, 
                            participation_type: str = None) -> List[int]:
        """Get war participants for a week"""
        try:
            with self.get_connection() as conn:
                cursor = self._get_cursor(conn)
                
                if participation_type:
                    cursor.execute("""
                        SELECT user_id FROM war_participants
                        WHERE guild_id = ? AND poll_week = ? AND participation_type = ?
                    """, (guild_id, poll_week, participation_type))
                else:
                    cursor.execute("""
                        SELECT user_id, participation_type FROM war_participants
                        WHERE guild_id = ? AND poll_week = ?
                    """, (guild_id, poll_week))
                
                rows = cursor.fetchall()
            return [row['user_id'] for row in rows]
        except Exception as e:
            logger.error(f"Error getting war participants: {e}")
            return []
    
    def get_war_participants_by_type(self, guild_id: int, poll_week: str) -> Dict[str, List[int]]:
        """Get war participants organized by participation type"""
        try:
            with self.get_connection() as conn:
                cursor = self._get_cursor(conn)
                
                cursor.execute("""
                    SELECT user_id, participation_type FROM war_participants
                    WHERE guild_id = ? AND poll_week = ?
                """, (guild_id, poll_week))
                
                result = {
                    "saturday": [],
                    "sunday": [],
                    "both": [],
                    "not_playing": []
                }
                
                for row in cursor.fetchall():
                    user_id = row['user_id']
                    participation_type = row['participation_type']
                    if participation_type in result:
                        result[participation_type].append(user_id)
            return result
        except Exception as e:
            logger.error(f"Error getting war participants by type: {e}")
            return {"saturday": [], "sunday": [], "both": [], "not_playing": []}
    
    def clear_war_participants(self, guild_id: int, poll_week: str) -> bool:
        """Clear all war participants for a week"""
        try:
            with self.get_connection() as conn:
                cursor = self._get_cursor(conn)
                cursor.execute("""
                    DELETE FROM war_participants WHERE guild_id = ? AND poll_week = ?
                """, (guild_id, poll_week))
            return True
        except Exception as e:
            logger.error(f"Error clearing war participants: {e}")
            return False
    
    def clear_all_war_participants(self, guild_id: int) -> bool:
        """Clear ALL war participants for a guild"""
        try:
            with self.get_connection() as conn:
                cursor = self._get_cursor(conn)
                cursor.execute("""
                    DELETE FROM war_participants WHERE guild_id = ?
                """, (guild_id,))
            return True
        except Exception as e:
            logger.error(f"Error clearing all war participants: {e}")
            return False
    
    # ==================== SERVER SETTINGS OPERATIONS ====================
    
    def get_server_settings(self, guild_id: int) -> Dict:
        """Get server settings"""
        try:
            with self.get_connection() as conn:
                cursor = self._get_cursor(conn)
                cursor.execute("""
                    SELECT * FROM server_settings WHERE guild_id = ?
                """, (guild_id,))
                row = cursor.fetchone()
                
                if row:
                    return dict(row)
                else:
                    # Create default settings
                    cursor.execute("""
                        INSERT INTO server_settings (guild_id) VALUES (?)
                    """, (guild_id,))
            # Recursively get the newly created settings
            return self.get_server_settings(guild_id)
        except Exception as e:
            logger.error(f"Error getting server settings: {e}")
            return {}
    
    def update_server_setting(self, guild_id: int, setting: str, value) -> bool:
        """Update a specific server setting"""
        # Validate setting name against whitelist to prevent SQL injection
        if setting not in ALLOWED_SETTINGS:
            logger.warning(f"Rejected unknown setting: {setting}")
            return False
        
        try:
            with self.get_connection() as conn:
                cursor = self._get_cursor(conn)
                
                # Ensure server settings exist
                cursor.execute("""
                    INSERT OR IGNORE INTO server_settings (guild_id) VALUES (?)
                """, (guild_id,))
                
                # Update the setting - safe because setting is validated against whitelist
                cursor.execute(f"""
                    UPDATE server_settings SET {setting} = ? WHERE guild_id = ?
                """, (value, guild_id))
            return True
        except Exception as e:
            logger.error(f"Error updating server setting: {e}")
            return False
    
    # ==================== USER LANGUAGE (per-user preference) ====================
    
    def get_user_language(self, user_id: int, guild_id: int) -> str:
        """Get user's language preference for this guild. Returns 'en' if not set."""
        try:
            with self.get_connection() as conn:
                cursor = self._get_cursor(conn)
                cursor.execute("""
                    SELECT language FROM user_language WHERE user_id = ? AND guild_id = ?
                """, (user_id, guild_id))
                row = cursor.fetchone()
            return row['language'] if row else 'en'
        except Exception as e:
            logger.error(f"Error getting user language: {e}")
            return 'en'

    def has_user_chosen_language(self, user_id: int, guild_id: int) -> bool:
        """True if the user has explicitly chosen a language (English or Arabic) for this guild."""
        try:
            with self.get_connection() as conn:
                cursor = self._get_cursor(conn)
                cursor.execute("""
                    SELECT 1 FROM user_language WHERE user_id = ? AND guild_id = ?
                """, (user_id, guild_id))
                row = cursor.fetchone()
            return row is not None
        except Exception as e:
            logger.error(f"Error checking user language: {e}")
            return False
    
    def set_user_language(self, user_id: int, guild_id: int, language: str) -> bool:
        """Set user's language preference for this guild (e.g. 'en' or 'ar')."""
        try:
            if language not in ('en', 'ar'):
                language = 'en'
            with self.get_connection() as conn:
                cursor = self._get_cursor(conn)
                cursor.execute("""
                    INSERT INTO user_language (user_id, guild_id, language)
                    VALUES (?, ?, ?)
                    ON CONFLICT(user_id, guild_id) DO UPDATE SET language = excluded.language
                """, (user_id, guild_id, language))
            return True
        except Exception as e:
            logger.error(f"Error setting user language: {e}")
            return False
    
    # ==================== MIGRATION OPERATIONS ====================
    
    def migrate_from_json(self, language_file: Path, war_data_file: Path) -> bool:
        """Migrate data from JSON files to database"""
        try:
            # Migrate language data
            if language_file.exists():
                with open(language_file, 'r', encoding='utf-8') as f:
                    language_data = json.load(f)
                    for guild_id, lang in language_data.items():
                        self.update_server_setting(int(guild_id), 'language', lang)
                logger.info("✅ Migrated language data")
            
            # Migrate war data
            if war_data_file.exists():
                with open(war_data_file, 'r') as f:
                    war_data = json.load(f)
                    
                    # Migrate war config
                    if 'config' in war_data:
                        config = war_data['config']
                        # This will be handled by the main bot code
                        logger.info("✅ War config found in JSON")
            
            return True
        except Exception as e:
            logger.error(f"Error migrating from JSON: {e}")
            return False
    
    # ==================== EVENT TRACKING OPERATIONS ====================
    
    def was_event_sent(self, guild_id: int, event_type: str, 
                      event_week: str, event_day: str = None) -> bool:
        """Check if an event was already sent this week/day"""
        try:
            with self.get_connection() as conn:
                cursor = self._get_cursor(conn)
                if event_day:
                    cursor.execute("""
                        SELECT COUNT(*) as count FROM sent_events
                        WHERE guild_id = ? AND event_type = ? AND event_week = ? AND event_day = ?
                    """, (guild_id, event_type, event_week, event_day))
                else:
                    cursor.execute("""
                        SELECT COUNT(*) as count FROM sent_events
                        WHERE guild_id = ? AND event_type = ? AND event_week = ?
                    """, (guild_id, event_type, event_week))
                
                result = cursor.fetchone()
            return result['count'] > 0
        except Exception as e:
            logger.error(f"Error checking event sent: {e}")
            return False
    
    def mark_event_sent(self, guild_id: int, event_type: str, 
                       event_week: str, event_day: str = None) -> bool:
        """Mark an event as sent"""
        try:
            with self.get_connection() as conn:
                cursor = self._get_cursor(conn)
                # Use proper UPSERT instead of REPLACE to avoid changing row IDs
                cursor.execute("""
                    INSERT INTO sent_events (guild_id, event_type, event_week, event_day, sent_at)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(guild_id, event_type, event_week, event_day) 
                    DO UPDATE SET sent_at = CURRENT_TIMESTAMP
                """, (guild_id, event_type, event_week, event_day))
            return True
        except Exception as e:
            logger.error(f"Error marking event sent: {e}")
            return False
    
    def clear_old_events(self, guild_id: int, older_than_date: datetime) -> bool:
        """Clear old event tracking data for a specific guild"""
        try:
            with self.get_connection() as conn:
                cursor = self._get_cursor(conn)
                cursor.execute("""
                    DELETE FROM sent_events 
                    WHERE guild_id = ? AND sent_at < ?
                """, (guild_id, older_than_date.strftime("%Y-%m-%d %H:%M:%S")))
            return True
        except Exception as e:
            logger.error(f"Error clearing old events for guild {guild_id}: {e}")
            return False
    
    # ==================== JOIN REQUEST OPERATIONS ====================
    
    def update_join_settings(self, guild_id: int, join_channel_id: int, admin_review_channel_id: int, build_setup_channel_id: int = None):
        """Update join request settings for a guild"""
        try:
            with self.get_connection() as conn:
                cursor = self._get_cursor(conn)
                cursor.execute("""
                    INSERT INTO server_join_settings 
                    (guild_id, join_channel_id, admin_review_channel_id, build_setup_channel_id, min_power_requirement, welcome_message_id)
                    VALUES (?, ?, ?, ?, 
                        COALESCE((SELECT min_power_requirement FROM server_join_settings WHERE guild_id = ?), 0),
                        (SELECT welcome_message_id FROM server_join_settings WHERE guild_id = ?))
                    ON CONFLICT(guild_id) DO UPDATE SET
                        join_channel_id = excluded.join_channel_id,
                        admin_review_channel_id = excluded.admin_review_channel_id,
                        build_setup_channel_id = excluded.build_setup_channel_id
                """, (guild_id, join_channel_id, admin_review_channel_id, build_setup_channel_id, guild_id, guild_id))
            return True
        except Exception as e:
            logger.error(f"Error updating join settings: {e}")
            return False
    
    def set_min_power_requirement(self, guild_id: int, min_power: int) -> bool:
        """Set minimum power requirement for join requests"""
        try:
            with self.get_connection() as conn:
                cursor = self._get_cursor(conn)
                cursor.execute("""
                    INSERT INTO server_join_settings (guild_id, min_power_requirement)
                    VALUES (?, ?)
                    ON CONFLICT(guild_id) DO UPDATE SET min_power_requirement = ?
                """, (guild_id, min_power, min_power))
            return True
        except Exception as e:
            logger.error(f"Error setting min power requirement: {e}")
            return False
    
    def get_join_settings(self, guild_id: int) -> Optional[Dict]:
        """Get join request settings for a guild"""
        try:
            with self.get_connection() as conn:
                cursor = self._get_cursor(conn)
                cursor.execute("""
                    SELECT join_channel_id, admin_review_channel_id, min_power_requirement, welcome_message_id, build_setup_channel_id
                    FROM server_join_settings
                    WHERE guild_id = ?
                """, (guild_id,))
                row = cursor.fetchone()
                if row:
                    return {
                        "join_channel_id": row[0],
                        "admin_review_channel_id": row[1],
                        "min_power_requirement": row[2] or 0,
                        "welcome_message_id": row[3],
                        "build_setup_channel_id": row[4]
                    }
            return None
        except Exception as e:
            logger.error(f"Error getting join settings: {e}")
            return None
    
    def set_welcome_message_id(self, guild_id: int, message_id: int) -> bool:
        """Store the welcome message ID"""
        try:
            with self.get_connection() as conn:
                cursor = self._get_cursor(conn)
                cursor.execute("""
                    UPDATE server_join_settings
                    SET welcome_message_id = ?
                    WHERE guild_id = ?
                """, (message_id, guild_id))
            return True
        except Exception as e:
            logger.error(f"Error setting welcome message ID: {e}")
            return False
    
    def create_join_request(self, user_id: int, guild_id: int, language: str,
                           in_game_name: str, level: int, power: int, admin_message_id: int = None) -> Optional[int]:
        """Create a new join request and return its ID"""
        try:
            with self.get_connection() as conn:
                cursor = self._get_cursor(conn)
                cursor.execute("""
                    INSERT INTO join_requests (user_id, guild_id, language, in_game_name, level, power, admin_message_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (user_id, guild_id, language, in_game_name, level, power, admin_message_id))
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"Error creating join request: {e}")
            return None
    
    def get_join_request(self, request_id: int) -> Optional[Dict]:
        """Get a join request by ID"""
        try:
            with self.get_connection() as conn:
                cursor = self._get_cursor(conn)
                cursor.execute("""
                    SELECT id, user_id, guild_id, language, in_game_name, level, power, status,
                           requested_at, reviewed_by, reviewed_at, rejection_reason, admin_message_id
                    FROM join_requests
                    WHERE id = ?
                """, (request_id,))
                row = cursor.fetchone()
                if row:
                    return {
                        "id": row[0],
                        "user_id": row[1],
                        "guild_id": row[2],
                        "language": row[3],
                        "in_game_name": row[4],
                        "level": row[5],
                        "power": row[6],
                        "status": row[7],
                        "requested_at": row[8],
                        "reviewed_by": row[9],
                        "reviewed_at": row[10],
                        "rejection_reason": row[11],
                        "admin_message_id": row[12]
                    }
            return None
        except Exception as e:
            logger.error(f"Error getting join request: {e}")
            return None
    
    def update_join_request_status(self, request_id: int, status: str, reviewed_by: int, rejection_reason: str = None) -> bool:
        """Update join request status"""
        try:
            with self.get_connection() as conn:
                cursor = self._get_cursor(conn)
                cursor.execute("""
                    UPDATE join_requests
                    SET status = ?, reviewed_by = ?, reviewed_at = CURRENT_TIMESTAMP, rejection_reason = ?
                    WHERE id = ?
                """, (status, reviewed_by, rejection_reason, request_id))
            return True
        except Exception as e:
            logger.error(f"Error updating join request status: {e}")
            return False
    
    def get_pending_join_requests(self, guild_id: int) -> List[Dict]:
        """Get all pending join requests for a guild"""
        try:
            with self.get_connection() as conn:
                cursor = self._get_cursor(conn)
                cursor.execute("""
                    SELECT id, user_id, language, in_game_name, level, power, requested_at
                    FROM join_requests
                    WHERE guild_id = ? AND status = 'pending'
                    ORDER BY requested_at DESC
                """, (guild_id,))
                rows = cursor.fetchall()
                return [{
                    "id": row[0],
                    "user_id": row[1],
                    "language": row[2],
                    "in_game_name": row[3],
                    "level": row[4],
                    "power": row[5],
                    "requested_at": row[6]
                } for row in rows]
        except Exception as e:
            logger.error(f"Error getting pending join requests: {e}")
            return []
    
    def close(self):
        """Close database connection - not needed anymore with connection pooling"""
        logger.info("Database using connection pooling - no persistent connection to close")
