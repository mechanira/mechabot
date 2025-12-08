import discord
from discord.ext import commands, tasks
from discord import app_commands
import random
import sqlite3
import re
from collections import defaultdict, Counter
import logging
from logging.handlers import TimedRotatingFileHandler

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
        self.conn.commit()

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info(f"{__name__} is online!")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author == self.bot.user:
            return
        
        self.cursor.execute(
                "INSERT INTO generator_message_cache (id, channel_id, content) VALUES (?, ?, ?)",
                (message.id, message.channel.id, message.content)
            )
        self.conn.commit()

        if self.bot.user in message.mentions or random.random() < 0.01:    
            generated_message = self.generate_message(message.channel.id, max_words=20)
            await message.channel.send(generated_message)   


    def generate_message(self, channel_id, max_words=20):
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

        for _ in range(random.randrange(1, max_words) - 2):
            pair = (w1, w2)
            if pair not in trigram_probs:
                w1, w2 = random.choice(list(trigram_probs.keys()))
                output.extend([w1, w2])
                continue

            next_words = trigram_probs[pair]
            words = list(next_words.keys())
            probs = list(next_words.values())

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

    async def cache_channel(self, channel: discord.TextChannel, forced: bool = False):
        logger.debug(f"Starting message caching for channel: {channel.id}")

        self.cursor.execute(
            "SELECT MAX(id), content FROM generator_message_cache WHERE channel_id = ?",
            (channel.id,)
        )
        id = self.cursor.fetchone()[0]

        logger.debug(f"Last cached message ID for channel {channel.id}: {id}")

        last_msg = await channel.fetch_message(id)

        async for msg in channel.history(limit=None, after=None if forced else last_msg.id, oldest_first=True):
            if msg.author == self.bot.user:
                continue
            
            self.cursor.execute(
                "INSERT OR IGNORE INTO generator_message_cache (id, channel_id, content) VALUES (?, ?, ?)",
                (msg.id, channel.id, msg.content)
            )
            self.conn.commit()

        logger.debug(f"Cached messages for channel {channel.id}")


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

async def setup(bot):
    await bot.add_cog(Generative(bot))