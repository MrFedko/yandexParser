from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
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
        # используем Firefox (geckodriver)
        op = Options()

        # headless режим
        try:
            # prefer explicit headless flag
            op.add_argument('-headless')
        except Exception:
            op.headless = True

        # стратегия загрузки страниц
        try:
            op.page_load_strategy = 'eager'
        except Exception:
            # некоторые версии selenium могут не поддерживать установку — безопасно игнорируем
            pass

        # ускорение: отключаем загрузку картинок
        # 2 = block images
        op.set_preference("permissions.default.image", 2)

        # создаём Firefox драйвер
        self.browser = webdriver.Firefox(service=ser, options=op)
        self.browser.implicitly_wait(10)

    def _wait_dom(self):
        WebDriverWait(self.browser, 15).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        WebDriverWait(self.browser, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "rating-ranking-view"))
        )

        sleep(1)  # короткая стабилизация UI

    def _inject_map_blocker(self):
        """Инъекция JS, блокирующего загрузку карты/плагина и удаляющего существующие элементы карты."""
        js = r"""
        (function(){
          const patterns = ['yandex.ru/maps','api-maps.yandex.ru','static-maps.yandex','maps.yandex','mapbox.com','openstreetmap.org','maps.gstatic.com'];
          function matches(u){ if(!u) return false; try{ return patterns.some(p=>u.indexOf(p)!==-1); }catch(e){return false;} }
  
          ['appendChild','insertBefore'].forEach(fn=>{
            const orig = Node.prototype[fn];
            Node.prototype[fn] = function(node, ref){
              try{
                if(node && node.tagName === 'SCRIPT'){
                  let src = node.src || (node.getAttribute && node.getAttribute('src')) || '';
                  if(matches(src) || (node.innerHTML && node.innerHTML.indexOf('maps')!==-1)){
                    return node;
                  }
                }
                if(node && node.tagName === 'IFRAME'){
                  let src = node.src || (node.getAttribute && node.getAttribute('src')) || '';
                  if(matches(src)){
                    return node;
                  }
                }
              }catch(e){}
              return orig.call(this, node, ref);
            };
          });
  
          const origCreate = Document.prototype.createElement;
          Document.prototype.createElement = function(tag){
            const el = origCreate.call(this, tag);
            try{
              if(tag.toLowerCase()==='script' || tag.toLowerCase()==='iframe'){
                const desc = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'src');
                const setter = desc && desc.set;
                Object.defineProperty(el,'src',{
                  set:function(v){ if(matches(v)){ return; } if(setter) setter.call(this,v); else this.setAttribute('src',v); },
                  get:function(){ return this.getAttribute('src'); },
                  configurable:true
                });
              }
            }catch(e){}
            return el;
          };
  
          try{
            const origFetch = window.fetch;
            window.fetch = function(input, init){
              let url = (typeof input==='string')? input : (input && input.url);
              if(matches(url)) return new Promise(()=>{});
              return origFetch.apply(this, arguments);
            };
          }catch(e){}
  
          try{
            const origOpen = XMLHttpRequest.prototype.open;
            XMLHttpRequest.prototype.open = function(method, url){
              if(matches(url)){ try{ this.abort(); }catch(e){}; return; }
              return origOpen.apply(this, arguments);
            };
          }catch(e){}
  
          setTimeout(()=>{
            try{
              document.querySelectorAll('iframe[src*="maps"], iframe[src*="map"], script[src*="maps"], script[src*="map"], div[class*="map"], .map, [id*="map"], [data-qa*="map"]').forEach(el=>el.remove());
            }catch(e){}
          }, 50);
        })();
        """
        try:
            self.browser.execute_script(js)
        except Exception as e:
            print("Map blocker injection failed:", e)

    def _enforce_russian_language(self):
        """Инъекция JS, которая принудительно ставит русскую локаль на странице."""
        js = r"""
        (function(){
          try{
            Object.defineProperty(navigator, 'language', {get: function(){ return 'ru-RU'; }, configurable: true});
            Object.defineProperty(navigator, 'languages', {get: function(){ return ['ru-RU','ru']; }, configurable: true});
          }catch(e){}
          try{ document.documentElement.lang = 'ru'; }catch(e){}
          try{ var h = document.querySelector('html'); if(h) h.setAttribute('lang','ru'); }catch(e){}
        })();
        """
        try:
            self.browser.execute_script(js)
        except Exception as e:
            print("Language enforcement injection failed:", e)

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
        """Открывает не более двух вкладок сразу. Остальные рестораны сохраняются в очередь self._queue.
        После вызова этой функции вызовите parse_all_tabs() чтобы последовательно обработать очередь.
        """
        self._init_browser()

        self.tab_map = {}
        # очередь оставшихся ресторанов (объекты SimpleNamespace / dataclass с полем .link)
        self._queue = []

        if not restaurants:
            return

        # открываем первую
        first = restaurants[0]
        self.browser.get(first.link)
        try:
            self._inject_map_blocker()
        except Exception:
            pass
        try:
            self._enforce_russian_language()
        except Exception:
            pass
        self._wait_dom()
        self.tab_map[self.browser.current_window_handle] = first

        # открываем вторую, если есть
        if len(restaurants) > 1:
            second = restaurants[1]
            self.browser.execute_script("window.open(arguments[0]);", second.link)
            new_handle = self.browser.window_handles[-1]
            self.browser.switch_to.window(new_handle)
            try:
                self._inject_map_blocker()
            except Exception:
                pass
            try:
                self._enforce_russian_language()
            except Exception:
                pass
            self._wait_dom()
            self.tab_map[new_handle] = second

        # остаток в очередь
        if len(restaurants) > 2:
            self._queue = restaurants[2:]

    # ---------------- PARSE ----------------

    def parse_all_tabs(self, restaurants=None):
        """Динамически обрабатывает открытые вкладки.
        После парсинга вкладка закрывается и при наличии очереди открывается следующая.
        Возвращает список всех найденных отзывов.
        Если `open_multiple_tabs` не вызывался, можно передать список restaurants — тогда он будет использован.
        """
        # если пользователь передал restaurants, и open_multiple_tabs не вызывали — инициализируем
        if restaurants and not getattr(self, 'tab_map', None):
            self.open_multiple_tabs(restaurants)

        all_reviews = []

        # пока есть открытые вкладки
        while getattr(self, 'tab_map', None) and len(self.tab_map) > 0:
            # snapshot списка handles — обрабатываем в порядке появления
            handles = list(self.tab_map.keys())

            for handle in handles:
                # если таб был закрыт в промежутке — пропускаем
                if handle not in self.tab_map:
                    continue

                rest = self.tab_map[handle]
                try:
                    self.browser.switch_to.window(handle)
                except Exception:
                    # если переключение не удалось — попробуем переключиться на любой существующий
                    if self.browser.window_handles:
                        self.browser.switch_to.window(self.browser.window_handles[-1])
                    else:
                        break

                print(f"Processing: {rest.rest_name}")

                try:
                    # попытка применить сортировку
                    sorted_ok = False
                    for _ in range(3):
                        try:
                            self.select_newest()
                            sorted_ok = True
                            break
                        except Exception as e:
                            print("retry sort:", str(e).split("\n")[0])
                            sleep(1)

                    if not sorted_ok:
                        print("⚠️ sort not applied, parsing as-is")

                    # ждём стабилизацию DOM
                    old_source = self.browser.page_source
                    try:
                        WebDriverWait(self.browser, 10).until(
                            lambda d: d.page_source != old_source
                        )
                    except Exception:
                        pass

                    sleep(1)

                    # парсим текущую вкладку (извлечение HTML отзывов — как раньше)
                    reviews_elems = self.browser.find_elements(
                        By.CLASS_NAME,
                        "business-reviews-card-view__review"
                    )
                    html = "".join([r.get_attribute("outerHTML") for r in reviews_elems])
                    soup = BeautifulSoup(html, "html.parser")

                    reviews = soup.find_all(
                        "div",
                        {"class": "business-reviews-card-view__review"}
                    )

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
                        date = dt_msk.strftime("%Y-%m-%d %H:%M:%S")

                        text_tag = review.find(itemprop="reviewBody")
                        text = None
                        if text_tag:
                            inner = text_tag.find("span", class_="spoiler-view__text-container")
                            text = inner.get_text(strip=True) if inner else text_tag.get_text(strip=True)

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

                # Закрываем обработанную вкладку
                try:
                    # switch to it to close
                    try:
                        self.browser.switch_to.window(handle)
                    except Exception:
                        pass
                    self.browser.close()
                except Exception as e:
                    print("Error closing tab:", e)

                # Удаляем из мапы
                try:
                    del self.tab_map[handle]
                except KeyError:
                    pass

                # Если в очереди есть еще рестораны — открываем следующий (чтобы было максимум 2 вкладки)
                if getattr(self, '_queue', None) and len(self._queue) > 0:
                    next_rest = self._queue.pop(0)
                    self.browser.execute_script("window.open(arguments[0]);", next_rest.link)
                    new_handle = self.browser.window_handles[-1]
                    # переключаемся и применяем блокировщик/локаль
                    try:
                        self.browser.switch_to.window(new_handle)
                        try:
                            self._inject_map_blocker()
                        except Exception:
                            pass
                        try:
                            self._enforce_russian_language()
                        except Exception:
                            pass
                        self._wait_dom()
                    except Exception as e:
                        print("Error opening next tab:", e)
                    self.tab_map[new_handle] = next_rest

                # после закрытия и возможного открытия следующего — переключимся на существующую вкладку, если есть
                if self.browser.window_handles:
                    try:
                        self.browser.switch_to.window(self.browser.window_handles[-1])
                    except Exception:
                        pass

        return all_reviews

    # ---------------- CLOSE ----------------

    def close(self):
        if self.browser:
            self.browser.quit()
