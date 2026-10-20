import pytest
from datetime import datetime, timedelta, timezone
from tests.conftest import make_test_init_data
from app.models.event import Event, EventStatus, utc_now
from app.models.interest import EventInterest
from app.models.attendee import EventAttendee
from app.services.event_service import (
    remove_event_rsvp,
    remove_event_interest,
    get_user_personal_events,
    cleanup_expired_interests,
    delete_organizer_event,
)
from sqlalchemy import select


@pytest.mark.asyncio
async def test_unlike_and_unrsvp_allowed_for_past_events(client, test_session):
    # 1. Create a past event directly in DB
    past_start = utc_now() - timedelta(days=2)
    past_event = Event(
        title="Прошедший концерт",
        description="Концерт, который уже завершился",
        category_id="concerts",
        city_id="moscow",
        start_at=past_start,
        venue_name="Старая площадка",
        address="ул. Тверская, 1",
        status=EventStatus.PUBLISHED.value,
        organizer_user_id=1,
    )
    test_session.add(past_event)
    await test_session.commit()
    await test_session.refresh(past_event)

    # 2. Add attendee and interest manually as if user joined before it ended
    user_id = 999
    attendee = EventAttendee(event_id=past_event.id, user_id=user_id)
    interest = EventInterest(event_id=past_event.id, user_id=user_id)
    test_session.add(attendee)
    test_session.add(interest)
    await test_session.commit()

    # 3. Test remove_event_rsvp on past event: MUST succeed without raising EventPastError
    is_att, att_count, msg = await remove_event_rsvp(test_session, past_event.id, user_id)
    assert is_att is False
    assert att_count == 0

    # 4. Test remove_event_interest on past event: MUST succeed without raising EventPastError
    is_int, int_count, _, _, msg = await remove_event_interest(test_session, past_event.id, user_id)
    assert is_int is False
    assert int_count == 0


@pytest.mark.asyncio
async def test_personal_events_excludes_past_events(client, test_session):
    user_id = 1001
    now = utc_now()

    # Create one future event and one past event
    future_ev = Event(
        title="Будущая выставка",
        description="Выставка современного искусства",
        category_id="exhibitions",
        city_id="spb",
        start_at=now + timedelta(days=5),
        venue_name="Манеж",
        address="Исаакиевская пл., 1",
        status=EventStatus.PUBLISHED.value,
        organizer_user_id=1,
    )
    past_ev = Event(
        title="Прошедшая выставка",
        description="Выставка, которая уже завершилась",
        category_id="exhibitions",
        city_id="spb",
        start_at=now - timedelta(days=3),
        venue_name="Манеж",
        address="Исаакиевская пл., 1",
        status=EventStatus.PUBLISHED.value,
        organizer_user_id=1,
    )
    test_session.add_all([future_ev, past_ev])
    await test_session.commit()
    await test_session.refresh(future_ev)
    await test_session.refresh(past_ev)

    # User attends future_ev and past_ev
    test_session.add(EventAttendee(event_id=future_ev.id, user_id=user_id))
    test_session.add(EventAttendee(event_id=past_ev.id, user_id=user_id))
    # User interests future_ev and past_ev
    test_session.add(EventInterest(event_id=future_ev.id, user_id=user_id))
    test_session.add(EventInterest(event_id=past_ev.id, user_id=user_id))
    await test_session.commit()

    # get_user_personal_events('attending') -> only future_ev
    attending = await get_user_personal_events(test_session, user_id, event_type="attending")
    attending_ids = [e.id for e in attending]
    assert future_ev.id in attending_ids
    assert past_ev.id not in attending_ids

    # get_user_personal_events('interested') -> only future_ev
    interested = await get_user_personal_events(test_session, user_id, event_type="interested")
    interested_ids = [e.id for e in interested]
    assert future_ev.id in interested_ids
    assert past_ev.id not in interested_ids

    # Check background cleanup prunes dead interest from DB
    dead_interests = (
        await test_session.execute(
            select(EventInterest).where(EventInterest.event_id == past_ev.id, EventInterest.user_id == user_id)
        )
    ).scalars().all()
    assert len(dead_interests) == 0


@pytest.mark.asyncio
async def test_delete_created_past_event_by_author(client, test_session):
    author_id = 1002
    now = utc_now()

    past_ev = Event(
        title="Мой прошедший мастер-класс",
        description="Прошел на прошлой неделе",
        category_id="education",
        city_id="kazan",
        start_at=now - timedelta(days=7),
        venue_name="Коворкинг",
        address="ул. Баумана, 10",
        status=EventStatus.PUBLISHED.value,
        organizer_user_id=author_id,
    )
    test_session.add(past_ev)
    await test_session.commit()
    await test_session.refresh(past_ev)

    # Author deletes their past event
    deleted = await delete_organizer_event(test_session, past_ev.id, author_id)
    assert deleted.status == EventStatus.DELETED.value
