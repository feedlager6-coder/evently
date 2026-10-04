import logging
from typing import Dict, Any, Optional
import httpx

from app.services.payment.base import (
    PaymentProvider,
    ProviderPaymentResult,
    ProviderRefundResult,
)

logger = logging.getLogger("evently.payments.yookassa")


class YooKassaError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None, response_body: Optional[Any] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class YooKassaProvider(PaymentProvider):
    """
    Official YooKassa v3 REST API implementation.
    Uses async httpx with HTTP Basic Auth (shop_id:secret_key) and Idempotence-Key header.
    """

    def __init__(
        self,
        shop_id: str,
        secret_key: str,
        base_url: str = "https://api.yookassa.ru/v3",
        timeout: float = 15.0,
        http_client: Optional[httpx.AsyncClient] = None
    ):
        self.shop_id = shop_id
        self.secret_key = secret_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._custom_client = http_client

    def _get_auth(self) -> httpx.BasicAuth:
        return httpx.BasicAuth(self.shop_id, self.secret_key)

    async def _request(
        self,
        method: str,
        path: str,
        headers: Optional[Dict[str, str]] = None,
        json_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/{path.lstrip('/')}"
        req_headers = {"Content-Type": "application/json"}
        if headers:
            req_headers.update(headers)

        client = self._custom_client
        if client:
            return await self._execute(client, method, url, req_headers, json_data)

        async with httpx.AsyncClient(timeout=self.timeout) as new_client:
            return await self._execute(new_client, method, url, req_headers, json_data)

    async def _execute(
        self,
        client: httpx.AsyncClient,
        method: str,
        url: str,
        headers: Dict[str, str],
        json_data: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        try:
            resp = await client.request(
                method=method,
                url=url,
                auth=self._get_auth(),
                headers=headers,
                json=json_data,
                timeout=self.timeout
            )
        except (httpx.TimeoutException, httpx.NetworkError) as e:
            logger.error("YooKassa network error for %s %s: %s", method, url, e)
            raise YooKassaError(f"YooKassa connection error: {str(e)}") from e

        if resp.status_code not in (200, 201):
            logger.error("YooKassa API HTTP %s: %s", resp.status_code, resp.text)
            try:
                err_data = resp.json()
            except Exception:
                err_data = resp.text
            raise YooKassaError(
                f"YooKassa API error HTTP {resp.status_code}",
                status_code=resp.status_code,
                response_body=err_data
            )

        return resp.json()

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
        body: Dict[str, Any] = {
            "amount": {
                "value": f"{amount:.2f}",
                "currency": currency.upper()
            },
            "confirmation": {
                "type": "redirect",
                "return_url": return_url
            },
            "capture": True,
            "description": description[:128],
            "metadata": metadata or {}
        }

        headers = {"Idempotence-Key": idempotency_key}
        data = await self._request("POST", "/payments", headers=headers, json_data=body)
        return self._parse_payment_response(data)

    async def get_payment(self, provider_payment_id: str) -> ProviderPaymentResult:
        data = await self._request("GET", f"/payments/{provider_payment_id}")
        return self._parse_payment_response(data)

    async def refund_payment(
        self,
        provider_payment_id: str,
        amount: float,
        currency: str,
        idempotency_key: str,
        description: Optional[str] = None
    ) -> ProviderRefundResult:
        body: Dict[str, Any] = {
            "payment_id": provider_payment_id,
            "amount": {
                "value": f"{amount:.2f}",
                "currency": currency.upper()
            }
        }
        if description:
            body["description"] = description[:128]

        headers = {"Idempotence-Key": idempotency_key}
        data = await self._request("POST", "/refunds", headers=headers, json_data=body)

        return ProviderRefundResult(
            provider_refund_id=data.get("id", ""),
            provider_payment_id=data.get("payment_id", provider_payment_id),
            status=data.get("status", "unknown"),
            amount=float(data.get("amount", {}).get("value", amount)),
            currency=data.get("amount", {}).get("currency", currency),
            raw_response=data
        )

    def parse_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parses YooKassa notification event structure:
        {
            "type": "notification",
            "event": "payment.succeeded",
            "object": { ... }
        }
        """
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

    def _parse_payment_response(self, data: Dict[str, Any]) -> ProviderPaymentResult:
        amount_dict = data.get("amount", {})
        val = float(amount_dict.get("value", 0.0)) if amount_dict.get("value") else 0.0
        curr = amount_dict.get("currency", "RUB")

        conf = data.get("confirmation", {})
        conf_url = conf.get("confirmation_url")

        return ProviderPaymentResult(
            provider_payment_id=data.get("id", ""),
            status=data.get("status", "unknown"),
            confirmation_url=conf_url,
            amount=val,
            currency=curr,
            paid=data.get("paid", False),
            created_at=data.get("created_at"),
            metadata=data.get("metadata", {}),
            raw_response=data
        )
