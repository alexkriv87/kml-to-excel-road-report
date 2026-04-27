# main.py
# -*- coding: utf-8 -*-
import sys
import io
import time
import warnings
import re
import pandas as pd
import geopandas as gpd
from pathlib import Path

import road_extractor
import road_analyzer
import excel_exporter

from constants import PATHS, TEMPLATE_PATH, DECLENSIONS_PATH, ROAD_PRIORITY
from road_analyzer import split_letter_number

from logger_config import setup_logging

logger = setup_logging()

# Настройка кодировки
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

if sys.stderr.encoding != 'utf-8':
    try:
        sys.stderr.reconfigure(encoding='utf-8')
    except:
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

warnings.filterwarnings('ignore')

total_start_time = time.time()

# Получаем путь от пользователя
folder_path = input("Вставьте путь из адресной строки: ").strip().strip('"')
folder_path = Path(folder_path)

# Ищем первый KML/KMZ файл по алфавиту
kml_files = [f for f in folder_path.iterdir() if f.suffix.lower() in ('.kml', '.kmz')]
kml_files.sort()
file_path = folder_path / kml_files[0]

logger.info("")
logger.info(">> [INIT] ЗАГРУЖЕН ФАЙЛ: %s", kml_files[0].name)

template_path = TEMPLATE_PATH
results_dir = folder_path
results_dir.mkdir(exist_ok=True)

logger.info(">> [INIT] ЗАПУСК ПРОЦЕССА")

# 1. ПАРСИНГ KML (ДОРОГИ)
logger.info("")
logger.info(">> [1] ПАРСИНГ ДОРОГ")
namespaces = {'kml': 'http://earth.google.com/kml/2.2'}
roads = road_extractor.extract_roads_from_kml(file_path, namespaces)
logger.info("     >> НАЙДЕНО: %s", len(roads))

# 2. ПАРСИНГ KML (ТОЧКИ ИНТЕРЕСА)
logger.info(">> [2] ПАРСИНГ ТОЧЕК")
points = road_extractor.extract_points_from_kml(file_path, namespaces)
logger.info("     >> НАЙДЕНО: %s", len(points))

# 3. ПОЛУЧЕНИЕ ГЕОМЕТРИИ ДОРОГ
logger.info(">> [3] ГЕОМЕТРИЯ ДОРОГ")
gdf_roads = road_extractor.get_road_dataframe(file_path, roads)
logger.info("     >> ДОРОГ: %s", len(gdf_roads))

# 4. ПОЛУЧЕНИЕ ГЕОМЕТРИИ ТОЧЕК
logger.info(">> [4] ГЕОМЕТРИЯ ТОЧЕК")
gdf_points = road_extractor.get_points_dataframe(file_path, points)
if gdf_points is not None:
    logger.info("     >> ТОЧЕК: %s", len(gdf_points))
else:
    logger.info("     >> НЕ НАЙДЕНО")

# 5. ОПРЕДЕЛЕНИЕ ПРИНАДЛЕЖНОСТИ
logger.info(">> [5] ПРИНАДЛЕЖНОСТЬ")
gdf_roads['Принадлежность'] = gdf_roads['full_path'].apply(
    road_extractor.get_ownership)

# 6. РАСЧЕТ ДЛИНЫ
logger.info(">> [6] РАСЧЕТ ДЛИНЫ")
gdf_roads['Протяженность'] = gdf_roads.apply(
    road_extractor.calculate_length, axis=1)

# 7. ПРЕОБРАЗОВАНИЕ КООРДИНАТ
logger.info(">> [7] КООРДИНАТЫ DMS")
coords_df = gdf_roads.apply(
    road_extractor.get_coordinates, axis=1, result_type='expand')
gdf_roads = pd.concat([gdf_roads, coords_df], axis=1)

# 8. ПАРСИНГ DESCRIPTION
logger.info(">> [8] ПАРСИНГ DESCRIPTION")
parsed = gdf_roads['description'].apply(road_extractor.parse_description)
gdf_roads['покрытие'] = parsed.apply(lambda x: x['покрытие'])
gdf_roads['принадлежность'] = parsed.apply(lambda x: x['принадлежность'])
gdf_roads['осевая_нагрузка'] = parsed.apply(lambda x: x['осевая_нагрузка'])
gdf_roads['категория'] = parsed.apply(lambda x: x['категория'])
gdf_roads['ширина'] = parsed.apply(lambda x: x['ширина'])

# 9. ОБРАБОТКА НАЗВАНИЙ
logger.info(">> [9] ОБРАБОТКА НАЗВАНИЙ")
gdf_roads['Name'] = gdf_roads['Name'].apply(road_extractor.fix_quotes)

gdf_roads['Номер'] = ""
gdf_roads['Название'] = ""

for idx, row in gdf_roads.iterrows():
    number, name = road_extractor.split_road_name(row['Name'])
    gdf_roads.at[idx, 'Номер'] = number
    gdf_roads.at[idx, 'Название'] = name

# 10. АНАЛИЗ СВЯЗЕЙ
logger.info(">> [10] АНАЛИЗ СВЯЗЕЙ")
gdf_roads = road_analyzer.analyze_connections(gdf_roads, gdf_points)

# 11. ФИНАЛЬНАЯ ЗАЧИСТКА
logger.info(">> [11] ФИНАЛЬНАЯ ЗАЧИСТКА")
gdf_roads['Откуда'] = gdf_roads['Откуда'].apply(
    road_extractor.final_text_cleanup)
gdf_roads['Куда'] = gdf_roads['Куда'].apply(road_extractor.final_text_cleanup)

# 12. СОРТИРОВКА ДОРОГ (буква + число)
logger.info(">> [12] СОРТИРОВКА ДОРОГ")

# Создаём колонки для сортировки
split_result = gdf_roads['Номер'].apply(split_letter_number)
gdf_roads['_letter'] = split_result.apply(lambda x: x[0])
gdf_roads['_number'] = split_result.apply(lambda x: x[1])

# Добавляем числовой приоритет
gdf_roads['_priority'] = gdf_roads['Принадлежность'].map(ROAD_PRIORITY).fillna(999)

# Сортируем: приоритет → буква → число
gdf_roads = gdf_roads.sort_values(by=['_priority', '_letter', '_number'])

# Сбрасываем индекс (важно для сохранения порядка в Excel)
gdf_roads = gdf_roads.reset_index(drop=True)

# Удаляем временные колонки
gdf_roads = gdf_roads.drop(columns=['_priority', '_letter', '_number'])

logger.info("     >> СОРТИРОВКА ЗАВЕРШЕНА")

# 13. ЭКСПОРТ В EXCEL
logger.info(">> [13] ЭКСПОРТ В EXCEL")
output_file = results_dir / "Ведомость.xlsx"

excel_exporter.export_to_excel(
    gdf=gdf_roads,
    output_file=output_file,
    template_path=template_path,
    include_geometry=False
)

# ИТОГИ
total_time = time.time() - total_start_time

logger.info("")
logger.info(">> [DONE] ДОРОГ: %s", len(gdf_roads))
logger.info(">> [DONE] ВРЕМЯ: %.2f сек", total_time)
logger.info(">> [DONE] ФАЙЛ: %s", output_file)

# Завершение
input("\nНажмите Enter для выхода...")