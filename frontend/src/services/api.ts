import type {
  City,
  Category,
  EventSummary,
  EventResponse,
  EventCreatePayload,
  DateFilterType,
  EventStatus,
  LocationSuggestion,
  UserProfile,
  OrganizationSummary,
  OrganizationResponse,
  OrganizationCreatePayload,
  OrganizationUpdatePayload,
  SubscriptionStatusResponse,
  UserSubscriptionItem,
  UnifiedDiscoveryResponse,
  EventInterestResponse,
  CompanyStatusResponse,
  CompanyMemberItem,
  CompanyRequestsResponse,
  CompanyMatchItem,
  CompanyActionResponse,
  TrackingSource,
  EventViewResponse,
  OrganizerAudienceResponse,
  BroadcastItem,
  BroadcastDetail,
  BroadcastPreviewResponse,
  BroadcastCreateRequest
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

export function extractErrorMessage(errData: any, fallback: string): string {
  if (!errData) return fallback;
  if (typeof errData === 'string') return errData;
  if (typeof errData.detail === 'string') return errData.detail;
  if (Array.isArray(errData.detail)) {
    const msgs = errData.detail.map((item: any) => {
      if (typeof item === 'string') return item;
      const field = Array.isArray(item.loc) ? item.loc[item.loc.length - 1] : '';
      const msg = item.msg || '';
      if (field && field !== 'body') {
        const fieldLabels: Record<string, string> = {
          title: 'Название',
          description: 'Описание',
          venue_name: 'Место',
          address: 'Адрес',
          start_at: 'Дата и время',
          city_id: 'Город',
          category_id: 'Категория',
          price_amount: 'Цена',
          name: 'Название',
          slug: 'Короткая ссылка',
        };
        const label = fieldLabels[field] || field;
        return `${label}: ${msg}`;
      }
      return msg;
    }).filter(Boolean);
    if (msgs.length > 0) return msgs.join(', ');
  }
  if (errData.message && typeof errData.message === 'string') {
    return errData.message;
  }
  return fallback;
}

let cachedBotUsername = 'Ivently_bot';

export const DEFAULT_CITIES: City[] = [
  // Dagestan & North Caucasus
  { id: 'makhachkala', name: 'Махачкала', country: 'Россия', timezone: 'Europe/Moscow', currency: 'RUB', latitude: 42.9849, longitude: 47.5047, is_active: true },
  { id: 'kaspiysk', name: 'Каспийск', country: 'Россия', timezone: 'Europe/Moscow', currency: 'RUB', latitude: 42.8816, longitude: 47.6394, is_active: true },
  { id: 'derbent', name: 'Дербент', country: 'Россия', timezone: 'Europe/Moscow', currency: 'RUB', latitude: 42.0678, longitude: 48.2899, is_active: true },
  { id: 'khasavyurt', name: 'Хасавюрт', country: 'Россия', timezone: 'Europe/Moscow', currency: 'RUB', latitude: 43.2509, longitude: 46.5872, is_active: true },
  { id: 'izberbash', name: 'Избербаш', country: 'Россия', timezone: 'Europe/Moscow', currency: 'RUB', latitude: 42.5684, longitude: 47.8654, is_active: true },
  { id: 'grozny', name: 'Грозный', country: 'Россия', timezone: 'Europe/Moscow', currency: 'RUB', latitude: 43.3170, longitude: 45.6982, is_active: true },
  { id: 'vladikavkaz', name: 'Владикавказ', country: 'Россия', timezone: 'Europe/Moscow', currency: 'RUB', latitude: 43.0246, longitude: 44.6817, is_active: true },
  { id: 'nalchik', name: 'Нальчик', country: 'Россия', timezone: 'Europe/Moscow', currency: 'RUB', latitude: 43.4853, longitude: 43.6071, is_active: true },
  { id: 'pyatigorsk', name: 'Пятигорск', country: 'Россия', timezone: 'Europe/Moscow', currency: 'RUB', latitude: 44.0486, longitude: 43.0594, is_active: true },
  { id: 'stavropol', name: 'Ставрополь', country: 'Россия', timezone: 'Europe/Moscow', currency: 'RUB', latitude: 45.0433, longitude: 41.9691, is_active: true },

  // Major Federal Centers & Key Regions
  { id: 'moscow', name: 'Москва', country: 'Россия', timezone: 'Europe/Moscow', currency: 'RUB', latitude: 55.7558, longitude: 37.6173, is_active: true },
  { id: 'spb', name: 'Санкт-Петербург', country: 'Россия', timezone: 'Europe/Moscow', currency: 'RUB', latitude: 59.9343, longitude: 30.3351, is_active: true },
  { id: 'kazan', name: 'Казань', country: 'Россия', timezone: 'Europe/Moscow', currency: 'RUB', latitude: 55.7961, longitude: 49.1064, is_active: true },
  { id: 'krasnodar', name: 'Краснодар', country: 'Россия', timezone: 'Europe/Moscow', currency: 'RUB', latitude: 45.0355, longitude: 38.9753, is_active: true },
  { id: 'sochi', name: 'Сочи', country: 'Россия', timezone: 'Europe/Moscow', currency: 'RUB', latitude: 43.6028, longitude: 39.7342, is_active: true },
  { id: 'rostov_on_don', name: 'Ростов-на-Дону', country: 'Россия', timezone: 'Europe/Moscow', currency: 'RUB', latitude: 47.2357, longitude: 39.7015, is_active: true },
  { id: 'volgograd', name: 'Волгоград', country: 'Россия', timezone: 'Europe/Volgograd', currency: 'RUB', latitude: 48.7080, longitude: 44.5133, is_active: true },
  { id: 'saratov', name: 'Саратов', country: 'Россия', timezone: 'Europe/Saratov', currency: 'RUB', latitude: 51.5336, longitude: 46.0343, is_active: true },
  { id: 'voronezh', name: 'Воронеж', country: 'Россия', timezone: 'Europe/Moscow', currency: 'RUB', latitude: 51.6755, longitude: 39.2089, is_active: true },
  { id: 'samara', name: 'Самара', country: 'Россия', timezone: 'Europe/Samara', currency: 'RUB', latitude: 53.1959, longitude: 50.1002, is_active: true },
  { id: 'nizhny_novgorod', name: 'Нижний Новгород', country: 'Россия', timezone: 'Europe/Moscow', currency: 'RUB', latitude: 56.3269, longitude: 44.0059, is_active: true },
  { id: 'ufa', name: 'Уфа', country: 'Россия', timezone: 'Asia/Yekaterinburg', currency: 'RUB', latitude: 54.7388, longitude: 55.9721, is_active: true },
  { id: 'perm', name: 'Пермь', country: 'Россия', timezone: 'Asia/Yekaterinburg', currency: 'RUB', latitude: 58.0105, longitude: 56.2502, is_active: true },
  { id: 'yekaterinburg', name: 'Екатеринбург', country: 'Россия', timezone: 'Asia/Yekaterinburg', currency: 'RUB', latitude: 56.8389, longitude: 60.6057, is_active: true },
  { id: 'chelyabinsk', name: 'Челябинск', country: 'Россия', timezone: 'Asia/Yekaterinburg', currency: 'RUB', latitude: 55.1644, longitude: 61.4368, is_active: true },
  { id: 'tyumen', name: 'Тюмень', country: 'Россия', timezone: 'Asia/Yekaterinburg', currency: 'RUB', latitude: 57.1530, longitude: 65.5343, is_active: true },
  { id: 'omsk', name: 'Омск', country: 'Россия', timezone: 'Asia/Omsk', currency: 'RUB', latitude: 54.9885, longitude: 73.3242, is_active: true },
  { id: 'novosibirsk', name: 'Новосибирск', country: 'Россия', timezone: 'Asia/Novosibirsk', currency: 'RUB', latitude: 55.0084, longitude: 82.9357, is_active: true },
  { id: 'krasnoyarsk', name: 'Красноярск', country: 'Россия', timezone: 'Asia/Krasnoyarsk', currency: 'RUB', latitude: 56.0153, longitude: 92.8932, is_active: true },
  { id: 'irkutsk', name: 'Иркутск', country: 'Россия', timezone: 'Asia/Irkutsk', currency: 'RUB', latitude: 52.2870, longitude: 104.3050, is_active: true },
  { id: 'khabarovsk', name: 'Хабаровск', country: 'Россия', timezone: 'Asia/Vladivostok', currency: 'RUB', latitude: 48.4814, longitude: 135.0721, is_active: true },
  { id: 'vladivostok', name: 'Владивосток', country: 'Россия', timezone: 'Asia/Vladivostok', currency: 'RUB', latitude: 43.1155, longitude: 131.8855, is_active: true },
  { id: 'kaliningrad', name: 'Калининград', country: 'Россия', timezone: 'Europe/Kaliningrad', currency: 'RUB', latitude: 54.7104, longitude: 20.4522, is_active: true },
  { id: 'yaroslavl', name: 'Ярославль', country: 'Россия', timezone: 'Europe/Moscow', currency: 'RUB', latitude: 57.6261, longitude: 39.8845, is_active: true },
];

export const api = {
  getBotUsername(): string {
    return cachedBotUsername;
  },

  async getAppMeta(): Promise<{ app_name: string; bot_username: string; mini_app_url: string }> {
    try {
      const res = await fetch(`${API_BASE}/meta`);
      if (res.ok) {
        const data = await res.json();
        if (data.bot_username) {
          cachedBotUsername = data.bot_username;
        }
        return data;
      }
    } catch {
      // Fallback to default
    }
    return {
      app_name: 'Ivently',
      bot_username: cachedBotUsername,
      mini_app_url: `https://t.me/${cachedBotUsername}/app`,
    };
  },

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
    if (!res.ok) throw new Error('Не удалось загрузить события');
    return res.json();
  },

  async searchDiscovery(
    query: string,
    cityId?: string,
    categoryId?: string,
    limit: number = 15
  ): Promise<UnifiedDiscoveryResponse> {
    const params = new URLSearchParams();
    params.append('q', query);
    if (cityId) params.append('city_id', cityId);
    if (categoryId) params.append('category_id', categoryId);
    params.append('limit', limit.toString());

    const res = await fetch(`${API_BASE}/discovery/search?${params.toString()}`, {
      headers: getAuthHeaders(),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(extractErrorMessage(err, 'Не удалось выполнить поиск'));
    }
    return res.json();
  },

  async getEventDetails(eventId: string): Promise<EventResponse> {
    const res = await fetch(`${API_BASE}/events/${eventId}`, {
      headers: getAuthHeaders(),
    });
    if (!res.ok) throw new Error(`Мероприятие не найдено: ${eventId}`);
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

  async uploadOrganizationAvatar(file: File): Promise<{ url: string }> {
    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch(`${API_BASE}/organizations/upload-avatar`, {
        method: 'POST',
        headers: getAuthHeaders(false),
        body: formData,
      });
      if (res.ok) {
        return await res.json();
      }
    } catch {
      // Fallback below
    }
    // Fallback to uploadCoverImage
    return this.uploadCoverImage(file);
  },

  async suggestLocations(q: string, cityId?: string): Promise<LocationSuggestion[]> {
    const cleanQ = q.trim().replace(/\.+$/, '');
    if (cleanQ.length < 2) return [];

    try {
      const params = new URLSearchParams();
      params.append('q', cleanQ);
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
    const fallbackAddr = city ? `${cleanQ}, ${city.name}` : cleanQ;
    return [
      {
        title: cleanQ,
        address: fallbackAddr,
        city: city?.name,
        latitude: city.latitude || 42.9849,
        longitude: city.longitude || 47.5047,
        display_name: fallbackAddr,
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

  async addInterest(eventId: string): Promise<EventInterestResponse> {
    const res = await fetch(`${API_BASE}/events/${eventId}/interest`, {
      method: 'POST',
      headers: getAuthHeaders(),
    });
    if (!res.ok) {
      if (res.status === 401) throw new Error('Необходима авторизация через Telegram');
      const err = await res.json().catch(() => ({}));
      throw new Error(extractErrorMessage(err, 'Не удалось сохранить интерес к мероприятию'));
    }
    return res.json();
  },

  async removeInterest(eventId: string): Promise<EventInterestResponse> {
    const res = await fetch(`${API_BASE}/events/${eventId}/interest`, {
      method: 'DELETE',
      headers: getAuthHeaders(),
    });
    if (!res.ok) {
      if (res.status === 401) throw new Error('Необходима авторизация через Telegram');
      const err = await res.json().catch(() => ({}));
      throw new Error(extractErrorMessage(err, 'Не удалось удалить интерес к мероприятию'));
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
      throw new Error(extractErrorMessage(err, 'Ошибка создания мероприятия'));
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

  async getOrganizerAudience(orgId?: string): Promise<OrganizerAudienceResponse> {
    const url = orgId
      ? `${API_BASE}/organizer/audience?org_id=${encodeURIComponent(orgId)}`
      : `${API_BASE}/organizer/audience`;
    const res = await fetch(url, {
      headers: getAuthHeaders(),
    });
    if (!res.ok) {
      if (res.status === 401) {
        return {
          total_subscribers: 0,
          new_subscribers_7d: 0,
          new_subscribers_30d: 0,
          total_views: 0,
          total_interest: 0,
          total_attendees: 0,
          total_unique_engaged: 0,
          organizations: [],
          recent_events: [],
        };
      }
      throw new Error('Failed to fetch organizer audience');
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
  },

  // Organizations & Subscriptions
  async createOrganization(payload: OrganizationCreatePayload): Promise<OrganizationResponse> {
    const res = await fetch(`${API_BASE}/organizations`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      if (res.status === 401) throw new Error('Необходима авторизация через Telegram');
      const err = await res.json().catch(() => ({}));
      throw new Error(extractErrorMessage(err, 'Ошибка создания организации'));
    }
    return res.json();
  },

  async getOrganization(idOrSlug: string): Promise<OrganizationResponse> {
    const res = await fetch(`${API_BASE}/organizations/${encodeURIComponent(idOrSlug)}`, {
      headers: getAuthHeaders(),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(extractErrorMessage(err, 'Организация не найдена'));
    }
    return res.json();
  },

  async updateOrganization(orgId: string, payload: OrganizationUpdatePayload): Promise<OrganizationResponse> {
    const res = await fetch(`${API_BASE}/organizations/${encodeURIComponent(orgId)}`, {
      method: 'PATCH',
      headers: getAuthHeaders(),
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      if (res.status === 401) throw new Error('Необходима авторизация через Telegram');
      if (res.status === 403) throw new Error('Нет прав на редактирование этой организации');
      const err = await res.json().catch(() => ({}));
      throw new Error(extractErrorMessage(err, 'Ошибка обновления профиля организации'));
    }
    return res.json();
  },

  async getMyOrganizations(): Promise<OrganizationSummary[]> {
    const res = await fetch(`${API_BASE}/organizations/me`, {
      headers: getAuthHeaders(),
    });
    if (!res.ok) {
      if (res.status === 401) return [];
      throw new Error('Failed to fetch my organizations');
    }
    const data = await res.json();
    return Array.isArray(data) ? data : data.organizations || [];
  },

  async getOrganizationEvents(orgId: string): Promise<EventSummary[]> {
    const res = await fetch(`${API_BASE}/organizations/${encodeURIComponent(orgId)}/events`, {
      headers: getAuthHeaders(),
    });
    if (!res.ok) {
      throw new Error('Failed to fetch organization events');
    }
    return res.json();
  },

  async subscribeOrganization(orgId: string): Promise<SubscriptionStatusResponse> {
    const res = await fetch(`${API_BASE}/organizations/${encodeURIComponent(orgId)}/subscribe`, {
      method: 'POST',
      headers: getAuthHeaders(),
    });
    if (!res.ok) {
      if (res.status === 401) throw new Error('Необходима авторизация через Telegram');
      const err = await res.json().catch(() => ({}));
      throw new Error(extractErrorMessage(err, 'Не удалось подписаться'));
    }
    return res.json();
  },

  async unsubscribeOrganization(orgId: string): Promise<SubscriptionStatusResponse> {
    const res = await fetch(`${API_BASE}/organizations/${encodeURIComponent(orgId)}/subscribe`, {
      method: 'DELETE',
      headers: getAuthHeaders(),
    });
    if (!res.ok) {
      if (res.status === 401) throw new Error('Необходима авторизация через Telegram');
      const err = await res.json().catch(() => ({}));
      throw new Error(extractErrorMessage(err, 'Не удалось отписаться'));
    }
    return res.json();
  },

  async getMySubscriptions(): Promise<UserSubscriptionItem[]> {
    const res = await fetch(`${API_BASE}/users/me/subscriptions`, {
      headers: getAuthHeaders(),
    });
    if (!res.ok) {
      if (res.status === 401) return [];
      throw new Error('Failed to fetch user subscriptions');
    }
    return res.json();
  },

  async getMyPersonalEvents(type: 'attending' | 'interested' = 'attending'): Promise<EventSummary[]> {
    const res = await fetch(`${API_BASE}/users/me/events?type=${encodeURIComponent(type)}`, {
      headers: getAuthHeaders(),
    });
    if (!res.ok) {
      if (res.status === 401) return [];
      throw new Error('Не удалось загрузить ваши события');
    }
    return res.json();
  },

  async trackEventView(
    eventId: string,
    source: TrackingSource = 'unknown',
    broadcastToken?: string | null
  ): Promise<EventViewResponse | null> {
    try {
      const payload: { source: TrackingSource; broadcast_token?: string } = { source };
      if (broadcastToken) {
        payload.broadcast_token = broadcastToken;
      }
      const res = await fetch(`${API_BASE}/events/${encodeURIComponent(eventId)}/view`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(payload),
      });
      if (!res.ok) return null;
      return await res.json();
    } catch {
      return null;
    }
  },

  // Event Company Discovery ("Найти компанию")
  async getCompanyStatus(eventId: string): Promise<CompanyStatusResponse> {
    const res = await fetch(`${API_BASE}/events/${encodeURIComponent(eventId)}/company/status`, {
      headers: getAuthHeaders(),
    });
    if (!res.ok) {
      throw new Error('Не удалось получить статус поиска компании');
    }
    return res.json();
  },

  async updateCompanyProfile(eventId: string, payload: { is_active?: boolean; note?: string }): Promise<CompanyStatusResponse> {
    const res = await fetch(`${API_BASE}/events/${encodeURIComponent(eventId)}/company/profile`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(extractErrorMessage(err, 'Не удалось обновить статус поиска компании'));
    }
    return res.json();
  },

  async optOutCompany(eventId: string): Promise<CompanyStatusResponse> {
    const res = await fetch(`${API_BASE}/events/${encodeURIComponent(eventId)}/company/profile`, {
      method: 'DELETE',
      headers: getAuthHeaders(),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(extractErrorMessage(err, 'Не удалось скрыть анкету'));
    }
    return res.json();
  },

  async getCompanyMembers(eventId: string): Promise<CompanyMemberItem[]> {
    const res = await fetch(`${API_BASE}/events/${encodeURIComponent(eventId)}/company/members`, {
      headers: getAuthHeaders(),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(extractErrorMessage(err, 'Не удалось загрузить список участников'));
    }
    return res.json();
  },

  async sendCompanyRequest(eventId: string, targetProfileId: string): Promise<CompanyActionResponse> {
    const res = await fetch(`${API_BASE}/events/${encodeURIComponent(eventId)}/company/requests`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ target_profile_id: targetProfileId }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(extractErrorMessage(err, 'Не удалось отправить запрос'));
    }
    return res.json();
  },

  async getCompanyRequests(eventId: string): Promise<CompanyRequestsResponse> {
    const res = await fetch(`${API_BASE}/events/${encodeURIComponent(eventId)}/company/requests`, {
      headers: getAuthHeaders(),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(extractErrorMessage(err, 'Не удалось загрузить запросы'));
    }
    return res.json();
  },

  async acceptCompanyRequest(eventId: string, requestId: string): Promise<CompanyActionResponse> {
    const res = await fetch(`${API_BASE}/events/${encodeURIComponent(eventId)}/company/requests/${encodeURIComponent(requestId)}/accept`, {
      method: 'POST',
      headers: getAuthHeaders(),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(extractErrorMessage(err, 'Не удалось принять запрос'));
    }
    return res.json();
  },

  async declineCompanyRequest(eventId: string, requestId: string): Promise<CompanyActionResponse> {
    const res = await fetch(`${API_BASE}/events/${encodeURIComponent(eventId)}/company/requests/${encodeURIComponent(requestId)}/decline`, {
      method: 'POST',
      headers: getAuthHeaders(),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(extractErrorMessage(err, 'Не удалось отклонить запрос'));
    }
    return res.json();
  },

  async cancelCompanyRequest(eventId: string, requestId: string): Promise<CompanyActionResponse> {
    const res = await fetch(`${API_BASE}/events/${encodeURIComponent(eventId)}/company/requests/${encodeURIComponent(requestId)}`, {
      method: 'DELETE',
      headers: getAuthHeaders(),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(extractErrorMessage(err, 'Не удалось отменить запрос'));
    }
    return res.json();
  },

  async getCompanyMatches(eventId: string): Promise<CompanyMatchItem[]> {
    const res = await fetch(`${API_BASE}/events/${encodeURIComponent(eventId)}/company/matches`, {
      headers: getAuthHeaders(),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(extractErrorMessage(err, 'Не удалось загрузить совпадения'));
    }
    return res.json();
  },

  async previewBroadcast(payload: BroadcastCreateRequest): Promise<BroadcastPreviewResponse> {
    const res = await fetch(`${API_BASE}/organizer/broadcasts/preview`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(extractErrorMessage(err, 'Не удалось рассчитать аудиторию рассылки'));
    }
    return res.json();
  },

  async createBroadcast(payload: BroadcastCreateRequest): Promise<BroadcastDetail> {
    const res = await fetch(`${API_BASE}/organizer/broadcasts`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(extractErrorMessage(err, 'Не удалось создать рассылку'));
    }
    return res.json();
  },

  async getOrganizerBroadcasts(): Promise<BroadcastItem[]> {
    const res = await fetch(`${API_BASE}/organizer/broadcasts`, {
      headers: getAuthHeaders(),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(extractErrorMessage(err, 'Не удалось загрузить список рассылок'));
    }
    return res.json();
  },

  async getBroadcastDetail(broadcastId: string): Promise<BroadcastDetail> {
    const res = await fetch(`${API_BASE}/organizer/broadcasts/${encodeURIComponent(broadcastId)}`, {
      headers: getAuthHeaders(),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(extractErrorMessage(err, 'Не удалось загрузить детали рассылки'));
    }
    return res.json();
  }
};

