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

export type EventStatus = 'pending' | 'published' | 'rejected' | 'cancelled' | 'deleted';

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
  allow_event_contact?: boolean;
  source_type?: string;
  source_name?: string;
  views_count?: number;
  broadcast_opens_count?: number;
  broadcast_interest_count?: number;
  broadcast_rsvp_count?: number;
  rejection_reason?: string;
  created_at: string;
}

export type TrackingSource = 'discovery' | 'deep_link' | 'personal' | 'organizer' | 'inline' | 'broadcast' | 'unknown';

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
  organizer_username?: string;
  organizer_contact_url?: string;
  external_id?: string;
  source_url?: string;
  last_synced_at?: string;
  organization_followers_count?: number;
  organization_is_subscribed?: boolean;
  is_organizer?: boolean;
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
  allow_event_contact?: boolean;
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

export type BroadcastTargetType = 'organization_subscribers' | 'event_interest';
export type BroadcastType = 'marketing' | 'transactional';
export type BroadcastTemplateKey = 'event_announcement' | 'event_update' | 'custom_update';
export type BroadcastStatus = 'draft' | 'queued' | 'processing' | 'completed' | 'partially_failed' | 'failed' | 'cancelled';

export interface BroadcastItem {
  id: string;
  organization_id: string;
  organization_name: string;
  event_id?: string | null;
  event_title?: string | null;
  target_type: BroadcastTargetType;
  broadcast_type: BroadcastType;
  template_key: BroadcastTemplateKey;
  custom_text?: string | null;
  status: BroadcastStatus;
  total_recipients: number;
  sent_count: number;
  delivered_count: number;
  failed_count: number;
  blocked_count: number;
  opened_count?: number;
  interest_count?: number;
  rsvp_count?: number;
  open_rate?: number;
  interest_conversion?: number;
  rsvp_conversion?: number;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
}

export interface BroadcastDetail extends BroadcastItem {
  message_text: string;
  button_text: string;
  button_url: string;
  attribution_token?: string | null;
}

export interface BroadcastPreviewResponse {
  organization_id: string;
  organization_name: string;
  target_type: string;
  broadcast_type: string;
  template_key: string;
  event_id?: string | null;
  event_title?: string | null;
  total_audience: number;
  eligible_recipients: number;
  disabled_notifications_count: number;
  fatigued_recipients_count: number;
  preview_text: string;
  preview_button_text: string;
  preview_button_url: string;
  cover_image_url?: string | null;
}

export interface BroadcastCreateRequest {
  organization_id: string;
  target_type: BroadcastTargetType;
  broadcast_type: BroadcastType;
  template_key: BroadcastTemplateKey;
  event_id?: string | null;
  custom_text?: string | null;
}

export interface AudienceGrowthMetrics {
  total_subscribers: number;
  new_subscribers_7d: number;
  new_subscribers_30d: number;
  total_unique_engaged: number;
}

export interface EventPerformanceTotals {
  total_events: number;
  upcoming_events_count: number;
  past_events_count: number;
  total_views: number;
  total_interest: number;
  total_rsvps: number;
}

export interface BroadcastPerformanceTotals {
  total_broadcasts: number;
  total_delivered: number;
  total_opened: number;
  total_attributed_interest: number;
  total_attributed_rsvp: number;
  overall_open_rate: number;
  overall_interest_conversion: number;
  overall_rsvp_conversion: number;
}

export interface ViewSourceMetric {
  source: string;
  label: string;
  views_count: number;
  percentage: number;
}

export interface OrganizerInsightsResponse {
  audience: AudienceGrowthMetrics;
  events: EventPerformanceTotals;
  broadcasts: BroadcastPerformanceTotals;
  sources: ViewSourceMetric[];
  fact_sentence: string;
  has_data: boolean;
}

export type CapabilityStatus = 'available' | 'locked' | 'coming_soon';

export interface CapabilityInfo {
  key: string;
  title: string;
  description: string;
  status: CapabilityStatus;
  is_pro_feature: boolean;
  limit?: number | null;
}

export interface EntitlementLimits {
  broadcasts_per_month: number;
  broadcasts_used_this_month: number;
  broadcasts_remaining: number;
}

export interface OrganizerEntitlementsResponse {
  organization_id?: string | null;
  organization_name?: string | null;
  plan: 'free' | 'pro' | string;
  status: 'active' | 'expired' | 'cancelled' | string;
  starts_at?: string | null;
  expires_at?: string | null;
  capabilities: Record<string, CapabilityInfo>;
  limits: EntitlementLimits;
}

export interface AdminOrganizationItem {
  id: string;
  name: string;
  slug: string;
  category: string;
  city_id: string;
  owner_user_id: number;
  status: string;
  plan: 'free' | 'pro' | string;
  plan_status: string;
  created_at: string;
}

export interface PaymentConfigResponse {
  payments_enabled: boolean;
  pro_monthly_price_rub: number;
  pro_days: number;
}

export interface PaymentOrder {
  id: string;
  organization_id: string;
  amount: number;
  currency: string;
  status: 'pending' | 'waiting_for_payment' | 'succeeded' | 'canceled' | 'failed' | 'refunded' | string;
  service_name: string;
  confirmation_url?: string | null;
  paid_at?: string | null;
  expires_at?: string | null;
  receipt_status: 'pending' | 'issued' | 'not_required' | string;
  receipt_url?: string | null;
  created_at: string;
}

export interface CreatePaymentOrderRequest {
  organization_id: string;
  customer_email?: string | null;
}



