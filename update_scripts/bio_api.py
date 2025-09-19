# Тут идёт выгрузка данных из Bio  по API  и сохранение в базу (с конвертацией цен по формуле)
import math
import sys
import os
import logging

# Настройка переменных окружения для Render
os.environ.setdefault("PYTHONUNBUFFERED", "1")
os.environ.setdefault("PYTHONIOENCODING", "UTF-8")

# Настройка логирования для Render
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True,  # сбросить чужие хэндлеры (например, werkzeug)
)
log = logging.getLogger("bio")

# Принудительно выводим информацию о среде
log.info("=" * 50)
log.info("🔧 ОТЛАДОЧНАЯ ИНФОРМАЦИЯ")
log.info(f"🔧 Python версия: {sys.version}")
log.info(f"🔧 Рабочая директория: {os.getcwd()}")
log.info(f"🔧 PYTHONUNBUFFERED: {os.environ.get('PYTHONUNBUFFERED', 'НЕ УСТАНОВЛЕН')}")
log.info(f"🔧 PYTHONIOENCODING: {os.environ.get('PYTHONIOENCODING', 'НЕ УСТАНОВЛЕН')}")
log.info(f"🔧 TZ: {os.environ.get('TZ', 'НЕ УСТАНОВЛЕН')}")
log.info(f"🔧 RENDER: {os.environ.get('RENDER', 'НЕ УСТАНОВЛЕН')}")
log.info("=" * 50)

import requests
import sqlite3
import json
from flask import Flask, jsonify
import info
import valute
import schedule
import time
import threading
import subprocess
from datetime import datetime

# Логируем загрузку модуля
log.info("📦 Модуль bio_api.py загружен")

app = Flask(__name__)

BASE_URL = "http://api.bioshop.ru:8030"
AUTH_CREDENTIALS = {
    "login": "dilyara@pospro.kz",
    "password": "qo8qe7ti"
}

DB_PATH = "products.db"

# Обновляем курсы валют
valute.valute()
# Перезагружаем модуль info для получения обновленных курсов
import importlib
importlib.reload(info)
log.info(f"💱 Курс валют обновлён: {info.exchange_rates}")


def calculate_delivery_cost(weight_kg, volume_m3):
    """
    Рассчитывает стоимость доставки по весовым категориям
    weight_kg - фактический вес в кг
    volume_m3 - объем в м³
    """
    # Объемный вес = объем * 200
    volumetric_weight = volume_m3 * 200
    
    # Выбираем больший вес для расчета
    delivery_weight = max(weight_kg, volumetric_weight)
    
    if delivery_weight <= 30:
        # До 30 кг: 7500 + 10000 + (26*400) + 4000 = 31,900 тг
        return 31900
    elif delivery_weight <= 300:
        # 30-300 кг: 7500 + (вес-30)*179 + 10000 + (вес-30)*20 + 26*400 + 4000 + (вес-30)*15
        excess_weight = delivery_weight - 30
        return 7500 + (excess_weight * 179) + 10000 + (excess_weight * 20) + 10400 + 4000 + (excess_weight * 15)
    elif delivery_weight <= 1000:
        # 300-1000 кг: сумма трех компонентов
        excess_300 = delivery_weight - 300
        excess_1000 = max(0, delivery_weight - 1000)
        
        # Компонент 1: город+город
        component1 = 7500 + (270 * 179) + (excess_300 * 164) + (excess_1000 * 143)
        
        # Компонент 2: забор склад БИО
        component2 = 10000 + (270 * 20) + (excess_300 * 15) + excess_1000 + 10400
        
        # Компонент 3: доставка по Астане
        component3 = 4000 + (270 * 15) + (excess_300 * 2) + (excess_1000 * 9) + 10400
        
        return component1 + component2 + component3
    else:
        # Свыше 1000 кг - используем формулу для 1000 кг (без рекурсии)
        excess_300 = 700  # 1000 - 300
        excess_1000 = 0   # 1000 - 1000 = 0
        
        # Компонент 1: город+город
        component1 = 7500 + (270 * 179) + (excess_300 * 164) + (excess_1000 * 143)
        
        # Компонент 2: забор склад БИО
        component2 = 10000 + (270 * 20) + (excess_300 * 15) + excess_1000 + 10400
        
        # Компонент 3: доставка по Астане
        component3 = 4000 + (270 * 15) + (excess_300 * 2) + (excess_1000 * 9) + 10400
        
        return component1 + component2 + component3


