import os
import json
import re
import statistics
import requests
from datetime import datetime, timedelta
from urllib.parse import quote_plus
from bs4 import BeautifulSoup
import gspread
from oauth2client.service_account import ServiceAccountCredentials

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
# TEXT UTILS
# =====================

def normalize(text):
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def similarity(a, b):
    a_words = set(normalize(a).split())
    b_words = set(normalize(b).split())

    if not a_words or not b_words:
        return 0

    return len(a_words & b_words) / len(a_words | b_words)


def extract_style_name(title, brand):
    title = title.replace(brand, "").strip()
    words = re.findall(r"[A-Za-z]+", title)

    candidates = [w for w in words if len(w) >= 4]

    return candidates[0] if candidates else ""

# =====================
# EBAY FUNCTIONS
# =====================

def get_real_titles_from_ebay(brand):

    url = f"https://www.ebay.com/sch/i.html?_nkw={quote_plus(brand + ' dress')}&LH_Sold=1&LH_Complete=1"

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    titles = []

    try:
        r = requests.get(url, headers=headers, timeout=20)
        soup = BeautifulSoup(r.text, "html.parser")

        items = soup.select(".s-item__title")

        for item in items:

            title = item.text.strip()

            if "Shop on eBay" in title or len(title) < 10:
                continue

            if brand.lower() not in title.lower():
                continue

            titles.append(title)

            if len(titles) >= 10:
                break

    except Exception as e:
        print("Title fetch error:", e)

    return titles


def get_ebay_sold_comps(brand, title):

    style = extract_style_name(title, brand)

    if style:
        query = f"{brand} {style} dress"
    else:
        query = f"{brand} dress"

    search_url = f"https://www.ebay.com/sch/i.html?_nkw={quote_plus(query)}&LH_Sold=1&LH_Complete=1"

    print("Searching eBay:", query)

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    prices = []
    matches = 0

    try:
        r = requests.get(search_url, headers=headers, timeout=20)
        soup = BeautifulSoup(r.text, "html.parser")

        items = soup.select(".s-item")

        for item in items[:30]:

            try:
                title_el = item.select_one(".s-item__title")
                price_el = item.select_one(".s-item__price")

                if not title_el or not price_el:
                    continue

                ebay_title = title_el.text.strip()
                price_text = price_el.text

                price_val = re.findall(r"\d+(?:\.\d+)?", price_text)
                if not price_val:
                    continue

                price = float(price_val[0])

                sim = similarity(title, ebay_title)

                if sim < 0.4:
                    continue

                prices.append(price)
                matches += 1

            except:
                continue

    except Exception as e:
        print("eBay error:", e)

    if len(prices) >= 3:
        median_price = round(statistics.median(prices), 2)

        if matches >= 8:
            confidence = "High"
        elif matches >= 4:
            confidence = "Medium"
        else:
            confidence = "Low"

        return median_price, matches, confidence

    return None, 0, "Low"

# =====================
# MAIN
# =====================

def main():

    sheet = connect_sheet()
    cleanup_old_rows(sheet)

    run_id = datetime.now().strftime("%Y%m%d%H%M")

    for brand in DESIGNERS:

        print(f"\nProcessing brand: {brand}")

        titles = get_real_titles_from_ebay(brand)

        print(f"Found {len(titles)} real titles")

        for title in titles:

            ebay_price, comps, confidence = get_ebay_sold_comps(brand, title)

            row = [
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "eBay",
                brand,
                title,
                "",
                "",
                "",
                ebay_price if ebay_price else "",
                comps,
                confidence,
                "",
                f"https://www.ebay.com/sch/i.html?_nkw={quote_plus(title)}&LH_Sold=1",
                run_id
            ]

            sheet.append_row(row)


if __name__ == "__main__":
    main()
