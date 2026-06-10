import discord
from discord.ext import commands
from discord import app_commands
from yt_dlp import YoutubeDL
import os
import tempfile
from io import BytesIO
import logging
from logging.handlers import TimedRotatingFileHandler
import random


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
        self.logger = bot.logger

        self.clear_downloads()

        self.object_video_cache = []
        self.cache_object_videos()

        

    @commands.Cog.listener()
    async def on_ready(self):
        self.logger.info(f"{__name__} is online!")


    def clear_downloads(self):
        download_dir = "./downloads"
        os.makedirs(download_dir, exist_ok=True)
        
        for filename in os.listdir(download_dir):
            file_path = os.path.join(download_dir, filename)
            try:
                if os.path.isfile(file_path):
                    os.remove(file_path)
            except Exception as e:
                self.logger.error(f"Error while clearing downloads: {e}")


    def cache_object_videos(self):
        yt_channel_url = "https://www.youtube.com/@objectsonncsmusic"
        video_blacklist = [
            "https://www.youtube.com/watch?v=tMiJ2Nk7zOQ"
        ]

        ydl_opts = {
            'ignoreerrors': True,
            'quiet': True,
            'skip_download': True,
            'extract_flat': True,
        }
        with YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(yt_channel_url, download=False)
            if 'entries' not in result:
                self.logger.error("Could not retrieve videos from the channel.")
                return

            self.object_video_cache = [entry for entry in result['entries'] if entry is not None]
            if not self.object_video_cache:
                self.logger.error("No videos found in the channel.")
                return
            
            # filter out blacklisted videos
            self.object_video_cache = [video for video in self.object_video_cache if f"https://www.youtube.com/watch?v={video['id']}" not in video_blacklist]

        self.logger.info(f"Successfully cached {len(self.object_video_cache)}/1000 object videos!")
    

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
            self.logger.error(e)
            await interaction.response.edit_message(f"An error occured while downloading: {e}")

    
    @app_commands.command(name="object", description="Posts a random object with NCS music")
    async def object_command(self, interaction: discord.Interaction, query: str = None):
        await interaction.response.defer(thinking=True)

        if not self.object_video_cache:
            await interaction.followup.send("No videos available.")
            return
        
        query = query.lower() if query else None
        if query:
            filtered_videos = [video for video in self.object_video_cache if query in video['title'].lower()]
            if not filtered_videos:
                # if no videos match the query, try the assets/Objects on NCS Music playlist instead
                folder_path = "./assets/Objects on NCS Music"
                
                video_files = [f for f in os.listdir(folder_path) if f.endswith('.mp4')]
                
                matching_videos = [f for f in video_files if query in f.lower()]
                if not matching_videos:
                    await interaction.followup.send("No videos found matching the query, and no fallback videos available.")
                    return
                
                video_file = random.choice(matching_videos)
                video_path = os.path.join(folder_path, video_file)

                with open(video_path, "rb") as f:
                    video_bytes = BytesIO(f.read())
                    video_bytes.seek(0)
                    file = discord.File(video_bytes, filename=os.path.basename(video_path))
                    await interaction.followup.send(content=f"{video_file[:-4]}", file=file)
                return
            
            video = random.choice(filtered_videos)
        else:
            video = random.choice(self.object_video_cache)
        
        video_url = f"https://www.youtube.com/watch?v={video['id']}"

        try:
            video_path = yt_download_video(video_url)
            with open(video_path, "rb") as f:
                video_bytes = BytesIO(f.read())
                video_bytes.seek(0)
                file = discord.File(video_bytes, filename=os.path.basename(video_path))
                await interaction.followup.send(content=f"{video['title']} [∾](<{video_url}>)", file=file)

            os.remove(video_path)
        except Exception as e:
            self.logger.error(e)
            await interaction.followup.send(f"An error occured while downloading: {e}")


async def setup(bot):
    await bot.add_cog(Youtube(bot))