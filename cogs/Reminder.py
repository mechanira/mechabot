import discord
from discord.ext import commands, tasks
from discord import app_commands
import re
import time
from datetime import datetime, timezone


class Reminder(commands.Cog):
    def __init__(self, bot, db, logger):
        self.bot = bot
        self.db = db
        self.self.logger = logger
        self.check_reminders.start()
        self.check_daily_reminders.start()

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
    async def set_reminder(
        self, 
        interaction: discord.Interaction, 
        label: str, 
        time_input: str, 
        user: discord.User = None, 
        send_dm: bool = False
    ):
        try:
            remind_at = Reminder._parse_time(time_input)
            if remind_at is None or remind_at < int(time.time()):
                await interaction.response.send_message(
                    "Invalid time format! Use formats like `10s`, `5m`, `2d1h30m`, `3M`, or a Unix timestamp.",
                    ephemeral=True
                )
                return

            user = user or interaction.user
            channel_id = interaction.channel.id if not send_dm else None

            self.db.insertReminder(user_id, channel_id, label, remind_at, None, send_dm)

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
            self.logger.error(f"An error occured: {e}")


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

            self.db.insertReminder(user_id, channel_id, label, None, time_input, send_dm)

            await interaction.response.send_message(
                f"🔁 Daily reminder set for <@{user.id}>: `{label}` every day at `{time_input} UTC`", ephemeral=True
            )

        except sqlite3.Error as e:
            self.logger.error(f"Database error: {e}")
            await interaction.response.send_message("There was an issue saving your reminder. Please try again later.", ephemeral=True)

        except Exception as e:
            self.logger.error(f"General error: {e}")
            await interaction.response.send_message("Something went wrong. Please try again later.", ephemeral=True)


    @app_commands.command(name="reminder_daily_cancel", description="Cancel a daily reminder by label")
    async def cancel_weekly_reminder(self, interaction: discord.Interaction, label: str):

        self.db.deleteReminder(interaction.user.id, label)

        await interaction.response.send_message(f"Daily reminder `{label}` has been canceled!", ephemeral=True)


    @app_commands.command(name="reminders", description="View all your active reminders")
    async def view_reminders(self, interaction: discord.Interaction):

        reminders = self.db.selectReminder_foruser(interaction.user.id)

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

        reminders = self.db.selectReminder_due(
                                        int(time.time()),
                                        datetime.now(timezone.utc).strftime("%H:%M")
        )

        for reminder in reminders:
            reminder_id, user_id, channel_id, label, send_dm, daily = reminder
            user = self.bot.get_user(user_id)

            message = "Reminder"
            if daily != "" or daily != None:
                message = "Daily reminder"

            if send_dm and user:
                try:
                    await user.send(f"{message}: **{label}** is due!")
                except discord.Forbidden:
                    self.logger.error(f"Could not DM {user_id}, they might have DMs disabled.")
            elif channel_id:
                channel = self.bot.get_channel(channel_id)
                if channel:
                    await channel.send(f"<@{user_id}>, {message.lower()}: **{label}** is due!")
