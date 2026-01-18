import sqlite3
import json
import os
from datetime import datetime, timedelta
from pathlib import Path


class Database:
    def __init__(self, base_path: str = "./data"):
        self.base_path = base_path
        Path(self.base_path).mkdir(parents=True, exist_ok=True)
        
        self.db_path = os.path.join(base_path, "dsbot.db")
        self.conn = None
        self.cursor = None
        
        self._init_db()

    def _get_connection(self):
        if self.conn is None:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            self.cursor = self.conn.cursor()
        return self.conn

    def _init_db(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                level INTEGER DEFAULT 1,
                experience INTEGER DEFAULT 0,
                total_exp INTEGER DEFAULT 0,
                last_exp_time TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                role_id INTEGER NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                message TEXT NOT NULL,
                time TEXT NOT NULL,
                is_recurring BOOLEAN DEFAULT 0,
                enabled BOOLEAN DEFAULT 1,
                channel_id INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reminder_roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reminder_id INTEGER NOT NULL,
                role_id INTEGER NOT NULL,
                FOREIGN KEY (reminder_id) REFERENCES reminders(id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER PRIMARY KEY,
                bg_color TEXT DEFAULT '[20, 20, 20]',
                bar_color TEXT DEFAULT '[220, 100, 50]',
                rank_text_color TEXT DEFAULT '[220, 100, 50]',
                level_text_color TEXT DEFAULT '[255, 150, 0]',
                username_text_color TEXT DEFAULT '[255, 255, 255]',
                exp_text_color TEXT DEFAULT '[100, 200, 255]',
                total_exp_text_color TEXT DEFAULT '[150, 150, 150]',
                font TEXT DEFAULT 'default',
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS guilds (
                guild_id INTEGER PRIMARY KEY,
                guild_name TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS guild_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                joined_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (guild_id) REFERENCES guilds(guild_id),
                UNIQUE(guild_id, user_id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id INTEGER PRIMARY KEY,
                activity_channels TEXT DEFAULT '[]',
                level_roles TEXT DEFAULT '{}',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (guild_id) REFERENCES guilds(guild_id)
            )
        ''')
        
        conn.commit()

    def _ensure_user_exists(self, user_id: int):
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
        if cursor.fetchone() is None:
            cursor.execute('''
                INSERT INTO users (user_id, level, experience, total_exp)
                VALUES (?, 1, 0, 0)
            ''', (user_id,))
            
            cursor.execute('''
                INSERT INTO user_settings (user_id)
                VALUES (?)
            ''', (user_id,))
            
            conn.commit()

    def _default_user(self) -> dict:
        return {
            "user_id": None,
            "level": 1,
            "experience": 0,
            "total_exp": 0,
            "last_exp_time": None,
            "roles": [],
            "settings": {
                "bg_color": [20, 20, 20],
                "bar_color": [220, 100, 50],
                "rank_text_color": [220, 100, 50],
                "level_text_color": [255, 150, 0],
                "username_text_color": [255, 255, 255],
                "exp_text_color": [100, 200, 255],
                "total_exp_text_color": [150, 150, 150],
                "font": "default"
            },
            "message_count": {
                "total": 0,
                "messages": []
            }
        }

    def add_reminder(self, name: str, message: str, time: str, is_recurring: bool, role_id: int = None):
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO reminders (name, message, time, is_recurring)
            VALUES (?, ?, ?, ?)
        ''', (name, message, time, is_recurring))
        
        reminder_id = cursor.lastrowid
        
        if role_id:
            cursor.execute('''
                INSERT INTO reminder_roles (reminder_id, role_id)
                VALUES (?, ?)
            ''', (reminder_id, role_id))
        
        conn.commit()
        
        return self.get_reminder(reminder_id)

    def create_reminder(self, name: str, message: str, time: str, is_recurring: bool, channel_id: int, role_ids: list = None):
        """Создать напоминание с channel_id и поддержкой списка ролей"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO reminders (name, message, time, is_recurring, channel_id)
            VALUES (?, ?, ?, ?, ?)
        ''', (name, message, time, is_recurring, channel_id))
        
        reminder_id = cursor.lastrowid
        
        if role_ids:
            for role_id in role_ids:
                cursor.execute('''
                    INSERT INTO reminder_roles (reminder_id, role_id)
                    VALUES (?, ?)
                ''', (reminder_id, role_id))
        
        conn.commit()
        
        return self.get_reminder(reminder_id)

    def get_reminders(self) -> list:
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM reminders ORDER BY id DESC')
        reminders = []
        
        for row in cursor.fetchall():
            reminder = dict(row)
            
            cursor.execute('''
                SELECT role_id FROM reminder_roles WHERE reminder_id = ?
            ''', (reminder['id'],))
            
            role_ids = [r[0] for r in cursor.fetchall()]
            reminder['role_ids'] = role_ids
            reminder['role_id'] = role_ids[0] if role_ids else None
            
            reminders.append(reminder)
        
        return reminders

    def get_reminder(self, reminder_id: int) -> dict:
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM reminders WHERE id = ?', (reminder_id,))
        row = cursor.fetchone()
        
        if not row:
            return None
        
        reminder = dict(row)
        
        cursor.execute('''
            SELECT role_id FROM reminder_roles WHERE reminder_id = ?
        ''', (reminder_id,))
        
        role_ids = [r[0] for r in cursor.fetchall()]
        reminder['role_ids'] = role_ids
        reminder['role_id'] = role_ids[0] if role_ids else None
        
        return reminder

    def delete_reminder(self, reminder_id: int) -> bool:
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM reminder_roles WHERE reminder_id = ?', (reminder_id,))
        cursor.execute('DELETE FROM reminders WHERE id = ?', (reminder_id,))
        
        conn.commit()
        return cursor.rowcount > 0

    def toggle_reminder(self, reminder_id: int) -> dict:
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT enabled FROM reminders WHERE id = ?', (reminder_id,))
        row = cursor.fetchone()
        
        if not row:
            return None
        
        new_enabled = not bool(row[0])
        cursor.execute('UPDATE reminders SET enabled = ? WHERE id = ?', (new_enabled, reminder_id))
        conn.commit()
        
        return self.get_reminder(reminder_id)

    def update_reminder_time(self, reminder_id: int, time: str):
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('UPDATE reminders SET time = ? WHERE id = ?', (time, reminder_id))
        conn.commit()
        
        return self.get_reminder(reminder_id)

    def update_reminder_name(self, reminder_id: int, name: str):
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('UPDATE reminders SET name = ? WHERE id = ?', (name, reminder_id))
        conn.commit()
        
        return self.get_reminder(reminder_id)

    def update_reminder_message(self, reminder_id: int, message: str):
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('UPDATE reminders SET message = ? WHERE id = ?', (message, reminder_id))
        conn.commit()
        
        return self.get_reminder(reminder_id)

    def update_reminder_recurring(self, reminder_id: int, is_recurring: bool):
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('UPDATE reminders SET is_recurring = ? WHERE id = ?', (is_recurring, reminder_id))
        conn.commit()
        
        return self.get_reminder(reminder_id)

    def update_reminder_roles(self, reminder_id: int, role_ids: list):
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM reminder_roles WHERE reminder_id = ?', (reminder_id,))
        
        for role_id in role_ids:
            cursor.execute('''
                INSERT INTO reminder_roles (reminder_id, role_id)
                VALUES (?, ?)
            ''', (reminder_id, role_id))
        
        conn.commit()
        return self.get_reminder(reminder_id)

    def update_reminder_channel_id(self, reminder_id: int, channel_id: int):
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('UPDATE reminders SET channel_id = ? WHERE id = ?', (channel_id, reminder_id))
        conn.commit()
        
        return self.get_reminder(reminder_id)

    def add_reminder_roles(self, reminder_id: int, new_role_ids: list):
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT role_id FROM reminder_roles WHERE reminder_id = ?
        ''', (reminder_id,))
        
        current_roles = [r[0] for r in cursor.fetchall()]
        
        for role_id in new_role_ids:
            if role_id not in current_roles:
                cursor.execute('''
                    INSERT INTO reminder_roles (reminder_id, role_id)
                    VALUES (?, ?)
                ''', (reminder_id, role_id))
        
        conn.commit()
        return self.get_reminder(reminder_id)

    def remove_reminder_roles(self, reminder_id: int, remove_role_ids: list):
        conn = self._get_connection()
        cursor = conn.cursor()
        
        for role_id in remove_role_ids:
            cursor.execute('''
                DELETE FROM reminder_roles WHERE reminder_id = ? AND role_id = ?
            ''', (reminder_id, role_id))
        
        conn.commit()
        return self.get_reminder(reminder_id)

    def add_activity(self, user_id: int, action: str):
        pass

    def get_user_activity(self, user_id: int, limit: int = 10):
        return []

    def get_top_active_users(self, limit: int = 10):
        return self.get_top_active_users_by_messages(limit)

    def add_message(self, user_id: int):
        self._ensure_user_exists(user_id)
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO messages (user_id)
            VALUES (?)
        ''', (user_id,))
        
        conn.commit()

    def get_user_message_count(self, user_id: int, days: int = None) -> int:
        conn = self._get_connection()
        cursor = conn.cursor()
        
        if days is None:
            cursor.execute('''
                SELECT COUNT(*) FROM messages WHERE user_id = ?
            ''', (user_id,))
        else:
            cutoff_date = datetime.now() - timedelta(days=days)
            cursor.execute('''
                SELECT COUNT(*) FROM messages 
                WHERE user_id = ? AND timestamp > ?
            ''', (user_id, cutoff_date.isoformat()))
        
        return cursor.fetchone()[0]

    def get_top_active_users_by_messages(self, limit: int = 100, days: int = None) -> list:
        conn = self._get_connection()
        cursor = conn.cursor()
        
        if days is None:
            cursor.execute('''
                SELECT user_id, COUNT(*) as count
                FROM messages
                GROUP BY user_id
                ORDER BY count DESC
                LIMIT ?
            ''', (limit,))
        else:
            cutoff_date = datetime.now() - timedelta(days=days)
            cursor.execute('''
                SELECT user_id, COUNT(*) as count
                FROM messages
                WHERE timestamp > ?
                GROUP BY user_id
                ORDER BY count DESC
                LIMIT ?
            ''', (cutoff_date.isoformat(), limit))
        
        return [(row[0], row[1]) for row in cursor.fetchall()]

    def add_notification(self, title: str, message: str, role_ids: list):
        pass

    def get_notifications(self):
        return []

    def calculate_exp_for_level(self, level: int) -> int:
        if level == 1:
            return 100
        if level == 2:
            return 100
        
        exp = 100
        for i in range(3, level + 1):
            exp = int(exp * 1.2)
        return exp

    def get_user_stats(self, user_id: int) -> dict:
        self._ensure_user_exists(user_id)
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        row = cursor.fetchone()
        
        if not row:
            return self._default_user()
        
        user = dict(row)
        user["user_id"] = user_id
        
        cursor.execute('SELECT role_id FROM user_roles WHERE user_id = ?', (user_id,))
        user["roles"] = [r[0] for r in cursor.fetchall()]
        
        cursor.execute('SELECT * FROM user_settings WHERE user_id = ?', (user_id,))
        settings_row = cursor.fetchone()
        
        if settings_row:
            settings_dict = dict(settings_row)
            settings = {}
            for key in ["bg_color", "bar_color", "rank_text_color", "level_text_color",
                       "username_text_color", "exp_text_color", "total_exp_text_color"]:
                if key in settings_dict and settings_dict[key]:
                    settings[key] = json.loads(settings_dict[key])
            settings["font"] = settings_dict.get("font", "default")
            user["settings"] = settings
        
        return user

    def add_experience(self, user_id: int, amount: int = 25) -> dict:
        self._ensure_user_exists(user_id)
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        row = cursor.fetchone()
        user = dict(row)
        
        user["experience"] += amount
        user["total_exp"] += amount
        user["last_exp_time"] = datetime.now().isoformat()
        
        exp_needed = self.calculate_exp_for_level(user["level"] + 1)
        
        while user["experience"] >= exp_needed and user["level"] < 100:
            user["experience"] -= exp_needed
            user["level"] += 1
            if user["level"] < 100:
                exp_needed = self.calculate_exp_for_level(user["level"] + 1)
        
        cursor.execute('''
            UPDATE users SET level = ?, experience = ?, total_exp = ?, last_exp_time = ?, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        ''', (user["level"], user["experience"], user["total_exp"], user["last_exp_time"], user_id))
        
        conn.commit()
        
        return self.get_user_stats(user_id)

    def get_top_users(self, limit: int = 10) -> list:
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT user_id, level, total_exp FROM users
            ORDER BY level DESC, total_exp DESC
            LIMIT ?
        ''', (limit,))
        
        result = []
        for row in cursor.fetchall():
            user_dict = {"user_id": row[0], "level": row[1], "total_exp": row[2]}
            result.append((row[0], user_dict))
        
        return result

    def get_user_rank(self, user_id: int) -> int:
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT COUNT(*) FROM users
            WHERE level > (SELECT level FROM users WHERE user_id = ?)
            OR (level = (SELECT level FROM users WHERE user_id = ?) AND total_exp > (SELECT total_exp FROM users WHERE user_id = ?))
        ''', (user_id, user_id, user_id))
        
        rank = cursor.fetchone()[0] + 1
        return rank

    def get_roles_for_level(self, level: int, guild_id: int = None) -> list:
        if guild_id:
            settings = self.get_guild_settings(guild_id)
            level_roles = settings["level_roles"]
        else:
            level_roles = self.config.level_roles
        
        if str(level) in level_roles:
            return [level_roles[str(level)]]
        return []
    
    def get_all_roles_for_level_and_below(self, level: int, guild_id: int = None) -> list:
        if guild_id:
            settings = self.get_guild_settings(guild_id)
            level_roles = settings["level_roles"]
        else:
            level_roles = self.config.level_roles
        
        roles = []
        for level_req, role_id in level_roles.items():
            if level >= int(level_req):
                roles.append(role_id)
        return roles

    def get_user_roles(self, user_id: int) -> list:
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT role_id FROM user_roles WHERE user_id = ?', (user_id,))
        return [row[0] for row in cursor.fetchall()]

    def set_user_roles(self, user_id: int, role_ids: list):
        self._ensure_user_exists(user_id)
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM user_roles WHERE user_id = ?', (user_id,))
        
        for role_id in role_ids:
            cursor.execute('''
                INSERT INTO user_roles (user_id, role_id)
                VALUES (?, ?)
            ''', (user_id, role_id))
        
        conn.commit()

    def get_user_settings(self, user_id: int) -> dict:
        self._ensure_user_exists(user_id)
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM user_settings WHERE user_id = ?', (user_id,))
        row = cursor.fetchone()
        
        if not row:
            return self._default_user()["settings"]
        
        settings_dict = dict(row)
        settings = {}
        
        for key in ["bg_color", "bar_color", "rank_text_color", "level_text_color",
                   "username_text_color", "exp_text_color", "total_exp_text_color"]:
            if key in settings_dict and settings_dict[key]:
                try:
                    settings[key] = tuple(json.loads(settings_dict[key]))
                except:
                    settings[key] = tuple(self._default_user()["settings"][key])
        
        settings["font"] = settings_dict.get("font", "default")
        
        return settings

    def set_user_settings(self, user_id: int, settings: dict):
        self._ensure_user_exists(user_id)
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        bg_color = json.dumps(list(settings.get("bg_color", [20, 20, 20])))
        bar_color = json.dumps(list(settings.get("bar_color", [220, 100, 50])))
        rank_text_color = json.dumps(list(settings.get("rank_text_color", [220, 100, 50])))
        level_text_color = json.dumps(list(settings.get("level_text_color", [255, 150, 0])))
        username_text_color = json.dumps(list(settings.get("username_text_color", [255, 255, 255])))
        exp_text_color = json.dumps(list(settings.get("exp_text_color", [100, 200, 255])))
        total_exp_text_color = json.dumps(list(settings.get("total_exp_text_color", [150, 150, 150])))
        font = settings.get("font", "default")
        
        cursor.execute('''
            UPDATE user_settings
            SET bg_color = ?, bar_color = ?, rank_text_color = ?, level_text_color = ?,
                username_text_color = ?, exp_text_color = ?, total_exp_text_color = ?, font = ?
            WHERE user_id = ?
        ''', (bg_color, bar_color, rank_text_color, level_text_color,
              username_text_color, exp_text_color, total_exp_text_color, font, user_id))
        
        conn.commit()
    def _ensure_guild_exists(self, guild_id: int):
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT guild_id FROM guild_settings WHERE guild_id = ?', (guild_id,))
        if cursor.fetchone() is None:
            cursor.execute('''
                INSERT INTO guild_settings (guild_id, activity_channels, level_roles)
                VALUES (?, ?, ?)
            ''', (guild_id, json.dumps([]), json.dumps({})))
            conn.commit()

    def get_guild_settings(self, guild_id: int) -> dict:
        self._ensure_guild_exists(guild_id)
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT activity_channels, level_roles FROM guild_settings WHERE guild_id = ?', (guild_id,))
        row = cursor.fetchone()
        
        if row:
            return {
                "activity_channels": json.loads(row[0]) if row[0] else [],
                "level_roles": json.loads(row[1]) if row[1] else {}
            }
        return {"activity_channels": [], "level_roles": {}}

    def set_guild_activity_channels(self, guild_id: int, channels: list):
        self._ensure_guild_exists(guild_id)
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE guild_settings
            SET activity_channels = ?, updated_at = CURRENT_TIMESTAMP
            WHERE guild_id = ?
        ''', (json.dumps(channels), guild_id))
        conn.commit()

    def add_activity_channel(self, guild_id: int, channel_id: int):
        settings = self.get_guild_settings(guild_id)
        channels = settings["activity_channels"]
        if channel_id not in channels:
            channels.append(channel_id)
            self.set_guild_activity_channels(guild_id, channels)

    def remove_activity_channel(self, guild_id: int, channel_id: int):
        settings = self.get_guild_settings(guild_id)
        channels = settings["activity_channels"]
        if channel_id in channels:
            channels.remove(channel_id)
            self.set_guild_activity_channels(guild_id, channels)

    def set_guild_level_roles(self, guild_id: int, level_roles: dict):
        self._ensure_guild_exists(guild_id)
        conn = self._get_connection()
        cursor = conn.cursor()
        
        level_roles_str = json.dumps({str(k): v for k, v in level_roles.items()})
        cursor.execute('''
            UPDATE guild_settings
            SET level_roles = ?, updated_at = CURRENT_TIMESTAMP
            WHERE guild_id = ?
        ''', (level_roles_str, guild_id))
        conn.commit()

    def set_role_for_level(self, guild_id: int, level: int, role_id: int):
        settings = self.get_guild_settings(guild_id)
        level_roles = settings["level_roles"]
        level_roles[str(level)] = role_id
        self.set_guild_level_roles(guild_id, level_roles)

    def remove_role_for_level(self, guild_id: int, level: int):
        settings = self.get_guild_settings(guild_id)
        level_roles = settings["level_roles"]
        if str(level) in level_roles:
            del level_roles[str(level)]
        self.set_guild_level_roles(guild_id, level_roles)
    def register_guild(self, guild_id: int, guild_name: str = None):
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT guild_id FROM guilds WHERE guild_id = ?', (guild_id,))
        if cursor.fetchone() is None:
            cursor.execute('''
                INSERT INTO guilds (guild_id, guild_name)
                VALUES (?, ?)
            ''', (guild_id, guild_name or f"Guild {guild_id}"))
            conn.commit()
        
        self._ensure_guild_exists(guild_id)

    def add_guild_member(self, guild_id: int, user_id: int):
        self.register_guild(guild_id)
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO guild_members (guild_id, user_id)
                VALUES (?, ?)
            ''', (guild_id, user_id))
            conn.commit()
        except sqlite3.IntegrityError:
            pass

    def get_user_guilds(self, user_id: int) -> list:
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT g.guild_id, g.guild_name FROM guilds g
            INNER JOIN guild_members gm ON g.guild_id = gm.guild_id
            WHERE gm.user_id = ?
            ORDER BY gm.joined_at DESC
        ''', (user_id,))
        
        guilds = []
        for row in cursor.fetchall():
            guild_id = row[0]
            guild_name = row[1] if row[1] else f"Сервер {guild_id}"
            guilds.append({"guild_id": guild_id, "guild_name": guild_name})
        return guilds

    def get_guild_info(self, guild_id: int) -> dict:
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT guild_id, guild_name FROM guilds WHERE guild_id = ?', (guild_id,))
        row = cursor.fetchone()
        
        if row:
            return {"guild_id": row[0], "guild_name": row[1]}
        return None
