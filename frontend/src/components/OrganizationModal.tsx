import React, { useState, useEffect, useCallback } from 'react';
import type { OrganizationResponse, EventSummary } from '../types';
import { api } from '../services/api';
import { telegram } from '../services/telegram';
import {
  ArrowLeft,
  Share2,
  Bell,
  Send,
  Ticket,
  Info,
  MapPin,
  Sparkles,
  Check,
  ExternalLink,
  ShieldCheck,
  Volume2,
  Loader2,
  AlertCircle,
  Bookmark,
  ArrowRight,
  ChevronRight,
  Edit3,
  Plus,
  Clock
} from 'lucide-react';
import { SafeAvatar } from './SafeAvatar';
import { SafeImage } from './SafeImage';

interface OrganizationModalProps {
  orgIdOrSlug: string | null;
  initialData?: {
    name?: string;
    avatar_url?: string;
    logo_url?: string;
    is_verified?: boolean;
    category?: string;
  } | null;
  isOpen: boolean;
  onClose: () => void;
  onEventClick: (event: EventSummary) => void;
  onOpenCreateEvent?: (orgId: string) => void;
  onEditOrg?: (org: OrganizationResponse) => void;
  onSubscriptionChanged?: () => void;
  onToggleInterest?: (eventId: string) => void;
}

export function getFollowersWord(count: number): string {
  const mod10 = count % 10;
  const mod100 = count % 100;
  if (mod100 >= 11 && mod100 <= 19) {
    return 'подписчиков';
  }
  if (mod10 === 1) {
    return 'подписчик';
  }
  if (mod10 >= 2 && mod10 <= 4) {
    return 'подписчика';
  }
  return 'подписчиков';
}

export function formatFollowers(count: number): string {
  return `${count} ${getFollowersWord(count)}`;
}

