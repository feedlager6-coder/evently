import React, { useState } from 'react';
import './design-lab.css';
import { LiquidGlassNavVariantA } from './components/LiquidGlassNavVariantA';
import { LiquidGlassNavVariantB } from './components/LiquidGlassNavVariantB';
import { EditorialEventCard, type EditorialEventCardData } from './components/EditorialEventCard';
import { EditorialControls } from './components/EditorialControls';
import { EventDetailsSheetMock } from './components/EventDetailsSheetMock';
import { OrganizerOverviewMock } from './components/OrganizerOverviewMock';
import { BroadcastComposerMock } from './components/BroadcastComposerMock';
import { useFpsMonitor } from './utils/fpsMonitor';
import { Search, MapPin, ChevronDown, Sparkles, Layers, Calendar, ArrowRight, Activity, LayoutGrid, FileText, Send, Building2 } from 'lucide-react';

export type LabScreen = 'feed' | 'details' | 'organizer' | 'broadcast';


// Representative Realistic Ivently Events
const SAMPLE_EVENTS: EditorialEventCardData[] = [
  {
    id: '1',
    title: 'Вечер джаза и неоклассики в оранжерее',
    coverUrl: '/design-lab/covers/cover1.jpg',
    category: 'Концерты',
    priceText: '1 500 ₽',
    isFree: false,
    dateText: '10 окт., 19:26',
    venueText: 'Ботаническая оранжерея (Москва)',
    cityText: 'Москва',
    attendeesCount: 42,
    likesCount: 88,
    initialInterested: true,
  },
  {
    id: '2',
    title: 'Выставка дагестанского ремесла и серебра Кубачи',
    coverUrl: '/design-lab/covers/cover2.jpg',
    category: 'Выставки',
    priceText: '300 ₽',
    isFree: false,
    dateText: '11 окт., 11:30',
    venueText: 'Музей изобразительных искусств им. Гамзатовой',
    cityText: 'Махачкала',
    attendeesCount: 18,
    likesCount: 64,
  },
  {
    id: '3',
    title: 'Утренний забег на гору Тарки-Тау',
    coverUrl: '/design-lab/covers/cover3.jpg',
    category: 'Спорт',
    priceText: 'Бесплатно',
    isFree: true,
    dateText: '12 окт., 07:00',
    venueText: 'Смотровая площадка Тарки-Тау',
    cityText: 'Махачкала',
    attendeesCount: 56,
    likesCount: 112,
  },
  {
    id: '4',
    title: 'Иммерсивная выставка «Вселенная Ван Гога и Климта»',
    coverUrl: '/design-lab/covers/cover4.jpg',
    category: 'Выставки',
    priceText: '900 ₽',
    isFree: false,
    dateText: '11 окт., 14:00',
    venueText: 'Artplay Design Center (Москва)',
    cityText: 'Москва',
    attendeesCount: 73,
    likesCount: 140,
  },
];


