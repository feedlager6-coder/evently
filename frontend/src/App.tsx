import React, { useState, useEffect, useCallback, useRef } from 'react';
import type { 
  City, 
  Category, 
  EventSummary, 
  EventResponse, 
  DateFilterType, 
  EventStatus,
  TelegramWebAppUser,
  OrganizationSummary,
  OrganizationResponse,
  VenueSummary,
  EventInterestResponse,
  TrackingSource
} from './types';
import { api, DEFAULT_CITIES } from './services/api';
import { telegram } from './services/telegram';
import { Header } from './components/Header';
import { CityModal } from './components/CityModal';
import { FilterBar } from './components/FilterBar';
import { EventCard } from './components/EventCard';
import { EventDetailsModal } from './components/EventDetailsModal';
import { CreateEventModal } from './components/CreateEventModal';
import { OrganizerTab } from './components/OrganizerTab';
import { OrganizerWorkspace } from './components/OrganizerWorkspace';
import type { WorkspaceTab } from './components/OrganizerWorkspace';
import { AdminTab } from './components/AdminTab';
import { Navigation } from './components/Navigation';
import { OrganizationModal } from './components/OrganizationModal';
import { CreateOrganizationModal } from './components/CreateOrganizationModal';
import { MySubscriptionsModal } from './components/MySubscriptionsModal';
import { DiscoveryModal } from './components/DiscoveryModal';
import { EventCompanyModal } from './components/EventCompanyModal';
import { UserProfileModal } from './components/UserProfileModal';
import { TicketModal } from './components/TicketModal';
import type { TabType } from './components/Navigation';
import type { UserSubscriptionItem } from './types';
import { Loader2, Compass, AlertCircle, RefreshCw, Search, MapPin, Plus, Calendar, SlidersHorizontal, Bookmark, ChevronRight } from 'lucide-react';
import { SafeImage } from './components/SafeImage';

