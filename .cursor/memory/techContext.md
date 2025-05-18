# Технический контекст Split Check Bot

## Стек технологий
- **Бот**: Python 3.12, aiogram 3.0+, asyncio, aiohttp
- **AI**: OpenAI API (GPT-4 Vision), модель gpt-4.1-mini
- **Веб**: Flask 2.x, Telegram WebApp SDK, Vanilla JS
- **Деплой**: Heroku Container Runtime
- **Данные**: JSON-файлы (MVP), планируется PostgreSQL/Redis/S3

## Архитектура
1. **Telegram Bot (main.py)** – обработка сообщений и команд
2. **WebApp Server (Flask)** – API для работы с чеками
3. **WebApp Client (JS)** – интерфейс выбора позиций
4. **Сервисы** – OCR чеков, бизнес-логика распределений

## Потоки данных
- **Распознавание**: Фото → Бот → OpenAI → Структурированные данные
- **Выбор товаров**: Бот → WebApp → Выбор позиций → Возврат в бот
- **Расчет**: Выборы пользователей → Расчет с учетом скидок → Результат
- **Взаиморасчеты**: Выборы → Ввод платежей → Simplify Debts → Кто-кому-сколько

## Ключевые особенности
- **Формат данных**: JSON-структуры для чеков и выборов позиций
- **Алгоритмы**: Пропорциональное распределение скидок, Simplify Debts
- **Валюта**: Decimal для точных денежных расчетов
- **TTL данных**: 7 дней хранения, автоочистка

## API-эндпоинты
- `GET/POST /api/receipt/{message_id}` – получение/сохранение чека
- `POST /api/selection/{message_id}` – сохранение выбора пользователя

## Режимы работы
- **Индивидуальный**: фото чека → личный выбор позиций
- **Групповой**: `/split` → параллельный выбор → взаиморасчеты

## Конфигурация
- **Env переменные**: TELEGRAM_BOT_TOKEN, OPENAI_API_KEY, WEBAPP_URL, PORT, MODEL_PROVIDER

## Планируемые улучшения
- **Хранение**: PostgreSQL, Redis (сессии), S3 (медиа)
- **Frontend**: React + TypeScript
- **Задачи**: Celery/RQ для асинхронных операций
- **DevOps**: Docker, GitHub Actions, структурированное логирование

## Структура репозитория (актуально)

```
split_check/
├── .env                       # Конфигурация (токены, ключи)
├── .gitignore                 # Игнорируемые файлы
├── README.md                  # Документация проекта
├── requirements.txt           # Зависимости
├── Procfile                   # Конфигурация для Heroku
├── main.py                    # Точка входа для Telegram-бота
├── config/                    # Конфигурация приложения
│   ├── __init__.py
│   └── settings.py            # Настройки приложения
├── handlers/                  # Обработчики событий Telegram
│   ├── __init__.py
│   ├── photo.py               # Фото и OCR чеков
│   ├── callbacks.py           # Callback-кнопки и подтверждения
│   ├── commands.py            # Команды /start, /help, /split
│   ├── webapp.py              # Интеграция с Mini App
│   └── inline.py              # Inline-режим Telegram
├── models/                    # Модели данных
│   ├── __init__.py
│   └── receipt.py             # Модели данных чеков
├── services/                  # Бизнес-логика
│   ├── __init__.py
│   ├── openai_service.py      # Работа с OpenAI Vision
│   └── receipt_service.py     # Бизнес-логика чеков
├── utils/                     # Вспомогательные утилиты
│   ├── __init__.py
│   ├── keyboards.py           # Генерация клавиатур
│   ├── helpers.py             # Вспомогательные функции
│   ├── calculations.py        # Расчёты итогов и скидок
│   ├── formatters.py          # Форматирование сообщений
│   ├── state.py               # Управление состоянием FSM
│   └── logging.py             # Структурное логирование
├── webapp/                    # Mini App (Telegram WebApp)
│   ├── README.md             # Документация WebApp
│   ├── run_webapp.py         # Точка входа для запуска WebApp
│   ├── backend/              # Backend часть (Flask)
│   │   └── server.py         # Flask backend для Mini App
│   ├── frontend/             # Frontend часть
│   │   └── index.html        # Фронтенд Mini App
│   └── data/                 # Данные приложения
│       └── receipt_data.json # Данные о чеках и выборах пользователей
├── docs/                      # Документация проекта
├── credentials/               # Конфиденциальные данные
└── app_env/                   # Переменные окружения
``` 