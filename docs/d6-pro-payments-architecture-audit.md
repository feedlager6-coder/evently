# D6 — Ivently Pro Payments: Architecture & Provider Selection Audit

> **Document Type:** Production Architecture Reference & Payment Provider Selection Audit  
> **Status:** APPROVED ARCHITECTURAL SPECIFICATION — D6.0.1 REVISED (DO NOT IMPLEMENT PAYMENT CODE YET)  
> **Release:** D6.0.1  
> **Base Commit:** `1df4263`  
> **Current Date:** October 2026  
> **Project:** Ivently (`https://ivently.up.railway.app`)

---

## 1. Executive Summary

Ivently is a Telegram-first city event discovery platform operating on a freemium model. Organizers can create unlimited events, manage venues, and gather subscribers for free. Commercial monetization is focused on the **Ivently Pro** subscription for event organizers, which unlocks:
- Direct Telegram marketing broadcasts (20 broadcasts/month).
- Advanced attendee analytics and conversion funnels.
- Upcoming Pro features: audience segmentation, smart reminders, CRM export, and verified venue badges.

Crucially, **transactional notifications** (event date/time/location changes, moderation updates, publication alerts) are operational, 100% free, and strictly isolated from the commercial marketing broadcast quota.

This revised specification (**D6.0.1**) incorporates essential architectural and legal corrections before D6.1 implementation:
1. Corrects the receipt automation assumption for self-employed accounts.
2. Removes recurring auto-renewals in favor of a clean, one-time purchase model for D6.1.
3. Removes unapproved hardcoded pricing in favor of server-side configuration.
4. Simplifies the domain model by keeping `OrganizationPlan` as the single source of truth without premature abstractions.

---

## 2. D6.0.1 Corrections & Scope Alignment

### Correction 1: YooKassa Self-Employed Receipt Assumption
- **Previous assumption:** The initial draft assumed YooKassa automatically registers income and issues receipts in the Federal Tax Service (ФНС) «Мой налог» application for self-employed individuals.
- **Official documentation verification:** Current official YooKassa documentation (`https://yookassa.ru/developers/payment-acceptance/receipts/basics#self-employed`) states:
  > *«Если вы самозанятый, то при приеме оплаты вам нужно регистрировать свой доход в сервисе Мой налог и передавать сформированный чек покупателю. Это регламентирует закон 422-ФЗ. Вы можете делать это вручную. **В ЮKassa эта опция недоступна**.»*
- **Correction:** We **explicitly remove** any architectural assumption of automated receipt generation by YooKassa.
- **Architectural Policy:** `RECEIPT DECISION = OPEN BUSINESS/LEGAL DECISION`. The D6.1 implementation MUST NOT silently assume automated receipt generation. Automated receipt integrations will not be built until the merchant legal status (self-employed individual vs. individual entrepreneur) and provider contract terms are finalized by the business owner.

### Correction 2: Auto-Renewal Deferred to Future Releases (D6.2+)
- **Scope limitation:** D6.1 will implement **ONLY ONE-TIME PURCHASES**:
  ```
  User taps "Оплатить Pro"
      ↓
  One-time Payment for Fixed Billing Period (e.g. 30 days)
      ↓
  Pro is ACTIVE until expires_at
      ↓
  When expires_at is reached → Organization degrades to Free
      ↓
  User manually purchases again when desired
  ```
- **Explicitly Deferred from D6.1:**
  - Auto-renewal and recurring billing.
  - Card tokenization and saved payment methods (`save_payment_method`).
  - Automatic scheduled card charges.
  - `PAST_DUE` subscription grace state.
  - Automatic payment retry engine.
  - Recurring cancellation workflows.
- **Rationale:** We must first validate organizers' real-world willingness to pay for Pro marketing broadcasts before introducing the legal, UX, and operational complexity of recurring billing.

### Correction 3: Removal of Undecided Hardcoded Pricing
- **Previous assumption:** Hardcoded `PRO_MONTHLY = 990 RUB` and `PRO_YEARLY = 9900 RUB`.
- **Correction:** Neither price was approved by the product owner.
  - All hardcoded price constants are removed.
  - Yearly plan (`PRO_YEARLY`) is removed from D6.1 scope entirely.
  - `PRO_MONTHLY_PRICE_RUB` is defined as a server-side configuration setting in `Settings`. It remains unset/disabled until the project owner explicitly chooses the launch price.
  - The frontend never determines or submits price. Test suites use clearly marked mock values in test fixtures only.

