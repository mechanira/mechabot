CREATE TABLE IF NOT EXISTS generator_message_cache(
    id INTEGER PRIMARY KEY,
    channel_id INTEGER NOT NULL,
    content TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS guild_generative_config(
    id INTEGER PRIMARY KEY,
    enabled BOOLEAN NOT NULL,
    temperature REAL NOT NULL,
    max_words INTEGER NOT NULL,
    auto_cache BOOLEAN NOT NULL,
    message_probability REAL NOT NULL
);