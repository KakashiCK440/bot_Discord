import sqlite3
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Tuple
import json

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path: str = "bot_data.db"):
        """Initialize database connection"""
        self.db_path = db_path
        self.conn = None
        self.init_database()
    
    def init_database(self):
        """Initialize database and create tables"""
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            self.create_tables()
            logger.info(f"✅ Database initialized: {self.db_path}")
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            raise
    
    def create_tables(self):
        """Create all necessary tables"""
        cursor = self.conn.cursor()
        
        # Players table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS players (
                user_id INTEGER,
                guild_id INTEGER,
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
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                guild_id INTEGER,
                weapon_name TEXT,
                FOREIGN KEY (user_id, guild_id) REFERENCES players(user_id, guild_id)
            )
        """)
        
        # War participants table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS war_participants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                guild_id INTEGER,
                poll_week TEXT,
                participation_type TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Server settings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS server_settings (
                guild_id INTEGER PRIMARY KEY,
                language TEXT DEFAULT 'en',
                war_channel_id INTEGER,
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
        
        # Poll and reminder tracking table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sent_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                event_type TEXT,
                event_week TEXT,
                event_day TEXT,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(guild_id, event_type, event_week, event_day)
            )
        """)
        
        self.conn.commit()
        logger.info("✅ Database tables created")
    
    # ==================== PLAYER PROFILE OPERATIONS ====================
    
    def create_or_update_player(self, user_id: int, guild_id: int, 
                                in_game_name: str, mastery_points: int, 
                                level: int, build_type: str = None) -> bool:
        """Create or update player profile"""
        try:
            cursor = self.conn.cursor()
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
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error creating/updating player: {e}")
            return False
    
    def update_player_stats(self, user_id: int, guild_id: int, 
                           mastery_points: int = None, level: int = None) -> bool:
        """Update only player stats (mastery/level)"""
        try:
            cursor = self.conn.cursor()
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
            cursor.execute(query, params)
            self.conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error updating player stats: {e}")
            return False
    
    def get_player(self, user_id: int, guild_id: int) -> Optional[Dict]:
        """Get player profile"""
        try:
            cursor = self.conn.cursor()
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
            cursor = self.conn.cursor()
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
            cursor = self.conn.cursor()
            
            if order_by not in ["mastery_points", "level"]:
                order_by = "mastery_points"
            
            cursor.execute(f"""
                SELECT user_id, in_game_name, mastery_points, level, build_type,
                       ROW_NUMBER() OVER (ORDER BY {order_by} DESC, in_game_name ASC) as rank
                FROM players
                WHERE guild_id = ? AND in_game_name IS NOT NULL
                ORDER BY {order_by} DESC, in_game_name ASC
                LIMIT ?
            """, (guild_id, limit))
            
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting leaderboard: {e}")
            return []
    
    def get_player_rank(self, user_id: int, guild_id: int, 
                       order_by: str = "mastery_points") -> Optional[int]:
        """Get player's rank in leaderboard"""
        try:
            cursor = self.conn.cursor()
            
            if order_by not in ["mastery_points", "level"]:
                order_by = "mastery_points"
            
            cursor.execute(f"""
                WITH ranked_players AS (
                    SELECT user_id,
                           ROW_NUMBER() OVER (ORDER BY {order_by} DESC, in_game_name ASC) as rank
                    FROM players
                    WHERE guild_id = ? AND in_game_name IS NOT NULL
                )
                SELECT rank FROM ranked_players WHERE user_id = ?
            """, (guild_id, user_id))
            
            row = cursor.fetchone()
            return row['rank'] if row else None
        except Exception as e:
            logger.error(f"Error getting player rank: {e}")
            return None
    
    def delete_player(self, user_id: int, guild_id: int) -> bool:
        """Delete player profile and associated data"""
        try:
            cursor = self.conn.cursor()
            
            # Delete weapons first (foreign key)
            cursor.execute("""
                DELETE FROM player_weapons WHERE user_id = ? AND guild_id = ?
            """, (user_id, guild_id))
            
            # Delete player
            cursor.execute("""
                DELETE FROM players WHERE user_id = ? AND guild_id = ?
            """, (user_id, guild_id))
            
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error deleting player: {e}")
            return False
    
    def set_player_weapons(self, user_id: int, guild_id: int, weapons: List[str]) -> bool:
        """Set player's weapons (replaces existing)"""
        try:
            cursor = self.conn.cursor()
            
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
            
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error setting player weapons: {e}")
            return False
    
    def get_player_weapons(self, user_id: int, guild_id: int) -> List[str]:
        """Get player's weapons"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT weapon_name FROM player_weapons 
                WHERE user_id = ? AND guild_id = ?
            """, (user_id, guild_id))
            return [row['weapon_name'] for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting player weapons: {e}")
            return []
            
    def get_all_player_weapons(self, guild_id: int) -> Dict[int, List[str]]:
        """Get all player weapons for a guild as a dictionary keyed by user_id"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT user_id, weapon_name FROM player_weapons 
                WHERE guild_id = ?
            """, (guild_id,))
            rows = cursor.fetchall()
            
            weapons = {}
            for row in rows:
                user_id = row['user_id']
                if user_id not in weapons:
                    weapons[user_id] = []
                weapons[user_id].append(row['weapon_name'])
                
            return weapons
        except Exception as e:
            logger.error(f"Error getting all player weapons: {e}")
            return {}
    
    # ==================== WAR OPERATIONS ====================
    
    def set_war_participation(self, user_id: int, guild_id: int, 
                             poll_week: str, participation_type: str) -> bool:
        """Set war participation for current week"""
        try:
            cursor = self.conn.cursor()
            
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
            
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error setting war participation: {e}")
            return False
    
    def get_war_participants(self, guild_id: int, poll_week: str, 
                            participation_type: str = None) -> List[int]:
        """Get war participants for a week"""
        try:
            cursor = self.conn.cursor()
            
            if participation_type:
                cursor.execute("""
                    SELECT user_id FROM war_participants
                    WHERE guild_id = ? AND poll_week = ? AND participation_type = ?
                """, (guild_id, poll_week, participation_type))
            else:
                cursor.execute("""
                    SELECT user_id FROM war_participants
                    WHERE guild_id = ? AND poll_week = ?
                """, (guild_id, poll_week))
            
            return [row['user_id'] for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting war participants: {e}")
            return []
    
    def clear_war_participants(self, guild_id: int, poll_week: str) -> bool:
        """Clear all war participants for a week"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                DELETE FROM war_participants WHERE guild_id = ? AND poll_week = ?
            """, (guild_id, poll_week))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error clearing war participants: {e}")
            return False
    
    # ==================== SERVER SETTINGS OPERATIONS ====================
    
    def get_server_settings(self, guild_id: int) -> Dict:
        """Get server settings"""
        try:
            cursor = self.conn.cursor()
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
                self.conn.commit()
                return self.get_server_settings(guild_id)
        except Exception as e:
            logger.error(f"Error getting server settings: {e}")
            return {}
    
    def update_server_setting(self, guild_id: int, setting: str, value) -> bool:
        """Update a specific server setting"""
        try:
            cursor = self.conn.cursor()
            
            # Ensure server settings exist
            cursor.execute("""
                INSERT OR IGNORE INTO server_settings (guild_id) VALUES (?)
            """, (guild_id,))
            
            # Update the setting
            cursor.execute(f"""
                UPDATE server_settings SET {setting} = ? WHERE guild_id = ?
            """, (value, guild_id))
            
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error updating server setting: {e}")
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
            cursor = self.conn.cursor()
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
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO sent_events (guild_id, event_type, event_week, event_day)
                VALUES (?, ?, ?, ?)
            """, (guild_id, event_type, event_week, event_day))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error marking event sent: {e}")
            return False
    
    def clear_old_events(self, older_than_weeks: int = 4) -> bool:
        """Clear old event tracking data"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                DELETE FROM sent_events 
                WHERE sent_at < datetime('now', '-' || ? || ' days')
            """, (older_than_weeks * 7,))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error clearing old events: {e}")
            return False
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")