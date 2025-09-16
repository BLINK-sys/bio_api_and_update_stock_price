#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import time
from datetime import datetime

def main():
    """Простая функция для тестирования логирования"""
    
    # Принудительно выводим логи
    print(f"🚀 [{datetime.now()}] ТЕСТ ЛОГИРОВАНИЯ НАЧАТ", flush=True)
    sys.stdout.flush()
    
    # Ждем 2 секунды
    time.sleep(2)
    
    print(f"📦 [{datetime.now()}] Модуль test_logs.py загружен", flush=True)
    sys.stdout.flush()
    
    # Ждем еще 2 секунды
    time.sleep(2)
    
    print(f"✅ [{datetime.now()}] ТЕСТ ЛОГИРОВАНИЯ ЗАВЕРШЕН", flush=True)
    sys.stdout.flush()
    
    # Запускаем простой Flask сервер
    from flask import Flask
    app = Flask(__name__)
    
    @app.route('/')
    def hello():
        return 'Hello, World! Test logs working!'
    
    print(f"🌐 [{datetime.now()}] Flask сервер запускается на порту 5000...", flush=True)
    sys.stdout.flush()
    
    app.run(debug=False, host='0.0.0.0', port=5000)

if __name__ == '__main__':
    main()
