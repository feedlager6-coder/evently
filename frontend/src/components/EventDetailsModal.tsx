import React, { useState, useEffect } from 'react';
import type { EventResponse } from '../types';
import { telegram } from '../services/telegram';
import { api } from '../services/api';
import { 
  Calendar, 
  MapPin, 
  Check, 
  ArrowLeft,
  Share2, 
  Ticket, 
  Heart,
  Edit,
  Send,
  Loader2,
  ShieldCheck,
  Compass,
  Lock,
  Handshake,
  Building2,
  X,
  ExternalLink,
  AlertCircle
} from 'lucide-react';
import { SafeAvatar } from './SafeAvatar';
import { TelegramIcon } from './TelegramIcon';

export function getAttendeesWord(count: number): string {
  const mod10 = count % 10;
  const mod100 = count % 100;
  if (mod100 >= 11 && mod100 <= 19) return 'человек идут';
  if (mod10 === 1) return 'человек идёт';
  if (mod10 >= 2 && mod10 <= 4) return 'человека идут';
  return 'человек идут';
}

export function getInterestedWord(count: number): string {
  const mod10 = count % 10;
  const mod100 = count % 100;
  if (mod100 >= 11 && mod100 <= 19) return 'хотят пойти';
  if (mod10 === 1) return 'хочет пойти';
  if (mod10 >= 2 && mod10 <= 4) return 'хотят пойти';
  return 'хотят пойти';
}

export function getCompanyMembersWord(count: number): string {
  const mod10 = count % 10;
  const mod100 = count % 100;
  if (mod100 >= 11 && mod100 <= 19) return 'человек ищут компанию';
  if (mod10 === 1) return 'человек ищет компанию';
  if (mod10 >= 2 && mod10 <= 4) return 'человека ищут компанию';
  return 'человек ищут компанию';
}

interface EventDetailsModalProps {
  event: EventResponse | null;
  isOpen: boolean;
  onClose: () => void;
  onToggleRsvp: (eventId: string, currentStatus: boolean) => Promise<void>;
  isRsvpLoading: boolean;
  onToggleInterest?: (eventId: string, currentStatus: boolean) => Promise<void>;
  isInterestLoading?: boolean;
  onOpenOrgModal?: (orgId: string, initialData?: { name?: string; avatar_url?: string; is_verified?: boolean; category?: string }) => void;
  onOpenCompanyModal?: (event: EventResponse) => void;
  isOrganizer?: boolean;
  onEditEvent?: (event: EventResponse) => void;
  onOpenBroadcastComposer?: (eventId: string, orgId?: string) => void;
  onOpenCreateOrg?: () => void;
  onOpenTicket?: (event: EventResponse) => void;
  onOpenScanner?: (event: EventResponse) => void;
}

