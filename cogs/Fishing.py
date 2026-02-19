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
import logging
from logging.handlers import TimedRotatingFileHandler
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

handler = TimedRotatingFileHandler(filename='logs/bot.log', encoding='utf-8', when='midnight', interval=1, backupCount=7)
handler.setFormatter(logging.Formatter('[%(asctime)s] [%(levelname)s/%(name)s]: %(message)s'))
logger.addHandler(handler)

console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('[%(asctime)s] [%(levelname)s/%(name)s]: %(message)s'))
logger.addHandler(console_handler)

with open("data/fishing/items.json", "r") as f:
    ITEM_REGISTRY = json.load(f)
    logger.debug(f"Loaded item registry with {len(ITEM_REGISTRY)} items")

emojis = None
logger.debug(f"Loaded emoji mappings!")

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
    discord.Color.orange()
]

async def item_autocomplete(interaction: discord.Interaction, current: str):
    current = current.lower()
    matched_items = [item for item in ITEM_REGISTRY if current in item['name'].lower() and item['type'] in ['rod', 'bait', 'accessory']]
    return [app_commands.Choice(name=item['name'], value=item['name']) for item in matched_items[:25]]

class Fishing(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.conn = sqlite3.connect('data.db')
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS fish_user(
                id INTEGER PRIMARY KEY,
                level INTEGER DEFAULT 1,
                xp INTEGER DEFAULT 0,
                max_xp INTEGER DEFAULT 100,
                money INTEGER DEFAULT 0,
                current_biome TEXT DEFAULT 'river'
            )
        """)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS fish_inventory(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER,
                user_id INTEGER,
                quantity INTEGERL,
                UNIQUE(item_id, user_id)
            )
        """)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS fish_equipment(
                user_id INTEGER NOT NULL,
                slot TEXT NOT NULL,
                item_id INTEGER,
                PRIMARY KEY (user_id, slot)
            )
        """)
        self.conn.commit()


    @commands.Cog.listener()
    async def on_ready(self):
        try:
            logger.info(f"{__name__} is online!")
        except Exception as e:
            logger.error(f"Error during on_ready: {e}")
    
    
    @app_commands.checks.cooldown(1, 5.0, key=lambda i: (i.user.id))
    @app_commands.command(name="fish", description="Catch a fish!")
    async def fish(self, interaction: discord.Interaction):
        user_id = interaction.user.id

        self.cursor.execute("SELECT level, xp, max_xp, current_biome FROM fish_user WHERE id = ?", (user_id,))
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
        highest_rarity = 0
        
        rolls = 1
        catches = []

        for _ in range(rolls):
            rarity = random.choices(rarity_levels, weights)[0]
            highest_rarity = max(highest_rarity, rarity)

            fish_items = [item for item in ITEM_REGISTRY if item['rarity'] == rarity and current_biome in item['biome']]
            if not fish_items:
                logger.warning(f"No fish found for rarity {rarity} in biome {current_biome}")
                continue
            catch = random.choice(fish_items)
            catches.append(dict(catch))
        
        xp_gain = int(sum(catch['value'] for catch in catches) / 2)
        xp += xp_gain
        old_level = level

        level_label = f"Level {level}"

        while(xp >= max_xp):
            xp -= max_xp
            max_xp = self.xp_required(level=level)
            level += 1
            level_label = f"**LEVEL UP! {old_level} >> {level}**"

        self.cursor.execute("""
            INSERT INTO fish_user (id, level, xp, max_xp, current_biome) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET level = ?, xp = ?, max_xp = ?, current_biome = ?
        """, (user_id, level, xp, max_xp, current_biome, level, xp, max_xp, current_biome))

        stacks = {}
        for catch in catches:
            self.cursor.execute("""
                INSERT INTO fish_inventory (item_id, user_id, quantity)
                VALUES (?, ?, ?)
                ON CONFLICT(item_id, user_id)
                DO UPDATE SET quantity = quantity + excluded.quantity
                """, (catch["id"], user_id, 1))

            catch_name = f"{catch['name']} {':star:' * catch['rarity']}"
            stacks[catch_name] = stacks.get(catch_name, 0) + 1

        catch_descriptions = [f"`x{quantity}` **{name}**" for name, quantity in stacks.items()]
        description = "\n".join(catch_descriptions)

        embed = discord.Embed(
            title=f"Caught fish",
            description=f"""
                            {description}
                            {level_label}
                            {self.xp_bar(xp, max_xp)} {xp:,}/{max_xp:,} {f'`+{xp_gain}`' if xp_gain > 0 else ''}
                        """,
            color=rarity_colors[highest_rarity]
        )
        embed.set_footer(text=f"Biome: {current_biome.capitalize()}")
        
        self.conn.commit()

        await interaction.response.send_message(embed=embed)


    @fish.error
    async def fish_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.CommandOnCooldown):
            await interaction.response.send_message(f"You are on cooldown! Try again <t:{int(error.retry_after + datetime.now().timestamp())}:R>", ephemeral=True)
    

    @app_commands.command(name="inventory", description="Check your fish inventory")
    async def inventory_command(self, interaction: discord.Interaction, item_name: str = None):
        if item_name:
            item_name_internalized = item_name.lower().replace(" ", "_")
            matched_item = next((item for item in ITEM_REGISTRY if item['internal_name'] == item_name_internalized), None)
            if not matched_item:
                await interaction.response.send_message("No such item exists. Try again!", ephemeral=True)
                return
            item_id = matched_item['id']

            self.cursor.execute("""
                SELECT item_id, quantity FROM fish_inventory WHERE user_id = ? AND item_id = ?
            """, (interaction.user.id, item_id,))
            item_stack = self.cursor.fetchone()

            if not item_stack:
                await interaction.response.send_message("No such items found in your inventory!", ephemeral=True)
                return
            
            embed = discord.Embed(
                title="Inventory",
                description=f"""
                `x{item_stack[1]:,}` **{matched_item['name']}** {':star:' * matched_item['rarity']}
                *"{matched_item['lore']}"*
                """
            )
            await interaction.response.send_message(embed=embed)
            return

        self.cursor.execute("""
            SELECT item_id, quantity FROM fish_inventory WHERE user_id = ?
        """, (interaction.user.id,))
        inventory_data = self.cursor.fetchall()

        if not inventory_data:
            await interaction.response.send_message("Your inventory is empty!", ephemeral=True)
            return

        description = ""
        for item_id, quantity in inventory_data[:10]:
            item_info = next((item for item in ITEM_REGISTRY if item['id'] == item_id), None)
            if item_info:
                description += f"`x{quantity}` **{item_info['name']}**\n"

        embed = discord.Embed(
            title=f"{interaction.user.display_name}'s Inventory",
            description=description
        )

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
    async def biomes_command(self, interaction: discord.Interaction, biome: app_commands.Choice[str] = None):
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

        user_data = self.cursor.execute("SELECT level FROM fish_user WHERE id = ?", (interaction.user.id,))
        level = user_data.fetchone()[0]

        if level < biome_level_requirements[biome.value]:
            await interaction.response.send_message(f"You need to be level {biome_level_requirements[biome.value]} to access the {biome.name} biome!", ephemeral=True)
            return


        self.cursor.execute(
            "UPDATE infi_user SET current_biome = ? WHERE id = ?",
            (biome.value, interaction.user.id))
        self.conn.commit()

        await interaction.response.send_message(f"Biome successfully changed to **{biome.name}**!")

    
    @app_commands.command(name="equip", description="Equip a fishing item to gain its bonuses. Run the same command again to unequip.")
    @app_commands.autocomplete(item_name=item_autocomplete)
    async def equip_command(self, interaction: discord.Interaction, item_name: str):
        matched_item = self.get_item(item_name)
        if not matched_item:
            await interaction.response.send_message("No such item exists. Try again!", ephemeral=True)
            return


    def get_item(self, item_name: str):
        item_name_internalized = item_name.lower().replace(" ", "_")
        matched_item = next((item for item in ITEM_REGISTRY if item['internal_name'] == item_name_internalized), None)
        return matched_item


    """
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
    """

    
    @app_commands.command(name="profile", description="Check your fishing profile")
    async def profile(self, interaction: discord.Interaction):
        self.cursor.execute("SELECT level, xp, max_xp, balance, current_biome FROM fish_user WHERE id = ?", (interaction.user.id,))
        user_data = self.cursor.fetchone()

        if user_data is None:
            user_data = (1, 0, 100, 0, 'river')

        level, xp, max_xp, balance, current_biome = user_data
        
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
        if emojis is None:
            return ""

        progress = max(0, min(1, xp / max_xp))
        filled_bars = int(progress * length)
        remaining = (progress * length) - filled_bars

        bar_string = ""

        for i in range(length):
            if i < filled_bars:
                if i == 0:
                    bar_string += emojis["xp_left_full"]
                elif i == length - 1:
                    bar_string += emojis["xp_right_full"]
                else:
                    bar_string += emojis["xp_middle_full"]
            elif i == filled_bars and remaining >= 0.5:
                if i == 0:
                    bar_string += emojis["xp_left_half"]
                elif i == length - 1:
                    bar_string += emojis["xp_right_half"]
                else:
                    bar_string += emojis["xp_middle_half"]
            else:
                if i == 0:
                    bar_string += emojis["xp_left_empty"]
                elif i == length - 1:
                    bar_string += emojis["xp_right_empty"]
                else:
                    bar_string += emojis["xp_middle_empty"]

        return bar_string


    # xp growth algorithm
    def xp_required(self, level, base_xp=100, growth=15, scale=1.1):
        return int(base_xp + (level ** 2 * growth) + (level * scale * base_xp))
       

async def setup(bot):
    await bot.add_cog(Fishing(bot))