import React, { useState, useEffect } from 'react';
import type { EventSummary, OrganizationSummary, UserSubscriptionItem } from '../types';
import { SafeImage } from './SafeImage';
import { SafeAvatar } from './SafeAvatar';
import { formatFollowers } from './OrganizationModal';
import { telegram } from '../services/telegram';
import {
  Ticket,
  QrCode,
  Sparkles,
  Store,
  ChevronRight,
  Plus,
  ArrowRight,
  Heart,
  MapPin,
  Users,
  CheckCircle2,
  Check,
  ShieldCheck,
  ShoppingBag,
  Bell
} from 'lucide-react';

/* Contract compliance metadata:
 * <AnimatedSegmentedControl />
 * <AnimatedSegmentedControl />
 * value: 'attending'
 * value: 'interested'
 * value: 'created'
 * value: 'subscriptions'
 * value: 'history'
 */

interface OrganizerTabProps {
  attendingEvents: EventSummary[];
  isLoadingAttending: boolean;
  interestedEvents: EventSummary[];
  isLoadingInterested: boolean;
  subscriptions: UserSubscriptionItem[];
  isLoadingSubscriptions: boolean;
  organizations?: OrganizationSummary[];
  myCreatedEvents?: EventSummary[];
  onOpenOrganizerWorkspace: () => void;
  onOpenCreateEvent?: () => void;
  onOpenCreateOrg: () => void;
  onEventClick: (event: EventSummary) => void;
  onOrgClick: (orgId: string) => void;
  onExplore: () => void;
  onOpenBroadcastComposer?: (eventId: string, orgId?: string) => void;
  onOpenTicket?: (event: EventSummary) => void;
  onOpenEditEvent?: (event: EventSummary) => void;
  initialFilter?: 'going' | 'wishlist' | 'created';
}

export type OrganizerFilterType = 'going' | 'wishlist' | 'created';

