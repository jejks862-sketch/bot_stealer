import discord
from discord.ext import commands
from discord import app_commands
from utils.database import Database
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

ACTIVITY_CHANNELS = [
    1461386311171702950,
    1458718606945812543,
    1444024262846578831,
    1459779624186941481,
    1459726206877306921
]


class ActivityCog(commands.Cog):
    def __init__(self, bot, db: Database):
        self.bot = bot
        self.db = db

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == self.bot.user:
            return

        if message.channel.id in ACTIVITY_CHANNELS:
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
                new_roles = self.db.get_roles_for_level(new_stats["level"])
                old_roles = self.db.get_user_roles(message.author.id)
                
                roles_to_add = [rid for rid in new_roles if rid not in old_roles]
                
                if roles_to_add:
                    guild = message.guild
                    member = message.author
                    
                    for role_id in roles_to_add:
                        try:
                            role = guild.get_role(role_id)
                            if role:
                                await member.add_roles(role)
                        except:
                            pass
                    
                    self.db.set_user_roles(message.author.id, new_roles)

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
        
        embed = discord.Embed(
            title="📊 Топ 100 активных пользователей",
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
        
        view = ActivityFilterView(self.db, interaction.user)
        await interaction.followup.send(embed=embed, view=view)


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


async def setup(bot):
    pass
