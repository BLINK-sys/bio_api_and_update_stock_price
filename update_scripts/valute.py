import requests
from bs4 import BeautifulSoup

import info


def valute():
    URL = "https://mig.kz/"
    headers = {"User-Agent": "Mozilla/5.0"}

    response = requests.get(URL, headers=headers)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # Находим блок с курсами НБ
    external_rates_block = soup.find("div", class_="external-rates")
    if not external_rates_block:
        raise ValueError("Блок с классом 'external-rates' не найден на странице.")

    currency_items = external_rates_block.find_all("li")
    if not currency_items:
        raise ValueError("Не найдены теги <li> в блоке 'external-rates'.")

    exchange_rates_nb = {}
    needed_currencies = {"USD", "EUR", "RUB"}  # нужны только эти коды

    for item in currency_items:
        currency_code_tag = item.find("h4")
        currency_rate_tag = item.find("p")

        if not currency_code_tag or not currency_rate_tag:
            continue

        currency_code = currency_code_tag.get_text(strip=True).upper()  # например "USD"
        currency_rate_text = currency_rate_tag.get_text(strip=True)  # например "521.6 тенге"

        # Проверяем, нужна ли нам именно эта валюта
        if currency_code not in needed_currencies:
            continue

        # Извлекаем число (до пробела) и приводим к float
        rate_str = currency_rate_text.split()[0].replace(',', '.')
        try:
            rate_value = float(rate_str)
            rate_value = round(rate_value + (rate_value * 0.01), 2)
        except ValueError:
            continue

        # Записываем только нужные валюты
        exchange_rates_nb[currency_code] = rate_value

    # В результате в exchange_rates_nb будут ТОЛЬКО USD, EUR, RUB (если они на сайте)
    print(exchange_rates_nb)

    # Записываем в info.py
    with open("info.py", "w", encoding="utf-8") as file:
        file.write(f"exchange_rates = {exchange_rates_nb}\n")

    print("Курсы USD, EUR, RUB Национального Банка сохранены в info.py")
    exchange_rates = info.exchange_rates
    return exchange_rates
