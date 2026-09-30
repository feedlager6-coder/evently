import React, { useState, useEffect, useRef, useCallback } from 'react';
import type { 
  City, 
  EventSummary, 
  VenueSummary, 
  UnifiedDiscoveryResponse 
} from '../types';
import { api } from '../services/api';
import { telegram } from '../services/telegram';
import { SafeImage } from './SafeImage';
import { SafeAvatar } from './SafeAvatar';
import { 
  Search, 
  X, 
  ArrowLeft, 
  MapPin, 
  Calendar, 
  Users, 
  ShieldCheck, 
  Compass, 
  Loader2, 
  AlertCircle, 
  ChevronRight,
  Sparkles
} from 'lucide-react';

interface DiscoveryModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentCity?: City;
  onOpenCityModal: () => void;
  onEventClick: (event: EventSummary) => void;
  onOrgClick: (orgId: string) => void;
  onVenueClick: (venue: VenueSummary) => void;
  initialQuery?: string;
}

type DiscoveryTab = 'all' | 'events' | 'organizations' | 'venues';

const QUICK_SUGGESTIONS = [
  'Концерты',
  'Спорт',
  'Кафе и бары',
  'Вечеринки',
  'Выставки',
  'Стендап',
  'Театр',
];

export const DiscoveryModal: React.FC<DiscoveryModalProps> = ({
  isOpen,
  onClose,
  currentCity,
  onOpenCityModal,
  onEventClick,
  onOrgClick,
  onVenueClick,
  initialQuery = ''
}) => {
  const [query, setQuery] = useState(initialQuery);
  const [activeTab, setActiveTab] = useState<DiscoveryTab>('all');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<UnifiedDiscoveryResponse | null>(null);

  const inputRef = useRef<HTMLInputElement>(null);
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Sync initial query if changed
  useEffect(() => {
    if (initialQuery && initialQuery !== query) {
      setQuery(initialQuery);
    }
  }, [initialQuery]);

  // Handle Telegram BackButton and search autofocus
  useEffect(() => {
    if (isOpen) {
      telegram.showBackButton(onClose);

      const triggerFocus = () => {
        if (inputRef.current) {
          inputRef.current.focus({ preventScroll: true });
        }
      };

      triggerFocus();
      const raf = requestAnimationFrame(triggerFocus);
      const timer50 = setTimeout(triggerFocus, 50);
      const timer150 = setTimeout(triggerFocus, 150);

      return () => {
        cancelAnimationFrame(raf);
        clearTimeout(timer50);
        clearTimeout(timer150);
        telegram.hideBackButton();
      };
    }
  }, [isOpen, onClose]);

  // Re-run search if city changes while modal is open and has an active query
  useEffect(() => {
    if (isOpen && query.trim()) {
      executeSearch(query, currentCity?.id);
    }
  }, [currentCity?.id]);

  // Perform search with debounce
  const executeSearch = useCallback(async (searchQuery: string, cityId?: string) => {
    const cleanQ = searchQuery.trim();
    if (!cleanQ) {
      setResults(null);
      setIsLoading(false);
      setError(null);
      return;
    }

    try {
      setIsLoading(true);
      setError(null);
      const data = await api.searchDiscovery(cleanQ, cityId, undefined, 20);
      setResults(data);
    } catch (err: any) {
      console.error('Discovery search error:', err);
      setError(err.message || 'Ошибка выполнения поиска');
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Debounced input change handler
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const nextQ = e.target.value;
    setQuery(nextQ);

    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    if (!nextQ.trim()) {
      setResults(null);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    debounceTimerRef.current = setTimeout(() => {
      executeSearch(nextQ, currentCity?.id);
    }, 250);
  };

  const handleClear = () => {
    telegram.hapticImpact('light');
    setQuery('');
    setResults(null);
    setError(null);
    inputRef.current?.focus();
  };

  const handleSuggestionClick = (suggestion: string) => {
    telegram.hapticImpact('light');
    setQuery(suggestion);
    executeSearch(suggestion, currentCity?.id);
  };

  const handleTabChange = (tab: DiscoveryTab) => {
    if (tab !== activeTab) {
      telegram.hapticImpact('light');
      setActiveTab(tab);
    }
  };

  if (!isOpen) return null;

  const totalEvents = results?.events.length || 0;
  const totalOrgs = results?.organizations.length || 0;
  const totalVenues = results?.venues.length || 0;
  const totalAll = totalEvents + totalOrgs + totalVenues;

  const showEvents = (activeTab === 'all' || activeTab === 'events') && totalEvents > 0;
  const showOrgs = (activeTab === 'all' || activeTab === 'organizations') && totalOrgs > 0;
  const showVenues = (activeTab === 'all' || activeTab === 'venues') && totalVenues > 0;

  const hasNoResults = !isLoading && query.trim().length > 0 && totalAll === 0 && !error;

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-[#0B0D13] backdrop-fade-in text-[#F3F4F6] overflow-hidden">
      {/* Top Search Header */}
      <div className="sticky top-0 z-20 bg-[#0B0D13]/95 backdrop-blur-md border-b border-white/8 px-4 py-3 space-y-2.5">
        <div className="flex items-center space-x-2.5 max-w-lg mx-auto">
          {/* Back Button */}
          <button
            onClick={() => {
              telegram.hapticImpact('light');
              onClose();
            }}
            className="p-2 -ml-1 rounded-xl text-gray-400 hover:text-white hover:bg-white/5 btn-press transition-colors shrink-0"
            aria-label="Назад"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>

          {/* Search Input Bar */}
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-indigo-400 absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
            <input
              ref={inputRef}
              type="search"
              inputMode="search"
              autoFocus
              value={query}
              onChange={handleInputChange}
              placeholder="События, места и организации"
              className="w-full pl-10 pr-9 py-2.5 rounded-2xl bg-[#161A28] border border-indigo-500/30 text-white placeholder-gray-400 text-sm focus:outline-none focus:border-indigo-500 transition-all shadow-inner"
            />
            {query && (
              <button
                onClick={handleClear}
                className="absolute right-3 top-1/2 -translate-y-1/2 p-1 text-gray-400 hover:text-white rounded-full bg-white/5"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>

          {/* City Context Pill */}
          <button
            onClick={() => {
              telegram.hapticImpact('light');
              onOpenCityModal();
            }}
            className="flex items-center space-x-1 px-3 py-2 rounded-xl bg-[#161A28] border border-white/8 hover:border-indigo-500/40 text-xs font-semibold text-gray-300 hover:text-white btn-press transition-all shrink-0"
            title="Сменить город"
          >
            <MapPin className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
            <span className="max-w-[70px] truncate">{currentCity?.name || 'Город'}</span>
          </button>
        </div>

        {/* Filter Segment Tabs */}
        {results && totalAll > 0 && (
          <div className="flex items-center space-x-1.5 overflow-x-auto no-scrollbar pt-1 max-w-lg mx-auto">
            <button
              onClick={() => handleTabChange('all')}
              className={`px-3 py-1 rounded-full text-xs font-semibold whitespace-nowrap btn-press transition-all ${
                activeTab === 'all'
                  ? 'bg-indigo-600 text-white shadow-sm shadow-indigo-600/30'
                  : 'bg-[#161A28] text-gray-400 hover:text-gray-200 border border-white/5'
              }`}
            >
              Все ({totalAll})
            </button>
            <button
              onClick={() => handleTabChange('events')}
              className={`px-3 py-1 rounded-full text-xs font-semibold whitespace-nowrap btn-press transition-all ${
                activeTab === 'events'
                  ? 'bg-indigo-600 text-white shadow-sm shadow-indigo-600/30'
                  : 'bg-[#161A28] text-gray-400 hover:text-gray-200 border border-white/5'
              }`}
            >
              События ({totalEvents})
            </button>
            <button
              onClick={() => handleTabChange('organizations')}
              className={`px-3 py-1 rounded-full text-xs font-semibold whitespace-nowrap btn-press transition-all ${
                activeTab === 'organizations'
                  ? 'bg-indigo-600 text-white shadow-sm shadow-indigo-600/30'
                  : 'bg-[#161A28] text-gray-400 hover:text-gray-200 border border-white/5'
              }`}
            >
              Организации ({totalOrgs})
            </button>
            <button
              onClick={() => handleTabChange('venues')}
              className={`px-3 py-1 rounded-full text-xs font-semibold whitespace-nowrap btn-press transition-all ${
                activeTab === 'venues'
                  ? 'bg-indigo-600 text-white shadow-sm shadow-indigo-600/30'
                  : 'bg-[#161A28] text-gray-400 hover:text-gray-200 border border-white/5'
              }`}
            >
              Места ({totalVenues})
            </button>
          </div>
        )}
      </div>

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto custom-scrollbar px-4 py-3 max-w-lg mx-auto w-full space-y-6">
        {/* 1. Loading Skeleton */}
        {isLoading && (
          <div className="space-y-4 pt-2">
            <div className="flex items-center space-x-2 text-indigo-400 text-xs font-medium">
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>Ищем события, места и организации...</span>
            </div>
            {[1, 2, 3].map((i) => (
              <div key={i} className="p-3.5 rounded-2xl bg-[#131722] border border-white/5 animate-pulse flex space-x-3">
                <div className="w-16 h-16 rounded-xl bg-white/5 shrink-0" />
                <div className="flex-1 space-y-2 py-1">
                  <div className="h-4 bg-white/5 rounded w-3/4" />
                  <div className="h-3 bg-white/5 rounded w-1/2" />
                </div>
              </div>
            ))}
          </div>
        )}

        {/* 2. Error State */}
        {error && !isLoading && (
          <div className="p-4 rounded-2xl bg-red-500/10 border border-red-500/20 text-red-300 text-xs flex flex-col items-center space-y-2 text-center my-6">
            <AlertCircle className="w-5 h-5 shrink-0" />
            <span>{error}</span>
            <button
              onClick={() => executeSearch(query, currentCity?.id)}
              className="px-3 py-1.5 rounded-xl bg-indigo-600/30 text-indigo-300 border border-indigo-500/30 text-xs font-semibold btn-press hover:bg-indigo-600/40"
            >
              Повторить попытку
            </button>
          </div>
        )}

        {/* 3. Empty Search / Suggestions */}
        {!query.trim() && !isLoading && (
          <div className="space-y-5 pt-2">
            {/* Guide Card */}
            <div className="p-4 rounded-2xl bg-[#131722] border border-white/8 space-y-1.5">
              <div className="flex items-center space-x-2 text-indigo-400 font-semibold text-xs">
                <Sparkles className="w-4 h-4" />
                <span>Что происходит рядом?</span>
              </div>
              <p className="text-xs text-gray-400 leading-relaxed">
                Введите название события, любимое кафе, концертную площадку или имя организатора в {currentCity?.name || 'вашем городе'}.
              </p>
            </div>

            {/* Popular Query Chips */}
            <div className="space-y-2.5">
              <div className="text-[11px] font-bold uppercase tracking-wider text-gray-400">
                Популярные запросы
              </div>
              <div className="flex flex-wrap gap-2">
                {QUICK_SUGGESTIONS.map((tag) => (
                  <button
                    key={tag}
                    onClick={() => handleSuggestionClick(tag)}
                    className="px-3.5 py-1.5 rounded-xl bg-[#161A28] border border-white/8 hover:border-indigo-500/50 text-xs text-gray-300 hover:text-white btn-press transition-all flex items-center space-x-1.5"
                  >
                    <span>{tag}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* 4. No Results State */}
        {hasNoResults && (
          <div className="py-16 px-4 text-center rounded-2xl bg-[#141724] border border-white/5 space-y-3 my-4">
            <div className="w-12 h-12 rounded-full bg-indigo-500/10 flex items-center justify-center mx-auto text-indigo-400">
              <Compass className="w-6 h-6" />
            </div>
            <div className="space-y-1">
              <h3 className="font-bold text-sm text-white">Ничего не нашли</h3>
              <p className="text-xs text-gray-400 max-w-xs mx-auto">
                Попробуйте изменить запрос, город или категорию.
              </p>
            </div>
            <div className="flex items-center justify-center space-x-2 pt-1">
              <button
                onClick={handleClear}
                className="px-3.5 py-1.5 rounded-xl bg-white/5 hover:bg-white/10 text-gray-300 text-xs font-semibold btn-press"
              >
                Очистить поиск
              </button>
              <button
                onClick={() => {
                  telegram.hapticImpact('light');
                  onOpenCityModal();
                }}
                className="px-3.5 py-1.5 rounded-xl bg-indigo-600/30 text-indigo-300 hover:bg-indigo-600/40 text-xs font-semibold btn-press border border-indigo-500/30"
              >
                Сменить город
              </button>
            </div>
          </div>
        )}

        {/* 5. Grouped Results */}
        {!isLoading && results && totalAll > 0 && (
          <div className="space-y-6 pb-8">
            {/* --- SECTION: EVENTS --- */}
            {showEvents && (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <span className="text-xs font-bold uppercase tracking-wider text-indigo-400">
                      События
                    </span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 font-bold">
                      {totalEvents}
                    </span>
                  </div>
                </div>

                <div className="space-y-2.5">
                  {results.events.map((ev) => {
                    const eventDate = new Date(ev.start_at);
                    const formattedDate = eventDate.toLocaleDateString('ru-RU', {
                      day: 'numeric',
                      month: 'short',
                      hour: '2-digit',
                      minute: '2-digit',
                    });
                    const priceLabel = ev.is_free
                      ? 'Бесплатно'
                      : `${ev.price_amount} ${ev.price_currency || 'RUB'}`;

                    return (
                      <div
                        key={ev.id}
                        onClick={() => {
                          telegram.hapticImpact('light');
                          onEventClick(ev);
                        }}
                        className="p-3 rounded-2xl bg-[#131722] border border-white/8 hover:border-indigo-500/40 cursor-pointer card-press transition-all flex space-x-3 items-center"
                      >
                        {/* Event Cover Thumbnail */}
                        <div className="relative w-16 h-16 rounded-xl overflow-hidden bg-gray-900 shrink-0">
                          <SafeImage
                            src={ev.cover_image_url}
                            alt={ev.title}
                            className="w-full h-full object-cover"
                          />
                        </div>

                        {/* Event Info */}
                        <div className="flex-1 min-w-0 space-y-1">
                          <div className="flex items-center justify-between gap-1.5">
                            <span className="text-[10px] font-semibold text-indigo-400 px-1.5 py-0.5 rounded bg-indigo-500/10 truncate">
                              {ev.category_name}
                            </span>
                            <span className="text-[10px] font-bold text-gray-300 shrink-0">
                              {priceLabel}
                            </span>
                          </div>

                          <h4 className="font-semibold text-xs text-white truncate">
                            {ev.title}
                          </h4>

                          <div className="flex items-center space-x-3 text-[10px] text-gray-400 truncate">
                            <div className="flex items-center space-x-1 shrink-0">
                              <Calendar className="w-3 h-3 text-indigo-300" />
                              <span>{formattedDate}</span>
                            </div>
                            <div className="flex items-center space-x-1 truncate">
                              <MapPin className="w-3 h-3 text-gray-500 shrink-0" />
                              <span className="truncate">{ev.venue_name}</span>
                            </div>
                          </div>
                        </div>

                        <ChevronRight className="w-4 h-4 text-gray-500 shrink-0" />
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* --- SECTION: ORGANIZATIONS --- */}
            {showOrgs && (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <span className="text-xs font-bold uppercase tracking-wider text-purple-400">
                      Организации
                    </span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-purple-500/20 text-purple-300 font-bold">
                      {totalOrgs}
                    </span>
                  </div>
                </div>

                <div className="space-y-2.5">
                  {results.organizations.map((org) => (
                    <div
                      key={org.id}
                      onClick={() => {
                        telegram.hapticImpact('light');
                        onOrgClick(org.id);
                      }}
                      className="p-3 rounded-2xl bg-[#131722] border border-white/8 hover:border-purple-500/40 cursor-pointer card-press transition-all flex space-x-3 items-center"
                    >
                      {/* Org Avatar */}
                      <SafeAvatar
                        src={org.avatar_url}
                        name={org.name}
                        type="org"
                        sizeClassName="w-12 h-12"
                        className="rounded-xl shrink-0"
                      />

                      {/* Org Info */}
                      <div className="flex-1 min-w-0 space-y-1">
                        <div className="flex items-center space-x-1.5">
                          <h4 className="font-semibold text-xs text-white truncate">
                            {org.name}
                          </h4>
                          {org.is_verified && (
                            <ShieldCheck className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
                          )}
                        </div>

                        <div className="flex items-center space-x-2 text-[10px] text-gray-400 truncate">
                          <span className="text-gray-300 font-medium truncate">{org.category}</span>
                          {org.city_name && (
                            <>
                              <span>•</span>
                              <span className="truncate">{org.city_name}</span>
                            </>
                          )}
                        </div>

                        <div className="flex items-center space-x-3 text-[10px] text-gray-400">
                          <div className="flex items-center space-x-1">
                            <Users className="w-3 h-3 text-purple-400" />
                            <span>{org.followers_count} подписчиков</span>
                          </div>
                          {org.events_count !== undefined && org.events_count > 0 && (
                            <div className="flex items-center space-x-1 text-emerald-400">
                              <span>• {org.events_count} событий</span>
                            </div>
                          )}
                        </div>
                      </div>

                      <ChevronRight className="w-4 h-4 text-gray-500 shrink-0" />
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* --- SECTION: VENUES --- */}
            {showVenues && (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <span className="text-xs font-bold uppercase tracking-wider text-emerald-400">
                      Места и площадки
                    </span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 font-bold">
                      {totalVenues}
                    </span>
                  </div>
                </div>

                <div className="space-y-2.5">
                  {results.venues.map((venue) => (
                    <div
                      key={venue.id}
                      onClick={() => {
                        telegram.hapticImpact('light');
                        onVenueClick(venue);
                      }}
                      className="p-3 rounded-2xl bg-[#131722] border border-white/8 hover:border-emerald-500/40 cursor-pointer card-press transition-all flex space-x-3 items-center"
                    >
                      {/* Venue Icon Squircle */}
                      <div className="w-12 h-12 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 shrink-0 shadow-sm">
                        <MapPin className="w-5 h-5" />
                      </div>

                      {/* Venue Info */}
                      <div className="flex-1 min-w-0 space-y-1">
                        <h4 className="font-semibold text-xs text-white truncate">
                          {venue.name}
                        </h4>

                        <div className="text-[10px] text-gray-400 truncate">
                          {venue.address ? (
                            <span>{venue.address} {venue.city_name ? `(${venue.city_name})` : ''}</span>
                          ) : (
                            <span>{venue.city_name || 'Локация'}</span>
                          )}
                        </div>

                        <div className="flex items-center space-x-2 text-[10px]">
                          {venue.organization_name && (
                            <span className="px-1.5 py-0.5 rounded bg-white/5 text-gray-300 border border-white/5 truncate max-w-[140px]">
                              {venue.organization_name}
                            </span>
                          )}
                          <span className="text-emerald-400 font-medium shrink-0">
                            {venue.upcoming_events_count > 0 
                              ? `${venue.upcoming_events_count} событий скоро`
                              : 'Площадка'}
                          </span>
                        </div>
                      </div>

                      <ChevronRight className="w-4 h-4 text-gray-500 shrink-0" />
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
