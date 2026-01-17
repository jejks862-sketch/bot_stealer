import discord
from discord.ext import commands
from discord import app_commands
from utils.database import Database
from utils.scheduler import ReminderScheduler
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class RecurringView(discord.ui.View):
    def __init__(self, callback):
        super().__init__(timeout=300)
        self.callback = callback

    @discord.ui.button(label="Да", style=discord.ButtonStyle.green)
    async def yes_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.callback(interaction, True)

    @discord.ui.button(label="Нет", style=discord.ButtonStyle.red)
    async def no_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.callback(interaction, False)


class RolesSkipView(discord.ui.View):
    def __init__(self, callback):
        super().__init__(timeout=300)
        self.callback = callback

    @discord.ui.button(label="Пропустить", style=discord.ButtonStyle.gray)
    async def skip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.callback(interaction)


class ReminderEditView(discord.ui.View):
    def __init__(self, db, bot, reminder_id: int, user: discord.User):
        super().__init__(timeout=600)
        self.db = db
        self.bot = bot
        self.reminder_id = reminder_id
        self.user = user
        self.editing = None

    @discord.ui.button(label="⏰ Изменить время", style=discord.ButtonStyle.primary)
    async def edit_time(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            await interaction.response.send_message("❌ Ты не можешь это делать", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="⏰ Изменение времени",
            description="Напиши новое время в формате HH:MM (например, 14:30)",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed)
        self.editing = "time"

    @discord.ui.button(label="📝 Изменить имя", style=discord.ButtonStyle.primary)
    async def edit_name(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            await interaction.response.send_message("❌ Ты не можешь это делать", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="📝 Изменение названия",
            description="Напиши новое название напоминания",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed)
        self.editing = "name"

    @discord.ui.button(label="💬 Изменить сообщение", style=discord.ButtonStyle.primary)
    async def edit_message(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            await interaction.response.send_message("❌ Ты не можешь это делать", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="💬 Изменение сообщения",
            description="Напиши новое сообщение напоминания",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed)
        self.editing = "message"

    @discord.ui.button(label="➕ Добавить роли", style=discord.ButtonStyle.success)
    async def add_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            await interaction.response.send_message("❌ Ты не можешь это делать", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="➕ Добавление ролей",
            description="Напиши ID ролей через запятую (например: 123456789,987654321)",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed)
        self.editing = "add_roles"

    @discord.ui.button(label="➖ Удалить роли", style=discord.ButtonStyle.danger)
    async def remove_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            await interaction.response.send_message("❌ Ты не можешь это делать", ephemeral=True)
            return
        
        reminder = self.db.get_reminder(self.reminder_id)
        if not reminder:
            await interaction.response.send_message("❌ Напоминание не найдено", ephemeral=True)
            return
        
        role_ids = reminder.get("role_ids", [])
        if not role_ids and reminder.get("role_id"):
            role_ids = [reminder["role_id"]]
        
        if not role_ids:
            await interaction.response.send_message("❌ В этом напоминании нет ролей для удаления", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="➖ Удаление ролей",
            description="Напиши ID ролей которые хочешь удалить через запятую",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="Текущие роли:",
            value=", ".join(f"<@&{rid}>" for rid in role_ids),
            inline=False
        )
        await interaction.response.send_message(embed=embed)
        self.editing = "remove_roles"


class AdminCog(commands.Cog):
    def __init__(self, bot, db: Database, scheduler: ReminderScheduler, admin_ids: list):
        self.bot = bot
        self.db = db
        self.scheduler = scheduler
        self.admin_ids = admin_ids
        self.setup_conversations = {}

    def is_admin(self, user_id: int):
        return user_id in self.admin_ids

    def check_admin(self):
        async def predicate(interaction: discord.Interaction):
            if not self.is_admin(interaction.user.id):
                await interaction.response.send_message("❌ У вас нет прав для использования этого бота.")
                return False
            return True
        return commands.check(predicate)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == self.bot.user:
            return

        if isinstance(message.channel, discord.DMChannel):
            if not self.is_admin(message.author.id):
                return

            user_id = message.author.id

            if user_id in self.setup_conversations:
                await self.handle_setup_step(message)
                return

    @app_commands.command(name="addrem", description="Создать новое напоминание")
    async def addrem(self, interaction: discord.Interaction):
        if not self.is_admin(interaction.user.id):
            await interaction.response.send_message("❌ У вас нет прав для использования этого бота.")
            return

        user_id = interaction.user.id
        self.setup_conversations[user_id] = {"step": "name", "role_ids": [], "channel_id": None}

        embed = discord.Embed(
            title="➕ Создание напоминания",
            description="Шаг 1 из 6",
            color=discord.Color.green()
        )
        embed.add_field(name="Шаг 1", value="Введи название для напоминания (в ДМ)")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="remlist", description="Показать все напоминания")
    async def remlist(self, interaction: discord.Interaction):
        if not self.is_admin(interaction.user.id):
            await interaction.response.send_message("❌ У вас нет прав для использования этого бота.")
            return

        reminders = self.db.get_reminders()

        if not reminders:
            embed = discord.Embed(
                title="📋 Напоминания",
                description="Напоминаний не найдено",
                color=discord.Color.orange()
            )
            await interaction.response.send_message(embed=embed)
            return

        embed = discord.Embed(title="📋 Все напоминания", color=discord.Color.blue())

        for reminder in reminders:
            status = "✅ Включено" if reminder["enabled"] else "❌ Выключено"
            recurring = "🔄 Постоянное" if reminder["is_recurring"] else "⏰ Одноразовое"

            field_value = (
                f"**ID:** {reminder['id']}\n"
                f"**Время:** {reminder['time']}\n"
                f"**Статус:** {status}\n"
                f"**Тип:** {recurring}\n"
                f"**Сообщение:** {reminder['message'][:100]}..."
            )
            embed.add_field(name=reminder["name"], value=field_value, inline=False)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="delrem", description="Удалить напоминание")
    @app_commands.describe(reminder_id="ID напоминания для удаления")
    async def delrem(self, interaction: discord.Interaction, reminder_id: int):
        if not self.is_admin(interaction.user.id):
            await interaction.response.send_message("❌ У вас нет прав для использования этого бота.")
            return

        self.db.delete_reminder(reminder_id)
        self.scheduler.remove_job(f"reminder_{reminder_id}")
        await interaction.response.send_message(f"✅ Напоминание #{reminder_id} удалено")

    @app_commands.command(name="remoff", description="Включить/выключить напоминание")
    @app_commands.describe(reminder_id="ID напоминания")
    async def remoff(self, interaction: discord.Interaction, reminder_id: int):
        if not self.is_admin(interaction.user.id):
            await interaction.response.send_message("❌ У вас нет прав для использования этого бота.")
            return

        reminder = self.db.toggle_reminder(reminder_id)
        if reminder:
            status = "✅ Включено" if reminder["enabled"] else "❌ Выключено"
            await interaction.response.send_message(f"Напоминание #{reminder_id} теперь {status}")
        else:
            await interaction.response.send_message(f"❌ Напоминание #{reminder_id} не найдено")

    @app_commands.command(name="seerem", description="Просмотреть и редактировать напоминание")
    @app_commands.describe(reminder_id="ID напоминания")
    async def seerem(self, interaction: discord.Interaction, reminder_id: int):
        if not self.is_admin(interaction.user.id):
            await interaction.response.send_message("❌ У вас нет прав для использования этого бота.")
            return

        reminder = self.db.get_reminder(reminder_id)
        if not reminder:
            await interaction.response.send_message(f"❌ Напоминание #{reminder_id} не найдено")
            return

        embed = discord.Embed(
            title=f"📌 Напоминание #{reminder_id}",
            color=discord.Color.blue()
        )
        embed.add_field(name="Название", value=reminder["name"], inline=False)
        embed.add_field(name="Сообщение", value=reminder["message"][:1024], inline=False)
        embed.add_field(name="Время", value=reminder["time"], inline=True)
        embed.add_field(
            name="Статус",
            value="✅ Включено" if reminder["enabled"] else "❌ Выключено",
            inline=True
        )
        embed.add_field(
            name="Тип",
            value="🔄 Постоянное" if reminder["is_recurring"] else "⏰ Одноразовое",
            inline=True
        )
        
        role_ids = reminder.get("role_ids", [])
        if not role_ids and reminder.get("role_id"):
            role_ids = [reminder["role_id"]]
        
        if role_ids:
            roles_text = ", ".join(f"<@&{rid}>" for rid in role_ids)
            embed.add_field(name="Роли для упоминания", value=roles_text, inline=False)

        view = ReminderEditView(self.db, self.bot, reminder_id, interaction.user)
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="help", description="Показать справку по командам")
    async def help(self, interaction: discord.Interaction):
        if not self.is_admin(interaction.user.id):
            await interaction.response.send_message("❌ У вас нет прав для использования этого бота.")
            return

        embed = discord.Embed(
            title="📋 Команды администратора",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="/addrem",
            value="Создать новое напоминание",
            inline=False
        )
        embed.add_field(
            name="/remlist",
            value="Посмотреть все напоминания",
            inline=False
        )
        embed.add_field(
            name="/delrem",
            value="Удалить напоминание",
            inline=False
        )
        embed.add_field(
            name="/remoff",
            value="Включить/выключить напоминание",
            inline=False
        )
        embed.add_field(
            name="/seerem",
            value="Просмотреть и редактировать напоминание",
            inline=False
        )
        embed.add_field(
            name="/activity",
            value="Посмотреть активность пользователей",
            inline=False
        )
        embed.add_field(
            name="/ai",
            value="Спросить у ИИ",
            inline=False
        )
        embed.add_field(
            name="/help",
            value="Показать эту справку",
            inline=False
        )
        embed.add_field(
            name="/zov",
            value="Отправить объявление",
            inline=False
        )
        embed.add_field(
            name="/mystats",
            value="Показать свою статистику уровня",
            inline=False
        )
        embed.add_field(
            name="/top",
            value="Показать топ игроков по уровню",
            inline=False
        )
        embed.add_field(
            name="/confstats",
            value="Настроить цвета карточки статистики",
            inline=False
        )
        await interaction.response.send_message(embed=embed)

    async def handle_roles_skip(self, interaction: discord.Interaction, user_id: int):
        conversation = self.setup_conversations.get(user_id)
        if not conversation:
            await interaction.response.send_message("❌ Ошибка: сессия истекла", ephemeral=True)
            return
        
        conversation["role_ids"] = []
        conversation["step"] = "channel"
        
        embed = discord.Embed(
            title="➕ Создание напоминания",
            description="Шаг 6 из 6",
            color=discord.Color.green()
        )
        embed.add_field(
            name="Шаг 6",
            value="Укажи ID канала для отправки напоминания"
        )
        await interaction.response.send_message(embed=embed)

    async def handle_recurring_choice(self, interaction: discord.Interaction, user_id: int, is_recurring: bool):
        conversation = self.setup_conversations.get(user_id)
        if not conversation:
            await interaction.response.send_message("❌ Ошибка: сессия истекла", ephemeral=True)
            return

        conversation["is_recurring"] = is_recurring
        conversation["step"] = "roles"

        embed = discord.Embed(
            title="➕ Создание напоминания",
            description="Шаг 5 из 6",
            color=discord.Color.green()
        )
        embed.add_field(
            name="Шаг 5",
            value="Укажи ID ролей через запятую для упоминания (или нажми 'Пропустить').\nПример: 123456789,987654321"
        )
        view = RolesSkipView(lambda interaction: self.handle_roles_skip(interaction, user_id))
        await interaction.response.send_message(embed=embed, view=view)


    async def handle_setup_step(self, message: discord.Message):
        user_id = message.author.id
        conversation = self.setup_conversations.get(user_id)
        if not conversation:
            return
        
        step = conversation.get("step")

        if step == "name":
            conversation["name"] = message.content.strip()
            conversation["step"] = "message"
            embed = discord.Embed(
                title="➕ Создание напоминания",
                description="Шаг 2 из 6",
                color=discord.Color.green()
            )
            embed.add_field(name="Шаг 2", value="Введи текст сообщения")
            await message.reply(embed=embed)

        elif step == "message":
            conversation["message"] = message.content.strip()
            conversation["step"] = "time"
            embed = discord.Embed(
                title="➕ Создание напоминания",
                description="Шаг 3 из 6",
                color=discord.Color.green()
            )
            embed.add_field(
                name="Шаг 3",
                value="Введи время в формате HH:MM (например, 12:00)"
            )
            await message.reply(embed=embed)

        elif step == "time":
            try:
                time_str = message.content.strip()
                datetime.strptime(time_str, "%H:%M")
                conversation["time"] = time_str
                conversation["step"] = "recurring"

                embed = discord.Embed(
                    title="➕ Создание напоминания",
                    description="Шаг 4 из 6",
                    color=discord.Color.green()
                )
                embed.add_field(
                    name="Шаг 4",
                    value="Это напоминание повторяющееся?"
                )
                
                view = RecurringView(lambda interaction, is_recurring:
                    self.handle_recurring_choice(interaction, user_id, is_recurring))
                
                await message.reply(embed=embed, view=view)
            except ValueError:
                embed = discord.Embed(
                    title="❌ Ошибка",
                    description="Неверный формат времени. Используй HH:MM (например, 12:00)",
                    color=discord.Color.red()
                )
                await message.reply(embed=embed)

        elif step == "roles":
            role_input = message.content.strip()
            role_ids = []
            
            if role_input:
                try:
                    role_ids = [int(rid.strip()) for rid in role_input.split(",")]
                except ValueError:
                    embed = discord.Embed(
                        title="❌ Ошибка",
                        description="ID ролей должны быть числами через запятую. Пример: 123456789,987654321",
                        color=discord.Color.red()
                    )
                    await message.reply(embed=embed)
                    return

            conversation["role_ids"] = role_ids
            conversation["step"] = "channel"
            
            embed = discord.Embed(
                title="➕ Создание напоминания",
                description="Шаг 6 из 6",
                color=discord.Color.green()
            )
            embed.add_field(
                name="Шаг 6",
                value="Укажи ID канала для отправки напоминания"
            )
            await message.reply(embed=embed)

        elif step == "channel":
            try:
                channel_id = int(message.content.strip())
                channel = self.bot.get_channel(channel_id)
                if not channel:
                    embed = discord.Embed(
                        title="❌ Ошибка",
                        description=f"Канал с ID {channel_id} не найден",
                        color=discord.Color.red()
                    )
                    await message.reply(embed=embed)
                    return
                
                conversation["channel_id"] = channel_id
                role_ids = conversation.get("role_ids", [])

                reminder = self.db.add_reminder(
                    name=conversation["name"],
                    message=conversation["message"],
                    time=conversation["time"],
                    is_recurring=conversation["is_recurring"],
                    role_id=role_ids[0] if role_ids else None
                )

                reminder["role_ids"] = role_ids
                reminder["channel_id"] = channel_id
                
                self.db.update_reminder_roles(reminder["id"], role_ids)
                reminders_data = self.db._load_reminders()
                for r in reminders_data["reminders"]:
                    if r["id"] == reminder["id"]:
                        r["channel_id"] = channel_id
                self.db._save_reminders(reminders_data)

                from cogs.notifications import NotificationsCog
                notifications_cog = self.bot.get_cog("NotificationsCog")
                if notifications_cog and self.bot.guilds:
                    notifications_cog.schedule_reminder(reminder, self.bot.guilds[0].id)

                embed = discord.Embed(
                    title="✅ Напоминание создано!",
                    color=discord.Color.green()
                )
                embed.add_field(name="ID", value=reminder["id"])
                embed.add_field(name="Название", value=reminder["name"])
                embed.add_field(name="Время", value=reminder["time"])
                embed.add_field(
                    name="Тип",
                    value="🔄 Постоянное" if conversation["is_recurring"] else "⏰ Одноразовое"
                )
                embed.add_field(name="Канал", value=f"<#{channel_id}>")
                if role_ids:
                    embed.add_field(name="Роли для упоминания", value=", ".join(f"<@&{rid}>" for rid in role_ids))
                embed.add_field(name="Сообщение", value=reminder["message"])

                await message.reply(embed=embed)
                del self.setup_conversations[user_id]
            except ValueError:
                embed = discord.Embed(
                    title="❌ Ошибка",
                    description="ID канала должен быть числом",
                    color=discord.Color.red()
                )
                await message.reply(embed=embed)

    @app_commands.command(name="zov", description="Отправить объявление")
    @app_commands.describe(
        text="Текст объявления",
        channel_id="ID канала для отправки",
        roles="ID ролей через запятую для упоминания (опционально)"
    )
    async def zov(self, interaction: discord.Interaction, text: str, channel_id: str, roles: str = None):
        if not self.is_admin(interaction.user.id):
            await interaction.response.send_message("❌ У вас нет прав для использования этого бота.")
            return

        try:
            try:
                channel_id = int(channel_id)
            except ValueError:
                await interaction.response.send_message("❌ ID канала должен быть числом")
                return
                
            channel = self.bot.get_channel(channel_id)
            if not channel:
                await interaction.response.send_message(f"❌ Канал с ID {channel_id} не найден")
                return

            role_mentions = ""
            if roles:
                try:
                    role_ids = [int(rid.strip()) for rid in roles.split(",")]
                    guild = channel.guild
                    mentions = []
                    for rid in role_ids:
                        role = guild.get_role(rid)
                        if role:
                            mentions.append(role.mention)
                    role_mentions = " ".join(mentions) if mentions else ""
                except ValueError:
                    await interaction.response.send_message("❌ ID ролей должны быть числами через запятую")
                    return

            embed = discord.Embed(
                title="📢 Объявление",
                description=text,
                color=discord.Color.gold()
            )
            embed.set_footer(text=f"От: {interaction.user.name}")
            
            if role_mentions:
                await channel.send(role_mentions, embed=embed)
            else:
                await channel.send(embed=embed)
            
            await interaction.response.send_message(f"✅ Объявление отправлено в <#{channel_id}>")

        except Exception as e:
            logger.error(f"Error in zov command: {e}")
            await interaction.response.send_message(f"❌ Ошибка: {str(e)}")


async def setup(bot):
    pass
