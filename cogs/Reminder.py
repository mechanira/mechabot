import discord
from discord.ext import commands, tasks
from discord import app_commands
import re
import time
from datetime import datetime, timezone
import sqlite3
import logging

class Reminder(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.database
        self.logger = bot.logger
        self.languages = bot.languages
        self.check_reminders.start()

    def _parse_time(input_time: str) -> str:
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
                elif unit == "w": total_seconds += amount * 604800
                elif unit == "M": total_seconds += amount * 2592000
                elif unit == "y": total_seconds += amount * 31536000

            return int(time.time()) + total_seconds
        except:
            return None

    @commands.Cog.listener()
    async def on_ready(self):
        self.logger.info(f"{__name__} is online!")

    def cog_unload(self):
        self.check_reminders.cancel()
        self.conn.close()


    @app_commands.command(name="reminder", description="Set a reminder")
    async def reminder_command(
        self, 
        interaction: discord.Interaction, 
        label: str, 
        time_input: str,
        user: discord.User = None, 
        send_dm: bool = False
    ):
        lang = interaction.locale
        remind_at = Reminder._parse_time(time_input)
        if remind_at is None or remind_at < int(time.time()):
            await interaction.response.send_message(
                self.languages.getText("reminder_command.error.invalid_time"),
                ephemeral=True
            )
            return

        user = user or interaction.user
        channel_id = interaction.channel.id if not send_dm else None

        self.db.insert_reminder(user.id, channel_id, label, remind_at, None, send_dm)

        human_time = datetime.fromtimestamp(remind_at, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')

        embed = discord.Embed(
            title=self.languages.getText("reminder_command.embed.title"),
            description=self.languages.getText("reminder_command.embed.description", label, human_time, remind_at),
            color=discord.Color.blurple())
        
        await interaction.response.send_message(
            self.languages.getText("reminder_command.response.message",
                user.id,
                label,
                remind_at,
                self.languages.getText("reminder.delivery_method.dm") if send_dm else self.languages.getText("reminder.delivery_method.channel")
            )
        )

    @reminder_command.error
    async def reminders_command_error(self, interaction: discord.Interaction, error):
        self.logger.error(error)


    @app_commands.command(name="reminders", description="View all your active reminders")
    async def reminders_command(self, interaction: discord.Interaction):

        reminders = self.db.fetch_all_user_reminders(interaction.user.id)

        if not reminders:
            await interaction.response.send_message(self.languages.getText("reminders_command.error.no_reminders"), ephemeral=True)
            return

        embed = discord.Embed(
            title=self.languages.getText("reminders_command.embed.title"),
            color=discord.Color.blue()
        )

        for index, (label, daily_time, send_dm) in enumerate(reminders, start=1):
            delivery_method = self.languages.getText("reminder.delivery_method.dm") if send_dm else self.languages.getText("reminder.delivery_method.channel")
            embed.add_field(
                name=self.languages.getText("reminders_command.reminder_index", index),
                value=self.languages.getText("reminders_command.reminder_details", label, daily_time, delivery_method),
                inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    
    @reminders_command.error
    async def reminders_command_error(self, interaction: discord.Interaction, error):
        self.logger.error(error)


    @tasks.loop(seconds=1)
    async def check_reminders(self):
        """Checks for due reminders and sends messages."""

        reminders = self.db.select_reminder_due(
            int(time.time()),
            datetime.now(timezone.utc).strftime("%H:%M")
        )

        for reminder in reminders:
            user = self.bot.get_user(reminder["user_id"])

            if reminder["send_dm"] and user:
                try:
                    await user.send(self.languages.getText("check_reminders.dm_reminder", reminder["label"]))
                except discord.Forbidden:
                    self.logger.error(f"Could not DM {reminder["user_id"]}, they might have DMs disabled.")
            elif reminder["channel_id"]:
                channel = self.bot.get_channel(reminder["channel_id"])
                if channel:
                    await channel.send(self.languages.getText("check_reminders.channel_reminder", reminder["user_id"], reminder["label"]))


async def setup(bot):
    await bot.add_cog(Reminder(bot))