def calculate_volume_from_dimensions(size_gross):
    """
    Рассчитывает объем из габаритов
    size_gross - строка с габаритами в формате "ДхШхВ" (мм)
    """
    if not size_gross or size_gross == "0":
        return 0
    
    try:
        # Заменяем "х" на "x" и разбиваем по "x"
        dimensions = size_gross.lower().replace("х", "x").split("x")
        if len(dimensions) != 3:
            return 0
        
        # Преобразуем в метры и рассчитываем объем
        width, height, depth = map(lambda x: float(x) / 1000, dimensions)
        volume = width * height * depth
        return volume
    except (ValueError, IndexError):
        return 0


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT,
        brand TEXT,
        code TEXT UNIQUE,
        country TEXT,
        dilerCurrency TEXT,
        dilerPrice REAL,
        fullName TEXT,
        inStock INTEGER,
        model TEXT,
        name TEXT,
        price REAL,
        priceCurrency TEXT,
        inReserve INTEGER,
        img TEXT,
        sizeNet TEXT,
        sizeGross TEXT,
        description TEXT
    )
    """)
    
    # Очищаем старые данные перед записью новых
    cursor.execute("DELETE FROM products")
    log.info("🗑️ Старые данные из базы удалены")
    
    conn.commit()
    conn.close()


def save_product_to_db(product):
    global cost
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Курсы валют
    exchange_rates = info.exchange_rates

    # Преобразование валюты
    price_currency = product.get("priceCurrency", "RUB").replace("УЕ ", "").replace(" ВН", "").replace(" 1.5", "")
    original_price = product.get("dilerPrice", 0)
    
    # Получаем вес и габариты
    weight_gross = product.get("weightGross", 0)
    size_gross = product.get("sizeGross", "0х0х0")
    
    # Проверяем наличие данных для расчета
    has_weight = weight_gross and weight_gross > 0
    has_dimensions = size_gross and size_gross != "0х0х0" and size_gross != "0"
    
    if not has_weight or not has_dimensions:
        # Записываем товар с нулевой ценой
        price = 0
        price_currency = "KZT"
        
        # Записываем в файл товаров без данных
        product_name = product.get("name", "Неизвестный товар")
        product_code = product.get("code", "Нет кода")
        
        with open("Товары без данных для расчётов.txt", "a", encoding="utf-8") as file:
            if not has_weight and not has_dimensions:
                file.write(f"Товар: {product_name} (код: {product_code}) - нет веса и габаритов для расчёта доставки\n")
            elif not has_weight:
                file.write(f"Товар: {product_name} (код: {product_code}) - цена товара у БИО - нет веса для расчёта доставки\n")
            else:
                file.write(f"Товар: {product_name} (код: {product_code}) - цена товара у БИО - нет габаритов для расчёта доставки\n")
    else:
        # Рассчитываем объем
        volume = calculate_volume_from_dimensions(size_gross)
        
        # Рассчитываем стоимость доставки
        delivery_cost = calculate_delivery_cost(weight_gross, volume)
        
        # Применяем новую формулу: (X/1.2*курс*1.12+доставка)*1.18
        converted_price = original_price / 1.2 * exchange_rates.get(price_currency, 1) * 1.12
        converted_price = converted_price + delivery_cost
        converted_price = converted_price * 1.18
        
        price = int(round(converted_price))
        price_currency = "KZT"

    # Проверка дубликатов перед вставкой
    cursor.execute("SELECT id FROM products WHERE code = ?", (product.get("code"),))
    if cursor.fetchone() is None:
        cursor.execute("""
        INSERT INTO products (category, brand, code, country, dilerCurrency, dilerPrice,
                              fullName, inStock, model, name, price, priceCurrency, inReserve, img, 
                              sizeNet, sizeGross, description)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            product.get("category"),
            product.get("brand"),
            product.get("code"),
            product.get("country"),
            product.get("dilerCurrency"),
            product.get("dilerPrice"),
            product.get("fullName"),
            product.get("inStock"),
            product.get("model"),
            product.get("name"),
            price,
            price_currency,
            product.get("inReserve"),
            product.get("img"),
            product.get("sizeNet", ""),
            product.get("sizeGross", ""),
            product.get("description", "")
        ))

    conn.commit()
    conn.close()


