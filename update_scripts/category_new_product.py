# Этот скрипт создаёт необходимые категории и товары на сервере путём отправки их на https://pospro.kz/add_product_category.php

import requests
import sqlite3
import time
from math import ceil


def fetch_data_from_db():
    db_path = "products.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM products")
    rows = cursor.fetchall()

    categories_dict = {}
    for row in rows:
        cat = row["category"]

        if cat not in categories_dict:
            categories_dict[cat] = []

        categories_dict[cat].append({
            "id": row["id"],
            "brand": row["brand"],
            "code": row["code"],
            "country": row["country"],
            "fullName": row["fullName"],
            "inStock": row["inStock"],
            "model": row["model"],
            "name": row["name"],
            "price": int(round(row["price"])) if row["price"] else 0,
            "priceCurrency": (
                row["priceCurrency"].replace("УЕ ", "").replace(" ВН", "") if row["priceCurrency"] else "KZT"
            ),
            "img": "https://portal.holdingbio.ru" + row["img"] if row["img"] else "",
            "description": row["description"]
        })

    conn.close()

    categories = [
        {"categoryName": cat_name, "products": products}
        for cat_name, products in categories_dict.items()
    ]

    return categories


def chunk_list(data, chunk_size):
    """Разделить список на чанки (части) фиксированного размера."""
    for i in range(0, len(data), chunk_size):
        yield data[i:i + chunk_size]


def send_category_to_server(category, chunk_size=10):
    global response
    url = "https://pospro.kz/add_product_category.php"
    products = category["products"]
    total_chunks = ceil(len(products) / chunk_size)
    chunk_index = 1

    for chunk in chunk_list(products, chunk_size):
        payload = {
            "categories": [{
                "categoryName": category["categoryName"],
                "products": chunk
            }]
        }
        max_retries = 5
        retry_count = 0

        while retry_count < max_retries:
            try:
                response = requests.post(url, json=payload, timeout=30)
                if response.status_code == 200:
                    try:
                        print(f"Порция {chunk_index}/{total_chunks} категории '{category['categoryName']}' успешно отправлена.")
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
            error_message = f"Порция {chunk_index}/{total_chunks} категории: {category['categoryName']}\n"
            error_message += f"Ошибка: {response.text if 'response' in locals() else 'Нет ответа от сервера'}\n\n"
            with open("failed_categories.txt", "a", encoding="utf-8") as file:
                file.write(error_message)
            print(f"Порция {chunk_index}/{total_chunks} категории '{category['categoryName']}' записана в failed_categories.txt из-за ошибок.")

        chunk_index += 1


if __name__ == "__main__":
    categories = fetch_data_from_db()
    for category in categories:
        send_category_to_server(category, chunk_size=10)  # Размер чанка = 10 товаров
        time.sleep(5)  # Задержка между категориями
