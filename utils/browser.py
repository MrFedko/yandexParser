from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from time import sleep
from datetime import datetime
from zoneinfo import ZoneInfo


class BrowserManager:
    def __init__(self, driver_path):
        self.driver_path = driver_path
        self.browser = None

    def init_browser(self):
        service = Service(self.driver_path)
        options = Options()

        options.add_argument("-headless")

        # стабильность
        options.set_preference("intl.accept_languages", "ru-RU,ru")
        options.set_preference("permissions.default.image", 2)

        self.browser = webdriver.Firefox(service=service, options=options)
        self.browser.implicitly_wait(10)

    def wait_page(self):
        WebDriverWait(self.browser, 15).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        sleep(2)

    def select_newest(self):
        try:
            btn = WebDriverWait(self.browser, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "rating-ranking-view"))
            )

            self.browser.execute_script("arguments[0].click();", btn)

            newest = WebDriverWait(self.browser, 10).until(
                EC.element_to_be_clickable((
                    By.CSS_SELECTOR,
                    "div.rating-ranking-view__popup-line[aria-label='По новизне']"
                ))
            )

            self.browser.execute_script("arguments[0].click();", newest)
            sleep(2)

            print("✅ Сортировка по новизне")
        except Exception as e:
            print("⚠️ Не удалось выбрать сортировку:", e)

    def parse_page(self, url):
        self.browser.get(url)
        self.wait_page()

        self.select_newest()

        html = self.browser.page_source
        soup = BeautifulSoup(html, "html.parser")

        reviews = soup.find_all(
            "div", {"class": "business-reviews-card-view__review"}
        )

        result = []

        for r in reviews:
            try:
                author = r.find(itemprop="author")
                name = author.find(itemprop="name").text if author else None

                rating = r.find(itemprop="ratingValue")
                rating = rating["content"] if rating else None

                date = r.find(itemprop="datePublished")
                if date:
                    dt = datetime.fromisoformat(date["content"].replace("Z", "+00:00"))
                    dt = dt.astimezone(ZoneInfo("Europe/Moscow"))
                    date = dt.strftime("%Y-%m-%d %H:%M:%S")

                text = r.find(itemprop="reviewBody")
                text = text.text.strip() if text else None

                result.append({
                    "author": name,
                    "rating": rating,
                    "date": date,
                    "text": text
                })

            except Exception as e:
                print("Ошибка парсинга:", e)

        return result

    def run(self, restaurants):
        self.init_browser()

        all_reviews = []

        for r in restaurants:
            print(f"Processing: {r['name']}")

            try:
                data = self.parse_page(r["link"])
                all_reviews.extend(data)
            except Exception as e:
                print("Ошибка:", e)

        self.browser.quit()
        return all_reviews