def fetch_categories():
    url = f"{BASE_URL}/categories"
    log.info(f"🌐 Запрашиваем категории: {url}")
    try:
        response = requests.post(url, json=AUTH_CREDENTIALS, timeout=30)
        log.info(f"📡 Ответ сервера: {response.status_code}")
        response.raise_for_status()
        categories_data = response.json()
        log.info(f"✅ Получено категорий: {len(categories_data) if isinstance(categories_data, list) else 'ошибка'}")
        return categories_data
    except Exception as e:
        log.error(f"❌ Ошибка получения категорий: {e}")
        return {"error": str(e)}


def fetch_products_by_category(category_id):
    url = f"{BASE_URL}/products"
    payload = {**AUTH_CREDENTIALS, "categoryId": category_id}
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        products_data = response.json()
        return products_data
    except Exception as e:
        log.error(f"❌ Ошибка получения товаров категории {category_id}: {e}")
        return {"error": str(e)}


def fetch_product_details(product_code):
    url = f"{BASE_URL}/product"
    payload = {**AUTH_CREDENTIALS, "code": product_code}
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        return data
    except Exception as e:
        log.error(f"❌ Ошибка получения деталей для {product_code}: {e}")
        return {}


@app.route('/products', methods=['GET'])
def get_all_products():
    start_time = datetime.now()
    log.info("🚀 СТАРТ ПОЛУЧЕНИЯ ДАННЫХ ИЗ БИО")
    
    init_db()

    categories_response = fetch_categories()
    if "error" in categories_response:
        log.error("❌ Критическая ошибка получения категорий")
        return jsonify(categories_response), 500

    total_products = 0
    
    for category_group in categories_response:
        categories = category_group.get("categories", [])
        for category in categories:
            category_id = category.get("id")
            category_name = category.get("name", "Unknown Category")
            if category_id:
                products = fetch_products_by_category(category_id)
                if isinstance(products, list):
                    for product in products:
                        product["category"] = category_name

                        # Получаем детальную информацию о товаре
                        product_details = fetch_product_details(product.get("code"))
                        if isinstance(product_details, dict):
                            product["description"] = product_details.get("description", "")
                            product["sizeNet"] = product_details.get("sizeNet", "")
                            product["sizeGross"] = product_details.get("sizeGross", "")
                            product["weightGross"] = product_details.get("weightGross", 0)
                            product["weightNet"] = product_details.get("weightNet", 0)

                        save_product_to_db(product)
                        total_products += 1
    
    end_time = datetime.now()
    duration = end_time - start_time
    log.info(f"✅ ПОЛУЧЕНИЕ ДАННЫХ ИЗ БИО ЗАВЕРШЕНО. Товаров: {total_products}, Время: {duration}")

    return jsonify({"message": "Данные успешно сохранены в базу", "total_products": total_products})


def run_update_stocks_script():
    """
    Запускает скрипт обновления остатков после завершения сбора данных
    """
    start_time = datetime.now()
    log.info("🔄 ОБНОВЛЕНИЕ ОСТАТКОВ И ЦЕН")
    
    try:
        # Запускаем скрипт update_stocks_bio.py с стримингом вывода
        proc = subprocess.Popen(
            ['python', '-u', 'update_stocks_bio.py'],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=os.getcwd()
        )
        
        # Читаем построчно и сразу пробрасываем в лог
        for line in proc.stdout:
            log.info("update_stocks | %s", line.rstrip())
        
        rc = proc.wait()
        end_time = datetime.now()
        duration = end_time - start_time
        
        if rc == 0:
            log.info("✅ Скрипт обновления остатков успешно завершён")
            log.info(f"✅ Продолжительность: {duration}")
        else:
            log.error("❌ Скрипт обновления остатков завершился с кодом %s", rc)
            log.error(f"❌ Продолжительность до ошибки: {duration}")
            
    except Exception as e:
        end_time = datetime.now()
        duration = end_time - start_time
        log.error("❌ Ошибка запуска скрипта обновления")
        log.error(f"❌ Продолжительность до ошибки: {duration}")
        log.exception("❌ Ошибка: %s", e)


