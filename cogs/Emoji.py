import discord
from discord.ext import commands
from discord import app_commands
import emoji
import aiohttp
import io

class Emoji(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"{__name__} is online!")

    group = app_commands.Group(name="emoji", description="...")

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