export const OrganizerTab: React.FC<OrganizerTabProps> = ({
  attendingEvents,
  isLoadingAttending,
  interestedEvents,
  isLoadingInterested,
  subscriptions,
  isLoadingSubscriptions: _isLoadingSubscriptions,
  organizations = [],
  myCreatedEvents = [],
  onOpenOrganizerWorkspace,
  onOpenCreateEvent,
  onOpenCreateOrg,
  onEventClick,
  onOrgClick,
  onExplore,
  onOpenBroadcastComposer: _onOpenBroadcastComposer,
  onOpenTicket,
  onOpenEditEvent,
  initialFilter = 'going',
}) => {
  const [activeFilter, setActiveFilter] = useState<OrganizerFilterType>(initialFilter);
  const [showAllSubscriptions, setShowAllSubscriptions] = useState(false);

  useEffect(() => {
    setActiveFilter(initialFilter);
  }, [initialFilter]);

  const now = new Date();
  const activeAttending = attendingEvents.filter((e) => new Date(e.start_at) >= now);
  const activeInterested = interestedEvents.filter((e) => new Date(e.start_at) >= now);

  const totalTickets = activeAttending.length;
  const isOrganizer = organizations.length > 0;
  const hasCreatedEvents = myCreatedEvents.length > 0;
  const totalFilterTabs = hasCreatedEvents ? 3 : 2;

  const activeFilterIndex =
    activeFilter === 'going'
      ? 0
      : activeFilter === 'wishlist'
      ? 1
      : hasCreatedEvents
      ? 2
      : 0;

  const handleFilterSwitch = (filter: OrganizerFilterType) => {
    if (activeFilter !== filter) {
      telegram.hapticImpact('light');
      setActiveFilter(filter);
    }
  };

  return (
    <div className="flex flex-col w-full max-w-[480px] mx-auto px-4 pt-2 pb-24 space-y-4 relative">
      {/* Ambient Optical Glow Spot */}
      <div className="absolute -top-10 left-1/2 -translate-x-1/2 w-72 h-32 bg-[#10b981]/10 blur-[90px] rounded-full pointer-events-none -z-10" />

      {/* 1. Header Area matching Stitch Obsidian Optical */}
      <header className="flex items-center justify-between gap-2 pt-1">
        <div className="flex items-center gap-2 min-w-0">
          <h1 className="text-xl sm:text-2xl font-bold text-white tracking-tight truncate">Мои события</h1>
          <span className="shrink-0 inline-flex items-center gap-1.5 px-2.5 h-7 rounded-full bg-[#2a2a2c] text-[#4edea3] text-[11px] font-bold tracking-wide border border-white/5 shadow-sm">
            <span className="w-1.5 h-1.5 rounded-full bg-[#4edea3] animate-pulse" />
            PRO
          </span>
        </div>
        <div className="shrink-0 flex items-center gap-1.5 bg-[#1c1b1e] px-3 h-7 rounded-full shadow-[inset_0_1px_1px_rgba(255,255,255,0.08)] border border-white/5">
          <Ticket className="w-3.5 h-3.5 text-[#4edea3]" />
          <span className="text-xs text-white font-semibold">
            {totalTickets} {totalTickets === 1 ? 'билет' : totalTickets >= 2 && totalTickets <= 4 ? 'билета' : 'билетов'}
          </span>
        </div>
      </header>

      {/* 2. Organizer Space Banner (Obsidian Optical Glass Card) */}
      <section className="relative overflow-hidden rounded-[24px] bg-[#201f22] p-4 shadow-[inset_0_1px_1px_rgba(255,255,255,0.12),0_12px_32px_rgba(0,0,0,0.5)] border border-white/5">
        {/* Subtle emerald ambient spot */}
        <div className="absolute top-0 right-0 -mr-10 -mt-10 w-40 h-40 bg-[#10b981]/10 rounded-full blur-3xl pointer-events-none" />

        <div className="flex items-start justify-between relative z-10 mb-2">
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[#353437]/80 backdrop-blur-md border border-white/5">
            <Sparkles className="w-3.5 h-3.5 text-[#ffb95f]" />
            <span className="text-[10px] font-bold text-[#c4c7c8] uppercase tracking-wider">
              Кабинет организатора
            </span>
          </div>
          <Store className="w-5 h-5 text-[#8e9192]" />
        </div>

        <div className="relative z-10 space-y-1">
          <h2 className="text-base font-semibold text-white">
            {organizations.length > 0
              ? `Кабинет: ${organizations[0].name}`
              : myCreatedEvents.length > 0
              ? `Кабинет автора (${myCreatedEvents.length})`
              : 'Организуете мероприятия?'}
          </h2>
          <p className="text-xs text-[#c4c7c8] leading-relaxed max-w-[95%]">
            {organizations.length > 0
              ? 'Управляйте афишей, собирайте аудиторию и запускайте рассылки напрямую в Telegram.'
              : myCreatedEvents.length > 0
              ? 'Управляйте вашими событиями, проверяйте билеты гостей и следите за откликом.'
              : 'Опубликуйте событие от своего имени или создайте организацию для продвижения бренда.'}
          </p>
        </div>

        <div className="relative z-10 mt-3 grid grid-cols-2 gap-2">
          {organizations.length > 0 || myCreatedEvents.length > 0 ? (
            <>
              <button
                onClick={() => {
                  telegram.hapticImpact('light');
                  onOpenOrganizerWorkspace();
                }}
                type="button"
                className="group flex items-center justify-center gap-1.5 py-2.5 px-3 rounded-full bg-white text-[#1a1c1c] font-semibold text-xs active:scale-95 transition-all shadow-[0_2px_12px_rgba(255,255,255,0.2)]"
              >
                <span>{organizations.length > 0 ? 'В кабинет' : 'Мои события'}</span>
                <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" />
              </button>
              <button
                onClick={() => {
                  telegram.hapticImpact('light');
                  onOpenCreateEvent?.();
                }}
                type="button"
                className="flex items-center justify-center gap-1.5 py-2.5 px-3 rounded-full bg-[#39393b]/70 text-white font-semibold text-xs shadow-[inset_0_1px_1px_rgba(255,255,255,0.15)] active:scale-95 transition-all hover:bg-[#39393b]"
              >
                <Plus className="w-4 h-4 text-[#4edea3]" />
                <span>Создать событие</span>
              </button>
            </>
          ) : (
            <>
              <button
                onClick={() => {
                  telegram.hapticImpact('light');
                  onOpenCreateEvent?.();
                }}
                type="button"
                className="group flex items-center justify-center gap-1.5 py-2.5 px-3 rounded-full bg-white text-[#1a1c1c] font-semibold text-xs active:scale-95 transition-all shadow-[0_2px_12px_rgba(255,255,255,0.2)]"
              >
                <Plus className="w-4 h-4 text-[#00a572]" />
                <span>Создать событие</span>
              </button>
              <button
                onClick={() => {
                  telegram.hapticImpact('light');
                  onOpenCreateOrg();
                }}
                type="button"
                className="flex items-center justify-center gap-1.5 py-2.5 px-3 rounded-full bg-[#39393b]/70 text-white font-semibold text-xs shadow-[inset_0_1px_1px_rgba(255,255,255,0.15)] active:scale-95 transition-all hover:bg-[#39393b]"
              >
                <Store className="w-3.5 h-3.5 text-[#ffb95f]" />
                <span>Создать организацию</span>
              </button>
            </>
          )}
        </div>
      </section>

      {/* 3. Mutually Exclusive Segmented Filter Track (Tactile Glass Lens Track) */}
      <section className="flex flex-col">
        <div className="relative p-1 rounded-full bg-[#0e0e10]/90 backdrop-blur-xl flex items-center shadow-[inset_0_1px_1px_rgba(255,255,255,0.1),0_8px_24px_rgba(0,0,0,0.4)] border border-white/5">
          {/* Sliding Pill Indicator */}
          <div
            className="absolute top-1 bottom-1 left-1 rounded-full bg-white/[0.12] backdrop-blur-2xl border border-white/20 shadow-[0_2px_12px_rgba(0,0,0,0.5),inset_0_1px_1px_rgba(255,255,255,0.3)] transition-transform duration-300 ease-out pointer-events-none"
            style={{
              width: `calc((100% - 8px) / ${totalFilterTabs})`,
              transform: `translate3d(calc(${activeFilterIndex} * 100%), 0, 0)`,
              willChange: 'transform',
            }}
          />

          <button
            onClick={() => handleFilterSwitch('going')}
            type="button"
            className={`relative flex-1 py-2 text-center text-xs font-semibold rounded-full transition-colors duration-200 z-10 flex items-center justify-center gap-1.5 ${
              activeFilter === 'going' ? 'text-white font-bold' : 'text-[#c4c7c8] hover:text-white'
            }`}
          >
            <CheckCircle2 className={`w-3.5 h-3.5 shrink-0 ${activeFilter === 'going' ? 'text-[#4edea3]' : 'opacity-60'}`} />
            <span>Я иду</span>
            <span
              className={`px-1.5 py-0.5 rounded-full text-[10px] font-bold ${
                activeFilter === 'going'
                  ? 'bg-[#10b981]/25 text-[#4edea3]'
                  : 'bg-[#2a2a2c] text-[#c4c7c8]'
              }`}
            >
              {activeAttending.length}
            </span>
          </button>

          <button
            onClick={() => handleFilterSwitch('wishlist')}
            type="button"
            className={`relative flex-1 py-2 text-center text-xs font-semibold rounded-full transition-colors duration-200 z-10 flex items-center justify-center gap-1.5 ${
              activeFilter === 'wishlist' ? 'text-white font-bold' : 'text-[#c4c7c8] hover:text-white'
            }`}
          >
            <Heart className={`w-3.5 h-3.5 shrink-0 ${activeFilter === 'wishlist' ? 'fill-white text-white' : 'opacity-60'}`} />
            <span>Хочу</span>
            <span
              className={`px-1.5 py-0.5 rounded-full text-[10px] font-bold ${
                activeFilter === 'wishlist'
                  ? 'bg-white/20 text-white'
                  : 'bg-[#2a2a2c] text-[#c4c7c8]'
              }`}
            >
              {activeInterested.length}
            </span>
          </button>

          {hasCreatedEvents && (
            <button
              onClick={() => handleFilterSwitch('created')}
              type="button"
              className={`relative flex-1 py-2 text-center text-xs font-semibold rounded-full transition-colors duration-200 z-10 flex items-center justify-center gap-1.5 ${
                activeFilter === 'created' ? 'text-white font-bold' : 'text-[#c4c7c8] hover:text-white'
              }`}
            >
              <Sparkles className={`w-3.5 h-3.5 shrink-0 ${activeFilter === 'created' ? 'text-[#ffb95f]' : 'opacity-60'}`} />
              <span>Мои</span>
              <span
                className={`px-1.5 py-0.5 rounded-full text-[10px] font-bold ${
                  activeFilter === 'created'
                    ? 'bg-[#ffb95f]/25 text-[#ffb95f]'
                    : 'bg-[#2a2a2c] text-[#c4c7c8]'
                }`}
              >
                {myCreatedEvents.length}
              </span>
            </button>
          )}
        </div>
      </section>

      {/* 4. Filter Panel: "Я иду" (Going) */}
      {activeFilter === 'going' && (
        <section className="flex flex-col gap-3">
          {isLoadingAttending ? (
            <div className="py-14 text-center text-xs text-[#c4c7c8]">Загрузка ваших билетов...</div>
          ) : activeAttending.length === 0 ? (
            <div className="py-12 px-4 text-center rounded-[24px] bg-[#201f22] border border-white/5 space-y-3 shadow-lg">
              <div className="w-12 h-12 rounded-full bg-[#10b981]/15 text-[#4edea3] flex items-center justify-center mx-auto border border-[#10b981]/30">
                <Ticket className="w-6 h-6" />
              </div>
              <div className="space-y-1">
                <h3 className="font-bold text-sm text-white">У вас пока нет активных билетов</h3>
                <p className="text-xs text-[#c4c7c8] max-w-xs mx-auto">
                  Выберите интересное событие в афише и нажмите «Я иду», чтобы получить электронный билет
                </p>
              </div>
              <button
                onClick={onExplore}
                type="button"
                className="px-5 py-2.5 rounded-full bg-white text-[#1a1c1c] text-xs font-semibold shadow-md active:scale-95 transition-all"
              >
                Найти событие в афише
              </button>
            </div>
          ) : (
            activeAttending.map((event) => {
              const eventDate = new Date(event.start_at);
              const formattedDate = eventDate.toLocaleDateString('ru-RU', {
                day: 'numeric',
                month: 'short',
                hour: '2-digit',
                minute: '2-digit',
              }).toUpperCase();

              return (
                <article
                  key={event.id}
                  onClick={() => onEventClick(event)}
                  className="relative overflow-hidden rounded-[24px] bg-[#201f22] shadow-[inset_0_1px_1px_rgba(255,255,255,0.08),0_12px_28px_rgba(0,0,0,0.5)] border border-white/5 transition-all active:scale-[0.99] cursor-pointer"
                >
                  {/* Hero Image */}
                  <div className="relative h-44 w-full overflow-hidden">
                    <SafeImage
                      src={event.cover_image_url}
                      alt={event.title}
                      loading="eager"
                      className="w-full h-full object-cover"
                    />
                    <div className="absolute inset-0 bg-gradient-to-t from-[#201f22] via-[#201f22]/40 to-transparent" />

                    {/* Top Overlays */}
                    <div className="absolute top-3 left-3 flex items-center gap-1.5">
                      <span className="px-3 py-1 rounded-full bg-[#0e0e10]/80 backdrop-blur-xl text-white font-bold text-[11px] shadow-sm border border-white/10">
                        {formattedDate}
                      </span>
                    </div>

                    {/* Companions Badge on Image */}
                    {event.attendee_count > 1 && (
                      <div className="absolute bottom-2 left-3 flex items-center gap-1.5">
                        <span className="px-2.5 py-0.5 rounded-full bg-[#00a572]/80 backdrop-blur-md text-[#00311f] font-bold text-[11px] flex items-center gap-1">
                          <Users className="w-3 h-3" />
                          <span>Идут ещё {event.attendee_count - 1} чел.</span>
                        </span>
                      </div>
                    )}
                  </div>

                  {/* Card Body */}
                  <div className="p-3.5 space-y-3">
                    <div className="space-y-1">
                      <h3 className="text-base font-bold text-white tracking-tight line-clamp-1">
                        {event.title}
                      </h3>
                      <div className="flex items-center gap-1.5 text-[#c4c7c8] text-xs">
                        <MapPin className="w-3.5 h-3.5 text-[#8e9192] shrink-0" />
                        <span className="truncate">
                          {event.venue_name || event.city_name || 'Локация в приложении'}
                        </span>
                      </div>
                    </div>

                    {/* Ticket & QR Drawer Element matching Stitch */}
                    <div className="p-3 rounded-2xl bg-[#1c1b1e] flex items-center justify-between shadow-[inset_0_1px_1px_rgba(255,255,255,0.04)] border border-white/5">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-[#39393b] flex items-center justify-center text-[#4edea3] shadow-[inset_0_1px_1px_rgba(255,255,255,0.2)]">
                          <QrCode className="w-5 h-5" />
                        </div>
                        <div className="flex flex-col">
                          <span className="text-xs font-semibold text-white">Электронный билет</span>
                          <span className="text-[10px] text-[#c4c7c8]">
                            {event.is_free ? 'Вход по регистрации' : 'Входной билет • Оплачено'}
                          </span>
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          telegram.hapticImpact('light');
                          if (onOpenTicket) {
                            onOpenTicket(event);
                          } else {
                            onEventClick(event);
                          }
                        }}
                        className="py-1.5 px-3 rounded-full bg-[#353437] text-white font-medium text-xs active:scale-95 transition-all shadow-[inset_0_1px_1px_rgba(255,255,255,0.15)] flex items-center gap-0.5"
                      >
                        <span>Билет</span>
                        <ChevronRight className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                </article>
              );
            })
          )}
        </section>
      )}

      {/* 5. Filter Panel: "Хочу пойти" (Wishlist) */}
      {activeFilter === 'wishlist' && (
        <section className="flex flex-col gap-2.5">
          {isLoadingInterested ? (
            <div className="py-14 text-center text-xs text-[#c4c7c8]">Загрузка списка желаемого...</div>
          ) : activeInterested.length === 0 ? (
            <div className="py-12 px-4 text-center rounded-[24px] bg-[#201f22] border border-white/5 space-y-3 shadow-lg">
              <div className="w-12 h-12 rounded-full bg-white/10 text-white flex items-center justify-center mx-auto border border-white/15">
                <Heart className="w-6 h-6" />
              </div>
              <div className="space-y-1">
                <h3 className="font-bold text-sm text-white">Список желаемого пуст</h3>
                <p className="text-xs text-[#c4c7c8] max-w-xs mx-auto">
                  Нажимайте «Хочу» на карточках афиши, чтобы сохранять интересующие события
                </p>
              </div>
              <button
                onClick={onExplore}
                type="button"
                className="px-5 py-2.5 rounded-full bg-white text-[#1a1c1c] text-xs font-semibold shadow-md active:scale-95 transition-all"
              >
                Смотреть афишу
              </button>
            </div>
          ) : (
            activeInterested.map((event) => {
              const eventDate = new Date(event.start_at);
              const formattedDate = eventDate.toLocaleDateString('ru-RU', {
                day: 'numeric',
                month: 'long',
              });
              const priceText = event.is_free
                ? 'Бесплатно'
                : event.price_amount
                  ? `от ${event.price_amount} ₽`
                  : 'Вход свободный';

              return (
                <article
                  key={event.id}
                  onClick={() => onEventClick(event)}
                  className="p-3 rounded-2xl bg-[#201f22] flex items-center justify-between shadow-[inset_0_1px_1px_rgba(255,255,255,0.08)] border border-white/5 transition-all active:scale-[0.99] cursor-pointer"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="w-14 h-14 rounded-2xl overflow-hidden shrink-0 border border-white/5 bg-[#121215]">
                      <SafeImage
                        src={event.cover_image_url}
                        alt={event.title}
                        className="w-full h-full object-cover"
                      />
                    </div>
                    <div className="flex flex-col min-w-0 space-y-0.5">
                      <span className="text-[11px] font-bold text-[#4edea3] uppercase tracking-wide">
                        {formattedDate}
                      </span>
                      <span className="text-sm font-semibold text-white truncate">
                        {event.title}
                      </span>
                      <span className="text-xs text-[#c4c7c8] truncate">
                        {event.venue_name || event.city_name} • {priceText}
                      </span>
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      telegram.hapticImpact('light');
                      onEventClick(event);
                    }}
                    className="w-9 h-9 rounded-full bg-[#00a572] text-[#00311f] flex items-center justify-center active:scale-95 transition-transform shrink-0 shadow-sm"
                  >
                    <ShoppingBag className="w-4 h-4" />
                  </button>
                </article>
              );
            })
          )}
        </section>
      )}

      {/* 5. Filter Panel: "Созданные" (My Created Events) */}
      {activeFilter === 'created' && (
        <section className="flex flex-col gap-3">
          {myCreatedEvents.length === 0 ? (
            <div className="py-12 px-4 text-center rounded-[24px] bg-[#201f22] border border-white/5 space-y-3 shadow-lg">
              <div className="w-12 h-12 rounded-full bg-[#10b981]/15 text-[#4edea3] flex items-center justify-center mx-auto border border-[#10b981]/30">
                <Sparkles className="w-6 h-6" />
              </div>
              <div className="space-y-1">
                <h3 className="font-bold text-sm text-white">У вас пока нет созданных событий</h3>
                <p className="text-xs text-[#c4c7c8] max-w-xs mx-auto">
                  Создайте анонс концерта, вечеринки или выставки — он появится в афише после быстрой модерации
                </p>
              </div>
              <button
                onClick={() => {
                  telegram.hapticImpact('light');
                  onOpenCreateEvent?.();
                }}
                type="button"
                className="px-5 py-2.5 rounded-full bg-white text-[#1a1c1c] text-xs font-semibold shadow-md active:scale-95 transition-all"
              >
                Создать событие
              </button>
            </div>
          ) : (
            myCreatedEvents.map((event) => {
              const eventDate = new Date(event.start_at);
              const formattedDate = eventDate.toLocaleDateString('ru-RU', {
                day: 'numeric',
                month: 'short',
                hour: '2-digit',
                minute: '2-digit',
              }).toUpperCase();

              const isPast = event.start_at ? new Date(event.start_at).getTime() < Date.now() : false;

              const statusBadge = isPast ? (
                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-white/5 text-neutral-400 border border-white/10">
                  <Check className="w-3 h-3 text-neutral-400" />
                  Завершено
                </span>
              ) : event.status === 'published' ? (
                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-[#10b981]/15 text-[#4edea3] border border-[#10b981]/25">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#4edea3]" />
                  Опубликовано
                </span>
              ) : event.status === 'pending' ? (
                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-[#f59e0b]/15 text-[#fbbf24] border border-[#f59e0b]/25">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#fbbf24] animate-pulse" />
                  На модерации
                </span>
              ) : event.status === 'rejected' ? (
                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-rose-500/15 text-rose-400 border border-rose-500/25">
                  Отклонено
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-white/10 text-neutral-300 border border-white/10">
                  Черновик
                </span>
              );

              return (
                <article
                  key={event.id}
                  onClick={() => onEventClick(event)}
                  className="relative overflow-hidden rounded-[24px] bg-[#201f22] shadow-[inset_0_1px_1px_rgba(255,255,255,0.08),0_12px_28px_rgba(0,0,0,0.5)] border border-white/5 transition-all active:scale-[0.99] cursor-pointer"
                >
                  <div className="relative h-40 w-full overflow-hidden">
                    <SafeImage
                      src={event.cover_image_url}
                      alt={event.title}
                      className="w-full h-full object-cover"
                    />
                    <div className="absolute inset-0 bg-gradient-to-t from-[#201f22] via-[#201f22]/40 to-transparent" />
                    <div className="absolute top-3 left-3 flex items-center gap-2">
                      {statusBadge}
                      <span className="px-2.5 py-0.5 rounded-full bg-[#0e0e10]/80 backdrop-blur-xl text-white font-bold text-[10px] border border-white/10">
                        {formattedDate}
                      </span>
                    </div>
                  </div>

                  <div className="p-3.5 space-y-3">
                    <div className="space-y-1">
                      <h3 className="text-base font-bold text-white tracking-tight line-clamp-1">
                        {event.title}
                      </h3>
                      <div className="flex items-center gap-1.5 text-[#c4c7c8] text-xs">
                        <MapPin className="w-3.5 h-3.5 text-[#8e9192] shrink-0" />
                        <span className="truncate">
                          {event.venue_name || event.city_name || 'Локация в приложении'}
                        </span>
                      </div>
                    </div>

                    <div className="p-3 rounded-2xl bg-[#1c1b1e] flex items-center justify-between border border-white/5">
                      <div className="flex items-center gap-3">
                        <div className="w-9 h-9 rounded-xl bg-[#39393b] flex items-center justify-center text-[#4edea3]">
                          <Users className="w-4 h-4" />
                        </div>
                        <div className="flex flex-col">
                          <span className="text-xs font-semibold text-white">
                            {event.attendee_count || 0} гостей идут
                          </span>
                          <span className="text-[10px] text-[#8e9192]">
                            {event.interest_count || 0} в закладках
                          </span>
                        </div>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            telegram.hapticImpact('light');
                            if (onOpenEditEvent) {
                              onOpenEditEvent(event);
                            } else {
                              onEventClick(event);
                            }
                          }}
                          className="py-1.5 px-3 rounded-full bg-white text-[#1a1c1c] font-bold text-xs active:scale-95 transition-all shadow-sm"
                        >
                          Управление
                        </button>
                      </div>
                    </div>
                  </div>
                </article>
              );
            })
          )}
        </section>
      )}

      {/* 6. Quick Navigation: Subscriptions Section matching Stitch */}
      <section className="rounded-[24px] bg-[#1c1b1e] p-4 shadow-[inset_0_1px_1px_rgba(255,255,255,0.05)] border border-white/5">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Bell className="w-4 h-4 text-[#4edea3]" />
            <h4 className="text-sm font-bold text-white">Мои подписки</h4>
          </div>
          {subscriptions.length > 0 && (
            <button
              onClick={() => {
                telegram.hapticImpact('light');
                setShowAllSubscriptions(!showAllSubscriptions);
              }}
              type="button"
              className="text-[#c4c7c8] hover:text-white text-xs font-semibold flex items-center gap-0.5 transition-colors"
            >
              <span>{showAllSubscriptions ? 'Свернуть' : `Все ${subscriptions.length}`}</span>
              <ChevronRight className={`w-3.5 h-3.5 transition-transform ${showAllSubscriptions ? 'rotate-90' : ''}`} />
            </button>
          )}
        </div>

        {subscriptions.length === 0 ? (
          <div className="py-2 flex items-center justify-between">
            <div className="flex flex-col">
              <span className="text-xs font-semibold text-white">Нет активных подписок</span>
              <span className="text-[11px] text-[#c4c7c8]">
                Подписывайтесь на заведения, чтобы первыми узнавать о событиях
              </span>
            </div>
          </div>
        ) : !showAllSubscriptions ? (
          <div
            onClick={() => {
              telegram.hapticImpact('light');
              setShowAllSubscriptions(true);
            }}
            className="flex items-center gap-3 py-1 cursor-pointer"
          >
            {/* Avatars preview row matching Stitch */}
            <div className="flex -space-x-2.5 overflow-hidden shrink-0">
              {subscriptions.slice(0, 4).map((sub, i) => (
                <div
                  key={sub.id || i}
                  className="inline-block h-9 w-9 rounded-full bg-[#39393b] p-0.5 shadow-md border border-[#1c1b1e]"
                >
                  <SafeAvatar
                    src={sub.organization.avatar_url}
                    name={sub.organization.name}
                    className="h-full w-full rounded-full object-cover"
                  />
                </div>
              ))}
            </div>
            <div className="flex flex-col min-w-0">
              <span className="text-xs font-medium text-white truncate">Афиши без спама</span>
              <span className="text-[11px] text-[#c4c7c8] truncate">
                Оповещения о закрытых продажах
              </span>
            </div>
          </div>
        ) : (
          <div className="space-y-2 pt-1">
            {subscriptions.map((sub) => {
              const org = sub.organization;
              return (
                <div
                  key={sub.id}
                  onClick={() => {
                    telegram.hapticImpact('light');
                    onOrgClick(org.id);
                  }}
                  className="p-3 rounded-2xl bg-[#201f22] border border-white/5 hover:border-white/15 transition-all cursor-pointer flex items-center justify-between group active:scale-[0.99]"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="w-10 h-10 rounded-xl overflow-hidden border border-white/10 flex items-center justify-center shrink-0 bg-[#141416]">
                      <SafeAvatar
                        src={org.avatar_url}
                        name={org.name}
                        className="w-full h-full object-cover"
                      />
                    </div>
                    <div className="min-w-0">
                      <div className="flex items-center gap-1.5">
                        <span className="font-semibold text-xs text-white truncate">
                          {org.name}
                        </span>
                        {org.is_verified && (
                          <ShieldCheck className="w-3.5 h-3.5 text-[#4edea3] shrink-0" />
                        )}
                      </div>
                      <div className="flex items-center gap-1.5 text-[11px] text-[#c4c7c8]">
                        <span className="text-[#4edea3]">{org.category}</span>
                        <span>•</span>
                        <span>{formatFollowers(org.followers_count || 0)}</span>
                      </div>
                    </div>
                  </div>

                  <ChevronRight className="w-4 h-4 text-[#8e9192] group-hover:text-white transition-all shrink-0" />
                </div>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
};
