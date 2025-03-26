import discord
from discord.ext import commands
from discord import app_commands
import random
import os
import traceback
import re

kaomoji = [">.<", ":3", "^-^", "^.^", ">w<", "^.~", "~.^", ">.<", "^o^", "^_^", ">.>", "^3^"]
uwu_pattern = [
    (r'[rl]', 'w'),
    (r'[RL]', 'W'),
    (r'n([aeiou])', 'ny\\g<1>'),
    (r'N([aeiou])', 'Ny\\g<1>'),
    (r'N([AEIOU])', 'NY\\g<1>'),
    (r'ove', 'uv'),
]
stutter_chance = 0.25
kaomoji_chance = 0.25

def uwuify(string: str):
    words = string.split(' ')

    for idx, word in enumerate(words):
        if not word:
            continue

        if re.search(r'((http:|https:)//[^ \<]*[^ \<\.])', word):
            continue

        if word[0] == '@' or word[0] == '#' or word[0] == ':' or word[0] == '<':
            continue

        for pattern, substitution in uwu_pattern:
            word = re.sub(pattern, substitution, word)
        
        # stutter handling
        next_char_case = word[1].isupper() if len(word) > 1 else False
        _word = ''
        
        if random.random() <= stutter_chance:
            stutter_len = random.randrange(1, 3)
            
            for j in range(stutter_len + 1):
                _word += (word[0] if j == 0 else (word[0].upper() if next_char_case else word[0].lower())) + "-"
                
            _word += (word[0].upper() if next_char_case else word[0].lower()) + word[1:]
        
        # kaomoji handling
        if random.random() <= kaomoji_chance:
            _word = (_word or word) + ' ' + kaomoji[random.randrange(0, len(kaomoji))]

        words[idx] = (_word or word)

    return ' '.join(words)
    

class Utils(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.uwuified = []

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"{__name__} is online!")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        try:
            if message.author.bot:
                return
            
            channel = message.channel

            if message.author.id in self.uwuified:
                webhooks = await channel.webhooks()
                webhook = next((wh for wh in webhooks if wh.name == "mechabot"), None)

                if webhook is None:
                    webhook = await channel.create_webhook(name="mechabot")

                uwuified_message = uwuify(message.content)
                print(uwuified_message)

                await message.delete()
                await webhook.send(
                    content=uwuified_message,
                    username=message.author.display_name,
                    avatar_url=message.author.display_avatar.url
                )

            stripped_content = message.content.lower().strip("")

            if "im" and "hungry" in stripped_content:
                await message.reply("https://tenor.com/view/treyreloaded-horse-staring-gif-26656776")
        except:
            print(traceback.print_exc())


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


    @app_commands.command(name="uwu", description="Toggle message uwuifier")
    async def uwu(self, interaction: discord.Interaction):
        if interaction.user.id not in self.uwuified:
            self.uwuified.append(interaction.user.id)
            await interaction.response.send_message("Turned uwuify on")
        else:
            self.uwuified.remove(interaction.user.id)
            await interaction.response.send_message("Turned uwuifier off")


async def setup(bot):
    await bot.add_cog(Utils(bot))