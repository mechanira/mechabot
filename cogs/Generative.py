import discord
from discord.ext import commands, tasks
from discord import app_commands
import random
import sqlite3
import re
from collections import defaultdict, Counter
import logging
from logging.handlers import TimedRotatingFileHandler
import math

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

handler = TimedRotatingFileHandler(filename='logs/bot.log', encoding='utf-8', when='midnight', interval=1, backupCount=7)
handler.setFormatter(logging.Formatter('[%(asctime)s] [%(levelname)s/%(name)s]: %(message)s'))
logger.addHandler(handler)

console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('[%(asctime)s] [%(levelname)s/%(name)s]: %(message)s'))
logger.addHandler(console_handler)

class Generative(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        self.conn = sqlite3.connect('data.db')
        self.cursor = self.conn.cursor()
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS generator_message_cache(
                id INTEGER PRIMARY KEY,
                channel_id INTEGER NOT NULL,
                content TEXT NOT NULL
            )
        """)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS guild_generative_config(
                id INTEGER PRIMARY KEY,
                enabled BOOLEAN NOT NULL,
                temperature REAL NOT NULL,
                max_words INTEGER NOT NULL,
                auto_cache BOOLEAN NOT NULL,
                message_probability REAL NOT NULL
            )
        """)
        self.conn.commit()

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info(f"{__name__} is online!")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author == self.bot.user:
            return
        
        gen_config = self.cursor.execute(
                "SELECT * FROM guild_generative_config WHERE id = ?", (message.guild.id,)
            ).fetchone()
        id, enabled, temperature, max_words, auto_cache = gen_config if gen_config else (message.guild.id, False, 1.5, 100, False)

        if not enabled:
            return
        
        if auto_cache:
            self.cursor.execute(
                "INSERT OR IGNORE INTO generator_message_cache (id, channel_id, content) VALUES (?, ?, ?)", (message.id, message.channel.id, message.content,)
            )
            self.conn.commit()

        if self.bot.user in message.mentions or random.random() < 0.002:
            generated_message = self.generate_message(message.channel.id, max_words, temperature)
            await message.channel.send(generated_message, allowed_mentions=discord.AllowedMentions.none())
            logger.debug("Generated message sent")


    def generate_message(self, channel_id, max_words, temperature):
        messages = []

        self.cursor.execute(
            "SELECT content FROM generator_message_cache WHERE channel_id = ?",
            (channel_id,)
        )
        rows = self.cursor.fetchall()
        for row in rows:
            messages.append(row[0])

        trigram_counts = self.build_trigram_counts(messages)
        trigram_probs = self.convert_to_probabilities(trigram_counts)

        # Generate message using trigram probabilities
        seed_pair = random.choice(list(trigram_probs.keys()))
        
        w1, w2 = seed_pair
        output = [w1, w2]

        for _ in range(max_words - 2):
            pair = (w1, w2)
            if pair not in trigram_probs and random.random() < 0.5:
                w1, w2 = random.choice(list(trigram_probs.keys()))
                output.extend([w1, w2])
                continue
            
            if pair not in trigram_probs:
                break

            next_words = trigram_probs[pair]
            
            tempered = self.apply_temperature(next_words, temperature)

            words = list(tempered.keys())
            probs = list(tempered.values())

            # Weighted random choice using trigram probabilities
            w3 = random.choices(words, weights=probs, k=1)[0]

            output.append(w3)
            w1, w2 = w2, w3

        generated_message = " ".join(output)

        logger.debug(f"Message generated: {generated_message}")

        return generated_message

    @app_commands.command(name="cache_messages", description="Cache messages in this channel for message generation")
    async def cache_messages_command(self, interaction: discord.Interaction, force: bool = False):
        await interaction.response.send_message("Caching messages in this channel...", ephemeral=True)
        await self.cache_channel(interaction.channel, force)
        await interaction.followup.send("Message caching complete!", ephemeral=True)


    async def cache_channel(self, channel: discord.TextChannel = None, forced: bool = False):
        logger.debug(f"Starting message caching for channel: {channel.id}")

        self.cursor.execute(
            "SELECT MAX(id) FROM generator_message_cache WHERE channel_id = ?",
            (channel.id,)
        )
        result = self.cursor.fetchone()
        id = result[0]

        logger.debug(f"Last cached message ID for channel {channel.id}: {id}")
        

        async for msg in channel.history(limit=None, after=None if forced else id, oldest_first=True):
            if msg.author.bot:
                continue
            
            self.cursor.execute(
                "INSERT OR IGNORE INTO generator_message_cache (id, channel_id, content) VALUES (?, ?, ?)",
                (msg.id, channel.id, msg.content)
            )
            self.conn.commit()

        logger.info(f"Cached messages for channel {channel.id}")


    @app_commands.checks.has_permissions(manage_messages=True)
    @app_commands.command(name="delete_cache", description="Deletes the message generation cache for this channel")
    async def delete_cache_command(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        if interaction.user.guild_permissions.manage_messages == False:
            await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
            return

        if channel == None:
            channel = interaction.channel

        self.cursor.execute(
            "DELETE FROM generator_message_cache WHERE channel_id = ?",
            (channel.id,)
        )
        self.conn.commit()

        logger.info(f"Deleted message generation cache for channel: {channel.id}")
        await interaction.response.send_message("Deleted message generation cache", ephemeral=True)


    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.command(name="gen_config", description="Configure the generative message settings")
    @app_commands.choices(option=[
        app_commands.Choice(name="enabled", value="enabled"),
        app_commands.Choice(name="temperature", value="temperature"),
        app_commands.Choice(name="max_words", value="max_words"),
        app_commands.Choice(name="auto_cache", value="auto_cache")
    ])
    async def gen_config_command(self, interaction: discord.Interaction, option: str = None, value: str = None):
        if interaction.user.guild_permissions.manage_guild == False:
            await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
            return

        if option == None or value == None:
            self.cursor.execute(
                "SELECT * FROM guild_generative_config WHERE id = ?", (interaction.guild.id,)
            )
            row = self.cursor.fetchone()
            if row is None:
                self.cursor.execute(
                    "INSERT INTO guild_generative_config (id, enabled, temperature, max_words, auto_cache, message_probability) VALUES (?, ?, ?, ?, ?, ?)",
                    (interaction.guild.id, False, 1.5, 100, False, 0.002)
                )
                row = (interaction.guild.id, False, 1.5, 100, False, 0.002)
                self.conn.commit()

            guild_id, enabled, temperature, max_words, auto_cache, message_probability = row

            embed = discord.Embed(
                title="Message Gen Config",
                description=f"`enabled` - {self.bool_emoji(enabled)}\n`temperature` - `{temperature}`\n`max_words` - `{max_words}`\n`auto_cache` - {self.bool_emoji(auto_cache)}\n`message_probability` - `{message_probability}`",
            )

            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        if option in ("enabled", "auto_cache"):
            value = value.lower() in ("true", "on")
        elif option in ("temperature", "message_probability"):
            try:
                value = float(value)
            except ValueError:
                await interaction.response.send_message("Value must be a number.", ephemeral=True)
                return
        elif option == "max_words":
            try:
                value = int(value)
            except ValueError:
                await interaction.response.send_message("Value must be an integer.", ephemeral=True)
                return
        else:
            await interaction.response.send_message("Invalid option.", ephemeral=True)
            return
        
        self.cursor.execute(
            f"UPDATE guild_generative_config SET {option} = ? WHERE id = ?",
            (value, interaction.guild.id)
        )
        self.conn.commit()
        
        await interaction.response.send_message(f"Set `{option}` to `{value}`", ephemeral=True)


    def build_trigram_counts(self, messages):
        trigram_counts = defaultdict(Counter)  # {(w1, w2): Counter({w3: n})}

        for msg in messages:
            words = msg.lower().split() # self.tokenize(msg)
            for w1, w2, w3 in zip(words, words[1:], words[2:]):
                trigram_counts[(w1, w2)][w3] += 1

        return trigram_counts
    
    def convert_to_probabilities(self, trigram_counts):
        trigram_probs = {}

        for pair, next_words in trigram_counts.items():
            total = sum(next_words.values())
            trigram_probs[pair] = {w3: count / total for w3, count in next_words.items()}

        return trigram_probs
    

    def tokenize(self, text):
        URL_REGEX = r'https?://\S+|www\.\S+'
        EMOJI_REGEX = r'<a?:\w+:\d+>'
        WORD_REGEX = r"[a-zA-Z0-9]+(?:'[a-zA-Z0-9]+)*"

        text = re.sub(URL_REGEX, '', text)
        
        text = re.sub(EMOJI_REGEX, '', text)
        
        return re.findall(WORD_REGEX, text.lower())
    
    
    def apply_temperature(self, probs, temperature):
        if temperature <= 0:
            # deterministic (argmax)
            max_word = max(probs, key=probs.get)
            return {max_word: 1.0}

        # Adjust probabilities
        adjusted = {
            w: math.pow(p, 1.0 / temperature)
            for w, p in probs.items()
        }

        # Normalize
        total = sum(adjusted.values())
        return {w: p / total for w, p in adjusted.items()}
    
    def bool_emoji(self, value: bool) -> str:
        return "✅" if value else "❌"

async def setup(bot):
    await bot.add_cog(Generative(bot))