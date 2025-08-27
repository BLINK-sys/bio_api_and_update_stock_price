# Этот скрипт обновляет данные одного товара (артикул 9590) на сервере,
# путём отправки на https://pospro.kz/dublicate_delete.php
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


def fetch_single_product_from_db(product_code="9590"):
    db_path = "products.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Извлекаем данные конкретного товара по артикулу
    cursor.execute("SELECT code, inStock, price FROM products WHERE code = ?", (product_code,))
    row = cursor.fetchone()

    if row is None:
        print(f"Товар с артикулом {product_code} не найден в базе данных.")
        conn.close()
        return None

    original_price = row["price"] if row["price"] else 0
    rounded_price = round_price_to_hundred(original_price)
    
    stock_data = [{
        "code": row["code"],
        "inStock": row["inStock"],
        "price": rounded_price  # Округляем цену до 100 вверх
    }]

    conn.close()
    return stock_data


def send_single_product_to_server(stock_data):
    url = "https://pospro.kz/dublicate_delete.php"
    payload = {"stocks": stock_data}
    max_retries = 5
    retry_count = 0

    while retry_count < max_retries:
        try:
            response = requests.post(url, json=payload, timeout=30)
            if response.status_code == 200:
                try:
                    print("Товар успешно отправлен на сервер.")
                    print("Статус-код:", response.status_code)
                    print("Ответ сервера:", response.json())
                    return True
                except Exception as e:
                    print("Ошибка обработки JSON:", str(e))
                    print("Текст ответа:", response.text)
                    return True
            else:
                print(f"Ошибка {response.status_code}. Текст ответа сервера:")
                print(response.text)
                retry_count += 1
                if retry_count < max_retries:
                    print(f"Попытка {retry_count} через 30 секунд...")
                    time.sleep(30)
        except requests.exceptions.Timeout:
            print(f"Таймаут. Попытка {retry_count + 1} через 30 секунд...")
            retry_count += 1
            if retry_count < max_retries:
                time.sleep(30)
        except requests.exceptions.ConnectionError as e:
            print(f"Ошибка соединения: {str(e)}. Попытка {retry_count + 1} через 30 секунд...")
            retry_count += 1
            if retry_count < max_retries:
                time.sleep(30)
        except requests.exceptions.RequestException as e:
            print(f"Общая ошибка: {str(e)}. Попытка {retry_count + 1} через 30 секунд...")
            retry_count += 1
            if retry_count < max_retries:
                time.sleep(30)

    # Если все попытки исчерпаны
    error_message = f"Товар с артикулом 9590 не отправлен.\n"
    error_message += f"Ошибка: {response.text if 'response' in locals() else 'Нет ответа от сервера'}\n\n"
    with open("failed_single_product.txt", "a", encoding="utf-8") as file:
        file.write(error_message)
    print("Ошибка записана в failed_single_product.txt")
    return False


if __name__ == "__main__":
    print("Начинаю обновление товара с артикулом 9590...")
    stock_data = fetch_single_product_from_db("9590")
    
    if stock_data:
        print(f"Найден товар: {stock_data[0]}")
        success = send_single_product_to_server(stock_data)
        if success:
            print("Обновление товара завершено успешно!")
        else:
            print("Обновление товара завершено с ошибками.")
    else:
        print("Товар не найден в базе данных.")

