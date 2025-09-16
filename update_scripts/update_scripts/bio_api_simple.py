#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import time
from datetime import datetime
from flask import Flask

# Принудительно выводим лог о запуске модуля
print(f"📦 [{datetime.now()}] Модуль bio_api_simple.py загружен", flush=True)
sys.stdout.flush()

app = Flask(__name__)

@app.route('/')
def hello():
    return 'Bio API Simple - Logs Working!'

def test_function():
    """Тестовая функция для проверки логирования"""
    print(f"🔍 [{datetime.now()}] Тестовая функция вызвана", flush=True)
    sys.stdout.flush()
    
    # Имитируем работу
    time.sleep(1)
    
    print(f"✅ [{datetime.now()}] Тестовая функция завершена", flush=True)
    sys.stdout.flush()

if __name__ == '__main__':
    try:
        # Принудительно выводим лог о запуске
        print(f"🎯 [{datetime.now()}] ЗАПУСК УПРОЩЕННОГО BIO API", flush=True)
        sys.stdout.flush()
        
        # Вызываем тестовую функцию
        test_function()
        
        # Запускаем Flask сервер
        print(f"🌐 [{datetime.now()}] Flask сервер запускается на порту 5000...", flush=True)
        print(f"🌐 [{datetime.now()}] Сервер готов к работе!", flush=True)
        sys.stdout.flush()
        
        app.run(debug=False, host='0.0.0.0', port=5000)
        
    except Exception as e:
        print(f"❌ [{datetime.now()}] КРИТИЧЕСКАЯ ОШИБКА: {e}", flush=True)
        import traceback
        print(f"❌ [{datetime.now()}] Traceback: {traceback.format_exc()}", flush=True)
        sys.stdout.flush()
