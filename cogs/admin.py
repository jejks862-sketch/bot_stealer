import discord
from discord.ext import commands
from discord import app_commands, TextStyle
from utils.database import Database
import os

_admin_ids_str = os.getenv("ADMIN_IDS", "").strip()
ADMIN_IDS = list(map(int, _admin_ids_str.split(","))) if _admin_ids_str else []


class AdminCog(commands.Cog):
    def __init__(self, bot, db: Database, scheduler=None, admin_ids=None):
        self.bot = bot
        self.db = db
        self.scheduler = scheduler
        self.admin_ids = admin_ids or ADMIN_IDS

    def is_admin(self, user_id: int) -> bool:
        return user_id in self.admin_ids

    @app_commands.command(name="help", description="Показать справку по командам")
    async def help_cmd(self, interaction: discord.Interaction):
        is_admin = self.is_admin(interaction.user.id)
        
        embed = discord.Embed(title="📋 Команды бота", color=discord.Color.blue())
        
        embed.add_field(name="/ai", value="Спросить у ИИ", inline=False)
        embed.add_field(name="/mystats", value="Показать свою статистику уровня", inline=False)
        embed.add_field(name="/top", value="Показать топ игроков по уровню", inline=False)
        embed.add_field(name="/zov", value="Отправить объявление", inline=False)
        embed.add_field(name="/confstats", value="Настроить цвета карточки статистики", inline=False)
        
        if is_admin:
            embed.add_field(name="\n🔐 Админ команды:", value="‎", inline=False)
            embed.add_field(name="/settings", value="Управление сервером (каналы, роли, юзеры)", inline=False)
            embed.add_field(name="/activity", value="Посмотреть активность пользователей", inline=False)
            embed.add_field(name="/addrem", value="Создать новое напоминание", inline=False)
            embed.add_field(name="/remlist", value="Посмотреть и управлять напоминаниями", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)

    async def get_admin_guilds(self, interaction: discord.Interaction) -> list:
        """Получить список серверов где пользователь админ"""
        user_guilds = self.db.get_user_guilds(interaction.user.id)
        guild_ids = [g["guild_id"] for g in user_guilds]
        
        available_guilds = []
        for guild_id in guild_ids:
            try:
                guild = self.bot.get_guild(guild_id)
                if guild:
                    available_guilds.append((guild_id, guild.name, guild))
            except:
                pass
        
        return available_guilds

    async def show_guild_select(self, interaction: discord.Interaction, callback, callback_name: str):
        """Показать выбор сервера для админа"""
        guilds = await self.get_admin_guilds(interaction)
        
        if not guilds:
            await interaction.response.send_message("❌ Ты не админ ни на одном сервере", ephemeral=False)
            return
        
        if len(guilds) == 1:
            await callback(interaction, guilds[0][0], guilds[0][2])
            return
        
        guild_options = [discord.SelectOption(label=name[:100], value=str(gid)) for gid, name, _ in guilds]
        
        class GuildSelect(discord.ui.Select):
            def __init__(self, callback_func, guild_dict):
                super().__init__(placeholder="Выбери сервер", options=guild_options)
                self.callback_func = callback_func
                self.guild_dict = guild_dict
            
            async def callback(self, select_interaction: discord.Interaction):
                guild_id = int(self.values[0])
                guild = self.guild_dict[guild_id]
                await self.callback_func(select_interaction, guild_id, guild)
        
        guild_dict = {gid: g for gid, _, g in guilds}
        view = discord.ui.View()
        view.add_item(GuildSelect(callback, guild_dict))
        await interaction.response.send_message(f"Выбери сервер для команды `/{callback_name}`:", view=view, ephemeral=False)

    @app_commands.command(name="addrem", description="Создать новое напоминание")
    async def addrem(self, interaction: discord.Interaction):
        if not self.is_admin(interaction.user.id):
            await interaction.response.send_message("❌ У вас нет прав.", ephemeral=False)
            return
        
        async def addrem_callback(int_interaction: discord.Interaction, guild_id: int, guild: discord.Guild):
            class ReminderModal(discord.ui.Modal):
                def __init__(self, admin_cog, guild_obj):
                    super().__init__(title="Создание напоминания")
                    self.admin_cog = admin_cog
                    self.guild_obj = guild_obj
                    
                    self.name_input = discord.ui.TextInput(label="Название", max_length=100)
                    self.message_input = discord.ui.TextInput(label="Текст напоминания", style=TextStyle.long)
                    self.time_input = discord.ui.TextInput(label="Время (HH:MM)", max_length=5)
                    self.recurring_input = discord.ui.TextInput(label="Повторяется каждый день? (да/нет)", max_length=3)
                    
                    self.add_item(self.name_input)
                    self.add_item(self.message_input)
                    self.add_item(self.time_input)
                    self.add_item(self.recurring_input)
                
                async def on_submit(self, modal_interaction: discord.Interaction):
                    try:
                        name = self.name_input.value
                        message = self.message_input.value
                        time_str = self.time_input.value
                        recurring_str = self.recurring_input.value.lower()
                        
                        if ":" not in time_str or len(time_str.split(":")) != 2:
                            await modal_interaction.response.send_message("❌ Неверный формат времени (используй HH:MM)", ephemeral=False)
                            return
                        
                        is_recurring = recurring_str in ["да", "yes", "true", "1"]
                        
                        all_channels = self.guild_obj.text_channels
                        if not all_channels:
                            await modal_interaction.response.send_message("❌ На сервере нет текстовых каналов", ephemeral=False)
                            return
                        
                        channels_per_page = 24
                        total_pages = (len(all_channels) + channels_per_page - 1) // channels_per_page
                        
                        def get_channel_page(page_num=0):
                            start = page_num * channels_per_page
                            end = start + channels_per_page
                            return all_channels[start:end]
                        
                        current_channel_page = 0
                        channels = get_channel_page(current_channel_page)
                        channel_options = [discord.SelectOption(label=ch.name[:100], value=str(ch.id)) for ch in channels]
                        
                        class ChannelSelect(discord.ui.Select):
                            def __init__(self, guild_obj, admin_cog):
                                super().__init__(placeholder="Выбери канал", options=channel_options)
                                self.guild_obj = guild_obj
                                self.admin_cog = admin_cog
                            
                            async def callback(self, ch_interaction: discord.Interaction):
                                channel_id = int(self.values[0])
                                
                                all_roles = [r for r in self.guild_obj.roles if r.name != "@everyone"]
                                roles_per_page = 24
                                total_role_pages = (len(all_roles) + roles_per_page - 1) // roles_per_page
                                
                                def get_role_page(page_num=0):
                                    start = page_num * roles_per_page
                                    end = start + roles_per_page
                                    return all_roles[start:end]
                                
                                current_role_page = 0
                                roles = get_role_page(current_role_page)
                                role_options = [discord.SelectOption(label=r.name[:100], value=str(r.id)) for r in roles]
                                
                                class RoleSelect(discord.ui.Select):
                                    def __init__(self, admin_cog):
                                        if role_options:
                                            super().__init__(placeholder="Выбери роли (опционально)", options=role_options, min_values=0, max_values=min(5, len(role_options)))
                                        else:
                                            super().__init__(placeholder="Нет ролей", options=[discord.SelectOption(label="Нет", value="0")], disabled=True)
                                        self.admin_cog = admin_cog
                                    
                                    async def callback(self, role_interaction: discord.Interaction):
                                        role_ids = [int(r) for r in self.values if r != "0"] if self.values else []
                                        
                                        reminder = self.admin_cog.db.create_reminder(name, message, time_str, is_recurring, channel_id, role_ids)
                                        # Schedule the reminder
                                        notifications_cog = self.admin_cog.bot.get_cog("NotificationsCog")
                                        if notifications_cog and reminder:
                                            notifications_cog.schedule_reminder(reminder, self.guild_obj.id)
                                        await role_interaction.response.send_message("✅ Напоминание создано", ephemeral=False)
                                
                                async def show_role_page(interaction, page_num):
                                    page_roles = get_role_page(page_num)
                                    page_role_options = [discord.SelectOption(label=r.name[:100], value=str(r.id)) for r in page_roles]
                                    
                                    class RoleSelectPaginated(discord.ui.Select):
                                        def __init__(self, admin_cog):
                                            if page_role_options:
                                                super().__init__(placeholder="Выбери роли (опционально)", options=page_role_options, min_values=0, max_values=min(5, len(page_role_options)))
                                            else:
                                                super().__init__(placeholder="Нет ролей", options=[discord.SelectOption(label="Нет", value="0")], disabled=True)
                                            self.admin_cog = admin_cog
                                        
                                        async def callback(self, role_inter: discord.Interaction):
                                            role_ids = [int(r) for r in self.values if r != "0"] if self.values else []
                                            reminder_id = self.admin_cog.db.create_reminder(name, message, time_str, is_recurring, channel_id, role_ids)
                                            await role_inter.response.send_message("✅ Напоминание создано", ephemeral=False)
                                    
                                    view = discord.ui.View()
                                    view.add_item(RoleSelectPaginated(self.admin_cog))
                                    
                                    if total_role_pages > 1:
                                        if page_num > 0:
                                            prev_btn = discord.ui.Button(label="← Пред.", style=discord.ButtonStyle.secondary)
                                            async def prev_cb(btn_inter):
                                                await btn_inter.response.defer()
                                                await show_role_page(btn_inter, page_num - 1)
                                            prev_btn.callback = prev_cb
                                            view.add_item(prev_btn)
                                        
                                        if page_num < total_role_pages - 1:
                                            next_btn = discord.ui.Button(label="Далее →", style=discord.ButtonStyle.secondary)
                                            async def next_cb(btn_inter):
                                                await btn_inter.response.defer()
                                                await show_role_page(btn_inter, page_num + 1)
                                            next_btn.callback = next_cb
                                            view.add_item(next_btn)
                                    
                                    if ch_interaction == interaction:
                                        await interaction.response.send_message(f"Выбери роли (страница {page_num + 1}/{total_role_pages}):", view=view, ephemeral=False)
                                    else:
                                        await interaction.followup.send(f"Выбери роли (страница {page_num + 1}/{total_role_pages}):", view=view, ephemeral=False)
                                
                                await show_role_page(ch_interaction, current_role_page)
                        
                        async def show_channel_page(interaction, page_num):
                            page_channels = get_channel_page(page_num)
                            page_channel_options = [discord.SelectOption(label=ch.name[:100], value=str(ch.id)) for ch in page_channels]
                            
                            class ChannelSelectPaginated(discord.ui.Select):
                                def __init__(self, guild_obj, admin_cog):
                                    super().__init__(placeholder="Выбери канал", options=page_channel_options)
                                    self.guild_obj = guild_obj
                                    self.admin_cog = admin_cog
                                
                                async def callback(self, ch_inter: discord.Interaction):
                                    channel_id = int(self.values[0])
                                    # Повторяем логику выбора ролей
                                    all_roles = [r for r in self.guild_obj.roles if r.name != "@everyone"]
                                    roles_per_page = 24
                                    total_role_pages = (len(all_roles) + roles_per_page - 1) // roles_per_page
                                    
                                    def get_role_page(page_num=0):
                                        start = page_num * roles_per_page
                                        end = start + roles_per_page
                                        return all_roles[start:end]
                                    
                                    async def show_role_page_inner(interaction, page_num):
                                        page_roles = get_role_page(page_num)
                                        page_role_options = [discord.SelectOption(label=r.name[:100], value=str(r.id)) for r in page_roles]
                                        
                                        class RoleSelectPaginated(discord.ui.Select):
                                            def __init__(self, admin_cog):
                                                if page_role_options:
                                                    super().__init__(placeholder="Выбери роли (опционально)", options=page_role_options, min_values=0, max_values=min(5, len(page_role_options)))
                                                else:
                                                    super().__init__(placeholder="Нет ролей", options=[discord.SelectOption(label="Нет", value="0")], disabled=True)
                                                self.admin_cog = admin_cog
                                            
                                            async def callback(self, role_inter: discord.Interaction):
                                                role_ids = [int(r) for r in self.values if r != "0"] if self.values else []
                                                reminder = self.admin_cog.db.create_reminder(name, message, time_str, is_recurring, channel_id, role_ids)
                                                # Schedule the reminder
                                                notifications_cog = self.admin_cog.bot.get_cog("NotificationsCog")
                                                if notifications_cog and reminder:
                                                    notifications_cog.schedule_reminder(reminder, self.guild_obj.id)
                                                await role_inter.response.send_message("✅ Напоминание создано", ephemeral=False)
                                        
                                        view = discord.ui.View()
                                        view.add_item(RoleSelectPaginated(self.admin_cog))
                                        
                                        skip_btn = discord.ui.Button(label="Пропустить", style=discord.ButtonStyle.secondary)
                                        async def skip_cb(skip_inter):
                                            reminder = self.admin_cog.db.create_reminder(name, message, time_str, is_recurring, channel_id, [])
                                            # Schedule the reminder
                                            notifications_cog = self.admin_cog.bot.get_cog("NotificationsCog")
                                            if notifications_cog and reminder:
                                                notifications_cog.schedule_reminder(reminder, self.guild_obj.id)
                                            await skip_inter.response.send_message("✅ Напоминание создано", ephemeral=False)
                                        skip_btn.callback = skip_cb
                                        view.add_item(skip_btn)
                                        
                                        if total_role_pages > 1:
                                            if page_num > 0:
                                                prev_btn = discord.ui.Button(label="← Пред.", style=discord.ButtonStyle.secondary)
                                                async def prev_cb(btn_inter):
                                                    await btn_inter.response.defer()
                                                    await show_role_page_inner(btn_inter, page_num - 1)
                                                prev_btn.callback = prev_cb
                                                view.add_item(prev_btn)
                                            
                                            if page_num < total_role_pages - 1:
                                                next_btn = discord.ui.Button(label="Далее →", style=discord.ButtonStyle.secondary)
                                                async def next_cb(btn_inter):
                                                    await btn_inter.response.defer()
                                                    await show_role_page_inner(btn_inter, page_num + 1)
                                                next_btn.callback = next_cb
                                                view.add_item(next_btn)
                                        
                                        if ch_inter == interaction:
                                            await interaction.response.send_message(f"Выбери роли (страница {page_num + 1}/{total_role_pages}):", view=view, ephemeral=False)
                                        else:
                                            await interaction.followup.send(f"Выбери роли (страница {page_num + 1}/{total_role_pages}):", view=view, ephemeral=False)
                                    
                                    await show_role_page_inner(ch_inter, 0)
                            
                            view = discord.ui.View()
                            view.add_item(ChannelSelectPaginated(self.guild_obj, self.admin_cog))
                            
                            if total_pages > 1:
                                if page_num > 0:
                                    prev_btn = discord.ui.Button(label="← Пред.", style=discord.ButtonStyle.secondary)
                                    async def prev_cb(btn_inter):
                                        await btn_inter.response.defer()
                                        await show_channel_page(btn_inter, page_num - 1)
                                    prev_btn.callback = prev_cb
                                    view.add_item(prev_btn)
                                
                                if page_num < total_pages - 1:
                                    next_btn = discord.ui.Button(label="Далее →", style=discord.ButtonStyle.secondary)
                                    async def next_cb(btn_inter):
                                        await btn_inter.response.defer()
                                        await show_channel_page(btn_inter, page_num + 1)
                                    next_btn.callback = next_cb
                                    view.add_item(next_btn)
                            
                            if modal_interaction == interaction:
                                await interaction.response.send_message(f"Выбери канал (страница {page_num + 1}/{total_pages}):", view=view, ephemeral=False)
                            else:
                                await interaction.followup.send(f"Выбери канал (страница {page_num + 1}/{total_pages}):", view=view, ephemeral=False)
                        
                        await show_channel_page(modal_interaction, current_channel_page)
                    
                    except Exception as e:
                        await modal_interaction.response.send_message(f"❌ Ошибка: {str(e)}", ephemeral=False)
            
            await int_interaction.response.send_modal(ReminderModal(self, guild))
        
        await self.show_guild_select(interaction, addrem_callback, "addrem")

    @app_commands.command(name="remlist", description="Список напоминаний с управлением")
    async def remlist(self, interaction: discord.Interaction):
        if not self.is_admin(interaction.user.id):
            await interaction.response.send_message("❌ У вас нет прав.", ephemeral=False)
            return
        
        async def remlist_callback(int_interaction: discord.Interaction, guild_id: int, guild: discord.Guild):
            reminders = self.db.get_reminders()
            if not reminders:
                await int_interaction.response.send_message("❌ Нет напоминаний", ephemeral=False)
                return
            
            total_pages = len(reminders)
            
            async def show_page(page_interaction, page=0):
                if page >= total_pages:
                    page = total_pages - 1
                if page < 0:
                    page = 0
                
                reminder = reminders[page]
                
                embed = discord.Embed(
                    title=f"📋 Напоминание: {reminder['name']} (стр. {page + 1}/{total_pages})",
                    color=discord.Color.blue()
                )
                embed.add_field(name="Текст", value=reminder["message"][:256], inline=False)
                embed.add_field(name="Время", value=reminder["time"], inline=True)
                embed.add_field(name="Статус", value="✅ Включено" if reminder["enabled"] else "❌ Отключено", inline=True)
                embed.add_field(name="Повтор", value="✅ Ежедневно" if reminder["is_recurring"] else "❌ Один раз", inline=True)
                
                view = discord.ui.View()
                
                toggle_btn = discord.ui.Button(label=f"{'✅ Выключить' if reminder['enabled'] else '❌ Включить'}", style=discord.ButtonStyle.primary)
                async def toggle_cb(btn_i):
                    self.db.cursor.execute('UPDATE reminders SET enabled = ? WHERE id = ?', (1 - reminder['enabled'], reminder['id']))
                    self.db.conn.commit()
                    reminders[page]['enabled'] = 1 - reminder['enabled']
                    
                    # Reschedule or remove job based on new state
                    job_id = f"reminder_{reminder['id']}"
                    new_enabled_state = 1 - reminder['enabled']
                    
                    if new_enabled_state:
                        # Schedule the reminder
                        updated_reminder = self.db.get_reminder(reminder['id'])
                        if updated_reminder:
                            notifications_cog = self.bot.get_cog("NotificationsCog")
                            if notifications_cog:
                                try:
                                    self.scheduler.remove_job(job_id)
                                except:
                                    pass
                                notifications_cog.schedule_reminder(updated_reminder, guild.id)
                    else:
                        # Remove from scheduler
                        try:
                            self.scheduler.remove_job(job_id)
                        except:
                            pass
                    
                    await btn_i.response.defer()
                    await show_page(btn_i, page)
                toggle_btn.callback = toggle_cb
                view.add_item(toggle_btn)
                
                edit_btn = discord.ui.Button(label="✏️ Редактировать", style=discord.ButtonStyle.secondary)
                async def edit_cb(btn_i):
                    class EditModal(discord.ui.Modal):
                        def __init__(self, admin_cog, guild_obj, rem_id, old_reminder):
                            super().__init__(title="Редактирование напоминания")
                            self.admin_cog = admin_cog
                            self.guild_obj = guild_obj
                            self.rem_id = rem_id
                            self.old_reminder = old_reminder
                            
                            self.name_input = discord.ui.TextInput(label="Название", max_length=100, default=old_reminder['name'])
                            self.message_input = discord.ui.TextInput(label="Текст напоминания", style=TextStyle.long, default=old_reminder['message'])
                            self.time_input = discord.ui.TextInput(label="Время (HH:MM)", max_length=5, default=old_reminder['time'])
                            self.recurring_input = discord.ui.TextInput(label="Повторяется каждый день? (да/нет)", max_length=3, default="да" if old_reminder['is_recurring'] else "нет")
                            
                            self.add_item(self.name_input)
                            self.add_item(self.message_input)
                            self.add_item(self.time_input)
                            self.add_item(self.recurring_input)
                        
                        async def on_submit(self, modal_interaction: discord.Interaction):
                            try:
                                name = self.name_input.value
                                message = self.message_input.value
                                time_str = self.time_input.value
                                recurring_str = self.recurring_input.value.lower()
                                
                                if ":" not in time_str or len(time_str.split(":")) != 2:
                                    await modal_interaction.response.send_message("❌ Неверный формат времени (используй HH:MM)", ephemeral=False)
                                    return
                                
                                is_recurring = recurring_str in ["да", "yes", "true", "1"]
                                
                                channels = self.guild_obj.text_channels[:25]
                                if not channels:
                                    await modal_interaction.response.send_message("❌ На сервере нет текстовых каналов", ephemeral=False)
                                    return
                                
                                channel_options = [discord.SelectOption(label=ch.name[:100], value=str(ch.id), default=ch.id == self.old_reminder['channel_id']) for ch in channels]
                                
                                class ChannelSelect(discord.ui.Select):
                                    def __init__(self, guild_obj, admin_cog, rem_id):
                                        super().__init__(placeholder="Выбери канал", options=channel_options)
                                        self.guild_obj = guild_obj
                                        self.admin_cog = admin_cog
                                        self.rem_id = rem_id
                                    
                                    async def callback(self, ch_interaction: discord.Interaction):
                                        channel_id = int(self.values[0])
                                        
                                        role_options = [discord.SelectOption(label=r.name[:100], value=str(r.id)) for r in self.guild_obj.roles if r.name != "@everyone"][:25]
                                        
                                        class RoleSelect(discord.ui.Select):
                                            def __init__(self, admin_cog, rem_id):
                                                if role_options:
                                                    super().__init__(placeholder="Выбери роли (опционально)", options=role_options, min_values=0, max_values=min(5, len(role_options)))
                                                else:
                                                    super().__init__(placeholder="Нет ролей", options=[discord.SelectOption(label="Нет", value="0")], disabled=True)
                                                self.admin_cog = admin_cog
                                                self.rem_id = rem_id
                                            
                                            async def callback(self, role_interaction: discord.Interaction):
                                                role_ids = [int(r) for r in self.values if r != "0"] if self.values else []
                                                
                                                self.admin_cog.db.cursor.execute('UPDATE reminders SET name=?, message=?, time=?, is_recurring=?, channel_id=? WHERE id=?',
                                                    (name, message, time_str, is_recurring, channel_id, self.rem_id))
                                                self.admin_cog.db.cursor.execute('DELETE FROM reminder_roles WHERE reminder_id = ?', (self.rem_id,))
                                                for role_id in role_ids:
                                                    self.admin_cog.db.cursor.execute('INSERT INTO reminder_roles (reminder_id, role_id) VALUES (?, ?)', (self.rem_id, role_id))
                                                self.admin_cog.db.conn.commit()
                                                
                                                reminders[page]['name'] = name
                                                reminders[page]['message'] = message
                                                reminders[page]['time'] = time_str
                                                reminders[page]['is_recurring'] = is_recurring
                                                reminders[page]['channel_id'] = channel_id
                                                
                                                # Reschedule the reminder with new settings
                                                updated_reminder = self.admin_cog.db.get_reminder(self.rem_id)
                                                if updated_reminder:
                                                    notifications_cog = self.admin_cog.bot.get_cog("NotificationsCog")
                                                    if notifications_cog:
                                                        job_id = f"reminder_{self.rem_id}"
                                                        try:
                                                            self.admin_cog.scheduler.remove_job(job_id)
                                                        except:
                                                            pass
                                                        notifications_cog.schedule_reminder(updated_reminder, guild.id)
                                                
                                                await role_interaction.response.send_message("✅ Напоминание обновлено", ephemeral=False)
                                                await show_page(role_interaction, page)
                                        
                                        view = discord.ui.View()
                                        view.add_item(RoleSelect(self.admin_cog, self.rem_id))
                                        await ch_interaction.response.send_message("Выбери роли для упоминания:", view=view, ephemeral=False)
                                
                                view = discord.ui.View()
                                view.add_item(ChannelSelect(self.guild_obj, self.admin_cog, self.rem_id))
                                await modal_interaction.response.send_message("Выбери канал для напоминания:", view=view, ephemeral=False)
                            
                            except Exception as e:
                                await modal_interaction.response.send_message(f"❌ Ошибка: {str(e)}", ephemeral=False)
                    
                    await btn_i.response.send_modal(EditModal(self, guild, reminder['id'], reminder))
                
                edit_btn.callback = edit_cb
                view.add_item(edit_btn)
                
                delete_btn = discord.ui.Button(label="🗑️ Удалить", style=discord.ButtonStyle.danger)
                async def delete_cb(btn_i):
                    # Remove from scheduler first
                    job_id = f"reminder_{reminder['id']}"
                    try:
                        self.scheduler.remove_job(job_id)
                    except:
                        pass
                    
                    self.db.cursor.execute('DELETE FROM reminders WHERE id = ?', (reminder['id'],))
                    self.db.cursor.execute('DELETE FROM reminder_roles WHERE reminder_id = ?', (reminder['id'],))
                    self.db.conn.commit()
                    reminders.pop(page)
                    await btn_i.response.send_message("✅ Напоминание удалено", ephemeral=False)
                    if reminders:
                        await show_page(btn_i, min(page, len(reminders) - 1))
                    else:
                        try:
                            await page_interaction.delete_original_response()
                        except:
                            pass
                delete_btn.callback = delete_cb
                view.add_item(delete_btn)
                
                if page > 0:
                    prev_btn = discord.ui.Button(label="← Пред.", style=discord.ButtonStyle.secondary)
                    async def prev_cb(btn_i):
                        await btn_i.response.defer()
                        await show_page(btn_i, page - 1)
                    prev_btn.callback = prev_cb
                    view.add_item(prev_btn)
                
                if page < total_pages - 1:
                    next_btn = discord.ui.Button(label="Далее →", style=discord.ButtonStyle.secondary)
                    async def next_cb(btn_i):
                        await btn_i.response.defer()
                        await show_page(btn_i, page + 1)
                    next_btn.callback = next_cb
                    view.add_item(next_btn)
                
                if page_interaction == int_interaction:
                    await page_interaction.response.send_message(embed=embed, view=view, ephemeral=False)
                else:
                    await page_interaction.followup.send(embed=embed, view=view, ephemeral=False)
            
            await show_page(int_interaction)
        
        await self.show_guild_select(interaction, remlist_callback, "remlist")

    @app_commands.command(name="zov", description="Сделать объявление на сервере")
    async def zov(self, interaction: discord.Interaction):
        user_guilds = self.db.get_user_guilds(interaction.user.id)
        guild_ids = [g["guild_id"] for g in user_guilds]
        
        available_guilds = []
        for guild_id in guild_ids:
            try:
                guild = self.bot.get_guild(guild_id)
                if guild:
                    available_guilds.append((guild_id, guild.name, guild))
            except:
                pass
        
        if interaction.guild and interaction.guild.id in guild_ids:
            await self.zov_inner(interaction, interaction.guild)
            return
        
        if not available_guilds:
            await interaction.response.send_message("❌ Нет доступных серверов", ephemeral=False)
            return
        
        if len(available_guilds) == 1:
            await self.zov_inner(interaction, available_guilds[0][2])
            return
        
        guild_options = [discord.SelectOption(label=name[:100], value=str(gid)) for gid, name, _ in available_guilds]
        
        class GuildSelect(discord.ui.Select):
            def __init__(self, guild_dict):
                super().__init__(placeholder="Выбери сервер", options=guild_options)
                self.guild_dict = guild_dict
            
            async def callback(self, select_interaction: discord.Interaction):
                guild_id = int(self.values[0])
                guild = self.guild_dict[guild_id]
                await self.owner.zov_inner(select_interaction, guild)
        
        guild_dict = {gid: g for gid, _, g in available_guilds}
        
        class GuildSelectView(discord.ui.View):
            def __init__(self, owner):
                super().__init__()
                self.owner = owner
                select = GuildSelect(guild_dict)
                select.owner = self.owner
                self.add_item(select)
        
        view = GuildSelectView(self)
        await interaction.response.send_message("Выбери сервер для объявления:", view=view, ephemeral=False)
    
    async def zov_inner(self, interaction: discord.Interaction, guild: discord.Guild):
        class ZovModal(discord.ui.Modal):
            def __init__(self, admin_cog, guild_obj):
                super().__init__(title="Отправить объявление")
                self.admin_cog = admin_cog
                self.guild_obj = guild_obj
                
                self.message_input = discord.ui.TextInput(label="Текст объявления", style=TextStyle.long)
                
                self.add_item(self.message_input)
            
            async def on_submit(self, modal_interaction: discord.Interaction):
                try:
                    message = self.message_input.value
                    
                    all_channels = self.guild_obj.text_channels
                    if not all_channels:
                        await modal_interaction.response.send_message("❌ Нет текстовых каналов", ephemeral=False)
                        return
                    
                    channels_per_page = 24
                    total_pages = (len(all_channels) + channels_per_page - 1) // channels_per_page
                    
                    def get_channel_page(page_num=0):
                        start = page_num * channels_per_page
                        end = start + channels_per_page
                        return all_channels[start:end]
                    
                    current_channel_page = 0
                    channels = get_channel_page(current_channel_page)
                    channel_options = [discord.SelectOption(label=ch.name[:100], value=str(ch.id)) for ch in channels]
                    
                    async def show_channel_page(interaction, page_num):
                        page_channels = get_channel_page(page_num)
                        page_channel_options = [discord.SelectOption(label=ch.name[:100], value=str(ch.id)) for ch in page_channels]
                        
                        class ChannelSelectPaginated(discord.ui.Select):
                            def __init__(self, guild_obj):
                                super().__init__(placeholder="Выбери канал", options=page_channel_options)
                                self.guild_obj = guild_obj
                            
                            async def callback(self, ch_inter: discord.Interaction):
                                channel_id = int(self.values[0])
                                
                                all_roles = [r for r in self.guild_obj.roles if r.name != "@everyone"]
                                roles_per_page = 24
                                total_role_pages = (len(all_roles) + roles_per_page - 1) // roles_per_page
                                
                                def get_role_page(page_num=0):
                                    start = page_num * roles_per_page
                                    end = start + roles_per_page
                                    return all_roles[start:end]
                                
                                async def show_role_page(interaction, page_num):
                                    page_roles = get_role_page(page_num)
                                    page_role_options = [discord.SelectOption(label=r.name[:100], value=str(r.id)) for r in page_roles]
                                    
                                    class RoleSelectPaginated(discord.ui.Select):
                                        def __init__(self, guild_obj):
                                            if page_role_options:
                                                super().__init__(placeholder="Выбери роли для упоминания (опционально)", options=page_role_options, min_values=0, max_values=min(5, len(page_role_options)))
                                            else:
                                                super().__init__(placeholder="Нет ролей", options=[discord.SelectOption(label="Нет", value="0")], disabled=True)
                                            self.guild_obj = guild_obj
                                        
                                        async def callback(self, role_inter: discord.Interaction):
                                            role_ids = [int(r) for r in self.values if r != "0"] if self.values else []
                                            channel = self.guild_obj.get_channel(channel_id)
                                            
                                            role_mentions = ""
                                            if role_ids:
                                                mentions = []
                                                for rid in role_ids:
                                                    role = self.guild_obj.get_role(rid)
                                                    if role:
                                                        mentions.append(role.mention)
                                                role_mentions = " ".join(mentions) if mentions else ""
                                            
                                            embed = discord.Embed(description=message, color=discord.Color.gold())
                                            embed.set_footer(text=f"_От {role_inter.user.name}_")
                                            is_ephemeral = role_inter.guild is not None
                                            try:
                                                if role_mentions:
                                                    await channel.send(role_mentions, embed=embed)
                                                else:
                                                    await channel.send(embed=embed)
                                                await role_inter.response.send_message("✅ Объявление отправлено", ephemeral=is_ephemeral)
                                            except Exception as e:
                                                await role_inter.response.send_message(f"❌ Ошибка: {str(e)}", ephemeral=is_ephemeral)
                                    
                                    view = discord.ui.View()
                                    view.add_item(RoleSelectPaginated(self.guild_obj))
                                    
                                    skip_btn = discord.ui.Button(label="Пропустить", style=discord.ButtonStyle.secondary)
                                    async def skip_cb(skip_inter):
                                        channel = self.guild_obj.get_channel(channel_id)
                                        embed = discord.Embed(description=message, color=discord.Color.gold())
                                        embed.set_footer(text=f"_От {skip_inter.user.name}_")
                                        is_ephemeral = skip_inter.guild is not None
                                        try:
                                            await channel.send(embed=embed)
                                            await skip_inter.response.send_message("✅ Объявление отправлено", ephemeral=is_ephemeral)
                                        except Exception as e:
                                            await skip_inter.response.send_message(f"❌ Ошибка: {str(e)}", ephemeral=is_ephemeral)
                                    skip_btn.callback = skip_cb
                                    view.add_item(skip_btn)
                                    
                                    if total_role_pages > 1:
                                        if page_num > 0:
                                            prev_btn = discord.ui.Button(label="← Пред.", style=discord.ButtonStyle.secondary)
                                            async def prev_cb(btn_inter):
                                                await btn_inter.response.defer()
                                                await show_role_page(btn_inter, page_num - 1)
                                            prev_btn.callback = prev_cb
                                            view.add_item(prev_btn)
                                        
                                        if page_num < total_role_pages - 1:
                                            next_btn = discord.ui.Button(label="Далее →", style=discord.ButtonStyle.secondary)
                                            async def next_cb(btn_inter):
                                                await btn_inter.response.defer()
                                                await show_role_page(btn_inter, page_num + 1)
                                            next_btn.callback = next_cb
                                            view.add_item(next_btn)
                                    
                                    embed = discord.Embed(title="Выбери роли", description=f"Страница {page_num + 1}/{total_role_pages}", color=discord.Color.blue())
                                    is_ephemeral = modal_interaction.guild is not None
                                    if ch_inter == interaction:
                                        await interaction.response.send_message(embed=embed, view=view, ephemeral=is_ephemeral)
                                    else:
                                        await interaction.followup.send(embed=embed, view=view, ephemeral=is_ephemeral)
                                
                                await show_role_page(ch_inter, 0)
                        
                        view = discord.ui.View()
                        view.add_item(ChannelSelectPaginated(self.guild_obj))
                        
                        if total_pages > 1:
                            if page_num > 0:
                                prev_btn = discord.ui.Button(label="← Пред.", style=discord.ButtonStyle.secondary)
                                async def prev_cb(btn_inter):
                                    await btn_inter.response.defer()
                                    await show_channel_page(btn_inter, page_num - 1)
                                prev_btn.callback = prev_cb
                                view.add_item(prev_btn)
                            
                            if page_num < total_pages - 1:
                                next_btn = discord.ui.Button(label="Далее →", style=discord.ButtonStyle.secondary)
                                async def next_cb(btn_inter):
                                    await btn_inter.response.defer()
                                    await show_channel_page(btn_inter, page_num + 1)
                                next_btn.callback = next_cb
                                view.add_item(next_btn)
                        
                        embed = discord.Embed(title="Выбери канал", description=f"Страница {page_num + 1}/{total_pages}", color=discord.Color.blue())
                        is_ephemeral = modal_interaction.guild is not None
                        if modal_interaction == interaction:
                            await interaction.response.send_message(embed=embed, view=view, ephemeral=is_ephemeral)
                        else:
                            await interaction.followup.send(embed=embed, view=view, ephemeral=is_ephemeral)
                    
                    await show_channel_page(modal_interaction, current_channel_page)
                
                except Exception as e:
                    await modal_interaction.response.send_message(f"❌ Ошибка: {str(e)}", ephemeral=False)
        
        await interaction.response.send_modal(ZovModal(self, guild))


async def setup(bot):
    db = bot.db if hasattr(bot, 'db') else Database()
    scheduler = bot.scheduler if hasattr(bot, 'scheduler') else None
    admin_ids = list(map(int, os.getenv("ADMIN_IDS", "").split(","))) if os.getenv("ADMIN_IDS") else []
    await bot.add_cog(AdminCog(bot, db, scheduler, admin_ids))

