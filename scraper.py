import os
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials

DESIGNERS = [
    "Zimmermann",
    "Staud",
    "Self-Portrait",`
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


def scrape_saks():

    urls = [
    "https://www.saksfifthavenue.com/c/women-s-apparel/dresses",
    "https://www.saksfifthavenue.com/c/women-s-apparel/tops",
    "https://www.saksfifthavenue.com/c/women-s-apparel/sweaters",
    "https://www.saksfifthavenue.com/c/women-s-apparel/jackets-coats",
    "https://www.saksfifthavenue.com/c/women-s-apparel/skirts",
    "https://www.saksfifthavenue.com/c/women-s-apparel/pants",
    "https://www.saksfifthavenue.com/c/women-shoes",
    "https://www.saksfifthavenue.com/c/handbags"
]

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    for url in urls:

    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")

    items = []

    products = soup.select(".product-tile")

    for product in products:

        try:
            brand = product.select_one(".product-brand").text.strip()

            if not any(d.lower() in brand.lower() for d in DESIGNERS):
                continue

            name = product.select_one(".product-name").text.strip()

            price = product.select_one(".sale-price").text.replace("$","").strip()
            original = product.select_one(".original-price").text.replace("$","").strip()

            price = float(price)
            original = float(original)

            discount = (original - price) / original

            if discount < 0.70:
                continue

            image = product.select_one("img").get("src")

            link = product.select_one("a").get("href")

            items.append({
                "brand": brand,
                "name": name,
                "price": price,
                "original": original,
                "discount": f"{round(discount*100)}%",
                "image": image,
                "link": "https://www.saksfifthavenue.com" + link
            })

        except:
            continue

    return items


def main():

    sheet = connect_sheet()
    cleanup_old_rows(sheet)

    run_id = datetime.now().strftime("%Y%m%d%H%M")

    items = scrape_saks()

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
