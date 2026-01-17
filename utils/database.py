import json
import os
from datetime import datetime, timedelta
from pathlib import Path


class Database:
    def __init__(self, base_path: str = "./data"):
        self.base_path = base_path
        self.users_dir = os.path.join(base_path, "users")
        self.reminders_file = os.path.join(base_path, "reminders.json")
        
        Path(self.users_dir).mkdir(parents=True, exist_ok=True)
        Path(self.base_path).mkdir(parents=True, exist_ok=True)
        
        self._ensure_reminders_file()

    def _ensure_reminders_file(self):
        if not os.path.exists(self.reminders_file):
            with open(self.reminders_file, 'w', encoding='utf-8') as f:
                json.dump({"reminders": []}, f, ensure_ascii=False, indent=2)

    def _get_user_file(self, user_id: int) -> str:
        return os.path.join(self.users_dir, f"{user_id}.json")

    def _load_user(self, user_id: int) -> dict:
        user_file = self._get_user_file(user_id)
        if os.path.exists(user_file):
            try:
                with open(user_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return self._default_user()
        return self._default_user()

    def _save_user(self, user_id: int, data: dict):
        user_file = self._get_user_file(user_id)
        with open(user_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

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

    def _load_reminders(self) -> dict:
        try:
            with open(self.reminders_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {"reminders": []}

    def _save_reminders(self, data: dict):
        with open(self.reminders_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def add_reminder(self, name: str, message: str, time: str, is_recurring: bool, role_id: int = None):
        reminders_data = self._load_reminders()
        
        reminder_id = max([r.get("id", 0) for r in reminders_data.get("reminders", [])], default=0) + 1
        
        reminder = {
            "id": reminder_id,
            "name": name,
            "message": message,
            "time": time,
            "is_recurring": is_recurring,
            "role_ids": [role_id] if role_id else [],
            "role_id": role_id,
            "created_at": datetime.now().isoformat(),
            "enabled": True,
            "channel_id": None
        }
        reminders_data["reminders"].append(reminder)
        self._save_reminders(reminders_data)
        return reminder

    def get_reminders(self) -> list:
        return self._load_reminders().get("reminders", [])

    def get_reminder(self, reminder_id: int) -> dict:
        reminders_data = self._load_reminders()
        for reminder in reminders_data.get("reminders", []):
            if reminder["id"] == reminder_id:
                return reminder
        return None

    def delete_reminder(self, reminder_id: int) -> bool:
        reminders_data = self._load_reminders()
        original_count = len(reminders_data["reminders"])
        reminders_data["reminders"] = [r for r in reminders_data["reminders"] if r["id"] != reminder_id]
        
        if len(reminders_data["reminders"]) < original_count:
            self._save_reminders(reminders_data)
            return True
        return False

    def toggle_reminder(self, reminder_id: int) -> dict:
        reminders_data = self._load_reminders()
        for reminder in reminders_data.get("reminders", []):
            if reminder["id"] == reminder_id:
                reminder["enabled"] = not reminder["enabled"]
                self._save_reminders(reminders_data)
                return reminder
        return None

    def update_reminder_time(self, reminder_id: int, time: str):
        reminders_data = self._load_reminders()
        for reminder in reminders_data.get("reminders", []):
            if reminder["id"] == reminder_id:
                reminder["time"] = time
                self._save_reminders(reminders_data)
                return reminder
        return None

    def update_reminder_name(self, reminder_id: int, name: str):
        reminders_data = self._load_reminders()
        for reminder in reminders_data.get("reminders", []):
            if reminder["id"] == reminder_id:
                reminder["name"] = name
                self._save_reminders(reminders_data)
                return reminder
        return None

    def update_reminder_message(self, reminder_id: int, message: str):
        reminders_data = self._load_reminders()
        for reminder in reminders_data.get("reminders", []):
            if reminder["id"] == reminder_id:
                reminder["message"] = message
                self._save_reminders(reminders_data)
                return reminder
        return None

    def update_reminder_roles(self, reminder_id: int, role_ids: list):
        reminders_data = self._load_reminders()
        for reminder in reminders_data.get("reminders", []):
            if reminder["id"] == reminder_id:
                reminder["role_ids"] = role_ids
                reminder["role_id"] = role_ids[0] if role_ids else None
                self._save_reminders(reminders_data)
                return reminder
        return None

    def add_reminder_roles(self, reminder_id: int, new_role_ids: list):
        reminders_data = self._load_reminders()
        for reminder in reminders_data.get("reminders", []):
            if reminder["id"] == reminder_id:
                current_roles = reminder.get("role_ids", [])
                if not current_roles and reminder.get("role_id"):
                    current_roles = [reminder["role_id"]]
                
                for rid in new_role_ids:
                    if rid not in current_roles:
                        current_roles.append(rid)
                
                reminder["role_ids"] = current_roles
                reminder["role_id"] = current_roles[0] if current_roles else None
                self._save_reminders(reminders_data)
                return reminder
        return None

    def remove_reminder_roles(self, reminder_id: int, remove_role_ids: list):
        reminders_data = self._load_reminders()
        for reminder in reminders_data.get("reminders", []):
            if reminder["id"] == reminder_id:
                current_roles = reminder.get("role_ids", [])
                if not current_roles and reminder.get("role_id"):
                    current_roles = [reminder["role_id"]]
                
                current_roles = [rid for rid in current_roles if rid not in remove_role_ids]
                
                reminder["role_ids"] = current_roles
                reminder["role_id"] = current_roles[0] if current_roles else None
                self._save_reminders(reminders_data)
                return reminder
        return None

    def add_activity(self, user_id: int, action: str):
        pass

    def get_user_activity(self, user_id: int, limit: int = 10):
        return []

    def get_top_active_users(self, limit: int = 10):
        return self.get_top_active_users_by_messages(limit)


    def add_message(self, user_id: int):
        user = self._load_user(user_id)
        user["user_id"] = user_id
        
        if "message_count" not in user:
            user["message_count"] = {"total": 0, "messages": []}
        
        user["message_count"]["total"] += 1
        user["message_count"]["messages"].append({
            "timestamp": datetime.now().isoformat()
        })
        
        self._save_user(user_id, user)

    def get_user_message_count(self, user_id: int, days: int = None) -> int:
        user = self._load_user(user_id)
        
        if days is None:
            return user.get("message_count", {}).get("total", 0)
        
        cutoff_date = datetime.now() - timedelta(days=days)
        count = 0
        for msg in user.get("message_count", {}).get("messages", []):
            msg_date = datetime.fromisoformat(msg["timestamp"])
            if msg_date > cutoff_date:
                count += 1
        
        return count

    def get_top_active_users_by_messages(self, limit: int = 100, days: int = None) -> list:
        activity_count = {}
        
        for filename in os.listdir(self.users_dir):
            if filename.endswith('.json'):
                try:
                    user_id = int(filename[:-5])
                    user = self._load_user(user_id)
                    
                    if days is None:
                        count = user.get("message_count", {}).get("total", 0)
                    else:
                        cutoff_date = datetime.now() - timedelta(days=days)
                        count = 0
                        for msg in user.get("message_count", {}).get("messages", []):
                            msg_date = datetime.fromisoformat(msg["timestamp"])
                            if msg_date > cutoff_date:
                                count += 1
                    
                    if count > 0:
                        activity_count[user_id] = count
                except:
                    continue
        
        return sorted(activity_count.items(), key=lambda x: x[1], reverse=True)[:limit]

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
        user = self._load_user(user_id)
        user["user_id"] = user_id
        return user

    def add_experience(self, user_id: int, amount: int = 25) -> dict:
        user = self._load_user(user_id)
        user["user_id"] = user_id
        user["experience"] += amount
        user["total_exp"] += amount
        user["last_exp_time"] = datetime.now().isoformat()
        
        exp_needed = self.calculate_exp_for_level(user["level"] + 1)
        
        while user["experience"] >= exp_needed and user["level"] < 100:
            user["experience"] -= exp_needed
            user["level"] += 1
            if user["level"] < 100:
                exp_needed = self.calculate_exp_for_level(user["level"] + 1)
        
        self._save_user(user_id, user)
        return user

    def get_top_users(self, limit: int = 10) -> list:
        users = []
        
        for filename in os.listdir(self.users_dir):
            if filename.endswith('.json'):
                try:
                    user_id = int(filename[:-5])
                    user = self._load_user(user_id)
                    users.append((user_id, user))
                except:
                    continue
        
        users.sort(key=lambda x: (x[1]["level"], x[1]["total_exp"]), reverse=True)
        return [(uid, user) for uid, user in users[:limit]]

    def get_user_rank(self, user_id: int) -> int:
        users = []
        
        for filename in os.listdir(self.users_dir):
            if filename.endswith('.json'):
                try:
                    uid = int(filename[:-5])
                    user = self._load_user(uid)
                    users.append((uid, user))
                except:
                    continue
        
        users.sort(key=lambda x: (x[1]["level"], x[1]["total_exp"]), reverse=True)
        
        for rank, (uid, user) in enumerate(users, 1):
            if uid == user_id:
                return rank
        return 0

    LEVEL_ROLES = {
        5: 1461765340093747343,
        10: 1461765418094956656,
        20: 1461764670066004052,
        40: 1461765509069668598,
        60: 1461765579298967797
    }

    def get_roles_for_level(self, level: int) -> list:
        roles = []
        for level_req, role_id in self.LEVEL_ROLES.items():
            if level >= level_req:
                roles.append(role_id)
        return roles

    def get_user_roles(self, user_id: int) -> list:
        user = self._load_user(user_id)
        return user.get("roles", [])

    def set_user_roles(self, user_id: int, role_ids: list):
        user = self._load_user(user_id)
        user["roles"] = role_ids
        self._save_user(user_id, user)

    def get_user_settings(self, user_id: int) -> dict:
        user = self._load_user(user_id)
        settings = user.get("settings", {})
        
        for key in ["bg_color", "bar_color", "rank_text_color", "level_text_color", 
                    "username_text_color", "exp_text_color", "total_exp_text_color"]:
            if key in settings and isinstance(settings[key], list):
                settings[key] = tuple(settings[key])
        
        return settings

    def set_user_settings(self, user_id: int, settings: dict):
        user = self._load_user(user_id)
        user["user_id"] = user_id
        user["settings"] = settings
        self._save_user(user_id, user)