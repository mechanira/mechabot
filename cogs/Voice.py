import discord
from discord.ext import commands
from discord import app_commands
import subprocess
import requests
import os
from pydub import AudioSegment
import traceback

class Voice(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.voice_clients = {}
        self.sam_whitelist = [425661467904180224]

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"{__name__} is online!")

    """
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.id not in self.sam_whitelist:
            return
        
        guild_id = message.guild.id if message.guild else None
        if guild_id and guild_id in self.voice_clients:
            text = message.content[:100]  # Limit text length for TTS
            if text:
                tts_audio = self.generate_sam_voice(text)
                if tts_audio:
                    if not self.voice_clients[guild_id].is_playing():
                        self.voice_clients[guild_id].play(discord.FFmpegPCMAudio(tts_audio))"
    """
        

    @app_commands.command(name="join", description="Join current VC")
    async def join(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id
        if interaction.user.voice:
            channel = interaction.user.voice.channel

            if guild_id in self.voice_clients and self.voice_clients[guild_id].is_connected():
                await interaction.response.send_message("I'm already in a voice channel", ephemeral=True)
                return
            
            self.voice_clients[guild_id] = await channel.connect()
            await interaction.response.send_message(f"Joined {channel.name}", ephemeral=True)
        else:
            await interaction.response.send_message("You need to be in a voice channel first!")


    @app_commands.command(name="leave", description="Leave VC")
    async def leave(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id
        if guild_id in self.voice_clients:
            await self.voice_clients[guild_id].disconnect()
            del self.voice_clients[guild_id]
            await interaction.response.send_message("Left the voice channel!", ephemeral=True)
        else:
            await interaction.response.send_message("I'm not in a voice channel!", ephemeral=True)


    @app_commands.command(name="sam", description="Software Automatic Mouth (SAM) text-to-speech")
    async def sam(self, interaction: discord.Interaction, text: str, voice_message: bool = False):
        try:
            output_file = self.generate_sam_voice(text)
            file = discord.File(output_file, filename=f"sam_tts_{interaction.id}.wav")

            await interaction.response.send_message(file=file, ephemeral=voice_message)

            if not voice_message:
                return

            upload_url, uploaded_filename = self.request_url(interaction.channel.id)
            self.upload_audio_file(upload_url)
            self.send_voice_message(interaction.channel.id, uploaded_filename)
        except:
            print(traceback.print_exc())


    def generate_sam_voice(self, text):
        output_file = "sam_output.wav"
        subprocess.run(["node", "sam_tts.js", text])
        return output_file
    

    def request_url(self, channel_id):
        # convert the audio file
        ffmpeg_command = ["ffmpeg", "-y", "-i", "sam_output.wav", "-c:a", "libopus", "sam_output.ogg"]
        subprocess.run(ffmpeg_command, check=True)

        token = os.getenv('TOKEN')

        file_size = os.path.getsize("sam_output.ogg")

        url = f"https://discord.com/api/v10/channels/{channel_id}/attachments"
        data = {
            "files": [
                {
                "filename": "sam_output.ogg",
                "file_size": file_size,
                "id": "2"
                }
            ]
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bot {token}"
        }

        response = requests.post(url, json=data, headers=headers)

        if response.status_code == 200:
            data = response.json()
            attachments = data.get("attachments", [])

            if attachments:
                upload_url = attachments[0].get("upload_url")
                upload_filename = attachments[0].get("upload_filename")
                return upload_url, upload_filename
            else:
                raise ValueError("No attachments found in response.")
        else:
            raise ValueError(f"Failed to get upload URL. Status: {response.status_code}, Response: {response.text}")


    def upload_audio_file(self, url):
        token = os.getenv('TOKEN')

        with open("sam_output.ogg", "rb") as file:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bot {token}"
            }

            response = requests.put(url, data=file, headers=headers)

            if response.status_code != 200:
                print(f"Audio file upload failed: {response.status_code}, {response.text}")


    def send_voice_message(self, channel_id, uploaded_filename):
        token = os.getenv('TOKEN')
        url = f"https://discord.com/api/v10/channels/{channel_id}/messages"

        data =  {
            "flags": 8192,
            "attachments": [
                {
                "id": 0,
                "filename": "sam_output.ogg",
                "uploaded_filename": uploaded_filename,
                "duration_secs": 0,
                "waveform": "WzAsIDAsIDAsIDAsIDAsIDAsIDAsIDAsIDAsIDAsIDAsIDBd"
                }
            ]
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bot {token}"
        }

        response = requests.post(url, json=data, headers=headers)

        if response.status_code != 200:
            print(f"Voice message eupload failed: {response.status_code}, {response.text}")



    

async def setup(bot):
    await bot.add_cog(Voice(bot))