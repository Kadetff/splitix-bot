import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

def create_structured_log(
    event_type: str,
    user_id: int,
    chat_type: str,
    session_id: Optional[str] = None,
    query: Optional[str] = None,
    error: Optional[str] = None,
    model_provider: str = "none",
    elapsed_ms: float = 0,
    additional_data: Optional[Dict[str, Any]] = None
) -> dict:
    """Создает структурированный лог в формате JSON для всего приложения.
    
    Args:
        event_type: Тип события (например, 'inline_query', 'photo_processing', 'webapp_data')
        user_id: ID пользователя
        chat_type: Тип чата (private, group, supergroup)
        session_id: ID сессии (опционально)
        query: Текст запроса (опционально)
        error: Текст ошибки (опционально)
        model_provider: Провайдер модели (none, openai, google, gemini)
        elapsed_ms: Время выполнения в миллисекундах
        additional_data: Дополнительные данные для логирования
    
    Returns:
        dict: Структурированный лог в формате JSON
    """
    log_data = {
        "timestamp": datetime.utcnow().isoformat(),
        "event_type": event_type,
        "user_id": user_id,
        "chat_type": chat_type,
        "elapsed_ms": elapsed_ms,
        "model_provider": model_provider
    }
    
    if session_id:
        log_data["session_id"] = session_id
    if query:
        log_data["query"] = query
    if error:
        log_data["error"] = error
    if additional_data:
        log_data.update(additional_data)
        
    return log_data

def log_event(
    event_type: str,
    user_id: int,
    chat_type: str,
    session_id: Optional[str] = None,
    query: Optional[str] = None,
    error: Optional[str] = None,
    model_provider: str = "none",
    elapsed_ms: float = 0,
    additional_data: Optional[Dict[str, Any]] = None,
    level: str = "info"
) -> None:
    """Логирует событие с использованием структурированного формата.
    
    Args:
        event_type: Тип события
        user_id: ID пользователя
        chat_type: Тип чата
        session_id: ID сессии (опционально)
        query: Текст запроса (опционально)
        error: Текст ошибки (опционально)
        model_provider: Провайдер модели
        elapsed_ms: Время выполнения в миллисекундах
        additional_data: Дополнительные данные
        level: Уровень логирования (info, error, warning, debug)
    """
    log_data = create_structured_log(
        event_type=event_type,
        user_id=user_id,
        chat_type=chat_type,
        session_id=session_id,
        query=query,
        error=error,
        model_provider=model_provider,
        elapsed_ms=elapsed_ms,
        additional_data=additional_data
    )
    
    log_message = json.dumps(log_data)
    
    if level == "error":
        logger.error(log_message, exc_info=bool(error))
    elif level == "warning":
        logger.warning(log_message)
    elif level == "debug":
        logger.debug(log_message)
    else:
        logger.info(log_message) 