export const DesignLab: React.FC = () => {
  const [navVariant, setNavVariant] = useState<'A' | 'B'>('B');
  const [currentScreen, setCurrentScreen] = useState<LabScreen>('feed');
  const [activeTab, setActiveTab] = useState('feed');
  const [selectedDate, setSelectedDate] = useState('all');
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [selectedCity, setSelectedCity] = useState('Махачкала');
  const [searchQuery, setSearchQuery] = useState('');
  const fps = useFpsMonitor();

  // Filter events
  const filteredEvents = SAMPLE_EVENTS.filter((ev) => {
    if (selectedCategory !== 'all') {
      const catMap: Record<string, string> = {
        concerts: 'Концерты',
        exhibitions: 'Выставки',
        sports: 'Спорт',
      };
      if (catMap[selectedCategory] && ev.category !== catMap[selectedCategory]) {
        return false;
      }
    }
    if (searchQuery.trim()) {
      return ev.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
             ev.venueText.toLowerCase().includes(searchQuery.toLowerCase());
    }
    return true;
  });

  return (
    <div className="min-h-screen bg-[#030406] text-white flex flex-col items-center justify-start p-2 sm:p-6 font-sans antialiased selection:bg-white/20">
      {/* 1. Prototype Lab Master Toolbar (Floating on top) */}
      <header className="w-full max-w-[440px] mb-4 z-40 bg-[#0B0D13]/90 border border-white/10 rounded-2xl p-3 backdrop-blur-xl shadow-2xl flex flex-col gap-2.5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse" />
            <h1 className="text-xs font-bold tracking-wider uppercase text-neutral-300">
              Ivently Design Lab
            </h1>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-mono text-emerald-400 bg-emerald-950/60 border border-emerald-500/20 px-2 py-0.5 rounded-md flex items-center gap-1 font-bold">
              <Activity size={11} />
              <span>{fps} FPS</span>
            </span>
            <span className="text-[11px] font-mono text-neutral-400 bg-white/5 px-2 py-0.5 rounded-md border border-white/5">
              390 × 844
            </span>
          </div>
        </div>

        {/* Screen Switcher */}
        <div className="flex items-center gap-1 bg-black/60 p-1 rounded-xl border border-white/5 overflow-x-auto no-scrollbar">
          {[
            { id: 'feed', label: 'Афиша', icon: LayoutGrid },
            { id: 'details', label: 'Детали', icon: FileText },
            { id: 'organizer', label: 'Кабинет', icon: Building2 },
            { id: 'broadcast', label: 'Рассылка', icon: Send },
          ].map((sc) => {
            const isActive = currentScreen === sc.id;
            const Icon = sc.icon;
            return (
              <button
                key={sc.id}
                type="button"
                onClick={() => setCurrentScreen(sc.id as LabScreen)}
                className={`flex-1 py-1.5 px-2 rounded-lg text-[11px] font-semibold transition-all duration-200 cursor-pointer flex items-center justify-center gap-1 whitespace-nowrap ${
                  isActive
                    ? 'bg-white text-black shadow-md shadow-white/10 font-bold'
                    : 'text-neutral-400 hover:text-white'
                }`}
              >
                <Icon size={12} />
                <span>{sc.label}</span>
              </button>
            );
          })}
        </div>

        {/* Variant Switcher (Glass vs Obsidian) */}
        <div className="flex items-center gap-2 bg-black/40 p-1 rounded-xl border border-white/5">
          <button
            onClick={() => setNavVariant('A')}
            className={`flex-1 py-1 px-2.5 rounded-lg text-[11px] font-semibold transition-all duration-200 cursor-pointer flex items-center justify-center gap-1.5 ${
              navVariant === 'A'
                ? 'bg-white/20 text-white border border-white/20 shadow-sm'
                : 'text-neutral-500 hover:text-neutral-300'
            }`}
          >
            <Layers size={12} />
            <span>Вариант A: Обсидиан</span>
          </button>
          <button
            onClick={() => setNavVariant('B')}
            className={`flex-1 py-1 px-2.5 rounded-lg text-[11px] font-semibold transition-all duration-200 cursor-pointer flex items-center justify-center gap-1.5 ${
              navVariant === 'B'
                ? 'bg-white/20 text-white border border-white/20 shadow-sm'
                : 'text-neutral-500 hover:text-neutral-300'
            }`}
          >
            <Sparkles size={12} />
            <span>Вариант B: Стекло (Выбран)</span>
          </button>
        </div>
      </header>

      {/* 2. Target Mobile Frame: 390px × 844px */}
      <main
        id="mobile-viewport"
        className="relative w-[390px] h-[844px] bg-[#050608] border border-white/[0.12] rounded-[48px] shadow-[0_32px_96px_-16px_rgba(0,0,0,0.9)] overflow-hidden flex flex-col"
        style={{
          boxShadow: '0 0 0 10px #111319, 0 30px 90px rgba(0,0,0,0.9)',
        }}
      >
        {/* Mobile Top Speaker & Dynamic Island */}
        <div className="absolute top-0 left-0 right-0 h-11 z-40 pointer-events-none flex items-center justify-between px-8 pt-1">
          <span className="text-[12px] font-semibold text-white/90">19:42</span>
          <div className="w-[120px] h-[30px] bg-black rounded-full border border-white/5 flex items-center justify-center">
            <div className="w-2.5 h-2.5 rounded-full bg-[#1A1A1A] mr-6" />
            <div className="w-2 h-2 rounded-full bg-[#0D243A]" />
          </div>
          <div className="flex items-center gap-1.5 text-white/80">
            <span className="text-[10px] font-bold">5G</span>
            <div className="w-5 h-2.5 border border-white/80 rounded-sm p-0.5">
              <div className="h-full bg-white rounded-2xs w-[80%]" />
            </div>
          </div>
        </div>

        {/* Mobile Screen Views */}
        {currentScreen === 'feed' && (
          <>
            {/* Scrollable Mobile Body */}
            <div className="flex-1 overflow-y-auto no-scrollbar pt-12 pb-28 flex flex-col">
              {/* Header Bar */}
              <header className="px-4 pt-2 pb-3 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="w-7 h-7 rounded-full bg-white/10 border border-white/20 flex items-center justify-center font-bold text-white text-sm shadow-inner">
                    ✦
                  </span>
                  <span className="font-extrabold text-lg tracking-tight text-white">
                    Ivently
                  </span>
                </div>

                {/* City Selector Pill */}
                <button
                  onClick={() => setSelectedCity((c) => (c === 'Махачкала' ? 'Москва' : 'Махачкала'))}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-white/[0.07] border border-white/10 text-xs font-semibold text-white/90 hover:bg-white/15 transition-all cursor-pointer shadow-sm active:scale-95"
                >
                  <MapPin size={13} className="text-neutral-400" />
                  <span>{selectedCity}</span>
                  <ChevronDown size={13} className="text-neutral-400" />
                </button>
              </header>

              {/* Search Input Bar */}
              <div className="px-4 mb-3">
                <div className="relative flex items-center bg-[#0B0D13] border border-white/[0.08] rounded-2xl px-3.5 py-2.5 shadow-inner">
                  <Search size={16} className="text-neutral-500 mr-2.5 shrink-0" />
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="События, места и организации..."
                    className="w-full bg-transparent text-xs text-white placeholder-neutral-500 outline-none"
                  />
                  <span className="text-[10px] text-neutral-400 bg-white/5 px-2 py-0.5 rounded-md border border-white/5 font-medium shrink-0">
                    {selectedCity}
                  </span>
                </div>
              </div>

              {/* Controls Block (Date Segmented Control + Category Pills) */}
              <EditorialControls
                selectedDate={selectedDate}
                onDateChange={setSelectedDate}
                selectedCategory={selectedCategory}
                onCategoryChange={setSelectedCategory}
                className="mb-4"
              />

              {/* Feed Content or My Events Tab */}
              {activeTab === 'feed' ? (
                <div className="px-4 flex flex-col gap-4">
                  <div className="flex items-center justify-between pt-1">
                    <h3 className="text-xs font-bold uppercase tracking-wider text-neutral-400">
                      Афиша событий ({filteredEvents.length})
                    </h3>
                    <span className="text-[11px] text-neutral-400">Популярное</span>
                  </div>

                  {filteredEvents.map((event) => (
                    <div 
                      key={event.id}
                      onClick={() => setCurrentScreen('details')}
                      className="cursor-pointer"
                      title="Нажмите, чтобы открыть детали события"
                    >
                      <EditorialEventCard event={event} />
                    </div>
                  ))}
                </div>
              ) : (
                <div className="px-4 py-8 flex flex-col items-center justify-center text-center gap-4 my-auto">
                  <div className="w-16 h-16 rounded-3xl liquid-lens flex items-center justify-center text-white mb-2 shadow-xl">
                    <Calendar size={28} />
                  </div>
                  <h3 className="text-base font-bold text-white">Мои события</h3>
                  <p className="text-xs text-neutral-400 max-w-[240px] leading-relaxed">
                    Вы пока не сохранили ни одного мероприятия. Отмечайте события в афише, чтобы они появились здесь.
                  </p>
                  <button
                    onClick={() => setActiveTab('feed')}
                    className="liquid-lens px-5 py-2.5 rounded-full text-xs font-bold text-white flex items-center gap-2 cursor-pointer shadow-lg active:scale-95"
                  >
                    <span>Смотреть афишу</span>
                    <ArrowRight size={14} />
                  </button>
                </div>
              )}
            </div>

            {/* 3. Floating Bottom Navigation Dock (Visible on Feed) */}
            {navVariant === 'A' ? (
              <LiquidGlassNavVariantA activeTab={activeTab} onTabChange={setActiveTab} />
            ) : (
              <LiquidGlassNavVariantB activeTab={activeTab} onTabChange={setActiveTab} />
            )}
          </>
        )}

        {/* Details Screen */}
        {currentScreen === 'details' && (
          <div className="flex-1 flex flex-col justify-end bg-black/60 pt-12 animate-fade-in">
            <EventDetailsSheetMock onClose={() => setCurrentScreen('feed')} />
          </div>
        )}

        {/* Organizer Workspace Screen */}
        {currentScreen === 'organizer' && (
          <div className="flex-1 flex flex-col pt-12 px-2 pb-6 animate-fade-in">
            <OrganizerOverviewMock 
              onBack={() => setCurrentScreen('feed')} 
              onOpenBroadcast={() => setCurrentScreen('broadcast')} 
            />
          </div>
        )}

        {/* Broadcast Composer Screen */}
        {currentScreen === 'broadcast' && (
          <div className="flex-1 flex flex-col justify-end bg-black/60 pt-12 px-2 pb-6 animate-fade-in">
            <BroadcastComposerMock onClose={() => setCurrentScreen('organizer')} />
          </div>
        )}

        {/* Mobile Home Bar Indicator */}
        <div className="absolute bottom-1.5 left-1/2 -translate-x-1/2 w-32 h-1 bg-white/40 rounded-full pointer-events-none z-50" />
      </main>

      {/* Lab Legend & Notes */}
      <footer className="mt-4 text-center text-neutral-400 text-xs max-w-[390px] flex flex-col gap-1">
        <p>
          <strong className="text-neutral-200">Текущий режим:</strong>{' '}
          {navVariant === 'A'
            ? 'Вариант A (Обсидиановая капсула + оптическая линза)'
            : 'Вариант B (Парящий док из жидкого стекла + линза)'}
        </p>
        <p className="text-[11px] text-neutral-400">
          Кликайте по вкладкам, фильтрам и кнопке «Хочу пойти» для проверки живой физики.
        </p>
      </footer>
    </div>
  );
};
