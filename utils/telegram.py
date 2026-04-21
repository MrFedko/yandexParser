import requests


def send_telegram(text: str, bot_token: str, chat_id: int):
    url = "https://api.telegram.org/bot"
    url += bot_token
    method = url + "/sendMessage"

    response = requests.post(method, data={
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    })

    if response.status_code != 200:
        print("❌ HTTP ERROR:", response.status_code)
        print(response.text)
        raise Exception("post_text error")

    data = response.json()

    if not data.get("ok"):
        print("❌ TELEGRAM ERROR:", data)
        raise Exception("post_text error")
