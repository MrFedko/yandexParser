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


# python
class BrowserManager:
    def __init__(self, path: str):
        self.path = path
        self.browser = None
        self.tab_map = {}

    def _init_browser(self):
        ser = Service(self.path)
        op = webdriver.ChromeOptions()

        headless = os.getenv("HEADLESS", "1") == "1"
        humanize = os.getenv("HUMANIZE", "1") == "1"

        if headless:
            op.add_argument('--headless=new')

        ua = os.getenv("USER_AGENT") or random.choice(UA_LIST)
        op.add_argument(f'--user-agent={ua}')

        proxy = os.getenv("PROXY")
        if proxy:
            op.add_argument(f'--proxy-server={proxy}')

        # Предпочтительно задавать через окружение для слабых машин
        width = int(os.getenv("BROWSER_WIDTH", "1024"))
        height = int(os.getenv("BROWSER_HEIGHT", "768"))
        op.add_argument(f'--window-size={width},{height}')

        # экономия памяти и стабильность на контейнерах/малой RAM
        op.add_argument('--disable-dev-shm-usage')
        op.add_argument('--no-sandbox')
        op.add_argument('--disable-gpu')
        op.add_argument('--disable-extensions')

        op.add_experimental_option('excludeSwitches', ['enable-automation'])
        op.add_experimental_option('useAutomationExtension', False)

        if not humanize:
            prefs = {
                "profile.managed_default_content_settings.images": 2,
                "profile.managed_default_content_settings.fonts": 2,
            }
            op.add_experimental_option("prefs", prefs)

        op.page_load_strategy = 'eager'

        self.browser = webdriver.Chrome(service=ser, options=op)
        self.browser.implicitly_wait(7)

        try:
            self.browser.execute_cdp_cmd(
                'Page.addScriptToEvaluateOnNewDocument',
                {
                    'source': """
                    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                    Object.defineProperty(navigator, 'languages', {get: () => ['ru-RU', 'ru']});
                    Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3]});
                    const originalQuery = window.navigator.permissions.query;
                    window.navigator.permissions.query = (parameters) => (
                        parameters.name === 'notifications' ? Promise.resolve({ state: 'denied' }) : originalQuery(parameters)
                    );
                    """
                }
            )
            try:
                headers = {'Accept-Language': os.getenv('ACCEPT_LANGUAGE', 'ru-RU,ru;q=0.9')}
                self.browser.execute_cdp_cmd('Network.enable', {})
                self.browser.execute_cdp_cmd('Network.setExtraHTTPHeaders', {'headers': headers})
            except Exception:
                pass
        except Exception:
            pass

    def _wait_dom(self):
        WebDriverWait(self.browser, 15).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        WebDriverWait(self.browser, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "rating-ranking-view"))
        )
        sleep(1)

    def human_sleep(self, a: float = 0.3, b: float = 1.2):
        sleep(random.uniform(a, b))

    def human_move_and_click(self, element):
        try:
            chain = ActionChains(self.browser)
            chain.move_to_element(element)
            for _ in range(random.randint(1, 3)):
                chain.pause(random.uniform(0.03, 0.15))
                chain.move_by_offset(random.randint(-3, 3), random.randint(-3, 3))
            chain.pause(random.uniform(0.05, 0.25))
            chain.click()
            chain.perform()
        except Exception:
            try:
                self.browser.execute_script("arguments[0].click();", element)
            except Exception:
                raise

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
        self.browser.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
        try:
            self.wait_clickable_js(btn)
        except StaleElementReferenceException:
            btn = WebDriverWait(self.browser, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "rating-ranking-view"))
            )
            self.browser.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
        try:
            self.human_move_and_click(btn)
        except Exception:
            try:
                self.browser.execute_script("arguments[0].click();", btn)
            except Exception:
                raise
        WebDriverWait(self.browser, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".rating-ranking-view__popup-line"))
        )

    def select_newest(self):
        self.open_sort_menu()
        selector = "div.rating-ranking-view__popup-line[aria-label='По новизне']"
        attempts = 3
        for attempt in range(1, attempts + 1):
            try:
                newest = WebDriverWait(self.browser, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                )
                self.browser.execute_script("arguments[0].scrollIntoView({block: 'center'});", newest)
                try:
                    self.human_move_and_click(newest)
                except Exception:
                    self.browser.execute_script("arguments[0].click();", newest)
                WebDriverWait(self.browser, 10).until(
                    lambda d: len(d.find_elements(By.CLASS_NAME, "business-reviews-card-view__review")) > 0
                )
                return
            except StaleElementReferenceException:
                self.human_sleep(0.3, 0.7)
                continue
            except TimeoutException:
                self.human_sleep(0.3, 0.7)
                continue
        raise Exception("Failed to select newest after retries")

    def open_multiple_tabs(self, restaurants):
        self._init_browser()
        self.tab_map = {}
        self.browser.get(restaurants[0].link)
        self._wait_dom()
        self.tab_map[self.browser.current_window_handle] = restaurants[0]
        for r in restaurants[1:]:
            self.human_sleep(0.2, 0.8)
            self.browser.execute_script("window.open(arguments[0]);", r.link)
            new_handle = self.browser.window_handles[-1]
            self.browser.switch_to.window(new_handle)
            self._wait_dom()
            self.tab_map[new_handle] = r

    def _parse_current_page(self, rest):
        all_reviews = []
        try:
            sorted_ok = False
            for _ in range(3):
                try:
                    self.select_newest()
                    sorted_ok = True
                    break
                except Exception:
                    self.human_sleep(0.8, 1.5)
            if not sorted_ok:
                pass
            old_source = self.browser.page_source
            WebDriverWait(self.browser, 10).until(lambda d: d.page_source != old_source)
            self.human_sleep(0.8, 1.5)
            reviews = self.browser.find_elements(By.CLASS_NAME, "business-reviews-card-view__review")
            html = "".join([r.get_attribute("outerHTML") for r in reviews])
            soup = BeautifulSoup(html, "html.parser")
            reviews = soup.find_all("div", {"class": "business-reviews-card-view__review"})
            for review in reviews:
                author_tag = review.find(itemprop="author")
                name_tag = author_tag.find(itemprop="name") if author_tag else None
                link_tag = author_tag.find("a") if author_tag else None
                author_name = name_tag.get_text(strip=True) if name_tag else None
                author_url = link_tag["href"] if link_tag else None
                rating_tag = review.find(itemprop="ratingValue")
                rating = rating_tag["content"] if rating_tag else None
                date_tag = review.find(itemprop="datePublished")
                date = date_tag["content"] if date_tag else None
                dt = datetime.fromisoformat(date.replace("Z", "+00:00"))
                dt_msk = dt.astimezone(ZoneInfo("Europe/Moscow"))
                date_str = dt_msk.strftime("%Y-%m-%d %H:%M:%S")
                text_tag = review.find(itemprop="reviewBody")
                text = None
                if text_tag:
                    inner = text_tag.find("span", class_="spoiler-view__text-container")
                    text = inner.get_text(strip=True) if inner else text_tag.get_text(strip=True)
                all_reviews.append(
                    Review(
                        rest_id=rest.id,
                        review_id=str(uuid.uuid4()),
                        date_time=date_str,
                        author_name=author_name,
                        author_url=author_url,
                        rating=rating,
                        text=text,
                        sent_to_telegram=False
                    )
                )
        except Exception as e:
            print(f"Error in {rest.rest_name}: {e}")
        return all_reviews

    def process_sequentially(self, restaurants):
        self._init_browser()
        results = []
        for rest in restaurants:
            try:
                self.browser.get(rest.link)
                self._wait_dom()
                results.extend(self._parse_current_page(rest))
                self.human_sleep(0.5, 1.5)
            except Exception as e:
                print(f"Error while processing {rest.rest_name}: {e}")
        self.close()
        return results

    def parse_all_tabs(self, restaurants):
        # старый метод оставлен для совместимости
        all_reviews = []
        for handle, rest in self.tab_map.items():
            self.browser.switch_to.window(handle)
            try:
                old = self.browser.page_source
                WebDriverWait(self.browser, 10).until(lambda d: d.page_source != old)
                self.human_sleep(0.8, 1.5)
                reviews = self.browser.find_elements(By.CLASS_NAME, "business-reviews-card-view__review")
                html = "".join([r.get_attribute("outerHTML") for r in reviews])
                soup = BeautifulSoup(html, "html.parser")
                reviews = soup.find_all("div", {"class": "business-reviews-card-view__review"})
                for review in reviews:
                    # краткий парсинг — можно переиспользовать _parse_current_page при рефакторе
                    pass
            except Exception as e:
                print(f"Error in {rest.rest_name}: {e}")
        return all_reviews

    def close(self):
        if self.browser:
            try:
                self.browser.quit()
            except Exception:
                pass
