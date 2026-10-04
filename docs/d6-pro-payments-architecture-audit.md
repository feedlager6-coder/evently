# D6 — Ivently Pro Payments: Architecture & Provider Selection Audit

> **Document Type:** Production Architecture Reference & Payment Provider Selection Audit  
> **Status:** APPROVED ARCHITECTURAL SPECIFICATION (DO NOT IMPLEMENT REAL PAYMENTS YET)  
> **Target Release:** D6.0  
> **Current Date:** October 2026  
> **Project:** Ivently (`https://ivently.up.railway.app`)

---

## 1. Executive Summary

Ivently is a Telegram-first city event discovery platform operating on a freemium model. Organizers can create unlimited events, manage venues, and gather subscribers for free. Commercial monetization is focused on the **Ivently Pro** subscription for event organizers, which unlocks:
- Direct Telegram marketing broadcasts (20 broadcasts/month).
- Advanced attendee analytics and conversion funnels.
- Upcoming Pro features: audience segmentation, smart reminders, CRM export, and verified venue badges.

Crucially, **transactional notifications** (event date/time/location changes, moderation updates, publication alerts) are operational, 100% free, and strictly isolated from the commercial marketing broadcast quota.

This audit establishes the end-to-end fintech architecture, evaluates payment providers under various legal forms (self-employed individual, individual entrepreneur, LLC), designs a provider-agnostic domain model, defines strict security invariants, and outlines the automated test and production deployment plans.

---

## 2. Phase 1 — Audit of Existing Pro Implementation

### 2.1 Existing Pro Architecture Components

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

## 3. Phase 2 — Payment Provider Research

We evaluated three candidate Russian payment providers:
1. **ЮKassa (YooKassa, ООО НКО «ЮМани»)**
2. **T-Bank Acquiring (Т-Банк / Тинькофф Эквайринг)**
3. **CloudPayments (АО «КлаудПэйментс»)**

### Comprehensive 20-Dimension Comparison Matrix

| # | Dimension | ЮKassa (YooKassa) | T-Bank (Т-Банк) | CloudPayments |
|---|---|---|---|---|
| **1** | **Self-Employed Individual (Самозанятый физлицо)** | **YES** (Dedicated program «Платежи для самозанятых») | **NO** for Internet Acquiring (SBP only in personal app, no API) | **NO** (Requires legal entity or IP) |
| **2** | **IP on NPD (ИП на НПД)** | **YES** (Standard merchant acquiring contract) | **YES** (With T-Business current account) | **YES** (Standard merchant acquiring contract) |
| **3** | **LLC / Company (ООО)** | **YES** | **YES** | **YES** |
| **4** | **Payment Methods** | Bank cards (MIR, Visa, MC), SBP, SberPay, T-Pay, YooMoney | Bank cards, SBP, T-Pay, Mir Pay | Bank cards, SBP, T-Pay, SberPay |
| **5** | **Integration Method** | REST API v3, Hosted Checkout redirect page, SDKs | REST API v2, Hosted Payment Page (PaymentURL) | REST API, Hosted Payment Page, Checkout Widget |
| **6** | **Webhooks** | HTTP POST event notifications (`payment.succeeded`, etc.) | HTTP POST notifications with SHA-256 token | HTTP POST webhooks (`check`, `pay`, `fail`) with HMAC |
| **7** | **Refunds Support** | Full & partial refunds via `POST /v3/refunds` | Full & partial refunds via `POST /v2/Cancel` | Full & partial refunds via API |
| **8** | **Recurring Subscriptions** | `save_payment_method: true` -> `payment_method_id` | `Recurrent: "Y"` -> `RebillId` -> `Charge` | Recurrent Subscriptions API / token charge |
| **9** | **Recurring for Self-Employed Individual** | Supported on card payments; subject to risk scoring & offer terms | **NO** (Internet acquiring not available for individuals) | **NO** (Not available for individuals) |
| **10** | **Cancellation Flow** | Merchant stops charging stored `payment_method_id` | Merchant stops calling `Charge` with `RebillId` | Merchant calls `POST /subscriptions/cancel` |
| **11** | **Payment Status Verification** | `GET /v3/payments/{payment_id}` | `POST /v2/GetState` | `POST /payments/get` |
| **12** | **Idempotency** | HTTP Header `Idempotence-Key: <UUID>` | Request field `OrderId` | Request field `InvoiceId` / `TransactionId` |
| **13** | **Test Mode** | Full sandbox (test `shopId`, test `secretKey`, test cards) | Test terminal, test credentials, test cards | Test public/private keys, test cards |
| **14** | **Receipt Requirements (Чеки / 54-ФЗ)** | Self-employed: exempt from 54-ФЗ, covered by 422-ФЗ | 54-ФЗ online cash register required for acquiring | 54-ФЗ online cash register required (CloudKassir) |
| **15** | **Self-Employed Receipt Automation** | **Automatic** via direct integration with FNS «Мой налог» | **Manual** (self-employed must manually issue in app) | **N/A** (not supported for self-employed individuals) |
| **16** | **Fund Settlement** | To bank card or bank account in 1–2 business days | To T-Business current account daily | To current account on next business day |
| **17** | **Fee Structure** | Cards: ~3.5% + VAT of fee; SBP: ~1% + VAT. No monthly fee | Cards: ~1.99–2.69%; SBP: ~0.4–0.7%. Current account fee applies | Cards: ~2.7–3.9%. Cash register fee (~1500–2500 ₽/mo) |
| **18** | **Telegram Mini App Compatibility** | **High** (`Telegram.WebApp.openLink` -> Hosted Checkout -> return deep-link) | **High** (`openLink` -> PaymentURL -> return deep-link) | **High** (`openLink` -> HPP -> return deep-link) |
| **19** | **SaaS Subscription Restrictions** | 2.4M ₽/year limit for self-employed NPD; requires IP above | Requires business registration (IP/LLC) | Requires business registration (IP/LLC) |
| **20** | **Webhook Security Verification** | IP whitelist + mandatory callback GET reconciliation | SHA-256 HMAC digest validation against shared password | HMAC-SHA256 signature in `Content-HMAC` header |

