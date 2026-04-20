import os
import json
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from playwright.sync_api import sync_playwright

# =====================
# CONFIG
# =====================

DESIGNERS = [
    "Zimmermann",
    "Staud",
    "Self-Portrait",
    "Ulla Johnson",
    "Farm Rio",
    "Ganni",
    "Cult Gaia"
]

# =====================
# GOOGLE SHEETS
# =====================

def connect_sheet():
    creds_json = os.environ['GOOGLE_SHEETS_CREDENTIALS']
    creds_dict = json.loads(creds_json)

    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]

    credentials = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(credentials)

    sheet_id = os.environ['GOOGLE_SHEET_ID']
    sheet = client.open_by_key(sheet_id).sheet1

    return sheet


def cleanup_old_rows(sheet):
    records = sheet.get_all_records()
    cutoff = datetime.now() - timedelta(hours=72)

    rows_to_delete = []

    for i, row in enumerate(records):
        try:
            timestamp = datetime.strptime(row["Timestamp"], "%Y-%m-%d %H:%M:%S")
            if timestamp < cutoff:
                rows_to_delete.append(i + 2)
        except:
            pass

    for row in reversed(rows_to_delete):
        sheet.delete_rows(row)


# =====================
# SCRAPER (PLAYWRIGHT)
# =====================

def scrape_nordstrom_rack():

    items = []

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )

        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )

        page = context.new_page()

        urls = [
            "https://www.nordstromrack.com/c/women/clothing",
            "https://www.nordstromrack.com/c/women/shoes",
            "https://www.nordstromrack.com/c/women/handbags"
        ]

        for base_url in urls:

            for page_num in range(1, 10):

                url = f"{base_url}?page={page_num}"
                print("Visiting:", url)

                try:
                    page.goto(url, timeout=60000)

                    # let JS load
                    page.wait_for_timeout(5000)

                    # scroll to trigger lazy loading
                    page.mouse.wheel(0, 6000)

                    page.wait_for_timeout(3000)

                    html = page.content()
                    soup = BeautifulSoup(html, "html.parser")

                    products = soup.select('[data-testid="product-card"]')

                    print("Products found:", len(products))

                    for product in products:

                        try:
                            brand_el = product.select_one('[data-testid="product-brand"]')
                            if not brand_el:
                                continue

                            brand = brand_el.text.strip()

                            if not any(d.lower() in brand.lower() for d in DESIGNERS):
                                continue

                            name_el = product.select_one('[data-testid="product-title"]')
                            price_el = product.select_one('[data-testid="product-price"]')
                            compare_el = product.select_one('[data-testid="product-compare-at-price"]')

                            if not name_el or not price_el or not compare_el:
                                continue

                            name = name_el.text.strip()

                            price = float(price_el.text.replace("$", "").replace(",", ""))
                            original = float(compare_el.text.replace("$", "").replace(",", ""))

                            discount = (original - price) / original

                            if discount < 0.70:
                                continue

                            image_el = product.select_one("img")
                            link_el = product.select_one("a")

                            if not image_el or not link_el:
                                continue

                            image = image_el.get("src", "")
                            link = "https://www.nordstromrack.com" + link_el.get("href", "")

                            items.append({
                                "brand": brand,
                                "name": name,
                                "price": price,
                                "original": original,
                                "discount": f"{round(discount * 100)}%",
                                "image": image,
                                "link": link
                            })

                        except Exception as e:
                            print("Item error:", e)

                except Exception as e:
                    print("Page error:", e)

        browser.close()

    return items


# =====================
# MAIN
# =====================

def main():

    sheet = connect_sheet()
    cleanup_old_rows(sheet)

    run_id = datetime.now().strftime("%Y%m%d%H%M")

    items = scrape_nordstrom_rack()

    print("Total items found:", len(items))

    for item in items:

        row = [
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Nordstrom Rack",
            item["brand"],
            item["name"],
            item["original"],
            item["price"],
            item["discount"],
            item["image"],
            item["link"],
            run_id
        ]

        sheet.append_row(row)


if __name__ == "__main__":
    main()
