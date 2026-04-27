# road_analyzer.py
from shapely.geometry import Point
import pandas as pd
import re
from pathlib import Path
from constants import BUFFER_SIZE, ROAD_PRIORITY, ROAD_GENITIVE, PATHS

# Загрузка словаря склонений из Excel
def load_declensions():
    """
    Загружает словарь склонений из файла 'точки интереса словарь.xlsx'
    Колонка A - слово, колонка B - родительный падеж
    """
    declensions_file = PATHS['data_folder'] / 'точки интереса словарь.xlsx'
    
    if not declensions_file.exists():
        return {}
    
    df = pd.read_excel(declensions_file, header=None)
    return dict(zip(df[0], df[1]))

DECLENSIONS = load_declensions()

def find_connecting_objects(point, roads_gdf, points_gdf, current_road_name):
    """
    Находит объекты, к которым примыкает точка.
    Сначала ищет среди дорог, потом среди точек интереса.
    """
    buffer = point.buffer(BUFFER_SIZE)
    
    # 1. Поиск среди ДОРОГ
    road_mask = roads_gdf.intersects(buffer) & (roads_gdf['Name'] != current_road_name)
    connecting_roads = roads_gdf[road_mask]
    
    if len(connecting_roads) > 0:
        connecting_roads = connecting_roads.copy()
        connecting_roads['distance'] = connecting_roads.geometry.distance(point)
        connecting_roads['priority'] = connecting_roads['Принадлежность'].map(ROAD_PRIORITY)
        sorted_roads = connecting_roads.sort_values(['priority', 'distance'])
        connected = sorted_roads.iloc[0]
        return ('road', connected['Название'], connected['Принадлежность'])
    
    # 2. Поиск среди ТОЧЕК ИНТЕРЕСА
    if points_gdf is not None and not points_gdf.empty:
        points_mask = points_gdf.intersects(buffer)
        connecting_points = points_gdf[points_mask]
        if len(connecting_points) > 0:
            connecting_points = connecting_points.copy()
            connecting_points['distance'] = connecting_points.geometry.distance(point)
            closest = connecting_points.sort_values('distance').iloc[0]
            return ('point', closest['Name'], None)
    
    return (None, None, None)

# ============================================================================
# ФУНКЦИИ ФОРМАТИРОВАНИЯ (БЕЗ ПРЕФИКСОВ ОТ/ДО)
# ============================================================================

def format_road_name(name, ownership):
    """
    Форматирует название дороги с учетом принадлежности и падежа.
    Возвращает только название в правильном падеже, без префикса от/до.
    """
    genitive = ROAD_GENITIVE[ownership]
    return f"{genitive} дороги «{name}»"

def format_point_name(name):
    """
    Форматирует название точки интереса.
    Возвращает только название в правильном падеже, без префикса от/до.
    1. Проверяет паттерн "км число"
    2. Если нет, берет первое слово и ищет в словаре склонений
    3. Если слово найдено, склоняет его
    4. Если не найдено, оставляет как есть
    """
    # Проверка на километровые отметки
    if re.search(r'км \d+', name.lower()):
        return f"пересечения с МГ {name}"
    
    # Разбиваем на слова
    words = name.split()
    if words and DECLENSIONS:
        first_word = words[0].lower()
        if first_word in DECLENSIONS:
            words[0] = DECLENSIONS[first_word]
            return ' '.join(words)
    
    return name

def format_connection(conn_tuple):
    """
    Форматирует связь по шаблону.
    Возвращает только название, без префикса от/до.
    """
    conn_type, name, ownership = conn_tuple
    if not name:
        return ""
    
    if conn_type == 'road':
        return format_road_name(name, ownership)
    else:
        return format_point_name(name)

# ============================================================================
# ФУНКЦИЯ ДЛЯ СОРТИРОВКИ (разделение номера на букву и число)
# ============================================================================

def split_letter_number(value):
    """
    Разделяет номер на букву и число.
    Пример: 'А 31.2' → ('А', 31.2)
    """
    if not value or pd.isna(value):
        return ('', 0)
    
    value_str = str(value).strip()
    
    # Ищем букву в начале (русская или английская)
    match = re.match(r'^([А-Яа-яA-Za-z]?)\s*(.*)$', value_str)
    if match:
        letter = match.group(1) if match.group(1) else ''
        number_part = match.group(2).strip()
        # Преобразуем число (с точкой) в float
        try:
            number = float(number_part) if number_part else 0
        except ValueError:
            number = 0
    else:
        letter = ''
        number = 0
    
    return letter, number

# ============================================================================
# ОСНОВНАЯ ФУНКЦИЯ АНАЛИЗА
# ============================================================================

def analyze_connections(gdf_roads, points_gdf=None):
    """
    Анализирует связи для всех дорог.
    Заполняет колонки 'Откуда' и 'Куда' названиями без префиксов от/до.
    """
    result = gdf_roads.copy()
    result['Откуда'] = ""
    result['Куда'] = ""
    
    found_start = 0
    found_end = 0
    
    for idx, row in result.iterrows():
        coords = list(row.geometry.coords)
        start_point = Point(coords[0])
        end_point = Point(coords[-1])
        
        start_conn = find_connecting_objects(start_point, result, points_gdf, row['Name'])
        end_conn = find_connecting_objects(end_point, result, points_gdf, row['Name'])
        
        if start_conn[0]:
            result.at[idx, 'Откуда'] = format_connection(start_conn)
            found_start += 1
        if end_conn[0]:
            result.at[idx, 'Куда'] = format_connection(end_conn)
            found_end += 1
    
    print(f"  Найдено связей: начало - {found_start}, конец - {found_end}")
    return result