---

## 4. Phase 3 — Recommendation & Decision Table

### Decision Summary

| Provider | Self-Employed Individual | IP on NPD | LLC | SBP | Cards | Recurring | Automated Receipts | Recommendation |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---|
| **ЮKassa** | **YES** | **YES** | **YES** | **YES** | **YES** | **YES** | **YES (Мой налог)** | **PRIMARY RECOMMENDATION (Score: 10/10)** |
| **T-Bank** | NO | YES | YES | YES | YES | YES | 54-ФЗ only | Feasible ONLY if registered as IP |
| **CloudPayments** | NO | YES | YES | YES | YES | YES | 54-ФЗ only | Feasible ONLY if registered as IP/LLC |

### Why ЮKassa is the Clear Winner

1. **Legal Viability from Day 1:** If Ivently launches monetization initially under a self-employed individual (самозанятый), ЮKassa is the **only major acquiring provider** that provides full-featured REST API online acquiring without requiring legal entity or IP registration.
2. **Zero Cash Register Overhead:** Through ЮKassa's official integration with the Federal Tax Service (ФНС) «Мой налог», receipts are created and delivered automatically. Neither an expensive physical/cloud cash register (54-ФЗ) nor a fiscal drive (ФН) is needed.
3. **Seamless Future Migration:** If Ivently scales beyond the 2.4M ₽ annual limit and transitions to an **IP on NPD** or an **LLC**, the backend integration with ЮKassa API v3 remains **100% unchanged**. Only the merchant contract and credentials in the personal cabinet are updated.
4. **All Modern Russian Payment Methods:** Customers can pay with Russian bank cards (MIR, Visa, Mastercard), SBP, SberPay, and T-Pay.
5. **Robust Idempotency & Reconciliation:** Native `Idempotence-Key` support and lightweight `GET /v3/payments/{id}` verification allow bulletproof payment reconciliation even under network failure or delayed webhooks.

---

## 5. Phase 4 — Provider-Agnostic Payment Domain Design

To prevent vendor lock-in, the payment architecture decouples high-level entitlements from provider-specific payment gateways.