def scheduled_data_update():
    """
    Функция для автоматического обновления данных в 01:00 по времени Франкфурта
    """
    start_time = datetime.now()
    log.info("🌅 НАЧАЛО АВТОМАТИЧЕСКОГО ОБНОВЛЕНИЯ ДАННЫХ")
    
    try:
        log.info("🔍 Функция scheduled_data_update вызвана")
        # Обновляем курсы валют
        log.info("💱 Обновляем курсы валют...")
        valute.valute()
        importlib.reload(info)
        log.info(f"💱 Курсы валют обновлены: {info.exchange_rates}")
        
        # Инициализируем базу данных
        log.info("🗄️ Инициализируем базу данных...")
        init_db()
        
        # Получаем категории
        log.info("📂 Получаем категории товаров...")
        categories_response = fetch_categories()
        if "error" in categories_response:
            log.error(f"❌ Ошибка получения категорий: {categories_response['error']}")
            return
        
        # Обрабатываем товары
        log.info("🔄 Начинаем обработку товаров...")
        total_products = 0
        
        for category_group in categories_response:
            categories = category_group.get("categories", [])
            for category in categories:
                category_id = category.get("id")
                category_name = category.get("name", "Unknown Category")
                if category_id:
                    products = fetch_products_by_category(category_id)
                    if isinstance(products, list):
                        for product in products:
                            product["category"] = category_name

                            # Получаем детальную информацию о товаре
                            product_details = fetch_product_details(product.get("code"))
                            if isinstance(product_details, dict):
                                product["description"] = product_details.get("description", "")
                                product["sizeNet"] = product_details.get("sizeNet", "")
                                product["sizeGross"] = product_details.get("sizeGross", "")
                                product["weightGross"] = product_details.get("weightGross", 0)
                                product["weightNet"] = product_details.get("weightNet", 0)

                            save_product_to_db(product)
                            total_products += 1
        
        log.info(f"✅ Данные успешно сохранены в базу. Всего товаров: {total_products}")
        
        # Запускаем скрипт обновления остатков
        log.info("🔄 Запускаем обновление остатков...")
        run_update_stocks_script()
        
        # Выводим итоговую информацию
        end_time = datetime.now()
        duration = end_time - start_time
        log.info("🎉 АВТОМАТИЧЕСКОЕ ОБНОВЛЕНИЕ УСПЕШНО ЗАВЕРШЕНО!")
        log.info(f"🎉 Общая продолжительность: {duration}")
        log.info(f"🎉 Обработано товаров: {total_products}")
        
    except Exception as e:
        end_time = datetime.now()
        duration = end_time - start_time
        log.error("❌ ОШИБКА АВТОМАТИЧЕСКОГО ОБНОВЛЕНИЯ!")
        log.error(f"❌ Продолжительность до ошибки: {duration}")
        log.exception("❌ Ошибка: %s", e)


def start_scheduler():
    """
    Запускает планировщик задач в отдельном потоке
    """
    def run_scheduler():
        # Планируем задачу на 1 утра по времени Франкфурта (UTC+1)
        # Если сервер в UTC, то это 0:00 UTC (полночь)
        schedule.every().day.at("00:00").do(scheduled_data_update)
        
        log.info("⏰ Планировщик запущен. Следующее обновление в 00:00 UTC")
        log.info(f"⏰ Текущее время: {datetime.now()}")
        log.info(f"⏰ Часовой пояс: {time.tzname}")
        
        while True:
            schedule.run_pending()
            time.sleep(60)  # Проверяем каждую минуту
    
    # Запускаем планировщик в отдельном потоке
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    log.info("🚀 Планировщик задач запущен в фоновом режиме")


if __name__ == '__main__':
    try:
        # Логируем запуск приложения
        log.info("🎯 ЗАПУСК ПРИЛОЖЕНИЯ BIO API")
        log.info("🔧 Проверяем доступность модулей...")
        
        # Проверяем импорты
        try:
            log.info("✅ requests импортирован успешно")
            log.info("✅ sqlite3 импортирован успешно")
            log.info("✅ flask импортирован успешно")
            log.info("✅ schedule импортирован успешно")
        except Exception as e:
            log.error(f"❌ Ошибка импорта: {e}")
        
        # Запускаем планировщик при старте приложения
        start_scheduler()
        
        # Запускаем обновление данных при старте приложения
        log.info("🚀 СТАРТ ПОЛУЧЕНИЯ ДАННЫХ ИЗ БИО")
        scheduled_data_update()
        
        # Для Background Worker Flask сервер не обязателен
        # Если нужен HTTP-эндпоинт, раскомментируйте следующую строку
        # app.run(debug=False, host='0.0.0.0', port=5000)
        
        # Для Background Worker просто держим процесс живым
        log.info("🌐 Приложение готово к работе (Background Worker)")
        while True:
            time.sleep(60)  # Проверяем каждую минуту
            
    except Exception as e:
        log.error("❌ КРИТИЧЕСКАЯ ОШИБКА: %s", e)
        log.exception("❌ Traceback:")
