import logging
import aiohttp
from decimal import Decimal
from typing import Dict, Any

logger = logging.getLogger(__name__)

async def check_api_health(session: aiohttp.ClientSession, base_url: str) -> bool:
    """Проверяет доступность API"""
    try:
        async with session.get(f"{base_url}/health") as response:
            if response.status != 200:
                return False
            data = await response.json()
            return data.get("status") == "ok"
    except Exception as e:
        logger.error(f"Ошибка при проверке API: {e}")
        return False

def prepare_data_for_api(data: Dict[str, Any]) -> Dict[str, Any]:
    """Подготавливает данные для отправки в API"""
    serializable_data = {}
    for key, value in data.items():
        if key == "items":
            serializable_data[key] = [
                {k: float(v) if isinstance(v, Decimal) else v 
                 for k, v in item.items()}
                for item in value
            ]
        elif isinstance(value, Decimal):
            serializable_data[key] = float(value)
        else:
            serializable_data[key] = value
    return serializable_data 