import discord
from discord.ext import commands
from discord import app_commands
from utils.database import Database
from PIL import Image, ImageDraw, ImageFont
import io
import aiohttp


class UsersCog(commands.Cog):
    def __init__(self, bot, db: Database):
        self.bot = bot
        self.db = db

    async def download_avatar(self, avatar_url: str) -> Image.Image:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(avatar_url) as resp:
                    avatar_data = await resp.read()
                    avatar = Image.open(io.BytesIO(avatar_data)).convert("RGBA")
                    return avatar.resize((180, 180), Image.Resampling.LANCZOS)
        except:
            return None

    def create_stats_image(self, user_name: str, level: int, rank: int, current_exp: int, 
                          exp_needed: int, total_exp: int, avatar: Image.Image = None, 
                          settings: dict = None) -> Image.Image:
        if settings is None:
            from utils.database import Database
            db = Database()
            settings = db.get_user_settings(user_name)
        
        cfg = {
            "canvas": {"width": 934, "height": 282, "color": settings.get("bg_color", (35, 39, 42))},
            "avatar": {"x": 35, "y": 36, "size": 210},
            "status": {"x": 190, "y": 190, "size": 45, "color": (67, 181, 129), "border": 6},
            "username": {"x": 270, "y": 125, "font_size": 38, "color": settings.get("username_text_color", (255, 255, 255))},
            "stats": {
                "right_margin": 40, "y": 35,
                "label_font_size": 22, "value_font_size": 48,
                "text_color": settings.get("rank_text_color", (255, 255, 255)), 
                "highlight_color": settings.get("level_text_color", (217, 126, 69))
            },
            "xp_text": {"end_x": 894, "y": 135, "font_size": 20, "color": settings.get("exp_text_color", (127, 127, 127))},
            "progress_bar": {
                "x": 270, "y": 175, "width": 624, "height": 35,
                "bg_color": (72, 75, 78), "fill_color": settings.get("bar_color", (214, 70, 46)), "radius": 17
            }
        }
        
        W, H = cfg["canvas"]["width"], cfg["canvas"]["height"]
        img = Image.new("RGB", (W, H), color=cfg["canvas"]["color"])
        draw = ImageDraw.Draw(img)
        
        try:
            font_username = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                                              cfg["username"]["font_size"])
            font_stats_label = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                                                 cfg["stats"]["label_font_size"])
            font_stats_val = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                                               cfg["stats"]["value_font_size"])
            font_xp = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                                        cfg["xp_text"]["font_size"])
        except:
            font_username = ImageFont.load_default()
            font_stats_label = ImageFont.load_default()
            font_stats_val = ImageFont.load_default()
            font_xp = ImageFont.load_default()
        
        bar = cfg["progress_bar"]
        draw.rounded_rectangle(
            [bar["x"], bar["y"], bar["x"] + bar["width"], bar["y"] + bar["height"]],
            radius=bar["radius"], fill=bar["bg_color"]
        )
        
        percent = min(current_exp / exp_needed, 1.0) if exp_needed > 0 else 0
        fill_width = int(bar["width"] * percent)
        if fill_width > 0:
            draw.rounded_rectangle(
                [bar["x"], bar["y"], bar["x"] + fill_width, bar["y"] + bar["height"]],
                radius=bar["radius"], fill=bar["fill_color"]
            )
        
        draw.text((cfg["username"]["x"], cfg["username"]["y"]), user_name,
                 font=font_username, fill=cfg["username"]["color"])
        
        def format_xp(xp_val):
            if xp_val >= 1000:
                return f"{xp_val / 1000:.2f}K"
            return str(int(xp_val))
        
        xp_str = f"{format_xp(current_exp)} / {format_xp(exp_needed)} XP"
        bbox = draw.textbbox((0, 0), xp_str, font=font_xp)
        text_width = bbox[2] - bbox[0]
        draw.text((cfg["xp_text"]["end_x"] - text_width, cfg["xp_text"]["y"]),
                 xp_str, font=font_xp, fill=cfg["xp_text"]["color"])
        
        cursor_x = W - cfg["stats"]["right_margin"]
        y_stats = cfg["stats"]["y"]
        
        level_str = str(level)
        bbox = draw.textbbox((0, 0), level_str, font=font_stats_val)
        w = bbox[2] - bbox[0]
        draw.text((cursor_x - w, y_stats - 10), level_str,
                 font=font_stats_val, fill=cfg["stats"]["highlight_color"])
        cursor_x -= (w + 5)
        
        bbox = draw.textbbox((0, 0), "LEVEL", font=font_stats_label)
        w = bbox[2] - bbox[0]
        draw.text((cursor_x - w, y_stats + 10), "LEVEL",
                 font=font_stats_label, fill=cfg["stats"]["highlight_color"])
        cursor_x -= (w + 20)
        
        rank_str = f"#{rank}"
        bbox = draw.textbbox((0, 0), rank_str, font=font_stats_val)
        w = bbox[2] - bbox[0]
        draw.text((cursor_x - w, y_stats - 10), rank_str,
                 font=font_stats_val, fill=cfg["stats"]["text_color"])
        cursor_x -= (w + 5)
        
        bbox = draw.textbbox((0, 0), "RANK", font=font_stats_label)
        w = bbox[2] - bbox[0]
        draw.text((cursor_x - w, y_stats + 10), "RANK",
                 font=font_stats_label, fill=cfg["stats"]["text_color"])
        
        if avatar:
            avatar_resized = avatar.resize((cfg["avatar"]["size"], cfg["avatar"]["size"]),
                                          Image.Resampling.LANCZOS)
            
            mask = Image.new("L", (cfg["avatar"]["size"], cfg["avatar"]["size"]), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.ellipse([0, 0, cfg["avatar"]["size"], cfg["avatar"]["size"]], fill=255)
            
            avatar_resized.putalpha(mask)
            img.paste(avatar_resized, (cfg["avatar"]["x"], cfg["avatar"]["y"]), avatar_resized)
        
        return img

    @app_commands.command(name="mystats", description="Показать твою статистику уровня")
    async def mystats(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        user_stats = self.db.get_user_stats(interaction.user.id)
        user_settings = self.db.get_user_settings(interaction.user.id)
        rank = self.db.get_user_rank(interaction.user.id)
        
        current_level = user_stats["level"]
        current_exp = user_stats["experience"]
        total_exp = user_stats["total_exp"]
        
        if current_level < 100:
            exp_needed = self.db.calculate_exp_for_level(current_level + 1)
        else:
            exp_needed = self.db.calculate_exp_for_level(100)
        
        avatar = None
        if interaction.user.avatar:
            avatar = await self.download_avatar(interaction.user.avatar.url)
        
        image = self.create_stats_image(
            user_name=interaction.user.name,
            level=current_level,
            rank=rank,
            current_exp=current_exp,
            exp_needed=exp_needed,
            total_exp=total_exp,
            avatar=avatar,
            settings=user_settings
        )
        
        image_bytes = io.BytesIO()
        image.save(image_bytes, format="PNG")
        image_bytes.seek(0)
        
        file = discord.File(image_bytes, filename="mystats.png")
        await interaction.followup.send(file=file)

    @app_commands.command(name="top", description="Показать топ пользователей по уровню")
    async def top(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        top_users = self.db.get_top_users(limit=10)
        
        if not top_users:
            await interaction.followup.send("❌ Нет данных об пользователях")
            return
        
        embed = discord.Embed(
            title="🏆 Топ 10 пользователей",
            color=discord.Color.gold(),
            description="По уровню и опыту"
        )
        
        for idx, (user_id, user_data) in enumerate(top_users, 1):
            level = user_data["level"]
            total_exp = user_data["total_exp"]
            
            medal = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else f"#{idx}"
            
            user = self.bot.get_user(user_id)
            username = user.name if user else f"ID: {user_id}"
            
            embed.add_field(
                name=f"{medal} {username}",
                value=f"Уровень {level} / {total_exp} EXP",
                inline=False
            )
        
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="confstats", description="Настроить внешний вид карточки статистики")
    async def confstats(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🎨 Кастомизация карточки статистики",
            color=discord.Color.blue(),
            description="Измени цвета элементов твоей карточки статистики"
        )
        
        view = SettingsView(self.bot, self.db, interaction.user)
        await interaction.response.send_message(embed=embed, view=view)


class SettingsView(discord.ui.View):
    def __init__(self, bot, db, user):
        super().__init__(timeout=600)
        self.bot = bot
        self.db = db
        self.user = user

    @discord.ui.button(label="🎨 Выбрать цвета", style=discord.ButtonStyle.primary)
    async def colors_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            await interaction.response.send_message("❌ Это не твоя команда", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="🎨 Выбор цветов",
            description="Выбери элемент для изменения цвета:",
            color=discord.Color.blue()
        )
        
        view = ColorSelectView(self.bot, self.db, self.user)
        await interaction.response.send_message(embed=embed, view=view)


class ColorSelectView(discord.ui.View):
    UNIFIED_COLORS = ["черный", "темно-серый", "серый", "светло-серый", "белый", 
                      "темно-красный", "красный", "розовый",
                      "темно-зеленый", "зеленый",
                      "темно-синий", "синий", "голубой",
                      "фиолетовый", "оранжевый", "желтый"]
    
    COLOR_OPTIONS = {
        "bg": ("Фон", (20, 20, 20)),
        "bar": ("Полоска опыта", (220, 100, 50)),
        "rank": ("Ранг текст", (220, 100, 50)),
        "level": ("Уровень текст", (255, 150, 0)),
        "username": ("Ник текст", (255, 255, 255)),
        "exp": ("Опыт текст", (100, 200, 255))
    }

    COLORS = {
        "черный": (0, 0, 0), "темно-серый": (64, 64, 64), "серый": (128, 128, 128), "светло-серый": (192, 192, 192), "белый": (255, 255, 255),
        "темно-красный": (128, 0, 0), "красный": (255, 0, 0), "розовый": (255, 192, 203),
        "темно-зеленый": (0, 100, 0), "зеленый": (0, 255, 0),
        "темно-синий": (0, 0, 128), "синий": (0, 0, 255), "голубой": (100, 200, 255),
        "фиолетовый": (128, 0, 128), "оранжевый": (255, 165, 0), "желтый": (255, 255, 0)
    }

    def __init__(self, bot, db, user):
        super().__init__(timeout=600)
        self.bot = bot
        self.db = db
        self.user = user
        
        select = discord.ui.Select(
            placeholder="Выбери элемент для изменения",
            options=[
                discord.SelectOption(label=self.COLOR_OPTIONS[k][0], value=k)
                for k in self.COLOR_OPTIONS
            ]
        )
        select.callback = self.select_element
        self.add_item(select)

    async def select_element(self, interaction: discord.Interaction):
        if interaction.user != self.user:
            await interaction.response.send_message("❌ Это не твоя команда", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        element = interaction.data["values"][0]
        name, default = self.COLOR_OPTIONS[element]
        
        embed = discord.Embed(
            title=f"🎨 Выбор цвета для: {name}",
            description=f"Текущий цвет: {str(default)}",
            color=discord.Color.blue()
        )
        
        select = discord.ui.Select(
            placeholder="Выбери цвет",
            options=[
                discord.SelectOption(label=color, value=color)
                for color in self.UNIFIED_COLORS
            ]
        )
        
        async def select_color(inter: discord.Interaction):
            if inter.user != self.user:
                await inter.response.send_message("❌ Это не твоя команда", ephemeral=True)
                return
            
            color_name = inter.data["values"][0]
            color_rgb = self.COLORS[color_name]
            
            settings = self.db.get_user_settings(self.user.id)
            
            if element == "bg":
                settings["bg_color"] = color_rgb
            elif element == "bar":
                settings["bar_color"] = color_rgb
            elif element == "rank":
                settings["rank_text_color"] = color_rgb
            elif element == "level":
                settings["level_text_color"] = color_rgb
            elif element == "username":
                settings["username_text_color"] = color_rgb
            elif element == "exp":
                settings["exp_text_color"] = color_rgb
            
            self.db.set_user_settings(self.user.id, settings)
            
            embed_done = discord.Embed(
                title="✅ Цвет изменён!",
                description=f"{name}: {color_name}",
                color=discord.Color.green()
            )
            await inter.response.send_message(embed=embed_done)
        
        select.callback = select_color
        view = discord.ui.View()
        view.add_item(select)
        
        custom_button = discord.ui.Button(label="🎯 Свой цвет", style=discord.ButtonStyle.secondary)
        async def custom_color(inter: discord.Interaction):
            if inter.user != self.user:
                await inter.response.send_message("❌ Это не твоя команда", ephemeral=True)
                return
            
            modal = RGBColorModal(self.db, self.user, element, name)
            await inter.response.send_modal(modal)
        
        custom_button.callback = custom_color
        view.add_item(custom_button)
        
        await interaction.followup.send(embed=embed, view=view)


class RGBColorModal(discord.ui.Modal):
    def __init__(self, db, user, element, name):
        super().__init__(title="🎨 Свой цвет")
        self.db = db
        self.user = user
        self.element = element
        self.name = name
        
        self.r = discord.ui.TextInput(
            label="Красный (0-255)",
            placeholder="0",
            required=True,
            min_length=1,
            max_length=3
        )
        self.g = discord.ui.TextInput(
            label="Зелёный (0-255)",
            placeholder="0",
            required=True,
            min_length=1,
            max_length=3
        )
        self.b = discord.ui.TextInput(
            label="Синий (0-255)",
            placeholder="0",
            required=True,
            min_length=1,
            max_length=3
        )
        
        self.add_item(self.r)
        self.add_item(self.g)
        self.add_item(self.b)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            r = int(self.r.value)
            g = int(self.g.value)
            b = int(self.b.value)
            
            if not (0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255):
                embed = discord.Embed(
                    title="❌ Ошибка",
                    description="Значения должны быть от 0 до 255",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            color_rgb = (r, g, b)
            settings = self.db.get_user_settings(self.user.id)
            
            if self.element == "bg":
                settings["bg_color"] = color_rgb
            elif self.element == "bar":
                settings["bar_color"] = color_rgb
            elif self.element == "rank":
                settings["rank_text_color"] = color_rgb
            elif self.element == "level":
                settings["level_text_color"] = color_rgb
            elif self.element == "username":
                settings["username_text_color"] = color_rgb
            elif self.element == "exp":
                settings["exp_text_color"] = color_rgb
            
            self.db.set_user_settings(self.user.id, settings)
            
            embed_done = discord.Embed(
                title="✅ Цвет изменён!",
                description=f"{self.name}: RGB({r}, {g}, {b})",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed_done)
        except ValueError:
            embed = discord.Embed(
                title="❌ Ошибка",
                description="Введите числа от 0 до 255",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    pass
