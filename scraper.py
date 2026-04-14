import os
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from playwright.sync_api import sync_playwright

DESIGNERS = [
    "Zimmermann",
    "Staud",
    "Self-Portrait",
    "Ulla Johnson",
    "Farm Rio",
    "Ganni",
    "Cult Gaia"
]

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
                rows_to_delete.append(i+2)
        except:
            pass

    for row in reversed(rows_to_delete):
        sheet.delete_rows(row)


def scrape_nordstrom_rack():

    items = []

    with sync_playwright() as p:

        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

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
                    page.wait_for_timeout(3000)

                    html = page.content()

                    soup = BeautifulSoup(html, "html.parser")

                    products = soup.select('[data-testid="product-card"]')

                    print("Products found:", len(products))

                    for product in products:

                        try:

                            brand = product.select_one('[data-testid="product-brand"]')

                            if not brand:
                                continue

                            brand = brand.text.strip()

                            if not any(d.lower() in brand.lower() for d in DESIGNERS):
                                continue

                            name = product.select_one('[data-testid="product-title"]').text.strip()

                            price = product.select_one('[data-testid="product-price"]')
                            compare = product.select_one('[data-testid="product-compare-at-price"]')

                            if not price or not compare:
                                continue

                            price = float(price.text.replace("$","").replace(",",""))
                            original = float(compare.text.replace("$","").replace(",",""))

                            discount = (original - price) / original

                            if discount < 0.70:
                                continue

                            image = product.select_one("img")["src"]
                            link = product.select_one("a")["href"]

                            items.append({
                                "brand": brand,
                                "name": name,
                                "price": price,
                                "original": original,
                                "discount": f"{round(discount*100)}%",
                                "image": image,
                                "link": "https://www.nordstromrack.com" + link
                            })

                        except Exception as e:
                            print("Item error:", e)

                except Exception as e:
                    print("Page error:", e)

        browser.close()

    return items

def main():

    sheet = connect_sheet()
    cleanup_old_rows(sheet)

    run_id = datetime.now().strftime("%Y%m%d%H%M")

    items = scrape_nordstrom_rack()

    for item in items:

        row = [
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Saks",
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
