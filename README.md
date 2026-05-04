# Waste Registry MVP

Мини-приложение на Python для учёта:

- объектов недвижимости `RealEstate`
- объектов образования отходов `WasteObject`
- юридических лиц `LegalEntity`

MVP умеет:

- загружать `xlsx` и `csv`
- нормализовать адреса и ИНН
- раскладывать плоскую таблицу по сущностям
- сохранять данные в SQLite
- работать как локальное desktop-приложение на `Tkinter`
- показывать dashboard, импорт, списки, поиск и карточки
- позволять вручную редактировать и дополнять данные

## Архитектура

Проект разделён по слоям:

- `app/services` — бизнес-логика, импорт, подготовка статистики, заглушки интеграций
- `app/repositories` — доступ к данным через SQLAlchemy
- `app/models` — ORM-модели
- `app/schemas` — Pydantic-схемы для сервисного слоя
- `app/utils` — нормализация строк, ИНН, дат и числовых полей
- `app/gui` — desktop-интерфейс на `Tkinter`
- `app/routes`, `app/templates`, `app/static` — сохранённая web-версия
- `alembic` — миграции БД

## Структура проекта

```text
app/
  desktop.py
  main.py
  config.py
  db.py
  gui/
  models/
  repositories/
  routes/
  schemas/
  services/
  static/
  templates/
  utils/
alembic/
  versions/
tests/
requirements.txt
README.md
```

## Модель данных

### RealEstate

Уникальный объект недвижимости по адресу. Для защиты от дублей используется внутреннее поле `address_key`, которое хранит нормализованный адрес.

### WasteObject

Создаётся по каждой строке импорта и связывает адрес с юридическим лицом.

### LegalEntity

Создаётся по уникальному ИНН. Если ИНН отсутствует, `WasteObject` сохраняется без привязки к юрлицу.

## Импорт

Импорт работает так:

1. Файл читается через `pandas`.
2. Колонки приводятся к каноническим именам через слой `app/services/import_mapping.py`.
3. Значения нормализуются:
   - строки обрезаются
   - пустые значения превращаются в `None`
   - ИНН очищается до цифр
   - адрес приводится к стабильному ключу для дедупликации
4. По каждому уникальному адресу создаётся `RealEstate`.
5. По каждой строке создаётся `WasteObject`.
6. По каждому уникальному ИНН создаётся `LegalEntity`.

## Поддерживаемые поля импорта

Сейчас настроен базовый mapping для колонок:

- `address`
- `district`
- `city`
- `street`
- `building`
- `cadastral_number`
- `area`
- `floors`
- `purpose`
- `object_type`
- `name`
- `category`
- `waste_type`
- `waste_generation_norm`
- `calculation_unit`
- `calculation_value`
- `inn`
- `contract_number`
- `contract_date`
- `legal_entity_name`
- `contact_person`
- `phone`
- `email`

Можно использовать как английские, так и основные русские названия столбцов.

## Заглушки под расширение

Добавлены сервисы-заглушки:

- `app/services/address_normalization_service.py`
- `app/services/rosreestr_service.py`
- `app/services/contract_matching_service.py`

Сейчас они возвращают mock/TODO-результаты и готовы к дальнейшему развитию.

## Локальный запуск как приложение

### 1. Создать окружение

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Применить миграции

```bash
alembic upgrade head
```

### 3. Запустить нативное desktop-приложение

```bash
python -m app.desktop
```

После запуска должно открыться именно локальное desktop-окно.

Если появляется ошибка `No module named '_tkinter'`, значит текущий Python собран без `Tkinter`.
В этом случае нужно:

```bash
python -c "import tkinter as tk; root = tk.Tk(); root.destroy(); print('Tk OK')"
```

Если команда падает, установи Python с поддержкой `Tkinter`, затем пересоздай `.venv` и заново поставь зависимости.

Если нужен старый web-режим, он запускается отдельно:

```bash
python -m app.desktop_web
```

### Где хранится база данных

Desktop-версия хранит SQLite в пользовательской папке:

- macOS: `~/Library/Application Support/WasteRegistryApp/app.db`
- Windows: `%APPDATA%/WasteRegistryApp/app.db`
- Linux: `~/.local/share/WasteRegistryApp/app.db`

Это удобно для переноса и для будущей сборки в `.app` и `.exe`.

## Что есть в desktop-версии

- вкладка `Сводка`
- вкладка `Импорт`
- вкладка `Недвижимость`
- вкладка `Объекты отходов`
- вкладка `Юрлица`
- переключение между несколькими проектами
- редактирование карточек прямо из приложения
- очистка ранее импортированных данных

## Работа с несколькими проектами

Desktop-версия поддерживает несколько независимых проектов. Проект — это отдельная SQLite-база данных.

При первом запуске создаётся проект `Основной проект`, который использует старую базу `app.db`.

В верхней части окна можно:

- выбрать текущий проект из списка
- нажать `Новый проект`
- создать пустую базу для нового набора файлов
- переключаться между проектами без смешивания данных

Каждый новый проект хранится отдельным файлом в папке `projects` внутри пользовательской папки приложения.

Файл со списком проектов:

```text
projects.json
```

## Сборка для другого компьютера

Для обычных пользователей приложение лучше собирать отдельно под каждую ОС:

- на macOS — на Mac
- на Windows — на Windows

Для сборки используется `PyInstaller`.

### macOS

```bash
./scripts/build_macos_app.sh
```

Готовое приложение появится здесь:

```text
dist/WasteRegistryApp.app
```

### Windows

На Windows нужно собирать на Windows:

```bat
scripts\build_windows_app.bat
```

Готовая папка приложения появится здесь:

```text
dist\WasteRegistryApp
```

После этого можно передавать другому человеку:

- zip-архив всей папки `WasteRegistryApp`
- при необходимости файл `app.db`, если нужно перенести уже загруженные данные

## Что можно улучшить дальше

- добавить пагинацию
- добавить валидацию схем импорта под конкретные форматы файлов
- добавить историю импортов
- подключить 2ГИС / Росреестр / договорную базу
- сделать полноценную упаковку под macOS и Windows
