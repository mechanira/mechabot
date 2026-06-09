import discord
from discord.ext import commands
from discord import app_commands
import random
import json
from logging.handlers import TimedRotatingFileHandler
import re


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
    emoji_map = {
        0: ":black_large_square:",
        1: ":red_circle:",
        2: ":blue_circle:"
    }
    number_emoji_row = "\n:one::two::three::four::five::six::seven:"
    return "\n".join("".join(emoji_map[cell] for cell in row) for row in grid) + number_emoji_row


def drop_piece(grid, column, player):
    for row in reversed(grid):
        if row[column] == 0:
            row[column] = player
            return True
    return False

class ConnectFourUI(discord.ui.View):
    def __init__(self, db):
        super().__init__(timeout=None)

        self.db = db


    @discord.ui.button(label="<", style=discord.ButtonStyle.primary)
    async def cf_move_left(self, interaction: discord.Interaction, button: discord.ui.Button):
        message_id = interaction.message.id
        player_id = interaction.user.id

        game = self.db.select_connect_four_game(message_id)

        selected_column -= 1

        if not game:
            await interaction.response.send_message("You are not in a game!", ephemeral=True)
            return

        grid = json.loads(game["grid"])

        if (game["turn"] == 1 and player_id != game["player1_id"]) or (game["turn"] == 2 and player_id != game["player2_id"]):
            await interaction.response.send_message("It's not your turn!", ephemeral=True)
            return

        if selected_column < 1:
            await interaction.response.send_message("Column out of range!", ephemeral=True)
            return
        
        self.db.connectfour_update_selection(game["game_id"], selected_column)

        await interaction.response.edit_message(embed=render_board(grid, game["player1_id"], game["player2_id"], game["turn"], selected_column), view=self)


    @discord.ui.button(label="Place", style=discord.ButtonStyle.primary)
    async def cf_place(self, interaction: discord.Interaction, button: discord.ui.Button):
        message_id = interaction.message.id
        player_id = interaction.user.id

        game = self.db.select_connect_four_game(message_id)

        if not game:
            await interaction.response.send_message("You are not in a game!", ephemeral=True)
            return

        grid = json.loads(grid)

        if (game["turn"] == 1 and player_id != game["player1_id"]) or (game["turn"] == 2 and player_id != game["player2_id"]):
            await interaction.response.send_message("It's not your turn!", ephemeral=True)
            return

        if game["selected_column"] < 1 or game["selected_column"] > 7:
            await interaction.response.send_message("Invalid column! Choose between 1 and 7.", ephemeral=True)
            return

        col_idx = game["selected_column"] - 1
        if not drop_piece(grid, col_idx, game["turn"]):
            await interaction.response.send_message("That column is full!", ephemeral=True)
            return

        winner = winCheck(grid)

        next_turn = 1 if game["turn"] == 2 else 2

        self.db.connectfour_check_game_state(winner, next_turn, grid, game)

        if winner:
            await self.disable_all(interaction) # disables the ui

            player_a = self.db.connectfour_fetch_user(game["player1_id"])
            player_b = self.db.connectfour_fetch_user(game["player2_id"])

            k_a = k_factor(player_a["games_played"])
            k_b = k_factor(player_b["games_played"])

            if winner == 1:
                result_a = 1
            elif winner == 2:
                result_a = 0
            else:
                result_a = 0.5

            new_rating_a, new_rating_b = update_ratings(
                player_a["rating"], player_b["rating"], result_a, k_a, k_b
            )

            new_rating_a = round(new_rating_a)
            new_rating_b = round(new_rating_b)

            games_played_a += 1
            games_played_b += 1

            if winner == 1:
                wins_a += 1
                losses_b += 1
            elif winner == 2:
                wins_b += 1
                losses_a += 1
            
            self.db.connectfour_user_insert(game["player1_id"], new_rating_a, games_played_a, wins_a, losses_a)
            self.db.connectfour_user_insert(game["player2_id"], new_rating_b, games_played_b, wins_b, losses_b)

        await interaction.response.edit_message(embed=render_board(grid, game["player1_id"], game["player2_id"], winner if winner else next_turn, game["selected_column"], winner), view=self)


    @discord.ui.button(label=">", style=discord.ButtonStyle.primary)
    async def cf_move_right(self, interaction: discord.Interaction, button: discord.ui.Button):
        message_id = interaction.message.id
        player_id = interaction.user.id

        game = self.db.select_connect_four_game(message_id)

        selected_column += 1

        if not game:
            await interaction.response.send_message("You are not in a game!", ephemeral=True)
            return

        grid = json.loads(grid)

        if (game["turn"] == 1 and player_id != game["player1_id"]) or (game["turn"] == 2 and player_id != game["player2_id"]):
            await interaction.response.send_message("It's not your turn!", ephemeral=True)
            return

        if selected_column > 7:
            await interaction.response.send_message("Column out of range!", ephemeral=True)
            return
        
        self.db.connectfour_update_selection(game["game_id"], selected_column)

        await interaction.response.edit_message(embed=render_board(grid, game["player1_id"], game["player2_id"], game["turn"], selected_column), view=self)


    async def disable_all(self, interaction: discord.Interaction):
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True


