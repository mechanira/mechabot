import discord
from discord.ext import commands
from discord import app_commands
import random
import os
import asyncio
import subprocess
import time

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
    async def sam(self, interaction: discord.Interaction, text: str):
        output_file = self.generate_sam_voice(text)
        file = discord.File(output_file, filename=f"sam_tts_{interaction.id}.wav")

        await interaction.response.send_message(file=file)


    def generate_sam_voice(self, text):
        output_file = "sam_output.wav"
        subprocess.run(["node", "sam_tts.js", text, 0.5])
        return output_file
    

async def setup(bot):
    await bot.add_cog(Voice(bot))