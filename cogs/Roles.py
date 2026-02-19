import discord
from discord.ext import commands
from discord import app_commands
import sqlite3
import logging
from logging.handlers import TimedRotatingFileHandler

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

handler = TimedRotatingFileHandler(filename='logs/bot.log', encoding='utf-8', when='midnight', interval=1, backupCount=7)
handler.setFormatter(logging.Formatter('[%(asctime)s] [%(levelname)s/%(name)s]: %(message)s'))
logger.addHandler(handler)

console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('[%(asctime)s] [%(levelname)s/%(name)s]: %(message)s'))
logger.addHandler(console_handler)
    

class Roles(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        self.conn = sqlite3.connect('data.db')
        self.cursor = self.conn.cursor()
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS custom_roles(
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                guild_id INTEGER,
                name TEXT,
                color TEXT
            )
        """)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS role_settings(
                guild_id INTEGER PRIMARY KEY,
                enabled INTEGER DEFAULT 0,
                whitelisted_role INTEGER DEFAULT NULL
            )
        """)
        self.conn.commit()

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info(f"{__name__} is online!")


    role_group = app_commands.Group(name="role", description="Custom role management commands")


    @role_group.command(name="create", description="Create your custom role in the server. Accepted color formats: hex, rgb")
    async def create_role_command(self, interaction: discord.Interaction, name: str, color: str):
        guild_data = self.cursor.execute("""
            SELECT * FROM role_settings WHERE guild_id = ?
        """, (interaction.guild.id,)).fetchone()

        if guild_data and guild_data[1] == 0:
            await interaction.response.send_message("Custom roles are disabled in this server.", ephemeral=True)
            return

        if guild_data and guild_data[2]:
            whitelisted_role = interaction.guild.get_role(guild_data[2])
            if whitelisted_role not in interaction.user.roles:
                await interaction.response.send_message("You are not eligible to create a custom role in this server.", ephemeral=True)
                return

        custom_role = await interaction.guild.create_role(name=name, color=discord.Color.from_str(color))
        await interaction.user.add_roles(custom_role)

        self.cursor.execute("""
            INSERT INTO custom_roles (id, user_id, guild_id, name, color) VALUES (?, ?, ?, ?, ?)
        """, (custom_role.id, interaction.user.id, interaction.guild.id, name, color))
        self.conn.commit()

        await interaction.response.send_message(f"Custom role '{custom_role.name}' created with color {custom_role.color}!", ephemeral=True)


    @role_group.command(name="edit", description="Edit your custom role in the server")
    async def edit_role_command(self, interaction: discord.Interaction, name: str = None, color: str = None):
        if not name and not color:
            await interaction.response.send_message("You must provide at least one argument to edit.", ephemeral=True)
            return
        
        self.cursor.execute("""
            SELECT id FROM custom_roles WHERE user_id = ? AND guild_id = ?
        """, (interaction.user.id, interaction.guild.id))
        result = self.cursor.fetchone()

        if not result:
            await interaction.response.send_message("You don't have a custom role to edit.", ephemeral=True)
            return
        
        role_id = result[0]
        role = interaction.guild.get_role(role_id)
        if not role:
            await interaction.response.send_message("Your custom role was not found in the server.", ephemeral=True)
            return
        
        updates = {}
        if name:
            updates['name'] = name
        if color:
            updates['color'] = self.get_color_from_string(color)
        
        await role.edit(**updates)

        update_query = "UPDATE custom_roles SET "
        update_params = []
        if name:
            update_query += "name = ?, "
            update_params.append(name)
        if color:
            update_query += "color = ?, "
            update_params.append(color)

        update_query = update_query.rstrip(', ') + " WHERE id = ?"
        update_params.append(role_id)

        self.cursor.execute(update_query, tuple(update_params))
        self.conn.commit()

        await interaction.response.send_message(f"Custom role '{role.name}' updated!", ephemeral=True)


    @role_group.command(name="remove", description="Delete your custom role from the server")
    async def remove_role_command(self, interaction: discord.Interaction, name: str, color: str):
        self.cursor.execute("""
            SELECT id FROM custom_roles WHERE user_id = ? AND guild_id = ?
        """, (interaction.user.id, interaction.guild.id))
        result = self.cursor.fetchone()

        if not result:
            await interaction.response.send_message("You don't have a custom role to remove.", ephemeral=True)
            return
        
        role_id = result[0]
        role = interaction.guild.get_role(role_id)
        if role:
            await role.delete()

        self.cursor.execute("""
            DELETE FROM custom_roles WHERE id = ?
        """, (role_id,))
        self.conn.commit()

        await interaction.response.send_message(f"Custom role removed successfully!", ephemeral=True)

    @remove_role_command.error
    async def remove_role_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.errors.BotMissingPermissions):
            await interaction.response.send_message("I don't have `Manage Roles` permission to remove your role.", ephemeral=True)
        

    @role_group.command(name="enable", description="[Manager] Enable custom roles in the server")
    async def enable_command(self, interaction: discord.Interaction, enable: bool):
        guild_data = self.cursor.execute("""
            SELECT enabled FROM role_settings WHERE guild_id = ?
        """, (interaction.guild.id,)).fetchone()

        if guild_data:
            self.cursor.execute("""
                UPDATE role_settings SET enabled = ? WHERE guild_id = ?
            """, (1 if enable else 0, interaction.guild.id))
        else:
            self.cursor.execute("""
                INSERT INTO role_settings (guild_id, enabled) VALUES (?, ?)
            """, (interaction.guild.id, 1 if enable else 0))
        self.conn.commit()
        status = "enabled" if enable else "disabled"
        await interaction.response.send_message(f"Custom roles have been **{status}** for this server.", ephemeral=True)


    @role_group.command(name="whitelist", description="[Manager] Whitelist a role for custom role eligibility")
    async def whitelist_command(self, interaction: discord.Interaction, role: discord.Role = None):
        guild_data = self.cursor.execute("""
            SELECT whitelisted_role_ids FROM role_settings WHERE guild_id = ?
        """, (interaction.guild.id,)).fetchone()

        whitelisted_roles = guild_data[0].split(',') if guild_data and guild_data[0] else []

        if str(role.id) in whitelisted_roles:
            await interaction.response.send_message(f"The role '{role.name}' is already whitelisted.", ephemeral=True)
            return

        whitelisted_roles.append(str(role.id))
        whitelisted_roles_str = ','.join(whitelisted_roles)

        if guild_data:
            self.cursor.execute("""
                UPDATE role_settings SET whitelisted_role_ids = ? WHERE guild_id = ?
            """, (whitelisted_roles_str, interaction.guild.id))
        else:
            self.cursor.execute("""
                INSERT INTO role_settings (guild_id, whitelisted_role_ids) VALUES (?, ?)
            """, (interaction.guild.id, whitelisted_roles_str))
        self.conn.commit()

        await interaction.response.send_message(f"The role '{role.name}' has been whitelisted for custom role eligibility.", ephemeral=True)
        
    

    def get_color_from_string(self, color_str: str) -> discord.Color:
        try:
            if color_str.startswith('#'):
                return discord.Color(int(color_str[1:], 16))
            elif ',' in color_str:
                r, g, b = map(int, color_str.split(','))
                return discord.Color.from_rgb(r, g, b)
            else:
                return discord.Color.default()
        except Exception as e:
            logger.error(f"Error parsing color: {e}")
            return discord.Color.default()

async def setup(bot):
    await bot.add_cog(Roles(bot))