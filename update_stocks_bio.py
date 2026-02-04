# Этот скрипт обновляет необходимые данные (ищет товар по Code,  меняет в нём price и  stock) на сервере ,
# путём отправки их на https://pospro.kz/data_stocks_bio.php
# путём отправки их на https://pospro.kz/dublicate_delete.php
# 
import requests
import sqlite3
import time
from math import ceil
import json
import os
import re


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
    
    # Проверяем существование базы данных
    if not os.path.exists(db_path):
        print("ОШИБКА: База данных products.db не найдена!")
        print("Сначала запустите bio_api.py для создания базы данных")
        return []
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Проверяем существование таблицы
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='products'")
    if not cursor.fetchone():
        print("ОШИБКА: Таблица products не найдена в базе данных!")
        print("Сначала запустите bio_api.py для создания таблиц")
        conn.close()
        return []

    # Извлекаем артикул, остатки, цену, описание и название товара
    cursor.execute("SELECT code, inStock, price, description, name FROM products")
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
            "name": row["name"],  # Добавляем имя товара для удаления дубликатов по имени на стороне Bitrix
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


def fetch_products_by_codes(product_codes):
    """
    Извлекает данные товаров по их артикулам из базы данных
    """
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


def create_products_on_server(product_codes):
    """
    Создает товары на сервере
    """
    if not product_codes:
        print("Нет товаров для создания")
        return True
    
    print(f"Создаем {len(product_codes)} товаров на сервере...")
    
    # Получаем данные товаров из базы
    products_data = fetch_products_by_codes(product_codes)
    if not products_data:
        print("ОШИБКА: Товары не найдены в базе данных")
        return False
    
    # Группируем по категориям
    categories_dict = group_products_by_category(products_data)
    
    success_count = 0
    total_count = len(products_data)
    
    for category_name, products in categories_dict.items():
        print(f"Создаем товары в категории: {category_name}")
        
        # Теперь сервер правильно обрабатывает существующие разделы
        
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
                        print(f"Создано {len(chunk)} товаров в категории '{category_name}'")
                        # Парсим ответ для проверки реального результата
                        try:
                            response_data = response.json()
                            print(f"Ответ сервера при создании: {response_data}")
                            
                            # Проверяем, есть ли ошибки в ответе
                            if isinstance(response_data, list):
                                has_errors = any(item.get('status') == 'error' for item in response_data)
                                if has_errors:
                                    print(f"ВНИМАНИЕ: Есть ошибки при создании товаров в категории '{category_name}'")
                                    # Не считаем товары успешно созданными, если есть ошибки
                                    break
                                else:
                                    success_count += len(chunk)
                            else:
                                success_count += len(chunk)
                        except:
                            print(f"Сырой ответ сервера: {response.text}")
                            success_count += len(chunk)
                        break
                    else:
                        print(f"ОШИБКА {response.status_code} при создании товаров в категории '{category_name}'")
                        print(f"Ответ сервера: {response.text}")
                        retry_count += 1
                        if retry_count < max_retries:
                            time.sleep(10)
                except Exception as e:
                    print(f"ОШИБКА при создании товаров: {e}")
                    retry_count += 1
                    if retry_count < max_retries:
                        time.sleep(10)
            
            if retry_count == max_retries:
                print(f"ОШИБКА: Не удалось создать товары в категории '{category_name}' после {max_retries} попыток")
            
            time.sleep(2)  # Задержка между чанками
    
    print(f"Создание товаров завершено. Успешно: {success_count}/{total_count}")
    return success_count == total_count


