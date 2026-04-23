from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException
)
from time import sleep


class BrowserManager:

    def __init__(self, path: str):
        self.path = path
        self.browser = None

    # ---------------- INIT ----------------

    def _init_browser(self):
        service = Service(self.path)
        options = Options()

        options.add_argument("-headless")

        # 🔥 КРИТИЧЕСКИЕ ФИКСЫ ДЛЯ FIREFOX
        options.set_preference("fission.webContentIsolationStrategy", 0)
        options.set_preference("browser.tabs.remote.autostart", False)

        # локаль
        options.set_preference("intl.accept_languages", "ru-RU,ru")

        self.browser = webdriver.Firefox(service=service, options=options)
        self.browser.implicitly_wait(5)

    # ---------------- UTILS ----------------

    def ensure_alive(self):
        try:
            _ = self.browser.title
        except Exception:
            raise WebDriverException("Browser context lost")

    def wait_page_loaded(self):
        WebDriverWait(self.browser, 15).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

    # ---------------- SORT ----------------

    def select_newest(self):
        """Стабильный выбор 'По новизне'"""

        for attempt in range(3):
            try:
                self.ensure_alive()

                # 1. открыть меню
                sort_btn = WebDriverWait(self.browser, 15).until(
                    EC.element_to_be_clickable((By.CLASS_NAME, "rating-ranking-view"))
                )

                self.browser.execute_script(
                    "arguments[0].scrollIntoView({block:'center'});", sort_btn
                )
                sleep(0.5)
                sort_btn.click()

                # 2. выбрать "По новизне"
                newest = WebDriverWait(self.browser, 10).until(
                    EC.element_to_be_clickable((
                        By.XPATH,
                        "//div[contains(@class,'rating-ranking-view__popup-line') and contains(., 'По новизне')]"
                    ))
                )

                newest.click()

                # 🔥 ВАЖНО: ждём НОВЫЙ DOM, а не page_source
                WebDriverWait(self.browser, 15).until(
                    EC.presence_of_all_elements_located(
                        (By.CLASS_NAME, "business-reviews-card-view__review")
                    )
                )

                sleep(1)

                print("✅ По новизне выбрано")
                return True

            except (StaleElementReferenceException, TimeoutException):
                print(f"retry sort {attempt+1}")
                sleep(1)

            except WebDriverException as e:
                print("context lost:", e)
                return False

        return False

    # ---------------- PARSE ----------------

    def parse_reviews(self):
        """Простой стабильный парсинг"""

        try:
            self.ensure_alive()

            reviews = self.browser.find_elements(
                By.CLASS_NAME,
                "business-reviews-card-view__review"
            )

            result = []

            for r in reviews:
                try:
                    text = r.text
                    result.append(text)
                except StaleElementReferenceException:
                    continue

            return result

        except WebDriverException:
            print("Browser died while parsing")
            return []

    # ---------------- RUN ----------------

    def run(self, url: str):
        self._init_browser()

        try:
            self.browser.get(url)
            self.wait_page_loaded()

            print("Opened:", url)

            if not self.select_newest():
                print("⚠️ не удалось применить сортировку")

            data = self.parse_reviews()

            print(f"Найдено отзывов: {len(data)}")
            return data

        finally:
            self.browser.quit()
