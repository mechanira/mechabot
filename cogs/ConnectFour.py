import discord
from discord.ext import commands
from discord import app_commands
import random
import sqlite3
import json
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


def winCheck(grid) -> int:
    """Checks if a player has won."""
    for row in grid:
        for col in range(4):
            if row[col] == row[col + 1] == row[col + 2] == row[col + 3] != 0:
                return row[col]

    for col in range(7):
        for row in range(3):
            if grid[row][col] == grid[row + 1][col] == grid[row + 2][col] == grid[row + 3][col] != 0:
                return grid[row][col]

    for row in range(3):
        for col in range(4):
            if grid[row][col] == grid[row + 1][col + 1] == grid[row + 2][col + 2] == grid[row + 3][col + 3] != 0:
                return grid[row][col]
            if grid[row + 3][col] == grid[row + 2][col + 1] == grid[row + 1][col + 2] == grid[row][col + 3] != 0:
                return grid[row + 3][col]
    return 0


def displayGrid(grid) -> str:
    """Converts grid to an emoji-based string representation."""
    emoji_map = {0: ":black_large_square:", 1: ":red_circle:", 2: ":blue_circle:"}
    return "\n".join("".join(emoji_map[cell] for cell in row) for row in grid) + "\n:one::two::three::four::five::six::seven:"


def drop_piece(grid, column, player):
    """Drops a piece into a column if possible."""
    for row in reversed(grid):
        if row[column] == 0:
            row[column] = player
            return True
    return False

class ConnectFour(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.conn = sqlite3.connect('data.db')
        self.cursor = self.conn.cursor()
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS connect_four (
                game_id INTEGER PRIMARY KEY,
                player1_id INTEGER NOT NULL,
                player2_id INTEGER NOT NULL,
                turn INTEGER NOT NULL,
                selected_column INTEGER DEFAULT 1,
                grid TEXT NOT NULL,
                message_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL
            )
        """)
        self.conn.commit()

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info(f"{__name__} is online!")


    @app_commands.command(name="connectfour", description="Start a Connect Four game")
    async def connect_four(self, interaction: discord.Interaction, opponent: discord.User):
        """Starts a new Connect Four game."""
        player1 = interaction.user.id
        player2 = opponent.id

        """
        if player1 == player2:
            await interaction.response.send_message("You cannot play against yourself!", ephemeral=True)
            return
        """

        # Check if players are already in a game
        self.cursor.execute("SELECT game_id FROM connect_four WHERE player1_id IN (?, ?) OR player2_id IN (?, ?)", (player1, player2, player1, player2))
        if self.cursor.fetchone():
            await interaction.response.send_message("One of you is already in a game!", ephemeral=True)

            self.cursor.execute("DELETE FROM connect_four WHERE player1_id IN (?, ?) OR player2_id IN (?, ?)", (player1, player2, player1, player2))
            return

        # Initialize game state
        grid = [[0] * 7 for _ in range(6)]
        turn = random.randint(1, 2)

        view = discord.ui.View()
        view.add_item(discord.ui.Button(label="<", style=discord.ButtonStyle.primary, custom_id="cf_left"))
        view.add_item(discord.ui.Button(label="Place", style=discord.ButtonStyle.primary, custom_id="cf_place"))
        view.add_item(discord.ui.Button(label=">", style=discord.ButtonStyle.primary, custom_id="cf_right"))

        await interaction.response.send_message(embed=render_board(grid, player1, player2, turn, 1), view=view)
        board_msg = await interaction.original_response()

        self.cursor.execute("INSERT INTO connect_four (player1_id, player2_id, turn, selected_column, grid, message_id, channel_id) VALUES (?, ?, ?, ?, ?, ?)",
                            (player1, player2, turn, json.dumps(grid), board_msg.id, board_msg.channel.id))
        self.conn.commit()


    @app_commands.command(name="connectfour_place", description="Drop a piece in a column")
    async def connect_four_place(self, interaction: discord.Interaction, column: int):
        try:
            """Handles piece placement."""
            player_id = interaction.user.id

            # Get active game
            self.cursor.execute("SELECT game_id, player1_id, player2_id, turn, selected_column, grid, message_id, channel_id FROM connect_four WHERE player1_id = ? OR player2_id = ?", (player_id, player_id))
            game = self.cursor.fetchone()

            if not game:
                await interaction.response.send_message("You are not in a game!", ephemeral=True)
                return

            game_id, player1, player2, turn, selected_column, grid_str, message_id, channel_id = game
            grid = json.loads(grid_str)

            if (turn == 1 and player_id != player1) or (turn == 2 and player_id != player2):
                await interaction.response.send_message("It's not your turn!", ephemeral=True)
                return

            if column < 1 or column > 7:
                await interaction.response.send_message("Invalid column! Choose between 1 and 7.", ephemeral=True)
                return

            col_idx = column - 1
            if not drop_piece(grid, col_idx, turn):
                await interaction.response.send_message("That column is full!", ephemeral=True)
                return

            winner = winCheck(grid)

            next_turn = 1 if turn == 2 else 2

            if winner == 0:
                self.cursor.execute("UPDATE connect_four SET turn = ?, grid = ? WHERE game_id = ?", (next_turn, json.dumps(grid), game_id))
            else:
                self.cursor.execute("DELETE FROM connect_four WHERE game_id = ?", (game_id,))
            self.conn.commit()

            channel = await self.bot.fetch_channel(channel_id)
            message = await channel.fetch_message(message_id)
            await message.edit(embed=render_board(grid, player1, player2, winner if winner else next_turn, selected_column, winner))

            if winner:
                await interaction.response.send_message(f"🎉 <@{player1 if winner == 1 else player2}> wins!", ephemeral=True)
            else:
                await interaction.response.send_message(f"Move placed in column `{column}`", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"An error occured: {e}", ephemeral=True)


async def setup(bot):
    await bot.add_cog(ConnectFour(bot))

def render_board(grid, player1, player2, turn, selected_column, winner=0):
        """Generates the game board as an embed."""
        embed = discord.Embed(
            title="Connect Four",
            color=discord.Color.green() if winner else discord.Color.red() if turn == 1 else discord.Color.blue())
        status_label = f"🎉 <@{player1 if winner == 1 else player2}> wins!" if winner else f"<@{player1 if turn == 1 else player2}>'s Turn {':red_circle:' if turn == 1 else ':blue_circle:'}"
        embed.description = f"{status_label}\n{displayGrid(grid)}\nSelected Column: `{selected_column}`"
        embed.set_footer(text="Use /connectfour_place to drop a piece")

        return embed