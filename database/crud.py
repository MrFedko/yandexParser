import sqlite3


class Database:
    def __init__(self, path):
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.scheme_tables = {
            "restaurants": ("rest_name", "link", "chat_id", "bot_token",),
            "reviews": ("rest_id", "review_id", "date_time", "author_name", "author_url", "rating", "text", "sent_to_telegram",),
        }

    def execute(self, query: str, params: tuple = (), fetchone=False, fetchall=False):
        with self.connection:
            cursor = self.connection.execute(query, params)
            if fetchone:
                return cursor.fetchone()
            if fetchall:
                return cursor.fetchall()

    def create_table_restaurants(self):
        self.execute("""CREATE TABLE restaurants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        rest_name TEXT NOT NULL,
        link TEXT NOT NULL,
        chat_id TEXT NOT NULL,
        bot_token TEXT NOT NULL
    );""")

    def create_table_reviews(self):
        self.execute("""CREATE TABLE reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        rest_id INTEGER NOT NULL,
        review_id TEXT NOT NULL,
        date_time TIMESTAMP NOT NULL,
        author_name TEXT NOT NULL,
        author_url TEXT,
        rating INTEGER NOT NULL,
        text TEXT NOT NULL,
        sent_to_telegram BOOLEAN NOT NULL DEFAULT 0,
        FOREIGN KEY (rest_id) REFERENCES restaurants(id)
    );""")
