# Настройка окружений для Split Check Bot (упрощенная)

## 🎯 Обзор

Проект поддерживает два окружения:
- **Development** - для разработки и тестирования новых функций
- **Production** - для реальных пользователей

## 🔧 Настройка переменных окружения

### Development (.env)
```bash
ENVIRONMENT=development
ENABLE_TEST_COMMANDS=true
DEBUG=true
LOG_LEVEL=DEBUG
TELEGRAM_BOT_TOKEN=<test_splitix_bot_token>
WEBAPP_URL=https://test-splitix-bot-e78b4714c182.herokuapp.com
```

### Production (.env)
```bash
ENVIRONMENT=production
ENABLE_TEST_COMMANDS=false
DEBUG=false
LOG_LEVEL=INFO
TELEGRAM_BOT_TOKEN=<splitix_bot_token>
WEBAPP_URL=https://bot.splitix.ru
```

## 🤖 Создание ботов

Для каждого окружения нужен отдельный бот:

1. **Production Bot**: `@Splitix_bot`
   - Основной бот для пользователей
   - Команды: `/start`, `/help`, `/split`

2. **Development Bot**: `@test_splitix_bot`
   - Для разработки и тестирования
   - Команды: `/start`, `/help`, `/split`, `/testbothwebapp`

## 🚀 Деплой на Heroku

### Создание приложений
```bash
# Production
heroku create splitix-bot

# Development
heroku create test-splitix-bot
```

### Настройка переменных окружения
```bash
# Production
heroku config:set ENVIRONMENT=production ENABLE_TEST_COMMANDS=false --app splitix-bot

# Development
heroku config:set ENVIRONMENT=development ENABLE_TEST_COMMANDS=true --app test-splitix-bot
```

## 📁 Структура файлов

```
webapp/frontend/
├── index.html              # Основной Mini App (все окружения)
└── debug/                  # Отладочные инструменты (только dev)
    ├── test_webapp.html    # Тестовая страница
    └── logs.html           # Логи (будущее)
```

## 🔒 Безопасность

### Доступ к тестовым функциям
- **Production**: тестовые команды и страницы недоступны (404)
- **Development**: полный доступ к отладочным инструментам

### Логирование
- **Production**: только INFO и выше
- **Development**: DEBUG логи включены

## 🔄 Workflow разработки

1. **Разработка**: работаем в ветке `feature/*` → тестируем на DEV боте
2. **Тестирование**: мержим в `develop` → автодеплой на DEV
3. **Production**: мержим в `main` → автодеплой на PRODUCTION

## 🧪 Тестирование

### Development
- Все функции доступны
- Детальное логирование
- Быстрые итерации
- Финальное тестирование перед релизом

### Production
- Только стабильные функции
- Минимальное логирование
- Мониторинг ошибок

## 📊 Мониторинг

### Heroku Logs
```bash
# Production
heroku logs --tail --app splitix-bot

# Development
heroku logs --tail --app test-splitix-bot
```

### Метрики
- **Production**: бизнес-метрики, ошибки
- **Development**: все логи включая отладочные 