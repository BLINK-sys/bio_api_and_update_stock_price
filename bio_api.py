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
    level=logging.INFO,  # Изменено с DEBUG на INFO
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True,  # сбросить чужие хэндлеры (например, werkzeug)
)

# Отключаем лишние логи от внешних библиотек
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
logging.getLogger("requests.packages.urllib3").setLevel(logging.WARNING)

log = logging.getLogger("bio")

# Минимальная информация о запуске
log.info("🚀 BIO API запущен")

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
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Логируем загрузку модуля
# Модуль загружен

app = Flask(__name__)

BASE_URL = "http://api.bioshop.ru:8030"
AUTH_CREDENTIALS = {
    "login": "dilyara@pospro.kz",
    "password": "qo8qe7ti"
}

DB_PATH = "products.db"

# Настройка сессии requests с повторными попытками и таймаутами
session = requests.Session()
retry_strategy = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["POST"]
)
adapter = HTTPAdapter(max_retries=retry_strategy)
session.mount("http://", adapter)
session.mount("https://", adapter)

# Блокировка для предотвращения множественных одновременных запусков
update_lock = threading.Lock()
is_updating = False

# Обновляем курсы валют
valute.valute()
# Перезагружаем модуль info для получения обновленных курсов
import importlib
importlib.reload(info)
log.info(f"💱 Курс валют обновлён: {info.exchange_rates}")

# Обновляем курсы BIO
import valute_bio
valute_bio.get_bio_rates()
log.info("💱 Курсы BIO обновлены")


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
        # До 30 кг: 9000 + 12000 + (26*450) + 5000 = 37,700 тг
        return 37700
    elif delivery_weight <= 300:
        # 30-300 кг: 9000 + (вес-30)*215 + 12000 + (вес-30)*27 + 26*450 + 5000 + (вес-30)*19
        excess_weight = delivery_weight - 30
        return 9000 + (excess_weight * 215) + 12000 + (excess_weight * 27) + 11700 + 5000 + (excess_weight * 19)
    elif delivery_weight <= 1000:
        # 300-1000 кг: сумма трех компонентов
        excess_300 = delivery_weight - 300
        excess_1000 = max(0, delivery_weight - 1000)

        # Компонент 1: город+город
        component1 = 9000 + (270 * 215) + (excess_300 * 164) + (excess_1000 * 143)

        # Компонент 2: забор склад БИО
        component2 = 12000 + (270 * 27) + (excess_300 * 15) + excess_1000 + 11700

        # Компонент 3: доставка по Астане
        component3 = 5000 + (270 * 19) + (excess_300 * 2) + (excess_1000 * 9) + 11700

        return component1 + component2 + component3
    else:
        # Свыше 1000 кг - используем формулу для 1000 кг (без рекурсии)
        excess_300 = 700  # 1000 - 300
        excess_1000 = 0   # 1000 - 1000 = 0

        # Компонент 1: город+город
        component1 = 9000 + (270 * 215) + (excess_300 * 164) + (excess_1000 * 143)

        # Компонент 2: забор склад БИО
        component2 = 12000 + (270 * 27) + (excess_300 * 15) + excess_1000 + 11700

        # Компонент 3: доставка по Астане
        component3 = 5000 + (270 * 19) + (excess_300 * 2) + (excess_1000 * 9) + 11700

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
    
    # Получаем курсы BIO для конвертации в рубли
    try:
        import bio_rates
        bio_rates_dict = bio_rates.bio_rates
    except ImportError:
        # Если файл bio_rates.py не существует, используем значения по умолчанию
        bio_rates_dict = {'EUR': 109.0, 'USD': 93.0}

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
        
        # Двухэтапная конвертация:
        # Этап 1: BIO курсы (EUR/USD -> RUB)
        # Этап 2: МИГ курсы (RUB -> KZT)
        
        if price_currency in ['EUR', 'USD']:
            # Этап 1: Конвертируем в рубли по курсам BIO
            price_in_rubles = original_price * bio_rates_dict.get(price_currency, 1)
            # Этап 2: Конвертируем рубли в тенге по курсам МИГ
            price_in_tenge = price_in_rubles * exchange_rates.get('RUB', 1)
        else:
            # Если уже в рублях, конвертируем только в тенге
            price_in_tenge = original_price * exchange_rates.get(price_currency, 1)
        
        # Применяем формулу: (X/1.2*1.12+доставка)*1.16
        converted_price = price_in_tenge / 1.22 * 1.16
        converted_price = converted_price + delivery_cost
        converted_price = converted_price * 1.16
        
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
    try:
        response = session.post(url, json=AUTH_CREDENTIALS, timeout=(10, 30))
        response.raise_for_status()
        categories_data = response.json()
        log.info(f"✅ Получено категорий: {len(categories_data) if isinstance(categories_data, list) else 'ошибка'}")
        return categories_data
    except requests.exceptions.Timeout:
        log.error(f"❌ Таймаут при получении категорий")
        return {"error": "Timeout"}
    except Exception as e:
        log.error(f"❌ Ошибка получения категорий: {e}")
        return {"error": str(e)}


def fetch_products_by_category(category_id):
    url = f"{BASE_URL}/products"
    payload = {**AUTH_CREDENTIALS, "categoryId": category_id}
    try:
        response = session.post(url, json=payload, timeout=(10, 30))
        response.raise_for_status()
        products_data = response.json()
        return products_data
    except requests.exceptions.Timeout:
        log.error(f"❌ Таймаут при получении товаров категории {category_id}")
        return {"error": "Timeout"}
    except Exception as e:
        log.error(f"❌ Ошибка получения товаров категории {category_id}: {e}")
        return {"error": str(e)}


