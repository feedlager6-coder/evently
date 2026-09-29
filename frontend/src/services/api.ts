import type {
  City,
  Category,
  EventSummary,
  EventResponse,
  EventCreatePayload,
  DateFilterType,
  EventStatus,
  LocationSuggestion,
  UserProfile
} from '../types';
import { telegram } from './telegram';

const API_BASE = '/api/v1';

function getAuthHeaders(isJson: boolean = true): HeadersInit {
  const initData = telegram.getInitData();
  const headers: Record<string, string> = {};
  if (isJson) {
    headers['Content-Type'] = 'application/json';
  }
  if (initData) {
    headers['Authorization'] = `tma ${initData}`;
  }
  return headers;
}

export const DEFAULT_CITIES: City[] = [
  { id: 'makhachkala', name: 'Махачкала', country: 'Россия', timezone: 'Europe/Moscow', currency: 'RUB', latitude: 42.9849, longitude: 47.5047, is_active: true },
  { id: 'moscow', name: 'Москва', country: 'Россия', timezone: 'Europe/Moscow', currency: 'RUB', latitude: 55.7558, longitude: 37.6173, is_active: true },
  { id: 'spb', name: 'Санкт-Петербург', country: 'Россия', timezone: 'Europe/Moscow', currency: 'RUB', latitude: 59.9343, longitude: 30.3351, is_active: true },
  { id: 'kazan', name: 'Казань', country: 'Россия', timezone: 'Europe/Moscow', currency: 'RUB', latitude: 55.7961, longitude: 49.1064, is_active: true },
  { id: 'krasnodar', name: 'Краснодар', country: 'Россия', timezone: 'Europe/Moscow', currency: 'RUB', latitude: 45.0355, longitude: 38.9753, is_active: true },
  { id: 'rostov_on_don', name: 'Ростов-на-Дону', country: 'Россия', timezone: 'Europe/Moscow', currency: 'RUB', latitude: 47.2357, longitude: 39.7015, is_active: true },
  { id: 'yekaterinburg', name: 'Екатеринбург', country: 'Россия', timezone: 'Asia/Yekaterinburg', currency: 'RUB', latitude: 56.8389, longitude: 60.6057, is_active: true },
  { id: 'novosibirsk', name: 'Новосибирск', country: 'Россия', timezone: 'Asia/Novosibirsk', currency: 'RUB', latitude: 55.0084, longitude: 82.9357, is_active: true },
  { id: 'nizhny_novgorod', name: 'Нижний Новгород', country: 'Россия', timezone: 'Europe/Moscow', currency: 'RUB', latitude: 56.3269, longitude: 44.0059, is_active: true },
  { id: 'samara', name: 'Самара', country: 'Россия', timezone: 'Europe/Samara', currency: 'RUB', latitude: 53.1959, longitude: 50.1002, is_active: true },
  { id: 'ufa', name: 'Уфа', country: 'Россия', timezone: 'Asia/Yekaterinburg', currency: 'RUB', latitude: 54.7388, longitude: 55.9721, is_active: true },
  { id: 'voronezh', name: 'Воронеж', country: 'Россия', timezone: 'Europe/Moscow', currency: 'RUB', latitude: 51.6755, longitude: 39.2089, is_active: true },
  { id: 'perm', name: 'Пермь', country: 'Россия', timezone: 'Asia/Yekaterinburg', currency: 'RUB', latitude: 58.0105, longitude: 56.2502, is_active: true },
  { id: 'volgograd', name: 'Волгоград', country: 'Россия', timezone: 'Europe/Moscow', currency: 'RUB', latitude: 48.7080, longitude: 44.5133, is_active: true },
  { id: 'sochi', name: 'Сочи', country: 'Россия', timezone: 'Europe/Moscow', currency: 'RUB', latitude: 43.6028, longitude: 39.7342, is_active: true },
];

