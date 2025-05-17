from decimal import Decimal, InvalidOperation
import logging

logger = logging.getLogger(__name__)

def parse_possible_price(price_value: any) -> Decimal | None:
    """Упрощенная версия парсинга цены."""
    if price_value is None:
        return None
    if isinstance(price_value, (int, float)):
        return Decimal(str(price_value))
    if isinstance(price_value, str):
        try:
            cleaned_str = price_value.strip().replace(',', '.')
            return Decimal(cleaned_str)
        except InvalidOperation:
            return None
    return None 