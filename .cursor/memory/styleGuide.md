# Руководство по стилю кода

## Общие принципы
- Консистентность (единообразие)
- Читаемость важнее всего
- KISS (Keep It Simple)
- DRY (Don't Repeat Yourself)

## Python
- **Отступы**: 4 пробела
- **Naming**: `snake_case` (переменные, методы), `PascalCase` (классы), `UPPER_SNAKE_CASE` (константы)
- **Docstrings**: обязательны для публичных API
- **Импорты**: стд. библиотека → сторонние пакеты → внутренние модули

```python
import os  # стандартная библиотека
from typing import Dict, Optional

import aiohttp  # сторонний пакет

from config.settings import API_KEY  # внутренний модуль


class ReceiptParser:
    """Краткое описание класса."""
    
    async def parse_receipt(self, image_data: bytes) -> Dict:
        """Парсит данные чека из изображения."""
        try:
            result = await self._process_image(image_data)
            return result
        except Exception as e:
            logger.error(f"Ошибка парсинга чека: {e}")
            return {}
```

## JavaScript (WebApp)
- **Отступы**: 2 пробела
- **Naming**: `camelCase` (переменные, функции), `PascalCase` (классы), `UPPER_SNAKE_CASE` (константы)
- **Строки**: одинарные кавычки (`'`)
- **Точки с запятой**: обязательны

```javascript
const API_URL = '/api/receipt';

function calculateTotal(items) {
  let total = 0;
  for (const item of items) {
    total += item.price * item.quantity;
  }
  return total.toFixed(2);
}

// Обработка ошибок
try {
  const data = await fetch(`${API_URL}/${messageId}`);
  return data.json();
} catch (error) {
  console.error('Error:', error);
}
```

## HTML/CSS
- HTML5 семантические элементы
- Адаптивный дизайн
- CSS-переменные для цветов и размеров
- Осмысленные имена классов

## REST API
- `GET` (чтение), `POST` (создание), `PUT`/`PATCH` (обновление), `DELETE` (удаление)
- URL в нижнем регистре с дефисами
- Вложенность через путь: `/api/receipt/{id}/items`

## Telegram API
- Асинхронная обработка через aiogram 3.x
- Отдельные модули для разных типов обработчиков
- Избегать блокирующих операций

## Работа с данными
- `Decimal` для денежных расчетов
- Строковые ключи в JSON
- Валидация входных данных
- Читать/писать файлы через контекстные менеджеры

## Git
- Коммиты: `категория: краткое описание` (feat, fix, docs, style, refactor)
- Одна логическая единица на коммит
- Feature-ветки: `feature/название` 