def process_chunk_with_immediate_creation(chunk, chunk_index, total_chunks, creation_attempts=0):
    """Обрабатывает один чанк с немедленным созданием недостающих товаров"""
    url = "https://pospro.kz/dublicate_delete.php"
    payload = {"stocks": chunk}
    max_retries = 5
    retry_count = 0
    response = None

    while retry_count < max_retries:
        try:
            print(f"Отправляем чанк {chunk_index}/{total_chunks} на сервер...")
            response = requests.post(url, json=payload, timeout=30)
            if response.status_code == 200:
                print(f"Чанк {chunk_index}/{total_chunks} успешно отправлен")
                
                # Парсим ответ для проверки ошибок "товар не найден"
                try:
                    response_data = response.json()
                    print(f"Ответ сервера: {response_data}")
                    
                    failed_products = []
                    if isinstance(response_data, list):
                        for item in response_data:
                            if item.get('status') == 'error' and 'не найден' in item.get('message', ''):
                                # Товар не найден - извлекаем код из сообщения
                                message = item.get('message', '')
                                code_match = re.search(r"артикулом '([^']+)'", message)
                                if code_match:
                                    code = code_match.group(1)
                                    failed_products.append(code)
                                    print(f"Товар с кодом {code} не найден на сервере")
                            elif item.get('status') == 'success':
                                print(f"Товар {item.get('code', 'N/A')} успешно обновлен")
                    
                    # Если есть товары, которые не найдены, создаем их немедленно
                    if failed_products:
                        print(f"В чанке {chunk_index} найдено {len(failed_products)} товаров, которых нет на сервере")
                        print(f"Коды товаров для создания: {failed_products}")
                        print("Создаем недостающие товары немедленно...")
                        
                        # Создаем товары на сервере
                        creation_success = create_products_on_server(failed_products)
                        
                        if creation_success:
                            # Записываем созданные товары в файл
                            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                            with open("created_products.txt", "a", encoding="utf-8") as file:
                                file.write(f"\n=== Создание товаров {timestamp} ===\n")
                                for product_code in failed_products:
                                    # Находим данные товара для записи
                                    product_data = None
                                    for item in chunk:
                                        if item['code'] == product_code:
                                            product_data = item
                                            break
                                    
                                    if product_data:
                                        file.write(f"Код: {product_code}\n")
                                        file.write(f"Название: {product_data.get('name', 'N/A')}\n")
                                        file.write(f"Бренд: {product_data.get('brand', 'N/A')}\n")
                                        file.write(f"Цена: {product_data.get('price', 'N/A')}\n")
                                        file.write(f"Остаток: {product_data.get('inStock', 'N/A')}\n")
                                        file.write(f"Категория: {product_data.get('category', 'N/A')}\n")
                                        file.write("---\n")
                                    else:
                                        file.write(f"Код: {product_code} (данные не найдены)\n")
                                        file.write("---\n")
                                file.write(f"Всего создано товаров: {len(failed_products)}\n\n")
                            
                            print("Товары успешно созданы. Ждем 10 секунд перед повторной попыткой...")
                            time.sleep(10)
                            
                            # Повторяем отправку этого же чанка для обновления созданных товаров
                            retry_chunk_data = []
                            for item in chunk:
                                if item['code'] in failed_products:
                                    retry_chunk_data.append(item)
                            
                            if retry_chunk_data:
                                print(f"Повторно отправляем чанк {chunk_index} для обновления созданных товаров...")
                                return process_chunk_with_immediate_creation(retry_chunk_data, chunk_index, total_chunks, creation_attempts + 1)
                        else:
                            print("ОШИБКА: Не удалось создать некоторые товары")
                    
                    return True  # Чанк успешно обработан
                    
                except (json.JSONDecodeError, KeyError, TypeError) as e:
                    print(f"Ошибка парсинга ответа: {e}")
                    print(f"Сырой ответ: {response.text}")
                    return False
                    
            else:
                print(f"ОШИБКА {response.status_code} при отправке чанка {chunk_index}")
                retry_count += 1
                if retry_count < max_retries:
                    print(f"Повторная попытка {retry_count}/{max_retries} через 30 секунд...")
                    time.sleep(30)
        except requests.exceptions.Timeout:
            print(f"ТАЙМАУТ при отправке чанка {chunk_index}")
            retry_count += 1
            if retry_count < max_retries:
                print(f"Повторная попытка {retry_count}/{max_retries} через 30 секунд...")
                time.sleep(30)
        except requests.exceptions.ConnectionError as e:
            print(f"Ошибка соединения при отправке чанка {chunk_index}: {e}")
            retry_count += 1
            if retry_count < max_retries:
                print(f"Повторная попытка {retry_count}/{max_retries} через 30 секунд...")
                time.sleep(30)
        except requests.exceptions.RequestException as e:
            print(f"ОШИБКА запроса при отправке чанка {chunk_index}: {e}")
            retry_count += 1
            if retry_count < max_retries:
                print(f"Повторная попытка {retry_count}/{max_retries} через 30 секунд...")
                time.sleep(30)
        except KeyboardInterrupt:
            print("\nПрервано пользователем")
            return False
        except Exception as e:
            print(f"НЕОЖИДАННАЯ ОШИБКА при отправке чанка {chunk_index}: {e}")
            retry_count += 1
            if retry_count < max_retries:
                print(f"Повторная попытка {retry_count}/{max_retries} через 30 секунд...")
                time.sleep(30)

    if retry_count == max_retries:
        error_message = f"Порция {chunk_index}/{total_chunks} не отправлена.\n"
        error_message += f"Ошибка: {response.text if response else 'Нет ответа от сервера'}\n\n"
        with open("failed_stocks.txt", "a", encoding="utf-8") as file:
            file.write(error_message)
        return False
    
    return False


def send_stock_with_price_to_server(stock_data, chunk_size=10, max_retries=2, creation_attempts=0):
    """Новая функция с немедленным созданием товаров"""
    total_chunks = ceil(len(stock_data) / chunk_size)
    chunk_index = 1
    
    # Защита от бесконечного цикла
    if creation_attempts >= 2:
        print(f"ПРЕДУПРЕЖДЕНИЕ: Достигнуто максимальное количество попыток создания ({creation_attempts})")
        print("Товары не удается создать или найти на сервере. Прекращаем попытки.")
        return

    for chunk in chunk_list(stock_data, chunk_size):
        # Используем новую функцию для обработки чанка с немедленным созданием
        success = process_chunk_with_immediate_creation(chunk, chunk_index, total_chunks, creation_attempts)
        if not success:
            print(f"Не удалось обработать чанк {chunk_index}")
        chunk_index += 1
    
    print("Все чанки обработаны")


if __name__ == "__main__":
    import sys
    import os
    import logging
    
    # Настройка переменных окружения для Render
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    os.environ.setdefault("PYTHONIOENCODING", "UTF-8")
    
    # Отключаем все логи
    logging.disable(logging.CRITICAL)
    
    print("Запуск скрипта обновления остатков...")
    
    stock_data = fetch_stock_data_with_price_from_db()
    
    if not stock_data:
        print("ОШИБКА: Нет данных для обновления!")
        print("Убедитесь, что база данных products.db существует и содержит данные")
        sys.exit(1)
    
    print(f"Найдено {len(stock_data)} товаров для обновления")
    
    try:
        send_stock_with_price_to_server(stock_data, chunk_size=10)  # Размер чанка = 10 записей
        print("Обновление остатков завершено")
    except KeyboardInterrupt:
        print("\nСкрипт прерван пользователем")
        sys.exit(0)
    except Exception as e:
        print(f"КРИТИЧЕСКАЯ ОШИБКА: {e}")
        sys.exit(1)
    
    time.sleep(5)  # Задержка между отправками чанков