```
┌────────────────────────────────────────────────────────────────────────┐
│ Organization (Core Multi-Tenant Entity)                                │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │ 1 : 1
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│ OrganizationPlan (Fast Entitlement Cache for O(1) Checks)              │
│ - plan: "free" | "pro"                                                 │
│ - status: "active" | "expired" | "cancelled"                           │
│ - expires_at: datetime                                                 │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │ 1 : 1
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│ OrganizationSubscription (Subscription Agreement & Renewal State)     │
│ - id: UUID                                                             │
│ - organization_id: String(36)                                          │
│ - plan_code: "PRO_MONTHLY" | "PRO_YEARLY"                              │
│ - status: "INACTIVE" | "ACTIVE" | "PAST_DUE" | "CANCELLED" | "EXPIRED" │
│ - provider: "yookassa"                                                 │
│ - provider_payment_method_id: String (Stored card token)                │
│ - auto_renew: Boolean                                                  │
│ - current_period_started_at, current_period_expires_at                 │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │ 1 : N
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│ PaymentOrder (Commercial Purchase Intent / Order)                      │
│ - id: UUID (Internal Order ID)                                         │
│ - organization_id: String(36)                                          │
│ - user_id: Integer (Telegram User who initiated checkout)              │
│ - subscription_id: UUID                                                │
│ - plan_code: "PRO_MONTHLY" | "PRO_YEARLY"                              │
│ - amount: Numeric(10, 2) (e.g. 990.00 RUB)                             │
│ - currency: "RUB"                                                      │
│ - status: "CREATED" | "PENDING" | "SUCCEEDED" | "CANCELLED" | "FAILED" │
│ - provider: "yookassa"                                                 │
│ - provider_payment_id: String (e.g. YooKassa Payment ID)               │
│ - idempotency_key: String(64)                                          │
│ - confirmation_url: String (Hosted payment URL)                        │
│ - paid_at, expires_at (Order TTL)                                      │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │ 1 : N
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│ PaymentTransaction (Ledger Entry / Attempt)                            │
│ - id: UUID                                                             │
│ - payment_order_id: UUID                                               │
│ - provider: "yookassa"                                                 │
│ - provider_transaction_id: String                                      │
│ - transaction_type: "initial" | "renewal" | "refund"                   │
│ - status: "PENDING" | "SUCCEEDED" | "FAILED"                           │
│ - amount, currency                                                     │
│ - raw_response: JSON (Masked audit trail)                              │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Phase 5 — Payment & Subscription State Machines

### 6.1 PaymentOrder State Machine

```
               ┌──────────────┐
               │   CREATED    │
               └──────┬───────┘
                      │ Provider checkout URL generated
                      ▼
               ┌──────────────┐
        ┌──────┤   PENDING    ├────────┐
        │      └──────┬───────┘        │
        │ Timeout /   │ Verified       │ Payment
        │ Cancelled   │ Webhook/API    │ Declined
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

**State Transition Rules:**
1. Only a verified provider notification (webhook validated via signature or callback GET) or direct API reconciliation can transition `PENDING -> SUCCEEDED`.
2. The frontend redirect URL or query string is **NEVER** trusted as proof of payment.
3. Once `SUCCEEDED`, a payment cannot transition to `FAILED` or `CANCELLED`.
4. Transition to `REFUNDED` immediately revokes commercial Pro entitlements.

### 6.2 OrganizationSubscription State Machine

```
               ┌──────────────┐
               │   INACTIVE   │
               └──────┬───────┘
                      │ First successful PaymentOrder
                      ▼
 ┌───────────┐ ┌──────────────┐ ┌────────────┐
 │  EXPIRED  │ │    ACTIVE    │ │  PAST_DUE  │
 └─────▲─────┘ └──┬─────────┬─┘ └──────▲─────┘
       │          │         │          │
       │ Period   │ User    │ Failed   │ Grace
       │ elapsed  │ cancels │ renewal  │ period
       │          ▼         │          │ (3 days)
       │   ┌───────────┐    └──────────┘
       └───┤ CANCELLED │
           └───────────┘
```

**Subscription Rules:**
- `ACTIVE`: Organization has full Pro entitlements.
- `PAST_DUE`: An automatic renewal attempt failed. Pro access is temporarily maintained during a 3-day grace period while retries occur.
- `CANCELLED`: User toggled off auto-renewal. Pro remains accessible until `current_period_expires_at`, then transitions to `EXPIRED`.
- `EXPIRED`: Period ended without payment. Organization degrades to Free tier instantly.

---

## 7. Phase 6 — Security Model & Payment Invariants

1. **Secret Isolation**:
   - Provider credentials (`YOOKASSA_SHOP_ID`, `YOOKASSA_SECRET_KEY`) exist strictly in Railway environment variables.
   - Absolutely zero credentials in Git, frontend code, or client responses.
