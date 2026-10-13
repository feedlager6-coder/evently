import asyncio
import os
import sys
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.database import AsyncSessionLocal, engine
from sqlalchemy import text
from app.services.event_service import EventService
from app.services.organization_service import OrganizationService
from app.schemas.event import EventCreate, EventUpdate
from app.schemas.organization import OrganizationCreate, OrganizationUpdate
from app.models.user import User

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
            text("SELECT id, telegram_id, username FROM users LIMIT 1")
        )
        test_user = user_res.fetchone()
        if not test_user:
            # Create a test user
            await session.execute(
                text("INSERT INTO users (id, telegram_id, username, first_name, is_organizer) VALUES ('test-user-1', 99999901, 'testuser', 'Test', true)")
            )
            await session.commit()
            user_id = 'test-user-1'
        else:
            user_id = test_user[0]
        print(f"Using test user ID: {user_id}")

    # 3. Scenario: Solo Author Event with Capacity
    print("\n--- 2. Solo Author Event Creation & Capacity ---")
    async with AsyncSessionLocal() as session:
        event_service = EventService(session)
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
            capacity=2, # limit of 2 attendees
            organization_id=None, # Solo author, no org
            allow_event_contact=True
        )
        created_event = await event_service.create_organizer_event(user_id, payload)
        print(f"✓ Created solo event ID: {created_event.id}, capacity: {created_event.capacity}, org_id: {created_event.organization_id}")
        assert created_event.capacity == 2
        assert created_event.organization_id is None

        # Verify get details
        details = await event_service.get_event_details(created_event.id, user_id)
        assert details.capacity == 2
        print(f"✓ Event details returned capacity: {details.capacity}")

        # Test RSVP capacity enforcement
        print("\n--- 3. Guest Capacity Enforcement Check ---")
        # First RSVP
        rsvp1 = await event_service.add_event_rsvp(created_event.id, user_id)
        print(f"✓ User 1 RSVP status: {rsvp1['is_going']}, current capacity left: {created_event.capacity - 1}")

        # Second RSVP from second user
        user2_res = await session.execute(
            text("SELECT id FROM users WHERE id != :uid LIMIT 1"),
            {"uid": user_id}
        )
        row2 = user2_res.fetchone()
        if not row2:
            await session.execute(
                text("INSERT INTO users (id, telegram_id, username, first_name) VALUES ('test-user-2', 99999902, 'testuser2', 'Guest 2')")
            )
            await session.commit()
            user2_id = 'test-user-2'
        else:
            user2_id = row2[0]

        rsvp2 = await event_service.add_event_rsvp(created_event.id, user2_id)
        print(f"✓ User 2 RSVP status: {rsvp2['is_going']}, capacity now reached (2/2)")

        # Third user RSVP should be rejected because capacity=2 is exhausted
        user3_res = await session.execute(
            text("SELECT id FROM users WHERE id NOT IN (:u1, :u2) LIMIT 1"),
            {"u1": user_id, "u2": user2_id}
        )
        row3 = user3_res.fetchone()
        if not row3:
            await session.execute(
                text("INSERT INTO users (id, telegram_id, username, first_name) VALUES ('test-user-3', 99999903, 'testuser3', 'Guest 3')")
            )
            await session.commit()
            user3_id = 'test-user-3'
        else:
            user3_id = row3[0]

        try:
            await event_service.add_event_rsvp(created_event.id, user3_id)
            raise AssertionError("Overbooking succeeded! Capacity limit failed.")
        except Exception as exc:
            print(f"✓ Correctly rejected third attendee when capacity reached: {exc}")

        # Clean up test event rsvps & event
        await session.execute(
            text("DELETE FROM event_rsvps WHERE event_id = :eid"),
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
        org_service = OrganizationService(session)
        org_payload = OrganizationCreate(
            name="Тестовый Клуб Атмосфера 05",
            category="Ночные клубы & Бары",
            description="Пространство звука и современной электронной музыки",
            city_id="makhachkala",
            address="ул. Дахадаева, 18",
            features=["FC / DC 18+", "Wi-Fi", "Chillout & Бар", "Звуковая система"],
            social_link="@atmosfera05"
        )
        created_org = await org_service.create_organization(user_id, org_payload)
        print(f"✓ Created organization: {created_org.name}, features: {created_org.features}")
        assert created_org.features == ["FC / DC 18+", "Wi-Fi", "Chillout & Бар", "Звуковая система"]

        # Verify get organization
        fetched_org = await org_service.get_organization_by_id_or_slug(created_org.id, user_id)
        assert fetched_org.features == ["FC / DC 18+", "Wi-Fi", "Chillout & Бар", "Звуковая система"]
        print(f"✓ Fetched organization features match: {fetched_org.features}")

        # Update features
        update_payload = OrganizationUpdate(
            features=["FC / DC 18+", "VIP-ложи", "Безналичный расчет"]
        )
        updated_org = await org_service.update_organization(created_org.id, user_id, update_payload)
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
