from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, Field, validator

class ReceiptItem(BaseModel):
    """Модель товарной позиции в чеке."""
    description: str
    quantity_from_openai: Decimal = Field(default=1)
    unit_price_from_openai: Optional[Decimal] = None
    total_amount_from_openai: Optional[Decimal] = None
    discount_percent: Optional[Decimal] = None
    discount_amount: Optional[Decimal] = None

    @validator('quantity_from_openai', 'unit_price_from_openai', 'total_amount_from_openai', 
               'discount_percent', 'discount_amount', pre=True)
    def parse_decimal(cls, v):
        """Конвертирует строки и числа в Decimal."""
        if v is None:
            return None
        try:
            return Decimal(str(v))
        except:
            return None

class Receipt(BaseModel):
    """Модель чека."""
    items: List[ReceiptItem]
    service_charge_percent: Optional[Decimal] = None
    total_check_amount: Optional[Decimal] = None
    total_discount_percent: Optional[Decimal] = None
    total_discount_amount: Optional[Decimal] = None
    actual_discount_percent: Optional[Decimal] = None
    user_selections: dict = Field(default_factory=dict)

    @validator('service_charge_percent', 'total_check_amount', 'total_discount_percent', 
               'total_discount_amount', 'actual_discount_percent', pre=True)
    def parse_decimal(cls, v):
        """Конвертирует строки и числа в Decimal."""
        if v is None:
            return None
        try:
            return Decimal(str(v))
        except:
            return None

    def calculate_total(self) -> Decimal:
        """Рассчитывает общую сумму чека."""
        total = sum(
            item.total_amount_from_openai or Decimal('0')
            for item in self.items
        )
        
        if self.total_discount_amount:
            total -= self.total_discount_amount
            
        if self.service_charge_percent:
            service_charge = (total * self.service_charge_percent / Decimal('100')).quantize(Decimal('0.01'))
            total += service_charge
            
        return total.quantize(Decimal('0.01')) 