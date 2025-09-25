import requests
from bs4 import BeautifulSoup
import re

def valute_bio():
    """
    Парсит курсы валют с сайта BIO (EUR/USD к рублю)
    Возвращает курсы BIO для конвертации в рубли
    """
    URL = "https://portal.holdingbio.ru/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    try:
        response = requests.get(URL, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Ищем курсы валют на странице
        bio_rates = {}
        
        # Поиск по различным паттернам
        patterns = [
            r'YE\s*EUR.*?(\d+,\d+)\s*P',
            r'EUR.*?(\d+,\d+)\s*P',
            r'(\d+,\d+)\s*P.*?EUR'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, soup.get_text(), re.IGNORECASE | re.DOTALL)
            if matches:
                try:
                    rate_str = matches[0].replace(',', '.')
                    bio_rates['EUR'] = float(rate_str)
                    print(f"Найден курс EUR: {bio_rates['EUR']}")
                    break
                except ValueError:
                    continue
        
        # Поиск USD курса
        usd_patterns = [
            r'YE\s*USD.*?(\d+,\d+)\s*P',
            r'USD.*?(\d+,\d+)\s*P',
            r'(\d+,\d+)\s*P.*?USD'
        ]
        
        for pattern in usd_patterns:
            matches = re.findall(pattern, soup.get_text(), re.IGNORECASE | re.DOTALL)
            if matches:
                try:
                    rate_str = matches[0].replace(',', '.')
                    bio_rates['USD'] = float(rate_str)
                    print(f"Найден курс USD: {bio_rates['USD']}")
                    break
                except ValueError:
                    continue
        
        # Если не нашли, используем значения по умолчанию
        if not bio_rates:
            print("⚠️ Курсы BIO не найдены на странице, используем значения по умолчанию")
            bio_rates = {'EUR': 109.0, 'USD': 93.0}
        
        print(f"Итоговые курсы BIO: {bio_rates}")
        return bio_rates
        
    except Exception as e:
        print(f"❌ Ошибка при парсинге курсов BIO: {e}")
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