### Correction 4: Simplified D6.1 Domain Model
- **Previous assumption:** Introduced a separate `OrganizationSubscription` entity alongside `OrganizationPlan`.
- **Correction:** For one-time purchases with manual renewal, a separate `OrganizationSubscription` entity introduces unnecessary indirection without immediate business value.
- **D6.1 Domain Model:**
  ```
  Organization
       ↓
  OrganizationPlan (Entitlement Source of Truth)
       ↓
  PaymentOrder (Purchase Intent / Order)
       ↓
  PaymentTransaction (Provider Transaction State)
  ```
  - `OrganizationPlan` remains the single entitlement source of truth.
  - `PaymentOrder` represents a purchase attempt with a specific provider.
  - `PaymentTransaction` records transaction attempts.
  - A verified successful payment extends `OrganizationPlan.expires_at`.

### Correction 5: Pro Extension Rules
- **If the organization currently has active Pro (`expires_at > utc_now()`):**
  A new 30-day purchase extends **from current `expires_at`**:
  $$\text{new\_expires\_at} = \text{current\_expires\_at} + 30\text{ days}$$
- **If the organization is Free or Pro is already expired (`expires_at <= utc_now()` or `None`):**
  The purchase starts **from the current UTC timestamp**:
  $$\text{new\_expires\_at} = \text{utc\_now()} + 30\text{ days}$$
- **Quota & Data Invariant:**
  A new payment **NEVER** resets:
  - Monthly marketing broadcast usage in the current calendar month.
  - Event analytics, views, RSVPs, or subscriber counts.
  - Existing organization data.

---

## 3. Phase 1 — Audit of Existing Pro Implementation

### 3.1 Existing Pro Architecture Components

1. **`OrganizationPlan` Model (`backend/app/models/organization_plan.py`)**:
   - Primary key: `id` (UUIDv4 string).
   - Foreign key: `organization_id` referencing `organizations.id` with `unique=True`, `nullable=False`, `index=True`, `ondelete="CASCADE"`.
   - Fields: `plan` (default `"free"`), `status` (default `"active"`), `starts_at` (DateTime UTC), `expires_at` (DateTime UTC, nullable), `created_at`, `updated_at`.
   - Composite index: `idx_organization_plans_org_status` on `(organization_id, status)`.
   - Multi-tenant boundary: Entitlements belong to the **Organization**, not the user. A single user can own Organization A (Pro) and Organization B (Free).

2. **`EntitlementService` (`backend/app/services/entitlement_service.py`)**:
   - Single source of truth for commercial capabilities.
   - `CAPABILITY_REGISTRY`: Defines platform features and access per plan (`available`, `locked`, `coming_soon`).
   - Dynamic Expiration: `get_organization_plan(...)` dynamically evaluates `expires_at < utc_now()`. If expired, it degrades the effective plan to `"free"` with status `"expired"` in O(1) without requiring cron jobs.
   - Quota Engine: `get_monthly_broadcast_usage(...)` computes marketing broadcast usage from the 1st of the calendar month (00:00:00 UTC). Transactional broadcasts, cancelled broadcasts, and failed broadcasts (0 sent) do not consume the quota.
   - Hard Enforcement Gate: `require_entitlement(...)` and `enforce_broadcast_capacity(...)` enforce plan requirements server-side with structured `HTTP 403 Forbidden` (`ENTITLEMENT_REQUIRED`, `LIMIT_EXCEEDED`).
   - Admin Upsert: `set_organization_plan(...)` allows upserting plan records.

3. **Admin Test & Inspection Endpoints (`backend/app/api/v1/admin.py`)**:
   - `GET /api/v1/admin/organizations`: Lists active organizations with their plan and status.
   - `GET /api/v1/admin/organizations/{org_id}/entitlements`: Inspects an organization's entitlements.
   - `POST /api/v1/admin/organizations/{org_id}/plan`: Switches an organization's plan (`free` <-> `pro`) with optional duration in days.
   - RBAC: All admin endpoints are protected by `require_admin`, verifying Telegram `initData` and checking `user.id in settings.ADMIN_USER_IDS`. Regular users receive `HTTP 403 Forbidden`.

