from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver import ActionChains
from bs4 import BeautifulSoup
from time import sleep
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from data.dataclasses import Review
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException


class BrowserManager:
    def __init__(self, path: str):
        self.path = path
        self.browser = None

    # ---------------- INIT ----------------

    def _init_browser(self):
        ser = Service(self.path)
        op = webdriver.ChromeOptions()

        # ускорение
        op.add_argument('--headless=new')
        op.add_argument('--no-sandbox')
        op.add_argument('--disable-gpu')
        op.add_argument('--disable-extensions')
        op.page_load_strategy = 'eager'

        # отключаем тяжёлое
        prefs = {
            "profile.managed_default_content_settings.images": 2,
            "profile.managed_default_content_settings.fonts": 2,
        }
        op.add_experimental_option("prefs", prefs)

        self.browser = webdriver.Chrome(service=ser, options=op)
        self.browser.implicitly_wait(10)

    def _wait_dom(self):
        WebDriverWait(self.browser, 15).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        WebDriverWait(self.browser, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "rating-ranking-view"))
        )

        sleep(1)  # короткая стабилизация UI

    # ---------------- SORT ----------------

    def wait_clickable_js(self, element):
        WebDriverWait(self.browser, 15).until(
            lambda d: d.execute_script("""
                const el = arguments[0];
                const rect = el.getBoundingClientRect();
                const elem = document.elementFromPoint(
                    rect.x + rect.width/2,
                    rect.y + rect.height/2
                );
                return el === elem || el.contains(elem);
            """, element)
        )

    def open_sort_menu(self):
        btn = WebDriverWait(self.browser, 15).until(
            EC.presence_of_element_located((By.CLASS_NAME, "rating-ranking-view"))
        )

        # скроллим
        self.browser.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});", btn
        )

        # 🔥 ждём реальной кликабельности (а не просто Selenium)
        try:
            self.wait_clickable_js(btn)
        except StaleElementReferenceException:
            # элемент мог стать stale — попытка пере-локализации
            btn = WebDriverWait(self.browser, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "rating-ranking-view"))
            )
            self.browser.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});", btn
            )

        # используем безопасный клик: сначала ActionChains, иначе JS click
        try:
            ActionChains(self.browser) \
                .move_to_element(btn) \
                .pause(0.2) \
                .click() \
                .perform()
        except Exception:
            try:
                self.browser.execute_script("arguments[0].click();", btn)
            except Exception as e:
                raise

        # ждём открытия меню
        WebDriverWait(self.browser, 10).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, ".rating-ranking-view__popup-line")
            )
        )

    def select_newest(self):
        # открываем меню сортировки
        self.open_sort_menu()

        selector = "div.rating-ranking-view__popup-line[aria-label='По новизне']"

        # пытаемся надёжно кликнуть по пункту 'По новизне' с повторными попытками
        attempts = 3
        for attempt in range(1, attempts + 1):
            try:
                newest = WebDriverWait(self.browser, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                )

                # скроллим к нему
                self.browser.execute_script(
                    "arguments[0].scrollIntoView({block: 'center'});", newest
                )

                # сначала пробуем нормальный клик через ActionChains
                try:
                    ActionChains(self.browser) \
                        .move_to_element(newest) \
                        .pause(0.2) \
                        .click() \
                        .perform()
                except Exception:
                    # fallback: JS click (устойчивее к overlay / быстрым изменениям DOM)
                    self.browser.execute_script("arguments[0].click();", newest)

                # подтверждаем, что отзывы загрузились
                WebDriverWait(self.browser, 10).until(
                    lambda d: len(
                        d.find_elements(By.CLASS_NAME, "business-reviews-card-view__review")
                    ) > 0
                )

                print("✅ По новизне выбрано")
                return

            except StaleElementReferenceException:
                print(f"Stale element when selecting newest, retry {attempt}/{attempts}")
                sleep(0.5)
                continue
            except TimeoutException:
                print(f"Timeout when locating 'По новизне', retry {attempt}/{attempts}")
                sleep(0.5)
                continue

        # если не удалось
        raise Exception("Failed to select newest after retries")

    # ---------------- TABS ----------------

    def open_multiple_tabs(self, restaurants):
        self._init_browser()

        self.tab_map = {}

        # первая вкладка
        self.browser.get(restaurants[0].link)
        self._wait_dom()

        self.tab_map[self.browser.current_window_handle] = restaurants[0]

        # остальные вкладки
        for r in restaurants[1:]:
            self.browser.execute_script("window.open(arguments[0]);", r.link)

            # переключаемся на новую вкладку (последнюю)
            new_handle = self.browser.window_handles[-1]
            self.browser.switch_to.window(new_handle)

            self._wait_dom()

            # фиксируем связь
            self.tab_map[new_handle] = r

    # ---------------- PARSE ----------------

    def parse_all_tabs(self, restaurants):
        all_reviews = []

        for handle, rest in self.tab_map.items():
            self.browser.switch_to.window(handle)

            print(f"Processing: {rest.rest_name}")

            try:
                # 1. пробуем применить сортировку
                sorted_ok = False

                for _ in range(3):
                    try:
                        self.select_newest()
                        sorted_ok = True
                        break
                    except Exception as e:
                        print("retry sort:", e)
                        sleep(1)

                if not sorted_ok:
                    print("⚠️ sort not applied, parsing as-is")

                # 2. ждём СТАБИЛИЗАЦИЮ DOM после возможного клика
                old_source = self.browser.page_source

                WebDriverWait(self.browser, 10).until(
                    lambda d: d.page_source != old_source
                )

                sleep(1)  # 🔥 React финальная стабилизация

                # 3. теперь парсим
                reviews = self.browser.find_elements(
                    By.CLASS_NAME,
                    "business-reviews-card-view__review"
                )
                html = "".join([r.get_attribute("outerHTML") for r in reviews])
                soup = BeautifulSoup(html, "html.parser")

                reviews = soup.find_all(
                    "div",
                    {"class": "business-reviews-card-view__review"}
                )

                for review in reviews:

                    # -------- author --------
                    author_tag = review.find(itemprop="author")
                    name_tag = author_tag.find(itemprop="name") if author_tag else None
                    link_tag = author_tag.find("a") if author_tag else None

                    author_name = name_tag.get_text(strip=True) if name_tag else None
                    author_url = link_tag["href"] if link_tag else None

                    # -------- rating --------
                    rating_tag = review.find(itemprop="ratingValue")
                    rating = rating_tag["content"] if rating_tag else None

                    # -------- date --------
                    date_tag = review.find(itemprop="datePublished")
                    date = date_tag["content"] if date_tag else None
                    dt = datetime.fromisoformat(date.replace("Z", "+00:00"))

                    dt_msk = dt.astimezone(ZoneInfo("Europe/Moscow"))

                    date = dt_msk.strftime("%Y-%m-%d %H:%M:%S")

                    # -------- text --------
                    text_tag = review.find(itemprop="reviewBody")
                    text = None

                    if text_tag:
                        inner = text_tag.find("span", class_="spoiler-view__text-container")
                        text = inner.get_text(strip=True) if inner else text_tag.get_text(strip=True)

                    # -------- save --------
                    all_reviews.append(
                        Review(
                            rest_id=rest.id,
                            review_id=str(uuid.uuid4()),
                            date_time=date,
                            author_name=author_name,
                            author_url=author_url,
                            rating=rating,
                            text=text,
                            sent_to_telegram=False
                        ))

            except Exception as e:
                print(f"Error in {rest.rest_name}: {e}")

        return all_reviews

    # ---------------- CLOSE ----------------

    def close(self):
        if self.browser:
            self.browser.quit()
