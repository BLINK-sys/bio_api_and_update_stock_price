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

    # Извлекаем артикул, остатки и цену
    cursor.execute("SELECT code, inStock, price FROM products")
    rows = cursor.fetchall()

    stock_data = []
    for row in rows:
        original_price = row["price"] if row["price"] else 0
        rounded_price = round_price_to_hundred(original_price)
        
        stock_data.append({
            "code": row["code"],
            "inStock": row["inStock"],
            "price": rounded_price  # Округляем цену до 100 вверх
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
                        print(f"Порция {chunk_index}/{total_chunks} успешно отправлена.")
                        print("Статус-код:", response.status_code)
                        print("Ответ сервера:", response.json())
                    except Exception as e:
                        print("Ошибка обработки JSON:", str(e))
                        print("Текст ответа:", response.text)
                    break  # Успешно, переходим к следующему чанку
                else:
                    print(f"Ошибка {response.status_code}. Текст ответа сервера:")
                    print(response.text)
                    retry_count += 1
                    print(f"Попытка {retry_count} через 30 секунд...")
                    time.sleep(30)
            except requests.exceptions.Timeout:
                print(f"Таймаут. Попытка {retry_count + 1} через 30 секунд...")
                retry_count += 1
                time.sleep(30)
            except requests.exceptions.ConnectionError as e:
                print(f"Ошибка соединения: {str(e)}. Попытка {retry_count + 1} через 30 секунд...")
                retry_count += 1
                time.sleep(30)
            except requests.exceptions.RequestException as e:
                print(f"Общая ошибка: {str(e)}. Попытка {retry_count + 1} через 30 секунд...")
                retry_count += 1
                time.sleep(30)

        if retry_count == max_retries:
            error_message = f"Порция {chunk_index}/{total_chunks} не отправлена.\n"
            error_message += f"Ошибка: {response.text if 'response' in locals() else 'Нет ответа от сервера'}\n\n"
            with open("failed_stocks.txt", "a", encoding="utf-8") as file:
                file.write(error_message)
            print(f"Порция {chunk_index}/{total_chunks} записана в failed_stocks.txt из-за ошибок.")

        chunk_index += 1


if __name__ == "__main__":
    stock_data = fetch_stock_data_with_price_from_db()
    send_stock_with_price_to_server(stock_data, chunk_size=10)  # Размер чанка = 10 записей
    time.sleep(5)  # Задержка между отправками чанков