export const OrganizationModal: React.FC<OrganizationModalProps> = ({
  orgIdOrSlug,
  initialData,
  isOpen,
  onClose,
  onEventClick,
  onOpenCreateEvent,
  onEditOrg,
  onSubscriptionChanged,
  onToggleInterest,
}) => {
  const [org, setOrg] = useState<OrganizationResponse | null>(null);
  const [events, setEvents] = useState<EventSummary[]>([]);
  const [activeTab, setActiveTab] = useState<'afisha' | 'about'>('afisha');
  const [isLoading, setIsLoading] = useState(false);
  const [isSubscribing, setIsSubscribing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [bookmarkedEventIds, setBookmarkedEventIds] = useState<Record<string, boolean>>({});

  const loadData = useCallback(async () => {
    if (!orgIdOrSlug) return;
    try {
      setIsLoading(true);
      setError(null);
      const orgData = await api.getOrganization(orgIdOrSlug);
      setOrg(orgData);

      const eventsData = await api.getOrganizationEvents(orgData.id);
      setEvents(eventsData);
      setBookmarkedEventIds(
        eventsData.reduce((acc, ev) => ({
          ...acc,
          [ev.id]: Boolean(ev.current_user_interested || (ev as any).is_interested || (ev as any).is_bookmarked),
        }), {})
      );
    } catch (err: any) {
      console.error('Failed to load organization:', err);
      setError(err.message || 'Не удалось загрузить данные организации');
    } finally {
      setIsLoading(false);
    }
  }, [orgIdOrSlug]);

  useEffect(() => {
    if (isOpen && orgIdOrSlug) {
      if (initialData) {
        setOrg({
          id: orgIdOrSlug,
          name: initialData.name || '',
          slug: orgIdOrSlug,
          category: initialData.category || 'Организатор',
          avatar_url: initialData.avatar_url || initialData.logo_url || null,
          is_verified: Boolean(initialData.is_verified),
          status: 'active',
          follower_count: 0,
          created_at: new Date().toISOString(),
          is_following: false,
        } as unknown as OrganizationResponse);
      }
      loadData();
      setActiveTab('afisha');
    } else {
      setOrg(null);
      setEvents([]);
      setError(null);
    }
  }, [isOpen, orgIdOrSlug, loadData, initialData]);

  if (!isOpen) return null;

  const handleToggleSubscribe = async () => {
    if (!org || isSubscribing || org.is_owner) return;
    try {
      setIsSubscribing(true);
      telegram.hapticImpact('medium');

      if (org.is_subscribed) {
        const res = await api.unsubscribeOrganization(org.id);
        setOrg((prev) =>
          prev
            ? {
                ...prev,
                is_subscribed: res.is_subscribed,
                followers_count: res.followers_count,
              }
            : null
        );
        telegram.hapticImpact('light');
      } else {
        telegram.ensureWriteAccess().then((allowed) => {
          if (allowed) api.setNotificationsPermission(true).catch(() => {});
        }).catch(() => {});
        const res = await api.subscribeOrganization(org.id);
        setOrg((prev) =>
          prev
            ? {
                ...prev,
                is_subscribed: res.is_subscribed,
                followers_count: res.followers_count,
              }
            : null
        );
        telegram.hapticSuccess();
      }
      onSubscriptionChanged?.();
    } catch (err: any) {
      telegram.hapticError();
      await telegram.showAlert(err.message || 'Ошибка обновления подписки');
    } finally {
      setIsSubscribing(false);
    }
  };

  const handleShare = async () => {
    if (!org) return;
    telegram.hapticImpact('light');
    const botUsername = api.getBotUsername();
    const shareUrl = `https://t.me/${botUsername}?startapp=org_${org.id}`;
    const shareText = `🏛️ ${org.name} (${org.category})\nПодписывайтесь на события в Ivently:`;

    let shared = false;
    if (navigator.share) {
      try {
        await navigator.share({
          title: `${org.name} — Ivently`,
          text: shareText,
          url: shareUrl,
        });
        shared = true;
      } catch (err: any) {
        if (err.name === 'AbortError') return;
      }
    }

    if (!shared) {
      try {
        if (navigator.clipboard && navigator.clipboard.writeText) {
          await navigator.clipboard.writeText(shareUrl);
        } else {
          const textArea = document.createElement('textarea');
          textArea.value = shareUrl;
          document.body.appendChild(textArea);
          textArea.select();
          document.execCommand('copy');
          document.body.removeChild(textArea);
        }
        setCopied(true);
        telegram.hapticSuccess();
        setTimeout(() => setCopied(false), 2500);
      } catch (copyErr) {
        console.warn('Clipboard copy failed:', copyErr);
      }
    }
  };

  const handleOpenContact = async () => {
    if (!org) return;
    telegram.hapticImpact('light');
    let target = org.social_link || '';
    if (!target && org.website) {
      target = org.website;
    }
    if (target) {
      const url = target.startsWith('http') ? target : `https://${target.replace(/^@/, 't.me/')}`;
      telegram.openLink(url);
    } else {
      await telegram.showAlert('Контакты организации уточняются');
    }
  };

  const handleToggleBookmark = async (e: React.MouseEvent, eventId: string) => {
    e.stopPropagation();
    telegram.hapticImpact('light');
    const wasBookmarked = Boolean(bookmarkedEventIds[eventId]);
    setBookmarkedEventIds((prev) => ({
      ...prev,
      [eventId]: !wasBookmarked,
    }));
    try {
      if (wasBookmarked) {
        await api.removeInterest(eventId);
      } else {
        await api.addInterest(eventId);
      }
      onToggleInterest?.(eventId);
    } catch (err: any) {
      // rollback
      setBookmarkedEventIds((prev) => ({
        ...prev,
        [eventId]: wasBookmarked,
      }));
      await telegram.showAlert(err?.message || 'Ошибка обновления закладки');
    }
  };

  const openRouteInYandexMaps = () => {
    if (!org) return;
    telegram.hapticImpact('light');
    const query = org.address ? `${org.city_name || ''} ${org.address}` : org.name;
    const url = `https://yandex.ru/maps/?text=${encodeURIComponent(query)}`;
    telegram.openLink(url);
  };

  const now = new Date();
  const upcomingEvents = events.filter((e) => new Date(e.start_at) >= now);
  const pastEvents = events.filter((e) => new Date(e.start_at) < now);

  const renderEventCard = (event: EventSummary, isPast: boolean) => {
    const eventDate = new Date(event.start_at);
    const formattedDate = eventDate.toLocaleDateString('ru-RU', {
      day: 'numeric',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
    }).toUpperCase();

    const isFree = Boolean(event.is_free) || (event.price_amount !== null && event.price_amount !== undefined && Number(event.price_amount) === 0);
    const priceAmount = event.price_amount;
    const priceFormatted = !isFree && priceAmount ? `${Number(priceAmount)} ₽` : 'Бесплатно';
    const isBookmarked = bookmarkedEventIds[event.id];

    return (
      <article
        key={event.id}
        onClick={() => {
          telegram.hapticImpact('light');
          onClose();
          onEventClick(event);
        }}
        className={`relative overflow-hidden rounded-[24px] bg-[#141417] border border-white/5 shadow-[0_12px_28px_rgba(0,0,0,0.5)] transition-all active:scale-[0.99] cursor-pointer ${
          isPast ? 'opacity-80' : ''
        }`}
      >
        {/* Cover Image 16:9 */}
        <div className="relative h-48 w-full overflow-hidden bg-[#1a1a1f]">
          <SafeImage
            src={event.cover_image_url}
            alt={event.title}
            className={`w-full h-full object-cover ${isPast ? 'grayscale-[20%]' : ''}`}
          />
          <div className="absolute inset-0 bg-gradient-to-t from-[#141417] via-[#141417]/30 to-transparent" />

          {/* Top Overlays: Date chip on left, Bookmark icon on right */}
          <div className="absolute top-3 left-3 flex items-center gap-1.5">
            <span className="px-3 py-1 rounded-full bg-[#08080A]/85 backdrop-blur-md text-white font-bold text-[11px] border border-white/10 shadow-sm">
              {formattedDate}
            </span>
            {isPast && (
              <span className="px-2.5 py-1 rounded-full bg-zinc-900/95 text-zinc-100 font-bold text-[11px] border border-white/30 shadow-lg backdrop-blur-md inline-flex items-center gap-1">
                <Clock className="w-3 h-3 text-zinc-300" />
                Завершено
              </span>
            )}
          </div>

          <button
            onClick={(e) => handleToggleBookmark(e, event.id)}
            type="button"
            className="w-8 h-8 rounded-full bg-[#08080A]/70 backdrop-blur-md border border-white/10 flex items-center justify-center text-white absolute top-3 right-3 active:scale-90 transition-transform"
            title="В закладки"
          >
            <Bookmark
              className={`w-4 h-4 ${
                isBookmarked ? 'fill-[#4edea3] text-[#4edea3]' : 'text-neutral-300'
              }`}
            />
          </button>

          {/* Pill on Image */}
          <div className="absolute bottom-3 left-3">
            {isPast ? (
              <span className="px-3 py-1 rounded-full bg-[#201f22]/90 backdrop-blur-md text-neutral-400 font-medium text-[11px] border border-white/10">
                Событие завершено
              </span>
            ) : isFree ? (
              <span className="px-3 py-1 rounded-full bg-[#201f22]/90 backdrop-blur-md text-white font-bold text-[11px] border border-white/10">
                Вход свободный
              </span>
            ) : event.capacity ? (
              <span className="px-3 py-1 rounded-full bg-[#00a572] text-[#00311f] font-bold text-[11px] flex items-center gap-1.5 shadow-md">
                <span className="w-1.5 h-1.5 rounded-full bg-[#00311f]" />
                <span>{event.capacity} мест</span>
              </span>
            ) : (
              <span className="px-3 py-1 rounded-full bg-[#201f22]/90 backdrop-blur-md text-[#4edea3] font-bold text-[11px] border border-white/10 flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-[#4edea3]" />
                <span>Регистрация открыта</span>
              </span>
            )}
          </div>
        </div>

        {/* Card Body */}
        <div className="p-3.5 space-y-3">
          <div className="space-y-1">
            <h3 className="text-base font-bold text-white tracking-tight line-clamp-1">
              {event.title}
            </h3>
            <div className="flex items-center gap-1.5 text-neutral-400 text-xs">
              <MapPin className="w-3.5 h-3.5 text-[#4edea3] shrink-0" />
              <span className="truncate">
                {event.venue_name || org?.name || 'Локация уточняется'} • {event.city_name || org?.city_name || 'Локация'}
              </span>
            </div>
          </div>

          {/* Footer Action Row */}
          <div className="flex items-center justify-between pt-1 border-t border-white/5">
            <div className="flex flex-col">
              <span className="text-[10px] text-neutral-500 uppercase tracking-wider">
                {isPast ? 'Статус' : isFree ? 'Регистрация' : 'Стоимость входа'}
              </span>
              <span
                className={`text-sm font-extrabold ${
                  isPast ? 'text-neutral-400' : isFree ? 'text-[#4edea3]' : 'text-white'
                }`}
              >
                {isPast ? 'Завершено' : isFree ? 'Бесплатно' : `от ${priceFormatted}`}
              </span>
            </div>

            {!isPast && !isFree ? (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  telegram.hapticImpact('light');
                  onClose();
                  onEventClick(event);
                }}
                className="px-4 py-2 rounded-full bg-[#4edea3] text-[#00311f] font-extrabold text-xs flex items-center gap-1 shadow-md active:scale-95 transition-transform"
              >
                <span>Купить билет</span>
                <ArrowRight className="w-3.5 h-3.5 stroke-[3]" />
              </button>
            ) : (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  telegram.hapticImpact('light');
                  onClose();
                  onEventClick(event);
                }}
                className="px-4 py-2 rounded-full bg-[#201f22] text-white font-bold text-xs flex items-center gap-1 border border-white/10 active:scale-95 transition-transform hover:bg-[#25252a]"
              >
                <span>Подробнее</span>
                <ChevronRight className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        </div>
      </article>
    );
  };

  return (
    <div className="fixed inset-0 z-[150] bg-[#08080A] overflow-y-auto overflow-x-hidden flex flex-col no-scrollbar">
      {/* Ambient Top Emerald Radial Glow Spot */}
      <div className="absolute top-0 inset-x-0 h-96 radial-emerald-glow pointer-events-none -z-10" />

      {/* Main Responsive Viewport Container */}
      <div className="w-full max-w-[480px] mx-auto min-h-screen flex flex-col pb-16 relative">
        {/* 1. Sticky Top Navigation Bar */}
        <header className="sticky top-0 z-30 px-4 py-3 flex items-center justify-between bg-[#08080A]/85 backdrop-blur-xl border-b border-white/5">
          <button
            onClick={() => {
              telegram.hapticImpact('light');
              onClose();
            }}
            type="button"
            className="w-10 h-10 rounded-full bg-[#18181b] border border-white/10 flex items-center justify-center text-white active:scale-95 transition-all shadow-sm"
            aria-label="Назад"
          >
            <ArrowLeft className="w-5 h-5 text-neutral-200" />
          </button>

          <div className="flex flex-col items-center">
            <span className="text-sm font-bold text-white tracking-tight leading-none">Профиль</span>
            <span className="text-[10px] font-extrabold text-[#4edea3] tracking-[0.15em] uppercase mt-0.5 leading-none">
              ORGANIZER
            </span>
          </div>

          <button
            onClick={handleShare}
            type="button"
            className="w-10 h-10 rounded-full bg-[#18181b] border border-white/10 flex items-center justify-center text-white active:scale-95 transition-all shadow-sm"
            aria-label="Поделиться"
          >
            {copied ? (
              <Check className="w-4 h-4 text-[#4edea3]" />
            ) : (
              <Share2 className="w-4 h-4 text-neutral-300" />
            )}
          </button>
        </header>

        {/* Loading State */}
        {isLoading && !org ? (
          <div className="flex-1 py-32 flex flex-col items-center justify-center space-y-3 text-neutral-400">
            <Loader2 className="w-8 h-8 animate-spin text-[#4edea3]" />
            <span className="text-xs font-medium">Загрузка профиля организации...</span>
          </div>
        ) : error && !org ? (
          <div className="p-6 m-4 text-center rounded-2xl bg-red-500/10 border border-red-500/20 text-red-300 space-y-3">
            <AlertCircle className="w-7 h-7 mx-auto text-red-400" />
            <div className="text-sm font-bold">{error}</div>
            <button
              onClick={loadData}
              type="button"
              className="px-5 py-2 rounded-full bg-white text-black font-bold text-xs active:scale-95 transition-all shadow-md"
            >
              Повторить попытку
            </button>
          </div>
        ) : org ? (
          <div className="flex-1 flex flex-col space-y-5 pt-3">
            {/* Owner Management Banner (if user is creator of this org) */}
            {org?.is_owner && (
              <div className="mx-4 p-3 rounded-2xl bg-[#1c1b1e] border border-white/10 flex items-center justify-between shadow-lg">
                <div className="flex items-center gap-2.5">
                  <div className="w-8 h-8 rounded-full bg-[#10b981]/20 text-[#4edea3] flex items-center justify-center">
                    <ShieldCheck className="w-4 h-4" />
                  </div>
                  <div className="flex flex-col">
                    <span className="text-xs font-bold text-white">Вы — владелец организации</span>
                    <span className="text-[10px] text-neutral-400">Управление публичным профилем</span>
                  </div>
                </div>
                <div className="flex items-center gap-1.5">
                  <button
                    onClick={() => {
                      telegram.hapticImpact('light');
                      onEditOrg?.(org);
                    }}
                    type="button"
                    className="p-2 rounded-full bg-white/10 text-white hover:bg-white/20 active:scale-95 transition-all"
                    title="Редактировать"
                  >
                    <Edit3 className="w-3.5 h-3.5" />
                  </button>
                  <button
                    onClick={() => {
                      telegram.hapticImpact('light');
                      onOpenCreateEvent?.(org.id);
                    }}
                    type="button"
                    className="px-3 py-1.5 rounded-full bg-white text-[#1a1c1c] text-xs font-bold active:scale-95 transition-all flex items-center gap-1 shadow-sm"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    <span>Событие</span>
                  </button>
                </div>
              </div>
            )}

            {/* 2. Hero Profile Section (Avatar, Name, Verification, Tags) */}
            <section className="flex flex-col items-center text-center px-4">
              {/* Specular Avatar Ring with Verified Badge */}
              <div className="relative mt-1">
                <div className="w-24 h-24 rounded-full p-1 bg-gradient-to-b from-white/25 via-white/10 to-transparent shadow-[0_0_28px_rgba(16,185,129,0.25)] flex items-center justify-center">
                  <div className="w-full h-full rounded-full overflow-hidden bg-[#18181b] border border-white/10 flex items-center justify-center">
                    <SafeAvatar
                      src={org.avatar_url || (org as any).logo_url}
                      name={org.name}
                      alt={org.name}
                      type="org"
                      sizeClassName="w-full h-full"
                      className="w-full h-full object-cover rounded-full"
                    />
                  </div>
                </div>
                {/* Verified Shield Badge on bottom-right of avatar */}
                {Boolean(org.is_verified) && (
                  <button
                    type="button"
                    onClick={() => {
                      telegram.hapticImpact('light');
                      telegram.showAlert('Верифицированный организатор Ivently — официальный статус проверенного бренда. Включает зелёную галочку в карточках событий, расширенную базу и приоритет в поиске. Активируется в тарифе PRO.');
                    }}
                    className="w-6 h-6 rounded-full bg-[#10b981] text-[#00311f] flex items-center justify-center absolute bottom-0 right-0 border-2 border-[#08080A] shadow-md active:scale-90 transition cursor-pointer"
                    title="Верифицированный организатор (нажмите для информации)"
                  >
                    <Check className="w-3.5 h-3.5 stroke-[3]" />
                  </button>
                )}
              </div>

              {/* Organization Title */}
              <h1 className="text-2xl font-extrabold text-white tracking-tight mt-3">
                {org.name}
              </h1>

              {/* Verified Organizer Status Badge with Pulsing Dot */}
              {Boolean(org.is_verified) && (
                <button
                  type="button"
                  onClick={() => {
                    telegram.hapticImpact('light');
                    telegram.showAlert('Верифицированный организатор Ivently — официальный статус проверенного бренда. Включает зелёную галочку в карточках событий, расширенную базу и приоритет в поиске. Активируется в тарифе PRO.');
                  }}
                  className="inline-flex items-center justify-center gap-1.5 mt-1 text-xs font-semibold text-[#4edea3] hover:opacity-85 active:scale-95 transition cursor-pointer mx-auto"
                >
                  <span className="w-2 h-2 rounded-full bg-[#4edea3] animate-pulse" />
                  <span>Верифицированный организатор</span>
                  <Info className="w-3 h-3 opacity-70" />
                </button>
              )}

              {/* Category Pill with Sound Wave Icon */}
              <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-[#1a1a1f] border border-white/5 text-xs text-neutral-300 mt-2.5">
                <Volume2 className="w-3.5 h-3.5 text-neutral-400" />
                <span>{org.category || 'Организатор'}</span>
              </div>

              {/* City Pill */}
              <div className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-white/5 text-[11px] text-neutral-400 mt-1.5">
                <MapPin className="w-3 h-3 text-[#4edea3]" />
                <span>{org.city_name || 'Локация не указана'}</span>
              </div>

              {/* 3. Action Buttons Row: [Подписаться], [Написать], [Редактировать] */}
              <div className="w-full mt-5 flex items-center justify-center gap-2">
                {/* Subscribe Button */}
                <button
                  onClick={handleToggleSubscribe}
                  disabled={isSubscribing || Boolean(org?.is_owner)}
                  type="button"
                  className={`h-10 min-w-[140px] px-4 rounded-full font-bold text-xs flex items-center justify-center gap-1.5 active:scale-95 transition-all shadow-md ${
                    org?.is_owner
                      ? 'bg-[#2a2a2e] text-neutral-400 cursor-default opacity-80 border border-transparent'
                      : org?.is_subscribed
                      ? 'bg-[#201f22] text-[#4edea3] border border-[#10b981]/30 shadow-[0_0_12px_rgba(16,185,129,0.15)]'
                      : 'bg-white text-[#1a1c1c] border border-transparent shadow-[0_2px_12px_rgba(255,255,255,0.2)] hover:bg-neutral-100'
                  }`}
                >
                  {isSubscribing ? (
                    <Loader2 className="w-4 h-4 animate-spin text-[#4edea3]" />
                  ) : org?.is_subscribed ? (
                    <>
                      <Check className="w-4 h-4 text-[#4edea3]" />
                      <span>Вы подписаны</span>
                    </>
                  ) : (
                    <>
                      <Bell className="w-4 h-4 text-[#1a1c1c]" />
                      <span>Подписаться</span>
                    </>
                  )}
                </button>

                {/* Direct Message (Send / Telegram) Button */}
                {org?.social_link ? (
                  <button
                    onClick={handleOpenContact}
                    type="button"
                    className="h-10 px-4 flex-1 rounded-full bg-[#1c1c20] border border-white/10 text-white font-semibold text-xs flex items-center justify-center gap-1.5 active:scale-95 transition-all hover:bg-[#25252a] shadow-sm"
                  >
                    <Send className="w-3.5 h-3.5 text-[#4edea3]" />
                    <span>Написать</span>
                  </button>
                ) : org.is_owner ? (
                  <button
                    onClick={() => {
                      telegram.hapticImpact('light');
                      onEditOrg?.(org);
                    }}
                    type="button"
                    className="h-10 px-4 flex-1 rounded-full bg-[#1c1c20] border border-white/10 text-neutral-300 font-semibold text-xs flex items-center justify-center gap-1.5 active:scale-95 transition-all hover:bg-[#25252a] shadow-sm"
                  >
                    <Edit3 className="w-3.5 h-3.5 text-[#4edea3]" />
                    <span>Указать контакт</span>
                  </button>
                ) : null}

                {/* Owner Edit Button */}
                {org.is_owner && (
                  <button
                    onClick={() => {
                      telegram.hapticImpact('light');
                      onEditOrg?.(org);
                    }}
                    type="button"
                    className="w-10 h-10 shrink-0 rounded-full bg-[#1c1c20] border border-white/10 flex items-center justify-center text-neutral-300 active:scale-95 transition-all hover:text-white"
                    title="Редактировать профиль"
                  >
                    <Edit3 className="w-4 h-4" />
                  </button>
                )}
              </div>
            </section>

            {/* 4. Bento Grid: Real Organization Metrics */}
            <section className="px-4 grid grid-cols-3 gap-2">
              {/* Metric 1: Followers */}
              <div className="p-3 rounded-2xl bg-[#141417] border border-white/5 flex flex-col items-center justify-center text-center shadow-sm">
                <span className="text-base font-extrabold text-white tracking-tight">
                  {org.followers_count >= 1000
                    ? `${(org.followers_count / 1000).toFixed(1).replace('.0', '')}k`
                    : org.followers_count ?? 0}
                </span>
                <span className="text-[10px] font-bold text-[#4edea3] mt-0.5">
                  Аудитория
                </span>
                <span className="text-[11px] text-neutral-400 mt-1">Подписчиков</span>
              </div>

              {/* Metric 2: Upcoming Events */}
              <div className="p-3 rounded-2xl bg-[#141417] border border-white/5 flex flex-col items-center justify-center text-center shadow-sm">
                <span className="text-base font-extrabold text-white tracking-tight">
                  {upcomingEvents.length}
                </span>
                <span className="text-[10px] font-medium text-neutral-400 mt-0.5">
                  В афише
                </span>
                <span className="text-[11px] text-neutral-400 mt-1">Ближайших</span>
              </div>

              {/* Metric 3: Total Events */}
              <div className="p-3 rounded-2xl bg-[#141417] border border-white/5 flex flex-col items-center justify-center text-center shadow-sm">
                <span className="text-base font-extrabold text-white tracking-tight">
                  {events.length}
                </span>
                <span className="text-[10px] font-medium text-neutral-400 mt-0.5">
                  {pastEvents.length > 0 ? `${pastEvents.length} архив` : 'Всего'}
                </span>
                <span className="text-[11px] text-neutral-400 mt-1">Всего событий</span>
              </div>
            </section>

            {/* 5. Tactile Optical Tab Switcher: [Афиша] vs [О нас] */}
            <section className="px-4">
              <div className="relative p-1 rounded-full bg-[#121215] border border-white/5 flex items-center shadow-[inset_0_1px_1px_rgba(255,255,255,0.08)]">
                {/* Sliding Lens Indicator */}
                <div
                  className="absolute top-1 bottom-1 left-1 rounded-full bg-white shadow-[0_2px_12px_rgba(255,255,255,0.2)] pointer-events-none transition-transform duration-300 ease-out"
                  style={{
                    width: 'calc(50% - 4px)',
                    transform: `translate3d(${activeTab === 'afisha' ? '0%' : '100%'}, 0, 0)`,
                  }}
                />

                <button
                  onClick={() => {
                    if (activeTab !== 'afisha') {
                      telegram.hapticImpact('light');
                      setActiveTab('afisha');
                    }
                  }}
                  type="button"
                  className={`relative flex-1 py-2 text-center text-xs font-bold rounded-full transition-colors duration-200 z-10 flex items-center justify-center gap-1.5 ${
                    activeTab === 'afisha' ? 'text-[#1a1c1c]' : 'text-neutral-400 hover:text-white'
                  }`}
                >
                  <Ticket className="w-3.5 h-3.5" />
                  <span>Афиша</span>
                  <span
                    className={`px-1.5 py-0.2 rounded-full text-[10px] font-bold ${
                      activeTab === 'afisha'
                        ? 'bg-[#1a1c1c]/10 text-[#1a1c1c]'
                        : 'bg-white/10 text-neutral-300'
                    }`}
                  >
                    {events.length}
                  </span>
                </button>

                <button
                  onClick={() => {
                    if (activeTab !== 'about') {
                      telegram.hapticImpact('light');
                      setActiveTab('about');
                    }
                  }}
                  type="button"
                  className={`relative flex-1 py-2 text-center text-xs font-bold rounded-full transition-colors duration-200 z-10 flex items-center justify-center gap-1.5 ${
                    activeTab === 'about' ? 'text-[#1a1c1c]' : 'text-neutral-400 hover:text-white'
                  }`}
                >
                  <Info className="w-3.5 h-3.5" />
                  <span>О нас</span>
                </button>
              </div>
            </section>

            {/* 6. TAB CONTENT: АФИША */}
            {activeTab === 'afisha' && (
              <section className="px-4 space-y-4">
                {/* Subtitle row */}
                <div className="flex items-center justify-between px-1">
                  <span className="text-[11px] font-bold tracking-wider text-neutral-400 uppercase">
                    БЛИЖАЙШИЕ СОБЫТИЯ
                  </span>
                  <span className="text-xs font-semibold text-[#4edea3]">
                    {upcomingEvents.length} {upcomingEvents.length === 1 ? 'анонс' : upcomingEvents.length >= 2 && upcomingEvents.length <= 4 ? 'анонса' : 'анонсов'}
                  </span>
                </div>

                {upcomingEvents.length === 0 ? (
                  <div className="py-12 px-4 text-center rounded-[24px] bg-[#141417] border border-white/5 space-y-3 shadow-lg">
                    <div className="w-12 h-12 rounded-full bg-[#10b981]/15 text-[#4edea3] flex items-center justify-center mx-auto border border-[#10b981]/25">
                      <Ticket className="w-6 h-6" />
                    </div>
                    <div className="space-y-1">
                      <h3 className="font-bold text-sm text-white">Пока нет предстоящих событий</h3>
                      <p className="text-xs text-neutral-400 max-w-xs mx-auto">
                        Подпишитесь на уведомления, чтобы первыми узнать о старте продаж билетов
                      </p>
                    </div>
                    {org.is_owner ? (
                      <button
                        onClick={() => {
                          telegram.hapticImpact('light');
                          onOpenCreateEvent?.(org.id);
                        }}
                        type="button"
                        className="px-5 py-2.5 rounded-full bg-white text-[#1a1c1c] text-xs font-bold shadow-md active:scale-95 transition-all"
                      >
                        Создать первое событие
                      </button>
                    ) : (
                      <button
                        onClick={handleToggleSubscribe}
                        type="button"
                        className="px-5 py-2.5 rounded-full bg-white text-[#1a1c1c] text-xs font-bold shadow-md active:scale-95 transition-all"
                      >
                        {org.is_subscribed ? 'Вы подписаны' : 'Подписаться на анонсы'}
                      </button>
                    )}
                  </div>
                ) : (
                  <div className="space-y-3">
                    {upcomingEvents.map((event) => renderEventCard(event, false))}
                  </div>
                )}

                {/* Past / Archived Events */}
                {pastEvents.length > 0 && (
                  <div className="pt-4 border-t border-white/5 space-y-3">
                    <div className="flex items-center justify-between px-1">
                      <span className="text-[11px] font-bold tracking-wider text-neutral-500 uppercase">
                        ПРОШЕДШИЕ СОБЫТИЯ
                      </span>
                      <span className="text-xs font-medium text-neutral-500">
                        {pastEvents.length} в архиве
                      </span>
                    </div>
                    <div className="space-y-3">
                      {pastEvents.map((event) => renderEventCard(event, true))}
                    </div>
                  </div>
                )}
              </section>
            )}

            {/* 7. TAB CONTENT: О НАС (Manifesto, Location, Venue Rules) */}
            {activeTab === 'about' && (
              <section className="px-4 space-y-4">
                {/* Manifesto Card */}
                <div className="p-4 rounded-2xl bg-[#141417] border border-white/5 space-y-2 shadow-sm">
                  <div className="flex items-center gap-2 text-[#4edea3] text-xs font-bold uppercase tracking-wider">
                    <Sparkles className="w-3.5 h-3.5" />
                    <span>О сообществе</span>
                  </div>
                  <p className="text-xs text-neutral-300 leading-relaxed whitespace-pre-line">
                    {org.description ||
                      'Официальная страница организатора мероприятий. Подпишитесь, чтобы первыми получать уведомления о новых событиях и анонсах.'}
                  </p>
                </div>

                {/* Residence Location & Map Link */}
                <div className="p-4 rounded-2xl bg-[#141417] border border-white/5 space-y-3 shadow-sm">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-white text-xs font-bold uppercase tracking-wider">
                      <MapPin className="w-3.5 h-3.5 text-[#4edea3]" />
                      <span>Локация и адрес</span>
                    </div>
                    <span className="text-[11px] text-[#4edea3] font-medium">{org.city_name || 'Локация не указана'}</span>
                  </div>

                  <div className="p-3 rounded-xl bg-[#08080A] border border-white/5 space-y-1">
                    <div className="text-sm font-bold text-white">
                      {org.address || 'Адрес уточняется'}
                    </div>
                    <div className="text-xs text-neutral-400">
                      {org.address ? `Резиденция «${org.name}»` : 'Контакты и подробности уточняются'}
                    </div>
                  </div>

                  <button
                    onClick={openRouteInYandexMaps}
                    type="button"
                    className="w-full py-2.5 px-4 rounded-xl bg-[#1c1c20] hover:bg-[#25252a] text-white text-xs font-semibold flex items-center justify-center gap-2 border border-white/10 active:scale-95 transition-all shadow-sm"
                  >
                    <span>Маршрут в Яндекс Карты</span>
                    <ExternalLink className="w-3.5 h-3.5 text-neutral-400" />
                  </button>
                </div>

                {/* Media & Official Contacts */}
                <div className="p-4 rounded-2xl bg-[#141417] border border-white/5 space-y-2.5 shadow-sm">
                  <div className="text-xs font-bold text-white uppercase tracking-wider">
                    Официальные каналы
                  </div>

                  <div className="space-y-1.5">
                    {org.social_link && (
                      <a
                        href={
                          org.social_link.startsWith('http')
                            ? org.social_link
                            : `https://${org.social_link.replace(/^@/, 't.me/')}`
                        }
                        target="_blank"
                        rel="noreferrer"
                        className="p-3 rounded-xl bg-[#08080A] border border-white/5 flex items-center justify-between text-xs text-neutral-200 hover:text-white transition-colors"
                      >
                        <div className="flex items-center gap-2.5">
                          <Send className="w-4 h-4 text-[#4edea3]" />
                          <span>Telegram канал</span>
                        </div>
                        <ExternalLink className="w-3.5 h-3.5 text-neutral-500" />
                      </a>
                    )}

                    {org.website && (
                      <a
                        href={org.website.startsWith('http') ? org.website : `https://${org.website}`}
                        target="_blank"
                        rel="noreferrer"
                        className="p-3 rounded-xl bg-[#08080A] border border-white/5 flex items-center justify-between text-xs text-neutral-200 hover:text-white transition-colors"
                      >
                        <div className="flex items-center gap-2.5">
                          <ExternalLink className="w-4 h-4 text-neutral-400" />
                          <span>Официальный сайт</span>
                        </div>
                        <ChevronRight className="w-3.5 h-3.5 text-neutral-500" />
                      </a>
                    )}
                  </div>
                </div>

                {/* Venue Rules & Features */}
                {org.features && org.features.length > 0 && (
                  <div className="p-4 rounded-2xl bg-[#141417] border border-white/5 space-y-2.5 shadow-sm">
                    <div className="text-xs font-bold text-white uppercase tracking-wider">
                      Особенности и удобства
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {org.features.map((feat, idx) => (
                        <div
                          key={idx}
                          className="px-3 py-1.5 rounded-xl bg-[#08080A] border border-white/5 text-xs text-neutral-200 flex items-center gap-1.5"
                        >
                          <span className="w-1.5 h-1.5 rounded-full bg-[#4edea3]" />
                          <span>{feat}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Footer Signature */}
                <div className="py-4 text-center text-[10px] text-neutral-500 tracking-wider uppercase">
                  IVENTLY PROTOCOL v2.4 • {org.name} • Организатор подтвержден
                </div>
              </section>
            )}
            </div>
        ) : null}
      </div>
    </div>
  );
};
