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


class Generative(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = bot.logger
        self.db = bot.database

    @commands.Cog.listener()
    async def on_ready(self):
        self.logger.info(f"{__name__} is online!")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author == self.bot.user:
            return
        
        gen_config = self.db.gen_fetch_guild_config(message.guild.id)
        enabled = gen_config["enabled"]
        temperature = gen_config["temperature"]
        max_words = gen_config["max_words"]
        auto_cache = gen_config["auto_cache"]
        message_probability = gen_config["message_probability"]

        if not enabled:
            return
        
        if auto_cache:
            self.db.gen_cache_message(message.id, message.channel.id, message.content)

        if self.bot.user in message.mentions or random.random() < message_probability:
            generated_message = self.generate_message(message.channel.id, max_words, temperature)
            if generated_message:
                await message.channel.send(generated_message, allowed_mentions=discord.AllowedMentions.none())
                self.logger.debug("Generated message sent")


    def generate_message(self, channel_id, max_words, temperature):
        messages = self.db.gen_fetch_cached_message_content(channel_id)

        if messages is None or len(messages) < 3:
            self.logger.debug("Not enough messages to generate from")
            return None

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

        self.logger.debug(f"Message generated: {generated_message}")

        return generated_message


    @app_commands.command(name="cache_messages", description="Cache messages in this channel for message generation")
    async def cache_messages_command(self, interaction: discord.Interaction, forced: bool = False):
        await interaction.response.send_message("Caching messages in this channel...", ephemeral=True)
        await self.cache_channel(interaction.channel, forced)
        await interaction.followup.send("Finished caching messages in this channel!", ephemeral=True)


    async def cache_channel(self, channel: discord.TextChannel = None, forced: bool = False):
        self.logger.debug(f"Starting message caching for channel: {channel.id}")

        if forced:
            self.logger.debug("Forced caching enabled, clearing existing cache for channel")
            self.db.gen_clear_channel_cache(channel.id)

        last_cached_message = self.db.gen_fetch_last_cached_message(channel.id)

        self.logger.debug(f"Last cached message ID: {last_cached_message}")

        after = None
        if last_cached_message:
            after = discord.Object(id=last_cached_message)

        self.logger.debug(f"Fetching messages after: {after}")
        
        async for message in channel.history(limit=None, oldest_first=True, after=after):
            if message.author.bot:
                continue
            self.db.gen_cache_message(message.id, channel.id, message.content)
        
        self.logger.debug("Finished caching messages for channel")


    @app_commands.checks.has_permissions(manage_messages=True)
    @app_commands.command(name="clear_cache", description="Clears the message generation cache for this channel")
    async def delete_cache_command(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        if channel is None:
            channel = interaction.channel

        self.db.gen_clear_channel_cache(channel.id)
        await interaction.response.send_message(f"Deleted message cache for {channel.mention}", ephemeral=True)


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
            config = self.db.gen_fetch_guild_config(interaction.guild.id)
            enabled = config["enabled"]
            temperature = config["temperature"]
            max_words = config["max_words"]
            auto_cache = config["auto_cache"]
            message_probability = config["message_probability"]

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
        
        self.db.gen_update_guild_config(interaction.guild.id, option, value)
        
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