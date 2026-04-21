class Restaurant:
    def __init__(self, id, rest_name, link, chat_id, bot_token):
        self.id = id
        self.rest_name = rest_name
        self.link = link
        self.chat_id = chat_id
        self.bot_token = bot_token


class Review:
    def __init__(self, rest_id, review_id, date_time, author_name, author_url, rating, text, sent_to_telegram):
        self.rest_id = rest_id
        self.review_id = review_id
        self.date_time = date_time
        self.author_name = author_name
        self.author_url = author_url
        self.rating = rating
        self.text = text
        self.sent_to_telegram = sent_to_telegram

    def __str__(self):
        return f"Review(rest_id={self.rest_id}, review_id={self.review_id}, date_time={self.date_time}, author_name={self.author_name}, " \
               f"author_url={self.author_url}, rating={self.rating}, text={self.text}, " \
               f"sent_to_telegram={self.sent_to_telegram})"


def convert_to_dataclass(data: list[dict], cls):
    return [cls(**item) for item in data]
