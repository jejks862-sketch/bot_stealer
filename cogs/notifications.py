import discord
from discord.ext import commands
from utils.database import Database
from utils.scheduler import ReminderScheduler
import logging

logger = logging.getLogger(__name__)


class NotificationsCog(commands.Cog):
    def __init__(self, bot, db: Database, scheduler: ReminderScheduler):
        self.bot = bot
        self.db = db
        self.scheduler = scheduler

    async def send_reminder(self, reminder_id: int, guild_id: int):
        reminder = self.db.get_reminder(reminder_id)
        if not reminder or not reminder["enabled"]:
            return

        guild = self.bot.get_guild(guild_id)
        if not guild:
            logger.warning(f"Guild {guild_id} not found")
            return

        role_mentions = ""
        role_ids = reminder.get("role_ids", [])
        
        if not role_ids and reminder.get("role_id"):
            role_ids = [reminder["role_id"]]
        
        if role_ids:
            mentions = []
            for rid in role_ids:
                role = guild.get_role(rid)
                if role:
                    mentions.append(role.mention)
            role_mentions = " ".join(mentions) if mentions else ""

        channel_id = reminder.get("channel_id")
        if channel_id:
            channel = self.bot.get_channel(channel_id)
        else:
            channel = guild.text_channels[0] if guild.text_channels else None
        
        if channel:
            embed = discord.Embed(
                title=reminder['name'],
                description=reminder['message'],
                color=discord.Color.blue()
            )
            
            if role_ids:
                mentions = []
                for rid in role_ids:
                    role = guild.get_role(rid)
                    if role:
                        mentions.append(role.mention)
                role_mentions = " ".join(mentions) if mentions else ""
                if role_mentions:
                    await channel.send(role_mentions, embed=embed)
                else:
                    await channel.send(embed=embed)
            else:
                await channel.send(embed=embed)
        
        # Автоудаление одноразового напоминания
        if not reminder.get("is_recurring", False):
            self.db.delete_reminder(reminder_id)
            job_id = f"reminder_{reminder_id}"
            try:
                self.scheduler.remove_job(job_id)
                logger.info(f"One-time reminder {reminder_id} deleted automatically")
            except:
                pass

    def schedule_reminder(self, reminder: dict, guild_id: int):
        if not reminder["enabled"]:
            return

        job_id = f"reminder_{reminder['id']}"

        try:
            if reminder["is_recurring"]:
                hour, minute = map(int, reminder["time"].split(":"))
                self.scheduler.add_job(
                    self.send_reminder,
                    "cron",
                    hour=hour,
                    minute=minute,
                    args=[reminder["id"], guild_id],
                    job_id=job_id
                )
            else:
                from datetime import datetime
                time_parts = reminder["time"].split(":")
                hour, minute = int(time_parts[0]), int(time_parts[1])

                from apscheduler.triggers.date import DateTrigger
                from datetime import datetime, timedelta

                next_run = datetime.now().replace(hour=hour, minute=minute, second=0)
                if next_run <= datetime.now():
                    next_run += timedelta(days=1)

                self.scheduler.add_job(
                    self.send_reminder,
                    "date",
                    run_date=next_run,
                    args=[reminder["id"], guild_id],
                    job_id=job_id
                )

            logger.info(f"Reminder {reminder['id']} scheduled")
        except Exception as e:
            logger.error(f"Error scheduling reminder {reminder['id']}: {e}")


async def setup(bot):
    pass
