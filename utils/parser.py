from data.dataclasses import Restaurant
from loader import browser_manager
import asyncio

semaphore = asyncio.Semaphore(2)  # максимум 2 страницы одновременно


async def parse(restaurant: Restaurant):
    page = await browser_manager.new_page()
    try:
        await page.goto(restaurant.link, wait_until="networkidle", timeout=30000)

        title = await page.title()
        print(title)

    finally:
        await page.close()


async def safe_parse(restaurant: Restaurant):
    async with semaphore:
        await parse(restaurant)
