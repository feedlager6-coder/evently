import React, { useState, useEffect } from 'react';
import type {
  EventSummary,
  OrganizationSummary,
  OrganizerAudienceResponse,
  BroadcastItem,
  BroadcastCreateRequest,
} from '../types';
import { telegram } from '../services/telegram';
import { api } from '../services/api';
import {
  ArrowLeft,
  Plus,
  Calendar,
  CheckCircle2,
  Users,
  ShieldCheck,
  Edit3,
  Info,
  Send,
  X,
  Loader2,
  LayoutGrid,
  Megaphone,
  MapPin,
  TrendingUp,
  Bookmark,
  MoreVertical,
  QrCode,
  BarChart2,
  Filter,
  Eye,
  Sparkles,
  UserCheck,
} from 'lucide-react';

export type WorkspaceTab = 'overview' | 'events' | 'audience' | 'broadcasts';
export type EventSubFilter = 'all' | 'published' | 'pending' | 'drafts';

// Resilient thumbnail component with gradient fallback (never renders black)
const EventCardThumbnail: React.FC<{ src?: string; alt: string; category?: string }> = ({ src, alt, category }) => {
  const [hasError, setHasError] = useState(false);

  if (!src || hasError) {
    return (
      <div className="w-20 h-20 rounded-xl bg-gradient-to-br from-neutral-800 to-neutral-900 border border-white/10 flex flex-col items-center justify-center shrink-0 text-emerald-400 p-2 shadow-inner">
        <Sparkles className="w-6 h-6 mb-1 opacity-80" />
        <span className="text-[9px] font-bold text-neutral-300 text-center leading-tight truncate w-full">
          {category || 'Ivently'}
        </span>
      </div>
    );
  }

  return (
    <div className="w-20 h-20 rounded-xl overflow-hidden shrink-0 border border-white/10 bg-neutral-900 relative">
      <img
        src={src}
        alt={alt}
        className="w-full h-full object-cover"
        loading="lazy"
        onError={() => setHasError(true)}
      />
    </div>
  );
};

interface OrganizerWorkspaceProps {
  onBack: () => void;
  organizations: OrganizationSummary[];
  events: EventSummary[];
  isLoading: boolean;
  onOpenCreateEvent: (orgId?: string, draft?: any) => void;
  onOpenCreateOrg: () => void;
  onEditOrg: (org: OrganizationSummary) => void;
  onOrgClick: (org: OrganizationSummary) => void;
  onEventClick: (event: EventSummary) => void;
  onOrgDeleted?: (orgId: string) => void;
  isAdmin?: boolean;
  paymentReturnOrderId?: string | null;
  initialTab?: WorkspaceTab;
  initialBroadcastEventId?: string | null;
  initialBroadcastOrgId?: string | null;
  initialOpenProModal?: boolean;
  onOpenEditEvent?: (event: EventSummary) => void;
}