4. **Organizer Endpoints (`backend/app/api/v1/organizer.py`)**:
   - `GET /api/v1/organizer/entitlements?org_id={id}`: Returns public capabilities, limits, and plan status.
   - Strictly enforces organization ownership (`org.owner_user_id == current_user.id`).
   - Rejects non-owners with `HTTP 403 Forbidden` and deleted organizations with `HTTP 404 Not Found`.

5. **Frontend State & Fake Door UX (`OrganizerWorkspace.tsx`, `AdminTab.tsx`)**:
   - Overview Tab: Displays current plan status and «Узнать о Pro» / «Возможности Pro» CTA. If the user is an admin (`isAdmin=true`), an inline test toggle `[ Включить Pro ]` / `[ Вернуть Free ]` is rendered.
   - Broadcasts Tab: Displays Pro banner and limits. Broadcast creation is blocked in the UI if on Free, opening the informative Fake Door Pro sheet.
   - Fake Door Pro Modal: Informative bottom sheet explaining upcoming Pro features and explicitly stating: *«Оплата пока не запущена. Мы готовим Pro. Все базовые функции Ivently навсегда остаются бесплатными для организаторов.»*
   - Zero card capture, zero fake billing transitions.

6. **Trust Boundaries & Tampering Resistance**:
   - **Can the frontend fake Pro?** **NO.** Every broadcast dispatch (`POST /api/v1/organizer/broadcasts`) strictly executes `require_entitlement` and `enforce_broadcast_capacity` against PostgreSQL/SQLite. Client tampering with JS state or localStorage has zero effect.
   - **Can organization owners manipulate plan IDs?** **NO.** There is no user-facing plan modification endpoint.
   - **Does state survive restart/deploy?** **YES.** All records are stored in PostgreSQL on Railway.
   - **Are expired plans handled correctly?** **YES.** When `expires_at` is reached, the backend instantly resolves the effective plan as Free.

---

## 4. Phase 2 — Payment Provider Research (Verified Against Current Docs)

### Provider Comparison Matrix

| № | Dimension | ЮKassa (YooKassa) | T-Bank (Т-Банк) | CloudPayments |
|---|---|---|---|---|
| **1** | **Self-Employed Individual (Самозанятый физлицо)** | **YES** (Program «Платежи для самозанятых») | **NO** for Internet Acquiring (SBP only in personal app, no API) | **NO** (Requires legal entity or IP) |
| **2** | **IP on NPD (ИП на НПД)** | **YES** (Standard merchant acquiring contract) | **YES** (With T-Business current account) | **YES** (Standard merchant acquiring contract) |
| **3** | **LLC / Company (ООО)** | **YES** | **YES** | **YES** |
| **4** | **Payment Methods** | Bank cards (MIR, Visa, MC), SBP, SberPay, T-Pay, YooMoney | Bank cards, SBP, T-Pay, Mir Pay | Bank cards, SBP, T-Pay, SberPay |
| **5** | **Hosted Checkout (Redirect)** | **YES** (`confirmation.type: "redirect"`) | **YES** (`PaymentURL`) | **YES** (Hosted Payment Page) |
| **6** | **Receipts for Self-Employed** | **MANUAL** in «Мой налог» (YooKassa explicitly discontinued automated receipts) | **MANUAL** in «Мой налог» | **N/A** (Only 54-ФЗ cash register for IP/LLC) |
| **7** | **Receipts for IP/LLC (54-ФЗ)** | Supports cloud cash registers (Чеки от ЮKassa / Атол) | Supports cloud cash registers (Т-Бизнес) | Supports cloud cash registers (CloudKassir) |
| **8** | **Refunds Support** | Full & partial refunds via `POST /v3/refunds` | Full & partial refunds via `POST /v2/Cancel` | Full & partial refunds via API |
| **9** | **Idempotency** | Header `Idempotence-Key: <UUID>` | Request field `OrderId` | Request field `InvoiceId` |
| **10** | **Payment Status Verification** | `GET /v3/payments/{payment_id}` | `POST /v2/GetState` | `POST /payments/get` |
| **11** | **Webhook Security Verification** | Official IP subnets whitelist + mandatory callback GET reconciliation | SHA-256 HMAC digest validation against shared password | HMAC-SHA256 signature in `Content-HMAC` header |
| **12** | **Telegram Mini App Compatibility** | **High** (`Telegram.WebApp.openLink` -> Hosted Checkout -> return deep-link) | **High** (`openLink` -> PaymentURL -> return deep-link) | **High** (`openLink` -> HPP -> return deep-link) |
| **13** | **Fees (Estimated)** | Cards: ~3.5% + VAT of fee; SBP: ~1% + VAT. No monthly fee | Cards: ~1.99–2.69%; SBP: ~0.4–0.7%. Current account fee applies | Cards: ~2.7–3.9%. Cash register fee (~1500–2500 ₽/mo) |
| **14** | **Test / Sandbox Mode** | Full sandbox (test `shopId`, test `secretKey`, test cards) | Test terminal, test credentials, test cards | Test public/private keys, test cards |

