import requests

def valute_bio():
    """
    Получает курсы валют с API BIO (EUR/USD к рублю)
    Возвращает курсы BIO для конвертации в рубли
    """
    BASE_URL = "http://api.bioshop.ru:8030"
    AUTH_CREDENTIALS = {
        "login": "dilyara@pospro.kz",
        "password": "qo8qe7ti"
    }
    
    try:
        # Авторизация и получение курсов валют
        url = f"{BASE_URL}/auth"
        headers = {"content-type": "application/json; charset=utf-8"}
        
        response = requests.post(url, headers=headers, json=AUTH_CREDENTIALS, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        # Извлекаем курсы из ответа
        if "rates" not in data:
            raise ValueError("Курсы валют не найдены в ответе API")
        
        rates_array = data["rates"]
        bio_rates = {}
        
        # Сначала ищем специальные курсы "УЕ EUR ВН" и "УЕ USD ВН" (как на сайте)
        # Если их нет, используем обычные EUR и USD
        ue_eur_found = False
        ue_usd_found = False
        
        for rate_item in rates_array:
            currency = rate_item.get("currency", "")
            rate = rate_item.get("rate")
            frequency = rate_item.get("frequency", 1)
            
            if rate is not None:
                # Учитываем кратность (frequency)
                final_rate = rate * frequency
                # Применяем ту же логику, что была в старом коде (добавляем 1%)
                rate_value = round(final_rate + (final_rate * 0.01), 2)
                
                # Приоритет: сначала ищем "УЕ EUR ВН" и "УЕ USD ВН"
                if currency == "УЕ EUR ВН":
                    bio_rates["EUR"] = rate_value
                    ue_eur_found = True
                    print(f"✓ Найден курс УЕ EUR ВН: {bio_rates['EUR']} (rate: {rate}, frequency: {frequency}, +1%: {rate_value})")
                elif currency == "УЕ USD ВН":
                    bio_rates["USD"] = rate_value
                    ue_usd_found = True
                    print(f"✓ Найден курс УЕ USD ВН: {bio_rates['USD']} (rate: {rate}, frequency: {frequency}, +1%: {rate_value})")
        
        # Если не нашли специальные курсы, используем обычные EUR и USD
        if not ue_eur_found or not ue_usd_found:
            for rate_item in rates_array:
                currency = rate_item.get("currency", "").upper()
                rate = rate_item.get("rate")
                frequency = rate_item.get("frequency", 1)
                
                if rate is not None:
                    final_rate = rate * frequency
                    # Применяем ту же логику, что была в старом коде (добавляем 1%)
                    rate_value = round(final_rate + (final_rate * 0.01), 2)
                    
                    if currency == "EUR" and "EUR" not in bio_rates:
                        bio_rates["EUR"] = rate_value
                        print(f"✓ Найден курс EUR: {bio_rates['EUR']} (rate: {rate}, frequency: {frequency}, +1%: {rate_value})")
                    elif currency == "USD" and "USD" not in bio_rates:
                        bio_rates["USD"] = rate_value
                        print(f"✓ Найден курс USD: {bio_rates['USD']} (rate: {rate}, frequency: {frequency}, +1%: {rate_value})")
        
        # Проверяем, что нашли оба курса
        if "EUR" not in bio_rates or "USD" not in bio_rates:
            missing = [c for c in ["EUR", "USD"] if c not in bio_rates]
            print(f"⚠️ Не найдены курсы для валют: {missing}, используем значения по умолчанию")
            if "EUR" not in bio_rates:
                bio_rates["EUR"] = 109.0
            if "USD" not in bio_rates:
                bio_rates["USD"] = 93.0
        
        print(f"Итоговые курсы BIO: {bio_rates}")
        return bio_rates
        
    except Exception as e:
        print(f"❌ Ошибка при получении курсов BIO через API: {e}")
        import traceback
        traceback.print_exc()
        print("Используем значения по умолчанию")
        return {'EUR': 109.0, 'USD': 93.0}

def get_bio_rates():
    """
    Получает курсы BIO и сохраняет их в файл
    """
    rates = valute_bio()
    
    # Сохраняем курсы BIO в отдельный файл
    with open("bio_rates.py", "w", encoding="utf-8") as file:
        file.write(f"bio_rates = {rates}\n")
    
    print("Курсы BIO сохранены в bio_rates.py")
    return rates

if __name__ == "__main__":
    rates = get_bio_rates()
    print(f"Курсы BIO: {rates}")