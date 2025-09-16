# Этот скрипт обновляет необходимые данные (ищет товар по Code,  меняет в нём price и  stock) на сервере ,
# путём отправки их на https://pospro.kz/data_stocks_bio.php
# путём отправки их на https://pospro.kz/dublicate_delete.php
# 
import requests
import sqlite3
import time
from math import ceil


def round_price_to_hundred(price):
    """
    Округляет цену до 100 вверх
    Например: 13480 -> 13500, 13500 -> 13500, 13501 -> 13600
    """
    if price <= 0:
        return 0
    return ceil(price / 100) * 100


def fetch_stock_data_with_price_from_db():
    db_path = "products.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Извлекаем артикул, остатки, цену и описание
    cursor.execute("SELECT code, inStock, price, description FROM products")
    rows = cursor.fetchall()

    stock_data = []
    for row in rows:
        original_price = row["price"] if row["price"] else 0
        rounded_price = round_price_to_hundred(original_price)
        
        # Формируем описание с добавлением "(B)" в конце
        description = row["description"] if row["description"] else ""
        if description:
            description = description + "\n(B)"
        else:
            description = "(B)"
        
        stock_data.append({
            "code": row["code"],
            "inStock": row["inStock"],
            "price": rounded_price,  # Округляем цену до 100 вверх
            "description": description
        })

    conn.close()
    return stock_data


def chunk_list(data, chunk_size):
    """Разделить список на чанки (части) фиксированного размера."""
    for i in range(0, len(data), chunk_size):
        yield data[i:i + chunk_size]


def send_stock_with_price_to_server(stock_data, chunk_size=10):
    global response
    url = "https://pospro.kz/dublicate_delete.php"
    total_chunks = ceil(len(stock_data) / chunk_size)
    chunk_index = 1

    for chunk in chunk_list(stock_data, chunk_size):
        payload = {"stocks": chunk}
        max_retries = 5
        retry_count = 0

        while retry_count < max_retries:
            try:
                response = requests.post(url, json=payload, timeout=30)
                if response.status_code == 200:
                    try:
                        log.info(f"Порция {chunk_index}/{total_chunks} успешно отправлена.")
                        log.info(f"Статус-код: {response.status_code}")
                        log.info(f"Ответ сервера: {response.json()}")
                    except Exception as e:
                        print("Ошибка обработки JSON:", str(e))
                        print("Текст ответа:", response.text)
                    break  # Успешно, переходим к следующему чанку
                else:
                    log.error(f"Ошибка {response.status_code}. Текст ответа сервера: {response.text}")
                    retry_count += 1
                    log.info(f"Попытка {retry_count} через 30 секунд...")
                    time.sleep(30)
            except requests.exceptions.Timeout:
                log.error(f"Таймаут. Попытка {retry_count + 1} через 30 секунд...")
                retry_count += 1
                time.sleep(30)
            except requests.exceptions.ConnectionError as e:
                log.error(f"Ошибка соединения: {str(e)}. Попытка {retry_count + 1} через 30 секунд...")
                retry_count += 1
                time.sleep(30)
            except requests.exceptions.RequestException as e:
                log.error(f"Общая ошибка: {str(e)}. Попытка {retry_count + 1} через 30 секунд...")
                retry_count += 1
                time.sleep(30)

        if retry_count == max_retries:
            error_message = f"Порция {chunk_index}/{total_chunks} не отправлена.\n"
            error_message += f"Ошибка: {response.text if 'response' in locals() else 'Нет ответа от сервера'}\n\n"
            with open("failed_stocks.txt", "a", encoding="utf-8") as file:
                file.write(error_message)
            log.error(f"Порция {chunk_index}/{total_chunks} записана в failed_stocks.txt из-за ошибок.")

        chunk_index += 1


if __name__ == "__main__":
    import sys
    import os
    import logging
    from datetime import datetime
    
    # Настройка переменных окружения для Render
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    os.environ.setdefault("PYTHONIOENCODING", "UTF-8")
    
    # Настройка логирования для Render
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )
    log = logging.getLogger("update_stocks")
    
    log.info("🔄 НАЧАЛО ОБНОВЛЕНИЯ ОСТАТКОВ И ЦЕН")
    
    stock_data = fetch_stock_data_with_price_from_db()
    log.info(f"📊 Получено {len(stock_data)} товаров для обновления")
    
    send_stock_with_price_to_server(stock_data, chunk_size=10)  # Размер чанка = 10 записей
    
    log.info("✅ ОБНОВЛЕНИЕ ОСТАТКОВ И ЦЕН ЗАВЕРШЕНО")
    time.sleep(5)  # Задержка между отправками чанков