---

## 5. Phase 3 — Recommendation & Decision Table

| Provider | Self-Employed Individual | IP on NPD | LLC | SBP | Cards | Automated Receipts | Recommendation |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---|
| **ЮKassa** | **YES** | **YES** | **YES** | **YES** | **YES** | **NO (Manual in Мой налог)** | **PRIMARY CANDIDATE** |
| **T-Bank** | NO | YES | YES | YES | YES | 54-ФЗ only | Feasible ONLY if registered as IP |
| **CloudPayments** | NO | YES | YES | YES | YES | 54-ФЗ only | Feasible ONLY if registered as IP/LLC |

### Recommendation Summary
- **ЮKassa remains the primary candidate** because it is the only major acquiring provider supporting self-employed individuals without mandatory IP registration.
- **Important Legal Clarification:** Self-employed income registration in «Мой налог» must initially be done manually by the merchant per current YooKassa API documentation.
- **Provider-Agnostic Design:** The backend domain is decoupled from provider specifics so switching between YooKassa, T-Bank, or another gateway in the future requires modifying only the client adapter.

---

## 6. Phase 4 — Simplified Payment Domain Design (D6.1)

```
┌────────────────────────────────────────────────────────────────────────┐
│ Organization (Core Multi-Tenant Entity)                                │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │ 1 : 1
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│ OrganizationPlan (Single Source of Truth for Entitlements & Expiration)│
│ - plan: "free" | "pro"                                                 │
│ - status: "active" | "expired"                                         │
│ - starts_at: DateTime UTC                                              │
│ - expires_at: DateTime UTC (Extended upon successful payment)          │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │ 1 : N
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│ PaymentOrder (Purchase Intent / Order)                                 │
│ - id: UUID (Internal Order ID)                                         │
│ - organization_id: String(36) (ForeignKey to organizations.id)         │
│ - user_id: Integer (Telegram User who initiated purchase)              │
│ - plan_code: String(30) (e.g. "PRO_MONTHLY")                           │
│ - billing_days: Integer (e.g. 30)                                      │
│ - amount: Numeric(10, 2) (Server-determined price)                     │
│ - currency: String(3) ("RUB")                                          │
│ - status: String(20) ("CREATED" | "PENDING" | "SUCCEEDED" |            │
│                       "FAILED"  | "CANCELLED" | "REFUNDED")            │
│ - provider: String(30) ("yookassa")                                    │
│ - provider_payment_id: Optional[String(255)]                           │
│ - idempotency_key: String(64)                                          │
│ - confirmation_url: Optional[String(1024)]                             │
│ - created_at, paid_at, expires_at (Order TTL, e.g. 30 minutes)         │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │ 1 : N
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│ PaymentTransaction (Provider Transaction Attempt / Event Log)          │
│ - id: UUID                                                             │
│ - payment_order_id: UUID (ForeignKey to payment_orders.id)             │
│ - provider: String(30)                                                 │
│ - provider_transaction_id: String(255)                                 │
│ - transaction_type: "payment" | "refund"                               │
│ - status: "PENDING" | "SUCCEEDED" | "FAILED"                           │
│ - amount: Numeric(10, 2)                                               │
│ - currency: String(3)                                                  │
│ - error_code, error_message: Optional strings                          │
│ - created_at, updated_at                                               │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 7. Phase 5 — Payment State Machine & Transition Rules

```
               ┌──────────────┐
               │   CREATED    │
               └──────┬───────┘
                      │ Provider checkout URL generated
                      ▼
               ┌──────────────┐
        ┌──────┤   PENDING    ├────────┐
        │      └──────┬───────┘        │
        │ Timeout /   │ Verified       │ Bank
        │ Cancelled   │ Webhook/API    │ Decline
        ▼             ▼                ▼
 ┌───────────┐ ┌──────────────┐ ┌────────────┐
 │ CANCELLED │ │  SUCCEEDED   │ │   FAILED   │
 └───────────┘ └──────┬───────┘ └────────────┘
                      │ Merchant initiates
                      ▼ refund
               ┌──────────────┐
               │   REFUNDED   │
               └──────────────┘
