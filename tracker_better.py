from cmath import log
import json
import logging
import os
import smtplib
from datetime import datetime
from email.message import EmailMessage

import numpy as np
import pandas as pd
import requests
import scraper_helper as sh
from bs4 import BeautifulSoup
from price_parser import Price

# Config
CSV_FILE = 'prices.csv'
SAVE_TO_CSV = True
SEND_MAIL = True
INPUT_FILE = 'products.csv'

# Logging
logger = logging.getLogger(__name__)
FORMAT = "[%(filename)s:%(lineno)s - %(funcName)s] %(message)s"
logging.basicConfig(format=FORMAT, filename='tracker.log')
logger.setLevel(logging.DEBUG)


def get_response(url):
    response = requests.get(url, headers=sh.headers())
    if response.status_code != 200:
        logger.error(f'Error in getting response for url: {url}')
        return None
    return response.text


def get_price(html):
    soup = BeautifulSoup(html, 'lxml')
    el = soup.select_one('.price_color')
    if not el: return None
    price = Price.fromstring(el.get_text())
    if not price:
        return np.NAN
    return price.amount_float


def process_products(products: list):
    updated_products = []
    for product in products:
        url = product['url']
        html = get_response(url)
        if not html:
            logger.warning(f'No response for url: {url}')
            continue
        product['price'] = get_price(html)
        product['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        product['alert'] = product['price'] < product['alert_price'] if product['price'] else False
        updated_products.append(product)
        logger.debug(product)
    logger.info(f'Updated products: {len(updated_products)}')
    return updated_products


def save_to_csv(data: list[dict]):
    df = pd.DataFrame(data)
    file_exists = os.path.isfile(CSV_FILE)
    if file_exists:
        df.to_csv(mode="a", header=False, index=False, encoding="utf-8")
    else:
        df.to_csv(index=False, encoding="utf-8")
    logger.info(f'Saved to CSV file: {CSV_FILE}')


def get_mail_subject_body(products):
    df = pd.DataFrame(products)
    with open('mail.html') as f:
        html_string = f.read()
    subject, body = None, None
    if df['alert'].any():
        subject = '[ALERT] Products Available'
        table_html = df[df['alert']].to_html(index=False)
        body = html_string.replace('{data}', table_html)
    logger.info(f'Mail Subject: {subject}')
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
        logger.error(f'Error in sending mail: {e}', exc_info=True, stack_info=True)
        print('Error in Sending Mail\n', e)
    else:
        logger.info('Mail sent successfully')
        print('Mail Sent!')


def get_products_to_track():
    df = pd.read_csv(INPUT_FILE)
    logger.info(f'Products to track: {len(df)}')
    logger.debug(f'Products to track: \n{df.to_string()}')
    return df.to_dict('records')


def main():
    products_to_track = get_products_to_track()
    if not products_to_track:
        logger.error('No products to track')
        exit(-1)
    products = process_products(products_to_track)
    if SAVE_TO_CSV:
        save_to_csv(products)
    if SEND_MAIL:
        send_mail(products)


if __name__ == '__main__':
    main()
