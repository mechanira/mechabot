import discord
from discord.ext import commands
from discord import app_commands
import random
import os

class Utils(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"{__name__} is online!")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        stripped_content = message.content.lower().strip("")

        if "im" and "hungry" in stripped_content:
            await message.reply("https://tenor.com/view/treyreloaded-horse-staring-gif-26656776") 


    @app_commands.command(name="ping", description="Gets the API latency")
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"Pong! :ping_pong: {round(interaction.client.latency * 1000)}ms")

    
    @app_commands.command(name="clear", description="Clears messages in channel after the passed message")
    @commands.has_permissions(manage_messages=True)
    async def clear(self, interaction: discord.Interaction,
                    message_id: str):
        await interaction.response.defer()

        try:
            target_message = await interaction.channel.fetch_message(int(message_id))

            deleted = await interaction.channel.purge(after = target_message.created_at)
            await interaction.response.send_message(f"Deleted {len(deleted)} messages after the specified message.")
        except discord.NotFound:
            await interaction.response.send_message("Message not found. Make sure the message ID is correct.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("I don't have permission to delete messages.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)


    @app_commands.command(name="object", description="Sends a random object with NCS music")
    async def object(self, interaction: discord.Interaction, 
                    query: str=None):
        try:
            path = "./assets/Objects on NCS Music"

            video_files = [file for file in os.listdir(path)]

            if query is not None:
                matching_videos = [file for file in video_files if f"{query}." in file]
                if not matching_videos:
                    await interaction.response.send_message(f"No object has been found. Try entering (1-1000)", ephemeral=True)
                    return
                # Select the first matching video (or modify if you want a different behavior)
                selected_video = matching_videos[0]
            else:
                # Pick a random video if no query is provided
                selected_video = random.choice(video_files)

            video_path = os.path.join(path, selected_video)

            await interaction.response.send_message(selected_video[:-4], file=discord.File(video_path))
        except Exception as e:
            print(e)


    @app_commands.command(name="meter", description="Create a random meter")
    async def meter(self, interaction: discord.Interaction, 
                    user: discord.User, meter: str):
        await interaction.response.send_message(f"{user.display_name} is **{random.randint(0, 100)}% {meter}**")


async def setup(bot):
    await bot.add_cog(Utils(bot))