class ConnectFourRequestUI(discord.ui.View):
    def __init__(self, db):
        super().__init__(timeout=300)

        self.db = db


    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success)
    async def cf_accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        id_pattern = r'<@(\d*)>'
        opponent_id = int(re.findall(id_pattern, interaction.message.content)[0])

        if interaction.user.id != opponent_id:
            await interaction.response.send_message("You can't use this interaction!", ephemeral=True)
            return

        player1 = interaction.message.interaction_metadata.user.id
        player2 = opponent_id

        self.db.connectfour_game_exists(player1, player2)

        # Initialize game state
        grid = [[0] * 7 for _ in range(6)]
        turn = random.randint(1, 2)

        view = ConnectFourUI()
        await interaction.response.edit_message(embed=render_board(grid, player1, player2, turn, 1), view=view)
        board_msg = interaction.message

        self.db.connectfour_create_game(player1, player2, turn, grid, board_msg)


    @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger)
    async def cf_decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        id_pattern = r'<@(\d*)>'
        opponent_id = int(re.findall(id_pattern, interaction.message.content)[0])

        if interaction.user.id != opponent_id:
            await interaction.response.send_message("You can't use this interaction!", ephemeral=True)
            return
        
        await interaction.response.edit_message(content=f"{interaction.message.content}\n*User declined the game invitation!*", view=None)


class ConnectFour(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.database
        self.logger = bot.logger
        self.languages = bot.languages
        

    @commands.Cog.listener()
    async def on_ready(self):
        self.logger.info(f"{__name__} is online!")


    @app_commands.command(name="connectfour", description="Start a Connect Four game")
    async def connect_four(self, interaction: discord.Interaction, opponent: discord.User):
        """Starts a new Connect Four game."""
        if interaction.user == opponent:
            await interaction.response.send_message("You cannot play against yourself!", ephemeral=True)
            return

        await interaction.response.send_message(f"{opponent.mention} **{interaction.user.name}** has invited you to a Connect Four match. Would you like to join?", view=ConnectFourRequestUI(self.db))

    
    @app_commands.command(name="connectfour_stats", description="Check your Connect Four stats")
    async def connect_four_stats_command(self, interaction: discord.Interaction):
        user = self.db.connectfour_fetch_user(interaction.user.id)
        
        embed = discord.Embed(
            title=f"{interaction.user.display_name}'s Connect Four stats",
            description=f"""
                Rating: `{user["rating"]}`
                Games played: `{user["games_played"]}`
                Wins: `{user["wins"]}`
                Losses: `{user["losses"]}`
            """
        )

        await interaction.response.send_message(embed=embed)

    
    @app_commands.command(name="connectfour_leaderboard", description="Shows the top Connect 4 players")
    async def connect_four_leaderboard_command(self, interaction: discord.Interaction, page: int = 1):
        user_data = self.db.connectfour_fetch_all_users(1)

        self.logger.debug(user_data)

        if not user_data:
            await interaction.response.send_message("No players found!", ephemeral=True)
            return

        emoji_list = [":first_place:", ":second_place:", ":third_place:"]

        description = ""
        i = 1
        for user in user_data:
            placement_index = emoji_list[i-1] if i <= 3 else f"#{i}" 

            description += f"{placement_index} <@{id}> `{user["rating"]}`\n"

            if i >= 10:
                break

            i += 1

        embed = discord.Embed(
            title="Connect 4 Leaderboard",
            description=description
        )
        
        await interaction.response.send_message(embed=embed)


def render_board(grid, player1, player2, turn, selected_column, winner=0):
        """Generates the game board as an embed."""
        embed = discord.Embed(
            title="Connect Four",
            color=discord.Color.green() if winner else discord.Color.red() if turn == 1 else discord.Color.blue())
        status_label = f"🎉 <@{player1 if winner == 1 else player2}> wins!" if winner else f"<@{player1 if turn == 1 else player2}>'s Turn {':red_circle:' if turn == 1 else ':blue_circle:'}"
        embed.description = f"{status_label}\n{displayGrid(grid)}\nSelected Column: `{selected_column}`"

        return embed

def update_ratings(rating_a, rating_b, result_a, k_a=32, k_b=32):
    expected_a = expected_a = 1 / (1 + 10 ** ((rating_b - rating_a) / 400))
    expected_b = 1 - expected_a

    new_rating_a = max(0, rating_a + k_a * (result_a - expected_a))
    new_rating_b = max(0, rating_b + k_b * ((1 - result_a) - expected_b))

    return new_rating_a, new_rating_b


def k_factor(games_played):
    if games_played < 5:
        return 60
    elif games_played < 30:
        return 40
    else:
        return 20
    

async def setup(bot):
    await bot.add_cog(ConnectFour(bot))