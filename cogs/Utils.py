import discord
from discord.ext import commands
from discord import app_commands
from discord.app_commands import Choice
import random
import os
import re
import aiohttp
import numpy as np
from PIL import Image
from io import BytesIO
from petpetgif import petpet
import sqlite3
import deepl
import zipfile
import json

kaomoji = [">.<", ":3", "^-^", "^.^", ">w<", "^.~", "~.^", ">.<", "^o^", "^_^", ">.>", "^3^"]
meows = ["meow", "nya", "mrow", "mrrp", "mreow", "mew", "miau"]

uwu_pattern = [
    (r'[rl]', 'w'),
    (r'[RL]', 'W'),
    (r'n([aeiou])', 'ny\\g<1>'),
    (r'N([aeiou])', 'Ny\\g<1>'),
    (r'N([AEIOU])', 'NY\\g<1>'),
    (r'ove', 'uv'),
]
lolcat_pattern = {
    'er': 'r',
    'you': 'u',
    'have': 'haz',
    'can i': 'i can',
    's': 'z',
    'th': 'd',
    'y': 'eh'
}

eight_ball_responses = [
    "It is certain.", "It is decidedly so.", "Without a doubt.",
    "Yes - definitely.", "You may rely on it.", "As I see it, yes.",
    "Most likely.", "Outlook good.", "Yes.", "Signs point to yes.",
    
    "Reply hazy, try again.", "Ask again later.", "Better not tell you now.",
    "Cannot predict now.", "Concentrate and ask again.",
    
    "Don't count on it.", "My reply is no.", "My sources say no.",
    "Outlook not so good.", "Very doubtful."
]

stutter_chance = 0.5
kaomoji_chance = 0.5


def translate_uwu(string: str):
    words = string.split(' ')

    for idx, word in enumerate(words):
        if not word:
            continue
        
        # link
        if re.search(r'((http:|https:)//[^ \<]*[^ \<\.])', word):
            words[idx] = word
            continue
        
        # discord mention, emoji
        if word[0] == '@' or word[0] == '#' or word[0] == ':' or word[0] == '<':
            words[idx] = word
            continue

        if word in kaomoji:
            words[idx] = word
            continue

        for pattern, substitution in uwu_pattern:
            word = re.sub(pattern, substitution, word)
        
        next_char_case = word[1].isupper() if len(word) > 1 else False
        _word = ''
        
        if random.random() <= stutter_chance:
            stutter_len = random.randrange(1, 3)
            
            for j in range(stutter_len + 1):
                _word += (word[0] if j == 0 else (word[0].upper() if next_char_case else word[0].lower())) + "-"
                
            _word += (word[0].upper() if next_char_case else word[0].lower()) + word[1:]
        
        if random.random() <= kaomoji_chance:
            _word = (_word or word) + ' ' + kaomoji[random.randrange(0, len(kaomoji))]

        words[idx] = (_word or word)

    return ' '.join(words)


def translate_lolcat(string: str):
    pass
    

