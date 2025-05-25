# Стратегия деплоя и разделения окружений (упрощенная)

## 🏗️ Архитектура окружений

### Окружения
```
🔴 PRODUCTION  - @Splitix_bot (реальные пользователи)
🟢 DEVELOPMENT - @test_splitix_bot (разработка + тестирование)
```

### Домены и URL
```
PROD: https://bot.splitix.ru (кастомный домен)
DEV:  https://test-splitix-bot-e78b4714c182.herokuapp.com
```

## 📋 Конфигурация по окружениям

### Production (.env.prod)
```bash
TELEGRAM_BOT_TOKEN=<splitix_bot_token>
WEBAPP_URL=https://bot.splitix.ru
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO
ENABLE_TEST_COMMANDS=false
```

### Development (.env.dev)
```bash
TELEGRAM_BOT_TOKEN=<test_splitix_bot_token>
WEBAPP_URL=https://test-splitix-bot-e78b4714c182.herokuapp.com
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=DEBUG
ENABLE_TEST_COMMANDS=true
```

## 🔄 Workflow разработки

### 1. Ветки Git
- `main` → автодеплой в PRODUCTION
- `develop` → автодеплой в DEVELOPMENT
- `feature/*` → ручной деплой в DEV (опционально)

### 2. Процесс релиза
```
feature/new-function → develop → main
     ↓                   ↓        ↓
   DEV BOT          DEV BOT   PRODUCTION
```

### 3. Тестирование
- **DEV**: разработка + финальное тестирование
- **PROD**: только стабильные версии

## 🧪 Управление тестовыми функциями

### Условная компиляция команд
```python
# config/settings.py
ENABLE_TEST_COMMANDS = os.getenv('ENABLE_TEST_COMMANDS', 'false').lower() == 'true'

# handlers/commands.py
if ENABLE_TEST_COMMANDS:
    @router.message(Command("testbothwebapp"))
    async def test_both_webapp_command(message: Message):
        # тестовая команда
```

### Разделение файлов WebApp
```
webapp/frontend/
├── index.html          # основной Mini App (всегда доступен)
└── debug/              # отладочные инструменты (только в dev)
    ├── test_webapp.html
    └── logs.html
```

## 🚀 GitHub Actions для CI/CD

### Автоматический деплой
```yaml
# .github/workflows/deploy.yml
name: Deploy
on:
  push:
    branches: [main, develop]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Deploy to Heroku
        uses: akhileshns/heroku-deploy@v3.12.12
        with:
          heroku_api_key: ${{secrets.HEROKU_API_KEY}}
          heroku_app_name: ${{env.HEROKU_APP_NAME}}
          heroku_email: ${{secrets.HEROKU_EMAIL}}
          usedocker: true
```

## 📊 Мониторинг и логирование

### Разделение логов по окружениям
```python
# utils/logging.py
def setup_logging():
    level = {
        'production': logging.INFO,
        'development': logging.DEBUG
    }.get(ENVIRONMENT, logging.INFO)
    
    logging.basicConfig(level=level)
```

### Метрики по окружениям
- **PROD**: только критичные ошибки и бизнес-метрики
- **DEV**: все логи включая отладочные

## 🔒 Безопасность

### Разделение секретов
- Отдельные токены ботов для каждого окружения
- Разные API ключи (если нужно)
- Изолированные базы данных

### Доступы
- **PROD**: только maintainer'ы
- **DEV**: все разработчики 