2. **Server-Side Pricing Invariant**:
   - Price and currency are determined strictly on the backend via server settings (`settings.PRO_MONTHLY_PRICE_RUB`, `settings.PRO_YEARLY_PRICE_RUB`).
   - The client submits only `organization_id` and `plan_code`. Client-provided price tampering is technically impossible.
3. **Strict Ownership Validation**:
   - Only the authenticated owner of an organization (`org.owner_user_id == current_user.id`) can create a payment order or view billing details.
4. **Idempotency & Replay Protection**:
   - Every `PaymentOrder` generates a unique `idempotency_key` (UUIDv4) passed to YooKassa.
   - Webhook processing checks whether the event has already been processed. Duplicate deliveries return `200 OK` without triggering duplicate subscription extensions.
5. **Two-Way Webhook Verification (Reconciliation Pattern)**:
   - When a webhook arrives at `POST /api/v1/payments/webhooks/yookassa`, the backend verifies that the remote IP belongs to YooKassa's official subnets (`185.71.76.0/27`, `185.71.77.0/27`, `77.75.153.0/25`, `77.75.156.11`, `77.75.156.35`).
   - Additionally, the backend immediately queries `GET https://api.yookassa.ru/v3/payments/{provider_payment_id}` using HTTP Basic Auth to verify the official payment status, amount, and currency before updating database state.
6. **No Card Data On Ivently Servers (PCI-DSS Scoping)**:
   - Ivently never receives, processes, or stores card numbers, CVVs, or expiration dates. All payment inputs are handled securely on YooKassa's hosted payment page.
7. **Audit & Log Redaction**:
   - Payment logs must never record cardholder names, tokens, or webhook authorization headers.

---

## 8. Phase 7 — Telegram Mini App UX & Payment Flow

```
[ Organizer Workspace ]
         │
         ▼
[ Click "Тариф Pro" ]
         │
         ▼
[ Pro Modal: Choose Monthly (990 ₽) or Yearly (9,900 ₽) ]
         │
         ▼ User taps "Оплатить Pro"
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
         └─── If PENDING/FAILED ► [ Show retry or support help options ]
```

### Edge Cases Handled

1. **User Closes Payment Page Without Paying**:
   - Order remains `PENDING` until TTL (30 min), then expires to `CANCELLED`.
   - Returning to the app shows a gentle message: *«Оплата не была завершена. Вы можете вернуться к оформлению в любой момент.»*
2. **Delayed Webhook (Network Lag / Asynchronous Processing)**:
   - When the client returns to the app and polls `GET /api/v1/payments/orders/{order_id}/status`, the backend actively queries YooKassa's API (`GET /v3/payments/{provider_payment_id}`).
   - If YooKassa reports `succeeded`, the backend activates the subscription immediately during the poll request, guaranteeing instant activation even if the webhook is delayed.
3. **Double Click on "Pay"**:
   - Frontend disables the pay button and shows a spinner immediately upon tap.
   - If a duplicate request is sent, the backend checks for an existing active `PENDING` order for this organization created in the last 60 seconds and returns the existing checkout URL.
4. **Mini App Reload / Session Restart**:
   - Order ID is persisted in `sessionStorage` or URL parameter. The user can reopen the app at any time and the status verification flow will resume cleanly.

---

## 9. Phase 8 — Product & Pricing Model

### Server-Configured Pricing

```python
class Settings(BaseSettings):
    # Pro Commercial Pricing (RUB)
    PRO_MONTHLY_PRICE_RUB: float = 990.00
    PRO_YEARLY_PRICE_RUB: float = 9900.00
    PRO_BILLING_CURRENCY: str = "RUB"
    
    # Quotas
    PRO_BROADCASTS_PER_MONTH: int = 20
    FREE_BROADCASTS_PER_MONTH: int = 0
```

### Plan Comparison

| Feature | Free Tier | Pro Tier (990 ₽/mo) |
|---|:---:|:---:|
| Event creation & editing | Unlimited | Unlimited |
| Organization profile & subscribers | Included | Included |
| Attendee RSVPs («Хочу пойти» / «Я иду») | Included | Included |
| Basic views & interaction analytics | Included | Included |
| **Transactional notifications** (event changes) | **Free & Unlimited** | **Free & Unlimited** |
| **Manual marketing broadcasts** | **0 / month** | **20 / month** |
| Broadcast conversion analytics | Locked | Available |
| Target interested guests | Locked | Available |
| Future: Audience segments & Auto-reminders | Locked | Included upon launch |