export const EventDetailsModal: React.FC<EventDetailsModalProps> = ({
  event,
  isOpen,
  onClose,
  onToggleRsvp,
  isRsvpLoading,
  onToggleInterest,
  isInterestLoading = false,
  onOpenOrgModal,
  onOpenCompanyModal,
  isOrganizer = false,
  onEditEvent,
  onOpenBroadcastComposer,
  onOpenCreateOrg,
  onOpenTicket,
  onOpenScanner,
}) => {
  const [showBroadcastExplainer, setShowBroadcastExplainer] = useState(false);
  const [shareToast, setShareToast] = useState<string | null>(null);
  const [companyMembersCount, setCompanyMembersCount] = useState<number>(0);
  const [isCompanyOptedIn, setIsCompanyOptedIn] = useState<boolean>(false);

  const canEdit = Boolean(isOrganizer || event?.is_organizer);

  // Load companion search status
  useEffect(() => {
    if (isOpen && event) {
      api.getCompanyStatus(event.id)
        .then(st => {
          setCompanyMembersCount(st.active_members_count);
          setIsCompanyOptedIn(st.is_active);
        })
        .catch(() => {});
    }
  }, [isOpen, event]);

  const [isRendered, setIsRendered] = useState(isOpen);
  const [isAnimatingOut, setIsAnimatingOut] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setIsRendered(true);
      setIsAnimatingOut(false);
    } else if (isRendered) {
      setIsAnimatingOut(true);
      const timer = setTimeout(() => {
        setIsRendered(false);
        setIsAnimatingOut(false);
      }, 200);
      return () => clearTimeout(timer);
    }
  }, [isOpen, isRendered]);

  if (!isRendered || !event) return null;

  const eventDate = new Date(event.start_at);
  const isPast = eventDate.getTime() < Date.now();
  const isToday = eventDate.toDateString() === new Date().toDateString();

  const formattedDayOfWeek = eventDate.toLocaleDateString('ru-RU', {
    weekday: 'long',
  });
  const formattedDayAndMonth = eventDate.toLocaleDateString('ru-RU', {
    day: 'numeric',
    month: 'long',
  });
  const formattedShortDate = eventDate.toLocaleDateString('ru-RU', {
    day: 'numeric',
    month: 'numeric',
  });

  const formattedTime = eventDate.toLocaleTimeString('ru-RU', {
    hour: '2-digit',
    minute: '2-digit',
  });

  const formattedFullDate = eventDate.toLocaleDateString('ru-RU', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });

  const priceAmount = event.price_amount;
  const isFree = Boolean(event.is_free) || (priceAmount !== null && priceAmount !== undefined && Number(priceAmount) === 0);
  const priceText = isFree
    ? 'Бесплатно'
    : priceAmount !== null && priceAmount !== undefined
      ? `${Number(priceAmount) % 1 === 0 ? Number(priceAmount) : priceAmount} ₽`
      : 'Вход свободный';

  // System Share for Header: Web Share API -> Clipboard copy (for WhatsApp, VK, SMS)
  const handleSystemShare = async () => {
    telegram.hapticImpact('light');
    const botUsername = api.getBotUsername();
    const shareUrl = `https://t.me/${botUsername}/app?startapp=event_${event.id}`;
    const venueLabel = event.venue_name || (event.city_name ? `г. ${event.city_name}` : 'Локация в приложении');
    const shareMessage = `Пойдём вместе на «${event.title}»!\n\n🗓 ${formattedFullDate}\n📍 ${venueLabel}\n\nПосмотреть событие в Ivently:\n${shareUrl}`;

    if (navigator.share) {
      try {
        await navigator.share({
          title: `Пойдём вместе на «${event.title}»!`,
          text: `Пойдём вместе на «${event.title}»!\n\n🗓 ${formattedFullDate}\n📍 ${venueLabel}\n\nПосмотреть событие:`,
          url: shareUrl,
        });
        return;
      } catch (err: any) {
        if (err.name === 'AbortError') return;
      }
    }

    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(shareMessage);
      } else {
        const textArea = document.createElement('textarea');
        textArea.value = shareMessage;
        document.body.appendChild(textArea);
        textArea.select();
        document.execCommand('copy');
        document.body.removeChild(textArea);
      }
      setShareToast('Ссылка скопирована!');
      telegram.hapticSuccess();
      setTimeout(() => setShareToast(null), 2500);
    } catch (copyErr) {
      console.warn('Clipboard copy failed:', copyErr);
    }
  };

  // Telegram Native Share for Hero Card: opens Telegram share sheet with 'Избранное' at top
  const handleTelegramNativeShare = () => {
    telegram.hapticImpact('light');
    const botUsername = api.getBotUsername();
    const shareUrl = `https://t.me/${botUsername}/app?startapp=event_${event.id}`;
    const venueLabel = event.venue_name || (event.city_name ? `г. ${event.city_name}` : 'Локация в приложении');
    const shareText = `Пойдём вместе на «${event.title}»!\n🗓 ${formattedFullDate}\n📍 ${venueLabel}`;
    const telegramShareUrl = `https://t.me/share/url?url=${encodeURIComponent(shareUrl)}&text=${encodeURIComponent(shareText)}`;
    telegram.openTelegramLink(telegramShareUrl);
  };

  const handleGoingClick = async () => {
    if (isRsvpLoading || isInterestLoading) return;
    const isAttending = Boolean(event.is_attending);
    if (!isAttending) {
      telegram.hapticNotification('success');
    } else {
      telegram.hapticImpact('light');
    }
    await onToggleRsvp(event.id, isAttending);
  };

  const handleInterestedClick = async () => {
    if (isInterestLoading || isRsvpLoading || !onToggleInterest) return;
    const isInterested = Boolean(event.current_user_interested);
    if (!isInterested) {
      telegram.hapticNotification('success');
    } else {
      telegram.hapticImpact('light');
    }
    await onToggleInterest(event.id, isInterested);
  };

  return (
    <div
      className={`fixed inset-0 z-[60] flex flex-col bg-[#131315] text-[#e5e1e4] selection:bg-[#4edea3]/30 overflow-hidden ${
        isAnimatingOut
          ? 'opacity-0 translate-y-8 transition-all duration-200 ease-out pointer-events-none'
          : 'animate-modal-slide-up'
      }`}
      style={{ willChange: 'transform, opacity' }}
    >
      {/* Top Header Bar (Stitch Mobile Stack style) */}
      <header className="fixed top-0 inset-x-0 z-50 pt-safe bg-[#131315]/80 backdrop-blur-xl border-b border-white/5 shadow-[0_1px_12px_rgba(0,0,0,0.4)]">
        <div className="h-14 max-w-[480px] mx-auto px-4 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 min-w-0">
            <button
              onClick={() => {
                telegram.hapticImpact('light');
                onClose();
              }}
              className="w-10 h-10 flex items-center justify-center rounded-full text-[#c4c7c8] hover:text-white active:scale-95 transition-all"
              aria-label="Назад"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
            <h1 className="text-base font-semibold text-white tracking-tight truncate pl-1">
              Детали события
            </h1>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleSystemShare}
              className="w-10 h-10 rounded-full bg-white/5 hover:bg-white/10 flex items-center justify-center text-[#c4c7c8] hover:text-white active:scale-95 transition-all"
              aria-label="Системный шеринг"
              title="Поделиться через другие приложения"
            >
              <Share2 className="w-4 h-4" />
            </button>
          </div>
        </div>
      </header>

      {/* Share Toast */}
      {shareToast && (
        <div className="fixed top-16 inset-x-0 z-50 flex justify-center pointer-events-none px-4">
          <div className="px-4 py-2 rounded-full bg-[#10b981] text-[#00311f] font-semibold text-xs shadow-lg animate-bounce">
            {shareToast}
          </div>
        </div>
      )}

      {/* Main Scrollable Body */}
      <main className="flex-1 overflow-y-auto custom-scrollbar w-full max-w-[480px] mx-auto pt-16 pb-[calc(7rem+var(--safe-bottom,0px))] px-4 space-y-5">
        {/* Hero Stage (320px rounded-3xl with scrim & top badges) */}
        <div className="relative w-full rounded-3xl overflow-hidden bg-[#201f22] shadow-xl">
          <div className="w-full h-80 relative">
            <img
              src={event.cover_image_url && !event.cover_image_url.includes('photo-1520523839898-50712140e698') ? event.cover_image_url : '/covers/default_event.jpg'}
              alt={event.title}
              loading="eager"
              onError={(e) => {
                (e.currentTarget as HTMLImageElement).src = '/covers/default_event.jpg';
              }}
              className="w-full h-full object-cover"
            />
            {/* Gradient Scrim for Readability */}
            <div className="absolute inset-0 bg-gradient-to-t from-[#131315] via-[#131315]/40 to-transparent" />

            {/* Floating Top Badges on Cover */}
            <div className="absolute top-4 inset-x-4 flex items-center justify-between pointer-events-auto">
              <div className="flex items-center gap-2">
                <span className={`px-2.5 py-1 rounded-full backdrop-blur-md text-[11px] tracking-tight shadow-md font-medium ${
                  isPast 
                    ? 'bg-neutral-800/80 text-neutral-400' 
                    : isToday 
                    ? 'bg-emerald-500/85 text-black font-bold' 
                    : 'bg-[#0e0e10]/75 text-white'
                }`}>
                  {isPast ? 'Завершено' : isToday ? 'Сегодня' : 'Скоро'}
                </span>
                <span className="px-2.5 py-1 rounded-full bg-[#0e0e10]/75 backdrop-blur-md text-[#c4c7c8] font-medium text-[11px] tracking-tight shadow-md">
                  {formattedShortDate}
                </span>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={handleTelegramNativeShare}
                  className="w-10 h-10 rounded-full bg-[#0e0e10]/75 backdrop-blur-md flex items-center justify-center text-[#c4c7c8] hover:text-[#4edea3] active:scale-95 transition-all shadow-md"
                  aria-label="Поделиться в Telegram"
                  title="Поделиться в Telegram"
                >
                  <TelegramIcon className="w-5 h-5 text-white" />
                </button>
                {onToggleInterest && (
                  <button
                    onClick={handleInterestedClick}
                    disabled={isInterestLoading}
                    className="w-10 h-10 rounded-full bg-[#0e0e10]/75 backdrop-blur-md flex items-center justify-center text-[#c4c7c8] hover:text-[#4edea3] active:scale-95 transition-all shadow-md"
                    aria-label="В закладки"
                  >
                    <Heart
                      className={`w-4 h-4 transition-transform ${
                        event.current_user_interested ? 'fill-[#4edea3] text-[#4edea3] scale-110' : ''
                      }`}
                    />
                  </button>
                )}
              </div>
            </div>

            {/* Bottom Hero Scrim Information */}
            <div className="absolute bottom-4 inset-x-4 flex items-end justify-between">
              <div className="flex flex-col gap-1">
                <span className="px-3 py-1 self-start rounded-full bg-[#2a2a2c]/85 backdrop-blur-md text-[#4edea3] font-semibold text-xs">
                  {event.category_name}
                </span>
              </div>
              <div className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-full bg-[#00a572] text-[#00311f] font-bold text-sm shadow-lg">
                <Ticket className="w-4 h-4" />
                <span>{priceText}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Event Headline */}
        <div className="flex flex-col space-y-3 px-1">
          <h2 className="text-xl sm:text-2xl font-bold text-white tracking-tight leading-snug">
            {event.title}
          </h2>

          <div className="grid grid-cols-1 gap-2.5">
            {/* Date & Time Row Card */}
            <div className="flex items-center gap-3.5 p-3.5 rounded-2xl bg-[#1c1b1e] shadow-sm">
              <div className="w-11 h-11 rounded-xl bg-[#2a2a2c] flex items-center justify-center text-[#4edea3] shrink-0">
                <Calendar className="w-5 h-5" />
              </div>
              <div className="flex flex-col min-w-0">
                <span className="text-white font-semibold text-sm truncate capitalize">
                  {formattedDayOfWeek}, {formattedDayAndMonth}
                </span>
                <span className="text-[#c4c7c8] text-xs">
                  {formattedTime} • Местное время
                </span>
              </div>
            </div>

            {/* Location Card & Route */}
            <div className="flex flex-col rounded-2xl bg-[#1c1b1e] overflow-hidden shadow-sm">
              <div className="p-3.5 flex items-center justify-between gap-3">
                <div className="flex items-center gap-3.5 min-w-0">
                  <div className="w-11 h-11 rounded-xl bg-[#2a2a2c] flex items-center justify-center text-[#4edea3] shrink-0">
                    <MapPin className="w-5 h-5" />
                  </div>
                  <div className="flex flex-col min-w-0">
                    <span className="text-white font-semibold text-sm truncate">
                      {event.venue_name || 'Локация'}
                    </span>
                    <span className="text-[#c4c7c8] text-xs truncate">
                      {event.address ? `${event.address}, ` : ''}{event.city_name || ''}
                    </span>
                  </div>
                </div>
                <button
                  onClick={() => {
                    telegram.hapticImpact('light');
                    const query = encodeURIComponent(`${event.venue_name || ''} ${event.address || ''} ${event.city_name || ''}`.trim());
                    telegram.openLink(`https://yandex.ru/maps/?text=${query}`);
                  }}
                  className="px-3.5 py-1.5 rounded-full bg-[#2a2a2c] hover:bg-[#353437] text-white text-xs font-semibold shrink-0 active:scale-95 transition-all"
                  type="button"
                >
                  Маршрут
                </button>
              </div>

              {/* Navigator Strip */}
              <div 
                onClick={() => {
                  telegram.hapticImpact('light');
                  const query = encodeURIComponent(`${event.venue_name || ''} ${event.address || ''} ${event.city_name || ''}`.trim());
                  telegram.openLink(`https://yandex.ru/maps/?text=${query}`);
                }}
                className="w-full h-16 bg-[#201f22] relative flex items-center justify-center cursor-pointer hover:bg-[#262529] transition-colors border-t border-white/5"
              >
                <div className="px-3 py-1 rounded-full bg-[#0e0e10]/80 backdrop-blur-md text-[#c4c7c8] text-[11px] font-bold flex items-center gap-1.5 shadow-sm">
                  <Compass className="w-3.5 h-3.5 text-[#4edea3]" />
                  <span>Открыть в навигаторе</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Organizer Entity Card */}
        {event.source_type === 'external' ? (
          <div className="flex items-center justify-between p-3.5 rounded-2xl bg-[#1c1b1e] shadow-sm border border-white/5">
            <div className="flex items-center gap-3 min-w-0">
              <div className="w-12 h-12 rounded-full overflow-hidden bg-[#2a2a2c] shrink-0 border border-white/10 flex items-center justify-center text-white/70">
                <Building2 className="w-6 h-6 text-[#4edea3]" />
              </div>
              <div className="flex flex-col min-w-0">
                <span className="text-white font-semibold text-sm truncate">
                  {event.venue_name || 'Городская афиша'}
                </span>
                <span className="text-[#8e9192] text-xs">
                  Официальная площадка • Городская афиша
                </span>
              </div>
            </div>
          </div>
        ) : event.organization_name ? (
          <div 
            onClick={() => {
              if (onOpenOrgModal && event.organization_id) {
                telegram.hapticImpact('light');
                onOpenOrgModal(event.organization_id, {
                  name: event.organization_name,
                  avatar_url: event.organization_avatar_url,
                  is_verified: event.organization_is_verified,
                  category: event.organization_category,
                });
              }
            }}
            className="flex items-center justify-between p-3.5 rounded-2xl bg-[#1c1b1e] hover:bg-[#201f22] transition-colors cursor-pointer shadow-sm"
          >
            <div className="flex items-center gap-3 min-w-0">
              <div className="w-12 h-12 rounded-full overflow-hidden bg-[#2a2a2c] shrink-0 border border-white/10">
                <SafeAvatar
                  src={event.organization_avatar_url}
                  name={event.organization_name}
                  type="org"
                  sizeClassName="w-12 h-12"
                  className="rounded-full"
                />
              </div>
              <div className="flex flex-col min-w-0">
                <div className="flex items-center gap-1">
                  <span className="text-white font-semibold text-sm truncate">
                    {event.organization_name}
                  </span>
                  <ShieldCheck className="w-4 h-4 text-[#4edea3] shrink-0" />
                </div>
                <span className="text-[#c4c7c8] text-xs">
                  Организатор события
                </span>
              </div>
            </div>
            <button
              onClick={(e) => {
                e.stopPropagation();
                if (onOpenOrgModal && event.organization_id) {
                  telegram.hapticImpact('light');
                  onOpenOrgModal(event.organization_id, {
                    name: event.organization_name,
                    avatar_url: event.organization_avatar_url,
                    is_verified: event.organization_is_verified,
                    category: event.organization_category,
                  });
                }
              }}
              className="px-4 py-2 rounded-full bg-[#2a2a2c] hover:bg-[#353437] text-white text-xs font-semibold active:scale-95 transition-all shrink-0"
              type="button"
            >
              В профиль
            </button>
          </div>
        ) : (
          <div className="flex items-center justify-between p-3.5 rounded-2xl bg-[#1c1b1e] shadow-sm border border-white/5">
            <div className="flex items-center gap-3 min-w-0">
              <div className="w-12 h-12 rounded-full overflow-hidden bg-[#2a2a2c] shrink-0 border border-white/10">
                <SafeAvatar
                  name={(event as any).organizer_name || 'Автор'}
                  type="user"
                  sizeClassName="w-12 h-12"
                  className="rounded-full"
                />
              </div>
              <div className="flex flex-col min-w-0">
                <div className="flex items-center gap-1">
                  <span className="text-white font-semibold text-sm truncate">
                    {(event as any).organizer_name || 'Автор события'}
                  </span>
                </div>
                <span className="text-[#8e9192] text-xs">
                  Частный организатор
                </span>
              </div>
            </div>
            {Boolean((event as any).organizer_contact_url || (event as any).organizer_username) && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  telegram.hapticImpact('light');
                  const url = (event as any).organizer_contact_url || `https://t.me/${(event as any).organizer_username?.replace(/^@/, '')}`;
                  telegram.openTelegramLink(url);
                }}
                className="px-3.5 py-2 rounded-full bg-[#2a2a2c] hover:bg-[#353437] text-[#4edea3] text-xs font-semibold active:scale-95 transition-all shrink-0 flex items-center gap-1.5"
                type="button"
              >
                <span>Написать</span>
              </button>
            )}
          </div>
        )}

        {/* Companion Discovery Feature ("Найти компанию") */}
        {!isPast && (
          <div className="p-4 rounded-3xl bg-[#1c1b1e] relative overflow-hidden shadow-md space-y-3.5">
            {/* Ambient subtle illumination orb */}
            <div className="absolute -right-10 -top-10 w-36 h-36 rounded-full bg-[#10b981]/10 blur-2xl pointer-events-none" />

            <div className="flex items-start justify-between gap-3 relative z-10">
              <div className="flex items-center gap-2.5">
                <div className="w-9 h-9 rounded-xl bg-[#10b981]/15 text-[#4edea3] flex items-center justify-center shrink-0">
                  <Handshake className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-white font-semibold text-base">
                    Найти компанию
                  </h3>
                  <p className="text-[#4edea3] text-xs font-medium">
                    {companyMembersCount > 0
                      ? `${companyMembersCount} ${getCompanyMembersWord(companyMembersCount)}`
                      : 'Познакомьтесь с теми, кто тоже идёт'}
                  </p>
                </div>
              </div>
            </div>

            <p className="text-[#c4c7c8] text-xs leading-relaxed relative z-10">
              Не с кем пойти? Активируйте приватный поиск компаньонов. Ваш профиль остаётся скрытым до момента взаимного согласия.
            </p>

            <div className="flex flex-col gap-2 relative z-10">
              <button
                onClick={() => {
                  telegram.hapticImpact('light');
                  onOpenCompanyModal?.(event);
                }}
                className="w-full py-3 px-4 rounded-full bg-[#2a2a2c] hover:bg-[#353437] text-white text-xs font-bold flex items-center justify-center gap-2 active:scale-95 transition-all shadow-sm"
                type="button"
              >
                <Handshake className="w-4 h-4 text-[#4edea3]" />
                <span>{isCompanyOptedIn ? 'Моя анкета компании' : 'Активировать поиск компании'}</span>
              </button>

              <div className="flex items-center justify-center gap-1.5 text-[#8e9192] text-[11px] pt-0.5">
                <Lock className="w-3.5 h-3.5" />
                <span>Приватность защищена: Telegram ID не раскрывается</span>
              </div>
            </div>
          </div>
        )}

        {/* About Event Description */}
        <div className="flex flex-col space-y-3 p-4 rounded-3xl bg-[#1c1b1e] shadow-sm">
          <h3 className="text-white font-semibold text-base">О событии</h3>
          <p className="text-[#c4c7c8] text-xs leading-relaxed whitespace-pre-line">
            {event.description || 'Описание мероприятия скоро появится.'}
          </p>

          {/* Highlights Badges */}
          <div className="flex flex-wrap gap-2 pt-1">
            <span className="px-3 py-1.5 rounded-full bg-[#2a2a2c] text-[#e5e1e4] text-xs font-medium flex items-center gap-1.5">
              <span>🎟️</span>
              <span>{priceText}</span>
            </span>
            <span className="px-3 py-1.5 rounded-full bg-[#2a2a2c] text-[#e5e1e4] text-xs font-medium flex items-center gap-1.5">
              <span>👥</span>
              <span>{event.attendee_count} {getAttendeesWord(event.attendee_count)}</span>
            </span>
            {event.interest_count > 0 && (
              <span className="px-3 py-1.5 rounded-full bg-[#2a2a2c] text-[#e5e1e4] text-xs font-medium flex items-center gap-1.5">
                <span>♡</span>
                <span>{event.interest_count} {getInterestedWord(event.interest_count)}</span>
              </span>
            )}
          </div>

          {/* VPN hint for external sources */}
          {event.source_type === 'external' && event.source_url?.includes('culture.ru') && (
            <div className="pt-2 flex items-center gap-1.5 text-[#8e9192] text-[11px] border-t border-white/5">
              <AlertCircle className="w-3.5 h-3.5 shrink-0 text-[#f59e0b]" />
              <span>Если сайт билетной кассы не загружается, временно отключите VPN</span>
            </div>
          )}
        </div>

        {/* Broadcast Entry for Organizers */}
        {canEdit && (
          <div className="p-4 rounded-2xl bg-[#1c1b1e] border border-white/10 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-[#4edea3] uppercase tracking-wide">
                Инструменты организатора
              </span>
            </div>
            <div className={`grid ${onOpenScanner ? 'grid-cols-3' : 'grid-cols-2'} gap-2`}>
              <button
                type="button"
                onClick={() => {
                  telegram.hapticImpact('light');
                  onEditEvent?.(event);
                }}
                className="py-2.5 px-2 rounded-xl bg-[#2a2a2c] hover:bg-[#353437] text-white text-xs font-semibold flex items-center justify-center gap-1.5 transition-all active:scale-95"
              >
                <Edit className="w-3.5 h-3.5" />
                <span>Изменить</span>
              </button>
              {onOpenScanner && (
                <button
                  type="button"
                  onClick={() => {
                    telegram.hapticImpact('light');
                    onOpenScanner(event);
                  }}
                  className="py-2.5 px-2 rounded-xl bg-[#2a2a2c] hover:bg-[#353437] text-white text-xs font-semibold flex items-center justify-center gap-1.5 transition-all active:scale-95"
                >
                  <Ticket className="w-3.5 h-3.5 text-[#10b981]" />
                  <span>Сканер</span>
                </button>
              )}
              {onOpenBroadcastComposer && (
                <button
                  type="button"
                  onClick={() => {
                    telegram.hapticImpact('light');
                    if (!event.organization_id) {
                      setShowBroadcastExplainer(true);
                    } else {
                      onOpenBroadcastComposer(event.id, event.organization_id);
                    }
                  }}
                  className="py-2.5 px-2 rounded-xl bg-[#2a2a2c] hover:bg-[#353437] text-white text-xs font-semibold flex items-center justify-center gap-1.5 transition-all active:scale-95"
                >
                  <Send className="w-3.5 h-3.5 text-[#4edea3]" />
                  <span>Рассылка</span>
                </button>
              )}
            </div>

            {/* Gamified Nudge Card for Bookmarkers */}
            {Boolean(event.interest_count && event.interest_count > 0 && onOpenBroadcastComposer) && (
              <div className="p-3 rounded-2xl bg-emerald-500/10 border border-emerald-500/25 flex flex-col gap-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-emerald-400 flex items-center gap-1.5">
                    <span>🔥</span>
                    <span>{event.interest_count} в закладках «Хочу пойти»</span>
                  </span>
                </div>
                <p className="text-[11px] text-zinc-300 leading-snug">
                  Отправьте персональный анонс или напоминание прямо в Telegram, чтобы превратить интерес в продажи билетов.
                </p>
                <button
                  type="button"
                  onClick={() => {
                    telegram.hapticImpact('light');
                    if (!event.organization_id) {
                      setShowBroadcastExplainer(true);
                    } else {
                      onOpenBroadcastComposer?.(event.id, event.organization_id);
                    }
                  }}
                  className="w-full py-2 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-black font-extrabold text-xs flex items-center justify-center gap-1.5 transition active:scale-95 shadow-md"
                >
                  <Send className="w-3.5 h-3.5" />
                  <span>Отправить анонс в Telegram ↗</span>
                </button>
              </div>
            )}
          </div>
        )}
      </main>

      {/* Sticky Bottom Optical Glass Action Dock (Matching Stitch Obsidian Optical) */}
      <div className="fixed dock-bottom inset-x-0 mx-auto w-full max-w-[480px] px-4 z-50 pointer-events-none">
        <div className="p-1.5 rounded-full bg-[#0e0e10]/90 backdrop-blur-2xl shadow-[0_16px_40px_rgba(0,0,0,0.85)] border border-white/12 flex items-center justify-between gap-2 pointer-events-auto">
          {event.source_type === 'external' ? (
            <>
              {/* External Event: Single "Хочу пойти" / "В закладках ✓" button */}
              <button
                onClick={handleInterestedClick}
                disabled={isInterestLoading || isPast || !onToggleInterest}
                type="button"
                className={`flex-1 h-11 px-4 rounded-full text-xs font-bold flex items-center justify-center gap-1.5 transition-all active:scale-95 shadow-md ${
                  event.current_user_interested
                    ? 'bg-[#2a2a2c] text-[#4edea3] border border-[#10b981]/40'
                    : 'bg-[#2a2a2c] text-white hover:bg-[#353437]'
                } disabled:opacity-50`}
              >
                {isInterestLoading ? (
                  <Loader2 className="w-4 h-4 animate-spin text-[#4edea3]" />
                ) : (
                  <Heart className={`w-4 h-4 ${event.current_user_interested ? 'fill-[#4edea3] text-[#4edea3]' : 'text-white'}`} />
                )}
                <span className="truncate">
                  {event.current_user_interested ? 'В закладках ✓' : 'Хочу пойти'}
                </span>
              </button>

              {/* External Event: Ticket / Website button */}
              {event.source_url && (
                <button
                  onClick={() => {
                    telegram.hapticImpact('light');
                    telegram.openLink(event.source_url!);
                  }}
                  disabled={isPast}
                  className="flex-1 h-11 px-4 rounded-full bg-white text-black font-bold text-xs flex items-center justify-center gap-1.5 shrink-0 active:scale-95 transition-all shadow-md disabled:opacity-50"
                  type="button"
                >
                  <ExternalLink className="w-4 h-4 text-black" />
                  <span className="truncate">
                    {isFree ? 'Подробнее на сайте' : 'Билеты на сайте'}
                  </span>
                </button>
              )}
            </>
          ) : (
            <>
              {/* Mutually Exclusive Intent Segmented Toggle Group */}
              <div 
                aria-label="Статус участия" 
                className="flex items-center bg-[#2a2a2c]/80 p-1 rounded-full flex-1 min-w-0" 
                role="radiogroup"
              >
                {/* Radio Option 1: "Я иду" */}
                <button
                  onClick={handleGoingClick}
                  disabled={isRsvpLoading || isInterestLoading || isPast}
                  aria-checked={Boolean(event.is_attending)}
                  role="radio"
                  type="button"
                  className={`flex-1 py-2 px-3 rounded-full text-xs font-bold flex items-center justify-center gap-1.5 transition-all active:scale-95 ${
                    event.is_attending
                      ? 'bg-white text-black shadow-md'
                      : 'text-[#c4c7c8] hover:text-white'
                  } disabled:opacity-50`}
                >
                  {isRsvpLoading ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <Check className={`w-3.5 h-3.5 ${event.is_attending ? 'text-black' : 'text-[#c4c7c8]'}`} />
                  )}
                  <span className="truncate">Я иду</span>
                </button>

                {/* Radio Option 2: "Хочу пойти" */}
                <button
                  onClick={handleInterestedClick}
                  disabled={isInterestLoading || isRsvpLoading || isPast || !onToggleInterest}
                  aria-checked={Boolean(event.current_user_interested)}
                  role="radio"
                  type="button"
                  className={`flex-1 py-2 px-3 rounded-full text-xs font-bold flex items-center justify-center gap-1.5 transition-all active:scale-95 ${
                    event.current_user_interested
                      ? 'bg-white text-black shadow-md'
                      : 'text-[#c4c7c8] hover:text-white'
                  } disabled:opacity-50`}
                >
                  {isInterestLoading ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <Heart className={`w-3.5 h-3.5 ${event.current_user_interested ? 'fill-black text-black' : 'text-[#c4c7c8]'}`} />
                  )}
                  <span className="truncate">Хочу</span>
                </button>
              </div>

              {/* Ticket / Registration Action Button */}
              {(() => {
                const ticketUrl = event.source_url || (event as any).registration_url || (event as any).ticket_link;
                
                // 1. If user is already attending, show dedicated "Мой билет" QR trigger
                if (event.is_attending) {
                  return (
                    <button
                      onClick={() => {
                        telegram.hapticImpact('light');
                        if (onOpenTicket) {
                          onOpenTicket(event);
                        }
                      }}
                      className="h-11 px-4 rounded-full bg-[#10b981] text-black font-bold text-xs flex items-center justify-center gap-1.5 shrink-0 active:scale-95 transition-all shadow-md"
                      type="button"
                    >
                      <Ticket className="w-4 h-4 text-black" />
                      <span>Мой билет</span>
                    </button>
                  );
                }

                // 2. If event has external ticket/registration URL
                if (ticketUrl) {
                  return (
                    <button
                      onClick={() => {
                        telegram.hapticImpact('light');
                        telegram.openLink(ticketUrl);
                      }}
                      disabled={isPast}
                      className="h-11 px-4 rounded-full bg-white text-black font-bold text-xs flex items-center justify-center gap-1.5 shrink-0 active:scale-95 transition-all shadow-md disabled:opacity-50"
                      type="button"
                    >
                      <Ticket className="w-4 h-4" />
                      <span>{isFree ? 'Регистрация' : 'Купить билет'}</span>
                    </button>
                  );
                }

                // 3. Otherwise, for standard in-app events, the segmented control spans cleanly without duplication
                return null;
              })()}
            </>
          )}
        </div>
      </div>

      {/* Broadcast Information Modal for Solo Creators */}
      {showBroadcastExplainer && (
        <div className="fixed inset-0 z-[100] bg-black/80 backdrop-blur-md flex items-end sm:items-center justify-center p-4">
          <div className="w-full max-w-sm rounded-[28px] bg-[#141417] border border-white/10 p-5 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between">
              <div className="w-10 h-10 rounded-2xl bg-[#10b981]/15 text-[#4edea3] flex items-center justify-center border border-[#10b981]/25">
                <Send className="w-5 h-5" />
              </div>
              <button
                onClick={() => setShowBroadcastExplainer(false)}
                type="button"
                className="w-8 h-8 rounded-full bg-white/5 flex items-center justify-center text-neutral-400 hover:text-white"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-1.5">
              <h3 className="text-base font-bold text-white tracking-tight">
                Рассылки доступны для брендов
              </h3>
              <p className="text-xs text-neutral-400 leading-relaxed">
                В Telegram рассылки отправляются подписчикам организации. Чтобы собирать базу постоянных подписчиков и делать анонсы в личные сообщения Telegram, создайте организацию и привяжите к ней событие.
              </p>
            </div>

            <div className="p-3 rounded-xl bg-white/[0.03] border border-white/5 space-y-2 text-xs text-neutral-300">
              <div className="flex items-start gap-2">
                <span className="text-[#4edea3] font-bold">✓</span>
                <span>Анонсы подписчикам прямо в Telegram-бот</span>
              </div>
              <div className="flex items-start gap-2">
                <span className="text-[#4edea3] font-bold">✓</span>
                <span>База постоянных гостей и аналитика переходов</span>
              </div>
            </div>

            <div className="space-y-2 pt-1">
              <button
                type="button"
                onClick={() => {
                  telegram.hapticImpact('medium');
                  setShowBroadcastExplainer(false);
                  onClose();
                  onOpenCreateOrg?.();
                }}
                className="w-full py-3 rounded-full bg-[#10b981] hover:bg-[#059669] text-[#00311f] font-bold text-xs active:scale-95 transition shadow-lg flex items-center justify-center gap-1.5"
              >
                <Building2 className="w-4 h-4" />
                <span>Создать организацию</span>
              </button>
              <button
                type="button"
                onClick={() => setShowBroadcastExplainer(false)}
                className="w-full py-2.5 rounded-full bg-white/5 text-neutral-400 hover:text-white font-medium text-xs active:scale-95 transition"
              >
                Понятно
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
