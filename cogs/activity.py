import discord
from discord.ext import commands, tasks
from discord import app_commands
from utils.database import Database
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class ActivityCog(commands.Cog):
    def __init__(self, bot, db: Database):
        self.bot = bot
        self.db = db
        self.voice_sessions = {}
        self.voice_xp_task.start()
    
    @tasks.loop(minutes=10)
    async def voice_xp_task(self):
        now = datetime.now()
        for user_id, session in list(self.voice_sessions.items()):
            time_in_voice = now - session["joined_at"]
            minutes = time_in_voice.total_seconds() / 60
            
            if minutes >= 10:
                old_level = self.db.get_user_stats(user_id).get("level", 1)
                new_stats = self.db.add_experience(user_id, 100)
                session["last_award"] = now
                
                if new_stats["level"] > old_level:
                    guild = self.bot.get_guild(session["guild_id"])
                    member = guild.get_member(user_id) if guild else None
                    
                    if member and guild:
                        old_role = self.db.get_roles_for_level(old_level, guild.id)
                        new_role = self.db.get_roles_for_level(new_stats["level"], guild.id)
                        
                        if old_role:
                            try:
                                role = guild.get_role(old_role[0])
                                if role:
                                    await member.remove_roles(role)
                            except Exception:
                                pass
                        
                        if new_role:
                            try:
                                role = guild.get_role(new_role[0])
                                if role:
                                    await member.add_roles(role)
                            except Exception:
                                pass
    
    @voice_xp_task.before_loop
    async def before_voice_xp_task(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == self.bot.user:
            return

        guild_settings = self.db.get_guild_settings(message.guild.id)
        activity_channels = guild_settings["activity_channels"]
        
        if message.channel.id in activity_channels:
            self.db.add_message(message.author.id)
            
            user_stats = self.db.get_user_stats(message.author.id)
            last_exp_time = user_stats.get("last_exp_time")
            
            if last_exp_time:
                last_time = datetime.fromisoformat(last_exp_time)
                if datetime.now() - last_time < timedelta(minutes=1):
                    return
            
            old_level = user_stats.get("level", 1)
            new_stats = self.db.add_experience(message.author.id, 25)
            
            if new_stats["level"] > old_level:
            new_role = self.db.get_roles_for_level(new_stats["level"], message.guild.id)
            old_role = self.db.get_roles_for_level(old_level, message.guild.id)
                guild = message.guild
                member = message.author
                
                if old_role:
                    try:
                        role = guild.get_role(old_role[0])
                        if role:
                            await member.remove_roles(role)
                    except Exception:
                        pass
                
                if new_role:
                    try:
                        role = guild.get_role(new_role[0])
                        if role:
                            await member.add_roles(role)
                    except Exception:
                        pass

    @app_commands.command(name="activity", description="Посмотреть активность")
    @app_commands.describe(
        subcommand="list (топ активных) или user (конкретный пользователь)"
    )
    async def activity(self, interaction: discord.Interaction, subcommand: str = "list"):
        if subcommand.lower() == "list":
            await self.show_activity_list(interaction)
        else:
            await interaction.response.send_message(
                "❌ Используй `/activity list` для топа активных пользователей или `/user @username`"
            )

    async def show_activity_list(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        top_users = self.db.get_top_active_users_by_messages(limit=100, days=None)
        
        if not top_users:
            await interaction.followup.send("❌ Нет данных об активности")
            return
        
        users_per_page = 10
        total_pages = (len(top_users) + users_per_page - 1) // users_per_page
        
        async def show_page(callback_interaction, page=0):
            start = page * users_per_page
            end = start + users_per_page
            page_users = top_users[start:end]
            
            embed = discord.Embed(
                title=f"📊 Топ активных пользователей (стр. {page + 1}/{total_pages})",
                color=discord.Color.purple()
            )
            
            activity_text = ""
            for idx, (user_id, count) in enumerate(page_users, start + 1):
                activity_text += f"{idx}. <@{user_id}> - {count} сообщений\n"
            
            embed.add_field(name="Рейтинг", value=activity_text, inline=False)
            
            buttons_view = discord.ui.View()
            
            if page > 0:
                prev_btn = discord.ui.Button(label="← Пред.", style=discord.ButtonStyle.secondary)
                async def prev_cb(btn_i):
                    await btn_i.response.defer()
                    await show_page(btn_i, page - 1)
                prev_btn.callback = prev_cb
                buttons_view.add_item(prev_btn)
            
            if page < total_pages - 1:
                next_btn = discord.ui.Button(label="Далее →", style=discord.ButtonStyle.secondary)
                async def next_cb(btn_i):
                    await btn_i.response.defer()
                    await show_page(btn_i, page + 1)
                next_btn.callback = next_cb
                buttons_view.add_item(next_btn)
            
            if callback_interaction == interaction:
                await callback_interaction.followup.send(embed=embed, view=buttons_view)
            else:
                await callback_interaction.followup.send(embed=embed, view=buttons_view)
        
        await show_page(interaction)


class ActivityFilterView(discord.ui.View):
    def __init__(self, db: Database, user: discord.User):
        super().__init__(timeout=300)
        self.db = db
        self.user = user

    @discord.ui.button(label="1 день", style=discord.ButtonStyle.primary)
    async def day_1(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            await interaction.response.send_message("❌ Ты не можешь использовать эту кнопку", ephemeral=True)
            return
        
        await self.show_filtered(interaction, days=1, period="1 день")

    @discord.ui.button(label="7 дней", style=discord.ButtonStyle.primary)
    async def day_7(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            await interaction.response.send_message("❌ Ты не можешь использовать эту кнопку", ephemeral=True)
            return
        
        await self.show_filtered(interaction, days=7, period="7 дней")

    @discord.ui.button(label="30 дней", style=discord.ButtonStyle.primary)
    async def day_30(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            await interaction.response.send_message("❌ Ты не можешь использовать эту кнопку", ephemeral=True)
            return
        
        await self.show_filtered(interaction, days=30, period="30 дней")

    @discord.ui.button(label="Всё время", style=discord.ButtonStyle.success)
    async def all_time(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            await interaction.response.send_message("❌ Ты не можешь использовать эту кнопку", ephemeral=True)
            return
        
        await self.show_filtered(interaction, days=None, period="всё время")

    async def show_filtered(self, interaction: discord.Interaction, days: int, period: str):
        await interaction.response.defer()
        
        top_users = self.db.get_top_active_users_by_messages(limit=100, days=days)
        
        if not top_users:
            await interaction.followup.send(f"❌ Нет активности за {period}")
            return
        
        embed = discord.Embed(
            title=f"📊 Топ 100 активных пользователей ({period})",
            color=discord.Color.purple()
        )
        
        activity_text = ""
        for idx, (user_id, count) in enumerate(top_users[:100], 1):
            activity_text += f"{idx}. <@{user_id}> - {count} сообщений\n"
            
            if len(activity_text) > 1000:
                embed.add_field(name=f"Рейтинг {idx-20}-{idx}", value=activity_text, inline=False)
                activity_text = ""
        
        if activity_text:
            embed.add_field(name="Рейтинг", value=activity_text, inline=False)
        
        await interaction.followup.send(embed=embed)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        user_id = member.id
        guild_id = member.guild.id
        
        if before.channel is None and after.channel is not None:
            self.voice_sessions[user_id] = {
                "joined_at": datetime.now(),
                "guild_id": guild_id,
                "last_award": datetime.now()
            }
        
        elif before.channel is not None and after.channel is None:
            if user_id in self.voice_sessions:
                del self.voice_sessions[user_id]


async def setup(bot):
    pass