```

### Transition & Activation Invariants
1. **Source of Truth:** Only a verified provider notification (callback reconciliation or validated webhook) can transition `PENDING -> SUCCEEDED`.
2. **Frontend Independence:** Neither `return_url` nor client query parameters can ever trigger activation.
3. **Pro Activation Logic:**
   ```python
   if order.status == PaymentOrderStatus.SUCCEEDED:
       now = utc_now()
       plan_record = await get_or_create_plan_record(session, order.organization_id)
       
       if plan_record.expires_at and plan_record.expires_at > now:
           # Active Pro: extend from existing expiration
           new_expires = plan_record.expires_at + timedelta(days=order.billing_days)
       else:
           # Free or expired Pro: start from now
           new_expires = now + timedelta(days=order.billing_days)
           
       plan_record.plan = "pro"
       plan_record.status = "active"
       plan_record.expires_at = new_expires
   ```
4. **Refund Policy:** If an order transitions to `REFUNDED`, the organization's Pro plan is revoked and reset to Free tier.

---

## 8. Phase 6 — Security Model & Payment Invariants

1. **Secret Isolation**:
   - Provider credentials (`YOOKASSA_SHOP_ID`, `YOOKASSA_SECRET_KEY`) reside exclusively in Railway environment variables.
   - Absolutely zero credentials in Git, frontend code, or API responses.
2. **Server-Side Pricing Invariant**:
   - Price and currency are determined strictly on the backend from server settings.
   - The client submits only `organization_id` and `plan_code`. Client price manipulation is rejected by Pydantic schema validation.
3. **Strict Ownership Validation**:
   - Only the authenticated owner of an organization (`org.owner_user_id == current_user.id`) can create a payment order or view order status.
4. **Idempotency & Replay Protection**:
   - Every `PaymentOrder` generates a unique `idempotency_key` (UUIDv4) passed to YooKassa.
   - Webhooks are idempotent: duplicate deliveries return `200 OK` without duplicating days.
   - Double-click protection: submitting order creation while an active pending order exists reuses the pending checkout URL within its 30-minute TTL.
5. **Two-Way Webhook Verification (Reconciliation Pattern)**:
   - When a webhook arrives at `POST /api/v1/payments/webhooks/yookassa`, the backend verifies that the remote IP belongs to YooKassa's official subnets (`185.71.76.0/27`, `185.71.77.0/27`, `77.75.153.0/25`, `77.75.156.11`, `77.75.156.35`).
   - Additionally, the backend queries `GET https://api.yookassa.ru/v3/payments/{provider_payment_id}` using HTTP Basic Auth to verify the official payment status, amount, and currency before updating database state.
6. **No Card Data On Ivently Servers (PCI-DSS Scoping)**:
   - Ivently never receives, processes, or stores card numbers, CVVs, or expiration dates. All payment inputs occur on YooKassa's hosted checkout form.
7. **Audit & Log Redaction**:
   - Payment logs must never record cardholder names, tokens, or authorization headers.

---

## 9. Phase 7 — Telegram Mini App UX & Flow

```
[ Organizer Workspace ]
         │
         ▼
[ Pro Card / Banner: Click "Оформить Pro" ]
         │
         ▼
[ Pro Details Sheet: View Features & Server-Provided Price ]
         │
         ▼ User taps "Оплатить"
[ POST /api/v1/payments/orders ]
         │
         ▼ Backend returns { order_id, confirmation_url }
[ Telegram.WebApp.openLink(confirmation_url) ]
         │
         ▼ Opens YooKassa Hosted Checkout in Telegram / Browser
[ User completes payment via Card / SBP / SberPay / T-Pay ]
         │
         ▼ YooKassa redirects to return_url
[ Return to Mini App: /?payment_order_id=... ]
         │
         ▼
[ UI renders "Проверяем оплату..." (Polling Loader) ]
         │
         ▼ Frontend polls GET /api/v1/payments/orders/{id}/status every 2s
[ Backend checks DB / Reconciles with YooKassa API ]
         │
         ├─── If SUCCEEDED ───► [ Show Celebration Screen: "Pro активирован!" ]
         │                      [ Refresh Entitlements -> 20 broadcasts available ]
         │
         └─── If PENDING/FAILED ► [ Show retry or assistance options ]
```

