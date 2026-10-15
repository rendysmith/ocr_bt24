# 🤖 OCR Bitrix24 RPA Bot

**Автоматическое распознавание бухгалтерских документов.**  
Загрузка из **Bitrix24** → OCR в **Entera** → выгрузка результатов обратно.

---

## Быстрый старт

```bash
cp .env.example .env        # заполни credentials
cp config.ini.example config.ini
pip install -r requirements.txt
python main.py
```

---

## Как это работает

```
Bitrix24                              Entera
┌────────────┐   ┌──────────────┐   ┌──────────┐
│  Исходные   │──►│  Загрузка    │──►│   OCR    │
│  PDF       │   │  на диск     │   │распозна-  │
│            │   │              │   │  вание   │
└────────────┘   └──────────────┘   └────┬─────┘
       ▲                                 │
       │          ┌──────────────┐       │
       │          │  Результаты   │◄──────┘
       └──────────│  JPG → PDF   │
                  │  загрузка    │
                  └──────────────┘
```

**7 шагов обработки:**

| Шаг | Что делает | Модуль |
|-----|-----------|--------|
| 1 | Создаёт папки в Bitrix24 на месяц вперёд | `bitrix_folder.py` |
| 2 | Скачивает PDF во временную папку | `bitrix_file.py` |
| 3 | Отправляет файлы в Entera, ждёт распознавания | `entera_ocr.py` |
| 4 | Склеивает JPG → PDF, загружает в Bitrix24 | `bitrix_file.py` |
| 5 | Перемещает исходники в архив/не распознано | `bitrix_file.py` |
| 6 | Удаляет временные файлы | `main.py` |
| 7 | Рассылает email-уведомления | `email.py` |

---

## Структура проекта

```
ocr_bt24/
│
├── main.py                      # 🎯 Точка входа — запуск пайплайна
│
├── utils/                       # 🧰 Все модули
│   ├── settings.py              #   Конфигурация (Bitrix24 URL из .env)
│   ├── db.py                    #   MSSQL (pyodbc)
│   ├── email.py                 #   SMTP / Outlook уведомления
│   │
│   ├── bitrix_client.py         #   Bitrix24: получение аккаунтов
│   ├── bitrix_file.py           #   Bitrix24: скачивание / загрузка / перемещение
│   ├── bitrix_folder.py         #   Bitrix24: создание / перемещение папок
│   │
│   ├── entera_auth.py           #   Entera: JWT-аутентификация
│   ├── entera_ocr.py            #   Entera: отправка на OCR + сбор результатов
│   │
│   ├── doc_types.py             #   Словарь типов документов
│   └── pdf_merge.py             #   Склейка JPG → PDF
│
├── .env.example                 # 🔐 Шаблон переменных окружения
├── config.ini.example           # 🔐 Шаблон конфига (MSSQL, email)
├── requirements.txt             # 📦 Зависимости
├── .gitignore
└── README.md
```

---

## Настройка

### 1. Переменные окружения (`.env`)

```ini
# Entera
entera_login=ivan@company.ru
entera_pass=secret

# Bitrix24 REST API
url_bitrix=https://bitrix.ubpo.ru/rest/899/your_token
access_token=your_token

# UBPO card API
url_ubpo_card=https://web01.ubpo.ru/OperBDOhttp/hs/api/...
```

### 2. Конфиг (`config.ini`)

```ini
[email]
password = smtp_password

[mssql]
server = sql.company.ru
database = RPA_OCR
username = sa
password = secret
```

---

## Зависимости

| Пакет | Зачем |
|-------|-------|
| `requests` | HTTP к Bitrix24 и Entera |
| `aiohttp` | Асинхронная отправка файлов |
| `pyodbc` | MSSQL |
| `pandas` + `sqlalchemy` | Работа с данными |
| `img2pdf` | JPG → PDF |
| `python-dotenv` | Загрузка `.env` |
| `pywin32` | Outlook (Windows, опционально) |
| `pretty-html-table` | HTML-таблицы для писем |

---

## Системные требования

- **Python 3.10+**
- **Windows** (Outlook/win32com опциональны, SMTP работает везде)
- **ODBC Driver** для MSSQL
- Доступ к API: Bitrix24, Entera, UBPO Card

---

## Разработка

```bash
python -m venv .venv
source .venv/bin/activate     # или .venv\Scripts\activate
pip install -r requirements.txt
```

Все модули в `utils/` — импортируй по необходимости:

```python
from utils.entera_auth import get_auth_cookies_sync
from utils.bitrix_folder import create_folder
from utils.doc_types import trans  # UTD → "УПД"
```
