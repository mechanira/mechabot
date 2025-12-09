import discord
from discord.ext import commands
from discord import app_commands
from yt_dlp import YoutubeDL
import os
import tempfile
from io import BytesIO
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

def yt_download_video(url):
    output_dir = "./downloads"
    os.makedirs(output_dir, exist_ok=True)

    downloaded_files = []

    def hook(d):
        if d['status'] == 'finished':
            downloaded_files.append(d['filename'])

    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'merge_output_format': 'mp4',
        'outtmpl': os.path.join(output_dir, '%(title)s.%(ext)s'),
        'ignoreerrors': True,
        'progress_hooks': [hook]
    }

    with YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    if not downloaded_files:
        raise Exception("No video file was downloaded.")

    return downloaded_files[0]


class Youtube(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info(f"{__name__} is online!")
    
    group = app_commands.Group(name="youtube", description="Youtube commands")

    @app_commands.command(name="download_video", description="Downloads Youtube video")
    async def download_video(self, interaction: discord.Interaction, url: str):
        await interaction.response.send_message("Downloading video...")

        try:
            video_path = yt_download_video(url)
            with open(video_path, "rb") as f:
                video_bytes = BytesIO(f.read())
                video_bytes.seek(0)
                file = discord.File(video_bytes, filename=os.path.basename(video_path))
                await interaction.followup.send(content="Video downloaded!", file=file)

                os.remove(video_path)

        except Exception as e:
            logger.error(e)
            await interaction.response.edit_message(f"An error occured while downloading: {e}")


async def setup(bot):
    await bot.add_cog(Youtube(bot))