---

## 10. Phase 8 — Product & Pricing Model

### Server-Configured Pricing (Settings)

```python
class Settings(BaseSettings):
    # Pro Commercial Pricing (RUB) - Unset until owner decision
    PRO_MONTHLY_PRICE_RUB: Optional[float] = None
    PRO_BILLING_CURRENCY: str = "RUB"
    PAYMENTS_ENABLED: bool = False
    
    # Quotas
    PRO_BROADCASTS_PER_MONTH: int = 20
    FREE_BROADCASTS_PER_MONTH: int = 0
```

- When `PRO_MONTHLY_PRICE_RUB` is `None` or `PAYMENTS_ENABLED` is `False`, the payment endpoint returns `503 Service Unavailable` with `"Платежи временно недоступны"`.
- Launch pricing is an open business decision requiring project owner confirmation.

---

## 11. Phase 9 — API Contract Specification (D6.1)

### 1. `GET /api/v1/payments/plans`
Returns available commercial plans and current server-configured prices.

- **Auth:** Public / Authenticated
- **Response (200 OK):**
  ```json
  {
    "plans": [
      {
        "plan_code": "PRO_MONTHLY",
        "title": "Ivently Pro (1 месяц)",
        "billing_days": 30,
        "price_amount": 990.00,
        "currency": "RUB",
        "broadcasts_per_month": 20,
        "is_available": true
      }
    ]
  }
  ```

### 2. `POST /api/v1/payments/orders`
Initiates a new one-time purchase.

- **Auth:** Required (`get_current_user`, must be organization owner)
- **Request Body:**
  ```json
  {
    "organization_id": "c7a82924-43cb-4654-97c7-08e1a1234567",
    "plan_code": "PRO_MONTHLY"
  }
  ```
- **Response (201 Created):**
  ```json
  {
    "order_id": "8fa19491-a67b-44ec-b91c-772911abcdef",
    "organization_id": "c7a82924-43cb-4654-97c7-08e1a1234567",
    "plan_code": "PRO_MONTHLY",
    "amount": 990.00,
    "currency": "RUB",
    "status": "PENDING",
    "confirmation_url": "https://yookassa.ru/checkout/payments/v2/contract?orderId=...",
    "expires_at": "2026-10-04T20:30:00Z"
  }
  ```

### 3. `GET /api/v1/payments/orders/{order_id}/status`
Polls payment status with automatic real-time reconciliation.

- **Auth:** Required (`get_current_user`, must be order owner)
- **Response (200 OK):**
  ```json
  {
    "order_id": "8fa19491-a67b-44ec-b91c-772911abcdef",
    "status": "SUCCEEDED",
    "plan": "pro",
    "paid_at": "2026-10-04T20:05:12Z",
    "pro_expires_at": "2026-11-04T20:05:12Z",
    "is_active": true
  }
  ```

### 4. `POST /api/v1/payments/webhooks/yookassa`
Public webhook endpoint for YooKassa notifications.

- **Auth:** Public (verified by IP whitelist + callback reconciliation)
- **Request Body:** Standard YooKassa Event Notification
- **Response (200 OK):** `{"received": true}`

---

## 12. Phase 10 — Automated Test Plan (26 Scenarios for D6.1)

The D6.1 implementation sprint will verify the following 26 automated test scenarios (using mocked YooKassa responses without real money):

