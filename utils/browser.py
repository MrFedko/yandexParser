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

import os
import random

# Небольшой список User-Agent-ов (можно расширить или подставлять из внешнего источника)
UA_LIST = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.5790.170 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36",
]


class BrowserManager:
    def __init__(self, path: str):
        self.path = path
        self.browser = None

    # ---------------- INIT ----------------

    def _init_browser(self):
        ser = Service(self.path)
        op = webdriver.ChromeOptions()

        # Параметры поведения, управляемые через переменные окружения
        # Если нужно запустить в headless на сервере, установите HEADLESS=1
        headless = os.getenv("HEADLESS", "1") == "1"
        # Если HUMANIZE=1 — применяем набор техник для снижения детектирования как бот
        humanize = os.getenv("HUMANIZE", "1") == "1"

        # Опции, которые делают браузер более похожим на реальный
        if headless:
            # оставляем возможность использования новых headless флагов, если нужно
            op.add_argument('--headless=new')

        # Устанавливаем User-Agent: можно задать через USER_AGENT или взять случайный из списка
        ua = os.getenv("USER_AGENT") or random.choice(UA_LIST)
        op.add_argument(f'--user-agent={ua}')

        # Proxy (опционально) — ожидается формат host:port или schema://host:port
        proxy = os.getenv("PROXY")
        if proxy:
            # Chrome принимает аргумент --proxy-server
            op.add_argument(f'--proxy-server={proxy}')

        # Размер окна — случайный стандартный размер (чтобы отличаться между запусками)
        width = random.choice([1200, 1366, 1440, 1600])
        height = random.choice([700, 768, 900, 1000])
        op.add_argument(f'--window-size={width},{height}')

        # Отключаем автоматические флаги, которые выдают Selenium
        op.add_experimental_option('excludeSwitches', ['enable-automation'])
        op.add_experimental_option('useAutomationExtension', False)

        # Если мы хотим очеловечить — не отключаем изображения и шрифты
        if not humanize:
            # ускорение при небезопасном (non-human) режиме — отключаем изображения/шрифты
            prefs = {
                "profile.managed_default_content_settings.images": 2,
                "profile.managed_default_content_settings.fonts": 2,
            }
            op.add_experimental_option("prefs", prefs)

        # другие оптимизации, но аккуратно
        op.add_argument('--no-sandbox')
        op.add_argument('--disable-gpu')
        op.add_argument('--disable-extensions')

        # op.add_argument("--single-process")
        # op.add_argument("--disable-extensions")
        # op.add_argument("--disable-background-networking")
        # op.add_argument("--disable-sync")
        # op.add_argument("--metrics-recording-only")
        # op.add_argument("--mute-audio")
        # op.add_argument("--no-first-run")
        # op.add_argument("--disable-default-apps")
        # op.add_argument("--renderer-process-limit=2")

        op.page_load_strategy = 'eager'

        self.browser = webdriver.Chrome(service=ser, options=op)
        # Устанавливаем не слишком маленькую implicit wait
        self.browser.implicitly_wait(10)

        # Применяем небольшой скрипт через CDP до загрузок страниц, чтобы скрыть navigator.webdriver и задать языки/plugins
        try:
            # Этот скрипт будет выполняться на каждой новой странице
            self.browser.execute_cdp_cmd(
                'Page.addScriptToEvaluateOnNewDocument',
                {
                    'source': """
                    // Отключаем webdriver флаг
                    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                    // Ставим языки
                    Object.defineProperty(navigator, 'languages', {get: () => ['ru-RU', 'ru']});
                    // Имитация плагинов
                    Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3]});
                    // Имитация разрешений (например, geolocation)
                    const originalQuery = window.navigator.permissions.query;
                    window.navigator.permissions.query = (parameters) => (
                        parameters.name === 'notifications' ? Promise.resolve({ state: 'denied' }) : originalQuery(parameters)
                    );
                    """
                }
            )
            # Устанавливаем дополнительные сетевые заголовки через CDP — полезно для очеловечивания
            try:
                # Включаем сетевой модуль и добавляем заголовки (Accept-Language и стандартный Referer если нужно)
                headers = {
                    'Accept-Language': os.getenv('ACCEPT_LANGUAGE', 'ru-RU,ru;q=0.9'),
                    # можно добавлять другие заголовки, например 'Referer' или 'User-Agent' при необходимости
                }
                self.browser.execute_cdp_cmd('Network.enable', {})
                self.browser.execute_cdp_cmd('Network.setExtraHTTPHeaders', {'headers': headers})
            except Exception:
                # если сетевые CDP вызовы не работают — продолжаем
                pass
        except Exception:
            # если CDP недоступен — продолжаем без него
            pass

    def _wait_dom(self):
        WebDriverWait(self.browser, 15).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        WebDriverWait(self.browser, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "rating-ranking-view"))
        )

        sleep(1)  # короткая стабилизация UI

    # ---------------- Human helpers ----------------

    def human_sleep(self, a: float = 0.3, b: float = 1.2):
        """Небольшая случайная пауза как у человека."""
        sleep(random.uniform(a, b))

    def human_move_and_click(self, element):
        """Делаем более естественный клик: небольшие смещения и паузы."""
        try:
            chain = ActionChains(self.browser)
            chain.move_to_element(element)
            # небольшие колебания курсора
            for _ in range(random.randint(1, 3)):
                chain.pause(random.uniform(0.03, 0.15))
                chain.move_by_offset(random.randint(-3, 3), random.randint(-3, 3))
            chain.pause(random.uniform(0.05, 0.25))
            chain.click()
            chain.perform()
        except Exception:
            # fallback на JS click
            try:
                self.browser.execute_script("arguments[0].click();", element)
            except Exception:
                raise

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
            # human-like
            self.human_move_and_click(btn)
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
                    # human-like
                    self.human_move_and_click(newest)
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
                self.human_sleep(0.3, 0.7)
                continue
            except TimeoutException:
                print(f"Timeout when locating 'По новизне', retry {attempt}/{attempts}")
                self.human_sleep(0.3, 0.7)
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
            self.human_sleep(0.2, 0.8)
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
                        print("retry sort:", str(e))
                        self.human_sleep(0.8, 1.5)

                if not sorted_ok:
                    print("⚠️ sort not applied, parsing as-is")

                # 2. ждём СТАБИЛИЗАЦИЮ DOM после возможного клика
                old_source = self.browser.page_source

                WebDriverWait(self.browser, 10).until(
                    lambda d: d.page_source != old_source
                )

                self.human_sleep(0.8, 1.5)  # 🔥 React финальная стабилизация

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
