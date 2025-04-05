import discord
from discord.ext import commands
from discord import app_commands
import google.generativeai as genai
import random
import os
import json
import sqlite3
import traceback
import datetime
import asyncio

xp_emojis = {
    "left_empty": "<:xp_right_empty:1351216992056639530>",
    "left_half": "<:xp_left_half:1351217325336039474>",
    "left_full": "<:xp_left_full:1351217303076995236>",
    "middle_empty": "<:xp_middle_empty:1351217360320594032>",
    "middle_half": "<:xp_middle_half:1351217426590601236>",
    "middle_full": "<:xp_middle_full:1351217406617587723>",
    "right_empty": "<:xp_right_empty:1351217444651405322>",
    "right_half": "<:xp_right_half:1351217474091225118>",
    "right_full": "<:xp_right_full:1351217458265980948>",
}

biome_level_requirements = {
    "river": 0,
    "lake": 10,
    "ocean": 20,
    "jungle": 30,
    "cave": 35,
    "volcano": 40,
    "sky": 50,
    "space": 60
}

rarity_colors = [
    None,
    discord.Color.greyple(),
    discord.Color.green(),
    discord.Color.blue(),
    discord.Color.purple(),
    discord.Color.yellow(),
    discord.Color.fuchsia()
]

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
                rarity INTEGER,
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

                If you catch a fish with a rarity of 0, that means you got a junk item. Junk is totally worthless, and can be generated uniquely in each biome.
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
        user_id = interaction.user.id

        self.cursor.execute("BEGIN TRANSACTION;")

        self.cursor.execute("SELECT level, xp, max_xp, current_biome FROM infi_user WHERE id = ?", (user_id,))
        user_data = self.cursor.fetchone()
        
        if user_data is not None:
            level, xp, max_xp, current_biome = user_data
        else:
            level = 1
            xp = 0
            max_xp = 100
            current_biome = 'river'
            
        weights = [1, 4, 20, 65, 195, 360, 100]
        rarity_levels = [6, 5, 4, 3, 2, 1, 0]
        
        rarity = random.choices(rarity_levels, weights)[0]

        payload = {
            "biome": current_biome,
            "rarity": rarity
        }
        print(payload)

        response = await asyncio.to_thread(self.model.generate_content, str(payload))
        print(response.text)
        response_dict = json.loads(response.text)
        fish_name, lore, size, value, xp_gain = (
            response_dict.get(k, default) for k, default in 
            [("name", "Unknown"), ("lore", "No lore available"), ("size", "Unknown"), ("value", 0), ("xp", 0)]
        )

        self.cursor.execute(
            "INSERT INTO infi_fish (user_id, name, lore, rarity, size, value, biome) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (interaction.user.id, fish_name, lore, rarity, size, value, current_biome)
        )
        fish_id = self.cursor.lastrowid

        xp += xp_gain
        old_level = level

        level_label = f"Level {level}"

        while(xp >= max_xp):
            xp -= max_xp
            max_xp = self.xp_required(level=level)
            level += 1
            level_label = f"**LEVEL UP! {old_level} >> {level}**"

        embed = discord.Embed(
            title=f"{fish_name} {':star:' * rarity}",
            description=f"""
            *{lore}*

            **Size:** {size} cm
            **Value:** ${value:,}

            {level_label}
            {self.xp_bar(xp, max_xp)} {xp:,}/{max_xp:,} {f'`+{xp_gain}`' if rarity > 0 else ''}
            """,
            color=rarity_colors[rarity]
        )
        embed.set_footer(text=f"Biome: {current_biome} {f'• ID: {fish_id}' if rarity > 0 else ''}")

        if rarity > 0:
            self.cursor.execute("""
                INSERT INTO infi_user (id, level, xp, max_xp, current_biome) 
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET 
                    level = excluded.level,
                    xp = excluded.xp,
                    max_xp = excluded.max_xp,
                    current_biome = excluded.current_biome;
            """, (user_id, level, xp, max_xp, current_biome))
        
        self.conn.commit()

        await interaction.response.send_message(embed=embed)


    @app_commands.command(name="biomes", description="Change the fishing biome")
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
    async def biomes(self, interaction: discord.Interaction, biome: app_commands.Choice[str] = None):
        if biome == None:
            description = ""
            for k, v in biome_level_requirements.items():
                description += f"{k.capitalize()} - Level {v}\n"

            embed = discord.Embed(
                title="Biome Menu",
                description=description
            )

            await interaction.response.send_message(embed=embed)
            return

        user_data = self.cursor.execute("SELECT level FROM infi_user WHERE id = ?", (interaction.user.id,))
        level = user_data.fetchone()[0]

        if level < biome_level_requirements[biome.value]:
            await interaction.response.send_message(f"You need to be level {biome_level_requirements[biome.value]} to access the {biome.name} biome!", ephemeral=True)
            return


        self.cursor.execute(
            "UPDATE infi_user SET current_biome = ? WHERE id = ?",
            (biome.value, interaction.user.id))
        self.conn.commit()

        await interaction.response.send_message(f"Biome successfully changed to **{biome.name}**!")


    @app_commands.command(name="sell", description="Sell all your fish")
    async def sell(self, interaction: discord.Interaction):
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

    
    @app_commands.command(name="profile", description="Check your fishing profile")
    async def profile(self, interaction: discord.Interaction):
        self.cursor.execute("SELECT level, xp, max_xp, balance, current_biome FROM infi_user WHERE id = ?", (interaction.user.id,))
        user_data = self.cursor.fetchone()

        if user_data is not None:
            level, xp, max_xp, balance, current_biome = user_data
        else:
            await interaction.response.send_message("You don't have a fishing profile created. Do `/fish` to create one")
            return
        
        self.cursor.execute("SELECT * FROM infi_fish WHERE user_id = ?", (interaction.user.id,))
        user_fish = self.cursor.fetchall()
        
        embed = discord.Embed(
            title=f"{interaction.user.display_name}'s Fishing Profile",
            description=f"""
                **Level {level}**
                {self.xp_bar(xp, max_xp)} {xp:,}/{max_xp:,}
                Balance: `${balance:,}`
                Fish caught: `{len(user_fish)}`
                Biome: `{current_biome}`
            """
        )

        await interaction.response.send_message(embed=embed)


    @app_commands.command(name="search_fish", description="Search for fish")
    @app_commands.choices(sort=[
        app_commands.Choice(name="Rarity (Ascending)", value="rarity_ascending"),
        app_commands.Choice(name="Rarity (Descending)", value="rarity_descending")
    ])
    async def search_fish(self, interaction: discord.Interaction, query: str = "", sort: app_commands.Choice[str] = None, filter_rarity: int = None, page: int = None):
        try: # try parsing the query into an id
            query = int(query)
            self.cursor.execute("SELECT id, user_id, name, lore, rarity, size, value, biome, sold FROM infi_fish WHERE id = ?", (int(query),))
            fish_data = self.cursor.fetchone()

            if fish_data is None:
                await interaction.response.send_message("No fish was found with the provided query.", ephemeral=True)
                return
            
            id, user_id, name, lore, rarity, size, value, biome, sold = fish_data

            embed = discord.Embed(
                title=f"{name} {':star:' * rarity}",
                description=f"*{lore}*",
                color=rarity_colors[rarity-1]
            )

            embed.add_field(name="Size", value=size)
            embed.add_field(name="Value", value=f"${value:,}")
            embed.add_field(name="Biome", value=biome.capitalize())
            embed.add_field(name="Caught by", value=f"<@{user_id}>")
            embed.add_field(name="Sold", value=f"{'true' if sold else 'false'}")

            embed.set_footer(text=f"ID: {id}")

            await interaction.response.send_message(embed=embed)

        except ValueError: # if query can't be parsed into an id
            start_time = datetime.datetime.now()

            if filter_rarity:
                self.cursor.execute("SELECT id, user_id, name, rarity FROM infi_fish WHERE name LIKE ? AND rarity = ?", (f"%{query}%", filter_rarity))
            else:
                self.cursor.execute("SELECT id, user_id, name, rarity FROM infi_fish WHERE name LIKE ?", (f"%{query}%",))
            fish_data = self.cursor.fetchall()

            end_time = datetime.datetime.now()
            query_time = int((end_time - start_time).microseconds / 1000)

            fish_data = sorted(fish_data, key=lambda x: x[0], reverse=True)

            if sort.value == "rarity_ascending":
                fish_data = sorted(fish_data, key=lambda x: x[3], reverse=False)
            elif sort.value == "rarity_descending":
                fish_data = sorted(fish_data, key=lambda x: x[3], reverse=True)

            description = ""

            for entry in fish_data[:10]:
                id, user_id, name, rarity = entry
                description += f"{name} • {':star:'}{rarity} • <@{user_id}> • `#{id}`\n"

            embed = discord.Embed(
                title="Fish Search Results",
                description=description
            )
            embed.set_footer(text=f"Found {len(fish_data)} results in {query_time}ms")

            await interaction.response.send_message(embed=embed)


    @app_commands.command(name="list_users", description="List all fishing users")
    async def list_users(self, interaction: discord.Interaction):
        self.cursor.execute("SELECT * FROM infi_user")
        user_data = self.cursor.fetchall()

        description = ""
        for user in user_data:
            id, level, xp, max_xp, balance, current_biome = user
            description += f"<@{id}> • LVL {level} {xp}/{max_xp} • {balance} \n"

        embed = discord.Embed(
            title="User List",
            description=description
        )
        
        await interaction.response.send_message(embed=embed)



    def xp_bar(self, xp, max_xp, length=10) -> str:
        progress = max(0, min(1, xp / max_xp))
        filled_bars = int(progress * length)
        remaining = (progress * length) - filled_bars

        bar_string = ""

        # left bar
        if filled_bars == 0:
            if remaining > 0.5:
                bar_string += xp_emojis["left_half"]
            elif remaining > 0:
                bar_string += xp_emojis["left_empty"]
            else:
                bar_string += xp_emojis["left_empty"]
        else:
            bar_string += xp_emojis["left_full"]

        # middle bars
        for i in range(1, length - 1):
            if i < filled_bars:
                bar_string += xp_emojis["middle_full"]
            elif i == filled_bars and remaining >= 0.5:
                bar_string += xp_emojis["middle_half"]
            else:
                bar_string += xp_emojis["middle_empty"]

        # right bar
        if filled_bars >= length - 1:
            bar_string += xp_emojis["right_full"]
        elif filled_bars == length - 1 and remaining >= 0.5:
            bar_string += xp_emojis["right_half"]
        else:
            bar_string += xp_emojis["right_empty"]

        return bar_string


    # xp growth algorithm
    def xp_required(self, level, base_xp=100, growth=15, scale=1.1):
        return int(base_xp + (level ** 2 * growth) + (level * scale * base_xp))
       

async def setup(bot):
    await bot.add_cog(Fishing(bot))