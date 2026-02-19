import discord
from discord.ext import commands
from dotenv import load_dotenv
import os
import asyncio
import traceback
import logging
from logging.handlers import TimedRotatingFileHandler

load_dotenv()

bot = commands.Bot(command_prefix="m.",
                   intents=discord.Intents.all(),
                   allowed_contexts=discord.app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True),
                   activity=discord.Game(name=os.getenv("BOT_STATUS"))
                   )

os.makedirs("logs", exist_ok=True)

logger = logging.getLogger("main")
logger.setLevel(logging.INFO)

handler = TimedRotatingFileHandler(filename='logs/bot.log', encoding='utf-8', when='midnight', interval=1, backupCount=7)
handler.setFormatter(logging.Formatter('[%(asctime)s] [%(levelname)s/%(name)s]: %(message)s'))
logger.addHandler(handler)

console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('[%(asctime)s] [%(levelname)s/%(name)s]: %(message)s'))
logger.addHandler(console_handler)

@bot.event
async def on_ready():
    logger.info("Bot ready!")
    try:
        synced_commands = await bot.tree.sync()
        logger.info(f"Synced {len(synced_commands)} commands.")
    except Exception as e:
        logger.error("An error while syncing application commands has occured: ", e)

@bot.event
async def on_app_command_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
    """Global error handler for slash commands"""
    if isinstance(error, discord.app_commands.CommandNotFound):
        await interaction.response.send_message("Command not found!", ephemeral=True)
    elif isinstance(error, discord.app_commands.MissingPermissions):
        await interaction.response.send_message("You don't have permission to use this command!", ephemeral=True)
    else:
        await interaction.response.send_message("An unexpected error occurred.", ephemeral=True)

@bot.event
async def on_interaction(interaction):
    logger.debug(f"Interaction received! {interaction.type}")

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