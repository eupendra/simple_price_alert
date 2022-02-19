import json
import os
import smtplib
from datetime import datetime
from email.message import EmailMessage

import pandas as pd
import requests
from bs4 import BeautifulSoup
from price_parser import Price

CSV_FILE = 'prices.csv'
SAVE_TO_CSV = True
SEND_MAIL = True
products_to_monitor = [{
    'product': 'A light in the Attic',
    'url': 'https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html',
    'alert_price': 100
}, {
    'product': 'Tipping the Velvet',
    'url': 'https://books.toscrape.com/catalogue/tipping-the-velvet_999/index.html',
    'alert_price': 100
},
]


def get_response(url):
    response = requests.get(url)
    return response.text


def get_price(html):
    soup = BeautifulSoup(html, 'lxml')
    el = soup.select_one('.price_color')
    if not el: return None
    price = Price.fromstring(el.get_text())
    if not price: return None
    return price.amount_float


def process_products(products: list):
    updated_products = []
    for product in products:
        url = product['url']
        html = get_response(url)
        product['price'] = get_price(html)
        product['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        product['alert'] = product['price'] < product['alert_price']
        updated_products.append(product)
    return updated_products


def save_to_csv(data: list[dict]):
    import csv
    file_exists = os.path.isfile(CSV_FILE)
    with open(CSV_FILE, 'a') as f:
        columns = data[0].keys()
        writer = csv.DictWriter(f, fieldnames=columns)
        if not file_exists:
            writer.writeheader()
        writer.writerows(data)


def get_mail_subject_body(products):
    df = pd.DataFrame(products)
    with open('mail.html') as f:
        html_string = f.read()
    subject, body = None, None
    if df['alert'].any():
        subject = '[ALERT] Products Available'
        table_html = df[df['alert']].to_html(index=False)
        body = html_string.replace('{data}', table_html)

    return subject, body


def send_mail(products):
    try:
        subject, body = get_mail_subject_body(products)
        if not (body and subject):
            print('No mail to send. Exiting...')
            return
        msg = EmailMessage()
        with open('config.json') as f:
            config = json.loads(f.read())

        mail_user = os.environ.get('MAIL_USER', config['mail_user'])
        mail_pass = os.environ.get('MAIL_PASS', config['mail_pass'])
        mail_to = os.environ.get('MAIL_TO', config['mail_to'])
        if not all([mail_pass, mail_user, mail_to]):
            raise ValueError('Mail Not Configured: check environment variables and config.json.')
        msg['Subject'] = subject
        msg['From'] = mail_user
        msg['To'] = mail_to

        msg.set_content(body, subtype='html')

        with smtplib.SMTP('smtp.gmail.com', 587) as smtp:
            smtp.starttls()
            smtp.login(mail_user, mail_pass)
            smtp.send_message(msg)

    except Exception as e:
        print('Error in Sending Mail\n', e)
    else:
        print('Mail Sent!')


def main():
    products = process_products(products_to_monitor)
    if SAVE_TO_CSV:
        save_to_csv(products)
    if SEND_MAIL:
        send_mail(products)


if __name__ == '__main__':
    main()
