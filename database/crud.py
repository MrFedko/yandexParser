import sqlite3

from data.dataclasses import Review


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

    def get_restaurant_by_id(self, r_id):
        return self.execute("SELECT * FROM restaurants WHERE id = ?", (r_id,), fetchone=True)

    def get_all_restaurants(self):
        return self.execute("SELECT * FROM restaurants", fetchall=True)


    def add_review(self, review: Review):
        self.execute(
            """
            INSERT INTO reviews (
                rest_id,
                review_id,
                date_time,
                author_name,
                author_url,
                rating,
                text,
                sent_to_telegram
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                review.rest_id,
                review.review_id,
                review.date_time,
                review.author_name,
                review.author_url,
                review.rating,
                review.text,
                review.sent_to_telegram
            )
        )

    def get_review(self, review: Review):
        return self.execute("SELECT * FROM reviews WHERE date_time = ? AND author_name = ?",
                            (review.date_time, review.author_name), fetchone=True)

    def get_all_reviews_not_sent_to_telegram(self):
        return self.execute(
            """SELECT rest_id,
                review_id,
                date_time,
                author_name,
                author_url,
                rating,
                text,
                sent_to_telegram 
                FROM reviews WHERE sent_to_telegram = 0 ORDER BY date_time ASC""",
            fetchall=True
        )

    def review_is_sent_to_telegram(self, review: Review):
        self.execute(
            """
            UPDATE reviews
            SET sent_to_telegram = 1
            WHERE author_name = ? AND date_time = ?
            """,
            (review.author_name, review.date_time)
        )

    def get_rest_name_by_id(self, rest_id):
        return self.execute("SELECT rest_name FROM restaurants WHERE id = ?", (rest_id,), fetchone=True)
