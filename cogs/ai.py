import discord
from discord.ext import commands
from discord import app_commands
import logging
import aiohttp
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "").split(","))) if os.getenv("ADMIN_IDS") else []
SYSTEM_PROMPT_FILE = "./data/system_prompt.txt"

MODELS = [
    "gpt-4o-mini",
    "gemini-2.0-flash-lite",
    "gemini-2.0-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-3-flash",
    "gpt-3.5-turbo",
    "gpt-4",
    "gpt-4-turbo",
    "gpt-4o",
    "grok-3"
]


class AIActionView(discord.ui.View):
    def __init__(self, user: discord.User, text: str, ai_cog):
        super().__init__(timeout=3600)
        self.user = user
        self.text = text
        self.ai_cog = ai_cog
    
    @discord.ui.button(label="🔄 Повторить", style=discord.ButtonStyle.secondary)
    async def retry_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            await interaction.response.send_message("❌ Ты не можешь использовать эту кнопку", ephemeral=True)
            return
        
        await interaction.response.defer()
        response = await self.ai_cog.get_ai_response(self.text)
        
        if len(response) > 2000:
            response = response[:2000] + "..."
        
        embed = discord.Embed(
            description=response,
            color=discord.Color.blue()
        )
        
        await interaction.followup.send(embed=embed, view=AIActionView(self.user, self.text, self.ai_cog))
    
    @discord.ui.button(label="⚙️ Промт", style=discord.ButtonStyle.primary)
    async def prompt_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in ADMIN_IDS:
            await interaction.response.send_message("❌ Только администраторы могут менять промт", ephemeral=True)
            return
        
        modal = SystemPromptModal(self.ai_cog)
        await interaction.response.send_modal(modal)


class SystemPromptModal(discord.ui.Modal):
    def __init__(self, ai_cog):
        super().__init__(title="⚙️ Системный промт ИИ")
        self.ai_cog = ai_cog
        
        self.prompt = discord.ui.TextInput(
            label="Введи системный промт",
            style=discord.TextStyle.paragraph,
            placeholder="Пример: Ты помощник, отвечай на русском языке кратко",
            required=True,
            max_length=1000
        )
        self.add_item(self.prompt)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            self.ai_cog.save_system_prompt(self.prompt.value)
            embed = discord.Embed(
                title="✅ Промт обновлён!",
                description=f"Новый системный промт: {self.prompt.value[:100]}...",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            await interaction.response.send_message(f"❌ Ошибка: {str(e)}", ephemeral=True)


class AICog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.system_prompt = self._load_system_prompt()

    def _load_system_prompt(self) -> str:
        try:
            if os.path.exists(SYSTEM_PROMPT_FILE):
                with open(SYSTEM_PROMPT_FILE, 'r', encoding='utf-8') as f:
                    return f.read().strip()
        except:
            pass
        return ""
    
    def save_system_prompt(self, prompt: str):
        os.makedirs(os.path.dirname(SYSTEM_PROMPT_FILE), exist_ok=True)
        with open(SYSTEM_PROMPT_FILE, 'w', encoding='utf-8') as f:
            f.write(prompt)
        self.system_prompt = prompt

    async def get_ai_response(self, text: str) -> str:
        api_url = "https://api.onlysq.ru/ai/openai/chat/completions"
        
        messages = []
        if self.system_prompt:
            messages.append({
                "role": "system",
                "content": self.system_prompt
            })
        
        messages.append({
            "role": "user",
            "content": text
        })
        
        for model in MODELS:
            try:
                payload = {
                    "model": model,
                    "messages": messages,
                    "max_tokens": 500
                }
                
                headers = {
                    "Authorization": "Bearer openai",
                    "Content-Type": "application/json"
                }
                
                async with aiohttp.ClientSession() as session:
                    async with session.post(api_url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=10, connect=5)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if "choices" in data and len(data["choices"]) > 0:
                                response = data["choices"][0]["message"]["content"]
                                
                                if len(response) > 2000:
                                    response = response[:2000] + "..."
                                
                                return response
                            
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                continue

        return "❌ Не удалось получить ответ ни от одной ИИ модели"

    @app_commands.command(name="ai", description="Спросить у ИИ")
    @app_commands.describe(text="Ваш вопрос или текст для ИИ")
    async def ai(self, interaction: discord.Interaction, text: str):
        await interaction.response.defer()

        try:
            response = await self.get_ai_response(text)
            
            embed = discord.Embed(
                description=response,
                color=discord.Color.blue()
            )
            
            view = AIActionView(interaction.user, text, self)
            await interaction.followup.send(embed=embed, view=view)
                
        except Exception as e:
            pass
            await interaction.followup.send(f"❌ Ошибка: {str(e)}")



async def setup(bot):
    await bot.add_cog(AICog(bot))

