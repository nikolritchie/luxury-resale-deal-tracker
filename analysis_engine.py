"""
This project is transitioning from exploratory data collection methods
to structured product feeds and affiliate integrations for scalability.
"""

import os
import json
import re
import statistics
import requests
import xml.etree.ElementTree as ET
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
    with open("credentials.json") as f:
    creds_dict = json.load(f)

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
# EBAY RSS (WORKS!)
# =====================

def get_real_titles_from_ebay(brand):

    url = f"https://www.ebay.com/sch/i.html?_nkw={quote_plus(brand + ' dress')}&LH_Sold=1&LH_Complete=1&_rss=1"

    titles = []

    try:
        r = requests.get(url, timeout=20)

        root = ET.fromstring(r.content)

        for item in root.findall(".//item"):

            title = item.find("title").text

            if not title:
                continue

            if brand.lower() not in title.lower():
                continue

            if len(title) < 15:
                continue

            titles.append(title)

            if len(titles) >= 10:
                break

    except Exception as e:
        print("RSS error:", e)

    return titles


def get_ebay_sold_comps(brand, title):

    style = extract_style_name(title, brand)

    if style:
        query = f"{brand} {style} dress"
    else:
        query = f"{brand} dress"

    url = f"https://www.ebay.com/sch/i.html?_nkw={quote_plus(query)}&LH_Sold=1&LH_Complete=1&_rss=1"

    prices = []

    try:
        r = requests.get(url, timeout=20)
        root = ET.fromstring(r.content)

        for item in root.findall(".//item"):

            title_el = item.find("title")
            price_el = item.find("description")

            if title_el is None or price_el is None:
                continue

            ebay_title = title_el.text
            desc = price_el.text

            # extract price
            price_match = re.findall(r"\$\d+(?:\.\d+)?", desc)
            if not price_match:
                continue

            price = float(price_match[0].replace("$", ""))

            sim = similarity(title, ebay_title)

            if sim < 0.4:
                continue

            prices.append(price)

    except Exception as e:
        print("Comp error:", e)

    if len(prices) >= 3:
        median_price = round(statistics.median(prices), 2)

        confidence = "High" if len(prices) >= 8 else "Medium"

        return median_price, len(prices), confidence

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

        print(f"Found {len(titles)} titles")

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
                "",
                run_id
            ]

            sheet.append_row(row)


if __name__ == "__main__":
    main()
