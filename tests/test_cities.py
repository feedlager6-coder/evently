import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_cities_returns_expanded_russian_cities(client: AsyncClient):
    """
    Verifies that GET /api/v1/cities returns all seeded Russian cities (at least 34),
    including key regional cities (Makhachkala, Kaspiysk, Derbent, Krasnodar, etc.).
    """
    response = await client.get("/api/v1/cities")
    assert response.status_code == 200

    cities = response.json()
    assert len(cities) >= 34

    city_ids = {c["id"] for c in cities}
    city_names = {c["name"] for c in cities}

    # Verify Dagestan and North Caucasus cities
    assert "makhachkala" in city_ids
    assert "kaspiysk" in city_ids
    assert "derbent" in city_ids
    assert "khasavyurt" in city_ids
    assert "izberbash" in city_ids

    # Verify major federal and regional hubs
    assert "moscow" in city_ids
    assert "spb" in city_ids
    assert "krasnodar" in city_ids
    assert "saratov" in city_ids
    assert "chelyabinsk" in city_ids
    assert "novosibirsk" in city_ids
    assert "kazan" in city_ids

    assert "Махачкала" in city_names
    assert "Каспийск" in city_names
    assert "Москва" in city_names
    assert "Санкт-Петербург" in city_names

    # Check structure of each city item
    for city in cities:
        assert "id" in city
        assert "name" in city
        assert "timezone" in city
        assert city["timezone"] is not None
        assert "country" in city
        assert "currency" in city
