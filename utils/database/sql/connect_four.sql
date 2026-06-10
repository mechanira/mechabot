CREATE TABLE IF NOT EXISTS connect_four (
    game_id INTEGER PRIMARY KEY,
    player1_id INTEGER NOT NULL,
    player2_id INTEGER NOT NULL,
    turn INTEGER NOT NULL,
    selected_column INTEGER DEFAULT 1,
    grid TEXT NOT NULL,
    message_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS connect_four_user (
    id INTEGER PRIMARY KEY,
    rating INTEGER NOT NULL DEFAULT 100,
    games_played INTEGER NOT NULL DEFAULT 0,
    wins INTEGER NOT NULL DEFAULT 0,
    losses INTEGER NOT NULL DEFAULT 0
);
