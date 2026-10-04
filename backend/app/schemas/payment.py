from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class CreatePaymentOrderRequest(BaseModel):
    organization_id: str = Field(..., description="UUID of the organization to upgrade")
    customer_email: Optional[str] = Field(None, description="Optional email for receipt delivery")


class PaymentOrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    amount: float
    currency: str
    status: str
    service_name: str
    confirmation_url: Optional[str] = None
    paid_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    receipt_status: str
    receipt_url: Optional[str] = None
    created_at: datetime


class PaymentConfigResponse(BaseModel):
    payments_enabled: bool
    pro_monthly_price_rub: float
    pro_days: int


class MarkReceiptRequest(BaseModel):
    receipt_url: str = Field(..., description="Official HTTPS receipt URL from «Мой налог»")


class PaymentTransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    payment_order_id: str
    operation_type: str
    amount: float
    currency: str
    status: str
    created_at: datetime

