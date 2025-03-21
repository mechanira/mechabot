import discord
from discord.ext import commands
from dotenv import load_dotenv
import os
import asyncio
import traceback
import logging

load_dotenv()

bot = commands.Bot(command_prefix="m.",
                   intents=discord.Intents.all(),
                   allowed_contexts=discord.app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True)
                   )

logger = logging.getLogger("discord")

@bot.event
async def on_ready():
    print("Bot ready!")
    try:
        synced_commands = await bot.tree.sync()
        print(f"Synced {len(synced_commands)} commands.")
    except Exception as e:
        print("An error while syncing application commands has occured: ", e)

@bot.event
async def on_app_command_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
    """Global error handler for slash commands"""
    if isinstance(error, discord.app_commands.CommandNotFound):
        await interaction.response.send_message("Command not found!", ephemeral=True)
    elif isinstance(error, discord.app_commands.CheckFailure):
        await interaction.response.send_message("You don't have permission to use this command!", ephemeral=True)
    else:
        await interaction.response.send_message("An unexpected error occurred.", ephemeral=True)

@bot.event
async def on_error(event: str, *args, **kwargs):
    """Catches all uncaught runtime errors."""
    print(f"Unhandled error in {event}:")
    logger.error(f"Unhandled exception in event: {event}", exc_info=True)


async def load():
    for file in os.listdir('./cogs'):
        if file.endswith('.py'):
            await bot.load_extension(f"cogs.{file[:-3]}")

async def main():
    async with bot:
        await load()
        await bot.start(os.getenv('TOKEN'))

if __name__ == "__main__":
    asyncio.run(main())