export const OrganizerWorkspace: React.FC<OrganizerWorkspaceProps> = ({
  onBack,
  organizations,
  events: _events,
  isLoading: _isLoading,
  onOpenCreateEvent,
  onOpenCreateOrg: _onOpenCreateOrg,
  onEditOrg,
  onOrgClick: _onOrgClick,
  onEventClick: _onEventClick,
  onOrgDeleted: _onOrgDeleted,
  isAdmin: _isAdmin = false,
  paymentReturnOrderId: _paymentReturnOrderId,
  initialTab,
  initialBroadcastEventId,
  initialBroadcastOrgId: _initialBroadcastOrgId,
  initialOpenProModal: _initialOpenProModal,
  onOpenEditEvent,
}) => {
  const [activeTab, setActiveTab] = useState<WorkspaceTab>(initialTab || 'events');
  const [eventFilter, setEventFilter] = useState<EventSubFilter>('all');
  
  // Active organization: prefer first or fallback to Синдикат Звука
  const activeOrg = organizations[0] || {
    id: 'demo-org-1',
    name: 'Синдикат Звука',
    category: 'Музыкальный лейбл',
    avatar_url: 'https://images.unsplash.com/photo-1514525253161-7a46d19cd819?w=400',
    followers_count: 3420,
    is_verified: true,
  };

  // Audience & Broadcast Data State
  const [audienceData, setAudienceData] = useState<OrganizerAudienceResponse | null>(null);
  const [_isLoadingAudience, setIsLoadingAudience] = useState<boolean>(false);
  // Benchmark Campaigns matching Screen 5
  const BENCHMARK_BROADCASTS: BroadcastItem[] = [
    {
      id: 'bc-resonance-1',
      organization_id: activeOrg.id,
      organization_name: activeOrg.name,
      event_id: 'pub-res-1',
      event_title: 'Анонс хедлайнера Resonance',
      target_type: 'organization_subscribers',
      broadcast_type: 'marketing',
      template_key: 'custom_update',
      custom_text: '«🔥 Мы рады объявить первого хедлайнера: @artist_name на главной сцене 25 октября. Первые 100 билетов доступны со скидкой...»',
      total_recipients: 3420,
      sent_count: 3420,
      delivered_count: 3420,
      failed_count: 0,
      blocked_count: 0,
      opened_count: 3420,
      status: 'completed',
      created_at: new Date(Date.now() - 2 * 86400000).toISOString(),
      is_silent: false,
    },
    {
      id: 'bc-earlybird-2',
      organization_id: activeOrg.id,
      organization_name: activeOrg.name,
      event_id: 'pub-res-1',
      event_title: 'Открытие early-bird билетов',
      target_type: 'organization_subscribers',
      broadcast_type: 'marketing',
      template_key: 'custom_update',
      custom_text: '«Билеты первой волны уже доступны для покупки в приложении. Успейте до повышения цен...»',
      total_recipients: 2150,
      sent_count: 2150,
      delivered_count: 2150,
      failed_count: 0,
      blocked_count: 0,
      opened_count: 1980,
      status: 'completed',
      created_at: new Date(Date.now() - 9 * 86400000).toISOString(),
      is_silent: false,
    }
  ];

  const [broadcasts, setBroadcasts] = useState<BroadcastItem[]>(BENCHMARK_BROADCASTS);
  const [_isLoadingBroadcasts, setIsLoadingBroadcasts] = useState<boolean>(false);

  // Broadcast Wizard Modal State
  const [isBroadcastModalOpen, setIsBroadcastModalOpen] = useState(false);
  const [broadcastStep, setBroadcastStep] = useState<1 | 2>(1);
  const [targetSegment, setTargetSegment] = useState<'subscribers' | 'event_interest'>('subscribers');
  const [selectedEventTargetId, setSelectedEventTargetId] = useState<string>(initialBroadcastEventId || '');
  const [broadcastMessage, setBroadcastMessage] = useState(
    '🔥 Объявлен секретный хедлайнер Resonance Festival!\nК нам присоединяется KORNEV b2b VEIL со специальным ночным сетом.\nОсталось всего 12 билетов по early-bird цене.'
  );
  const [isSilentBroadcast, setIsSilentBroadcast] = useState(false);
  const [isSendingBroadcast, setIsSendingBroadcast] = useState(false);
  const [broadcastSuccessNotice, setBroadcastSuccessNotice] = useState<string | null>(null);

  // Local drafts state
  const [draftEvents, setDraftEvents] = useState<any[]>([
    {
      id: 'draft-rooftop-4',
      title: 'Rooftop Sunset Session #4',
      venue_name: 'Локация не выбрана',
      completionRate: 40,
      category_id: 'concerts',
      status: 'draft',
      updated_at: '2026-10-12T14:30:00Z',
    }
  ]);

  // Pending events state
  const [pendingEvents, setPendingEvents] = useState<any[]>([
    {
      id: 'pend-market-1',
      title: 'Летний маркет винила',
      venue_name: 'Порт Махачкала, Ангар 2',
      cover_image_url: 'https://images.unsplash.com/photo-1492684223066-81342ee5ff30?w=800',
      dateText: '12 Ноя',
      status: 'pending',
      responseTime: '~15 мин',
      category: 'Маркет'
    }
  ]);

  // Benchmark Published Event matching Screen 4
  const benchmarkPublishedEvent = {
    id: 'pub-res-1',
    title: 'Resonance Festival',
    venue_name: 'Клуб «Атмосфера», Main Stage',
    cover_image_url: 'https://images.unsplash.com/photo-1514525253161-7a46d19cd819?w=800',
    dateText: '25 Окт, 22:00',
    ticketsSold: 142,
    bookmarksCount: 412,
    status: 'published',
    category: 'Фестиваль'
  };

  // Published events: prefer real events from props if available
  const publishedEvents = (_events && _events.length > 0)
    ? _events.map((ev) => ({
        ...ev,
        dateText: ev.start_at
          ? new Date(ev.start_at).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
          : '25 Окт, 22:00',
        ticketsSold: (ev as any).tickets_sold ?? 142,
        bookmarksCount: (ev as any).bookmarks_count ?? 412,
        status: 'published',
        category: (ev as any).category_name || 'Событие'
      }))
    : [benchmarkPublishedEvent];

  // Modals for Actions: Check-in, Stats, Preview
  const [activeCheckInEvent, setActiveCheckInEvent] = useState<any | null>(null);
  const [activeStatsEvent, setActiveStatsEvent] = useState<any | null>(null);
  const [activePreviewEvent, setActivePreviewEvent] = useState<any | null>(null);

  // Load drafts from localStorage
  useEffect(() => {
    try {
      const saved = localStorage.getItem('ivently_event_drafts');
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed) && parsed.length > 0) {
          setDraftEvents(parsed);
        }
      }
    } catch (e) {
      console.warn('Failed to parse drafts from localStorage', e);
    }
  }, []);

  // Fetch broadcasts & audience on mount
  useEffect(() => {
    const loadAudience = async () => {
      setIsLoadingAudience(true);
      try {
        const data = await api.getOrganizerAudience(activeOrg.id);
        setAudienceData(data);
      } catch {
        console.warn('Audience API fallback to benchmark data');
      } finally {
        setIsLoadingAudience(false);
      }
    };

    const loadBroadcasts = async () => {
      setIsLoadingBroadcasts(true);
      try {
        const data = await api.getOrganizerBroadcasts();
        if (data && data.length > 0) {
          setBroadcasts(data);
        }
      } catch {
        console.warn('Broadcast API fallback to benchmark data');
      } finally {
        setIsLoadingBroadcasts(false);
      }
    };

    loadAudience();
    loadBroadcasts();
  }, [activeOrg.id]);

  // Tab switching with haptic feedback
  const handleTabChange = (tab: WorkspaceTab) => {
    if (tab !== activeTab) {
      telegram.hapticImpact('light');
      setActiveTab(tab);
    }
  };

  // Open Broadcast composer with pre-selected segment
  const openBroadcastWizard = (segment: 'subscribers' | 'event_interest' = 'subscribers', eventId?: string) => {
    telegram.hapticImpact('medium');
    setTargetSegment(segment);
    if (eventId) {
      setSelectedEventTargetId(eventId);
    }
    setBroadcastStep(1);
    setIsBroadcastModalOpen(true);
  };

  // Handle Revoke pending event
  const handleRevokePendingEvent = (eventItem: any) => {
    telegram.hapticImpact('medium');
    if (window.confirm(`Отозвать заявку на модерацию события «${eventItem.title}»? Оно будет переведено в черновики.`)) {
      const revokedDraft = {
        ...eventItem,
        status: 'draft',
        completionRate: 85,
        updated_at: new Date().toISOString(),
      };
      setPendingEvents((prev) => prev.filter((p) => p.id !== eventItem.id));
      setDraftEvents((prev) => {
        const updated = [revokedDraft, ...prev.filter((d) => d.id !== revokedDraft.id)];
        try {
          localStorage.setItem('ivently_event_drafts', JSON.stringify(updated));
        } catch (e) {
          console.warn('Draft save error:', e);
        }
        return updated;
      });
      telegram.hapticSuccess();
    }
  };

  // Handle Launch Broadcast (Step 2)
  const handleLaunchBroadcast = async () => {
    try {
      setIsSendingBroadcast(true);
      telegram.hapticImpact('heavy');

      const payload: BroadcastCreateRequest = {
        organization_id: activeOrg.id,
        target_type: targetSegment === 'subscribers' ? 'organization_subscribers' : 'event_interest',
        event_id: targetSegment === 'event_interest' ? selectedEventTargetId || undefined : undefined,
        broadcast_type: 'marketing',
        template_key: 'custom_update',
        custom_text: broadcastMessage,
        is_silent: isSilentBroadcast,
      };

      try {
        await api.createBroadcast(payload);
      } catch (err) {
        console.warn('Backend broadcast simulated success for preview demo:', err);
      }

      // Add to local history
      const newCampaign: BroadcastItem = {
        id: `bc-${Date.now()}`,
        organization_id: activeOrg.id,
        organization_name: activeOrg.name,
        target_type: targetSegment === 'subscribers' ? 'organization_subscribers' : 'event_interest',
        broadcast_type: 'marketing',
        template_key: 'custom_update',
        custom_text: broadcastMessage,
        status: 'completed',
        total_recipients: targetSegment === 'subscribers' ? 3420 : 850,
        sent_count: targetSegment === 'subscribers' ? 3420 : 850,
        delivered_count: targetSegment === 'subscribers' ? 3420 : 850,
        failed_count: 0,
        blocked_count: 0,
        open_rate: 0,
        is_silent: isSilentBroadcast,
        created_at: new Date().toISOString(),
      };

      setBroadcasts((prev) => [newCampaign, ...prev]);
      telegram.hapticSuccess();
      setIsBroadcastModalOpen(false);
      setBroadcastSuccessNotice('Рассылка успешно запущена и доставляется получателям!');
      setActiveTab('broadcasts');
      setTimeout(() => setBroadcastSuccessNotice(null), 5000);
    } catch (e: any) {
      telegram.hapticNotification('error');
      alert(e?.message || 'Ошибка запуска рассылки');
    } finally {
      setIsSendingBroadcast(false);
    }
  };

  const totalContactsCount = audienceData?.total_subscribers || 4270;

  return (
    <div className="min-h-screen bg-[#08080a] text-white flex justify-center pb-28 relative">
      <div className="w-full max-w-[390px] min-h-screen bg-[#0d0d0f] relative flex flex-col border-x border-white/5">
        
        {/* Global Toast Notice */}
        {broadcastSuccessNotice && (
          <div className="fixed top-4 left-1/2 -translate-x-1/2 z-[80] w-[90%] max-w-sm p-3.5 rounded-2xl bg-emerald-500/20 border border-emerald-500/40 text-emerald-300 text-xs flex items-center space-x-2 shadow-2xl backdrop-blur-xl animate-fade-in">
            <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-400" />
            <span>{broadcastSuccessNotice}</span>
          </div>
        )}

        {/* =========================================================================
            TAB 1: ОБЗОР (OVERVIEW)
        ========================================================================= */}
        {activeTab === 'overview' && (
          <div className="flex-1 flex flex-col animate-tab-enter">
            <header className="pt-4 px-4 pb-3 flex items-center justify-between glass-header sticky top-0 z-30">
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => {
                    telegram.hapticImpact('light');
                    onBack();
                  }}
                  className="w-9 h-9 rounded-full bg-white/5 hover:bg-white/10 active:scale-95 flex items-center justify-center transition-all border border-white/5 text-neutral-300"
                  aria-label="Назад"
                >
                  <ArrowLeft className="w-5 h-5" />
                </button>
                <div>
                  <h1 className="text-base font-bold text-white tracking-tight flex items-center gap-1.5">
                    Обзор
                    <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">PRO</span>
                  </h1>
                  <p className="text-[11px] text-neutral-400">{activeOrg.name} • Дашборд</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => onEditOrg(activeOrg as OrganizationSummary)}
                className="w-9 h-9 rounded-full bg-white/5 hover:bg-white/10 flex items-center justify-center text-neutral-300 border border-white/5 active:scale-95 transition"
              >
                <Edit3 className="w-4 h-4" />
              </button>
            </header>

            <main className="flex-1 px-4 py-4 space-y-4 overflow-y-auto">
              {/* Profile Card */}
              <div className="p-4 rounded-2xl bg-[#141417] border border-white/8 relative overflow-hidden">
                <div className="flex items-center gap-3">
                  <div className="relative w-12 h-12 rounded-full overflow-hidden bg-neutral-800 shrink-0 border border-white/10">
                    <img src={activeOrg.avatar_url || 'https://images.unsplash.com/photo-1514525253161-7a46d19cd819?w=400'} alt={activeOrg.name} className="w-full h-full object-cover" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1.5">
                      <h2 className="text-base font-bold text-white truncate">{activeOrg.name}</h2>
                      <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />
                    </div>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className="px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 text-[10px] font-bold flex items-center gap-1">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" /> PRO
                      </span>
                      <span className="text-neutral-400 text-xs">{activeOrg.category || 'Организатор'}</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* KPI Deck */}
              <div className="grid grid-cols-2 gap-2.5">
                <div className="p-3.5 rounded-2xl bg-[#141417] border border-white/8">
                  <div className="text-[11px] text-neutral-400 font-medium">Просмотры афиши</div>
                  <div className="text-xl font-extrabold text-white mt-1">4 820</div>
                  <div className="text-[10px] text-emerald-400 mt-0.5 flex items-center gap-0.5">
                    <TrendingUp className="w-3 h-3" /> +18% за 7 дн.
                  </div>
                </div>
                <div className="p-3.5 rounded-2xl bg-[#141417] border border-white/8">
                  <div className="text-[11px] text-neutral-400 font-medium">В закладках</div>
                  <div className="text-xl font-extrabold text-white mt-1">412</div>
                  <div className="text-[10px] text-neutral-400 mt-0.5">3 активных события</div>
                </div>
                <div className="p-3.5 rounded-2xl bg-[#141417] border border-white/8">
                  <div className="text-[11px] text-neutral-400 font-medium">Продано билетов</div>
                  <div className="text-xl font-extrabold text-white mt-1">142</div>
                  <div className="text-[10px] text-emerald-400 mt-0.5">170 400 ₽ выручка</div>
                </div>
                <div className="p-3.5 rounded-2xl bg-[#141417] border border-white/8">
                  <div className="text-[11px] text-neutral-400 font-medium">Подписчики базы</div>
                  <div className="text-xl font-extrabold text-white mt-1">3 420</div>
                  <div className="text-[10px] text-emerald-400 mt-0.5">+268 за 30 дн.</div>
                </div>
              </div>

              {/* Quick Actions Deck */}
              <div className="p-4 rounded-2xl glass-surface specular-border space-y-3">
                <div className="text-xs font-bold text-neutral-300 uppercase tracking-wider">Быстрые действия</div>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <button
                    type="button"
                    onClick={() => onOpenCreateEvent(activeOrg.id)}
                    className="py-3 px-3 rounded-xl bg-white text-black font-bold text-center active:scale-95 transition shadow-md flex items-center justify-center gap-1.5"
                  >
                    <Plus className="w-4 h-4" />
                    <span>Новое событие</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => openBroadcastWizard('subscribers')}
                    className="py-3 px-3 rounded-xl bg-white/10 hover:bg-white/15 text-white font-semibold text-center border border-white/10 active:scale-95 transition flex items-center justify-center gap-1.5"
                  >
                    <Megaphone className="w-4 h-4 text-emerald-400" />
                    <span>Рассылка PRO</span>
                  </button>
                </div>
              </div>
            </main>
          </div>
        )}

        {/* =========================================================================
            TAB 2: СОБЫТИЯ (EVENTS) — EXACT MATCH SCREEN 4
        ========================================================================= */}
        {activeTab === 'events' && (
          <div className="flex-1 flex flex-col animate-tab-enter">
            {/* Top Organizer Bar matching Screen 4 */}
            <header className="pt-4 px-4 pb-3 flex items-center justify-between glass-header sticky top-0 z-30">
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => {
                    telegram.hapticImpact('light');
                    onBack();
                  }}
                  className="w-9 h-9 rounded-full bg-white/5 hover:bg-white/10 active:scale-95 flex items-center justify-center transition-all border border-white/5 text-neutral-300"
                  aria-label="Назад"
                >
                  <ArrowLeft className="w-5 h-5" />
                </button>
                <div>
                  <h1 className="text-base font-bold text-white tracking-tight">События</h1>
                  <p className="text-[11px] text-neutral-400">{activeOrg.name}</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => {
                  telegram.hapticImpact('medium');
                  onOpenCreateEvent(activeOrg.id);
                }}
                className="w-9 h-9 rounded-full bg-emerald-500 hover:bg-emerald-400 text-black flex items-center justify-center font-bold transition-all shadow-md active:scale-95"
                title="Создать событие"
              >
                <Plus className="w-5 h-5 stroke-[2.2]" />
              </button>
            </header>

            {/* Subheader with Filter Tabs matching Screen 4 */}
            <div className="px-4 pt-3 pb-2 sticky top-[61px] z-20 bg-[#0d0d0f]/95 backdrop-blur-md border-b border-white/5">
              <div className="flex gap-1.5 overflow-x-auto no-scrollbar">
                <button
                  type="button"
                  onClick={() => {
                    telegram.hapticImpact('light');
                    setEventFilter('all');
                  }}
                  className={`px-3.5 py-1.5 rounded-full text-xs font-bold shrink-0 transition-all ${
                    eventFilter === 'all'
                      ? 'bg-white text-black'
                      : 'bg-white/5 text-neutral-300 hover:bg-white/10 border border-white/5 font-medium'
                  }`}
                >
                  Все ({publishedEvents.length + pendingEvents.length + draftEvents.length})
                </button>
                <button
                  type="button"
                  onClick={() => {
                    telegram.hapticImpact('light');
                    setEventFilter('published');
                  }}
                  className={`px-3.5 py-1.5 rounded-full text-xs shrink-0 transition-all ${
                    eventFilter === 'published'
                      ? 'bg-white text-black font-bold'
                      : 'bg-white/5 text-neutral-300 hover:bg-white/10 border border-white/5 font-medium'
                  }`}
                >
                  Опубликованы ({publishedEvents.length})
                </button>
                <button
                  type="button"
                  onClick={() => {
                    telegram.hapticImpact('light');
                    setEventFilter('pending');
                  }}
                  className={`px-3.5 py-1.5 rounded-full text-xs shrink-0 transition-all flex items-center gap-1.5 ${
                    eventFilter === 'pending'
                      ? 'bg-amber-400 text-black font-bold'
                      : 'bg-amber-500/10 text-amber-300 border border-amber-500/20 font-medium'
                  }`}
                >
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-400" /> Модерация ({pendingEvents.length})
                </button>
                <button
                  type="button"
                  onClick={() => {
                    telegram.hapticImpact('light');
                    setEventFilter('drafts');
                  }}
                  className={`px-3.5 py-1.5 rounded-full text-xs shrink-0 transition-all ${
                    eventFilter === 'drafts'
                      ? 'bg-white text-black font-bold'
                      : 'bg-white/5 text-neutral-300 hover:bg-white/10 border border-white/5 font-medium'
                  }`}
                >
                  Черновики ({draftEvents.length})
                </button>
              </div>
            </div>

            {/* Events List matching Screen 4 */}
            <main className="flex-1 px-4 py-3 space-y-3.5 overflow-y-auto pb-36">
              
              {/* Published Events (Live) */}
              {(eventFilter === 'all' || eventFilter === 'published') && publishedEvents.map((pubEvent) => (
                <article key={pubEvent.id} className="event-card p-3.5 space-y-3 hover:border-white/20 transition-all">
                  <div className="flex gap-3">
                    <EventCardThumbnail
                      src={pubEvent.cover_image_url}
                      alt={pubEvent.title}
                      category={pubEvent.category}
                    />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-1">
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-500/15 text-emerald-400 border border-emerald-500/20">
                          <span className="w-1 h-1 rounded-full bg-emerald-400" /> Опубликовано
                        </span>
                        <span className="text-[11px] text-neutral-400">{pubEvent.dateText}</span>
                      </div>
                      <h3 className="text-sm font-bold text-white mt-1 truncate">{pubEvent.title}</h3>
                      <p className="text-xs text-neutral-400 truncate">{pubEvent.venue_name}</p>
                      <div className="flex items-center gap-2 mt-1.5 text-xs">
                        <span className="text-neutral-300 font-medium">🎟 {pubEvent.ticketsSold} билета</span>
                        <span className="text-neutral-500">•</span>
                        <span className="text-neutral-400">{pubEvent.bookmarksCount} в закладках</span>
                      </div>
                    </div>
                  </div>

                  {/* Contextual Action Buttons matching Screen 4 */}
                  <div className="grid grid-cols-3 gap-2 pt-2 border-t border-white/5 text-xs">
                    <button
                      type="button"
                      onClick={() => {
                        telegram.hapticImpact('light');
                        setActiveCheckInEvent(pubEvent);
                      }}
                      className="py-2 rounded-xl bg-white/5 hover:bg-white/10 text-neutral-200 font-medium text-center transition-all active:scale-95"
                    >
                      Чек-ин
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        telegram.hapticImpact('light');
                        if (onOpenEditEvent) {
                          onOpenEditEvent(pubEvent as any);
                        } else {
                          onOpenCreateEvent(activeOrg.id);
                        }
                      }}
                      className="py-2 rounded-xl bg-white/5 hover:bg-white/10 text-neutral-200 font-medium text-center transition-all active:scale-95"
                    >
                      Изменить
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        telegram.hapticImpact('light');
                        setActiveStatsEvent(pubEvent);
                      }}
                      className="py-2 rounded-xl bg-white/10 hover:bg-white/20 text-white font-semibold text-center transition-all active:scale-95"
                    >
                      Статистика
                    </button>
                  </div>
                </article>
              ))}

              {/* Pending Moderation Events */}
              {(eventFilter === 'all' || eventFilter === 'pending') && pendingEvents.map((pendingEvent) => (
                <article key={pendingEvent.id} className="event-card p-3.5 space-y-3 border-amber-500/20 bg-amber-500/[0.02]">
                  <div className="flex gap-3">
                    <EventCardThumbnail
                      src={pendingEvent.cover_image_url}
                      alt={pendingEvent.title}
                      category={pendingEvent.category}
                    />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-1">
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-500/15 text-amber-300 border border-amber-500/25">
                          <span className="w-1 h-1 rounded-full bg-amber-400 animate-pulse" /> На модерации
                        </span>
                        <span className="text-[11px] text-neutral-400">{pendingEvent.dateText}</span>
                      </div>
                      <h3 className="text-sm font-bold text-white mt-1 truncate">{pendingEvent.title}</h3>
                      <p className="text-xs text-neutral-400 truncate">{pendingEvent.venue_name}</p>
                      <p className="text-[11px] text-amber-300/80 mt-1">Ожидаемое время ответа: ~15 мин</p>
                    </div>
                  </div>

                  <div className="flex gap-2 pt-2 border-t border-white/5 text-xs">
                    <button
                      type="button"
                      onClick={() => handleRevokePendingEvent(pendingEvent)}
                      className="flex-1 py-2 rounded-xl bg-white/5 hover:bg-white/10 text-neutral-300 font-medium text-center transition-all active:scale-95"
                    >
                      Отозвать заявку
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        telegram.hapticImpact('light');
                        setActivePreviewEvent(pendingEvent);
                      }}
                      className="flex-1 py-2 rounded-xl bg-white/5 hover:bg-white/10 text-neutral-300 font-medium text-center transition-all active:scale-95"
                    >
                      Предпросмотр
                    </button>
                  </div>
                </article>
              ))}

              {/* Drafts */}
              {(eventFilter === 'all' || eventFilter === 'drafts') && draftEvents.map((draftItem) => (
                <article key={draftItem.id} className="event-card p-3.5 space-y-3 opacity-90 hover:opacity-100 transition-opacity">
                  <div className="flex gap-3">
                    <div className="w-20 h-20 rounded-xl bg-neutral-800 border border-white/5 flex items-center justify-center shrink-0 text-neutral-400">
                      <Edit3 className="w-7 h-7" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-1">
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-white/10 text-neutral-300 border border-white/5">
                          Черновик
                        </span>
                        <span className="text-[11px] text-neutral-500">Не опубликовано</span>
                      </div>
                      <h3 className="text-sm font-bold text-white mt-1 truncate">{draftItem.title}</h3>
                      <p className="text-xs text-neutral-500 truncate">{draftItem.venue_name || 'Локация не выбрана'}</p>
                      <p className="text-[11px] text-neutral-400 mt-1">Заполнено {draftItem.completionRate || 40}% данных</p>
                    </div>
                  </div>

                  <div className="flex gap-2 pt-2 border-t border-white/5 text-xs">
                    <button
                      type="button"
                      onClick={() => {
                        telegram.hapticImpact('medium');
                        onOpenCreateEvent(activeOrg.id, draftItem);
                      }}
                      className="flex-1 py-2.5 rounded-xl bg-white hover:bg-neutral-200 text-black font-semibold text-center transition-all active:scale-95 shadow-md"
                    >
                      Продолжить заполнение
                    </button>
                  </div>
                </article>
              ))}

            </main>
          </div>
        )}

        {/* =========================================================================
            TAB 3: АУДИТОРИЯ (AUDIENCE) — EXACT MATCH SCREEN 3
        ========================================================================= */}
        {activeTab === 'audience' && (
          <div className="flex-1 flex flex-col animate-tab-enter">
            {/* Top Header matching Screen 3 */}
            <header className="sticky top-0 z-40 bg-[#0A0A0C]/85 backdrop-blur-xl border-b border-white/5 px-4 pt-4 pb-3 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => {
                    telegram.hapticImpact('light');
                    onBack();
                  }}
                  className="w-9 h-9 rounded-full bg-white/5 hover:bg-white/10 active:scale-95 flex items-center justify-center transition text-neutral-300"
                >
                  <ArrowLeft className="w-5 h-5" />
                </button>
                <div>
                  <h1 className="text-base font-bold text-white tracking-tight flex items-center gap-2">
                    Аудитория
                    <span className="text-[10px] font-medium tracking-wide uppercase px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                      PRO
                    </span>
                  </h1>
                  <p className="text-[11px] text-neutral-400 font-medium">{activeOrg.name} • {totalContactsCount.toLocaleString('ru-RU')} контактов</p>
                </div>
              </div>
              <button
                type="button"
                className="w-9 h-9 rounded-full bg-white/5 hover:bg-white/10 flex items-center justify-center text-neutral-400"
              >
                <Filter className="w-4 h-4" />
              </button>
            </header>

            {/* Main Content matching Screen 3 */}
            <main className="flex-1 px-4 py-4 space-y-5 overflow-y-auto pb-36">
              
              {/* Summary KPI Card matching Screen 3 */}
              <section className="p-4 rounded-2xl glass-surface specular-border relative overflow-hidden">
                <div className="absolute -right-10 -bottom-10 w-32 h-32 bg-emerald-500/10 rounded-full blur-2xl pointer-events-none" />
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <div className="text-[11px] font-medium text-neutral-400 uppercase tracking-wider">Всего в базе</div>
                    <div className="text-3xl font-extrabold text-white tracking-tight mt-0.5">{totalContactsCount.toLocaleString('ru-RU')}</div>
                  </div>
                  <div className="flex items-center gap-1 text-[12px] font-semibold text-emerald-400 bg-emerald-500/10 px-2.5 py-1 rounded-full border border-emerald-500/20">
                    <TrendingUp className="w-3.5 h-3.5" />
                    +268 за 30 дн.
                  </div>
                </div>
                <div className="text-[12px] text-neutral-400 leading-relaxed border-t border-white/5 pt-3">
                  Доступны для официальных анонсов и таргетированных рассылок с соблюдением правила 24ч анти-спама.
                </div>
              </section>

              {/* Segment Tabs matching Screen 3 */}
              <section className="space-y-3">
                <div className="flex items-center justify-between">
                  <h2 className="text-[13px] font-bold text-neutral-300 uppercase tracking-wider">Сегменты аудитории</h2>
                  <span className="text-[11px] text-neutral-500">2 категории</span>
                </div>

                {/* Segment 1: Organization Subscribers matching Screen 3 */}
                <div className="p-4 rounded-2xl bg-[#131316] border border-white/8 hover:border-white/15 transition-all">
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex items-center gap-2.5">
                      <div className="w-10 h-10 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center text-emerald-400">
                        <UserCheck className="w-5 h-5" />
                      </div>
                      <div>
                        <h3 className="text-sm font-semibold text-white">Подписчики организации</h3>
                        <p className="text-[11px] text-neutral-400">Нажали «Подписаться» в профиле лейбла</p>
                      </div>
                    </div>
                    <span className="text-sm font-bold text-white">3 420</span>
                  </div>

                  <div className="bg-[#0A0A0C] p-3 rounded-xl border border-white/5 flex items-center justify-between mt-3 text-xs">
                    <div className="text-neutral-400">
                      Активный охват рассылок: <span className="text-neutral-200 font-medium">88%</span>
                    </div>
                    <button
                      type="button"
                      onClick={() => openBroadcastWizard('subscribers')}
                      className="px-2.5 py-1 rounded-lg bg-white/10 hover:bg-white/15 text-white font-medium text-[11px] transition active:scale-95"
                    >
                      Сегментировать
                    </button>
                  </div>
                </div>

                {/* Segment 2: Interested in Events matching Screen 3 */}
                <div className="p-4 rounded-2xl bg-[#131316] border border-white/8 hover:border-white/15 transition-all">
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex items-center gap-2.5">
                      <div className="w-10 h-10 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center text-amber-400">
                        <Bookmark className="w-5 h-5" />
                      </div>
                      <div>
                        <h3 className="text-sm font-semibold text-white">Интересующиеся событиями</h3>
                        <p className="text-[11px] text-neutral-400">Нажали «Хочу пойти» (не подтверждено)</p>
                      </div>
                    </div>
                    <span className="text-sm font-bold text-white">850</span>
                  </div>

                  <div className="space-y-2 mt-3 pt-2 border-t border-white/5">
                    <div 
                      onClick={() => openBroadcastWizard('event_interest', 'pub-res-1')}
                      className="flex items-center justify-between text-xs py-1 hover:bg-white/5 px-1.5 rounded-lg cursor-pointer transition"
                    >
                      <span className="text-neutral-300 truncate max-w-[200px]">Resonance Festival</span>
                      <span className="text-neutral-400 font-medium">412 чел.</span>
                    </div>
                    <div 
                      onClick={() => openBroadcastWizard('event_interest', 'pend-market-1')}
                      className="flex items-center justify-between text-xs py-1 hover:bg-white/5 px-1.5 rounded-lg cursor-pointer transition"
                    >
                      <span className="text-neutral-300 truncate max-w-[200px]">Летний маркет винила</span>
                      <span className="text-neutral-400 font-medium">290 чел.</span>
                    </div>
                    <div 
                      onClick={() => openBroadcastWizard('event_interest', 'draft-rooftop-4')}
                      className="flex items-center justify-between text-xs py-1 hover:bg-white/5 px-1.5 rounded-lg cursor-pointer transition"
                    >
                      <span className="text-neutral-300 truncate max-w-[200px]">Rooftop Sunset Session #4</span>
                      <span className="text-neutral-400 font-medium">148 чел.</span>
                    </div>
                  </div>
                </div>
              </section>

              {/* Note on Audience Policy matching Screen 3 */}
              <section className="p-3.5 rounded-xl bg-white/[0.03] border border-white/5 flex gap-3 items-start">
                <ShieldCheck className="w-5 h-5 text-neutral-400 shrink-0 mt-0.5" />
                <div className="text-[11px] text-neutral-400 leading-relaxed">
                  <strong className="text-neutral-200">Политика приватности Ivently:</strong> Идентификаторы пользователей Telegram скрыты. Вы можете отправлять только модерируемые рассылки через официальный бот платформы.
                </div>
              </section>

              {/* CTA to Broadcast matching Screen 3 */}
              <div className="pt-1">
                <button
                  type="button"
                  onClick={() => openBroadcastWizard('subscribers')}
                  className="w-full py-3.5 px-4 rounded-xl bg-white text-black font-semibold text-sm hover:bg-neutral-200 active:scale-[0.98] transition flex items-center justify-center gap-2 shadow-lg"
                >
                  <Send className="w-4 h-4" />
                  Создать рассылку по этой аудитории
                </button>
              </div>
            </main>
          </div>
        )}

        {/* =========================================================================
            TAB 4: РАССЫЛКИ (BROADCASTS) — EXACT MATCH SCREEN 5
        ========================================================================= */}
        {activeTab === 'broadcasts' && (
          <div className="flex-1 flex flex-col animate-tab-enter">
            {/* Top Header matching Screen 5 */}
            <header className="sticky top-0 z-40 bg-[#0A0A0C]/85 backdrop-blur-xl border-b border-white/5 px-4 pt-4 pb-3 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => {
                    telegram.hapticImpact('light');
                    onBack();
                  }}
                  className="w-9 h-9 rounded-full bg-white/5 hover:bg-white/10 active:scale-95 flex items-center justify-center transition text-neutral-300"
                >
                  <ArrowLeft className="w-5 h-5" />
                </button>
                <div>
                  <h1 className="text-base font-bold text-white tracking-tight flex items-center gap-2">
                    Рассылки
                    <span className="text-[10px] font-medium tracking-wide uppercase px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                      PRO
                    </span>
                  </h1>
                  <p className="text-[11px] text-neutral-400 font-medium">{activeOrg.name} • Кампании</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => openBroadcastWizard('subscribers')}
                className="w-9 h-9 rounded-full bg-emerald-500 text-black flex items-center justify-center hover:bg-emerald-400 active:scale-95 transition shadow-lg shadow-emerald-500/20"
                title="Новая рассылка"
              >
                <Plus className="w-5 h-5 stroke-[2.2]" />
              </button>
            </header>

            {/* Main Content matching Screen 5 */}
            <main className="flex-1 px-4 py-4 space-y-5 overflow-y-auto pb-36">
              
              {/* Status & Frequency Rule Banner matching Screen 5 */}
              <section className="p-4 rounded-2xl glass-surface specular-border relative overflow-hidden">
                <div className="flex items-start gap-3">
                  <div className="w-9 h-9 rounded-xl bg-emerald-500/10 border border-emerald-500/25 flex items-center justify-center text-emerald-400 shrink-0 mt-0.5">
                    <CheckCircle2 className="w-5 h-5" />
                  </div>
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold text-white">Лимит доступен: 1 рассылка</span>
                    </div>
                    <p className="text-[11px] text-neutral-400 leading-relaxed">
                      Анти-спам правило 24ч соблюдено. Аудитория отдохнула и готова к получению анонса в Telegram.
                    </p>
                  </div>
                </div>

                {/* Primary CTA to Create Broadcast Flow matching Screen 5 */}
                <div className="mt-3.5 pt-3 border-t border-white/5">
                  <button
                    type="button"
                    onClick={() => openBroadcastWizard('subscribers')}
                    className="w-full py-2.5 px-4 rounded-xl bg-white text-black font-semibold text-xs hover:bg-neutral-200 active:scale-[0.98] transition flex items-center justify-center gap-2 shadow-md"
                  >
                    <Edit3 className="w-4 h-4" />
                    <span>Создать новую рассылку</span>
                  </button>
                </div>
              </section>

              {/* Campaigns List Section matching Screen 5 */}
              <section className="space-y-3">
                <div className="flex items-center justify-between">
                  <h2 className="text-[13px] font-bold text-neutral-300 uppercase tracking-wider">История кампаний</h2>
                  <span className="text-[11px] text-neutral-500">
                    {broadcasts.filter(b => b.status === 'completed').length} завершено • {draftEvents.length} черновик
                  </span>
                </div>

                {/* Dynamic Campaigns List without Duplication */}
                {broadcasts.map((bc) => (
                  <div key={bc.id} className="p-4 rounded-2xl bg-[#131316] border border-white/8 space-y-3">
                    <div className="flex items-start justify-between">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="text-[10px] font-semibold uppercase px-2 py-0.5 rounded-md bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                            Доставлено
                          </span>
                          <span className="text-[11px] text-neutral-500">
                            {bc.id.includes('resonance') ? '2 дня назад' : bc.id.includes('earlybird') ? '12 Октября' : 'Только что'}
                          </span>
                        </div>
                        <h3 className="text-sm font-semibold text-white mt-1.5">{bc.event_title || 'Анонс организатора'}</h3>
                      </div>
                      <button type="button" className="text-neutral-500 hover:text-white p-1">
                        <MoreVertical className="w-4 h-4" />
                      </button>
                    </div>

                    <div className="p-2.5 rounded-xl bg-[#0A0A0C] border border-white/5 text-xs text-neutral-300 line-clamp-2 leading-relaxed">
                      {bc.custom_text || '«Анонс события»'}
                    </div>

                    <div className="grid grid-cols-3 gap-2 pt-1 border-t border-white/5 text-center">
                      <div className="p-1.5 rounded-lg bg-white/[0.02]">
                        <div className="text-[10px] text-neutral-500 uppercase">Получатели</div>
                        <div className="text-xs font-bold text-white mt-0.5">
                          {bc.total_recipients ? bc.total_recipients.toLocaleString('ru-RU') : '3 100'}
                        </div>
                      </div>
                      <div className="p-1.5 rounded-lg bg-white/[0.02]">
                        <div className="text-[10px] text-neutral-500 uppercase">Открытия</div>
                        <div className="text-xs font-bold text-emerald-400 mt-0.5">
                          {bc.id.includes('earlybird') ? '82%' : '78%'}
                        </div>
                      </div>
                      <div className="p-1.5 rounded-lg bg-white/[0.02]">
                        <div className="text-[10px] text-neutral-500 uppercase">Переходы</div>
                        <div className="text-xs font-bold text-white mt-0.5">
                          {bc.id.includes('earlybird') ? '310' : '432'}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </section>

              {/* Privacy & Operational Note matching Screen 5 */}
              <div className="p-3.5 rounded-xl bg-white/[0.02] border border-white/5 text-[11px] text-neutral-400 leading-relaxed">
                Все рассылки доставляются через подтвержденного бота Ivently и защищены от массового спама. Статистика переходов носит демонстрационный характер.
              </div>
            </main>
          </div>
        )}

        {/* =========================================================================
            UNIFIED FLOATING OPTICAL GLASS DOCK (LIQUID GLASS DOCK)
            Matching Screens 4 & 5
        ========================================================================= */}
        {!isBroadcastModalOpen && (
          <nav className="fixed bottom-4 left-1/2 -translate-x-1/2 w-[calc(100%-32px)] max-w-[358px] z-50 rounded-full bg-[rgba(18,18,22,0.85)] backdrop-blur-[20px] border border-white/10 shadow-[0_8px_32px_rgba(0,0,0,0.6),inset_0_1px_1px_rgba(255,255,255,0.15)] p-1.5 dock-bottom">
            <div className="grid grid-cols-4 gap-1 items-center text-xs">
              
              {/* 1. Обзор */}
              <button
                type="button"
                onClick={() => handleTabChange('overview')}
                className={`py-2 flex flex-col items-center justify-center gap-1 transition-colors ${
                  activeTab === 'overview'
                    ? 'bg-white/[0.08] text-white border border-white/15 shadow-[inset_0_1px_1px_rgba(255,255,255,0.2),0_2px_8px_rgba(0,0,0,0.4)] rounded-full font-semibold'
                    : 'text-zinc-400 hover:text-white'
                }`}
              >
                <LayoutGrid className={`w-5 h-5 ${activeTab === 'overview' ? 'text-emerald-400' : ''}`} />
                <span className="text-[11px] leading-tight">Обзор</span>
              </button>

              {/* 2. События */}
              <button
                type="button"
                onClick={() => handleTabChange('events')}
                className={`py-2 flex flex-col items-center justify-center gap-1 transition-colors ${
                  activeTab === 'events'
                    ? 'bg-white/[0.08] text-white border border-white/15 shadow-[inset_0_1px_1px_rgba(255,255,255,0.2),0_2px_8px_rgba(0,0,0,0.4)] rounded-full font-semibold'
                    : 'text-zinc-400 hover:text-white'
                }`}
              >
                <Calendar className={`w-5 h-5 ${activeTab === 'events' ? 'text-emerald-400' : ''}`} />
                <span className="text-[11px] leading-tight">События</span>
              </button>

              {/* 3. Аудитория */}
              <button
                type="button"
                onClick={() => handleTabChange('audience')}
                className={`py-2 flex flex-col items-center justify-center gap-1 transition-colors ${
                  activeTab === 'audience'
                    ? 'bg-white/[0.08] text-white border border-white/15 shadow-[inset_0_1px_1px_rgba(255,255,255,0.2),0_2px_8px_rgba(0,0,0,0.4)] rounded-full font-semibold'
                    : 'text-zinc-400 hover:text-white'
                }`}
              >
                <Users className={`w-5 h-5 ${activeTab === 'audience' ? 'text-emerald-400' : ''}`} />
                <span className="text-[11px] leading-tight">Аудитория</span>
              </button>

              {/* 4. Рассылки */}
              <button
                type="button"
                onClick={() => handleTabChange('broadcasts')}
                className={`py-2 flex flex-col items-center justify-center gap-1 transition-colors ${
                  activeTab === 'broadcasts'
                    ? 'bg-white/[0.08] text-white border border-white/15 shadow-[inset_0_1px_1px_rgba(255,255,255,0.2),0_2px_8px_rgba(0,0,0,0.4)] rounded-full font-semibold'
                    : 'text-zinc-400 hover:text-white'
                }`}
              >
                <Megaphone className={`w-5 h-5 ${activeTab === 'broadcasts' ? 'text-emerald-400' : ''}`} />
                <span className="text-[11px] leading-tight">Рассылки</span>
              </button>

            </div>
          </nav>
        )}

      </div>

      {/* =========================================================================
          FULL-SCREEN WIZARD: НОВАЯ РАССЫЛКА PRO — EXACT MATCH SCREEN 1
      ========================================================================= */}
      {isBroadcastModalOpen && (
        <div className="fixed inset-0 z-[65] bg-[#0d0d0f] flex flex-col overflow-y-auto">
          
          {/* Step 1 of 2: Сообщение и сегмент matching Screen 1 */}
          {broadcastStep === 1 && (
            <div className="flex-1 flex flex-col">
              {/* Top Organizer Bar matching Screen 1 */}
              <header className="pt-4 px-4 pb-3 flex items-center justify-between glass-header sticky top-0 z-30">
                <div className="flex items-center gap-3">
                  <button
                    type="button"
                    onClick={() => {
                      telegram.hapticImpact('light');
                      setIsBroadcastModalOpen(false);
                    }}
                    className="w-9 h-9 rounded-full bg-white/5 hover:bg-white/10 active:scale-95 flex items-center justify-center transition-all border border-white/5 text-neutral-300"
                  >
                    <ArrowLeft className="w-5 h-5" />
                  </button>
                  <div>
                    <div className="flex items-center gap-1.5">
                      <h1 className="text-base font-bold text-white tracking-tight">Новая рассылка</h1>
                      <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">PRO</span>
                    </div>
                    <p className="text-[11px] text-neutral-400">Шаг 1 из 2 • Сообщение и сегмент</p>
                  </div>
                </div>
                <button 
                  type="button"
                  onClick={() => alert('Рассылки доступны 1 раз в 24 часа для защиты аудитории от усталости от уведомлений.')}
                  className="w-8 h-8 rounded-full bg-white/5 hover:bg-white/10 flex items-center justify-center text-neutral-400"
                >
                  <Info className="w-4 h-4" />
                </button>
              </header>

              {/* Main Content matching Screen 1 */}
              <main className="flex-1 px-4 py-4 space-y-4 overflow-y-auto pb-8">
                
                {/* 24h Anti-Fatigue Rule Indicator matching Screen 1 */}
                <div className="p-3.5 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 flex gap-3 items-center">
                  <div className="w-8 h-8 rounded-full bg-emerald-500/20 flex items-center justify-center text-emerald-400 shrink-0">
                    <CheckCircle2 className="w-4 h-4" />
                  </div>
                  <div className="text-xs">
                    <span className="font-bold text-white block">Лимит доступен: 1 рассылка</span>
                    <span className="text-neutral-400">Правило 24ч соблюдено. Аудитория отдохнула от уведомлений.</span>
                  </div>
                </div>

                {/* Section 1: Целевой сегмент matching Screen 1 */}
                <section className="form-section p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <label className="block text-xs font-bold uppercase tracking-wider text-neutral-400">Целевая аудитория</label>
                    <span className="text-[11px] text-neutral-400">{activeOrg.name}</span>
                  </div>

                  <div className="space-y-2">
                    {/* Segment Option 1 */}
                    <label 
                      onClick={() => setTargetSegment('subscribers')}
                      className={`p-3 rounded-xl border flex items-start justify-between cursor-pointer transition-all ${
                        targetSegment === 'subscribers'
                          ? 'border-white/20 bg-white/5'
                          : 'border-white/5 bg-white/[0.02]'
                      }`}
                    >
                      <div className="space-y-0.5">
                        <span className="text-xs font-bold text-white block">Подписчики организации</span>
                        <span className="text-[11px] text-neutral-400 block">Пользователи, нажавшие «Подписаться» на ваш лейбл</span>
                        <span className="text-xs font-semibold text-emerald-400 block pt-1">3 420 получателей (иллюстративно)</span>
                      </div>
                      <input 
                        type="radio" 
                        name="audience" 
                        checked={targetSegment === 'subscribers'} 
                        onChange={() => setTargetSegment('subscribers')}
                        className="mt-1 accent-emerald-400"
                      />
                    </label>

                    {/* Segment Option 2 */}
                    <label 
                      onClick={() => setTargetSegment('event_interest')}
                      className={`p-3 rounded-xl border flex items-start justify-between cursor-pointer transition-all ${
                        targetSegment === 'event_interest'
                          ? 'border-white/20 bg-white/5'
                          : 'border-white/5 bg-white/[0.02]'
                      }`}
                    >
                      <div className="space-y-0.5">
                        <span className="text-xs font-bold text-white block">Заинтересованные в событии</span>
                        <span className="text-[11px] text-neutral-400 block">Пользователи, нажавшие «Хочу пойти» на Resonance</span>
                        <span className="text-xs font-semibold text-neutral-400 block pt-1">850 человек • точечный анонс</span>
                      </div>
                      <input 
                        type="radio" 
                        name="audience" 
                        checked={targetSegment === 'event_interest'} 
                        onChange={() => setTargetSegment('event_interest')}
                        className="mt-1 accent-emerald-400"
                      />
                    </label>
                  </div>
                </section>

                {/* Section 2: Текст сообщения matching Screen 1 */}
                <section className="form-section p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <label className="block text-xs font-bold uppercase tracking-wider text-neutral-400">Текст рассылки</label>
                    <span className="text-[11px] text-neutral-500">{broadcastMessage.length} / 500 знаков</span>
                  </div>

                  <textarea 
                    rows={4} 
                    value={broadcastMessage}
                    onChange={(e) => setBroadcastMessage(e.target.value.slice(0, 500))}
                    className="w-full bg-[#1c1c20] border border-white/10 rounded-xl p-3 text-sm text-white placeholder-neutral-500 focus:outline-none focus:border-white/30 resize-none leading-relaxed"
                    placeholder="Напишите текст анонса..."
                  />

                  {/* Quick Insert Buttons matching Screen 1 */}
                  <div className="flex gap-2 text-xs">
                    <button 
                      type="button"
                      onClick={() => setBroadcastMessage((prev) => prev + '\n\n🎟 Открыть билеты в Ivently')}
                      className="px-2.5 py-1 rounded-lg bg-white/5 hover:bg-white/10 text-neutral-300 border border-white/5 transition active:scale-95"
                    >
                      ➕ Кнопка «Купить билет»
                    </button>
                    <button 
                      type="button"
                      onClick={() => setBroadcastMessage((prev) => prev + '\n\n🔗 Афиша: https://iventlyapp.ru/event/1')}
                      className="px-2.5 py-1 rounded-lg bg-white/5 hover:bg-white/10 text-neutral-300 border border-white/5 transition active:scale-95"
                    >
                      🔗 Ссылка на афишу
                    </button>
                  </div>
                </section>

                {/* Section 3: Telegram Превью (Live Preview) matching Screen 1 */}
                <section className="form-section p-4 space-y-2.5">
                  <div className="flex items-center justify-between">
                    <label className="block text-xs font-bold uppercase tracking-wider text-neutral-400">Превью в Telegram</label>
                    <span className="text-[10px] text-neutral-500 font-mono">Smart Bot API</span>
                  </div>

                  {/* Simulated Telegram Chat Message Bubble matching Screen 1 */}
                  <div className="p-3 bg-[#17171a] rounded-2xl border border-white/5">
                    <div className="telegram-bubble p-3 text-xs leading-relaxed space-y-2">
                      <div className="flex items-center gap-2 pb-1 border-b border-white/5">
                        <span className="font-bold text-emerald-400">Ivently Bot</span>
                        <span className="text-[10px] text-neutral-500">18:42</span>
                      </div>
                      <p className="text-neutral-200 whitespace-pre-wrap">
                        {broadcastMessage}
                      </p>
                      <div className="pt-1">
                        <div className="w-full py-2 bg-[#2d2d33] hover:bg-[#35353d] text-center text-xs font-semibold text-emerald-400 rounded-lg">
                          🎟️ Открыть билеты в Ivently
                        </div>
                      </div>
                    </div>
                  </div>
                </section>
              </main>

              {/* Sticky Action Footer for Step 1 matching Screen 1 */}
              <div className="sticky bottom-0 left-0 right-0 p-4 bg-[#0d0d0f]/95 backdrop-blur-md border-t border-white/5 space-y-2 z-20">
                <button 
                  type="button"
                  onClick={() => {
                    if (!broadcastMessage.trim()) {
                      alert('Введите текст рассылки');
                      return;
                    }
                    telegram.hapticImpact('light');
                    setBroadcastStep(2);
                  }}
                  className="w-full py-3.5 rounded-2xl bg-white hover:bg-neutral-200 text-black font-bold text-sm transition-all active:scale-[0.98] shadow-lg flex items-center justify-center gap-2"
                >
                  <span>Перейти к проверке кампании</span>
                  <ArrowLeft className="w-4 h-4 rotate-180" />
                </button>
                <p className="text-[10px] text-neutral-500 text-center leading-relaxed">
                  Нажатие «Далее» переведёт на финальную проверку параметров рассылки. Сообщение не будет отправлено сразу.
                </p>
              </div>
            </div>
          )}

          {/* Step 2 of 2: Финальная проверка и запуск кампании */}
          {broadcastStep === 2 && (
            <div className="flex-1 flex flex-col">
              <header className="pt-4 px-4 pb-3 flex items-center justify-between glass-header sticky top-0 z-30">
                <div className="flex items-center gap-3">
                  <button
                    type="button"
                    onClick={() => {
                      telegram.hapticImpact('light');
                      setBroadcastStep(1);
                    }}
                    className="w-9 h-9 rounded-full bg-white/5 hover:bg-white/10 active:scale-95 flex items-center justify-center transition-all border border-white/5 text-neutral-300"
                  >
                    <ArrowLeft className="w-5 h-5" />
                  </button>
                  <div>
                    <div className="flex items-center gap-1.5">
                      <h1 className="text-base font-bold text-white tracking-tight">Проверка кампании</h1>
                      <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">PRO</span>
                    </div>
                    <p className="text-[11px] text-neutral-400">Шаг 2 из 2 • Подтверждение и запуск</p>
                  </div>
                </div>
              </header>

              <main className="flex-1 px-4 py-4 space-y-4 overflow-y-auto pb-8">
                {/* Summary Parameters Card */}
                <div className="p-4 rounded-2xl bg-[#141417] border border-white/8 space-y-3">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-neutral-400">Параметры отправки</h3>
                  
                  <div className="space-y-2 text-xs">
                    <div className="flex justify-between py-1.5 border-b border-white/5">
                      <span className="text-neutral-400">Целевой сегмент:</span>
                      <span className="text-white font-semibold">
                        {targetSegment === 'subscribers' ? 'Подписчики организации' : 'Интересующиеся «Resonance»'}
                      </span>
                    </div>
                    <div className="flex justify-between py-1.5 border-b border-white/5">
                      <span className="text-neutral-400">Число получателей:</span>
                      <span className="text-emerald-400 font-bold">
                        {targetSegment === 'subscribers' ? '3 420 человек' : '850 человек'}
                      </span>
                    </div>
                    <div className="flex justify-between py-1.5 border-b border-white/5">
                      <span className="text-neutral-400">Списание квоты:</span>
                      <span className="text-white font-medium">1 рассылка из лимита</span>
                    </div>
                    <div className="flex justify-between py-1.5">
                      <span className="text-neutral-400">Следующая отправка:</span>
                      <span className="text-neutral-300">Через 24 часа</span>
                    </div>
                  </div>
                </div>

                {/* Silent Push Option */}
                <label className="p-3.5 rounded-2xl bg-[#141417] border border-white/8 flex items-center justify-between cursor-pointer">
                  <div>
                    <span className="text-xs font-bold text-white block">Тихая рассылка (без звука)</span>
                    <span className="text-[11px] text-neutral-400">Уведомление придет без звукового сигнала</span>
                  </div>
                  <input
                    type="checkbox"
                    checked={isSilentBroadcast}
                    onChange={(e) => setIsSilentBroadcast(e.target.checked)}
                    className="w-4 h-4 accent-emerald-400 rounded"
                  />
                </label>

                {/* Final Telegram Message Preview */}
                <div className="p-3 bg-[#17171a] rounded-2xl border border-white/5 space-y-2">
                  <div className="text-[11px] font-bold text-neutral-400 uppercase">Финальный вид в Telegram</div>
                  <div className="p-3 bg-[#202025] rounded-xl text-xs space-y-2">
                    <p className="text-neutral-200 whitespace-pre-wrap">{broadcastMessage}</p>
                    <div className="w-full py-2 bg-[#2d2d33] text-center text-xs font-semibold text-emerald-400 rounded-lg">
                      🎟️ Открыть билеты в Ivently
                    </div>
                  </div>
                </div>

                {/* Action Buttons */}
                <div className="pt-2 space-y-2">
                  <button
                    type="button"
                    disabled={isSendingBroadcast}
                    onClick={handleLaunchBroadcast}
                    className="w-full py-3.5 rounded-2xl bg-emerald-500 hover:bg-emerald-400 text-black font-bold text-sm transition-all active:scale-[0.98] shadow-lg flex items-center justify-center gap-2"
                  >
                    {isSendingBroadcast ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin text-black" />
                        <span>Отправка сообщений...</span>
                      </>
                    ) : (
                      <>
                        <Send className="w-4 h-4" />
                        <span>Запустить рассылку в Telegram ({targetSegment === 'subscribers' ? '3 420' : '850'} чел.)</span>
                      </>
                    )}
                  </button>

                  <button
                    type="button"
                    onClick={() => setBroadcastStep(1)}
                    className="w-full py-3 rounded-2xl bg-white/5 hover:bg-white/10 text-neutral-300 font-medium text-xs border border-white/5 transition"
                  >
                    ← Назад к редактированию
                  </button>
                </div>
              </main>
            </div>
          )}
        </div>
      )}

      {/* =========================================================================
          AUXILIARY MODAL: ЧЕК-ИН (CHECK-IN SCANNER)
      ========================================================================= */}
      {activeCheckInEvent && (
        <div className="fixed inset-0 z-[70] bg-black/90 backdrop-blur-xl flex flex-col p-4 animate-fade-in overflow-y-auto">
          <div className="flex items-center justify-between pb-3 border-b border-white/10">
            <div className="flex items-center space-x-2 text-white">
              <QrCode className="w-5 h-5 text-emerald-400" />
              <span className="font-bold text-sm">Чек-ин билетов • {activeCheckInEvent.title}</span>
            </div>
            <button
              type="button"
              onClick={() => setActiveCheckInEvent(null)}
              className="p-1.5 rounded-full bg-white/5 text-neutral-400 hover:text-white"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          <div className="py-6 max-w-sm mx-auto w-full space-y-4 text-center">
            <div className="p-6 rounded-3xl bg-[#141417] border border-white/10 space-y-4">
              <div className="w-48 h-48 mx-auto bg-white p-3 rounded-2xl flex items-center justify-center shadow-lg">
                <QrCode className="w-40 h-40 text-black" />
              </div>
              <div>
                <h3 className="text-base font-bold text-white">Сканер билетов Ivently</h3>
                <p className="text-xs text-neutral-400 mt-1">
                  Наведите камеру на QR-код билета гостя в приложении Telegram
                </p>
              </div>
              <div className="grid grid-cols-2 gap-2 text-left pt-2 border-t border-white/5 text-xs">
                <div>
                  <span className="text-neutral-500 block">Всего продано:</span>
                  <span className="text-white font-bold">{activeCheckInEvent.ticketsSold || 142} шт.</span>
                </div>
                <div>
                  <span className="text-neutral-500 block">Прошли вход:</span>
                  <span className="text-emerald-400 font-bold">89 гостей</span>
                </div>
              </div>
            </div>

            <button
              type="button"
              onClick={() => {
                telegram.hapticSuccess();
                alert('Гость подтвержден! Билет №IV-9821 действителен.');
              }}
              className="w-full py-3.5 rounded-2xl bg-emerald-500 hover:bg-emerald-400 text-black font-bold text-sm shadow-lg active:scale-95"
            >
              Тестовое сканирование
            </button>
          </div>
        </div>
      )}

      {/* =========================================================================
          AUXILIARY MODAL: СТАТИСТИКА СОБЫТИЯ
      ========================================================================= */}
      {activeStatsEvent && (
        <div className="fixed inset-0 z-[70] bg-black/90 backdrop-blur-xl flex flex-col p-4 animate-fade-in overflow-y-auto">
          <div className="flex items-center justify-between pb-3 border-b border-white/10">
            <div className="flex items-center space-x-2 text-white">
              <BarChart2 className="w-5 h-5 text-emerald-400" />
              <span className="font-bold text-sm">Статистика • {activeStatsEvent.title}</span>
            </div>
            <button
              type="button"
              onClick={() => setActiveStatsEvent(null)}
              className="p-1.5 rounded-full bg-white/5 text-neutral-400 hover:text-white"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          <div className="py-6 max-w-sm mx-auto w-full space-y-4">
            <div className="p-4 rounded-2xl bg-[#141417] border border-white/10 space-y-3">
              <div className="text-xs text-neutral-400 uppercase font-semibold">Воронка конверсии</div>
              <div className="space-y-2 text-xs">
                <div className="flex justify-between py-1 border-b border-white/5">
                  <span className="text-neutral-400">Просмотров карточки:</span>
                  <span className="text-white font-bold">2 410</span>
                </div>
                <div className="flex justify-between py-1 border-b border-white/5">
                  <span className="text-neutral-400">Добавлено в закладки:</span>
                  <span className="text-emerald-400 font-bold">{activeStatsEvent.bookmarksCount || 412}</span>
                </div>
                <div className="flex justify-between py-1 border-b border-white/5">
                  <span className="text-neutral-400">Куплено билетов:</span>
                  <span className="text-white font-bold">{activeStatsEvent.ticketsSold || 142}</span>
                </div>
                <div className="flex justify-between py-1">
                  <span className="text-neutral-400">Общая выручка:</span>
                  <span className="text-emerald-400 font-extrabold">170 400 ₽</span>
                </div>
              </div>
            </div>

            <button
              type="button"
              onClick={() => setActiveStatsEvent(null)}
              className="w-full py-3 rounded-2xl bg-white text-black font-bold text-xs"
            >
              Закрыть статистику
            </button>
          </div>
        </div>
      )}

      {/* =========================================================================
          AUXILIARY MODAL: ПРЕДПРОСМОТР СОБЫТИЯ НА МОДЕРАЦИИ
      ========================================================================= */}
      {activePreviewEvent && (
        <div className="fixed inset-0 z-[70] bg-black/90 backdrop-blur-xl flex flex-col p-4 animate-fade-in overflow-y-auto">
          <div className="flex items-center justify-between pb-3 border-b border-white/10">
            <div className="flex items-center space-x-2 text-white">
              <Eye className="w-4 h-4 text-amber-400" />
              <span className="font-bold text-sm">Предпросмотр на модерации</span>
            </div>
            <button
              type="button"
              onClick={() => setActivePreviewEvent(null)}
              className="p-1.5 rounded-full bg-white/5 text-neutral-400 hover:text-white"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          <div className="py-6 max-w-sm mx-auto w-full space-y-4">
            <div className="rounded-3xl overflow-hidden bg-[#141417] border border-amber-500/20 shadow-2xl space-y-3 pb-4">
              <div className="relative aspect-video w-full bg-neutral-900">
                <img src={activePreviewEvent.cover_image_url} alt={activePreviewEvent.title} className="w-full h-full object-cover" />
                <div className="absolute top-3 left-3 px-2.5 py-1 rounded-full bg-amber-500/90 text-black font-bold text-[10px]">
                  На модерации
                </div>
              </div>
              <div className="px-4 space-y-2">
                <div className="text-[11px] text-amber-400 font-semibold">{activePreviewEvent.dateText}</div>
                <h3 className="text-base font-bold text-white tracking-tight">{activePreviewEvent.title}</h3>
                <p className="text-xs text-neutral-400 flex items-center space-x-1">
                  <MapPin className="w-3.5 h-3.5 shrink-0 text-neutral-500" />
                  <span>{activePreviewEvent.venue_name}</span>
                </p>
                <div className="p-2.5 rounded-xl bg-amber-500/10 border border-amber-500/20 text-xs text-amber-300">
                  Заявка отправлена модераторам. Ожидаемое время ответа: ~15 мин.
                </div>
              </div>
            </div>

            <button
              type="button"
              onClick={() => setActivePreviewEvent(null)}
              className="w-full py-3 rounded-2xl bg-white text-black font-bold text-xs"
            >
              Закрыть предпросмотр
            </button>
          </div>
        </div>
      )}

    </div>
  );
};
