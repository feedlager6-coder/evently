from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class ProviderPaymentResult:
    provider_payment_id: str
    status: str
    confirmation_url: Optional[str]
    amount: float
    currency: str
    paid: bool
    created_at: Optional[str]
    metadata: Dict[str, Any]
    raw_response: Dict[str, Any]


@dataclass
class ProviderRefundResult:
    provider_refund_id: str
    provider_payment_id: str
    status: str
    amount: float
    currency: str
    raw_response: Dict[str, Any]


class PaymentProvider(ABC):
    """
    Abstract payment gateway interface.
    Allows swappable implementations (YooKassa, Mock sandbox, etc.) without coupling domain logic.
    """

    @abstractmethod
    async def create_payment(
        self,
        amount: float,
        currency: str,
        description: str,
        return_url: str,
        idempotency_key: str,
        metadata: Optional[Dict[str, Any]] = None,
        customer_email: Optional[str] = None
    ) -> ProviderPaymentResult:
        """Initiates a payment with the provider and returns confirmation details."""
        pass

    @abstractmethod
    async def get_payment(self, provider_payment_id: str) -> ProviderPaymentResult:
        """Fetches verified payment state directly from the provider."""
        pass

    @abstractmethod
    async def refund_payment(
        self,
        provider_payment_id: str,
        amount: float,
        currency: str,
        idempotency_key: str,
        description: Optional[str] = None
    ) -> ProviderRefundResult:
        """Executes a payment refund."""
        pass

    @abstractmethod
    def parse_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Parses and sanitizes incoming webhook payload."""
        pass
