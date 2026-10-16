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
  ShieldCheck, 
  Loader2, 
  AlertCircle, 
  Compass,
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

  // Handle search autofocus
  useEffect(() => {
    if (isOpen) {
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
      };
    }
  }, [isOpen]);

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

  // Re-run search if city changes while modal is open and has an active query
  useEffect(() => {
    if (isOpen && query.trim()) {
      executeSearch(query, currentCity?.id);
    }
  }, [currentCity?.id]);

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
    <div className="fixed inset-0 z-[60] flex flex-col bg-[#0d0d0f] text-white selection:bg-emerald-500/30 overflow-hidden pb-safe">
      {/* Top Navigation Bar (Obsidian Optical Stitch Style) */}
      <header className="pt-3 px-4 pb-2.5 flex items-center justify-between border-b border-white/5 bg-[#0d0d0f]/95 sticky top-0 z-30 backdrop-blur-md">
        <div className="flex items-center gap-3">
          <button
            onClick={() => {
              telegram.hapticImpact('light');
              onClose();
            }}
            className="w-9 h-9 rounded-full bg-white/5 hover:bg-white/10 active:scale-95 flex items-center justify-center transition-all border border-white/5 shrink-0"
            aria-label="Назад"
          >
            <ArrowLeft className="w-5 h-5 text-neutral-300" />
          </button>
          <div className="flex flex-col text-left">
            <span className="text-xs text-neutral-400 font-medium truncate max-w-[170px]">
              {currentCity ? `Поиск по ${currentCity.name}` : 'Поиск событий'}
            </span>
            <span className="text-sm font-semibold tracking-tight text-white">
              {activeTab === 'all' 
                ? 'Все разделы' 
                : activeTab === 'events' 
                  ? 'Мероприятия' 
                  : activeTab === 'organizations' 
                    ? 'Организации' 
                    : 'Площадки'}
            </span>
          </div>
        </div>

        {/* City Switch Button */}
        <button
          onClick={() => {
            telegram.hapticImpact('light');
            onOpenCityModal();
          }}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-white/5 hover:bg-white/10 active:scale-95 border border-white/5 text-xs text-neutral-300 transition-all shrink-0 font-medium"
        >
          <MapPin className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
          <span className="max-w-[70px] truncate">{currentCity?.name || 'Город'}</span>
        </button>
      </header>

      {/* Search Input Area */}
      <div className="px-4 pt-3 pb-2 sticky top-[57px] z-20 bg-[#0d0d0f]/95 backdrop-blur-md border-b border-white/5 space-y-2.5">
        <div className="relative flex items-center">
          <Search className="w-5 h-5 text-neutral-400 absolute left-3.5 pointer-events-none" />
          <input
            ref={inputRef}
            type="search"
            inputMode="search"
            autoFocus
            value={query}
            onChange={handleInputChange}
            placeholder="События, артисты, площадки..."
            className="w-full pl-11 pr-10 py-3 rounded-2xl bg-[#202026]/90 border border-white/12 text-[15px] font-medium text-white placeholder-neutral-500 focus:outline-none focus:border-white/30 transition-all shadow-inner"
          />
          {query && (
            <button
              onClick={handleClear}
              className="absolute right-3 w-6 h-6 rounded-full bg-white/10 hover:bg-white/20 flex items-center justify-center text-neutral-300 active:scale-90 transition-all"
              aria-label="Очистить"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>

        {/* Quick Filter Pills (Obsidian Optical Stitch tabs) */}
        {results && totalAll > 0 && (
          <div className="flex gap-2 overflow-x-auto no-scrollbar pt-1 pb-1">
            <button
              onClick={() => handleTabChange('all')}
              className={`px-3.5 py-1.5 rounded-full text-xs shrink-0 transition-all ${
                activeTab === 'all'
                  ? 'bg-white text-black font-semibold shadow-sm'
                  : 'bg-white/5 text-neutral-300 hover:bg-white/10 border border-white/5 font-medium'
              }`}
            >
              Все ({totalAll})
            </button>
            <button
              onClick={() => handleTabChange('events')}
              className={`px-3.5 py-1.5 rounded-full text-xs shrink-0 transition-all ${
                activeTab === 'events'
                  ? 'bg-white text-black font-semibold shadow-sm'
                  : 'bg-white/5 text-neutral-300 hover:bg-white/10 border border-white/5 font-medium'
              }`}
            >
              События ({totalEvents})
            </button>
            <button
              onClick={() => handleTabChange('organizations')}
              className={`px-3.5 py-1.5 rounded-full text-xs shrink-0 transition-all ${
                activeTab === 'organizations'
                  ? 'bg-white text-black font-semibold shadow-sm'
                  : 'bg-white/5 text-neutral-300 hover:bg-white/10 border border-white/5 font-medium'
              }`}
            >
              Организации ({totalOrgs})
            </button>
            <button
              onClick={() => handleTabChange('venues')}
              className={`px-3.5 py-1.5 rounded-full text-xs shrink-0 transition-all ${
                activeTab === 'venues'
                  ? 'bg-white text-black font-semibold shadow-sm'
                  : 'bg-white/5 text-neutral-300 hover:bg-white/10 border border-white/5 font-medium'
              }`}
            >
              Площадки ({totalVenues})
            </button>
          </div>
        )}
      </div>

      {/* Main Scrollable Results Content */}
      <main className="flex-1 overflow-y-auto custom-scrollbar px-4 py-3 space-y-6">
        {/* 1. Loading State */}
        {isLoading && (
          <div className="space-y-4 pt-2">
            <div className="flex items-center gap-2 text-neutral-400 text-xs font-medium">
              <Loader2 className="w-4 h-4 animate-spin text-emerald-400" />
              <span>Поиск по каталогу Ivently...</span>
            </div>
            {[1, 2, 3].map((i) => (
              <div 
                key={i} 
                className="p-3 rounded-2xl bg-[#1a1a1e]/70 border border-white/8 animate-pulse flex gap-3"
              >
                <div className="w-24 h-24 rounded-xl bg-white/5 shrink-0" />
                <div className="flex-1 space-y-2 py-1">
                  <div className="h-4 bg-white/5 rounded w-3/4" />
                  <div className="h-3 bg-white/5 rounded w-1/2" />
                  <div className="h-3 bg-white/5 rounded w-1/3 mt-4" />
                </div>
              </div>
            ))}
          </div>
        )}

        {/* 2. Error State */}
        {error && !isLoading && (
          <div className="p-4 rounded-2xl bg-red-500/10 border border-red-500/20 text-[#ffb4ab] text-xs flex flex-col items-center space-y-2 text-center my-6">
            <AlertCircle className="w-5 h-5 shrink-0" />
            <span>{error}</span>
            <button
              onClick={() => executeSearch(query, currentCity?.id)}
              className="px-4 py-1.5 rounded-full bg-white/10 hover:bg-white/20 text-white border border-white/10 text-xs font-semibold btn-press transition-all"
            >
              Повторить попытку
            </button>
          </div>
        )}

        {/* 3. Empty Search / Popular Tags / Recent Searches */}
        {!query.trim() && !isLoading && (
          <div className="space-y-6 pt-2">
            {/* Guide Card */}
            <div className="p-4 rounded-2xl bg-[#1a1a1e]/70 border border-white/8 space-y-1.5 backdrop-blur-md">
              <div className="flex items-center gap-2 text-emerald-400 font-semibold text-xs">
                <Sparkles className="w-4 h-4" />
                <span>Что происходит рядом?</span>
              </div>
              <p className="text-xs text-neutral-400 leading-relaxed">
                Введите название события, артиста, клуб или локацию в {currentCity?.name || 'вашем городе'}.
              </p>
            </div>

            {/* Popular Query Chips */}
            <div className="space-y-3">
              <div className="flex items-center justify-between text-xs text-neutral-400">
                <span className="font-semibold uppercase tracking-wider text-[11px]">Популярные запросы</span>
              </div>
              <div className="flex flex-wrap gap-2">
                {QUICK_SUGGESTIONS.map((tag) => (
                  <button
                    key={tag}
                    onClick={() => handleSuggestionClick(tag)}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs bg-white/5 text-neutral-300 hover:text-white hover:bg-white/10 border border-white/5 active:scale-95 transition-all"
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
          <div className="py-16 px-4 text-center rounded-3xl bg-[#1a1a1e]/70 border border-white/8 space-y-3.5 my-4">
            <div className="w-12 h-12 rounded-full bg-white/5 border border-white/10 flex items-center justify-center mx-auto text-emerald-400">
              <Compass className="w-6 h-6" />
            </div>
            <div className="space-y-1">
              <h3 className="font-bold text-sm text-white">Ничего не найдено</h3>
              <p className="text-xs text-neutral-400 max-w-xs mx-auto">
                Попробуйте изменить запрос, проверить название или сменить город.
              </p>
            </div>
            <div className="flex items-center justify-center gap-2 pt-2">
              <button
                onClick={handleClear}
                className="px-4 py-2 rounded-full bg-white/5 hover:bg-white/10 text-neutral-300 text-xs font-semibold border border-white/10 active:scale-95 transition-all"
              >
                Очистить поиск
              </button>
              <button
                onClick={() => {
                  telegram.hapticImpact('light');
                  onOpenCityModal();
                }}
                className="px-4 py-2 rounded-full bg-white text-black hover:bg-neutral-200 text-xs font-semibold active:scale-95 transition-all shadow-sm"
              >
                Сменить город
              </button>
            </div>
          </div>
        )}

        {/* 5. Grouped Results matching Stitch Obsidian Optical */}
        {!isLoading && results && totalAll > 0 && (
          <div className="space-y-6 pb-12">
            {/* --- SECTION: EVENTS --- */}
            {showEvents && (
              <section className="space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold uppercase tracking-wider text-neutral-400">
                      Мероприятия
                    </span>
                    <span className="w-5 h-5 rounded-full bg-white/10 text-[11px] font-medium flex items-center justify-center text-neutral-300">
                      {totalEvents}
                    </span>
                  </div>
                  <span className="text-xs text-neutral-500 font-medium">По соответствию</span>
                </div>

                <div className="space-y-2.5">
                  {results.events.map((ev) => {
                    const eventDate = new Date(ev.start_at);
                    const formattedDateBadge = eventDate.toLocaleDateString('ru-RU', {
                      day: 'numeric',
                      month: 'short',
                    }).toUpperCase();

                    const formattedTime = eventDate.toLocaleTimeString('ru-RU', {
                      hour: '2-digit',
                      minute: '2-digit',
                    });

                    const priceAmount = ev.price_amount;
                    const isFree = Boolean(ev.is_free) || (priceAmount !== null && priceAmount !== undefined && Number(priceAmount) === 0);
                    const priceLabel = isFree
                      ? 'Бесплатно'
                      : priceAmount !== null && priceAmount !== undefined
                        ? `от ${Number(priceAmount) % 1 === 0 ? Number(priceAmount) : priceAmount} ₽`
                        : 'Вход свободный';

                    return (
                      <article
                        key={ev.id}
                        onClick={() => {
                          telegram.hapticImpact('light');
                          onEventClick(ev);
                        }}
                        className="rounded-2xl bg-[#1a1a1e]/70 backdrop-blur-md border border-white/8 hover:border-white/20 p-3 flex gap-3 transition-all active:scale-[0.99] cursor-pointer"
                      >
                        {/* Event Thumbnail with Date badge */}
                        <div className="relative w-24 h-24 rounded-xl overflow-hidden shrink-0 bg-neutral-800">
                          <SafeImage
                            src={ev.cover_image_url}
                            alt={ev.title}
                            className="w-full h-full object-cover"
                          />
                          <div className="absolute top-1.5 left-1.5 px-1.5 py-0.5 rounded bg-black/75 backdrop-blur text-[10px] font-semibold text-emerald-400">
                            {formattedDateBadge}
                          </div>
                        </div>

                        {/* Event Info */}
                        <div className="flex-1 flex flex-col justify-between py-0.5 min-w-0">
                          <div>
                            <div className="flex items-center gap-1.5 text-[11px] text-neutral-400 font-medium truncate">
                              <span>{formattedTime}</span>
                              {ev.venue_name && (
                                <>
                                  <span>•</span>
                                  <span className="truncate">{ev.venue_name}</span>
                                </>
                              )}
                            </div>
                            <h3 className="text-sm font-bold text-white tracking-tight mt-0.5 truncate">
                              {ev.title}
                            </h3>
                            <p className="text-xs text-neutral-400 line-clamp-1 mt-0.5">
                              {ev.category_name}
                            </p>
                          </div>

                          <div className="flex items-center justify-between mt-2 pt-1.5 border-t border-white/5">
                            <span className="text-xs font-semibold text-emerald-400">
                              {priceLabel}
                            </span>
                            <span className="text-[11px] text-neutral-400 bg-white/5 px-2 py-0.5 rounded-full">
                              {ev.attendee_count > 0 ? `${ev.attendee_count} идут` : 'Афиша'}
                            </span>
                          </div>
                        </div>
                      </article>
                    );
                  })}
                </div>
              </section>
            )}

            {/* --- SECTION: ORGANIZATIONS --- */}
            {showOrgs && (
              <section className="space-y-3">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold uppercase tracking-wider text-neutral-400">
                    Организации
                  </span>
                  <span className="w-5 h-5 rounded-full bg-white/10 text-[11px] font-medium flex items-center justify-center text-neutral-300">
                    {totalOrgs}
                  </span>
                </div>

                <div className="space-y-2.5">
                  {results.organizations.map((org) => (
                    <div
                      key={org.id}
                      onClick={() => {
                        telegram.hapticImpact('light');
                        onOrgClick(org.id);
                      }}
                      className="rounded-2xl bg-[#1a1a1e]/70 backdrop-blur-md border border-white/8 hover:border-white/20 p-3.5 flex items-center justify-between transition-all cursor-pointer active:scale-[0.99]"
                    >
                      {/* Org Avatar */}
                      <div className="flex items-center gap-3 min-w-0">
                        <div className="w-12 h-12 rounded-full bg-neutral-800 border border-white/10 flex items-center justify-center shrink-0 overflow-hidden">
                          <SafeAvatar
                            src={org.avatar_url}
                            name={org.name}
                            type="org"
                            sizeClassName="w-12 h-12"
                            className="rounded-full"
                          />
                        </div>

                        {/* Org Info */}
                        <div className="min-w-0">
                          <div className="flex items-center gap-1.5">
                            <h4 className="text-sm font-bold text-white truncate">
                              {org.name}
                            </h4>
                            {org.is_verified && (
                              <ShieldCheck className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                            )}
                          </div>
                          <p className="text-xs text-neutral-400 truncate">
                            {org.category || 'Организатор'} • {org.followers_count} подписчиков
                          </p>
                        </div>
                      </div>

                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          telegram.hapticImpact('light');
                          onOrgClick(org.id);
                        }}
                        className="px-3 py-1.5 rounded-full text-xs font-semibold bg-white/10 hover:bg-white/20 text-white transition-all shrink-0 ml-2"
                      >
                        В профиль
                      </button>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* --- SECTION: VENUES --- */}
            {showVenues && (
              <section className="space-y-3">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold uppercase tracking-wider text-neutral-400">
                    Площадки
                  </span>
                  <span className="w-5 h-5 rounded-full bg-white/10 text-[11px] font-medium flex items-center justify-center text-neutral-300">
                    {totalVenues}
                  </span>
                </div>

                <div className="space-y-2.5">
                  {results.venues.map((venue) => (
                    <div
                      key={venue.id}
                      onClick={() => {
                        telegram.hapticImpact('light');
                        onVenueClick(venue);
                      }}
                      className="rounded-2xl bg-[#1a1a1e]/70 backdrop-blur-md border border-white/8 hover:border-white/20 p-3.5 flex items-center justify-between transition-all cursor-pointer active:scale-[0.99]"
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        <div className="w-12 h-12 rounded-xl bg-neutral-800 border border-white/10 flex items-center justify-center text-neutral-300 shrink-0">
                          <MapPin className="w-6 h-6 text-neutral-400" />
                        </div>
                        <div className="min-w-0">
                          <h4 className="text-sm font-bold text-white truncate">
                            {venue.name}
                          </h4>
                          <p className="text-xs text-neutral-400 truncate">
                            {venue.address ? venue.address : (venue.city_name || 'Локация')}
                            {venue.upcoming_events_count > 0 ? ` • ${venue.upcoming_events_count} активных событий` : ''}
                          </p>
                        </div>
                      </div>

                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          telegram.hapticImpact('light');
                          onVenueClick(venue);
                        }}
                        className="px-3 py-1.5 rounded-full text-xs font-semibold bg-white/5 hover:bg-white/10 text-neutral-300 border border-white/10 transition-all shrink-0 ml-2"
                      >
                        На карте
                      </button>
                    </div>
                  ))}
                </div>
              </section>
            )}
          </div>
        )}
      </main>
    </div>
  );
};
