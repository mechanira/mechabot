import sqlite3
import os

class DBManager:


    def __init__(self):

        self.connection = sqlite3.connect('data.db')
        self.cursor = self.connection.cursor()

        return None


    def init_tables(self):

        for file in os.listdir('sql'):
            if file.endswith('.sql'):
                reqs = ""
                with open(file, 'r') as l:
                    reqs = l.readlines()
                self.cursor.execute(reqs)
        self.conn.commit()

        return None


    def insertReminder(self, user_id, channel_id, label, remind_at, daily_remind_at, send_dm):

        self.cursor.execute(
                "INSERT INTO reminders (user_id, channel_id, label, remind_at, daily_time, send_dm) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, channel_id, label, remind_at, daily_remind_at, send_dm)
            )
        self.connection.commit()


    def deleteReminder(self, user_id, label):

        self.cursor.execute("DELETE FROM reminders WHERE user_id = ? AND label = ?", (user_id, label))
        self.connection.commit()


    def selectReminder_foruser(self, user_id):

        self.cursor.execute("SELECT label, daily_time, send_dm FROM reminders WHERE user_id = ?", (user_id,))
        return self.cursor.fetchall()


    def selectReminder_due(self, current_time, daily_time):

        self.cursor.execute("SELECT id, user_id, channel_id, label, send_dm, daily_time FROM reminders WHERE remind_at <= ? OR daily_time = ?", (current_time,daily_time))
        results = self.cursor.fetchall()

        for reminder in results:
            self.cursor.execute("DELETE FROM reminders WHERE id = ?", (reminder[0],))

        self.connection.commit()

        return results