### Commercial Policies (Requiring Legal Approval)

1. **Auto-Renewal Policy**: Clearly disclosed on checkout screen with an explicit checkbox or button label: *«Оплачивая, вы соглашаетесь с условиями оферты и регулярным списанием 990 ₽/месяц. Подписку можно отменить в любой момент в кабинете организатора.»*
2. **Cancellation Policy**: Cancellation takes effect at the end of the paid billing cycle. No further charges occur.
3. **Refund Policy**: Refunds permitted within 14 days of purchase if fewer than 2 broadcasts were sent during the billing period.

---

## 10. Phase 9 — API Contract Specification

### 1. `POST /api/v1/payments/orders`
Initiates a new subscription purchase.

- **Auth:** Required (`get_current_user`)
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

### 2. `GET /api/v1/payments/orders/{order_id}/status`
Polls payment status with automatic real-time reconciliation.

- **Auth:** Required (`get_current_user`)
- **Response (200 OK):**
  ```json
  {
    "order_id": "8fa19491-a67b-44ec-b91c-772911abcdef",
    "status": "SUCCEEDED",
    "plan": "pro",
    "paid_at": "2026-10-04T20:05:12Z",
    "subscription_expires_at": "2026-11-04T20:05:12Z",
    "is_active": true
  }
  ```

### 3. `POST /api/v1/payments/webhooks/yookassa`
Public webhook endpoint for YooKassa notifications.

- **Auth:** Public (verified by IP whitelist + callback reconciliation)
- **Request Body:** Standard YooKassa Event Notification
- **Response (200 OK):** `{"received": true}`

### 4. `POST /api/v1/organizer/subscription/cancel`
Disables automatic renewal for an organization's subscription.

- **Auth:** Required (`get_current_user`, must be owner)
- **Request Body:**
  ```json
  {
    "organization_id": "c7a82924-43cb-4654-97c7-08e1a1234567"
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "organization_id": "c7a82924-43cb-4654-97c7-08e1a1234567",
    "status": "CANCELLED",
    "auto_renew": false,
    "expires_at": "2026-11-04T20:05:12Z"
  }
  ```

---

## 11. Phase 10 — Automated Test Plan (28 Scenarios)

The implementation sprint must build and verify the following 28 automated test scenarios:

1. `test_create_payment_order_success`: Authenticated owner creates valid order; receives 201 with `confirmation_url`.
2. `test_create_payment_order_price_server_determined`: Client cannot override or tamper with plan price.
3. `test_create_payment_order_non_owner_forbidden`: Stranger attempting to pay for another user's org receives 403.
4. `test_create_payment_order_invalid_plan_rejected`: Submitting unknown plan code receives 422/400.
5. `test_create_payment_order_deleted_org_rejected`: Soft-deleted organization receives 404.
6. `test_duplicate_payment_order_reuse`: Repeated creation within TTL returns existing pending order.
7. `test_webhook_payment_succeeded_activates_pro`: Valid webhook triggers subscription activation and sets Pro.
8. `test_webhook_duplicate_delivery_idempotent`: Duplicate webhook execution is harmless and does not duplicate days.
9. `test_webhook_payment_canceled_marks_order_cancelled`: Cancelled payment updates order status without activating Pro.
10. `test_webhook_payment_failed_does_not_activate_pro`: Failed transaction leaves plan on Free.
11. `test_delayed_webhook_handled_by_polling_reconciliation`: Polling endpoint verifies directly with provider API.
12. `test_webhook_replay_attack_rejected`: Stale or forged webhook is rejected.
13. `test_webhook_unauthorized_ip_rejected`: Webhook from non-YooKassa IP address is blocked.
14. `test_subscription_expiry_downgrades_to_free`: When `expires_at` passes, effective plan resolves to Free.
15. `test_cancel_subscription_preserves_access_until_period_end`: Cancelled subscription remains Pro until expiration.
16. `test_refund_webhook_immediately_revokes_pro`: Refund event cancels subscription and restores Free tier.
17. `test_second_payment_extends_active_subscription`: Paying while active adds 30 days onto current expiration date.
18. `test_double_click_pay_protection`: Concurrent checkout creation requests execute safely via database locks.
19. `test_admin_test_endpoints_remain_isolated`: Admin toggle remains strictly separate from customer billing paths.
20. `test_free_org_blocked_from_broadcast`: Free organization cannot send manual marketing broadcasts (403).
21. `test_active_pro_can_broadcast`: Organization with activated Pro successfully sends broadcast up to quota.
22. `test_expired_pro_cannot_broadcast`: Organization whose Pro just expired is immediately blocked (403).
23. `test_transactional_notifications_remain_free`: Event changes dispatch freely regardless of plan or quota.
24. `test_broadcast_quota_fixed_at_20_per_month`: Pro limit strictly enforces 20 marketing broadcasts.
25. `test_payment_order_does_not_reset_current_month_usage`: Paying for renewal does not wipe current broadcast counters.
26. `test_payment_state_survives_db_reconnect`: Subscription and order states persist cleanly across restarts.
27. `test_schema_migration_idempotent_on_postgres_and_sqlite`: Database migration script runs without errors on both engines.
28. `test_sensitive_data_not_leaked_in_logs_or_errors`: Secret keys and card tokens never appear in tracebacks or responses.

