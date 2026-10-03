import pytest
import httpx
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy import select

from tests.conftest import make_test_init_data
from app.config import settings
from app.models.user import User
from app.models.event import Event, EventStatus
from app.models.organization import Organization
from app.models.subscription import Subscription
from app.models.interest import EventInterest
from app.models.broadcast import (
    Broadcast,
    BroadcastRecipient,
    BroadcastType,
    BroadcastTargetType,
    BroadcastTemplateKey,
    BroadcastStatus,
    RecipientStatus,
)
from app.services.broadcast_service import (
    preview_broadcast,
    format_broadcast_content,
    create_broadcast,
    dispatch_broadcast,
    calculate_audience,
)
from app.schemas.broadcast import BroadcastCreateRequest
from app.services.entitlement_service import EntitlementService
from app.models.organization_plan import OrganizationPlan, PlanType, PlanStatus


@pytest.mark.asyncio
async def test_d506_01_broadcast_preview_includes_cover_image_url(client, test_session):
    """
    D5.0.6: Broadcast preview must include cover_image_url so the Telegram
    photo card can be rendered in the preview bubble accurately.
    """
    owner_id = 906101
    auth_headers = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner_d506')}"}

    u = User(id=owner_id, telegram_id=owner_id, username="owner_d506")
    org = Organization(id="org_d506_1", name="Театр Д506", slug="teatr-d506-1", category="Театр", city_id="makhachkala", owner_user_id=owner_id)
    ev = Event(
        id="ev_d506_1",
        title="Премьера спектакля",
        description="Описание премьеры спектакля",
        category_id="theatre",
        city_id="makhachkala",
        organization_id=org.id,
        organizer_user_id=owner_id,
        start_at=datetime(2026, 11, 1, 19, 0, tzinfo=timezone.utc),
        venue_name="Большой зал",
        address="ул. Пушкина, д. 1",
        status=EventStatus.PUBLISHED.value,
        cover_image_url="https://images.unsplash.com/photo-test-theatre.jpg",
    )
    test_session.add_all([u, org, ev])
    await test_session.commit()

    # 1. Preview for event_announcement with cover photo
    preview = await preview_broadcast(
        session=test_session,
        organizer_user_id=owner_id,
        organization_id=org.id,
        target_type=BroadcastTargetType.ORGANIZATION_SUBSCRIBERS.value,
        broadcast_type=BroadcastType.MARKETING.value,
        template_key=BroadcastTemplateKey.EVENT_ANNOUNCEMENT.value,
        event_id=ev.id,
        custom_text="Ждём всех на премьере!",
    )
    assert preview.cover_image_url == "https://images.unsplash.com/photo-test-theatre.jpg"
    assert "Премьера спектакля" in preview.preview_text
    assert "Ждём всех на премьере!" in preview.preview_text

    # 2. Preview for custom_update (organization news) should have no cover_image_url
    preview_news = await preview_broadcast(
        session=test_session,
        organizer_user_id=owner_id,
        organization_id=org.id,
        target_type=BroadcastTargetType.ORGANIZATION_SUBSCRIBERS.value,
        broadcast_type=BroadcastType.MARKETING.value,
        template_key=BroadcastTemplateKey.CUSTOM_UPDATE.value,
        custom_text="Открытие нового сезона!",
    )
    assert preview_news.cover_image_url is None
    assert "Открытие нового сезона!" in preview_news.preview_text


@pytest.mark.asyncio
async def test_d506_02_broadcast_content_multiline_formatting_and_escaping():
    """
    D5.0.6: format_broadcast_content preserves multi-line paragraphs,
    handles long Russian words, and safely escapes HTML tags.
    """
    org = Organization(id="org_d506_fmt", name="Джаз-клуб & Бар <Jam>")
    ev = Event(
        id="ev_d506_fmt",
        title="Осенний фестиваль экспериментальной импровизационной музыки",
        venue_name="Зал консерватории, ул. Ленина, д. 45/2",
        start_at=datetime(2026, 10, 20, 20, 0, tzinfo=timezone.utc),
        organization_id=org.id,
    )

    multiline_text = (
        "Первый абзац: Привет всем любителям джаза!\n\n"
        "Второй абзац:\n"
        "1. Начало в 20:00 ровно.\n"
        "2. Вход по спискам <VIP> & гостям.\n\n"
        "До встречи!"
    )

    text, btn_text, btn_url = format_broadcast_content(
        organization=org,
        template_key=BroadcastTemplateKey.EVENT_ANNOUNCEMENT.value,
        event=ev,
        custom_text=multiline_text,
    )

    # 1. Verification of safe HTML escaping
    assert "<script>" not in text
    assert "&lt;Jam&gt;" in text
    assert "&lt;VIP&gt;" in text
    assert "&amp;" in text

    # 2. Verification of paragraphs preservation (\n\n)
    assert "Первый абзац" in text
    assert "Второй абзац" in text
    assert "1. Начало в 20:00 ровно." in text
    assert "До встречи!" in text

    # 3. Button text and URL
    assert btn_text == "Открыть событие 🧭"
    assert f"event_{ev.id}" in btn_url


