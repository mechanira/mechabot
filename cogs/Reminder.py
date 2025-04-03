import discord
from discord.ext import commands, tasks
from discord import app_commands
import re
import time
from datetime import datetime, timezone
import sqlite3

def parse_time(input_time: str) -> str:
    try:
        if input_time.isdigit():
            return int(input_time)
        
        time_regex = re.findall(r'(\d+)([smhdwMy])', input_time.lower())
        if not time_regex:
            return None
        
        total_seconds = 0
        for amount, unit in time_regex:
            amount = int(amount)
            if unit == "s": total_seconds += amount
            elif unit == "m": total_seconds += amount * 60
            elif unit == "h": total_seconds += amount * 3600
            elif unit == "d": total_seconds += amount * 86400
            elif unit == "M": total_seconds += amount * 2592000
            elif unit == "y": total_seconds += amount * 31536000
            

        return int(time.time()) + total_seconds
    except:
        return None
    

class Reminder(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.conn = sqlite3.connect('data.db')
        self.cursor = self.conn.cursor()
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                channel_id INTEGER,
                label TEXT,
                remind_at INTEGER,
                daily_time TEXT,
                send_dm BOOLEAN
            )
        """)
        self.conn.commit()
        self.check_reminders.start()
        self.check_daily_reminders.start()

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"{__name__} is online!")

    def cog_unload(self):
        self.check_reminders.cancel()
        self.conn.close()


    @app_commands.command(name="reminder", description="Set a reminder")
    async def set_reminder(
        self, 
        interaction: discord.Interaction, 
        label: str, 
        time_input: str, 
        user: discord.User = None, 
        send_dm: bool = False
    ):
        try:
            remind_at = parse_time(time_input)
            if remind_at is None or remind_at < int(time.time()):
                await interaction.response.send_message(
                    "Invalid time format! Use formats like `10s`, `5m`, `2d1h30m`, `3M`, or a Unix timestamp.",
                    ephemeral=True
                )
                return

            user = user or interaction.user
            channel_id = interaction.channel.id if not send_dm else None

            self.cursor.execute(
                "INSERT INTO reminders (user_id, channel_id, label, remind_at, send_dm) VALUES (?, ?, ?, ?, ?)", 
                (user.id, channel_id, label, remind_at, send_dm)
            )
            self.conn.commit()

            human_time = datetime.fromtimestamp(remind_at, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')

            embed = discord.Embed(
                title="Reminder set!",
                description=f'**"{label}"**\n\nAt `{human_time} (<t:{remind_at}:R>)`',
                color=discord.Color.blurple())
            
            await interaction.response.send_message(
                f"Reminder set for <@{user.id}>: `{label}` <t:{remind_at}:R>\n"
                f"**Will be sent to:** {'DM' if send_dm else 'here' if channel_id == interaction.channel_id else f'<#{channel_id}>'}"
            )
        except Exception as e:
            print(e)


    @app_commands.command(name="reminder_daily", description="Set a daily reminder for ")
    @app_commands.describe(
        time_input = "Expected format: HH:MM"
    )
    async def set_daily_reminder(
        self, 
        interaction: discord.Interaction, 
        label: str, 
        time_input: str
    ):
        try:
            if not time_input or len(time_input) != 5 or ":" not in time_input:
                await interaction.response.send_message("Invalid time format! Use `HH:MM` (UTC).", ephemeral=True)
                return

            user = interaction.user
            channel_id = None
            send_dm = True

            self.cursor.execute(
                "INSERT INTO reminders (user_id, channel_id, label, daily_time, send_dm) VALUES (?, ?, ?, ?, ?)",
                (user.id, channel_id, label, time_input, send_dm)
            )
            self.conn.commit()

            await interaction.response.send_message(
                f"🔁 Daily reminder set for <@{user.id}>: `{label}` every day at `{time_input} UTC`", ephemeral=True
            )

        except sqlite3.Error as e:
            print(f"Database error: {e}")
            await interaction.response.send_message("There was an issue saving your reminder. Please try again later.", ephemeral=True)

        except Exception as e:
            print(f"General error: {e}")
            await interaction.response.send_message("Something went wrong. Please try again later.", ephemeral=True)


    @app_commands.command(name="reminder_daily_cancel", description="Cancel a daily reminder by label")
    async def cancel_weekly_reminder(self, interaction: discord.Interaction, label: str):
        self.cursor.execute("DELETE FROM reminders WHERE user_id = ? AND label = ?", (interaction.user.id, label))
        self.conn.commit()
        await interaction.response.send_message(f"Daily reminder `{label}` has been canceled!", ephemeral=True)


    @app_commands.command(name="reminders", description="View all your active reminders")
    async def view_reminders(self, interaction: discord.Interaction):
        user_id = interaction.user.id

        self.cursor.execute("SELECT label, daily_time, send_dm FROM reminders WHERE user_id = ?", (user_id,))
        reminders = self.cursor.fetchall()

        if not reminders:
            await interaction.response.send_message("You have no active reminders.", ephemeral=True)
            return

        embed = discord.Embed(
            title="Your Active Reminders",
            color=discord.Color.blue()
        )

        for index, (label, daily_time, send_dm) in enumerate(reminders, start=1):
            delivery_method = "DM" if send_dm else "Channel"
            embed.add_field(
                name=f"Reminder {index}",
                value=f"**Label:** {label}\n**Time:** `{daily_time} UTC`\n**Delivery:** {delivery_method}",
                inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)


    @tasks.loop(seconds=10)
    async def check_reminders(self):
        """Checks for due reminders and sends messages."""
        current_time = int(time.time())
        self.cursor.execute("SELECT id, user_id, channel_id, label, send_dm FROM reminders WHERE remind_at <= ?", (current_time,))
        reminders = self.cursor.fetchall()

        for reminder in reminders:
            reminder_id, user_id, channel_id, label, send_dm = reminder
            user = self.bot.get_user(user_id)

            if send_dm and user:
                try:
                    await user.send(f"Reminder: **{label}** is due!")
                except discord.Forbidden:
                    print(f"Could not DM {user_id}, they might have DMs disabled.")
            elif channel_id:
                channel = self.bot.get_channel(channel_id)
                if channel:
                    await channel.send(f"<@{user_id}>, reminder: **{label}** is due!")

            self.cursor.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
            self.conn.commit()


    @tasks.loop(minutes=1)
    async def check_daily_reminders(self):
        """Checks for daily reminders at the correct time."""
        current_time = datetime.now(timezone.utc)
        current_hour_minute = current_time.strftime("%H:%M")

        self.cursor.execute(
            "SELECT user_id, channel_id, label, send_dm FROM reminders WHERE daily_time = ?", 
            (current_hour_minute,)
        )
        reminders = self.cursor.fetchall()

        for user_id, channel_id, label, send_dm in reminders:
            user = self.bot.get_user(user_id) or await self.bot.fetch_user(user_id)

            if send_dm and user:
                try:
                    await user.send(f"Daily Reminder: **{label}**")
                except discord.Forbidden:
                    print(f"Could not DM {user_id}, they might have DMs disabled.")
            elif channel_id:
                channel = self.bot.get_channel(channel_id)
                if channel:
                    try:
                        await channel.send(f"<@{user_id}>, daily reminder: **{label}**")
                    except discord.Forbidden:
                        print(f"Bot lacks permission to send messages in channel {channel_id}.")


async def setup(bot):
    await bot.add_cog(Reminder(bot))