---

## 12. Phase 11 — Production Deployment & Rollout Plan

### Step-by-Step Production Roadmap

1. **Pre-Flight Configuration**:
   - Register account in YooKassa as self-employed individual (or IP).
   - Complete FNS «Мой налог» integration in YooKassa dashboard.
   - Configure Railway variables:
     - `YOOKASSA_SHOP_ID`
     - `YOOKASSA_SECRET_KEY`
     - `YOOKASSA_WEBHOOK_SECRET`
     - `PRO_MONTHLY_PRICE_RUB=990`
     - `PRO_YEARLY_PRICE_RUB=9900`
2. **Database Migration**:
   - Deploy schema additions (`organization_subscriptions`, `payment_orders`, `payment_transactions`, `payment_webhook_logs`) via idempotent migrations in `init_db()`.
3. **Webhook Registration**:
   - Register webhook URL in YooKassa dashboard:
     `https://ivently.up.railway.app/api/v1/payments/webhooks/yookassa`
   - Select events: `payment.succeeded`, `payment.canceled`, `refund.succeeded`.
4. **End-to-End Test in Sandbox**:
   - Run 1 real sandbox test transaction using YooKassa test cards.
   - Confirm automatic activation, UI feedback, and broadcast quota unlock.
5. **Production Enablement**:
   - Switch credentials from sandbox to live keys in Railway.
   - Flip `PAYMENTS_ENABLED=true`.

---

## 13. Risks & Open Questions for Project Owner

1. **Legal Status Confirmation**:
   - Is Ivently launching as a **физлицо-самозанятый** (НПД) or an **ИП на НПД**?
   - *Architectural impact:* If launching as an individual self-employed, ЮKassa is mandatory. If launching as an IP, T-Bank or CloudPayments can also be considered.
2. **Annual Turnover Limit**:
   - Self-employed status is capped at **2.4 million RUB/year** (~200 Pro subscribers paying 990 ₽/mo reaches ~2.37M ₽/year). Once this threshold is approached, registration as an IP is required by Russian law.
3. **Public Offer & Legal Terms**:
   - A public user agreement and offer (Публичная оферта на оказание информационных услуг) must be published at `/terms` or linked in the Mini App before accepting live payments.
4. **Chargeback & Cancellation Policy**:
   - Decision on refund window (e.g. 14 calendar days) and automated vs. manual refund processing.

---

## 14. Next Implementation Sprint (D6.1)

When authorized, the next development sprint (**D6.1**) will execute:
1. Creation of database models (`PaymentOrder`, `OrganizationSubscription`, `PaymentTransaction`, `PaymentWebhookLog`) and migrations in `app/database.py`.
2. Implementation of `YooKassaClient` with idempotency, retry backoff, and mock test fixtures.
3. Creation of payment endpoints (`POST /api/v1/payments/orders`, `GET /api/v1/payments/orders/{id}/status`, `POST /api/v1/payments/webhooks/yookassa`).
4. Implementation of the 28 automated tests.
5. Frontend payment flow integration in `OrganizerWorkspace.tsx` and `EventDetailsModal.tsx`.
