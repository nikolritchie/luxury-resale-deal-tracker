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


def scrape_saks():

    items = []

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
        "Referer": "https://www.saksfifthavenue.com/",
        "Origin": "https://www.saksfifthavenue.com"
    }

    for start in range(0, 1000, 24):

        url = f"https://www.saksfifthavenue.com/api/product/search?start={start}&sz=24"

        try:
            response = requests.get(url, headers=headers)

            print("Status:", response.status_code)
            print("URL:", url)

            data = response.json()

            for product in data.get("products", []):

                brand = product.get("brand", "")

                if not any(d.lower() in brand.lower() for d in DESIGNERS):
                    continue

                original = product.get("originalPrice", 0)
                sale = product.get("salePrice", 0)

                if not original or not sale:
                    continue

                discount = (original - sale) / original

                if discount < 0.70:
                    continue

                image = product.get("image", "")
                name = product.get("name", "")
                link = "https://www.saksfifthavenue.com" + product.get("url", "")

                items.append({
                    "brand": brand,
                    "name": name,
                    "price": sale,
                    "original": original,
                    "discount": f"{round(discount*100)}%",
                    "image": image,
                    "link": link
                })

        except Exception as e:
            print("Error:", e)
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
