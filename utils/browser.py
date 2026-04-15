from playwright.async_api import async_playwright


class BrowserManager:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None

    async def start(self):
        self.playwright = await async_playwright().start()

        self.browser = await self.playwright.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-extensions"
            ]
        )

        self.context = await self.browser.new_context(
            user_agent="Mozilla/5.0 ...",
            viewport={"width": 1280, "height": 800}
        )

        # блокировка тяжёлых ресурсов
        await self.context.route("**/*", lambda route:
            route.abort() if route.request.resource_type in ["image", "media", "font"]
            else route.continue_()
        )

    async def new_page(self):
        if not self.context:
            raise RuntimeError("BrowserManager не запущен")

        return await self.context.new_page()

    async def close(self):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
