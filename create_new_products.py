# Этот скрипт создаёт товары на сервере, которых не существует
# путём отправки их на https://pospro.kz/add_product_category.php

import requests
import sqlite3
import time
from math import ceil


def fetch_products_by_codes(product_codes):
    """
    Извлекает данные товаров по их артикулам из базы данных
    """
    print("создаю товар")
    if not product_codes:
        return []
    
    db_path = "products.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Создаем плейсхолдеры для IN запроса
    placeholders = ','.join(['?' for _ in product_codes])
    cursor.execute(f"SELECT * FROM products WHERE code IN ({placeholders})", product_codes)
    rows = cursor.fetchall()

    products_data = []
    for row in rows:
        # Формируем описание с добавлением "(B)" в конце
        description = row["description"] if row["description"] else ""
        if description:
            description = description + "\n(B)"
        else:
            description = "(B)"
        
        products_data.append({
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
            "description": description
        })

    conn.close()
    return products_data


def group_products_by_category(products_data):
    """
    Группирует товары по категориям
    """
    categories_dict = {}
    
    for product in products_data:
        # Получаем категорию товара из базы данных
        db_path = "products.db"
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT category FROM products WHERE code = ?", (product["code"],))
        row = cursor.fetchone()
        category = row["category"] if row else "Без категории"
        conn.close()
        
        if category not in categories_dict:
            categories_dict[category] = []
        
        categories_dict[category].append(product)
    
    return categories_dict


def chunk_list(data, chunk_size):
    """Разделить список на чанки (части) фиксированного размера."""
    for i in range(0, len(data), chunk_size):
        yield data[i:i + chunk_size]


def create_products_on_server(product_codes):
    """
    Создает товары на сервере
    """
    if not product_codes:
        print("Нет товаров для создания")
        return True
    
    print(f"🔄 Создаем {len(product_codes)} товаров на сервере...")
    
    # Получаем данные товаров из базы
    products_data = fetch_products_by_codes(product_codes)
    if not products_data:
        print("❌ Товары не найдены в базе данных")
        return False
    
    # Группируем по категориям
    categories_dict = group_products_by_category(products_data)
    
    success_count = 0
    total_count = len(products_data)
    
    for category_name, products in categories_dict.items():
        print(f"📂 Создаем товары в категории: {category_name}")
        
        # Отправляем товары чанками по 10 штук
        for chunk in chunk_list(products, 10):
            payload = {
                "categories": [{
                    "categoryName": category_name,
                    "products": chunk
                }]
            }
            
            url = "https://pospro.kz/add_product_category.php"
            max_retries = 3
            retry_count = 0
            
            while retry_count < max_retries:
                try:
                    response = requests.post(url, json=payload, timeout=30)
                    if response.status_code == 200:
                        print(f"✅ Создано {len(chunk)} товаров в категории '{category_name}'")
                        success_count += len(chunk)
                        break
                    else:
                        print(f"❌ Ошибка {response.status_code} при создании товаров в категории '{category_name}'")
                        print(f"Ответ сервера: {response.text}")
                        retry_count += 1
                        if retry_count < max_retries:
                            time.sleep(10)
                except Exception as e:
                    print(f"❌ Ошибка при создании товаров: {e}")
                    retry_count += 1
                    if retry_count < max_retries:
                        time.sleep(10)
            
            if retry_count == max_retries:
                print(f"❌ Не удалось создать товары в категории '{category_name}' после {max_retries} попыток")
            
            time.sleep(2)  # Задержка между чанками
    
    print(f"🎉 Создание товаров завершено. Успешно: {success_count}/{total_count}")
    return success_count == total_count


if __name__ == "__main__":
    # Пример использования
    test_codes = ["157687", "9590"]  # Тестовые артикулы
    create_products_on_server(test_codes)
