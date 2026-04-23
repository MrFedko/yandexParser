from loader import data_base, browserManager
from data.dataclasses import Restaurant, Review, convert_to_dataclass
from utils.message_builder import message_builder
from utils.telegram import send_telegram
import time
import random


def main():
    restaurants = convert_to_dataclass(data_base.get_all_restaurants(), Restaurant)

    if not restaurants:
        print('No restaurants found in DB')
        return

    # Парсим все вкладки последовательно (они будут открываться по мере освобождения)
    data = browserManager.run(restaurants)

    # Закрываем браузер один раз
    browserManager.close()

    # Сохраняем новые отзывы
    for i in data:
        if not data_base.get_review(i):
            data_base.add_review(i)

    # Отправляем те отзывы, которые ещё не отправлены в телеграм
    reviews_to_sent = data_base.get_all_reviews_not_sent_to_telegram()
    reviews_to_sent_dataclass = convert_to_dataclass(reviews_to_sent, Review)
    restaurants_map = {r.id: r for r in restaurants}
    for review in reviews_to_sent_dataclass:
        rest = restaurants_map.get(review.rest_id)

        if not rest:
            continue
        text = message_builder(review)
        send_telegram(
            text,
            rest.bot_token,
            rest.chat_id
        )
        data_base.review_is_sent_to_telegram(review)
        # ⏱ задержка 1–2 секунды
        time.sleep(random.uniform(1.0, 2.0))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # Печатаем только сообщение об ошибке без стэктрейса
        print(str(e))
    finally:
        # Пытаемся корректно закрыть браузер, если он был инициализирован
        try:
            browserManager.close()
        except Exception:
            pass
