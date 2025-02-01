import discord
from discord.ext import commands
from discord import app_commands
import random
import os

def winCheck(grid) -> int:
    # Horizontal check
    for row in grid:
        for col in range(4):
            if row[col] == row[col + 1] == row[col + 2] == row[col + 3] != 0:
                player_index = row[col]
                return player_index

    # Vertical check
    for col in range(7):
        for row in range(3):
            if grid[row][col] == grid[row + 1][col] == grid[row + 2][col] == grid[row + 3][col] != 0:
                player_index = grid[row][col]
                return player_index

    # Diagonal check (down-right and up-right)
    for row in range(3):
        for col in range(4):
            if grid[row][col] == grid[row + 1][col + 1] == grid[row + 2][col + 2] == grid[row + 3][col + 3] != 0:
                player_index = grid[row][col]
                return player_index
            if grid[row + 3][col] == grid[row + 2][col + 1] == grid[row + 1][col + 2] == grid[row][col + 3] != 0:
                player_index = grid[row + 3][col]
                return player_index
    return 0

def displayGrid(grid) -> str:
    gridDisplay = ""
    for row in grid:
        for column in row:
            if column == 0:
                gridDisplay += ":black_large_square:"
            elif column == 1:
                gridDisplay += ":red_circle:"
            elif column == 2:
                gridDisplay += ":blue_circle:"
        gridDisplay += "\n"
    gridDisplay += ":one::two::three::four::five::six::seven:"
    return gridDisplay

def drop_piece(grid, column, player):
    for row in reversed(grid):
        if row[column] == 0:
            row[column] = player
            return

class ConnectFour(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.game_message = None
        self.game_players = []
        self.turn = 0
        self.game_grid = []

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"{__name__} is online!")


    @app_commands.command(name="connectfour", description="Start a Connect Four game")
    async def connect_four(self, interaction: discord.Interaction, opponent: discord.User):
        try:
            self.game_grid = [[0] * 7 for _ in range(6)]
            self.game_players = [interaction.user.id, opponent.id]
            self.turn = random.randint(1,2)

            current_player = await self.bot.fetch_user(self.game_players[self.turn-1])
            grid_display = f"{current_player.mention}'s Turn {':red_circle:' if self.turn == 1 else ':blue_circle:'}\n" + displayGrid(self.game_grid)
            embed = discord.Embed(
                title="Connect Four",
                description=grid_display,
                color=discord.Color.red() if self.turn == 1 else discord.Color.blue()
            )
            embed.set_footer(text="Use /connectfour_place to drop piece", icon_url=self.bot.user.avatar.url)

            await interaction.response.send_message(embed=embed)
            self.game_message = await interaction.original_response()
        except Exception as e:
            await interaction.response.send_message(e, ephemeral=True)


    @app_commands.command(name="connectfour_place", description="Place a piece on the Connect Four board")
    async def connect_four_place(self, interaction: discord.Interaction, column: str):
        try:
            if self.game_message == None:
                await interaction.response.send_message("There is no ongoing game! Use /connectfour to start a game.", ephemeral=True)
                return
            print(self.game_players)
            if interaction.user.id not in self.game_players:
                await interaction.response.send_message("You are not in an ongoing game! Use /connectfour to start a game.", ephemeral=True)
                return
            print(self.game_players[self.turn-1])
            if interaction.user.id != self.game_players[self.turn-1]:
                await interaction.response.send_message("It's not your turn!", ephemeral=True)
                return
            if not column.isdigit():
                await interaction.response.send_message("Not a valid input! Please input a number between 1-7", ephemeral=True)
                return
            
            column = int(column)

            if column < 1 or column > 7:
                await interaction.response.send_message("Column is out of range! Please input a number between 1-7", ephemeral=True)
                return
            if self.game_grid[0][column - 1] != 0:
                await interaction.response.send_message("Column is full!", ephemeral=True)
                return
            
            drop_piece(self.game_grid, column - 1, self.turn)

            self.turn = 3 - self.turn
            current_player = await self.bot.fetch_user(self.game_players[self.turn-1])
            
            status_label = ""
            winValue = winCheck(self.game_grid)
            if winValue != 0:
                winner_user = await self.bot.fetch_user(self.game_players[winValue-1])
                status_label = f":tada: {winner_user.mention} has won!"
            else:
                status_label = f"{current_player.mention}'s Turn {':red_circle:' if self.turn == 1 else ':blue_circle:'}\n"
            grid_display = f"{status_label}\n" + displayGrid(self.game_grid)
            embed = discord.Embed(
                    title="Connect Four",
                    description=grid_display,
                    color=discord.Color.green() if winValue != 0 else discord.Color.red() if self.turn == 1 else discord.Color.blue()
                )
            embed.set_footer(text="Use /connectfour_place to drop piece", icon_url=self.bot.user.avatar.url)

            await interaction.response.send_message(f"Piece placed on column {column}", ephemeral=True)
            await self.game_message.edit(embed=embed)

            if winValue != 0: self.game_message = None
        except Exception as e:
            await interaction.response.send_message(e, ephemeral=True)

        

async def setup(bot):
    await bot.add_cog(ConnectFour(bot))