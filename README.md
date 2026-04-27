# KML to Excel — автоматическая ведомость дорог

Консольное приложение для преобразования KML файлов (из SAS.Планет) в форматированную Excel-ведомость с анализом дорожной сети.

## Возможности

- Рекурсивный парсинг KML — находит дороги и точки интереса по папкам
- Геодезический расчёт длины (pyproj) — точность как в SAS.Планет
- Анализ связей — определяет, откуда и куда ведёт дорога (через буфер 50 м)
- Автоматическое форматирование Excel: шрифты, границы, цветовая кодировка по типам дорог
- Гиперссылки между листами
- Копирование шаблонного листа "аб1" для каждой дороги
- Очистка кавычек, разделение названий на номер и имя

## Структура проекта

| Файл | Назначение |
|------|------------|
| `main.py` | Главный скрипт, оркестратор |
| `road_extractor.py` | Парсинг KML, геодезия, описание |
| `road_analyzer.py` | Анализ связей (откуда-куда) |
| `excel_exporter.py` | Генерация Excel с форматированием |
| `constants.py` | Системные константы |
| `logger_config.py` | Логирование |

## Установка

```bash
pip install -r requirements.txt
```

## Сборка .exe

Для создания исполняемого файла используйте PyInstaller:

```bash
pyinstaller --noconfirm --onedir --console --add-data "data;data" --collect-all fiona --collect-all pyogrio --hidden-import "geopandas" --hidden-import "shapely" --hidden-import "pyproj" --hidden-import "openpyxl" main.py
```

Примечание: Если папка `data` не копируется автоматически, используйте абсолютный путь:

```bash
pyinstaller --noconfirm --onedir --console --add-data "C:\путь\к\проекту\data;data/" --collect-all fiona --collect-all pyogrio --hidden-import "geopandas" --hidden-import "shapely" --hidden-import "pyproj" --hidden-import "openpyxl" "C:\путь\к\проекту\main.py"
```

После сборки готовая программа находится в папке `dist/main/`. Распространяйте всю папку целиком.