# Чек-лист настройки окружений (упрощенный)

## 🤖 1. Создание ботов в BotFather

- [x] **Production Bot**: `@Splitix_bot`
  - Команда: `/newbot`
  - Имя: `Splitix Bot`
  - Username: `Splitix_bot`
  - ✅ Токен сохранен для production

- [x] **Development Bot**: `@test_splitix_bot`
  - Команда: `/newbot`
  - Имя: `Test Splitix Bot`
  - Username: `test_splitix_bot`
  - ✅ Токен сохранен для development

## 🌳 2. Создание веток в GitHub

```bash
# Создаем ветку develop из main
git checkout main
git checkout -b develop
git push -u origin develop
```

## 🚀 3. Создание приложений в Heroku

```bash
# Production
heroku create splitix-bot

# Development
heroku create test-splitix-bot
```

## ⚙️ 4. Настройка переменных окружения

### Production
```bash
heroku config:set \
  ENVIRONMENT=production \
  ENABLE_TEST_COMMANDS=false \
  DEBUG=false \
  LOG_LEVEL=INFO \
  TELEGRAM_BOT_TOKEN=<splitix_bot_token> \
  OPENAI_API_KEY=<your_openai_key> \
  WEBAPP_URL=https://bot.splitix.ru \
  --app splitix-bot
```

### Development
```bash
heroku config:set \
  ENVIRONMENT=development \
  ENABLE_TEST_COMMANDS=true \
  DEBUG=true \
  LOG_LEVEL=DEBUG \
  TELEGRAM_BOT_TOKEN=<test_splitix_bot_token> \
  OPENAI_API_KEY=<your_openai_key> \
  WEBAPP_URL=https://test-splitix-bot-e78b4714c182.herokuapp.com \
  --app test-splitix-bot
```

## 🔄 5. Настройка автодеплоя

### В Heroku Dashboard:

**Production App:**
- [ ] Deploy → GitHub → Connect to repository
- [ ] Automatic deploys → Enable for `main` branch
- [ ] Wait for CI to pass before deploy ✅

**Development App:**
- [ ] Deploy → GitHub → Connect to repository
- [ ] Automatic deploys → Enable for `develop` branch
- [ ] Wait for CI to pass before deploy ✅

## 🧪 6. Тестирование

### Development
- [ ] Деплой в `develop` ветку
- [ ] Проверить команды: `/start`, `/help`, `/split`, `/testbothwebapp`
- [ ] Проверить доступ к `/test_webapp`
- [ ] Финальное тестирование новых функций

### Production
- [ ] Мерж `develop` → `main`
- [ ] Проверить команды: `/start`, `/help`, `/split`
- [ ] Убедиться что `/testbothwebapp` недоступна
- [ ] Убедиться что `/test_webapp` возвращает 404

## 📊 7. Мониторинг

### Логи
```bash
# Production
heroku logs --tail --app splitix-bot

# Development
heroku logs --tail --app test-splitix-bot
```

### Проверка переменных
```bash
# Проверить настройки
heroku config --app splitix-bot
heroku config --app test-splitix-bot
```

## ✅ Готово!

После выполнения всех пунктов у вас будет:
- 2 бота для разных окружений
- 2 ветки в GitHub с автодеплоем
- 2 приложения в Heroku с правильными настройками
- Безопасное разделение тестовых и продакшн функций 