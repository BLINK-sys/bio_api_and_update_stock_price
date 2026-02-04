import requests

import info


def valute():
    URL = "https://back.halykbank.kz/common/currency-history"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Referer": "https://halykbank.kz/exchange-rates"
    }

    response = requests.get(URL, headers=headers)
    response.raise_for_status()

    data = response.json()
    
    if not data.get("result") or not data.get("data"):
        raise ValueError("Неверный формат ответа от API.")

    # Получаем данные для бизнеса (legalPersons)
    currency_history = data["data"].get("currencyHistory", [])
    if not currency_history:
        raise ValueError("Не найдены данные о курсах валют.")

    # Обрабатываем разные форматы ответа API
    if isinstance(currency_history, list):
        # Если это список, берем первый элемент
        if len(currency_history) == 0:
            raise ValueError("Список currency_history пуст.")
        latest_data = currency_history[0]
    elif isinstance(currency_history, dict):
        # Если это словарь, берем данные по ключу '0' (самые свежие)
        # Если ключа '0' нет, берем первый доступный ключ
        if '0' in currency_history:
            latest_data = currency_history['0']
        else:
            keys = list(currency_history.keys())
            if keys:
                # Сортируем ключи и берем первый (самый свежий)
                sorted_keys = sorted(keys, key=lambda x: int(x) if x.isdigit() else 0, reverse=True)
                latest_data = currency_history[sorted_keys[0]]
            else:
                raise ValueError("Словарь currency_history пуст.")
    else:
        raise ValueError(f"Неожиданный тип currency_history: {type(currency_history)}")
    legal_persons = latest_data.get("legalPersons", {})
    
    # Сохраняем существующие курсы из info.py (если есть USD и EUR)
    try:
        existing_rates = info.exchange_rates.copy()
    except:
        existing_rates = {}
    
    # Парсим только RUB - курс продажи для бизнеса
    rub_data = legal_persons.get("RUB/KZT")
    if not rub_data:
        raise ValueError("Не найден курс RUB в данных API.")
    
    sell_rate = rub_data.get("sell")
    if sell_rate is None:
        raise ValueError("Не найден курс продажи RUB.")
    
    # Применяем ту же логику, что была в старом коде (добавляем 1%)
    rate_value = round(sell_rate + (sell_rate * 0.01), 2)
    
    # Обновляем только RUB, сохраняя остальные валюты
    exchange_rates_nb = existing_rates.copy()
    exchange_rates_nb["RUB"] = rate_value

    print(exchange_rates_nb)

    # Записываем в info.py
    with open("info.py", "w", encoding="utf-8") as file:
        file.write(f"exchange_rates = {exchange_rates_nb}\n")

    print("Курс RUB Halyk Bank (продажа для бизнеса) сохранен в info.py")
    # Перезагружаем модуль для получения обновленных курсов
    import importlib
    importlib.reload(info)
    return info.exchange_rates


if __name__ == "__main__":
    valute()
