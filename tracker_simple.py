import csv
import json
import os
import smtplib
from email.message import EmailMessage
from h11 import PRODUCT_ID

import pandas as pd
import requests
from bs4 import BeautifulSoup
from price_parser import Price

CSV_FILE = "prices.csv"
SAVE_TO_CSV = True
SEND_MAIL = True
PRODUCT_URL_CSV = "products.csv"


def get_response(url):
    response = requests.get(url)
    return response.text


def get_price(html):
    soup = BeautifulSoup(html, "lxml")
    el = soup.select_one(".price_color")
    price = Price.fromstring(el.text)
    return price.amount_float


def process_products(products):
    updated_products = []
    for product in products:
        html = get_response(product["url"])
        product["price"] = get_price(html)
        product["alert"] = product["price"] < product["alert_price"]
        updated_products.append(product)
    return updated_products


def save_to_csv(data: list[dict]):
    with open(CSV_FILE, "w") as f:
        columns = data[0].keys()
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(data)


def get_mail_subject_body(products: list[dict]) -> tuple[str, str]:
    df = pd.DataFrame(products)
    with open("mail.html") as f:
        html_string = f.read()
    subject, body = None, None
    if df["alert"].any():
        subject = "[ALERT] Products Available"
        table_html = df[df["alert"]].to_html(index=False)
        body = html_string.replace("{data}", table_html)

    return subject, body


def send_mail(products):
    try:
        subject, body = get_mail_subject_body(products)
        if not (body and subject):
            print("No mail to send. Exiting...")
            return
        msg = EmailMessage()
        with open("config.json") as f:
            config = json.loads(f.read())

        mail_user = os.environ.get("MAIL_USER", config["mail_user"])
        mail_pass = os.environ.get("MAIL_PASS", config["mail_pass"])
        mail_to = os.environ.get("MAIL_TO", config["mail_to"])
        if not all([mail_pass, mail_user, mail_to]):
            raise ValueError(
                "Mail Not Configured: check environment variables and config.json."
            )
        msg["Subject"] = subject
        msg["From"] = mail_user
        msg["To"] = mail_to

        msg.set_content(body, subtype="html")

        with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
            smtp.starttls()
            smtp.login(mail_user, mail_pass)
            smtp.send_message(msg)

    except Exception as e:
        print("Error in Sending Mail\n", e)
    else:
        print("Mail Sent!")

def get_urls(csv_file):
    df = pd.read_csv(csv_file)
    return df.to_dict('records')
    
def main():
    products_to_track = get_urls(PRODUCT_URL_CSV)
    products_updated = process_products(products_to_track)
    if SAVE_TO_CSV:
        save_to_csv(products_updated)
    if SEND_MAIL:
        send_mail(products_updated)


if __name__ == "__main__":
    main()