class Utils(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = bot.logger
        self.uwuified = []
        self.DEEPL_API_KEY = os.getenv("DEEPL_API_KEY")
        self.deepl_client = deepl.DeepLClient(self.DEEPL_API_KEY)

        self.ctx_menus = {
            "translate": app_commands.ContextMenu(
                name="Translate",
                callback=self.translate_context_menu
            )
        }
        self.bot.tree.add_command(self.ctx_menus["translate"])

        self.conn = sqlite3.connect('data.db')
        self.cursor = self.conn.cursor()

    @commands.Cog.listener()
    async def on_ready(self):
        self.logger.info(f"{__name__} is online!")


    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        try:
            channel = message.channel

            if message.author.bot:
                return

            if message.author.id in self.uwuified:
                webhooks = await channel.webhooks()
                webhook = next((wh for wh in webhooks if wh.name == "mechabot"), None)

                if webhook is None:
                    webhook = await channel.create_webhook(name="mechabot")

                uwuified_message = translate_uwu(message.content)
                self.logger.debug(f"Message uwuified: {uwuified_message}")

                await message.delete()

                reference_message = None
                if message.reference and message.mentions:
                    try:
                        reference_message = await channel.fetch_message(message.reference.message_id)
                    except:
                        pass
                
                reply_substring = f"-# [↪]({reference_message.jump_url}) {message.mentions[0].mention} {reference_message.content}\n" if message.reference and message.mentions else ""

                webhook_allowed_mentions = discord.AllowedMentions(users=False, roles=False, everyone=False)

                await webhook.send(
                    content=reply_substring + uwuified_message,
                    username=message.author.display_name,
                    avatar_url=message.author.display_avatar.url,
                    allowed_mentions=webhook_allowed_mentions
                )

            stripped_content = message.content.lower().strip("")

            if "im" and "hungry" in stripped_content:
                hungry_horse = [
                    "https://media.discordapp.net/attachments/1286778100616527915/1355572584619573428/images.png?ex=67e96ad9&is=67e81959&hm=c7d2f8408782b2771497939fb4af00a69f6929b5fae9b9d7b8d69afbec2a9121&=&format=webp&quality=lossless",
                    "https://tenor.com/view/treyreloaded-horse-staring-gif-26656776"
                ]

                await message.reply(random.choice(hungry_horse))

            for meow in meows:
                if meow in message.content.lower():
                    await message.channel.send(random.choice(meows))
                    break

            if message.content.startswith(":3") and message.content.endswith("3"):
                await message.channel.send(":3")

        except Exception as e:
            self.logger.error(e)


    @app_commands.command(name="ping", description="Gets the API latency")
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"Pong! :ping_pong: {round(interaction.client.latency * 1000)}ms")

    
    @app_commands.command(name="clear", description="Clears messages in channel after the passed message")
    @commands.has_permissions(manage_messages=True)
    async def clear(self, interaction: discord.Interaction,
                    message_id: str):
        return
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
                selected_video = matching_videos[0]
            else:
                selected_video = random.choice(video_files)

            video_path = os.path.join(path, selected_video)

            await interaction.response.send_message(selected_video[:-4], file=discord.File(video_path))
        except Exception as e:
            self.logger.error(e)


    @app_commands.command(name="meter", description="Create a random meter")
    async def meter(self, interaction: discord.Interaction, 
                    user: discord.User, meter: str):
        await interaction.response.send_message(f"{user.display_name} is **{random.randint(0, 100)}% {meter}**")


    @app_commands.choices(translation=[
        Choice(name="UwU", value="uwuspeak"),
        Choice(name="LOLCAT", value="lolspeak"),
        Choice(name="Pirate", value="pirate"),
        Choice(name="Shakespearean", value="shakespeare"),
        Choice(name="uʍoᗡ ǝpᴉsd∩", value="upside_down"),
        Choice(name="Disable", value="disable")
    ])
    @app_commands.command(name="autotranslate", description="Enable realtime autotranslation of your messages")
    async def autotranslate_command(self, interaction: discord.Interaction, translation: Choice[str]):
        match translation.value:
            case "uwuspeak":
                pass


    async def translate_context_menu(self, interaction: discord.Interaction, message: discord.Message):
        result = self.deepl_client.translate_text(message.content, target_lang="EN-US")
        await interaction.response.send_message(result.text, ephemeral=True)


    # @app_commands.checks.bot_has_permissions(manage_messages=True, manage_webhooks=True)
    # @app_commands.command(name="uwu", description="Toggle message uwuifier")
    async def uwu(self, interaction: discord.Interaction):
        # checks if bot has permission to manage messages and manage webhooks in the channel
        if not interaction.channel.permissions_for(interaction.guild.me).manage_messages or not interaction.channel.permissions_for(interaction.guild.me).manage_webhooks:
            await interaction.response.send_message("I need the **Manage Messages** and **Manage Webhooks** permissions to use this feature.", ephemeral=True)
            return
        
        if interaction.user.id not in self.uwuified:
            self.uwuified.append(interaction.user.id)
            await interaction.response.send_message("Turned uwuify on")
        else:
            self.uwuified.remove(interaction.user.id)
            await interaction.response.send_message("Turned uwuifier off")
    
    # @uwu.error
    async def uwu_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.errors.BotMissingPermissions):
            await interaction.response.send_message("I need the **Manage Messages** and **Manage Webhooks** permissions to use this feature.", ephemeral=True)


    @app_commands.command(name="average_color", description="Gets the average color of an image")
    async def average_color(self, interaction: discord.Interaction, url: str):
        avg_color, avg_color_hex = await self.get_average_color(url)

        solid_image = Image.new("RGB", (100, 100), avg_color)
        image_buffer = BytesIO()
        solid_image.save(image_buffer, format="PNG")
        image_buffer.seek(0)
        
        file = discord.File(image_buffer, filename="average_color.png")

        await interaction.response.send_message(f"The average color of the [image](<{url}>) is `{avg_color_hex}`.", file=file)


    @app_commands.command(name="avatar", description="Gets the user's avatar")
    async def average_color(self, interaction: discord.Interaction, user: discord.User=None):
        user = user or interaction.user
        avatar_url = user.display_avatar.url

        avg_color, avg_color_hex = await self.get_average_color(avatar_url)

        embed = discord.Embed(title=f"{user.display_name}'s Avatar", url=avatar_url, color=discord.Color.from_rgb(*avg_color))
        embed.set_image(url=avatar_url)

        await interaction.response.send_message(embed=embed)


    @app_commands.command(name="average_color", description="Gets the average color of an image")
    async def average_color_command(self, interaction: discord.Interaction, url: str):
        avg_color, avg_color_hex = await self.get_average_color(url)

        solid_image = Image.new("RGB", (256, 256), avg_color)
        image_buffer = BytesIO()
        solid_image.save(image_buffer, format="PNG")
        image_buffer.seek(0)
        
        file = discord.File(image_buffer, filename=f"mechabot_average_color_{interaction.id}.png")

        await interaction.response.send_message(f"Average color of [image]({url}) is `{avg_color_hex}`", file=file)


    async def get_average_color(self, url: str):
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    return

                img_data = await response.read()
                image = Image.open(BytesIO(img_data))
                image = image.convert("RGB")

                img_array = np.array(image)
                avg_color = tuple(map(int, np.mean(img_array, axis=(0, 1))))
                avg_color_hex = "#{:02x}{:02x}{:02x}".format(*avg_color)

                return avg_color, avg_color_hex
            

    @app_commands.command(name="say", description="Send a message via the bot")
    async def say_command(self, interaction: discord.Interaction, content: str = None, file: discord.Attachment = None):
        if interaction.user.id != 425661467904180224:
            await interaction.response.send_message("You do not have permission to use this command!", ephemeral=True)
            return
        
        if file != None:
            file = await file.to_file()

        await interaction.channel.send(content, file=file)
        await interaction.response.send_message("Message sent!", ephemeral=True)


    @app_commands.checks.has_permissions(manage_roles=True)
    @app_commands.command(name="verify", description="[Exclusive Command] Verify user to give access to the server")
    async def verify(self, interaction: discord.Interaction, member: discord.Member):
        if interaction.guild.id != 1183359049287340062:
            await interaction.response.send_message("Command access denied", ephemeral=True)
            return

        unverified_role = discord.utils.get(interaction.guild.roles, name="Vetting pending")

        if unverified_role not in member.roles:
            await interaction.response.send_message("User already verified!", ephemeral=True)
            return

        await interaction.user.remove_roles(unverified_role)
        await interaction.response.send_message("User has been verified and given access to the server!")

    # @commands.Cog.listener()
    # async def on_member_join(self, member: discord.Member):
    #    if member.guild.id == 1183359049287340062:     
    #        vetting_role = discord.utils.get(member.guild.roles, name="Vetting pending")
    #        await member.add_roles(vetting_role)


    @app_commands.command(name="pet", description="Pet someone")
    async def pet_command(self, interaction: discord.Interaction, user: discord.User):
        # retrieve user avater bytes
        async with aiohttp.ClientSession() as session:
            async with session.get(user.display_avatar.url) as response:
                if response.status != 200:
                    await interaction.response.send_message("Failed to retrieve user avatar.", ephemeral=True)
                    return
                avatar_bytes = await response.read()

        source = BytesIO(avatar_bytes)
        dest = BytesIO()
        petpet.make(source, dest)
        dest.seek(0)
        await interaction.response.send_message(file=discord.File(dest, filename=f"pet_{interaction.id}.gif"))

    
    @app_commands.command(name="8ball", description="Ask the magic 8 ball a question")
    async def eight_ball(self, interaction: discord.Interaction, question: str):
        response = random.choice(eight_ball_responses)
        await interaction.response.send_message(f"\"{question}\"\n**:8ball: {response}**")


    @app_commands.command(name="pack_emojiful", description="Create an Emojiful datapack from server emojis")
    async def pack_emojiful(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return

        emojis = interaction.guild.emojis
        if not emojis:
            await interaction.response.send_message("This server has no custom emojis to pack.", ephemeral=True)
            return

        """
        datapack structure:
            emojiful_pack.zip/
                pack.mcmeta
                data/
                    emojiful/
                        recipe/
                            emoji.json

        emoji recipe structure:
        {
            "category": "server name",
            "name": "emoji name",
            "url": "https://cdn.discordapp.com/emojis/1105820265327370312.png",
            "type": "emojiful:emoji_recipe"
        }
        """

        self.logger.info(f"Creating Emojiful datapack for server {interaction.guild.name} with {len(emojis)} emojis")

        await interaction.response.defer()

        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
            # create pack.mcmeta
            pack_mcmeta = {
                "pack": {
                    "pack_format": 48,
                    "description": f"Emojiful datapack for {interaction.guild.name}"
                }
            }
            bytes_pack_mcmeta = json.dumps(pack_mcmeta, indent=4).encode('utf-8')
            zip_file.writestr("pack.mcmeta", bytes_pack_mcmeta)

            self.logger.debug("Added pack.mcmeta to datapack")

            # create emoji recipes
            for emoji in emojis:
                emoji_name_lowercase = emoji.name.lower()

                recipe = {
                    "category": interaction.guild.name,
                    "name": emoji_name_lowercase,
                    "url": str(emoji.url),
                    "type": "emojiful:emoji_recipe"
                }
                bytes_recipe = json.dumps(recipe, indent=4).encode('utf-8')
                zip_file.writestr(f"data/emojiful/recipe/{emoji_name_lowercase}.json", bytes_recipe)

                self.logger.debug(f"Added emoji {emoji.name} to datapack")
            
        zip_buffer.seek(0)
        await interaction.followup.send(file=discord.File(zip_buffer, filename=f"{interaction.guild.name}_emojiful_pack.zip"))


async def setup(bot):
    await bot.add_cog(Utils(bot))