"""Render the LinkedIn-post mockups to PNG via Playwright."""
import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[2]
MOCKUPS = ROOT / "docs" / "mockups"
OUT = ROOT / "docs" / "images"
OUT.mkdir(parents=True, exist_ok=True)

TARGETS = [
    # (html, png, extra_wait_ms — architecture needs mermaid to finish)
    ("slack_dm.html",     "slack_dm.png",     500),
    ("dashboard.html",    "dashboard.png",    500),
    ("terminal.html",     "terminal.png",     500),
    ("copilot.html",      "copilot.png",      500),
    ("architecture.html", "architecture.png", 2500),
]


async def main() -> None:
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(
            viewport={"width": 1200, "height": 675},
            device_scale_factor=2,  # retina-crisp PNGs
        )
        for src, dst, wait_ms in TARGETS:
            page = await ctx.new_page()
            url = (MOCKUPS / src).as_uri()
            await page.goto(url, wait_until="networkidle")
            await page.wait_for_timeout(wait_ms)
            png_path = OUT / dst
            await page.screenshot(path=str(png_path), full_page=False)
            size = png_path.stat().st_size
            print(f"  {dst:24s}  {size:>9,} bytes")
            await page.close()
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