1. `test_create_payment_order_success`: Authenticated owner creates valid order; receives 201 with `confirmation_url`.
2. `test_create_payment_order_server_side_price`: Price is determined server-side; client cannot tamper with amount.
3. `test_create_payment_order_unauthorized_org_rejected`: Stranger attempting to pay for another user's org receives 403.
4. `test_create_payment_order_invalid_plan_rejected`: Submitting unknown plan code receives 422/400.
5. `test_create_payment_order_deleted_org_rejected`: Soft-deleted organization receives 404.
6. `test_duplicate_payment_order_reuses_pending`: Repeated checkout click within TTL returns existing pending order.
7. `test_webhook_payment_succeeded_activates_pro`: Valid webhook triggers Pro activation.
8. `test_webhook_duplicate_delivery_is_noop`: Duplicate webhook is harmless and does not duplicate activation days.
9. `test_webhook_payment_failed_does_not_activate_pro`: Failed transaction leaves plan on Free.
10. `test_webhook_payment_canceled_marks_order_cancelled`: Cancelled payment updates order status without activating Pro.
11. `test_delayed_webhook_handled_by_polling_reconciliation`: Polling endpoint reconciles directly with provider API.
12. `test_webhook_replay_attack_rejected`: Stale or forged webhook is rejected.
13. `test_amount_mismatch_rejected`: Webhook reporting unexpected amount is rejected.
14. `test_currency_mismatch_rejected`: Webhook with non-RUB currency is rejected.
15. `test_expired_pro_purchase_starts_from_now`: Purchasing Pro for expired org sets `expires_at = now() + 30 days`.
16. `test_active_pro_purchase_extends_from_expires_at`: Purchasing Pro for active org sets `expires_at = current_expires_at + 30 days`.
17. `test_payment_does_not_reset_broadcast_quota`: Purchasing Pro does not wipe current month broadcast counters.
18. `test_payment_state_survives_restart`: Order and plan records persist cleanly across app/db restart.
19. `test_refund_webhook_revokes_pro`: Refund event cancels active Pro and restores Free tier.
20. `test_sensitive_data_not_leaked_in_logs`: Secret keys and auth tokens never appear in tracebacks or responses.
21. `test_admin_test_pro_remains_separate`: Admin toggle remains strictly separate from customer billing paths.
22. `test_frontend_cannot_provide_custom_price`: Request payload with custom price is rejected.
23. `test_free_org_cannot_use_marketing_broadcast`: Free organization receives 403 ENTITLEMENT_REQUIRED.
24. `test_active_pro_can_broadcast`: Organization with activated Pro successfully sends marketing broadcast.
25. `test_expired_pro_cannot_broadcast`: Organization whose Pro expired is immediately blocked (403).
26. `test_transactional_notifications_remain_free`: Operational event notifications dispatch freely on Free and Pro.

---

## 13. Phase 11 — D6.1 Implementation Boundary

### Included in D6.1 Scope
- **Backend Models:** `PaymentOrder`, `PaymentTransaction`, `PaymentWebhookLog` in `app/models/payment.py`.
- **Database Migrations:** Idempotent table and index creation in `init_db()` in `app/database.py`.
- **YooKassa Client:** `YooKassaClient` abstraction with `Idempotence-Key`, timeout handling, and test mocking.
- **Order Endpoints:** `GET /plans`, `POST /orders`, `GET /orders/{id}/status`, `POST /webhooks/yookassa`.
- **Status Reconciliation:** Real-time polling reconciliation against YooKassa API.
- **Entitlement Extension:** Clean extension of `OrganizationPlan.expires_at`.
- **Frontend UI:** Pro modal with server-provided price, redirect to checkout, pending status polling, success state, and error handling.
- **Automated Tests:** 26 test scenarios in `tests/test_d6_payments.py`.

### Strictly Deferred (Out of Scope for D6.1)
- Yearly plans (`PRO_YEARLY`).
- Auto-renewal / recurring billing.
- Card tokenization (`save_payment_method`).
- `PAST_DUE` subscription grace period.
- Payment retry engine.
- Automated receipt integration.
- Real production credentials / real money transactions.

---

## 14. Phase 12 — Open Decisions for Project Owner

1. **Merchant Legal Status:** Confirmation whether merchant contract is registered as a **самозанятый физлицо** or an **ИП на НПД**.
2. **Launch Price Decision:** Final approval of the single monthly price (`PRO_MONTHLY_PRICE_RUB`), which remains unset in settings until approved.
3. **Public Offer & Terms:** Legal text of the service agreement to be linked from the Mini App checkout screen.
4. **Receipt Operational Workflow:** Acknowledgment that for self-employed status, income registration in «Мой налог» must initially be performed manually per current YooKassa documentation.