@pytest.mark.asyncio
async def test_d506_03_photo_broadcast_timeout_no_duplicate_delivery(test_session):
    """
    D5.0.6: Photo broadcast timeout must mark recipient FAILED and NEVER
    attempt text fallback, preventing duplicate delivery.
    """
    owner_id = 906301
    user_id = 906302

    org = Organization(id="org_d506_photo", name="Фото Орг", slug="photo-org-d506", category="Клуб", city_id="makhachkala", owner_user_id=owner_id)
    u_recipient = User(id=user_id, telegram_id=user_id, username="photo_rec")
    ev = Event(
        id="ev_d506_photo",
        title="Событие с фото",
        description="Описание события с фото",
        category_id="concerts",
        city_id="makhachkala",
        organization_id=org.id,
        organizer_user_id=owner_id,
        start_at=datetime(2026, 11, 5, 20, 0, tzinfo=timezone.utc),
        venue_name="Сцена",
        address="ул. Музыки, д. 5",
        status=EventStatus.PUBLISHED.value,
        cover_image_url="https://images.unsplash.com/photo-concert.jpg",
    )
    b = Broadcast(
        id="b_d506_photo",
        organization_id=org.id,
        event_id=ev.id,
        broadcast_type=BroadcastType.MARKETING.value,
        target_type=BroadcastTargetType.ORGANIZATION_SUBSCRIBERS.value,
        template_key=BroadcastTemplateKey.EVENT_ANNOUNCEMENT.value,
        status=BroadcastStatus.PROCESSING.value,
        total_recipients=1,
    )
    rec = BroadcastRecipient(
        id="rec_d506_photo",
        broadcast_id=b.id,
        user_id=user_id,
        status=RecipientStatus.PENDING.value,
    )
    test_session.add_all([org, u_recipient, ev, b, rec])
    await test_session.commit()

    # Mock client that raises TimeoutException on sendPhoto
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.side_effect = httpx.TimeoutException("Connection timed out to api.telegram.org")

    await dispatch_broadcast(
        session=test_session,
        broadcast_id=b.id,
        http_client=mock_client,
    )

    await test_session.refresh(rec)
    await test_session.refresh(b)

    # 1. Exactly 1 post attempt made (to sendPhoto)
    assert mock_client.post.call_count == 1
    call_url = mock_client.post.call_args[0][0]
    assert "sendPhoto" in call_url

    # 2. Recipient marked FAILED with photo_timeout
    assert rec.status == RecipientStatus.FAILED.value
    assert rec.error_code == "photo_timeout"

    # 3. Broadcast failed_count incremented, sent_count is 0
    assert b.sent_count == 0
    assert b.failed_count == 1


@pytest.mark.asyncio
async def test_d506_04_pro_quota_free_vs_pro_boundaries(test_session):
    """
    D5.0.6: Verifies quota boundaries:
    - Free organization has 0 broadcasts remaining.
    - Pro organization has 20 broadcasts per month.
    - Remaining never goes negative.
    """
    free_org = Organization(id="org_d506_free", name="Бесплатная Орг", slug="free-org-d506", category="Кафе", city_id="makhachkala", owner_user_id=906401)
    pro_org = Organization(id="org_d506_pro", name="Про Орг", slug="pro-org-d506", category="Клуб", city_id="makhachkala", owner_user_id=906402)
    pro_plan = OrganizationPlan(
        organization_id=pro_org.id,
        plan=PlanType.PRO.value,
        status=PlanStatus.ACTIVE.value,
        starts_at=datetime.now(timezone.utc),
    )
    test_session.add_all([free_org, pro_org, pro_plan])
    await test_session.commit()

    free_ent = await EntitlementService.get_entitlements(test_session, free_org.id)
    assert free_ent.limits.broadcasts_per_month == 0
    assert free_ent.limits.broadcasts_remaining == 0

    pro_ent = await EntitlementService.get_entitlements(test_session, pro_org.id)
    assert pro_ent.limits.broadcasts_per_month == 20
    assert pro_ent.limits.broadcasts_remaining == 20
    assert pro_ent.limits.broadcasts_remaining >= 0
