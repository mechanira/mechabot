import sqlite3
import os
import json

class DBManager:
    def __init__(self):
        self.conn = sqlite3.connect('test_data.db')
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()

        self.init_tables()

        return None


    def init_tables(self):
        for file in os.listdir('./utils/database/sql'):
            if file.endswith('.sql'):
                with open(f'./utils/database/sql/{file}', 'r') as f:
                    sql = f.read()
                    self.cursor.executescript(sql)
        self.conn.commit()


    def insert_reminder(self, user_id, channel_id, label, remind_at, daily_remind_at, send_dm):
        self.cursor.execute(
                "INSERT INTO reminders (user_id, channel_id, label, remind_at, daily_time, send_dm) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, channel_id, label, remind_at, daily_remind_at, send_dm)
            )
        self.conn.commit()


    def delete_reminder(self, user_id, label):
        self.cursor.execute("DELETE FROM reminders WHERE user_id = ? AND label = ?", (user_id, label))
        self.conn.commit()


    def fetch_all_user_reminders(self, user_id):
        self.cursor.execute("SELECT label, daily_time, send_dm FROM reminders WHERE user_id = ?", (user_id,))
        return self.cursor.fetchall()


    def select_reminder_due(self, current_time, daily_time):
        self.cursor.execute("SELECT id, user_id, channel_id, label, send_dm, daily_time FROM reminders WHERE remind_at <= ? OR daily_time = ?", (current_time,daily_time))
        results = self.cursor.fetchall()

        for reminder in results:
            self.cursor.execute("DELETE FROM reminders WHERE id = ?", (reminder[0],))

        self.conn.commit()

        return results
    

    def get_connect_four_game(self, message_id) -> dict:
        self.cursor.execute("SELECT * FROM connect_four WHERE message_id = ?", (message_id,))
        return self.cursor.fetchone()
    

    def connectfour_update_selection(self, game_id, column_idx):
        self.cursor.execute("UPDATE connect_four SET selected_column = ? WHERE game_id = ?", (column_idx, game_id,))
        self.conn.commit()

    
    def connectfour_fetch_user(self, player_id) -> dict:
        self.cursor.execute(
            "SELECT id, rating, games_played, wins, losses FROM connect_four_user WHERE id = ?",
            (player_id,)
        )
        row = self.cursor.fetchone()

        # insert new user
        if row is None:
            self.cursor.execute("INSERT INTO connect_four_user (id) VALUES (?)", (player_id,))
            self.conn.commit()
            return player_id, 100, 0, 0, 0

        return row
    
    
    def connectfour_user_insert(self, player_id, rating, games_played, wins, losses):
        self.cursor.execute("""
                INSERT INTO connect_four_user (id, rating, games_played, wins, losses)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    rating = excluded.rating,
                    games_played = excluded.games_played,
                    wins = excluded.wins,
                    losses = excluded.losses;
            """, (player_id, rating, games_played, wins, losses))

        self.conn.commit()

    
    def connectfour_game_exists(self, player1_id, player2_id) -> bool:
        self.cursor.execute("SELECT game_id FROM connect_four WHERE player1_id IN (?, ?) OR player2_id IN (?, ?)", (player1_id, player2_id, player1_id, player2_id))

        if self.cursor.fetchone():
            self.cursor.execute("DELETE FROM connect_four WHERE player1_id IN (?, ?) OR player2_id IN (?, ?)", (player1_id, player2_id, player1_id, player2_id))
            self.conn.commit()
            return True
        
        return False


    def connectfour_create_game(self, player1, player2, turn, grid, board_msg):
        self.cursor.execute("INSERT INTO connect_four (player1_id, player2_id, turn, selected_column, grid, message_id, channel_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (player1, player2, turn, 1, json.dumps(grid), board_msg.id, board_msg.channel.id))
        self.conn.commit()

    
    def connectfour_fetch_all_users(self, page) -> list:
        offset = (page - 1) * 10
        self.cursor.execute("SELECT id, rating, games_played, wins, losses FROM connect_four_user ORDER BY rating DESC LIMIT 10 OFFSET ?", (offset,))
        return self.cursor.fetchall()
    

    def connectfour_check_game_state(self, winner, next_turn, grid, game):
        if winner == 0:
            self.cursor.execute("UPDATE connect_four SET turn = ?, grid = ? WHERE game_id = ?", (next_turn, json.dumps(grid), game["game_id"]))
        else:
            self.cursor.execute("DELETE FROM connect_four WHERE game_id = ?", (game["game_id"],))
        self.conn.commit()


    def gen_fetch_guild_config(self, guild_id):
        config = self.cursor.execute("SELECT * FROM guild_generative_config WHERE id = ?", (guild_id,)).fetchone()
        if config is None:
            self.cursor.execute("INSERT INTO guild_generative_config (id, enabled, temperature, max_words, auto_cache, message_probability) VALUES (?, ?, ?, ?, ?, ?)", (guild_id, False, 1.0, 50, False, 0.01))
            self.conn.commit()
            return self.cursor.execute("SELECT * FROM guild_generative_config WHERE id = ?", (guild_id,)).fetchone()
        return config
    

    def gen_update_guild_config(self, guild_id, option, value):
        self.cursor.execute(f"UPDATE guild_generative_config SET {option} = ? WHERE id = ?", (value, guild_id))
        self.conn.commit()
    
    
    def gen_cache_message(self, message_id, channel_id, content):
        self.cursor.execute(
                "INSERT OR IGNORE INTO generator_message_cache (id, channel_id, content) VALUES (?, ?, ?)", (message_id, channel_id, content,)
            )
        self.conn.commit()


    def gen_fetch_cached_message_content(self, channel_id):
        self.cursor.execute(
            "SELECT content FROM generator_message_cache WHERE channel_id = ?",
            (channel_id,)
        )
        rows = self.cursor.fetchall()
        if not rows:
            return []
        return [row["content"] for row in rows]
    

    def gen_fetch_last_cached_message(self, channel_id):
        self.cursor.execute(
            "SELECT MAX(id) FROM generator_message_cache WHERE channel_id = ?",
            (channel_id,)
        )
        result = self.cursor.fetchone()
        return result[0] if result and result[0] is not None else None
    

    def gen_clear_channel_cache(self, channel_id):
        self.cursor.execute(
            "DELETE FROM generator_message_cache WHERE channel_id = ?",
            (channel_id,)
        )
        self.conn.commit()