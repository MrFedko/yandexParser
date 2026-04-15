class Restaurant:
    def __init__(self, r_id, rest_name, link, chat_id, bot_token):
        self.r_id = r_id
        self.rest_name = rest_name
        self.link = link
        self.chat_id = chat_id
        self.bot_token = bot_token


class Review:
    def __init__(self, review_id, date_time, author_name, author_url, rating, text, sent_to_telegram):
        self.review_id = review_id
        self.date_time = date_time
        self.author_name = author_name
        self.author_url = author_url
        self.rating = rating
        self.text = text
        self.sent_to_telegram = sent_to_telegram
