from decimal import Decimal
from typing import Dict, Any, Optional, List, Tuple

def format_item_line(item: Dict[str, Any]) -> str:
    """Форматирует строку товара для сообщения"""
    description = item.get("description", "N/A")
    quantity = item.get("quantity_from_openai", 1)
    unit_price = item.get("unit_price_from_openai")
    total_amount = item.get("total_amount_from_openai")
    
    if quantity == 1 and total_amount is not None and unit_price is not None:
        price_diff = abs(total_amount - unit_price)
        if price_diff > Decimal("0.01"):
            return f"• {description}: {total_amount:.2f}\n"
    
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