# road_extractor.py
import xml.etree.ElementTree as ET
import geopandas as gpd
import pandas as pd
import fiona
import re
from pyproj import Geod
from pathlib import Path

# ============================================================================
# ПАРСИНГ KML (ДОРОГИ)
# ============================================================================
def extract_roads_from_kml(file_path, namespaces):
    """
    Парсит KML и возвращает список дорог с путями.
    """
    file_path = Path(file_path)
    tree = ET.parse(file_path)
    root = tree.getroot()
    roads = []
    
    def walk(element, current_path):
        if 'Placemark' in element.tag:
            path_lower = [p.lower() for p in current_path]
            if any('дороги' in p for p in path_lower) and element.find('.//kml:LineString', namespaces):
                name = element.find("kml:name", namespaces).text
                full_path = ' / '.join(current_path + [name])
                roads.append({'name': name, 'path': full_path})
        
        for child in element:
            if 'Folder' in child.tag:
                folder_name = child.find("kml:name", namespaces).text
                walk(child, current_path + [folder_name])
            else:
                walk(child, current_path)
    
    walk(root, [])
    return roads

# ============================================================================
# ПАРСИНГ KML (ТОЧКИ ИНТЕРЕСА)
# ============================================================================
def extract_points_from_kml(file_path, namespaces):
    """
    Парсит KML и возвращает список точек интереса с путями.
    """
    file_path = Path(file_path)
    tree = ET.parse(file_path)
    root = tree.getroot()
    points = []
    
    def walk(element, current_path):
        if 'Placemark' in element.tag:
            path_lower = [p.lower() for p in current_path]
            if any('точки интереса' in p for p in path_lower) and element.find('.//kml:Point', namespaces):
                name = element.find("kml:name", namespaces).text
                full_path = ' / '.join(current_path + [name])
                points.append({'name': name, 'path': full_path})
        
        for child in element:
            if 'Folder' in child.tag:
                folder_name = child.find("kml:name", namespaces).text
                walk(child, current_path + [folder_name])
            else:
                walk(child, current_path)
    
    walk(root, [])
    return points

# ============================================================================
# ПОЛУЧЕНИЕ ДАННЫХ ИЗ KML ЧЕРЕЗ GEOPANDAS
# ============================================================================
def get_road_dataframe(file_path, roads):
    """
    Собирает все линии из KML и соединяет их с путями из roads.
    """
    file_path = Path(file_path)
    all_lines = []
    for layer in fiona.listlayers(str(file_path)):
        gdf = gpd.read_file(file_path, layer=layer)
        lines = gdf[gdf.geom_type == 'LineString']
        all_lines.append(lines)
    
    gdf_all = pd.concat(all_lines, ignore_index=True)
    
    road_to_path = {r['name']: r['path'] for r in roads}
    gdf_all['full_path'] = gdf_all['Name'].map(road_to_path)
    
    gdf_roads = gdf_all[gdf_all['full_path'].notna()].copy()
    
    return gdf_roads

def get_points_dataframe(file_path, points):
    """
    Собирает все точки из KML и соединяет их с путями из points.
    """
    file_path = Path(file_path)
    all_points = []
    for layer in fiona.listlayers(str(file_path)):
        gdf = gpd.read_file(file_path, layer=layer)
        pts = gdf[gdf.geom_type == 'Point']
        all_points.append(pts)
    
    if not all_points:
        return None
    
    gdf_all = pd.concat(all_points, ignore_index=True)
    
    point_to_path = {p['name']: p['path'] for p in points}
    gdf_all['full_path'] = gdf_all['Name'].map(point_to_path)
    
    gdf_points = gdf_all[gdf_all['full_path'].notna()].copy()
    
    if not gdf_points.empty:
        gdf_points['Name'] = gdf_points['Name'].apply(fix_quotes)
    
    return gdf_points

# ============================================================================
# ОПРЕДЕЛЕНИЕ ПРИНАДЛЕЖНОСТИ
# ============================================================================
def get_ownership(path):
    """
    Определяет принадлежность дороги по полному пути.
    """
    path_lower = path.lower()
    
    if 'федеральные' in path_lower:
        return 'федеральная'
    elif 'региональные' in path_lower:
        return 'региональная'
    elif 'местные' in path_lower:
        return 'местная'
    elif 'частные' in path_lower:
        return 'частная'
    elif 'лесные' in path_lower:
        return 'лесная'
    elif 'ведомственные' in path_lower:
        return 'ведомственная'
    else:
        return 'не определена'

