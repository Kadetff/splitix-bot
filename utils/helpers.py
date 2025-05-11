from decimal import Decimal, InvalidOperation
import logging

logger = logging.getLogger(__name__)

def parse_possible_price(price_value: any) -> Decimal | None:
    """Пытается распарсить значение цены в Decimal, обрабатывая строки с запятыми/точками."""
    if price_value is None: return None
    if isinstance(price_value, (int, float)): 
        return Decimal(str(price_value))
    if isinstance(price_value, str):
        try:
            # Убираем пробелы, заменяем запятые, если это разделитель тысяч - убираем (сложно без контекста)
            # Для простоты предполагаем, что запятая - это десятичный разделитель, если нет точки
            # Или если есть точка, то запятые - это разделители тысяч (удаляем)
            cleaned_str = price_value.strip()
            if '.' in cleaned_str and ',' in cleaned_str:
                 cleaned_str = cleaned_str.replace(',', '') # Удаляем запятые-тысячные
            elif ',' in cleaned_str:
                 cleaned_str = cleaned_str.replace(',', '.') # Заменяем запятую-десятичную на точку
            return Decimal(cleaned_str)
        except InvalidOperation:
            return None
    return None 