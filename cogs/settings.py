import discord
from discord.ext import commands
from discord import app_commands
from utils.database import Database
import asyncio


class GuildSelectView(discord.ui.View):
    def __init__(self, bot, db, user_id):
        super().__init__(timeout=300)
        self.bot = bot
        self.db = db
        self.user_id = user_id
        
        user_guilds = db.get_user_guilds(user_id)
        if not user_guilds:
            return
        
        options = []
        for guild_data in user_guilds:
            guild_id = guild_data["guild_id"]
            guild = bot.get_guild(guild_id)
            guild_name = guild.name if guild else guild_data["guild_name"]
            
            options.append(discord.SelectOption(
                label=guild_name[:100],
                value=str(guild_id)
            ))
        
        if options:
            class GuildSelect(discord.ui.Select):
                def __init__(self, parent_view):
                    super().__init__(
                        placeholder="Выбери сервер",
                        options=options
                    )
                    self.parent_view = parent_view

                async def callback(self, select_interaction: discord.Interaction):
                    guild_id = int(self.values[0])
                    self.parent_view.selected_guild_id = guild_id
                    await select_interaction.response.defer()
                    await self.parent_view.show_settings(select_interaction, guild_id)
            
            self.add_item(GuildSelect(self))
            self.selected_guild_id = None
    
    async def show_settings(self, interaction, guild_id):
        from cogs.settings import SettingsView
        view = SettingsView(self.bot, self.db, guild_id)
        
        embed = discord.Embed(
            title="⚙️ Настройки бота",
            description=f"Управляй параметрами работы бота",
            color=discord.Color.blurple()
        )
        embed.add_field(
            name="📢 Каналы активности",
            value="Выбери каналы, где будет считаться активность пользователей",
            inline=False
        )
        embed.add_field(
            name="🎖️ Роли по уровням",
            value="Установи, какие роли выдавать за определённые уровни",
            inline=False
        )
        
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)


