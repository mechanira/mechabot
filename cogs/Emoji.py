import discord
from discord.ext import commands
from discord import app_commands
import emoji
import aiohttp
import io
import traceback
import re

class Emoji(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot


    @commands.Cog.listener()
    async def on_ready(self):
        print(f"{__name__} is online!")


    group = app_commands.Group(name="emoji", description="...")

    @group.command(name="clone", description="Clones emoji to the server")
    @app_commands.checks.has_permissions(create_expressions=True)
    async def clone(self, interaction: discord.Interaction, emoji: str, name: str = None):
        if not interaction.guild:
            return await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)

        match = re.search(r"<(a?):(\w+):(\d+)>", emoji)
        if not match:
            return await interaction.response.send_message("Invalid emoji format. Please use a custom emoji.", ephemeral=True)
        
        animated, emoji_name, emoji_id = match.groups()
        emoji_url = f"https://cdn.discordapp.com/emojis/{emoji_id}.{'gif' if animated else 'png'}"

        name = name or emoji_name

        async with aiohttp.ClientSession() as session:
            async with session.get(emoji_url) as response:
                if response.status == 200:
                    img_data = await response.read()
                    new_emoji = await interaction.guild.create_custom_emoji(name=name, image=img_data)
                    await interaction.response.send_message(f"Emoji cloned successfully: {new_emoji}")
                else:
                    await interaction.response.send_message("Failed to download the emoji.", ephemeral=True)


    @group.command(name="combine", description="Combines two emojis")
    async def ping(self, interaction: discord.Interaction,
                   emoji_1: str, emoji_2: str):
        for x in [emoji_1, emoji_2]:
            if not emoji.is_emoji(x):
                await interaction.response.send_message("Invalid emojis", ephemeral=True)

        url = f"https://emojik.vercel.app/s/{emoji_1}_{emoji_2}?size=128"
        print(url)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.read()
                        image_file = discord.File(io.BytesIO(data), filename=f"{emoji_1}_{emoji_2}.png".strip(":"))
                        await interaction.response.send_message(file=image_file)
                    else:
                        await interaction.response.send_message(f"Failed to fetch image.\nHTTP Status: {response.status}")
        except Exception as e:
            print(f"An error occured: {e}")


async def setup(bot):
    await bot.add_cog(Emoji(bot))