def fetch_product_details(product_code, max_retries=2):
    url = f"{BASE_URL}/product"
    payload = {**AUTH_CREDENTIALS, "code": product_code}
    
    for attempt in range(max_retries):
        try:
            response = session.post(url, json=payload, timeout=(5, 15))
            response.raise_for_status()
            data = response.json()
            return data
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                log.warning(f"⏳ Таймаут при получении деталей для {product_code}, попытка {attempt + 1}/{max_retries}")
                time.sleep(1)
                continue
            else:
                log.error(f"❌ Таймаут при получении деталей для {product_code} после {max_retries} попыток")
                return {}
        except requests.exceptions.ConnectionError as e:
            if attempt < max_retries - 1:
                log.warning(f"⏳ Ошибка соединения для {product_code}, попытка {attempt + 1}/{max_retries}")
                time.sleep(2)
                continue
            else:
                log.error(f"❌ Ошибка соединения для {product_code}: {e}")
                return {}
        except Exception as e:
            log.error(f"❌ Ошибка получения деталей для {product_code}: {e}")
            return {}
    
    return {}


@app.route('/products', methods=['GET'])
def get_all_products():
    global is_updating
    
    # Проверяем, не выполняется ли уже обновление
    if not update_lock.acquire(blocking=False):
        log.warning("⚠️ Обновление данных уже выполняется, возвращаем ошибку")
        return jsonify({"error": "Обновление данных уже выполняется, попробуйте позже"}), 429
    
    if is_updating:
        update_lock.release()
        log.warning("⚠️ Обновление данных уже выполняется, возвращаем ошибку")
        return jsonify({"error": "Обновление данных уже выполняется, попробуйте позже"}), 429
    
    is_updating = True
    start_time = datetime.now()
    log.info("🚀 СТАРТ ПОЛУЧЕНИЯ ДАННЫХ ИЗ БИО")
    
    try:
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
                            
                            # Небольшая задержка между запросами, чтобы не перегружать API
                            if total_products % 10 == 0:
                                time.sleep(0.1)  # Задержка каждые 10 товаров
    
        end_time = datetime.now()
        duration = end_time - start_time
        log.info(f"✅ ПОЛУЧЕНИЕ ДАННЫХ ИЗ БИО ЗАВЕРШЕНО. Товаров: {total_products}, Время: {duration}")

        return jsonify({"message": "Данные успешно сохранены в базу", "total_products": total_products})
    except Exception as e:
        log.error(f"❌ Ошибка в эндпоинте /products: {e}")
        log.exception("❌ Traceback:")
        return jsonify({"error": str(e)}), 500
    finally:
        is_updating = False
        update_lock.release()
        log.info("🔓 Блокировка обновления снята (эндпоинт /products)")


def run_update_stocks_script():
    """
    Запускает скрипт обновления остатков после завершения сбора данных
    """
    start_time = datetime.now()
    log.info("🔄 Обновление остатков...")
    
    try:
        # Запускаем скрипт update_stocks_bio.py с стримингом вывода
        proc = subprocess.Popen(
            ['python', '-u', 'update_stocks_bio.py'],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='replace',
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
    global is_updating
    
    # Проверяем, не выполняется ли уже обновление
    if not update_lock.acquire(blocking=False):
        log.warning("⚠️ Обновление данных уже выполняется, пропускаем этот запуск")
        return
    
    if is_updating:
        log.warning("⚠️ Обновление данных уже выполняется, пропускаем этот запуск")
        update_lock.release()
        return
    
    is_updating = True
    start_time = datetime.now()
    log.info("🔄 Начинаем обновление данных")
    
    try:
        # Обновляем курсы валют
        valute.valute()
        importlib.reload(info)
        log.info(f"💱 Курсы обновлены: {info.exchange_rates}")
        
        # Инициализируем базу данных
        init_db()
        
        # Получаем категории
        log.info("📂 Получаем категории...")
        categories_response = fetch_categories()
        if "error" in categories_response:
            log.error(f"❌ Ошибка получения категорий: {categories_response['error']}")
            return
        
        # Обрабатываем товары
        log.info("🔄 Обработка товаров...")
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
                            
                            # Небольшая задержка между запросами, чтобы не перегружать API
                            if total_products % 10 == 0:
                                time.sleep(0.1)  # Задержка каждые 10 товаров
        
        log.info(f"✅ Данные успешно сохранены в базу. Всего товаров: {total_products}")
        
        # Запускаем скрипт обновления остатков
        log.info("🔄 Обновление остатков...")
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
    finally:
        is_updating = False
        update_lock.release()
        log.info("🔓 Блокировка обновления снята")


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
        # Запускаем в отдельном потоке, чтобы не блокировать планировщик
        update_thread = threading.Thread(target=scheduled_data_update, daemon=True)
        update_thread.start()
        
        # Для веб-сервиса раскомментируйте следующую строку
        # app.run(debug=False, host='0.0.0.0', port=5000)
        
        # Для Background Worker просто держим процесс живым
        log.info("🌐 Приложение готово к работе (Background Worker)")
        while True:
            time.sleep(60)  # Проверяем каждую минуту
            
    except Exception as e:
        log.error("❌ КРИТИЧЕСКАЯ ОШИБКА: %s", e)
        log.exception("❌ Traceback:")
