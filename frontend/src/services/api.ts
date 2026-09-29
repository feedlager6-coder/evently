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

export const api = {
  async getCities(search?: string): Promise<City[]> {
    const params = new URLSearchParams();
    if (search && search.trim()) {
      params.append('q', search.trim());
    }
    const queryStr = params.toString() ? `?${params.toString()}` : '';
    const res = await fetch(`${API_BASE}/cities${queryStr}`);
    if (!res.ok) throw new Error('Failed to fetch cities');
    return res.json();
  },

  async getNearestCity(latitude: number, longitude: number): Promise<City> {
    const res = await fetch(`${API_BASE}/cities/nearest?latitude=${latitude}&longitude=${longitude}`);
    if (!res.ok) throw new Error('Failed to determine nearest city');
    return res.json();
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
    const params = new URLSearchParams();
    params.append('q', q);
    if (cityId) params.append('city_id', cityId);

    const res = await fetch(`${API_BASE}/locations/suggest?${params.toString()}`);
    if (!res.ok) return [];
    return res.json();
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