export const App: React.FC = () => {
  // Navigation & UI state
  const [currentTab, setCurrentTab] = useState<TabType>('feed');
  const [isCityModalOpen, setIsCityModalOpen] = useState<boolean>(false);

  // Core metadata - initialize with cached cities for instant 0ms startup
  const [cities, setCities] = useState<City[]>(() => api.getCachedCities());
  const [categories, setCategories] = useState<Category[]>([]);
  const [selectedCityId, setSelectedCityId] = useState<string>(() => {
    try {
      const saved = localStorage.getItem('evently_selected_city_id');
      const cached = api.getCachedCities();
      if (saved && cached.some((c) => c.id === saved)) return saved;
      return 'makhachkala';
    } catch {
      return 'makhachkala';
    }
  });
  const [selectedCategoryId, setSelectedCategoryId] = useState<string | undefined>(undefined);
  const [dateFilter, setDateFilter] = useState<DateFilterType>('all');

  // Discovery Feed state
  const [events, setEvents] = useState<EventSummary[]>([]);
  const [isLoadingEvents, setIsLoadingEvents] = useState(true);
  const [feedError, setFeedError] = useState<string | null>(null);

  // Active Event Details modal
  const [selectedEventDetails, setSelectedEventDetails] = useState<EventResponse | null>(null);
  const [isDetailsOpen, setIsDetailsOpen] = useState(false);
  const isDetailsOpenRef = useRef(false);
  useEffect(() => {
    isDetailsOpenRef.current = isDetailsOpen;
  }, [isDetailsOpen]);

  // Horizontal Carousel ref & gesture lock to prevent iOS TMA pull-to-dismiss
  const carouselTrackRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    const el = carouselTrackRef.current;
    if (!el) return;

    let startX = 0;
    let startY = 0;
    let isHorizontalGesture: boolean | null = null;

    const onTouchStart = (e: TouchEvent) => {
      if (e.touches.length !== 1) return;
      startX = e.touches[0].clientX;
      startY = e.touches[0].clientY;
      isHorizontalGesture = null;
      try {
        window.Telegram?.WebApp?.disableVerticalSwipes?.();
      } catch {
        // ignore
      }
    };

    const onTouchMove = (e: TouchEvent) => {
      if (e.touches.length !== 1) return;
      const dx = Math.abs(e.touches[0].clientX - startX);
      const dy = Math.abs(e.touches[0].clientY - startY);

      if (isHorizontalGesture === null && (dx > 4 || dy > 4)) {
        isHorizontalGesture = dx >= dy;
      }

      if (isHorizontalGesture) {
        e.stopPropagation();
      }
    };

    el.addEventListener('touchstart', onTouchStart, { passive: true });
    el.addEventListener('touchmove', onTouchMove, { passive: false });

    return () => {
      el.removeEventListener('touchstart', onTouchStart);
      el.removeEventListener('touchmove', onTouchMove);
    };
  }, [dateFilter]);

  const isDeepLinkActiveRef = useRef<boolean>(false);
  const [isRsvpLoading, setIsRsvpLoading] = useState(false);
  const [isInterestLoading, setIsInterestLoading] = useState(false);

  // Event Company Modal state
  const [companyEvent, setCompanyEvent] = useState<EventResponse | null>(null);
  const [isCompanyModalOpen, setIsCompanyModalOpen] = useState(false);

  // Personal Hub state (attending, interested, subscriptions)
  const [attendingEvents, setAttendingEvents] = useState<EventSummary[]>([]);
  const [isLoadingAttending, setIsLoadingAttending] = useState(false);
  const [interestedEvents, setInterestedEvents] = useState<EventSummary[]>([]);
  const [isLoadingInterested, setIsLoadingInterested] = useState(false);
  const [userSubscriptions, setUserSubscriptions] = useState<UserSubscriptionItem[]>([]);
  const [isLoadingUserSubscriptions, setIsLoadingUserSubscriptions] = useState(false);

  // Organizer workspace & creation state
  const [isOrganizerWorkspaceOpen, setIsOrganizerWorkspaceOpen] = useState(false);
  const [workspaceInitialTab, setWorkspaceInitialTab] = useState<WorkspaceTab>('overview');
  const [workspaceBroadcastEventId, setWorkspaceBroadcastEventId] = useState<string | null>(null);
  const [workspaceBroadcastOrgId, setWorkspaceBroadcastOrgId] = useState<string | null>(null);
  const [workspaceOpenProModal, setWorkspaceOpenProModal] = useState<boolean>(false);
  const [paymentReturnOrderId, setPaymentReturnOrderId] = useState<string | null>(null);
  const [isCreateEventModalOpen, setIsCreateEventModalOpen] = useState(false);
  const [organizerEvents, setOrganizerEvents] = useState<EventSummary[]>([]);
  const [isLoadingOrganizer, setIsLoadingOrganizer] = useState(false);
  const [myOrganizations, setMyOrganizations] = useState<OrganizationSummary[]>([]);
  const [isLoadingMyOrganizations, setIsLoadingMyOrganizations] = useState(false);

  // Organizations Modals state
  const [selectedOrgId, setSelectedOrgId] = useState<string | null>(null);
  const [isOrgModalOpen, setIsOrgModalOpen] = useState(false);
  const [isCreateOrgModalOpen, setIsCreateOrgModalOpen] = useState(false);
  const [editingOrgData, setEditingOrgData] = useState<OrganizationResponse | null>(null);
  const [isSubscriptionsModalOpen, setIsSubscriptionsModalOpen] = useState(false);
  const [preselectedOrgForEventCreate, setPreselectedOrgForEventCreate] = useState<string | undefined>(undefined);
  const [editingEventData, setEditingEventData] = useState<EventResponse | null>(null);
  const [editingDraftData, setEditingDraftData] = useState<any | null>(null);

  // Admin tab state
  const [isAdmin, setIsAdmin] = useState(false);
  const [adminStatusFilter, setAdminStatusFilter] = useState<EventStatus>('pending');
  const [adminEvents, setAdminEvents] = useState<EventSummary[]>([]);
  const [isLoadingAdmin, setIsLoadingAdmin] = useState(false);

  // Telegram User
  const [user, setUser] = useState<TelegramWebAppUser | null>(null);

  // User Profile modal state
  const [isUserProfileModalOpen, setIsUserProfileModalOpen] = useState(false);

  // Electronic Ticket Modal state
  const [ticketEvent, setTicketEvent] = useState<EventResponse | EventSummary | null>(null);
  const [isTicketModalOpen, setIsTicketModalOpen] = useState(false);
  const [organizerInitialFilter, setOrganizerInitialFilter] = useState<'going' | 'wishlist'>('going');

  // Unified Discovery search state
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [searchInitialQuery, setSearchInitialQuery] = useState('');

  // Helper to open Organization details
  const openOrgById = useCallback((orgId: string) => {
    setIsCityModalOpen(false);
    setIsOrganizerWorkspaceOpen(false);
    setIsCreateEventModalOpen(false);
    setSelectedOrgId(orgId);
    setIsOrgModalOpen(true);
    telegram.consumeStartParam();
  }, []);

  // Helper to handle Venue click in Discovery
  const handleVenueClick = useCallback((venue: VenueSummary) => {
    if (venue.organization_id) {
      setIsSearchOpen(false);
      openOrgById(venue.organization_id);
    } else {
      // Standalone venue: keep search query focused on this venue or filter events
      setSearchInitialQuery(venue.name);
    }
  }, [openOrgById]);

  // Helper to open Event details
  const openEventById = useCallback(async (eventId: string, source: TrackingSource = 'unknown', broadcastToken?: string | null) => {
    try {
      const details = await api.getEventDetails(eventId);

      // Dismiss conflicting full-screen modals to avoid covering the event
      setIsCityModalOpen(false);
      setIsOrganizerWorkspaceOpen(false);
      setIsOrgModalOpen(false);
      setIsCreateEventModalOpen(false);

      // If user has no city selected, sync selected city to this event's city
      if (details.city_id) {
        setSelectedCityId((currentCity) => {
          if (!currentCity) {
            try {
              localStorage.setItem('evently_selected_city_id', details.city_id);
            } catch {
              // ignore storage errors
            }
            return details.city_id;
          }
          return currentCity;
        });
      }

      setIsCityModalOpen(false);
      setSelectedEventDetails(details);
      setIsDetailsOpen(true);

      // Fire-and-forget background view tracking with attribution support
      api.trackEventView(eventId, source, broadcastToken);
    } catch (err: any) {
      console.error('Failed to open event details:', err);
      alert(err.message || 'Мероприятие не найдено или было удалено');
    }
  }, []);

  // Helper to process deep link parameters (event_<id>, event_<id>_b_<token>, org_<id>, create)
  const processStartParam = useCallback((rawParam: string | null) => {
    if (!rawParam) return;
    const clean = rawParam.trim();
    if (!clean) return;

    if (clean.startsWith('event_')) {
      isDeepLinkActiveRef.current = true;
      setIsCityModalOpen(false);
      telegram.consumeStartParam(clean);
      const paramRest = clean.slice(6).split('?')[0].split('&')[0].split('#')[0].replace(/\/+$/, '').trim();
      let eventId = paramRest;
      let broadcastToken: string | null = null;
      if (paramRest.includes('_b_')) {
        const parts = paramRest.split('_b_');
        eventId = parts[0];
        broadcastToken = parts[1] || null;
      }
      while (eventId.startsWith('event_')) {
        eventId = eventId.slice(6);
      }
      console.log('[Ivently TMA Debug]', {
        version: (window.Telegram?.WebApp as any)?.version,
        platform: (window.Telegram?.WebApp as any)?.platform,
        start_param: rawParam,
        event_id: eventId
      });
      if (eventId) {
        if (broadcastToken) {
          try {
            sessionStorage.setItem(`bcast_token_${eventId}`, broadcastToken);
          } catch {
            // ignore storage errors
          }
          openEventById(eventId, 'broadcast', broadcastToken);
        } else {
          openEventById(eventId, 'deep_link');
        }
      }
    } else if (clean.startsWith('org_')) {
      const orgId = clean.slice(4).split('?')[0].split('&')[0].split('#')[0].replace(/\/+$/, '').trim();
      if (orgId) {
        openOrgById(orgId);
      }
    } else if (clean.startsWith('payment_')) {
      const orderId = clean.slice(8).split('?')[0].split('&')[0].split('#')[0].replace(/\/+$/, '').trim();
      if (orderId) {
        setIsCityModalOpen(false);
        setPaymentReturnOrderId(orderId);
        setCurrentTab('organizer');
        setIsOrganizerWorkspaceOpen(true);
        telegram.consumeStartParam();
      }
    } else if (clean === 'create') {
      setIsCityModalOpen(false);
      setIsCreateEventModalOpen(true);
      telegram.consumeStartParam();
    }

  }, [openEventById, openOrgById]);

  const handleOpenBroadcastComposerFromEvent = useCallback((eventId: string, orgId?: string) => {
    setIsDetailsOpen(false);
    setCurrentTab('organizer');
    setWorkspaceInitialTab('broadcasts');
    setWorkspaceBroadcastEventId(eventId);
    setWorkspaceBroadcastOrgId(orgId || null);
    setWorkspaceOpenProModal(false);
    setIsOrganizerWorkspaceOpen(true);
  }, []);

  // 1. Initial Load: Metadata & Telegram initialization
  useEffect(() => {
    telegram.ready();
    const tgUser = telegram.getUser();
    setUser(tgUser);

    let t1: ReturnType<typeof setTimeout> | undefined;
    let t2: ReturnType<typeof setTimeout> | undefined;

    // Check URL query parameters for payment return (?payment_order_id=...)
    try {
      const searchParams = new URLSearchParams(window.location.search);
      const urlPaymentId = searchParams.get('payment_order_id');
      if (urlPaymentId) {
        setPaymentReturnOrderId(urlPaymentId);
        setCurrentTab('organizer');
        setIsOrganizerWorkspaceOpen(true);
      }
    } catch {
      // ignore URLSearchParams errors
    }

    // Process deep link IMMEDIATELY on mount without waiting for metadata
    const initialParam = telegram.getStartParam();
    if (initialParam) {
      if (initialParam.trim().startsWith('event_')) {
        isDeepLinkActiveRef.current = true;
      }
      processStartParam(initialParam);
    } else {
      // Async retries in case Telegram WebApp SDK finishes initialization after initial render
      t1 = setTimeout(() => {
        const p = telegram.getStartParam();
        if (p) {
          if (p.trim().startsWith('event_')) isDeepLinkActiveRef.current = true;
          processStartParam(p);
        }
      }, 150);
      t2 = setTimeout(() => {
        const p = telegram.getStartParam();
        if (p) {
          if (p.trim().startsWith('event_')) isDeepLinkActiveRef.current = true;
          processStartParam(p);
        }
      }, 500);
    }

    const initMetadata = async () => {
      try {
        const [loadedCities, loadedCategories] = await Promise.all([
          api.getCities().catch(() => api.getCachedCities()),
          api.getCategories().catch(() => []),
          api.getAppMeta().catch(() => null),
        ]);
        if (loadedCities && loadedCities.length > 0) {
          setCities(loadedCities);
        }
        if (loadedCategories && loadedCategories.length > 0) {
          setCategories(loadedCategories);
        }

        // City selection preference:
        // 1. Explicitly saved city in localStorage
        // 2. Returning user's saved default_city_id on backend
        // 3. NO silent fallback to Makhachkala! Prompt CityModal immediately.
        const savedCityId = localStorage.getItem('evently_selected_city_id');
        const effectiveCities = (loadedCities && loadedCities.length > 0) ? loadedCities : DEFAULT_CITIES;
        let confirmedCity = '';

        if (savedCityId && effectiveCities.some((c) => c.id === savedCityId)) {
          confirmedCity = savedCityId;
        }

        // Verify user profile & admin permission via GET /api/v1/users/me
        try {
          const userProfile = await api.getCurrentUser();
          setIsAdmin(Boolean(userProfile?.is_admin));

          // If no city saved in localStorage, restore returning user's saved city
          if (!confirmedCity && userProfile?.default_city_id && effectiveCities.some((c) => c.id === userProfile.default_city_id)) {
            confirmedCity = userProfile.default_city_id;
            try {
              localStorage.setItem('evently_selected_city_id', confirmedCity);
            } catch {
              // Ignore storage write error
            }
          }
        } catch {
          setIsAdmin(false);
        }

        if (confirmedCity) {
          setSelectedCityId(confirmedCity);
          setIsCityModalOpen(false);
        } else {
          const defaultCity = effectiveCities.some((c) => c.id === 'makhachkala') ? 'makhachkala' : (effectiveCities[0]?.id || 'makhachkala');
          setSelectedCityId(defaultCity);
          if (!isDeepLinkActiveRef.current) {
            setIsCityModalOpen(true);
          }
        }
      } catch (err: any) {
        console.error('Failed to initialize app metadata:', err);
      }
    };

    initMetadata();

    return () => {
      if (t1) clearTimeout(t1);
      if (t2) clearTimeout(t2);
    };
  }, [processStartParam]);

  const feedRequestIdRef = useRef<number>(0);
  const feedLoadingStartedAtRef = useRef<number>(0);

  // 2. Fetch Discovery Feed Events
  const loadFeedEvents = useCallback(async () => {
    const currentRequestId = ++feedRequestIdRef.current;
    feedLoadingStartedAtRef.current = Date.now();

    if (!selectedCityId) {
      setEvents([]);
      setIsLoadingEvents(false);
      setFeedError(null);
      return;
    }
    try {
      setIsLoadingEvents(true);
      setFeedError(null);
      const res = await api.getEvents(
        selectedCityId,
        selectedCategoryId,
        dateFilter
      );
      if (currentRequestId === feedRequestIdRef.current) {
        setEvents(res.events);
      }
    } catch (err: any) {
      if (currentRequestId === feedRequestIdRef.current) {
        setFeedError(err.message || 'Ошибка загрузки событий');
      }
    } finally {
      if (currentRequestId === feedRequestIdRef.current) {
        setIsLoadingEvents(false);
      }
    }
  }, [selectedCityId, selectedCategoryId, dateFilter]);

  useEffect(() => {
    loadFeedEvents();
  }, [loadFeedEvents]);

  // 1.1 Listen for URL, hash, visibility, and focus changes while app is running
  useEffect(() => {
    const handleUrlChange = (force = false) => {
      if (force) {
        telegram.resetConsumedStartParam();
      }
      const param = telegram.getStartParam(force);
      if (param) {
        processStartParam(param);
      }

      // Recovery watchdog: If WebApp resumed and feed loading has been stuck for >5s, recover & reload
      if (document.visibilityState === 'visible') {
        const loadingDuration = Date.now() - feedLoadingStartedAtRef.current;
        if (isLoadingEvents && loadingDuration > 5000) {
          console.warn('Recovering from stuck feed loading state after WebApp resume');
          loadFeedEvents();
        }
      }
    };

    const handleExternalActivation = () => handleUrlChange(true);
    const handlePassiveResume = () => handleUrlChange(!isDetailsOpenRef.current);

    window.addEventListener('hashchange', handleExternalActivation);
    window.addEventListener('popstate', handleExternalActivation);
    document.addEventListener('visibilitychange', handlePassiveResume);
    window.addEventListener('focus', handlePassiveResume);
    const unbindActivated = telegram.onActivated(handleExternalActivation);

    return () => {
      window.removeEventListener('hashchange', handleExternalActivation);
      window.removeEventListener('popstate', handleExternalActivation);
      document.removeEventListener('visibilitychange', handlePassiveResume);
      window.removeEventListener('focus', handlePassiveResume);
      unbindActivated();
    };
  }, [processStartParam, isLoadingEvents, loadFeedEvents]);

  const hasLoadedHubRef = useRef(false);

  // 3. Consolidated Personal Hub & Organizer Loader (Single fast HTTP request with SWR)
  const loadPersonalHub = useCallback(async (silent = false) => {
    if (!silent && !hasLoadedHubRef.current) {
      setIsLoadingAttending(true);
      setIsLoadingInterested(true);
      setIsLoadingUserSubscriptions(true);
      setIsLoadingOrganizer(true);
      setIsLoadingMyOrganizations(true);
    }
    try {
      const hub = await api.getMyHub();
      setAttendingEvents(hub.attending || []);
      setInterestedEvents(hub.interested || []);
      setUserSubscriptions(hub.subscriptions || []);
      setOrganizerEvents(hub.created || []);
      setMyOrganizations(hub.organizations || []);
      hasLoadedHubRef.current = true;
    } catch (err) {
      console.error('Failed to load user hub data:', err);
      // SWR fallback: keep existing state intact, never pop blocking alerts on tab switch
    } finally {
      setIsLoadingAttending(false);
      setIsLoadingInterested(false);
      setIsLoadingUserSubscriptions(false);
      setIsLoadingOrganizer(false);
      setIsLoadingMyOrganizations(false);
    }
  }, []);

  const loadPersonalEvents = useCallback(async () => {
    await loadPersonalHub(true);
  }, [loadPersonalHub]);

  const loadOrganizerEvents = useCallback(async () => {
    await loadPersonalHub(true);
  }, [loadPersonalHub]);

  const loadMyOrganizations = useCallback(async () => {
    await loadPersonalHub(true);
  }, [loadPersonalHub]);

  // 5. Fetch Admin Events
  const loadAdminEvents = useCallback(async () => {
    if (!isAdmin) return;
    try {
      setIsLoadingAdmin(true);
      const data = await api.getAdminEvents(adminStatusFilter);
      setAdminEvents(data);
    } catch (err) {
      console.error('Error loading admin events:', err);
    } finally {
      setIsLoadingAdmin(false);
    }
  }, [isAdmin, adminStatusFilter]);

  useEffect(() => {
    if (currentTab === 'my_events' || currentTab === 'organizer') {
      loadPersonalHub(hasLoadedHubRef.current);
    } else if (currentTab === 'admin') {
      loadAdminEvents();
    }
  }, [currentTab, loadPersonalHub, loadAdminEvents]);

  // BackButton support for Organizer Workspace and modals
  useEffect(() => {
    if (isOrganizerWorkspaceOpen) {
      telegram.showBackButton(() => {
        setIsOrganizerWorkspaceOpen(false);
      });
    } else if (isCreateEventModalOpen) {
      telegram.showBackButton(() => {
        setIsCreateEventModalOpen(false);
      });
    } else {
      telegram.hideBackButton();
    }
    return () => {
      if (isOrganizerWorkspaceOpen || isCreateEventModalOpen) {
        telegram.hideBackButton();
      }
    };
  }, [isOrganizerWorkspaceOpen, isCreateEventModalOpen]);

  const handleCardClick = async (event: EventSummary) => {
    openEventById(event.id, 'discovery');
  };

  // 5. Toggle RSVP (Idempotent with optimistic update)
  const handleToggleRsvp = async (eventId: string, currentStatus: boolean) => {
    // 1. Optimistic update of attendingEvents & interestedEvents
    const targetEvent = selectedEventDetails?.id === eventId
      ? selectedEventDetails
      : events.find((e) => e.id === eventId) || attendingEvents.find((e) => e.id === eventId) || interestedEvents.find((e) => e.id === eventId);

    if (currentStatus) {
      // User is canceling RSVP
      setAttendingEvents((prev) => prev.filter((e) => e.id !== eventId));
    } else if (targetEvent) {
      // User is confirming RSVP: add to attending, remove from interested
      const updatedItem: EventSummary = {
        ...targetEvent,
        is_attending: true,
        attendee_count: (targetEvent.attendee_count || 0) + 1,
        current_user_interested: false,
        interest_count: targetEvent.current_user_interested
          ? Math.max(0, (targetEvent.interest_count || 1) - 1)
          : targetEvent.interest_count || 0,
      };
      setAttendingEvents((prev) => [updatedItem, ...prev.filter((e) => e.id !== eventId)]);
      setInterestedEvents((prev) => prev.filter((e) => e.id !== eventId));
    }

    try {
      setIsRsvpLoading(true);
      let res;
      if (currentStatus) {
        res = await api.removeRsvp(eventId);
      } else {
        res = await api.addRsvp(eventId);
        if (!localStorage.getItem('evently_write_access_prompted')) {
          localStorage.setItem('evently_write_access_prompted', 'true');
          telegram.requestWriteAccess().catch(() => {});
        }
      }

      // Update Details modal state
      if (selectedEventDetails && selectedEventDetails.id === eventId) {
        const wasInterested = selectedEventDetails.current_user_interested;
        setSelectedEventDetails({
          ...selectedEventDetails,
          is_attending: res.is_attending,
          attendee_count: res.attendee_count,
          current_user_interested: res.is_attending ? false : wasInterested,
          interest_count: res.is_attending && wasInterested
            ? Math.max(0, selectedEventDetails.interest_count - 1)
            : selectedEventDetails.interest_count,
        });
      }

      // Update Feed list state
      setEvents((prev) =>
        prev.map((e) => {
          if (e.id !== eventId) return e;
          const wasInterested = e.current_user_interested;
          return {
            ...e,
            is_attending: res.is_attending,
            attendee_count: res.attendee_count,
            current_user_interested: res.is_attending ? false : wasInterested,
            interest_count: res.is_attending && wasInterested
              ? Math.max(0, e.interest_count - 1)
              : e.interest_count,
          };
        })
      );

      // Immediate reactive background sync of personal hub
      loadPersonalEvents();
    } catch (err: any) {
      loadPersonalEvents();
      alert(err.message || 'Ошибка обновления статуса участия');
    } finally {
      setIsRsvpLoading(false);
    }
  };

  // 6. Toggle Interest (Idempotent with optimistic update)
  const handleToggleInterest = async (eventId: string, currentStatus: boolean) => {
    const prevDetails = selectedEventDetails;
    const prevEvents = events;
    const prevInterested = interestedEvents;
    const prevAttending = attendingEvents;

    const targetEvent = selectedEventDetails?.id === eventId
      ? selectedEventDetails
      : events.find((e) => e.id === eventId) || attendingEvents.find((e) => e.id === eventId) || interestedEvents.find((e) => e.id === eventId);

    // Optimistic update of Personal Hub tabs
    if (currentStatus) {
      // User is canceling interest
      setInterestedEvents((prev) => prev.filter((e) => e.id !== eventId));
    } else if (targetEvent) {
      // User is confirming interest: add to interested, remove from attending
      const updatedItem: EventSummary = {
        ...targetEvent,
        current_user_interested: true,
        interest_count: (targetEvent.interest_count || 0) + 1,
        is_attending: false,
        attendee_count: targetEvent.is_attending
          ? Math.max(0, (targetEvent.attendee_count || 1) - 1)
          : targetEvent.attendee_count || 0,
      };
      setInterestedEvents((prev) => [updatedItem, ...prev.filter((e) => e.id !== eventId)]);
      setAttendingEvents((prev) => prev.filter((e) => e.id !== eventId));
    }

    try {
      setIsInterestLoading(true);

      // Optimistic update
      if (selectedEventDetails && selectedEventDetails.id === eventId) {
        const nextInterested = !currentStatus;
        const nextInterestCount = nextInterested
          ? selectedEventDetails.interest_count + 1
          : Math.max(0, selectedEventDetails.interest_count - 1);
        const nextAttending = nextInterested ? false : selectedEventDetails.is_attending;
        const nextAttendeeCount = (nextInterested && selectedEventDetails.is_attending)
          ? Math.max(0, selectedEventDetails.attendee_count - 1)
          : selectedEventDetails.attendee_count;

        setSelectedEventDetails({
          ...selectedEventDetails,
          current_user_interested: nextInterested,
          interest_count: nextInterestCount,
          is_attending: nextAttending,
          attendee_count: nextAttendeeCount,
        });
      }

      setEvents((prev) =>
        prev.map((e) => {
          if (e.id !== eventId) return e;
          const nextInterested = !currentStatus;
          const nextInterestCount = nextInterested
            ? e.interest_count + 1
            : Math.max(0, e.interest_count - 1);
          const nextAttending = nextInterested ? false : e.is_attending;
          const nextAttendeeCount = (nextInterested && e.is_attending)
            ? Math.max(0, e.attendee_count - 1)
            : e.attendee_count;
          return {
            ...e,
            current_user_interested: nextInterested,
            interest_count: nextInterestCount,
            is_attending: nextAttending,
            attendee_count: nextAttendeeCount,
          };
        })
      );

      let res: EventInterestResponse;
      if (currentStatus) {
        res = await api.removeInterest(eventId);
      } else {
        res = await api.addInterest(eventId);
        if (!localStorage.getItem('evently_write_access_prompted')) {
          localStorage.setItem('evently_write_access_prompted', 'true');
          telegram.requestWriteAccess().catch(() => {});
        }
      }

      // Sync confirmed state from server
      if (selectedEventDetails && selectedEventDetails.id === eventId) {
        setSelectedEventDetails((prev) =>
          prev && prev.id === eventId
            ? {
                ...prev,
                current_user_interested: res.is_interested,
                interest_count: res.interest_count,
                is_attending: res.is_attending,
                attendee_count: res.attendee_count,
              }
            : prev
        );
      }

      setEvents((prev) =>
        prev.map((e) =>
          e.id === eventId
            ? {
                ...e,
                current_user_interested: res.is_interested,
                interest_count: res.interest_count,
                is_attending: res.is_attending,
                attendee_count: res.attendee_count,
              }
            : e
        )
      );

      // Immediate reactive background sync of personal hub
      loadPersonalEvents();
    } catch (err: any) {
      if (prevDetails) setSelectedEventDetails(prevDetails);
      setEvents(prevEvents);
      setInterestedEvents(prevInterested);
      setAttendingEvents(prevAttending);
      loadPersonalEvents();
      alert(err.message || 'Ошибка обновления статуса интереса');
    } finally {
      setIsInterestLoading(false);
    }
  };

  // Real-device UX: memoized weekend events (Saturday & Sunday) for horizontal highlight carousel
  const weekendEvents = React.useMemo(() => {
    return events.filter((ev) => {
      const d = new Date(ev.start_at);
      const day = d.getDay(); // 0 = Sunday, 6 = Saturday
      return day === 0 || day === 6;
    });
  }, [events]);

  const carouselEvents = React.useMemo(() => {
    if (weekendEvents.length > 0) return weekendEvents.slice(0, 8);
    return events.slice(1, 6);
  }, [weekendEvents, events]);

  const currentCity = cities.find((c) => c.id === selectedCityId) || DEFAULT_CITIES.find(c => c.id === selectedCityId) || DEFAULT_CITIES[0];

  return (
    <div className="min-h-screen bg-[#08080A] text-[#e5e1e4] content-safe-bottom selection:bg-[#10b981]/30 selection:text-[#4edea3] relative overflow-x-hidden">
      {/* Ambient Obsidian Glow Orbs matching Stitch */}
      <div className="fixed top-20 left-1/2 -translate-x-1/2 w-[340px] h-[340px] bg-[#10b981]/6 rounded-full blur-[110px] pointer-events-none -z-10" />
      <div className="fixed top-[480px] right-0 w-[260px] h-[260px] bg-[#f59e0b]/5 rounded-full blur-[90px] pointer-events-none -z-10" />

      {/* Top Header (only when not in Organizer Workspace) */}
      {!isOrganizerWorkspaceOpen && (
        <Header
          currentCity={currentCity}
          onOpenCityModal={() => setIsCityModalOpen(true)}
          user={user}
          isAdmin={isAdmin}
          onOpenUserProfile={() => setIsUserProfileModalOpen(true)}
        />
      )}

      {/* Main Content Area based on Tab */}
      <main className="max-w-[480px] mx-auto">
        {currentTab === 'feed' && (
          <div className="space-y-3 pb-8">
            {/* Prominent Discovery Search Trigger */}
            <div className="px-4 pt-1.5">
              <div
                onClick={() => {
                  telegram.hapticImpact('light');
                  setSearchInitialQuery('');
                  setIsSearchOpen(true);
                }}
                role="button"
                tabIndex={0}
                aria-label="Открыть поиск"
                className="relative flex items-center w-full h-12 bg-[#18181b]/80 backdrop-blur-md rounded-full border border-white/10 shadow-[inset_0_1px_1px_rgba(255,255,255,0.08)] hover:border-white/20 transition-all cursor-pointer group px-4 justify-between"
              >
                <div className="flex items-center min-w-0 flex-1">
                  <Search className="w-4 h-4 text-[#8e9192] mr-2.5 shrink-0 group-hover:text-white transition-colors" />
                  <span className="text-[#8e9192] text-xs font-normal truncate">
                    Поиск событий, мест, организаторов...
                  </span>
                </div>
                <div className="w-8 h-8 rounded-full flex items-center justify-center text-[#8e9192] group-hover:text-white transition-colors shrink-0">
                  <SlidersHorizontal className="w-4 h-4" />
                </div>
              </div>
            </div>

            {/* Filter Bar */}
            <FilterBar
              dateFilter={dateFilter}
              onSelectDate={(df) => setDateFilter(df)}
              categories={categories}
              selectedCategoryId={selectedCategoryId}
              onSelectCategory={(cid) => setSelectedCategoryId(cid)}
            />

            {/* Feed List */}
            <div className="px-4 space-y-4 pt-1">
              {isLoadingEvents ? (
                <div className="py-20 flex flex-col items-center justify-center space-y-3 text-[#c4c7c8]">
                  <Loader2 className="w-7 h-7 animate-spin text-[#10b981]" />
                  <span className="text-xs">Загрузка афиши...</span>
                </div>
              ) : feedError ? (
                <div className="p-4 rounded-2xl bg-red-500/10 border border-red-500/20 text-[#ffb4ab] text-xs flex flex-col items-center space-y-2 text-center">
                  <div className="flex items-center space-x-2">
                    <AlertCircle className="w-4 h-4 shrink-0 text-[#ffb4ab]" />
                    <span>{feedError}</span>
                  </div>
                  <button
                    onClick={() => loadFeedEvents()}
                    className="flex items-center space-x-1.5 px-3 py-1.5 rounded-full bg-white/10 text-white border border-white/15 text-xs font-medium hover:bg-white/20 transition-colors btn-press"
                  >
                    <RefreshCw className="w-3.5 h-3.5" />
                    <span>Повторить попытку</span>
                  </button>
                </div>
              ) : events.length === 0 ? (
                (() => {
                  if (!selectedCityId) {
                    return (
                      <div className="py-14 px-4 text-center rounded-3xl bg-[#1c1b1e] border border-white/8 space-y-3.5 shadow-lg">
                        <div className="w-12 h-12 rounded-full bg-white/5 text-[#4edea3] flex items-center justify-center mx-auto border border-white/10">
                          <MapPin className="w-6 h-6" />
                        </div>
                        <div className="space-y-1">
                          <h3 className="font-bold text-sm text-white">Город не выбран</h3>
                          <p className="text-xs text-[#c4c7c8] max-w-xs mx-auto">
                            Выберите город, чтобы увидеть актуальную афишу мероприятий
                          </p>
                        </div>
                        <button
                          type="button"
                          onClick={() => {
                            telegram.hapticImpact('light');
                            setIsCityModalOpen(true);
                          }}
                          className="px-5 py-2.5 rounded-full bg-white text-[#08080a] text-xs font-semibold shadow-md btn-press transition-all inline-flex items-center space-x-1.5"
                        >
                          <MapPin className="w-3.5 h-3.5" />
                          <span>Выбрать город</span>
                        </button>
                      </div>
                    );
                  }

                  const hasActiveFilters = Boolean(dateFilter !== 'all' || selectedCategoryId);
                  const currentCity = cities.find((c) => c.id === selectedCityId);
                  const cityName = currentCity ? currentCity.name : 'выбранном городе';

                  if (hasActiveFilters) {
                    return (
                      <div className="py-14 px-4 text-center rounded-3xl bg-[#1c1b1e] border border-white/8 space-y-3.5 shadow-lg">
                        <div className="w-12 h-12 rounded-full bg-white/5 text-[#c4c7c8] flex items-center justify-center mx-auto border border-white/10">
                          <Compass className="w-6 h-6" />
                        </div>
                        <div className="space-y-1">
                          <h3 className="font-bold text-sm text-white">Ничего не найдено</h3>
                          <p className="text-xs text-[#c4c7c8] max-w-xs mx-auto">
                            По выбранным фильтрам ничего не найдено.
                          </p>
                        </div>
                        <button
                          type="button"
                          onClick={() => {
                            telegram.hapticImpact('light');
                            setDateFilter('all');
                            setSelectedCategoryId(undefined);
                          }}
                          className="px-4 py-2 rounded-full bg-white/10 text-white border border-white/15 text-xs font-semibold hover:bg-white/15 btn-press transition-all"
                        >
                          Сбросить фильтры
                        </button>
                      </div>
                    );
                  }

                  // Genuine empty city
                  return (
                    <div className="py-14 px-4 text-center rounded-3xl bg-[#1c1b1e] border border-white/8 space-y-4 shadow-lg">
                      <div className="w-12 h-12 rounded-full bg-white/5 text-[#4edea3] flex items-center justify-center mx-auto border border-white/10">
                        <Calendar className="w-6 h-6" />
                      </div>
                      <div className="space-y-1.5 max-w-xs mx-auto">
                        <h3 className="font-bold text-sm text-white">
                          В г. {cityName} пока нет актуальных событий
                        </h3>
                        <p className="text-xs text-[#c4c7c8] leading-relaxed">
                          Станьте первым, кто опубликует событие, или выберите другой город.
                        </p>
                      </div>
                      <div className="flex flex-col sm:flex-row items-center justify-center gap-2 pt-1 max-w-xs mx-auto w-full">
                        <button
                          type="button"
                          onClick={() => {
                            telegram.hapticImpact('medium');
                            setPreselectedOrgForEventCreate(undefined);
                            setIsCreateEventModalOpen(true);
                          }}
                          className="w-full py-2.5 px-4 rounded-full bg-white text-[#08080a] font-semibold text-xs shadow-md transition-all btn-press flex items-center justify-center space-x-1.5"
                        >
                          <Plus className="w-3.5 h-3.5" />
                          <span>Создать событие</span>
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            telegram.hapticImpact('light');
                            setIsCityModalOpen(true);
                          }}
                          className="w-full py-2.5 px-4 rounded-full bg-white/5 hover:bg-white/10 text-[#c4c7c8] hover:text-white border border-white/10 text-xs font-medium transition-all btn-press flex items-center justify-center space-x-1.5"
                        >
                          <MapPin className="w-3.5 h-3.5 text-[#8e9192]" />
                          <span>Выбрать другой город</span>
                        </button>
                      </div>
                    </div>
                  );
                })()
              ) : (
                <div className="space-y-6">
                  {/* 1. Featured Top Hero Event */}
                  {events.length > 0 && (
                    <EventCard
                      key={`hero-${events[0].id}`}
                      event={events[0]}
                      onClick={() => handleCardClick(events[0])}
                      isHero={true}
                      onToggleInterest={(ev) => handleToggleInterest(ev.id, Boolean(ev.current_user_interested))}
                    />
                  )}

                  {/* 2. Главное на выходных (Horizontal Weekend Highlights Carousel) */}
                  {dateFilter === 'all' && carouselEvents.length > 0 && (
                    <section className="space-y-2.5 pt-1">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-1">
                          <h2 className="text-[15px] font-extrabold text-white tracking-tight">
                            Главное на выходных
                          </h2>
                          <span className="text-[#10b981] text-xs">▾</span>
                        </div>
                        <button
                          type="button"
                          onClick={() => {
                            telegram.hapticImpact('light');
                            setDateFilter('weekend');
                          }}
                          className="text-xs font-semibold text-[#8e9192] hover:text-white flex items-center gap-0.5 transition-colors"
                        >
                          <span>Все</span>
                          <ChevronRight className="w-3.5 h-3.5" />
                        </button>
                      </div>

                      {/* Horizontal Swipeable Track with touch-action safety against TMA pull-down dismiss */}
                      <div ref={carouselTrackRef} className="horizontal-carousel flex gap-3 overflow-x-auto pb-2 -mx-4 px-4 scrollbar-none snap-x">
                        {carouselEvents.map((weEvent) => {
                          const weDate = new Date(weEvent.start_at);
                          const weFormatted = weDate.toLocaleDateString('ru-RU', { weekday: 'short', hour: '2-digit', minute: '2-digit' }).toUpperCase();
                          const wePrice = weEvent.is_free
                            ? 'Бесплатно'
                            : weEvent.price_amount
                              ? `${weEvent.price_amount} ₽`
                              : 'Вход свободный';

                          return (
                            <div
                              key={`we-${weEvent.id}`}
                              onClick={() => handleCardClick(weEvent)}
                              className="snap-start shrink-0 w-[210px] h-[220px] rounded-2xl overflow-hidden relative border border-white/10 bg-[#1c1b1e] cursor-pointer group shadow-[0_8px_20px_rgba(0,0,0,0.5)] flex flex-col justify-between p-3 active:scale-[0.98] transition-all"
                            >
                              <div className="absolute inset-0 z-0">
                                <SafeImage
                                  src={weEvent.cover_image_url}
                                  alt={weEvent.title}
                                  loading="eager"
                                  className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                                />
                                <div className="absolute inset-0 bg-gradient-to-t from-[#08080a] via-[#08080a]/50 to-black/35 pointer-events-none" />
                              </div>

                              <div className="relative z-10 flex items-center justify-between">
                                <span className="px-2 py-0.5 rounded-full bg-black/60 backdrop-blur-md text-white font-bold text-[10px] border border-white/10">
                                  {weFormatted}
                                </span>
                                <button
                                  type="button"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    telegram.hapticImpact('light');
                                    handleToggleInterest(weEvent.id, Boolean(weEvent.current_user_interested));
                                  }}
                                  aria-label={weEvent.current_user_interested ? 'Удалить из закладок' : 'В закладки'}
                                  className="w-7 h-7 rounded-full bg-black/60 backdrop-blur-md border border-white/10 flex items-center justify-center text-white/90 active:scale-90 transition-transform btn-press"
                                >
                                  <Bookmark className={`w-3.5 h-3.5 ${weEvent.current_user_interested ? 'fill-white text-white' : 'text-white'}`} />
                                </button>
                              </div>

                              <div className="relative z-10 flex flex-col gap-1">
                                <h3 className="font-bold text-[13px] text-white line-clamp-2 leading-tight">
                                  {weEvent.title}
                                </h3>
                                <span className="text-[10px] text-[#c4c7c8] truncate">
                                  {weEvent.venue_name}
                                </span>
                                <div className="flex items-center justify-between pt-1">
                                  <span className={`text-xs font-bold ${weEvent.is_free ? 'text-[#4edea3]' : 'text-white'}`}>
                                    {wePrice}
                                  </span>
                                  {weEvent.category_name && (
                                    <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-white/10 text-white font-medium backdrop-blur-sm border border-white/10">
                                      {weEvent.category_name}
                                    </span>
                                  )}
                                </div>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </section>
                  )}

                  {/* 3. Все события (Vertical Cards) */}
                  <section className="space-y-3 pt-1">
                    <div className="flex items-center justify-between">
                      <h2 className="text-[15px] font-extrabold text-white tracking-tight">
                        Все события
                      </h2>
                      <span className="text-xs font-medium text-[#8e9192]">
                        По дате ▾
                      </span>
                    </div>

                    <div className="space-y-4">
                      {events.slice(1).map((event) => (
                        <EventCard
                          key={event.id}
                          event={event}
                          onClick={() => handleCardClick(event)}
                          isHero={false}
                          onToggleInterest={(ev) => handleToggleInterest(ev.id, Boolean(ev.current_user_interested))}
                        />
                      ))}
                    </div>
                  </section>
                </div>
              )}
            </div>
          </div>
        )}

        {(currentTab === 'my_events' || currentTab === 'organizer') && (
          isOrganizerWorkspaceOpen ? (
            <OrganizerWorkspace
              isAdmin={isAdmin}
              paymentReturnOrderId={paymentReturnOrderId}
              initialTab={workspaceInitialTab}
              initialBroadcastEventId={workspaceBroadcastEventId}
              initialBroadcastOrgId={workspaceBroadcastOrgId}
              initialOpenProModal={workspaceOpenProModal}
              onBack={() => {
                setPaymentReturnOrderId(null);
                setWorkspaceBroadcastEventId(null);
                setWorkspaceBroadcastOrgId(null);
                setWorkspaceOpenProModal(false);
                setIsOrganizerWorkspaceOpen(false);
              }}
              organizations={myOrganizations}
              events={organizerEvents}
              isLoading={isLoadingOrganizer || isLoadingMyOrganizations}
              onOpenCreateEvent={(orgId, draft) => {
                setPreselectedOrgForEventCreate(orgId);
                setEditingDraftData(draft || null);
                setEditingEventData(null);
                setIsCreateEventModalOpen(true);
              }}
              onOpenCreateOrg={() => {
                setEditingOrgData(null);
                setIsCreateOrgModalOpen(true);
              }}
              onEditOrg={(org) => {
                setEditingOrgData(org as any);
                setIsCreateOrgModalOpen(true);
              }}
              onOrgClick={(org) => openOrgById(org.id)}
              onEventClick={(ev) => openEventById(ev.id, 'organizer')}
              onOrgDeleted={() => {
                loadPersonalHub(true);
                loadFeedEvents();
              }}
            />
          ) : (
            <OrganizerTab
              attendingEvents={attendingEvents}
              isLoadingAttending={isLoadingAttending}
              interestedEvents={interestedEvents}
              isLoadingInterested={isLoadingInterested}
              subscriptions={userSubscriptions}
              isLoadingSubscriptions={isLoadingUserSubscriptions}
              organizations={myOrganizations}
              myCreatedEvents={organizerEvents}
              onOpenOrganizerWorkspace={() => setIsOrganizerWorkspaceOpen(true)}
              onOpenBroadcastComposer={handleOpenBroadcastComposerFromEvent}
              onOpenCreateEvent={() => {
                setPreselectedOrgForEventCreate(undefined);
                setIsCreateEventModalOpen(true);
              }}
              onOpenCreateOrg={() => {
                setEditingOrgData(null);
                setIsCreateOrgModalOpen(true);
              }}
              onEventClick={(ev) => openEventById(ev.id, 'personal')}
              onOrgClick={(orgId) => openOrgById(orgId)}
              onExplore={() => {
                setCurrentTab('feed');
              }}
              onOpenTicket={(ev) => {
                setTicketEvent(ev);
                setIsTicketModalOpen(true);
              }}
              initialFilter={organizerInitialFilter}
            />
          )
        )}


        {currentTab === 'admin' && (
          <AdminTab
            events={adminEvents}
            isLoading={isLoadingAdmin}
            activeStatus={adminStatusFilter}
            onStatusChange={(st) => setAdminStatusFilter(st)}
            onRefresh={loadAdminEvents}
            onEventClick={(ev) => openEventById(ev.id, 'organizer')}
          />
        )}
      </main>

      {/* City Selector Modal */}
      <CityModal
        isOpen={isCityModalOpen}
        onClose={() => setIsCityModalOpen(false)}
        cities={cities}
        selectedCityId={selectedCityId}
        onSelectCity={(cid) => {
          setSelectedCityId(cid);
          try {
            localStorage.setItem('evently_selected_city_id', cid);
          } catch (e) {
            console.warn('Failed to save selected city:', e);
          }
          api.setDefaultCity(cid).catch(() => {});
        }}
      />

      {/* Event Details Sheet */}
      <EventDetailsModal
        isOpen={isDetailsOpen}
        event={selectedEventDetails}
        onClose={() => {
          setIsDetailsOpen(false);
          telegram.resetConsumedStartParam();
          isDeepLinkActiveRef.current = false;
        }}
        onToggleRsvp={handleToggleRsvp}
        isRsvpLoading={isRsvpLoading}
        onToggleInterest={handleToggleInterest}
        isInterestLoading={isInterestLoading}
        isOrganizer={Boolean(selectedEventDetails?.is_organizer || organizerEvents.some((oe) => oe.id === selectedEventDetails?.id))}
        onEditEvent={(ev) => {
          setIsDetailsOpen(false);
          setEditingEventData(ev);
          setIsCreateEventModalOpen(true);
        }}
        onOpenOrgModal={(orgId) => {
          setIsDetailsOpen(false);
          openOrgById(orgId);
        }}
        onOpenCompanyModal={(ev) => {
          setCompanyEvent(ev);
          setIsCompanyModalOpen(true);
        }}
        onOpenBroadcastComposer={handleOpenBroadcastComposerFromEvent}
        onOpenTicket={(ev) => {
          setTicketEvent(ev);
          setIsTicketModalOpen(true);
        }}
      />

      {/* Event Company Discovery Modal */}
      <EventCompanyModal
        event={companyEvent}
        isOpen={isCompanyModalOpen}
        onClose={() => setIsCompanyModalOpen(false)}
        onRequireParticipation={() => {
          setIsCompanyModalOpen(false);
        }}
      />

      {/* Organization Details Modal */}
      <OrganizationModal
        isOpen={isOrgModalOpen}
        orgIdOrSlug={selectedOrgId}
        onClose={() => {
          setIsOrgModalOpen(false);
          setSelectedOrgId(null);
        }}
        onEventClick={(ev) => openEventById(ev.id)}
        onOpenCreateEvent={(orgId) => {
          setIsOrgModalOpen(false);
          setPreselectedOrgForEventCreate(orgId);
          setIsCreateEventModalOpen(true);
        }}
        onEditOrg={(org) => {
          setIsOrgModalOpen(false);
          setEditingOrgData(org);
          setIsCreateOrgModalOpen(true);
        }}
        onSubscriptionChanged={() => {
          loadMyOrganizations();
          loadPersonalEvents();
        }}
      />

      {/* Create / Edit Event Modal */}
      <CreateEventModal
        isOpen={isCreateEventModalOpen}
        onClose={() => {
          setPreselectedOrgForEventCreate(undefined);
          setEditingEventData(null);
          setEditingDraftData(null);
          setIsCreateEventModalOpen(false);
        }}
        cities={cities}
        categories={categories}
        defaultCityId={selectedCityId}
        myOrganizations={myOrganizations}
        initialOrganizationId={preselectedOrgForEventCreate}
        initialEvent={editingEventData}
        initialDraft={editingDraftData}
        onSaveDraft={(draft) => {
          try {
            const saved = localStorage.getItem('ivently_event_drafts');
            const existing: any[] = saved ? JSON.parse(saved) : [];
            const updated = [draft, ...existing.filter((d: any) => d.id !== draft.id)];
            localStorage.setItem('ivently_event_drafts', JSON.stringify(updated));
          } catch (e) {
            console.warn('Draft save error', e);
          }
        }}
        onEventUpdated={(updatedEvent) => {
          setEditingEventData(null);
          setEditingDraftData(null);
          setIsCreateEventModalOpen(false);
          setSelectedEventDetails(updatedEvent);
          loadFeedEvents();
          loadOrganizerEvents();
          loadPersonalEvents();
        }}
        onEventCreated={() => {
          setPreselectedOrgForEventCreate(undefined);
          setEditingEventData(null);
          setEditingDraftData(null);
          setIsCreateEventModalOpen(false);
          loadFeedEvents();
          loadOrganizerEvents();
          loadMyOrganizations();
          loadPersonalEvents();
        }}
        onEventDeleted={(deletedId) => {
          setEditingEventData(null);
          setIsCreateEventModalOpen(false);
          setOrganizerEvents((prev) => prev.filter((e) => e.id !== deletedId));
          setEvents((prev) => prev.filter((e) => e.id !== deletedId));
          setAttendingEvents((prev) => prev.filter((e) => e.id !== deletedId));
          setInterestedEvents((prev) => prev.filter((e) => e.id !== deletedId));
          loadOrganizerEvents();
          loadFeedEvents();
          loadPersonalEvents();
        }}
      />

      {/* Create / Edit Organization Modal */}
      <CreateOrganizationModal
        isOpen={isCreateOrgModalOpen}
        onClose={() => {
          setIsCreateOrgModalOpen(false);
          setEditingOrgData(null);
        }}
        cities={cities}
        defaultCityId={selectedCityId}
        initialData={editingOrgData}
        onSaved={(savedOrg) => {
          loadMyOrganizations();
          loadPersonalEvents();
          openOrgById(savedOrg.id);
        }}
        onDeleted={() => {
          loadMyOrganizations();
          loadOrganizerEvents();
          loadPersonalEvents();
          loadFeedEvents();
        }}
      />


      {/* My Subscriptions Modal */}
      <MySubscriptionsModal
        isOpen={isSubscriptionsModalOpen}
        onClose={() => setIsSubscriptionsModalOpen(false)}
        onSelectOrg={(orgId) => openOrgById(orgId)}
      />

      {/* Unified Discovery Search Modal */}
      <DiscoveryModal
        isOpen={isSearchOpen}
        onClose={() => setIsSearchOpen(false)}
        currentCity={currentCity}
        onOpenCityModal={() => setIsCityModalOpen(true)}
        onEventClick={(ev) => {
          setIsSearchOpen(false);
          openEventById(ev.id, 'discovery');
        }}
        onOrgClick={(orgId) => {
          setIsSearchOpen(false);
          openOrgById(orgId);
        }}
        onVenueClick={handleVenueClick}
        initialQuery={searchInitialQuery}
      />

      {/* User Profile Modal */}
      <UserProfileModal
        isOpen={isUserProfileModalOpen}
        onClose={() => setIsUserProfileModalOpen(false)}
        user={user}
        currentCity={currentCity}
        onOpenCityModal={() => {
          setIsUserProfileModalOpen(false);
          setIsCityModalOpen(true);
        }}
        attendingCount={attendingEvents.length}
        interestedCount={interestedEvents.length}
        subscriptionsCount={userSubscriptions.length}
        onNavigateToAttending={() => {
          setIsUserProfileModalOpen(false);
          setOrganizerInitialFilter('going');
          setCurrentTab('organizer');
        }}
        onNavigateToInterested={() => {
          setIsUserProfileModalOpen(false);
          setOrganizerInitialFilter('wishlist');
          setCurrentTab('organizer');
        }}
        onOpenSubscriptions={() => {
          setIsUserProfileModalOpen(false);
          setIsSubscriptionsModalOpen(true);
        }}
        onOpenOrganizerWorkspace={() => {
          setIsUserProfileModalOpen(false);
          setCurrentTab('organizer');
          setIsOrganizerWorkspaceOpen(true);
        }}
        isAdmin={isAdmin}
        onOpenAdminPanel={() => {
          if (isAdmin) {
            setIsUserProfileModalOpen(false);
            setCurrentTab('admin');
          }
        }}
      />

      {/* Electronic Ticket Modal */}
      <TicketModal
        isOpen={isTicketModalOpen}
        onClose={() => {
          setIsTicketModalOpen(false);
          setTicketEvent(null);
        }}
        event={ticketEvent}
      />

      {/* Bottom Navigation — only render when no full-screen sheet or workspace is active */}
      {!isCreateEventModalOpen && !isCreateOrgModalOpen && !isDetailsOpen && !isTicketModalOpen && !isOrganizerWorkspaceOpen && (
        <Navigation
          currentTab={currentTab}
          onChangeTab={(tab) => setCurrentTab(tab)}
          isAdmin={isAdmin}
        />
      )}
    </div>
  );
};

export default App;
