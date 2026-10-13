import asyncio
import os
import sys
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, "/app/backend")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.database import AsyncSessionLocal
from sqlalchemy import text
from app.services.event_service import (
    create_organizer_event,
    get_event_details,
    add_event_rsvp,
    EventValidationError
)
from app.services.organization_service import (
    create_organization,
    get_organization_by_id_or_slug,
    update_organization
)
from app.schemas.event import EventCreate, EventUpdate
from app.schemas.organization import OrganizationCreate, OrganizationUpdate

async def run_verification():
    print("=== STARTING END-TO-END PERSONA VERIFICATION ===")
    
    # 1. Database Schema Check
    print("\n--- 1. Database Schema Check ---")
    async with AsyncSessionLocal() as session:
        events_col = await session.execute(
            text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'events' AND column_name = 'capacity'")
        )
        col_res = events_col.fetchall()
        print(f"events.capacity column: {col_res}")
        assert len(col_res) == 1, "Missing events.capacity column!"

        org_col = await session.execute(
            text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'organizations' AND column_name = 'features'")
        )
        org_res = org_col.fetchall()
        print(f"organizations.features column: {org_res}")
        assert len(org_res) == 1, "Missing organizations.features column!"
        print("✓ Database Schema verified.")

    # 2. Setup Test User
    async with AsyncSessionLocal() as session:
        user_res = await session.execute(
            text("SELECT id FROM users LIMIT 1")
        )
        test_user = user_res.fetchone()
        user_id = test_user[0]
        print(f"Using test user ID: {user_id}")

    # 3. Scenario: Solo Author Event with Capacity
    print("\n--- 2. Solo Author Event Creation & Capacity ---")
    async with AsyncSessionLocal() as session:
        payload = EventCreate(
            title="Тестовый Воркшоп Solo Автора",
            description="Интенсив по дизайну для начинающих",
            city_id="makhachkala",
            category_id="education",
            start_at="2026-11-20T19:00:00Z",
            venue_name="Коворкинг Лофт",
            address="ул. Расула Гамзатова, 45",
            price_amount=500,
            price_currency="RUB",
            capacity=2,
            organization_id=None,
            allow_event_contact=True
        )
        created_event = await create_organizer_event(session, payload, user_id)
        print(f"✓ Created solo event ID: {created_event.id}, capacity: {created_event.capacity}, org_id: {created_event.organization_id}")
        assert created_event.capacity == 2
        assert created_event.organization_id is None

        # Verify get details
        details = await get_event_details(session, created_event.id, user_id)
        assert details.capacity == 2
        print(f"✓ Event details returned capacity: {details.capacity}")

        # Test RSVP capacity enforcement
        print("\n--- 3. Guest Capacity Enforcement Check ---")
        rsvp1 = await add_event_rsvp(session, created_event.id, user_id)
        print(f"✓ User 1 RSVP status: {rsvp1[0]}")

        user2_res = await session.execute(
            text("SELECT id FROM users WHERE id != :uid LIMIT 1"),
            {"uid": user_id}
        )
        row2 = user2_res.fetchone()
        user2_id = row2[0]

        rsvp2 = await add_event_rsvp(session, created_event.id, user2_id)
        print(f"✓ User 2 RSVP status: {rsvp2[0]}, capacity now reached (2/2)")

        user3_res = await session.execute(
            text("SELECT id FROM users WHERE id NOT IN (:u1, :u2) LIMIT 1"),
            {"u1": user_id, "u2": user2_id}
        )
        row3 = user3_res.fetchone()
        user3_id = row3[0]

        try:
            await add_event_rsvp(session, created_event.id, user3_id)
            raise AssertionError("Overbooking succeeded! Capacity limit failed.")
        except EventValidationError as exc:
            print(f"✓ Correctly rejected third attendee when capacity reached: {exc}")

        # Clean up test event rsvps & event
        await session.execute(
            text("DELETE FROM event_attendees WHERE event_id = :eid"),
            {"eid": created_event.id}
        )
        await session.execute(
            text("DELETE FROM events WHERE id = :eid"),
            {"eid": created_event.id}
        )
        await session.commit()
        print("✓ Test event cleaned up.")

    # 4. Scenario: Organization Creation with Features Chips
    print("\n--- 4. Organization Owner Features Chips Check ---")
    async with AsyncSessionLocal() as session:
        org_payload = OrganizationCreate(
            name="Тестовый Клуб Атмосфера 05",
            category="Ночные клубы & Бары",
            description="Пространство звука и современной электронной музыки",
            city_id="makhachkala",
            address="ул. Дахадаева, 18",
            features=["FC / DC 18+", "Wi-Fi", "Chillout & Бар", "Звуковая система"],
            social_link="@atmosfera05"
        )
        created_org = await create_organization(session, org_payload, user_id)
        print(f"✓ Created organization: {created_org.name}, features: {created_org.features}")
        assert created_org.features == ["FC / DC 18+", "Wi-Fi", "Chillout & Бар", "Звуковая система"]

        # Verify get organization
        fetched_org = await get_organization_by_id_or_slug(session, created_org.id, user_id)
        assert fetched_org.features == ["FC / DC 18+", "Wi-Fi", "Chillout & Бар", "Звуковая система"]
        print(f"✓ Fetched organization features match: {fetched_org.features}")

        # Update features
        update_payload = OrganizationUpdate(
            features=["FC / DC 18+", "VIP-ложи", "Безналичный расчет"]
        )
        updated_org = await update_organization(session, created_org.id, update_payload, user_id)
        assert updated_org.features == ["FC / DC 18+", "VIP-ложи", "Безналичный расчет"]
        print(f"✓ Updated organization features match: {updated_org.features}")

        # Clean up test organization
        await session.execute(
            text("DELETE FROM organizations WHERE id = :oid"),
            {"oid": created_org.id}
        )
        await session.commit()
        print("✓ Test organization cleaned up.")

    print("\n=== ALL SCENARIOS PASSED WITH 100% SUCCESS ===")

if __name__ == "__main__":
    asyncio.run(run_verification())
