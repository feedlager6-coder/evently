export interface City {
  id: string;
  name: string;
  country: string;
  timezone: string;
  currency: string;
  latitude?: number;
  longitude?: number;
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
  address?: string;
  latitude?: number;
  longitude?: number;
  price_amount?: number;
  price_currency?: string;
  is_free: boolean;
  status: EventStatus;
  attendee_count: number;
  is_attending: boolean;
  interest_count: number;
  current_user_interested: boolean;
  organization_id?: string;
  organization_name?: string;
  organization_category?: string;
  organization_avatar_url?: string;
  views_count?: number;
  rejection_reason?: string;
  created_at: string;
}

export type TrackingSource = 'discovery' | 'deep_link' | 'personal' | 'organizer' | 'inline' | 'unknown';

export interface EventViewResponse {
  recorded: boolean;
  views_count: number;
}

export interface EventInterestResponse {
  event_id: string;
  is_interested: boolean;
  interest_count: number;
  is_attending: boolean;
  attendee_count: number;
  message: string;
}

export interface EventResponse extends EventSummary {
  description: string;
  organizer_user_id?: number;
  organizer_name?: string;
  organization_followers_count?: number;
  organization_is_subscribed?: boolean;
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
  latitude?: number;
  longitude?: number;
  price_amount?: number;
  price_currency?: string;
  organization_id?: string;
}

export const ORGANIZATION_CATEGORIES = [
  'Кафе',
  'Ресторан',
  'Бар',
  'Клуб',
  'Концертная площадка',
  'Театр',
  'Спорт',
  'Образование',
  'Культура',
  'Другое'
] as const;

export type OrganizationCategory = typeof ORGANIZATION_CATEGORIES[number] | string;

export interface OrganizationSummary {
  id: string;
  name: string;
  slug: string;
  category: string;
  city_id?: string;
  city_name?: string;
  address?: string;
  latitude?: number;
  longitude?: number;
  avatar_url?: string;
  status: string;
  is_verified: boolean;
  followers_count: number;
  events_count?: number;
  is_subscribed: boolean;
  is_owner: boolean;
  created_at: string;
}

export interface OrganizationResponse extends OrganizationSummary {
  description?: string;
  website?: string;
  social_link?: string;
  owner_user_id: number;
  updated_at: string;
}

export interface OrganizationCreatePayload {
  name: string;
  category: string;
  description?: string;
  city_id?: string;
  address?: string;
  latitude?: number;
  longitude?: number;
  avatar_url?: string;
  website?: string;
  social_link?: string;
}

export interface OrganizationUpdatePayload {
  name?: string;
  category?: string;
  description?: string;
  city_id?: string;
  address?: string;
  latitude?: number;
  longitude?: number;
  avatar_url?: string;
  website?: string;
  social_link?: string;
  status?: string;
}

export interface SubscriptionStatusResponse {
  is_subscribed: boolean;
  followers_count: number;
  message: string;
}

export interface UserSubscriptionItem {
  id: string;
  organization: OrganizationSummary;
  created_at: string;
}

export interface LocationSuggestion {
  title?: string;
  address: string;
  city?: string;
  latitude: number;
  longitude: number;
  display_name: string;
}


export interface UserProfile {
  id: number;
  telegram_id: number;
  username?: string;
  first_name?: string;
  last_name?: string;
  avatar_url?: string;
  default_city_id?: string;
  is_admin: boolean;
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

export interface VenueSummary {
  id: string;
  name: string;
  address?: string;
  city_id?: string;
  city_name?: string;
  latitude?: number;
  longitude?: number;
  organization_id?: string;
  organization_name?: string;
  organization_avatar_url?: string;
  upcoming_events_count: number;
}

export interface UnifiedDiscoveryResponse {
  query: string;
  city_id?: string;
  events: EventSummary[];
  organizations: OrganizationSummary[];
  venues: VenueSummary[];
  total_events: number;
  total_organizations: number;
  total_venues: number;
}

export interface CompanyStatusResponse {
  event_id: string;
  is_opted_in: boolean;
  is_active: boolean;
  note?: string;
  active_members_count: number;
  matches_count: number;
  pending_incoming_count: number;
}

export interface CompanyMemberItem {
  profile_id: string;
  display_name: string;
  avatar_url?: string;
  attendance_status: string;
  note?: string;
  relationship_status: 'none' | 'pending_outgoing' | 'pending_incoming' | 'matched';
  is_me?: boolean;
}

export interface CompanyRequestItem {
  request_id: string;
  other_user_id: number;
  other_user_display_name: string;
  other_user_avatar_url?: string;
  status: 'pending' | 'accepted' | 'declined' | 'cancelled';
  created_at: string;
}

export interface CompanyRequestsResponse {
  incoming: CompanyRequestItem[];
  outgoing: CompanyRequestItem[];
}

export interface CompanyMatchItem {
  match_id: string;
  partner_id: number;
  partner_display_name: string;
  partner_avatar_url?: string;
  partner_telegram_username?: string;
  partner_telegram_url?: string;
  has_telegram_username: boolean;
  attendance_status: string;
  matched_at: string;
}

export interface CompanyActionResponse {
  success: boolean;
  message: string;
  match_created: boolean;
  match?: CompanyMatchItem;
}

export interface OrganizationAudienceItem {
  id: string;
  name: string;
  slug: string;
  avatar_url?: string;
  category: string;
  city_name?: string;
  subscribers_count: number;
  new_subscribers_7d: number;
  new_subscribers_30d: number;
  events_count: number;
  total_views: number;
  total_interest: number;
  total_attendees: number;
}

export interface EventAudienceItem {
  id: string;
  title: string;
  start_at: string;
  venue_name: string;
  status: string;
  organization_id?: string;
  organization_name?: string;
  views_count: number;
  interest_count: number;
  attendee_count: number;
}

export interface OrganizerAudienceResponse {
  total_subscribers: number;
  new_subscribers_7d: number;
  new_subscribers_30d: number;
  total_views: number;
  total_interest: number;
  total_attendees: number;
  total_unique_engaged: number;
  organizations: OrganizationAudienceItem[];
  recent_events: EventAudienceItem[];
}

