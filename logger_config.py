import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def get_base_path():
    """Возвращает путь к папке, где находится исполняемый файл"""
    if getattr(sys, 'frozen', False):
        # Запущено из exe
        return Path(sys.executable).parent
    else:
        # Запущено из скрипта
        return Path(__file__).parent


def setup_logging():
    """Настройка логирования"""

    # Папка для логов
    base_dir = get_base_path()
    log_dir = base_dir / "_internal" / "logs"

    # Создаём папку, если её нет
    log_dir.mkdir(parents=True, exist_ok=True)

    # Имя файла лога
    log_filename = log_dir / 'app.log'

    # Создаём логгер
    logger = logging.getLogger('kml_to_excel')
    logger.setLevel(logging.INFO)

    # Очистка существующих обработчиков
    if logger.handlers:
        logger.handlers.clear()

    # Обработчик для файла (с ротацией)
    file_handler = RotatingFileHandler(
        log_filename,
        maxBytes=5_000_000,  # 5 МБ
        backupCount=3,       # 3 файла бэкапа
        encoding='utf-8'
    )

    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    # Обработчик для консоли
    console_handler = logging.StreamHandler()
    console_formatter = logging.Formatter('%(levelname)s: %(message)s')
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    return logger