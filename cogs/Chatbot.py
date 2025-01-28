import discord
import os
import datetime
from discord.ext import commands
from dotenv import load_dotenv
import google.generativeai as genai

class Chatbot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.CHANNEL_ID = 1328122057254371429
        self.chat = None

        # Load environment variables
        load_dotenv()

        # Configure genai API
        genai.configure(api_key=os.getenv("GEMINI_KEY"))

        # Initialize the model
        self.model = genai.GenerativeModel(
            model_name='models/gemini-1.5-flash-001',
            system_instruction=(
                "You are a helpful and conversational Discord chatbot named Kirabot. "
                "When responding to messages, do not include your own name or display name. "
                "When interpreting user inputs, they will be formatted as: "
                "username (display_name): [message content]. "
                "Your responses should directly address the user's query without including any prefixes."
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
            async with message.channel.typing():
                # Send user message to the chat model
                response = self.chat.send_message(
                    f"{message.author.name} ({message.author.display_name}): {message.content}"
                )
                response_text = response.text

                if response_text.startswith("Kirabot (Kirabot):"):
                    response_text = response_text.split(": ", 1)[-1]

                await message.reply(response_text)
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