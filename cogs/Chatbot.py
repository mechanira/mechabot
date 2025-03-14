import discord
import os
import datetime
from discord.ext import commands
from dotenv import load_dotenv
import google.generativeai as genai
import re

class Chatbot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.CHANNEL_ID = 1328122057254371429
        self.chat = None

        load_dotenv()

        genai.configure(api_key=os.getenv("GEMINI_KEY"))

        # Initialize the model
        self.model = genai.GenerativeModel(
            model_name='models/gemini-2.0-flash',
            system_instruction=(
                "You are a chatbot named Mechabot."
                "When responding to messages, do not include your own name or display name. "
                "When interpreting user inputs, they will be formatted as: "
                "username (display_name): [message content]. "
                "Your responses should directly address the user's query without including any prefixes."
                "Your responses should be as concise as possible"
                "Avoid unnecessary line breaks in your responses"
                "You can return a response of \"/fallback\" if the message doesn't need to be replied to, like when someone isn't referencing you directly"
            )
        )

    @commands.Cog.listener()
    async def on_ready(self):
        try:
            # Fetch channel history
            history = await self.fetch_channel_history(self.CHANNEL_ID)
            self.chat = self.model.start_chat(history=history)
            print(f"{__name__} is online!")
        except Exception as e:
            print(f"Error during on_ready: {e}")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignore messages outside the target channel or from bots
        if message.channel.id != self.CHANNEL_ID or message.author.bot:
            return
        
        '''
        bot_user = self.bot.user
        is_mentioned = bot_user in message.mentions
        is_reply_to_bot = message.reference and \
                        (await message.channel.fetch_message(message.reference.message_id)).author == bot_user

        if not (is_mentioned or is_reply_to_bot):
            return
        '''

        try:
            response = self.chat.send_message(
                f"{message.author.name} ({message.author.display_name}): {message.content}"
            )
            response_text = response.text

            if "/fallback" in response_text.lower():
                return

            if response_text.startswith("Kirabot (Kirabot):"):
                response_text = response_text.split(": ", 1)[-1]

            emoji_pattern = re.compile("["
                            u"\U0001F600-\U0001F64F"  # emoticons
                            u"\U0001F300-\U0001F5FF"  # symbols & pictographs
                            u"\U0001F680-\U0001F6FF"  # transport & map symbols
                            u"\U0001F1E0-\U0001F1FF"  # flags (iOS)
                            "]+", flags=re.UNICODE)
            filtered_response = emoji_pattern.sub(r'', response_text)

            await message.reply(filtered_response)
        except Exception as e:
            print(f"Error processing message: {e}")

    async def fetch_channel_history(self, channel_id):
        try:
            channel = await self.bot.fetch_channel(channel_id)
            history = []

            async for message in channel.history(limit=100, oldest_first=True):
                if message.author.bot:
                    role = "model"
                    parts = message.content
                else:
                    role = "user"
                    parts = f"{message.author.name} ({message.author.display_name}): {message.content}"

                history.append({"role": role, "parts": parts})
                # print({"role": role, "parts": parts})

            return history
        except Exception as e:
            print(f"Error fetching channel history: {e}")
            return []

async def setup(bot):
    await bot.add_cog(Chatbot(bot))