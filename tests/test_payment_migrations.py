import pytest
import uuid
from datetime import datetime, timezone
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.database import Base, init_db
from app.models.user import User
from app.models.city import City
from app.models.organization import Organization
from app.models.organization_plan import OrganizationPlan, PlanType, PlanStatus
from app.models.payment import PaymentOrder, PaymentTransaction, PaymentWebhookLog, PaymentOrderStatus, ReceiptStatus


@pytest.mark.asyncio
async def test_init_db_is_idempotent_and_preserves_existing_data(tmp_path):
    """
    Verifies that init_db() can run multiple times safely on an existing database
    without corrupting or wiping existing business records.
    """
    db_file = tmp_path / "test_migration.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"

    engine = create_async_engine(db_url, echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    # 1. First initialization
    await init_db(engine)

    # 2. Insert test user, organization and plan
    org_id = str(uuid.uuid4())
    async with async_session() as sess:
        user = User(
            id=1,
            telegram_id=999999,
            username="migration_user",
            first_name="Mig",
        )
        sess.add(user)
        await sess.flush()

        org = Organization(
            id=org_id,
            owner_user_id=user.id,
            name="Migration Test Org",
            slug=f"mig-org-{org_id[:8]}",
            category="Музыка",
            city_id="makhachkala",
            is_verified=False
        )
        sess.add(org)
        plan = OrganizationPlan(
            id=str(uuid.uuid4()),
            organization_id=org_id,
            plan=PlanType.FREE.value,
            status=PlanStatus.ACTIVE.value
        )
        sess.add(plan)
        await sess.commit()

    # 3. Run init_db a second and third time (simulating app restarts / deployments)
    await init_db(engine)
    await init_db(engine)

    # 4. Verify original data is untouched
    async with async_session() as sess:
        org_check = await sess.get(Organization, org_id)
        assert org_check is not None
        assert org_check.name == "Migration Test Org"

        plan_check = (await sess.execute(
            select(OrganizationPlan).where(OrganizationPlan.organization_id == org_id)
        )).scalar_one_or_none()
        assert plan_check is not None
        assert plan_check.plan == "free"

    # 5. Insert payment records into newly created tables to verify schema integrity
    async with async_session() as sess:
        order = PaymentOrder(
            id=str(uuid.uuid4()),
            organization_id=org_id,
            user_id=1,
            amount=499.0,
            currency="RUB",
            provider="yookassa",
            provider_payment_id="pay_mig_123",
            idempotency_key=str(uuid.uuid4()),
            status=PaymentOrderStatus.PENDING.value,
            service_name="pro_subscription_30d",
            receipt_status=ReceiptStatus.PENDING.value
        )
        sess.add(order)
        await sess.commit()

        # Verify query back
        retrieved = await sess.get(PaymentOrder, order.id)
        assert retrieved is not None
        assert retrieved.amount == 499.0
        assert retrieved.provider_payment_id == "pay_mig_123"

    await engine.dispose()
