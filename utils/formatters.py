from decimal import Decimal
from typing import Dict, Any, Optional, List, Tuple

def format_item_line(item: Dict[str, Any]) -> str:
    """Форматирует строку товара для сообщения"""
    description = item.get("description", "N/A")
    quantity = item.get("quantity_from_openai", 1)
    unit_price = item.get("unit_price_from_openai")
    total_amount = item.get("total_amount_from_openai")
    
    if unit_price is not None:
        return f"• {description}: {unit_price:.2f} × {quantity} = {unit_price * quantity:.2f}\n"
    elif total_amount is not None:
        return f"• {description}: {total_amount:.2f}\n"
    
    return f"• {description}\n"

def calculate_totals(items: List[Dict[str, Any]], 
                    service_charge: Optional[Decimal], 
                    total_discount_amount: Optional[Decimal]) -> Tuple[Decimal, Decimal, Decimal]:
    """Рассчитывает итоговые суммы"""
    total_items_cost = sum(
        item["total_amount_from_openai"] 
        for item in items 
        if item.get("total_amount_from_openai") is not None
    )
    
    total_discounts = total_discount_amount or Decimal("0.00")
    calculated_total = total_items_cost - total_discounts
    
    service_charge_amount = Decimal("0.00")
    if service_charge is not None:
        service_charge_amount = (calculated_total * service_charge / Decimal("100")).quantize(Decimal("0.01"))
        calculated_total += service_charge_amount
    
    actual_discount_percent = Decimal("0.00")
    if total_items_cost > 0:
        actual_discount_percent = (total_discounts * Decimal("100") / total_items_cost).quantize(Decimal("0.01"))
    
    return calculated_total, service_charge_amount, actual_discount_percent 

def format_user_summary(
    username: str,
    items: List[Dict[str, Any]],
    user_counts: Dict[str, int],
    total_sum: Decimal,
    summary: str
) -> str:
    """Форматирует итоговое сообщение для пользователя."""
    user_mention = f"@{username}" if username else "Пользователь"
    return f"<b>{user_mention}, ваш выбор:</b>\n\n{summary}"

def format_final_summary(
    user_results: Dict[int, Dict[str, Any]],
    usernames: Dict[int, str]
) -> str:
    """Форматирует финальный итог с результатами всех участников."""
    summary = "<b>💸 Итог взаиморасчетов</b>\n\n"
    
    # Собираем данные о платежах
    payments = []
    for user_id, result in user_results.items():
        username = usernames.get(user_id, f"Пользователь {user_id}")
        total_sum = Decimal(str(result["total_sum"]))
        payments.append((username, total_sum))
    
    # Сортируем по сумме (от большей к меньшей)
    payments.sort(key=lambda x: x[1], reverse=True)
    
    # Формируем итог
    for username, amount in payments:
        summary += f"{username}: {amount:.2f}\n"
    
    return summary 