export const api = {
  async getCities(search?: string): Promise<City[]> {
    try {
      const params = new URLSearchParams();
      if (search && search.trim()) {
        params.append('q', search.trim());
      }
      const queryStr = params.toString() ? `?${params.toString()}` : '';
      const res = await fetch(`${API_BASE}/cities${queryStr}`);
      if (!res.ok) throw new Error('Failed to fetch cities');
      const data = await res.json();
      return Array.isArray(data) && data.length > 0 ? data : DEFAULT_CITIES;
    } catch {
      if (search && search.trim()) {
        const q = search.toLowerCase().trim();
        return DEFAULT_CITIES.filter(c => c.name.toLowerCase().includes(q) || c.id.toLowerCase().includes(q));
      }
      return DEFAULT_CITIES;
    }
  },

  async getNearestCity(latitude: number, longitude: number): Promise<City> {
    try {
      const res = await fetch(`${API_BASE}/cities/nearest?latitude=${latitude}&longitude=${longitude}`);
      if (res.ok) {
        return await res.json();
      }
    } catch {
      // Local fallback
    }
    let closest = DEFAULT_CITIES[0];
    let minD = Infinity;
    for (const c of DEFAULT_CITIES) {
      if (c.latitude != null && c.longitude != null) {
        const d = Math.hypot(c.latitude - latitude, c.longitude - longitude);
        if (d < minD) {
          minD = d;
          closest = c;
        }
      }
    }
    return closest;
  },

  async getCategories(): Promise<Category[]> {
    const res = await fetch(`${API_BASE}/categories`);
    if (!res.ok) throw new Error('Failed to fetch categories');
    return res.json();
  },

  async getEvents(
    cityId?: string,
    categoryId?: string,
    dateFilter: DateFilterType = 'all'
  ): Promise<{ events: EventSummary[]; total: number }> {
    const params = new URLSearchParams();
    if (cityId) params.append('city_id', cityId);
    if (categoryId) params.append('category_id', categoryId);
    if (dateFilter && dateFilter !== 'all') params.append('date_filter', dateFilter);

    const res = await fetch(`${API_BASE}/events?${params.toString()}`, {
      headers: getAuthHeaders(),
    });
    if (!res.ok) throw new Error('Failed to fetch events');
    return res.json();
  },

  async getEventDetails(eventId: string): Promise<EventResponse> {
    const res = await fetch(`${API_BASE}/events/${eventId}`, {
      headers: getAuthHeaders(),
    });
    if (!res.ok) throw new Error(`Event not found: ${eventId}`);
    return res.json();
  },

  async uploadCoverImage(file: File): Promise<{ url: string }> {
    const formData = new FormData();
    formData.append('file', file);

    const res = await fetch(`${API_BASE}/events/upload-cover`, {
      method: 'POST',
      headers: getAuthHeaders(false),
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Не удалось загрузить изображение');
    }
    return res.json();
  },

  async suggestLocations(q: string, cityId?: string): Promise<LocationSuggestion[]> {
    try {
      const params = new URLSearchParams();
      params.append('q', q);
      if (cityId) params.append('city_id', cityId);

      const res = await fetch(`${API_BASE}/locations/suggest?${params.toString()}`);
      if (res.ok) {
        const list = await res.json();
        if (Array.isArray(list) && list.length > 0) return list;
      }
    } catch {
      // Fall through to resilient local suggestion
    }

    const city = DEFAULT_CITIES.find(c => c.id === cityId) || DEFAULT_CITIES[0];
    const cleanQ = q.trim();
    return [
      {
        display_name: `${cleanQ}, ${city.name}`,
        address: `${cleanQ}, ${city.name}`,
        latitude: city.latitude || 42.9849,
        longitude: city.longitude || 47.5047,
      }
    ];
  },

  async getCurrentUser(): Promise<UserProfile | null> {
    try {
      const res = await fetch(`${API_BASE}/users/me`, {
        headers: getAuthHeaders(),
      });
      if (!res.ok) return null;
      return res.json();
    } catch {
      return null;
    }
  },

  async addRsvp(eventId: string): Promise<{ is_attending: boolean; attendee_count: number }> {
    const res = await fetch(`${API_BASE}/events/${eventId}/rsvp`, {
      method: 'POST',
      headers: getAuthHeaders(),
    });
    if (!res.ok) {
      if (res.status === 401) throw new Error('Необходима авторизация через Telegram');
      throw new Error('Не удалось зарегистрироваться на мероприятие');
    }
    return res.json();
  },

  async removeRsvp(eventId: string): Promise<{ is_attending: boolean; attendee_count: number }> {
    const res = await fetch(`${API_BASE}/events/${eventId}/rsvp`, {
      method: 'DELETE',
      headers: getAuthHeaders(),
    });
    if (!res.ok) {
      if (res.status === 401) throw new Error('Необходима авторизация через Telegram');
      throw new Error('Не удалось отменить регистрацию');
    }
    return res.json();
  },

  async createEvent(payload: EventCreatePayload): Promise<EventResponse> {
    const res = await fetch(`${API_BASE}/events`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      if (res.status === 401) throw new Error('Необходима авторизация через Telegram');
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Ошибка создания мероприятия');
    }
    return res.json();
  },

  async getOrganizerEvents(): Promise<EventSummary[]> {
    const res = await fetch(`${API_BASE}/organizer/events`, {
      headers: getAuthHeaders(),
    });
    if (!res.ok) {
      if (res.status === 401) return [];
      throw new Error('Failed to fetch organizer events');
    }
    return res.json();
  },

  async getAdminEvents(status: EventStatus = 'pending'): Promise<EventSummary[]> {
    const res = await fetch(`${API_BASE}/admin/events?status=${status}&status_filter=${status}`, {
      headers: getAuthHeaders(),
    });
    if (!res.ok) {
      if (res.status === 403) throw new Error('Доступ запрещен: требуются права администратора');
      if (res.status === 401) throw new Error('Требуется авторизация в Telegram');
      throw new Error('Failed to fetch admin moderation queue');
    }
    return res.json();
  },

  async adminPublishEvent(eventId: string): Promise<EventResponse> {
    const res = await fetch(`${API_BASE}/admin/events/${eventId}/publish`, {
      method: 'POST',
      headers: getAuthHeaders(),
    });
    if (!res.ok) throw new Error('Failed to publish event');
    return res.json();
  },

  async adminRejectEvent(eventId: string, reason: string): Promise<EventResponse> {
    const res = await fetch(`${API_BASE}/admin/events/${eventId}/reject`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ reason }),
    });
    if (!res.ok) throw new Error('Failed to reject event');
    return res.json();
  },

  async adminCancelEvent(eventId: string): Promise<EventResponse> {
    const res = await fetch(`${API_BASE}/admin/events/${eventId}/cancel`, {
      method: 'POST',
      headers: getAuthHeaders(),
    });
    if (!res.ok) throw new Error('Failed to cancel event');
    return res.json();
  }
};
