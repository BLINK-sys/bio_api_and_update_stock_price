#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import logging
import time
from datetime import datetime

# Настройка переменных окружения для Render
os.environ.setdefault("PYTHONUNBUFFERED", "1")
os.environ.setdefault("PYTHONIOENCODING", "UTF-8")

# Настройка логирования для Render
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True,
)
log = logging.getLogger("test_render")

def main():
    """Простая функция для тестирования логирования на Render"""
    
    log.info("=" * 60)
    log.info("🚀 ТЕСТ ЛОГИРОВАНИЯ НА RENDER")
    log.info("=" * 60)
    
    # Информация о среде
    log.info("🔧 ИНФОРМАЦИЯ О СРЕДЕ:")
    log.info(f"🔧 Python версия: {sys.version}")
    log.info(f"🔧 Рабочая директория: {os.getcwd()}")
    log.info(f"🔧 PYTHONUNBUFFERED: {os.environ.get('PYTHONUNBUFFERED', 'НЕ УСТАНОВЛЕН')}")
    log.info(f"🔧 PYTHONIOENCODING: {os.environ.get('PYTHONIOENCODING', 'НЕ УСТАНОВЛЕН')}")
    log.info(f"🔧 TZ: {os.environ.get('TZ', 'НЕ УСТАНОВЛЕН')}")
    log.info(f"🔧 RENDER: {os.environ.get('RENDER', 'НЕ УСТАНОВЛЕН')}")
    log.info(f"🔧 PORT: {os.environ.get('PORT', 'НЕ УСТАНОВЛЕН')}")
    
    # Тест логирования
    for i in range(5):
        log.info(f"📝 Тест логирования #{i+1} - {datetime.now()}")
        time.sleep(2)
    
    log.info("✅ ТЕСТ ЛОГИРОВАНИЯ ЗАВЕРШЕН")
    log.info("=" * 60)

if __name__ == "__main__":
    try:
        main()
        # Держим процесс живым для Background Worker
        log.info("🔄 Процесс работает...")
        while True:
            time.sleep(60)
            log.info(f"⏰ Процесс активен - {datetime.now()}")
    except KeyboardInterrupt:
        log.info("🛑 Получен сигнал завершения")
    except Exception as e:
        log.error(f"❌ Ошибка: {e}")
        log.exception("❌ Traceback:")
