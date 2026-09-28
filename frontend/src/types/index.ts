export interface City {
  id: string;
  name: string;
  country: string;
  timezone: string;
  currency: string;
  is_active: boolean;
}

export interface Category {
  id: string;
  name: string;
  slug: string;
  is_active: boolean;
}

export type EventStatus = 'pending' | 'published' | 'rejected' | 'cancelled';

export interface EventSummary {
  id: string;
  title: string;
  cover_image_url?: string;
  category_id: string;
  category_name: string;
  city_id: string;
  city_name: string;
  start_at: string;
  venue_name: string;
  price_amount?: number;
  price_currency?: string;
  is_free: boolean;
  status: EventStatus;
  attendee_count: number;
  is_attending: boolean;
  created_at: string;
}

export interface EventResponse extends EventSummary {
  description: string;
  address?: string;
  organizer_user_id?: number;
  organizer_name?: string;
  rejection_reason?: string;
  updated_at: string;
}

export interface EventCreatePayload {
  title: string;
  description: string;
  cover_image_url?: string;
  category_id: string;
  city_id: string;
  start_at: string;
  venue_name: string;
  address?: string;
  price_amount?: number;
  price_currency?: string;
}

export type DateFilterType = 'all' | 'today' | 'tomorrow' | 'weekend';

export interface TelegramWebAppUser {
  id: number;
  is_bot?: boolean;
  first_name: string;
  last_name?: string;
  username?: string;
  language_code?: string;
  is_premium?: boolean;
}