class ChannelSelect(discord.ui.Select):
    def __init__(self, bot, db, guild_id, channels):
        self.bot = bot
        self.db = db
        self.guild_id = guild_id
        
        options = []
        for channel in channels:
            options.append(discord.SelectOption(
                label=channel.name[:100],
                value=str(channel.id)
            ))
        
        super().__init__(
            placeholder="Выбери каналы активности",
            min_values=0,
            max_values=min(25, len(options)) if options else 1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        selected_ids = [int(val) for val in self.values]
        self.db.set_guild_activity_channels(self.guild_id, selected_ids)
        
        await interaction.response.defer()
        await interaction.followup.send(
            f"✅ Установлены каналы активности: {', '.join([f'<#{cid}>' for cid in selected_ids]) if selected_ids else 'Нет'}",
            ephemeral=True
        )


class ChannelSelectView(discord.ui.View):
    def __init__(self, bot, db, guild_id, page=0):
        super().__init__()
        self.bot = bot
        self.db = db
        self.guild_id = guild_id
        self.page = page
        
        guild = bot.get_guild(guild_id)
        self.all_channels = list(guild.text_channels) if guild else []
        self.channels_per_page = 24
        self.total_pages = (len(self.all_channels) + self.channels_per_page - 1) // self.channels_per_page
        
        self.add_item(ChannelSelect(bot, db, guild_id, self.get_page_channels()))
        
        if self.total_pages > 1:
            if page > 0:
                self.add_item(self.create_prev_button())
            if page < self.total_pages - 1:
                self.add_item(self.create_next_button())
    
    def get_page_channels(self):
        start = self.page * self.channels_per_page
        end = start + self.channels_per_page
        return self.all_channels[start:end]
    
    def create_prev_button(self):
        button = discord.ui.Button(label="← Предыдущая", style=discord.ButtonStyle.secondary)
        async def prev_callback(interaction: discord.Interaction):
            await interaction.response.defer()
            new_view = ChannelSelectView(self.bot, self.db, self.guild_id, self.page - 1)
            await interaction.followup.send(
                f"Страница {self.page - 1 + 1}/{self.total_pages}",
                view=new_view,
                ephemeral=True
            )
        button.callback = prev_callback
        return button
    
    def create_next_button(self):
        button = discord.ui.Button(label="Следующая →", style=discord.ButtonStyle.secondary)
        async def next_callback(interaction: discord.Interaction):
            await interaction.response.defer()
            new_view = ChannelSelectView(self.bot, self.db, self.guild_id, self.page + 1)
            await interaction.followup.send(
                f"Страница {self.page + 1 + 1}/{self.total_pages}",
                view=new_view,
                ephemeral=True
            )
        button.callback = next_callback
        return button


class LevelRoleModal(discord.ui.Modal):
    def __init__(self, db, guild_id):
        super().__init__(title="Добавить роль за уровень")
        self.db = db
        self.guild_id = guild_id
        
        self.level_input = discord.ui.TextInput(
            label="Уровень",
            placeholder="5",
            max_length=3
        )
        self.role_input = discord.ui.TextInput(
            label="ID роли",
            placeholder="1234567890",
            max_length=20
        )
        
        self.add_item(self.level_input)
        self.add_item(self.role_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            level = int(self.level_input.value)
            role_id = int(self.role_input.value)
            
            self.db.set_role_for_level(self.guild_id, level, role_id)
            await interaction.response.send_message(
                f"✅ Роль {role_id} установлена за уровень {level}",
                ephemeral=True
            )
        except ValueError:
            await interaction.response.send_message(
                "❌ Ошибка: уровень и ID роли должны быть числами",
                ephemeral=True
            )


class SettingsView(discord.ui.View):
    def __init__(self, bot, db, guild_id):
        super().__init__()
        self.bot = bot
        self.db = db
        self.guild_id = guild_id

    @discord.ui.button(label="Выбрать каналы", style=discord.ButtonStyle.primary)
    async def select_channels(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = ChannelSelectView(self.bot, self.db, self.guild_id)
        message = f"Выбери каналы, где считать активность:\nСтраница 1/{view.total_pages}"
        await interaction.response.send_message(
            message,
            view=view,
            ephemeral=True
        )

    @discord.ui.button(label="Добавить роль", style=discord.ButtonStyle.success)
    async def add_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(LevelRoleModal(self.db, self.guild_id))

    @discord.ui.button(label="Просмотр настроек", style=discord.ButtonStyle.secondary)
    async def view_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        settings = self.db.get_guild_settings(self.guild_id)
        
        channels_text = "Нет"
        if settings["activity_channels"]:
            channels_text = ", ".join([f"<#{cid}>" for cid in settings["activity_channels"]])
        
        roles_text = "Нет"
        if settings["level_roles"]:
            roles_text = "\n".join([f"Уровень {level}: <@&{role_id}>" for level, role_id in settings["level_roles"].items()])
        
        embed = discord.Embed(
            title="⚙️ Настройки сервера",
            color=discord.Color.blurple()
        )
        embed.add_field(name="📢 Каналы активности", value=channels_text, inline=False)
        embed.add_field(name="🎖️ Роли по уровням", value=roles_text, inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Удалить роль", style=discord.ButtonStyle.danger)
    async def remove_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        settings = self.db.get_guild_settings(self.guild_id)
        
        if not settings["level_roles"]:
            await interaction.response.send_message(
                "❌ Нет ролей для удаления",
                ephemeral=True
            )
            return
        
        options = [
            discord.SelectOption(
                label=f"Уровень {level}",
                value=str(level)
            )
            for level in settings["level_roles"].keys()
        ]
        
        class RemoveRoleSelect(discord.ui.Select):
            def __init__(self):
                super().__init__(
                    placeholder="Выбери роль для удаления",
                    options=options
                )
            
            async def callback(self, select_interaction: discord.Interaction):
                level = int(self.values[0])
                self.db.remove_role_for_level(self.guild_id, level)
                await select_interaction.response.send_message(
                    f"✅ Роль за уровень {level} удалена",
                    ephemeral=True
                )
        
        class RemoveRoleView(discord.ui.View):
            def __init__(self):
                super().__init__()
                self.add_item(RemoveRoleSelect())
        
        await interaction.response.send_message(
            "Выбери роль для удаления:",
            view=RemoveRoleView(),
            ephemeral=True
        )

    @discord.ui.button(label="👥 Юзеры", style=discord.ButtonStyle.secondary)
    async def manage_users(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = self.bot.get_guild(self.guild_id)
        if not guild:
            await interaction.response.send_message("❌ Сервер не найден", ephemeral=True)
            return
        
        all_members = [m for m in guild.members if not m.bot]
        members_per_page = 24
        total_pages = (len(all_members) + members_per_page - 1) // members_per_page
        
        async def show_members_page(page_interaction, page=0):
            start = page * members_per_page
            end = start + members_per_page
            members = all_members[start:end]
            
            options = [
                discord.SelectOption(label=member.name, value=str(member.id))
                for member in members
            ]
            
            if not options:
                await page_interaction.response.send_message("❌ Нет юзеров", ephemeral=True)
                return
            
            class UserSelect(discord.ui.Select):
                def __init__(self, parent_cog):
                    super().__init__(placeholder="Выбери юзера", options=options)
                    self.parent_cog = parent_cog
                
                async def callback(self, user_interaction: discord.Interaction):
                    user_id = int(self.values[0])
                    user_stats = self.parent_cog.db.get_user_stats(user_id)
                    member = guild.get_member(user_id)
                    
                    member_name = member.name if member else "Неизвестный юзер"
                    embed = discord.Embed(title=f"👤 Данные юзера ({member_name})", color=discord.Color.blurple())
                    embed.add_field(name="ID", value=user_id, inline=True)
                    embed.add_field(name="Уровень", value=user_stats.get("level", 1), inline=True)
                    embed.add_field(name="Опыт", value=user_stats.get("total_exp", 0), inline=True)
                    embed.add_field(name="Сообщений", value=user_stats.get("message_count", 0), inline=True)
                    
                    if member:
                        roles_text = ", ".join([r.name for r in member.roles[1:]]) if len(member.roles) > 1 else "Нет"
                        embed.add_field(name="Роли", value=roles_text, inline=False)
                    
                    give_role_button = discord.ui.Button(label="➕ Выдать роль", style=discord.ButtonStyle.success)
                    
                    async def give_role_callback(role_interaction: discord.Interaction):
                        if not member:
                            await role_interaction.response.send_message("❌ Юзер не найден", ephemeral=True)
                            return
                        
                        role_options = [discord.SelectOption(label=r.name, value=str(r.id)) for r in guild.roles[:25]]
                        
                        class RoleSelect(discord.ui.Select):
                            def __init__(self):
                                super().__init__(placeholder="Выбери роль", options=role_options)
                            
                            async def callback(self, role_interaction: discord.Interaction):
                                role = guild.get_role(int(self.values[0]))
                                try:
                                    await member.add_roles(role)
                                    await role_interaction.response.send_message(f"✅ Роль {role.mention} выдана", ephemeral=True)
                                except Exception as e:
                                    await role_interaction.response.send_message(f"❌ Ошибка: {str(e)}", ephemeral=True)
                        
                        view = discord.ui.View()
                        view.add_item(RoleSelect())
                        await role_interaction.response.send_message("Выбери роль:", view=view, ephemeral=True)
                    
                    give_role_button.callback = give_role_callback
                    view = discord.ui.View()
                    view.add_item(give_role_button)
                    
                    if member:
                        kick_button = discord.ui.Button(label="🚪 Выгнать", style=discord.ButtonStyle.danger)
                        async def kick_callback(k_interaction):
                            try:
                                await member.kick(reason="Управление через бота")
                                await k_interaction.response.send_message(f"✅ {member_name} выгнан", ephemeral=True)
                            except Exception as e:
                                await k_interaction.response.send_message(f"❌ Ошибка: {str(e)}", ephemeral=True)
                        kick_button.callback = kick_callback
                        view.add_item(kick_button)
                        
                        mute_button = discord.ui.Button(label="🔇 Замутить", style=discord.ButtonStyle.secondary)
                        async def mute_callback(m_interaction):
                            class MuteModal(discord.ui.Modal):
                                def __init__(self):
                                    super().__init__(title="Замутить юзера")
                                    self.minutes_input = discord.ui.TextInput(
                                        label="Время мута (минут)",
                                        placeholder="30",
                                        max_length=5
                                    )
                                    self.add_item(self.minutes_input)
                                
                                async def on_submit(self, modal_interaction: discord.Interaction):
                                    try:
                                        minutes = int(self.minutes_input.value)
                                        mute_role = discord.utils.find(lambda r: r.name.lower() == "muted", guild.roles)
                                        
                                        if not mute_role:
                                            mute_role = await guild.create_role(name="muted")
                                        
                                        await member.add_roles(mute_role, reason=f"Мут на {minutes} минут")
                                        
                                        import asyncio
                                        await asyncio.sleep(minutes * 60)
                                        await member.remove_roles(mute_role, reason="Мут истек")
                                        
                                        await modal_interaction.response.send_message(
                                            f"✅ {member_name} замучен на {minutes} минут",
                                            ephemeral=True
                                        )
                                    except ValueError:
                                        await modal_interaction.response.send_message(
                                            "❌ Введи число",
                                            ephemeral=True
                                        )
                                    except Exception as e:
                                        await modal_interaction.response.send_message(f"❌ Ошибка: {str(e)}", ephemeral=True)
                            
                            await m_interaction.response.send_modal(MuteModal())
                        
                        mute_button.callback = mute_callback
                        view.add_item(mute_button)
                        
                        remove_role_button = discord.ui.Button(label="➖ Снять роль", style=discord.ButtonStyle.secondary)
                        async def remove_role_callback(r_interaction):
                            member_roles = [r for r in member.roles[1:]]
                            if not member_roles:
                                await r_interaction.response.send_message("❌ У юзера нет ролей", ephemeral=True)
                                return
                            
                            options = [discord.SelectOption(label=r.name, value=str(r.id)) for r in member_roles[:25]]
                            
                            class RemoveRoleSelect(discord.ui.Select):
                                def __init__(self):
                                    super().__init__(placeholder="Выбери роль", options=options)
                                
                                async def callback(self, sel_interaction: discord.Interaction):
                                    role = guild.get_role(int(self.values[0]))
                                    try:
                                        await member.remove_roles(role)
                                        await sel_interaction.response.send_message(f"✅ Роль {role.name} снята", ephemeral=True)
                                    except Exception as e:
                                        await sel_interaction.response.send_message(f"❌ Ошибка: {str(e)}", ephemeral=True)
                            
                            view_role = discord.ui.View()
                            view_role.add_item(RemoveRoleSelect())
                            await r_interaction.response.send_message("Выбери роль для снятия:", view=view_role, ephemeral=True)
                        
                        remove_role_button.callback = remove_role_callback
                        view.add_item(remove_role_button)
                    
                    await user_interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            
            class UserView(discord.ui.View):
                def __init__(self, parent_cog):
                    super().__init__()
                    self.add_item(UserSelect(parent_cog))
                    
                    if page > 0:
                        btn = discord.ui.Button(label="← Пред.", style=discord.ButtonStyle.secondary)
                        async def prev_cb(i): 
                            await i.response.defer()
                            await show_members_page(i, page - 1)
                        btn.callback = prev_cb
                        self.add_item(btn)
                    
                    if page < total_pages - 1:
                        btn = discord.ui.Button(label="Далее →", style=discord.ButtonStyle.secondary)
                        async def next_cb(i): 
                            await i.response.defer()
                            await show_members_page(i, page + 1)
                        btn.callback = next_cb
                        self.add_item(btn)
            
            msg = f"Юзеры (стр. {page + 1}/{total_pages}):"
            await page_interaction.response.send_message(msg, view=UserView(self), ephemeral=True)
        
        await show_members_page(interaction)

    @discord.ui.button(label="🎭 Создать роль", style=discord.ButtonStyle.success)
    async def create_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        class CreateRoleModal(discord.ui.Modal):
            def __init__(self, parent_cog):
                super().__init__(title="Создать роль")
                self.parent_cog = parent_cog
                
                self.name_input = discord.ui.TextInput(
                    label="Название роли",
                    placeholder="Admin",
                    max_length=100
                )
                self.add_item(self.name_input)
            
            async def on_submit(self, modal_interaction: discord.Interaction):
                try:
                    guild = self.parent_cog.bot.get_guild(self.parent_cog.guild_id)
                    role = await guild.create_role(name=self.name_input.value)
                    await modal_interaction.response.send_message(
                        f"✅ Роль {role.mention} создана",
                        ephemeral=True
                    )
                except Exception as e:
                    await modal_interaction.response.send_message(
                        f"❌ Ошибка: {str(e)}",
                        ephemeral=True
                    )
        
        await interaction.response.send_modal(CreateRoleModal(self))

    @discord.ui.button(label="🗑️ Удалить роль", style=discord.ButtonStyle.danger)
    async def delete_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = self.bot.get_guild(self.guild_id)
        if not guild:
            await interaction.response.send_message("❌ Сервер не найден", ephemeral=True)
            return
        
        options = [
            discord.SelectOption(label=role.name, value=str(role.id))
            for role in guild.roles[:25]
            if role != guild.default_role and not role.managed
        ]
        
        if not options:
            await interaction.response.send_message("❌ Нет ролей для удаления", ephemeral=True)
            return
        
        class RoleDeleteSelect(discord.ui.Select):
            def __init__(self, parent_cog):
                super().__init__(
                    placeholder="Выбери роль для удаления",
                    options=options
                )
                self.parent_cog = parent_cog
            
            async def callback(self, del_interaction: discord.Interaction):
                role_id = int(self.values[0])
                role = guild.get_role(role_id)
                try:
                    await role.delete()
                    await del_interaction.response.send_message(
                        f"✅ Роль удалена",
                        ephemeral=True
                    )
                except Exception as e:
                    await del_interaction.response.send_message(
                        f"❌ Ошибка: {str(e)}",
                        ephemeral=True
                    )
        
        class RoleDeleteView(discord.ui.View):
            def __init__(self):
                super().__init__()
                self.add_item(RoleDeleteSelect(self))
        
        await interaction.response.send_message(
            "Выбери роль для удаления:",
            view=RoleDeleteView(),
            ephemeral=True
        )

    @discord.ui.button(label="Обновить данные", style=discord.ButtonStyle.primary)
    async def update_data(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        
        guild = self.bot.get_guild(self.guild_id)
        if not guild:
            await interaction.followup.send("❌ Сервер не найден", ephemeral=True)
            return
        
        user_count = 0
        user_roles_count = 0
        for member in guild.members:
            if not member.bot:
                self.db._ensure_user_exists(member.id)
                self.db.add_guild_member(self.guild_id, member.id)
                user_count += 1
                
                member_roles = [r.id for r in member.roles[1:]]
                if member_roles:
                    user_roles_count += len(member_roles)
        
        embed = discord.Embed(
            title="✅ Данные обновлены",
            color=discord.Color.green()
        )
        embed.add_field(name="👥 Юзеры", value=user_count, inline=True)
        embed.add_field(name="🎭 Роли", value=len(guild.roles), inline=True)
        embed.add_field(name="🔗 Роли у юзеров", value=user_roles_count, inline=True)
        embed.add_field(name="📢 Текст-каналы", value=len(guild.text_channels), inline=True)
        embed.add_field(name="🎙️ Голос-каналы", value=len(guild.voice_channels), inline=True)
        
        await interaction.followup.send(embed=embed, ephemeral=True)


class SettingsCog(commands.Cog):
    def __init__(self, bot, db: Database):
        self.bot = bot
        self.db = db

    @app_commands.command(name="settings", description="Управление настройками сервера")
    async def settings(self, interaction: discord.Interaction):
        is_dm = isinstance(interaction.channel, discord.DMChannel)
        is_guild = interaction.guild is not None
        
        if is_dm:
            user_guilds = self.db.get_user_guilds(interaction.user.id)
            if not user_guilds:
                await interaction.response.send_message(
                    "❌ Ты не админ ни на одном сервере, где работает этот бот"
                )
                return
            
            view = GuildSelectView(self.bot, self.db, interaction.user.id)
            embed = discord.Embed(
                title="⚙️ Выбор сервера",
                description="Выбери сервер для управления",
                color=discord.Color.blurple()
            )
            await interaction.response.send_message(embed=embed, view=view)
        
        elif is_guild:
            member = interaction.guild.get_member(interaction.user.id)
            if not member or not member.guild_permissions.administrator:
                await interaction.response.send_message(
                    "❌ У тебя нет прав администратора",
                    ephemeral=True
                )
                return
            
            view = SettingsView(self.bot, self.db, interaction.guild_id)
            embed = discord.Embed(
                title="⚙️ Настройки бота",
                description="Управляй параметрами работы бота на сервере",
                color=discord.Color.blurple()
            )
            embed.add_field(
                name="📢 Каналы активности",
                value="Выбери каналы, где будет считаться активность пользователей",
                inline=False
            )
            embed.add_field(
                name="🎖️ Роли по уровням",
                value="Установи, какие роли выдавать за определённые уровни",
                inline=False
            )
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def setup(bot):
    db = bot.db if hasattr(bot, 'db') else Database()
    await bot.add_cog(SettingsCog(bot, db))
