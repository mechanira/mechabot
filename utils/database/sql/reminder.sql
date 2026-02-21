CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY,
    user_id INTEGER,
    channel_id INTEGER,
    label TEXT,
    remind_at INTEGER,
    daily_time TEXT,
    send_dm BOOLEAN
);
