from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class MessageState:
    """Класс для управления состоянием сообщений."""
    
    def __init__(self, ttl: int = 48):
        """
        Инициализация хранилища состояний.
        
        Args:
            ttl: Время жизни состояния в часах (по умолчанию 48 часов)
        """
        self._states: Dict[int, Dict[str, Any]] = {}
        self._timestamps: Dict[int, datetime] = {}
        self._ttl = timedelta(hours=ttl)
    
    def set_state(self, message_id: int, data: Dict[str, Any]) -> None:
        """Устанавливает состояние для сообщения."""
        self._states[message_id] = data
        self._timestamps[message_id] = datetime.now()
        logger.debug(f"Установлено состояние для message_id={message_id}")
    
    def get_state(self, message_id: int) -> Optional[Dict[str, Any]]:
        """Получает состояние сообщения."""
        if message_id not in self._states:
            return None
            
        # Проверяем TTL
        if datetime.now() - self._timestamps[message_id] > self._ttl:
            self.delete_state(message_id)
            return None
            
        return self._states[message_id]
    
    def delete_state(self, message_id: int) -> None:
        """Удаляет состояние сообщения."""
        if message_id in self._states:
            del self._states[message_id]
            del self._timestamps[message_id]
            logger.debug(f"Удалено состояние для message_id={message_id}")
    
    def get_user_selection(
        self,
        message_id: int,
        user_id: int
    ) -> Optional[Dict[str, int]]:
        """Получает выбор пользователя."""
        state = self.get_state(message_id)
        if not state or "user_selections" not in state:
            return None
            
        return state["user_selections"].get(user_id)
    
    def cleanup_expired(self) -> None:
        """Очищает устаревшие состояния."""
        now = datetime.now()
        expired = [
            message_id for message_id, timestamp in self._timestamps.items()
            if now - timestamp > self._ttl
        ]
        
        for message_id in expired:
            self.delete_state(message_id)
            
        if expired:
            logger.info(f"Очищено {len(expired)} устаревших состояний")

# Создаем глобальный экземпляр для использования в обработчиках
message_state = MessageState() 