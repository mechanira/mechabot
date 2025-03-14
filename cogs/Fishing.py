import discord
from discord.ext import commands
from discord import app_commands
import google.generativeai as genai
import random
import os
import json
import sqlite3
import traceback

xp_emojis = ["<:xp_bar_1:1348303541944586302>",
             "<:xp_bar_2:1348303635033100339>",
             "<:xp_bar_3:1348304289558298724>",
             "<:xp_bar_filled_1:1348303686069387264>",
             "<:xp_bar_filled_2:1348303598999834725>",
             "<:xp_bar_filled_3:1348304333455888495>"]

class Fishing(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.conn = sqlite3.connect('data.db')
        self.cursor = self.conn.cursor()
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS infi_user(
                id INTEGER PRIMARY KEY,
                level INTEGER,
                xp INTEGER,
                max_xp INTEGER,
                balance INTEGER DEFAULT 0,
                current_biome TEXT
            )
        """)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS infi_fish(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                name TEXT,
                lore TEXT,
                size INTEGER,
                value INTEGER,
                biome TEXT,
                sold BOOLEAN DEFAULT 0,
                FOREIGN KEY(user_id) REFERENCES infi_user(id)
            )
        """)
        self.conn.commit()
        
        genai.configure(api_key=os.environ["GEMINI_KEY"])

        self.model = genai.GenerativeModel(
            model_name='models/gemini-1.5-flash-001',
            system_instruction=(
                "You are a fish data generation model that works for a Discord bot."
                """
                Your prompts will come as payload data in the form of a JSON string such as:
                {
                    "biome": "river",
                    "rarity": 1
                }
                """
                "The biome tag specifies which biome the fish is being catched from"
                "The rarity tag specifies the rarity of fish (1-6). Lower rarity fish are typically small and more realistic, and higher rarity fish are typically more mythical or fantasy and they can even be very massive"
                """
                Your responses should ONLY contain a raw string of the specified JSON template which you can fill out. The template will be for the fish that you catch:
                {
                    "name": "insert fish name (species)",
                    "lore": "insert fish description (make sure to not reuse the fish name here)",
                    "size": insert an exact size in centimeters eg. (120), must be an integer
                    "value": insert value of the catch in dollars, must be an integer
                    "xp": insert xp gain from the catch, must be an integer
                }
                """
            )
        )

    @commands.Cog.listener()
    async def on_ready(self):
        try:
            print(f"{__name__} is online!")
        except Exception as e:
            print(f"Error during on_ready: {e}")
    
    
    @app_commands.command(name="fish", description="Catch a fish!")
    async def fish(self, interaction: discord.Interaction):
        try:
            user_id = interaction.user.id

            self.cursor.execute("SELECT level, xp, max_xp, current_biome FROM infi_user WHERE id = ?", (user_id,))
            user_data = self.cursor.fetchone()
            
            if user_data is not None:
                level, xp, max_xp, current_biome = user_data
            else:
                level = 1
                xp = 0
                max_xp = 100
                current_biome = 'river'
                
            weights = [1, 4, 20, 65, 195, 360]
            rarity_levels = [6, 5, 4, 3, 2, 1]
            
            rarity = random.choices(rarity_levels, weights)[0]

            payload = {
                "biome": current_biome,
                "rarity": rarity
            }
            print(payload)

            response = self.model.generate_content(str(payload))
            print(response.text)
            response_dict = json.loads(response.text)
            fish_name, lore, size, value, xp_gain = (
                response_dict.get(k, default) for k, default in 
                [("name", "Unknown"), ("lore", "No lore available"), ("size", "Unknown"), ("value", 0), ("xp", 0)]
            )

            self.cursor.execute(
                "INSERT INTO infi_fish (user_id, name, lore, size, value, biome) VALUES (?, ?, ?, ?, ?, ?)",
                (interaction.user.id, fish_name, lore, size, value, current_biome)
            )
            fish_id = self.cursor.lastrowid

            xp += xp_gain
            old_level = level

            level_label = f"Level {level}"

            while(xp >= max_xp):
                xp -= max_xp
                level += 1
                max_xp = round(max_xp * 1.5)
                level_label = f"**LEVEL UP! {old_level} >> {level}**"

            rarity_colors = [
                discord.Color.greyple(),
                discord.Color.green(),
                discord.Color.blue(),
                discord.Color.purple(),
                discord.Color.yellow(),
                discord.Color.fuchsia()
            ]

            embed = discord.Embed(
                title=f"{fish_name} • {':star:' * rarity}",
                description=f"""
                *{lore}*

                **Size:** {size} cm
                **Value:** ${value:,}

                {level_label}
                {self.xp_bar(xp, max_xp)} {xp:,}/{max_xp:,} `+{xp_gain}`
                """,
                color=rarity_colors[rarity-1]
            )
            embed.set_footer(text=f"Biome: {current_biome} • ID: {fish_id}")

            self.cursor.execute(
                "UPDATE infi_user SET level = ?, xp = ?, max_xp = ?, current_biome = ? WHERE id = ?",
                (level, xp, max_xp, current_biome, user_id)
            )
            self.conn.commit()

            await interaction.response.send_message(embed=embed)
        except Exception as e:
            print(traceback.format_exc())

    @app_commands.command(name="biome", description="Change the fishing biome")
    @app_commands.choices(biome=[
        app_commands.Choice(name="River", value="river"),
        app_commands.Choice(name="Lake", value="lake"),
        app_commands.Choice(name="Ocean", value="ocean"),
        app_commands.Choice(name="Jungle", value="jungle"),
        app_commands.Choice(name="Cave", value="cave"),
        app_commands.Choice(name="Volcano", value="volcano"),
        app_commands.Choice(name="Sky", value="sky"),
        app_commands.Choice(name="Space", value="space")
        ])
    async def biome(self, interaction: discord.Interaction, biome: app_commands.Choice[str]):
        self.cursor.execute(
            "UPDATE infi_user SET current_biome = ? WHERE id = ?",
            (biome.value, interaction.user.id))
        self.conn.commit()

        await interaction.response.send_message(f"Biome changed to **{biome.value}**")


    @app_commands.command(name="sell", description="Sell all your fish")
    async def sell(self, interaction: discord.Interaction):
        try:
            self.cursor.execute("BEGIN TRANSACTION;")

            self.cursor.execute("SELECT id, value from infi_fish WHERE user_id = ? AND sold = 0", (interaction.user.id,))
            unsold_fish = self.cursor.fetchall()

            total_value = sum(fish[1] for fish in unsold_fish)

            if unsold_fish:
                self.cursor.execute("UPDATE infi_fish SET sold = 1 WHERE user_id = ? AND sold = 0", (interaction.user.id,)) 

                self.cursor.execute("UPDATE infi_user SET balance = balance + ? WHERE id = ?", (total_value, interaction.user.id))
            else:
                await interaction.response.send_message("You have no fish to sell.", ephemeral=True)
                return

            self.conn.commit()

            await interaction.response.send_message(f"Sold {len(unsold_fish)} fish for ${total_value:,}")
        except Exception as e:
            print(traceback.format_exc())

    
    @app_commands.command(name="profile", description="Check your fishing profile")
    async def profile(self, interaction: discord.Interaction):
        self.cursor.execute("SELECT level, xp, max_xp, balance, current_biome FROM infi_user WHERE id = ?", (interaction.user.id,))
        user_data = self.cursor.fetchone()

        if user_data is not None:
            level, xp, max_xp, balance, current_biome = user_data
        else:
            await interaction.response.send_message("You don't have a fishing profile created. Do `/fish` to create one")
            return
        
        embed = discord.Embed(
            title=f"{interaction.user.display_name}'s Fishing Profile",
            description=f"""
                **Level {level}**
                {self.xp_bar(xp, max_xp)} {xp:,}/{max_xp:,}
                Balance: `${balance:,}`
                Biome: `{current_biome}`
            """
        )

        await interaction.response.send_message(embed=embed)


    def xp_bar(self, xp, max_xp, length=10) -> str:
        percentage = round((xp / max_xp) * 100)
        filled_bars = round(percentage / length)

        bar_string = ""

        for i in range(1, length+1):
            if i <= filled_bars:
                if i == 1:
                    bar_string += xp_emojis[3]
                elif i < length:
                    bar_string += xp_emojis[4]
                else:
                    bar_string += xp_emojis[5]
            else:
                if i == 1:
                    bar_string += xp_emojis[0]
                elif i < length:
                    bar_string += xp_emojis[1]
                else:
                    bar_string += xp_emojis[2]

        return bar_string
    
        

async def setup(bot):
    await bot.add_cog(Fishing(bot))