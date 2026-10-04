import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from app.services.payment.base import (
    PaymentProvider,
    ProviderPaymentResult,
    ProviderRefundResult,
)


class MockYooKassaProvider(PaymentProvider):
    """
    Deterministic mock provider for automated tests and sandbox simulation.
    Never initiates external network requests or processes real money.
    """

    def __init__(self):
        self.payments: Dict[str, Dict[str, Any]] = {}
        self.refunds: Dict[str, Dict[str, Any]] = {}
        self.should_timeout: bool = False
        self.should_fail: bool = False
        self.failure_status_code: int = 500

    def reset(self):
        self.payments.clear()
        self.refunds.clear()
        self.should_timeout = False
        self.should_fail = False

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
        if self.should_timeout:
            raise TimeoutError("Simulated provider timeout during create_payment")
        if self.should_fail:
            raise RuntimeError(f"Simulated provider HTTP {self.failure_status_code} error")

        pid = f"mock_pay_{uuid.uuid4().hex[:16]}"
        conf_url = f"https://yookassa.ru/checkout/mock/{pid}"

        payment_data = {
            "id": pid,
            "status": "pending",
            "paid": False,
            "amount": {"value": f"{amount:.2f}", "currency": currency.upper()},
            "confirmation": {"type": "redirect", "confirmation_url": conf_url, "return_url": return_url},
            "description": description,
            "metadata": metadata or {},
            "idempotency_key": idempotency_key,
            "customer_email": customer_email,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        self.payments[pid] = payment_data

        return ProviderPaymentResult(
            provider_payment_id=pid,
            status="pending",
            confirmation_url=conf_url,
            amount=amount,
            currency=currency.upper(),
            paid=False,
            created_at=payment_data["created_at"],
            metadata=metadata or {},
            raw_response=payment_data
        )

    async def get_payment(self, provider_payment_id: str) -> ProviderPaymentResult:
        if self.should_timeout:
            raise TimeoutError("Simulated provider timeout during get_payment")
        if self.should_fail:
            raise RuntimeError(f"Simulated provider HTTP {self.failure_status_code} error")

        if provider_payment_id not in self.payments:
            raise ValueError(f"Payment {provider_payment_id} not found in mock store")

        p = self.payments[provider_payment_id]
        return ProviderPaymentResult(
            provider_payment_id=p["id"],
            status=p["status"],
            confirmation_url=p.get("confirmation", {}).get("confirmation_url"),
            amount=float(p["amount"]["value"]),
            currency=p["amount"]["currency"],
            paid=p["paid"],
            created_at=p["created_at"],
            metadata=p.get("metadata", {}),
            raw_response=p
        )

    async def refund_payment(
        self,
        provider_payment_id: str,
        amount: float,
        currency: str,
        idempotency_key: str,
        description: Optional[str] = None
    ) -> ProviderRefundResult:
        if self.should_timeout:
            raise TimeoutError("Simulated provider timeout during refund_payment")
        if self.should_fail:
            raise RuntimeError(f"Simulated provider HTTP {self.failure_status_code} error")

        ref_id = f"mock_ref_{uuid.uuid4().hex[:16]}"
        ref_data = {
            "id": ref_id,
            "payment_id": provider_payment_id,
            "status": "succeeded",
            "amount": {"value": f"{amount:.2f}", "currency": currency.upper()},
            "description": description
        }
        self.refunds[ref_id] = ref_data

        if provider_payment_id in self.payments:
            self.payments[provider_payment_id]["status"] = "canceled"

        return ProviderRefundResult(
            provider_refund_id=ref_id,
            provider_payment_id=provider_payment_id,
            status="succeeded",
            amount=amount,
            currency=currency.upper(),
            raw_response=ref_data
        )

    def parse_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        event_type = payload.get("event", "")
        obj = payload.get("object", {})
        return {
            "event_type": event_type,
            "provider_payment_id": obj.get("id"),
            "status": obj.get("status"),
            "paid": obj.get("paid", False),
            "amount": float(obj.get("amount", {}).get("value", 0.0)) if obj.get("amount") else 0.0,
            "currency": obj.get("amount", {}).get("currency", "RUB") if obj.get("amount") else "RUB",
            "metadata": obj.get("metadata", {}),
            "created_at": obj.get("created_at"),
            "raw_object": obj
        }

    # Test Helper Methods
    def simulate_payment_status(self, provider_payment_id: str, status: str, paid: bool = True):
        """Changes mock payment status to succeeded/canceled/etc."""
        if provider_payment_id in self.payments:
            self.payments[provider_payment_id]["status"] = status
            self.payments[provider_payment_id]["paid"] = paid

    def generate_webhook_payload(self, provider_payment_id: str, event: str = "payment.succeeded") -> Dict[str, Any]:
        """Generates realistic YooKassa notification webhook payload."""
        p = self.payments.get(provider_payment_id, {})
        status = "succeeded" if event == "payment.succeeded" else "canceled"
        return {
            "type": "notification",
            "event": event,
            "object": {
                "id": provider_payment_id,
                "status": status,
                "paid": event == "payment.succeeded",
                "amount": p.get("amount", {"value": "499.00", "currency": "RUB"}),
                "description": p.get("description", "Ivently Pro — доступ на 30 дней"),
                "metadata": p.get("metadata", {}),
                "created_at": p.get("created_at", datetime.now(timezone.utc).isoformat())
            }
        }
