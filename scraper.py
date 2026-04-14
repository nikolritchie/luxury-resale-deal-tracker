import os
import json
import requests
import pandas as pd
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


def main():

    sheet = connect_sheet()

    cleanup_old_rows(sheet)

    run_id = datetime.now().strftime("%Y%m%d%H%M")

    # Placeholder test rows (will replace with Saks scraper next)
    sample_data = [
        {
            "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Retailer": "Saks",
            "Brand": "Zimmermann",
            "Item": "Sample Dress",
            "Retail Price": "795",
            "Sale Price": "199",
            "Discount %": "75%",
            "Photo": "",
            "Link": "https://www.saksfifthavenue.com/",
            "Run ID": run_id
        }
    ]

    for item in sample_data:
        sheet.append_row(list(item.values()))


if __name__ == "__main__":
    main()
