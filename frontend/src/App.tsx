import React, { useState, useEffect, useCallback } from 'react';
import type { 
  City, 
  Category, 
  EventSummary, 
  EventResponse, 
  DateFilterType, 
  EventStatus,
  TelegramWebAppUser 
} from './types';
import { api } from './services/api';
import { telegram } from './services/telegram';
import { Header } from './components/Header';
import { CityModal } from './components/CityModal';
import { FilterBar } from './components/FilterBar';
import { EventCard } from './components/EventCard';
import { EventDetailsModal } from './components/EventDetailsModal';
import { CreateEventModal } from './components/CreateEventModal';
import { OrganizerTab } from './components/OrganizerTab';
import { AdminTab } from './components/AdminTab';
import { Navigation } from './components/Navigation';
import type { TabType } from './components/Navigation';
import { Loader2, Ticket, AlertCircle } from 'lucide-react';

export const App: React.FC = () => {
  // Navigation & UI state
  const [currentTab, setCurrentTab] = useState<TabType>('feed');
  const [isCityModalOpen, setIsCityModalOpen] = useState(false);

  // Core metadata
  const [cities, setCities] = useState<City[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [selectedCityId, setSelectedCityId] = useState<string>('warsaw');
  const [selectedCategoryId, setSelectedCategoryId] = useState<string | undefined>(undefined);
  const [dateFilter, setDateFilter] = useState<DateFilterType>('all');

  // Discovery Feed state
  const [events, setEvents] = useState<EventSummary[]>([]);
  const [isLoadingEvents, setIsLoadingEvents] = useState(true);
  const [feedError, setFeedError] = useState<string | null>(null);

  // Active Event Details modal
  const [selectedEventDetails, setSelectedEventDetails] = useState<EventResponse | null>(null);
  const [isDetailsOpen, setIsDetailsOpen] = useState(false);
  const [isRsvpLoading, setIsRsvpLoading] = useState(false);

  // Organizer tab state
  const [organizerEvents, setOrganizerEvents] = useState<EventSummary[]>([]);
  const [isLoadingOrganizer, setIsLoadingOrganizer] = useState(false);

  // Admin tab state
  const [isAdmin, setIsAdmin] = useState(false);
  const [adminStatusFilter, setAdminStatusFilter] = useState<EventStatus>('pending');
  const [adminEvents, setAdminEvents] = useState<EventSummary[]>([]);
  const [isLoadingAdmin, setIsLoadingAdmin] = useState(false);

  // Telegram User
  const [user, setUser] = useState<TelegramWebAppUser | null>(null);

  // 1. Initial Load: Metadata & Telegram initialization
  useEffect(() => {
    telegram.ready();
    const tgUser = telegram.getUser();
    setUser(tgUser);

    const initMetadata = async () => {
      try {
        const [loadedCities, loadedCategories] = await Promise.all([
          api.getCities(),
          api.getCategories(),
        ]);
        setCities(loadedCities);
        setCategories(loadedCategories);
        if (loadedCities.length > 0) {
          setSelectedCityId(loadedCities[0].id);
        }

        // Check if user is admin
        try {
          const adminQueue = await api.getAdminEvents('pending');
          // If 200 OK without error, user is admin
          setIsAdmin(true);
          setAdminEvents(adminQueue);
        } catch {
          setIsAdmin(false);
        }

        // Handle Deep Linking via start_param (e.g., event_waw_01 or create)
        const startParam = telegram.getStartParam();
        if (startParam) {
          if (startParam.startsWith('event_')) {
            const eventId = startParam.replace('event_', '');
            openEventById(eventId);
          } else if (startParam === 'create') {
            setCurrentTab('create');
          }
        }
      } catch (err: any) {
        console.error('Failed to initialize app metadata:', err);
      }
    };

    initMetadata();
  }, []);

  // 2. Fetch Discovery Feed Events
  const loadFeedEvents = useCallback(async () => {
    try {
      setIsLoadingEvents(true);
      setFeedError(null);
      const res = await api.getEvents(selectedCityId, selectedCategoryId, dateFilter);
      setEvents(res.events);
    } catch (err: any) {
      setFeedError(err.message || 'Ошибка загрузки событий');
    } finally {
      setIsLoadingEvents(false);
    }
  }, [selectedCityId, selectedCategoryId, dateFilter]);

  useEffect(() => {
    loadFeedEvents();
  }, [loadFeedEvents]);

  // 3. Fetch Organizer Events
  const loadOrganizerEvents = useCallback(async () => {
    try {
      setIsLoadingOrganizer(true);
      const data = await api.getOrganizerEvents();
      setOrganizerEvents(data);
    } catch (err) {
      console.error('Error loading organizer events:', err);
    } finally {
      setIsLoadingOrganizer(false);
    }
  }, []);

  // 4. Fetch Admin Events
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
    if (currentTab === 'organizer') {
      loadOrganizerEvents();
    } else if (currentTab === 'admin') {
      loadAdminEvents();
    }
  }, [currentTab, loadOrganizerEvents, loadAdminEvents]);

  // Open Event Details
  const openEventById = async (eventId: string) => {
    try {
      setIsRsvpLoading(true);
      const details = await api.getEventDetails(eventId);
      setSelectedEventDetails(details);
      setIsDetailsOpen(true);
    } catch (err) {
      console.error('Failed to open event details:', err);
    } finally {
      setIsRsvpLoading(false);
    }
  };

  const handleCardClick = async (event: EventSummary) => {
    openEventById(event.id);
  };

  // 5. Toggle RSVP (Idempotent with optimistic update)
  const handleToggleRsvp = async (eventId: string, currentStatus: boolean) => {
    try {
      setIsRsvpLoading(true);
      let res;
      if (currentStatus) {
        // DELETE RSVP
        res = await api.removeRsvp(eventId);
      } else {
        // POST RSVP
        res = await api.addRsvp(eventId);
      }

      // Update Details modal state
      if (selectedEventDetails && selectedEventDetails.id === eventId) {
        setSelectedEventDetails({
          ...selectedEventDetails,
          is_attending: res.is_attending,
          attendee_count: res.attendee_count,
        });
      }

      // Update Feed list state
      setEvents((prev) =>
        prev.map((e) =>
          e.id === eventId
            ? { ...e, is_attending: res.is_attending, attendee_count: res.attendee_count }
            : e
        )
      );
    } catch (err: any) {
      alert(err.message || 'Ошибка обновления статуса участия');
    } finally {
      setIsRsvpLoading(false);
    }
  };

  const currentCity = cities.find((c) => c.id === selectedCityId);

  return (
    <div className="min-h-screen bg-[#0B0D13] text-[#F3F4F6] content-safe-bottom selection:bg-indigo-500">
      {/* Top Header */}
      <Header
        currentCity={currentCity}
        onOpenCityModal={() => setIsCityModalOpen(true)}
        user={user}
        isAdmin={isAdmin}
      />

      {/* Main Content Area based on Tab */}
      <main className="max-w-lg mx-auto">
        {currentTab === 'feed' && (
          <div className="space-y-3">
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
                <div className="py-20 flex flex-col items-center justify-center space-y-3 text-gray-400">
                  <Loader2 className="w-7 h-7 animate-spin text-indigo-500" />
                  <span className="text-xs">Загрузка афиши...</span>
                </div>
              ) : feedError ? (
                <div className="p-4 rounded-2xl bg-red-500/10 border border-red-500/20 text-red-300 text-xs flex items-center space-x-2">
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  <span>{feedError}</span>
                </div>
              ) : events.length === 0 ? (
                <div className="py-16 px-4 text-center rounded-2xl bg-[#141724] border border-white/5 space-y-3">
                  <div className="w-12 h-12 rounded-full bg-white/5 flex items-center justify-center mx-auto text-indigo-400">
                    <Ticket className="w-6 h-6" />
                  </div>
                  <div className="space-y-1">
                    <h3 className="font-bold text-sm text-white">Событий не найдено</h3>
                    <p className="text-xs text-gray-400 max-w-xs mx-auto">
                      Попробуйте выбрать другой день или переключить категорию
                    </p>
                  </div>
                  {(dateFilter !== 'all' || selectedCategoryId) && (
                    <button
                      onClick={() => {
                        setDateFilter('all');
                        setSelectedCategoryId(undefined);
                      }}
                      className="px-4 py-2 rounded-xl bg-indigo-600/30 text-indigo-300 text-xs font-semibold hover:bg-indigo-600/40"
                    >
                      Сбросить фильтры
                    </button>
                  )}
                </div>
              ) : (
                <div className="space-y-4">
                  {events.map((event) => (
                    <EventCard
                      key={event.id}
                      event={event}
                      onClick={() => handleCardClick(event)}
                    />
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {currentTab === 'create' && (
          <div className="p-4">
            <CreateEventModal
              isOpen={true}
              onClose={() => setCurrentTab('feed')}
              cities={cities}
              categories={categories}
              defaultCityId={selectedCityId}
              onEventCreated={() => {
                loadFeedEvents();
                setCurrentTab('organizer');
              }}
            />
          </div>
        )}

        {currentTab === 'organizer' && (
          <OrganizerTab
            events={organizerEvents}
            isLoading={isLoadingOrganizer}
            onOpenCreateModal={() => {
              setCurrentTab('create');
            }}
            onEventClick={(ev) => openEventById(ev.id)}
          />
        )}

        {currentTab === 'admin' && (
          <AdminTab
            events={adminEvents}
            isLoading={isLoadingAdmin}
            activeStatus={adminStatusFilter}
            onStatusChange={(st) => setAdminStatusFilter(st)}
            onRefresh={loadAdminEvents}
            onEventClick={(ev) => openEventById(ev.id)}
          />
        )}
      </main>

      {/* City Selector Modal */}
      <CityModal
        isOpen={isCityModalOpen}
        onClose={() => setIsCityModalOpen(false)}
        cities={cities}
        selectedCityId={selectedCityId}
        onSelectCity={(cid) => setSelectedCityId(cid)}
      />

      {/* Event Details Sheet */}
      <EventDetailsModal
        isOpen={isDetailsOpen}
        event={selectedEventDetails}
        onClose={() => setIsDetailsOpen(false)}
        onToggleRsvp={handleToggleRsvp}
        isRsvpLoading={isRsvpLoading}
      />

      {/* Bottom Navigation */}
      <Navigation
        currentTab={currentTab}
        onChangeTab={(tab) => setCurrentTab(tab)}
        isAdmin={isAdmin}
      />
    </div>
  );
};

export default App;
