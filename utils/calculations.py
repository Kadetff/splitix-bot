from decimal import Decimal
from typing import Dict, Any, List, Tuple

def calculate_item_total(
    item: Dict[str, Any],
    count: int,
    is_weight_item: bool = False
) -> Tuple[Decimal, str]:
    """Рассчитывает общую стоимость товара с учетом скидок."""
    openai_quantity = item.get("quantity_from_openai", 1)
    total_amount_openai = item.get("total_amount_from_openai")
    unit_price_openai = item.get("unit_price_from_openai")
    
    # Расчет базовой стоимости
    if is_weight_item and total_amount_openai is not None:
        item_total = total_amount_openai
    elif unit_price_openai is not None:
        item_total = unit_price_openai * Decimal(count)
    elif total_amount_openai is not None and openai_quantity > 0:
        try:
            unit_price = total_amount_openai / Decimal(str(openai_quantity))
            item_total = unit_price * Decimal(count)
        except Exception:
            item_total = total_amount_openai
    else:
        return Decimal("0.00"), ""
    
    # Применение скидок
    discount_info = ""
    if item.get("discount_percent") is not None:
        discount_amount = (item_total * item["discount_percent"] / Decimal("100")).quantize(Decimal("0.01"))
        item_total -= discount_amount
        discount_info = f" (скидка {item['discount_percent']}%)"
    elif item.get("discount_amount") is not None:
        if openai_quantity > 0:
            item_discount = (item["discount_amount"] * Decimal(count) / Decimal(str(openai_quantity))).quantize(Decimal("0.01"))
            item_total -= item_discount
            discount_info = f" (скидка {item_discount:.2f})"
    
    return item_total, discount_info

def calculate_total_with_charges(
    items: List[Dict[str, Any]],
    user_counts: Dict[str, int],
    service_charge_percent: float = None,
    actual_discount_percent: float = None,
    total_discount_amount: Decimal = None
) -> Tuple[Decimal, str]:
    """Рассчитывает итоговую сумму с учетом сервисного сбора и скидок."""
    total_sum = Decimal("0.00")
    summary = ""
    
    # Расчет общей суммы всех позиций для распределения скидки
    total_check_sum = sum(
        item.get("total_amount_from_openai", Decimal("0.00"))
        for item in items
    )
    
    # Формируем список выбранных товаров и считаем сумму
    for idx_str, count in user_counts.items():
        if count > 0:
            idx = int(idx_str)
            item = items[idx]
            description = item.get("description", "N/A")
            
            # Расчет стоимости
            unit_price = item.get("unit_price_from_openai")
            total_amount = item.get("total_amount_from_openai")
            
            if unit_price is not None:
                item_total = unit_price * Decimal(count)
            elif total_amount is not None:
                item_total = total_amount
            else:
                continue
            
            # Применяем скидки на товар, если есть
            discount_info = ""
            if item.get("discount_percent") is not None:
                discount_amount = (item_total * item["discount_percent"] / Decimal("100")).quantize(Decimal("0.01"))
                item_total -= discount_amount
                discount_info = f" (скидка {item['discount_percent']}%)"
            elif item.get("discount_amount") is not None:
                item_discount = item["discount_amount"]
                item_total -= item_discount
                discount_info = f" (скидка {item_discount:.2f})"
            
            # Добавляем позицию в итог
            total_sum += item_total
            summary += f"- {description}: {count} шт. = {item_total:.2f}{discount_info}\n"
    
    # Добавляем информацию о сервисном сборе
    if service_charge_percent is not None:
        service_amount = (total_sum * Decimal(str(service_charge_percent)) / Decimal("100")).quantize(Decimal("0.01"))
        total_sum += service_amount
        summary += f"\n<b>Плата за обслуживание ({service_charge_percent}%): {service_amount:.2f}</b>"
    
    # Добавляем информацию об общей скидке
    if actual_discount_percent is not None and actual_discount_percent > 0:
        discount_amount = (total_sum * Decimal(str(actual_discount_percent)) / Decimal("100")).quantize(Decimal("0.01"))
        total_sum -= discount_amount
        summary += f"\n<b>Скидка ({actual_discount_percent}%): -{discount_amount:.2f}</b>"
    elif total_discount_amount is not None and total_check_sum > 0:
        user_discount = (total_discount_amount * total_sum / total_check_sum).quantize(Decimal("0.01"))
        total_sum -= user_discount
        summary += f"\n<b>Скидка: -{user_discount:.2f}</b>"
    
    summary += f"\n\n<b>Итоговая сумма: {total_sum:.2f}</b>"
    
    return total_sum, summary 