# ============================================================================
# ГЕОДЕЗИЧЕСКИЕ РАСЧЕТЫ
# ============================================================================
geod = Geod(ellps='WGS84')

def calculate_length(row):
    """
    Рассчитывает длину дороги геодезическим методом.
    """
    coords = list(row.geometry.coords)
    total_length = 0
    
    for i in range(len(coords) - 1):
        lon1, lat1 = coords[i][:2]
        lon2, lat2 = coords[i+1][:2]
        _, _, distance = geod.inv(lon1, lat1, lon2, lat2)
        total_length += distance
    
    return round(total_length / 1000, 2)

def decimal_to_dms(coord, is_latitude):
    """
    Преобразует десятичные градусы в формат градусы/минуты/секунды.
    """
    if is_latitude:
        direction = "N" if coord >= 0 else "S"
    else:
        direction = "E" if coord >= 0 else "W"
    
    coord = abs(coord)
    degrees = int(coord)
    minutes_full = (coord - degrees) * 60
    minutes = int(minutes_full)
    seconds = (minutes_full - minutes) * 60
    
    return f"{direction}{degrees}°{minutes:02d}'{seconds:.4f}\""

def get_coordinates(row):
    """
    Извлекает координаты начала и конца линии в формате DMS.
    """
    coords = list(row.geometry.coords)
    lon_start, lat_start = coords[0][:2]
    lon_end, lat_end = coords[-1][:2]
    
    return {
        'Начало (широта)': decimal_to_dms(lat_start, is_latitude=True),
        'Начало (долгота)': decimal_to_dms(lon_start, is_latitude=False),
        'Конец (широта)': decimal_to_dms(lat_end, is_latitude=True),
        'Конец (долгота)': decimal_to_dms(lon_end, is_latitude=False)
    }

# ============================================================================
# ПАРСИНГ DESCRIPTION
# ============================================================================
def parse_description(desc_text):
    """
    Парсит поле description и возвращает словарь с атрибутами.
    """
    if pd.isna(desc_text) or not isinstance(desc_text, str):
        return {
            'покрытие': '',
            'принадлежность': '',
            'осевая_нагрузка': None,
            'категория': '',
            'ширина': ''
        }
    
    result = {}
    for line in desc_text.split('\n'):
        if ':' in line:
            key, value = line.split(':', 1)
            result[key.strip()] = value.strip()
    
    ownership = result.get('Принадлежность', '')
    if ownership:
        ownership = fix_quotes(ownership)
    
    axle_load_str = result.get('Осевая нагрузка', '')
    if axle_load_str:
        try:
            axle_load = float(axle_load_str.replace(',', '.'))
        except (ValueError, TypeError):
            axle_load = None
    else:
        axle_load = None
    
    return {
        'покрытие': result.get('Покрытие', ''),
        'принадлежность': ownership,
        'осевая_нагрузка': axle_load,
        'категория': result.get('Категория', ''),
        'ширина': result.get('Ширина', '')
    }

# ============================================================================
# ОБРАБОТКА ТЕКСТА
# ============================================================================
def fix_quotes(text):
    """
    Исправляет кавычки в тексте: заменяет " на « » по контексту.
    """
    text = text.strip()
    result = []
    
    for i, char in enumerate(text):
        if char != '"':
            result.append(char)
            continue
        
        prev_char = text[i-1] if i > 0 else None
        next_char = text[i+1] if i < len(text)-1 else None
        
        prev_is_significant = prev_char and (prev_char.isalpha() or prev_char.isdigit())
        next_is_significant = next_char and (next_char.isalpha() or next_char.isdigit())
        
        if next_is_significant:
            result.append('«')
        elif prev_is_significant:
            result.append('»')
        else:
            result.append('"')
    
    return ''.join(result)

def split_road_name(name):
    """
    Разделяет название дороги на номер и чистое название.
    """
    match = re.search(r'^.{0,10}\d\. ', name)
    if match:
        return name[:match.end()-2], name[match.end():]
    return "", name

def final_text_cleanup(text):
    """
    Финальная зачистка: заменяет две подряд идущие »» на одну.
    """
    if isinstance(text, str):
        return text.replace('»»', '»')
    return text