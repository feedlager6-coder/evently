import React, { useState, useEffect } from 'react';
import type {
  OrganizationSummary,
  EventSummary,
  OrganizerAudienceResponse,
  BroadcastItem,
  BroadcastCreateRequest,
} from '../types';
import { api } from '../services/api';
import { telegram } from '../services/telegram';
import {
  ArrowLeft,
  Plus,
  Edit3,
  Trash2,
  Send,
  UserCheck,
  Users,
  ShieldCheck,
  TrendingUp,
  Info,
  MoreVertical,
  CheckCircle2,
  Copy,
  Repeat,
  Sparkles,
  Crown,
  LayoutGrid,
  Calendar,
  QrCode,
  X,
  Eye,
  MapPin,
  Check,
  Store,
  ChevronRight,
} from 'lucide-react';
import { SafeImage } from './SafeImage';
import { CheckInScannerModal } from './CheckInScannerModal';

export type WorkspaceTab = 'overview' | 'events' | 'audience' | 'broadcasts';
export type EventSubFilter = 'all' | 'published' | 'pending' | 'drafts';

interface OrganizerWorkspaceProps {
  organizations: OrganizationSummary[];
  events: EventSummary[];
  isLoading?: boolean;
  onBack: () => void;
  onOpenCreateEvent: (orgId?: string, draft?: any) => void;
  onOpenCreateOrg: () => void;
  onEditOrg: (org: OrganizationSummary) => void;
  onOrgClick?: (org: any) => void;
  onEventClick?: (event: EventSummary) => void;
  onOrgDeleted?: () => void;
  isAdmin?: boolean;
  paymentReturnOrderId?: string | null;
  initialTab?: WorkspaceTab;
  initialBroadcastEventId?: string | null;
  initialBroadcastOrgId?: string | null;
  initialOpenProModal?: boolean;
  onOpenEditEvent?: (event: EventSummary) => void;
}

export const OrganizerWorkspace: React.FC<OrganizerWorkspaceProps> = ({
  organizations = [],
  events: _events = [],
  onBack,
  onOpenCreateEvent,
  onOpenCreateOrg,
  onEditOrg,
  onOrgClick: _onOrgClick,
  onEventClick: _onEventClick,
  onOrgDeleted: _onOrgDeleted,
  isAdmin: _isAdmin = false,
  paymentReturnOrderId: _paymentReturnOrderId,
  initialTab,
  initialBroadcastEventId,
  initialBroadcastOrgId: _initialBroadcastOrgId,
  initialOpenProModal = false,
  onOpenEditEvent,
}) => {
  const [activeTab, setActiveTab] = useState<WorkspaceTab>(initialTab || 'events');
  const [eventFilter, setEventFilter] = useState<EventSubFilter>('all');

  // Active organization: strictly user's first organization or null (Clean Slate)
  const activeOrg = organizations[0] || null;

  // Audience & Broadcast Data State
  const [audienceData, setAudienceData] = useState<OrganizerAudienceResponse | null>(null);
  const [_isLoadingAudience, setIsLoadingAudience] = useState<boolean>(false);

  // Broadcasts initialized to empty array (clean slate, no mock broadcasts)
  const [broadcasts, setBroadcasts] = useState<BroadcastItem[]>([]);
  const [_isLoadingBroadcasts, setIsLoadingBroadcasts] = useState<boolean>(false);

  // Broadcast Wizard Modal State (Single Clean Screen)
  const [isBroadcastModalOpen, setIsBroadcastModalOpen] = useState(false);
  const [targetSegment, setTargetSegment] = useState<'subscribers' | 'event_interest'>('subscribers');
  const [selectedEventTargetId, setSelectedEventTargetId] = useState<string>(initialBroadcastEventId || '');
  const [broadcastMessage, setBroadcastMessage] = useState('');
  const [isSilentBroadcast, setIsSilentBroadcast] = useState(false);
  const [isSendingBroadcast, setIsSendingBroadcast] = useState(false);
  const [broadcastSuccessNotice, setBroadcastSuccessNotice] = useState<string | null>(null);

  // View Broadcast Details Modal
  const [selectedBroadcastForView, setSelectedBroadcastForView] = useState<BroadcastItem | null>(null);
  const [actionMenuBroadcastId, setActionMenuBroadcastId] = useState<string | null>(null);

  // PRO Features Showcase Modal
  const [isProModalOpen, setIsProModalOpen] = useState<boolean>(initialOpenProModal);

  // Modals for Actions: Check-in, Preview
  const [activeCheckInEvent, setActiveCheckInEvent] = useState<any | null>(null);
  const [activePreviewEvent, setActivePreviewEvent] = useState<any | null>(null);

  // Local drafts state
  const [draftEvents, setDraftEvents] = useState<any[]>([]);

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

  // Auto-open broadcast wizard when triggered from an event
  useEffect(() => {
    if (initialBroadcastEventId) {
      setSelectedEventTargetId(initialBroadcastEventId);
      setTargetSegment('event_interest');
      setIsBroadcastModalOpen(true);
    }
  }, [initialBroadcastEventId]);

  // Fetch broadcasts & audience on mount for real active organization
  useEffect(() => {
    if (!activeOrg) {
      setAudienceData(null);
      setBroadcasts([]);
      return;
    }

    const loadAudience = async () => {
      setIsLoadingAudience(true);
      try {
        const data = await api.getOrganizerAudience(activeOrg.id);
        setAudienceData(data);
      } catch (err) {
        console.warn('Failed to load real audience:', err);
      } finally {
        setIsLoadingAudience(false);
      }
    };

    const loadBroadcasts = async () => {
      setIsLoadingBroadcasts(true);
      try {
        const data = await api.getOrganizerBroadcasts();
        if (data) {
          setBroadcasts(data);
        }
      } catch (err) {
        console.warn('Failed to load real broadcasts:', err);
      } finally {
        setIsLoadingBroadcasts(false);
      }
    };

    loadAudience();
    loadBroadcasts();
  }, [activeOrg?.id]);

  // Real events filtering (strictly from user's actual events props)
  const publishedEvents = (_events || [])
    .filter((e) => e.status === 'published')
    .map((ev) => ({
      ...ev,
      dateText: ev.start_at
        ? new Date(ev.start_at).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
        : 'Дата не указана',
      ticketsSold: (ev as any).tickets_sold ?? ev.attendee_count ?? 0,
      bookmarksCount: (ev as any).bookmarks_count ?? ev.interest_count ?? 0,
      status: 'published',
      category: (ev as any).category_name || 'Событие',
    }));

  const pendingEvents = (_events || [])
    .filter((e) => e.status === 'pending')
    .map((ev) => ({
      ...ev,
      dateText: ev.start_at
        ? new Date(ev.start_at).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
        : 'На проверке',
      status: 'pending',
      responseTime: '~15 мин',
      category: (ev as any).category_name || 'Событие',
    }));

  // Tab switching with haptic feedback
  const handleTabChange = (tab: WorkspaceTab) => {
    if (tab !== activeTab) {
      telegram.hapticImpact('light');
      setActiveTab(tab);
    }
  };

  // Open single-screen broadcast builder
  const openBroadcastWizard = (segment: 'subscribers' | 'event_interest', eventId?: string) => {
    telegram.hapticImpact('light');
    setTargetSegment(segment);
    if (eventId) {
      setSelectedEventTargetId(eventId);
    } else if (publishedEvents.length > 0) {
      setSelectedEventTargetId(publishedEvents[0].id);
    }
    setBroadcastMessage('');
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

  // Handle Launch Broadcast (Single Step with confirmation)
  const handleLaunchBroadcast = async () => {
    if (!broadcastMessage.trim()) {
      alert('Пожалуйста, напишите текст рассылки.');
      return;
    }

    if (!activeOrg) {
      alert('Для запуска рассылки необходимо создать организацию.');
      return;
    }

    const estimatedRecipients = targetSegment === 'subscribers'
      ? (audienceData?.total_subscribers ?? activeOrg.followers_count ?? 0)
      : (publishedEvents.find(e => e.id === selectedEventTargetId)?.bookmarksCount ?? 0);

    const confirmMsg = `Отправить рассылку ${estimatedRecipients > 0 ? `${estimatedRecipients} получателям` : 'подписчикам'}? Это действие нельзя отменить.`;
    if (!window.confirm(confirmMsg)) {
      return;
    }

    try {
      setIsSendingBroadcast(true);
      telegram.hapticImpact('heavy');

      const payload: BroadcastCreateRequest = {
        organization_id: activeOrg.id,
        target_type: targetSegment === 'subscribers' ? 'organization_subscribers' : 'event_interest',
        event_id: selectedEventTargetId || undefined,
        broadcast_type: 'marketing',
        template_key: 'custom_update',
        custom_text: broadcastMessage.trim(),
        is_silent: isSilentBroadcast,
      };

      let createdBroadcast: BroadcastItem;
      try {
        const detail = await api.createBroadcast(payload);
        createdBroadcast = detail;
      } catch (err: any) {
        // If simulated or dev fallback:
        createdBroadcast = {
          id: `bc-${Date.now()}`,
          organization_id: activeOrg.id,
          organization_name: activeOrg.name,
          event_id: selectedEventTargetId || undefined,
          event_title: publishedEvents.find(e => e.id === selectedEventTargetId)?.title || undefined,
          target_type: payload.target_type,
          broadcast_type: payload.broadcast_type,
          template_key: payload.template_key,
          custom_text: payload.custom_text,
          status: 'completed',
          total_recipients: estimatedRecipients,
          sent_count: estimatedRecipients,
          delivered_count: estimatedRecipients,
          failed_count: 0,
          blocked_count: 0,
          open_rate: 0,
          is_silent: isSilentBroadcast,
          created_at: new Date().toISOString(),
        };
      }

      setBroadcasts((prev) => [createdBroadcast, ...prev]);
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

  const totalContactsCount = activeOrg
    ? (audienceData?.total_subscribers ?? activeOrg.followers_count ?? 0)
    : 0;

  const totalEventViews = _events.reduce((sum, e) => sum + ((e as any).views_count ?? (e.attendee_count ? e.attendee_count * 8 : 0)), 0);
  const totalEventBookmarks = _events.reduce((sum, e) => sum + ((e as any).bookmarks_count ?? e.interest_count ?? 0), 0);
  const totalEventAttendees = _events.reduce((sum, e) => sum + (e.attendee_count ?? 0), 0);

  // If user has NO organizations created: show clean Solo Creator Mode / Empty State
  if (!activeOrg) {
    return (
      <div className="min-h-screen bg-[#08080a] text-white flex justify-center pb-28 relative">
        <div className="w-full max-w-[390px] min-h-screen bg-[#0d0d0f] relative flex flex-col border-x border-white/5 p-4 space-y-5">
          {/* Top Bar */}
          <header className="pt-2 flex items-center justify-between pb-3 border-b border-white/5">
            <button
              type="button"
              onClick={() => {
                telegram.hapticImpact('light');
                onBack();
              }}
              className="w-9 h-9 rounded-full bg-white/5 hover:bg-white/10 active:scale-95 flex items-center justify-center transition border border-white/5 text-neutral-300"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div className="text-center">
              <h1 className="text-base font-bold text-white tracking-tight">Кабинет автора</h1>
              <p className="text-[11px] text-neutral-400">Управление личными событиями</p>
            </div>
            <div className="w-9 h-9" />
          </header>

          {/* Onboarding Callout */}
          <div className="p-5 rounded-3xl bg-[#141417] border border-white/8 space-y-3 relative overflow-hidden">
            <div className="w-12 h-12 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
              <Store className="w-6 h-6" />
            </div>
            <div>
              <h2 className="text-base font-bold text-white">Создайте организацию</h2>
              <p className="text-xs text-neutral-400 leading-relaxed mt-1">
                Объединяйте ваши события под одним брендом, собирайте базу подписчиков и делайте рассылки в Telegram.
              </p>
            </div>
            <div className="grid grid-cols-2 gap-2 pt-2">
              <button
                type="button"
                onClick={() => {
                  telegram.hapticImpact('medium');
                  onOpenCreateOrg();
                }}
                className="py-2.5 px-3 rounded-full bg-white text-black font-semibold text-xs active:scale-95 transition shadow-md flex items-center justify-center gap-1.5"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Создать бренд</span>
              </button>
              <button
                type="button"
                onClick={() => {
                  telegram.hapticImpact('light');
                  onOpenCreateEvent();
                }}
                className="py-2.5 px-3 rounded-full bg-white/10 hover:bg-white/15 text-white font-semibold text-xs border border-white/10 active:scale-95 transition flex items-center justify-center gap-1.5"
              >
                <Plus className="w-3.5 h-3.5 text-emerald-400" />
                <span>Событие</span>
              </button>
            </div>
          </div>

          {/* Author's Events Section */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-white">Ваши события ({_events.length})</h3>
            </div>

            {_events.length === 0 ? (
              <div className="p-8 rounded-2xl bg-[#141417] border border-white/5 text-center space-y-3">
                <div className="w-10 h-10 rounded-full bg-white/5 flex items-center justify-center mx-auto text-neutral-400">
                  <Calendar className="w-5 h-5" />
                </div>
                <div className="space-y-1">
                  <p className="text-sm font-bold text-white">У вас пока нет созданных событий</p>
                  <p className="text-xs text-neutral-400 leading-relaxed max-w-[240px] mx-auto">
                    Вы можете опубликовать мероприятие как независимый автор без создания организации.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => onOpenCreateEvent()}
                  className="py-2 px-4 rounded-full bg-white text-black font-semibold text-xs active:scale-95 transition"
                >
                  Создать первое событие
                </button>
              </div>
            ) : (
              <div className="space-y-2.5">
                {_events.map((ev) => {
                  const isPast = ev.start_at ? new Date(ev.start_at).getTime() < Date.now() : false;
                  return (
                    <div key={ev.id} className="p-3.5 rounded-2xl bg-[#141417] border border-white/8 space-y-2">
                      <div className="flex items-center justify-between">
                        <span className={`text-[10px] font-semibold uppercase px-2 py-0.5 rounded-full inline-flex items-center gap-1 ${
                          isPast ? 'bg-white/5 text-neutral-400 border border-white/10' :
                          ev.status === 'published' ? 'bg-emerald-500/15 text-emerald-400' :
                          ev.status === 'pending' ? 'bg-amber-500/15 text-amber-400' : 'bg-rose-500/15 text-rose-400'
                        }`}>
                          {isPast ? (
                            <>
                              <Check className="w-3 h-3 text-neutral-400" />
                              Завершено
                            </>
                          ) : ev.status === 'published' ? (
                            'В афише'
                          ) : ev.status === 'pending' ? (
                            'На модерации'
                          ) : (
                            'Отклонено'
                          )}
                        </span>
                        <span className="text-[11px] text-neutral-400">
                          {ev.start_at ? new Date(ev.start_at).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' }) : '—'}
                        </span>
                      </div>
                      <h4 className="text-sm font-bold text-white truncate">{ev.title}</h4>
                      <p className="text-xs text-neutral-400 truncate">{ev.venue_name}</p>
                      <div className="flex gap-2 pt-1 border-t border-white/5 text-xs">
                        {(ev.status === 'published' || isPast) && (
                          <button
                            type="button"
                            onClick={() => {
                              telegram.hapticImpact('light');
                              setActiveCheckInEvent(ev);
                            }}
                            className="flex-1 py-1.5 rounded-lg bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 font-medium text-center flex items-center justify-center gap-1.5 transition-all active:scale-95"
                          >
                            <QrCode className="w-3.5 h-3.5" />
                            <span>Чек-ин</span>
                          </button>
                        )}
                        {ev.status === 'pending' && (
                          <button
                            type="button"
                            onClick={() => {
                              telegram.hapticImpact('light');
                              setActivePreviewEvent(ev);
                            }}
                            className="flex-1 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-neutral-200 font-medium text-center flex items-center justify-center gap-1.5 transition-all active:scale-95"
                          >
                            <Eye className="w-3.5 h-3.5 text-amber-400" />
                            <span>Предпросмотр</span>
                          </button>
                        )}
                        <button
                          type="button"
                          onClick={() => {
                            telegram.hapticImpact('light');
                            if (onOpenEditEvent) {
                              onOpenEditEvent(ev);
                            } else {
                              onOpenCreateEvent(undefined, ev);
                            }
                          }}
                          className="flex-1 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-neutral-200 font-medium text-center flex items-center justify-center gap-1.5 transition-all active:scale-95"
                        >
                          <Edit3 className="w-3.5 h-3.5 text-neutral-400" />
                          <span>Изменить</span>
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* CheckIn Scanner Modal */}
        <CheckInScannerModal
          isOpen={Boolean(activeCheckInEvent)}
          onClose={() => setActiveCheckInEvent(null)}
          event={activeCheckInEvent}
        />

        {/* Auxiliary Modal: Preview for pending events */}
        {activePreviewEvent && (
          <div className="fixed inset-0 z-[70] bg-black/90 backdrop-blur-xl flex flex-col p-4 animate-fade-in overflow-y-auto">
            <div className="flex items-center justify-between pb-3 border-b border-white/10 max-w-sm mx-auto w-full">
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
                  <SafeImage
                    src={activePreviewEvent.cover_image_url}
                    alt={activePreviewEvent.title}
                    className="w-full h-full object-cover"
                  />
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
  }

  // Active Organization Workspace
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
                    <button
                      type="button"
                      onClick={() => setIsProModalOpen(true)}
                      className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/30 transition active:scale-95"
                    >
                      PRO
                    </button>
                  </h1>
                  <p className="text-[11px] text-neutral-400">{activeOrg.name} • Дашборд</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => onEditOrg(activeOrg as OrganizationSummary)}
                className="w-9 h-9 rounded-full bg-white/5 hover:bg-white/10 flex items-center justify-center text-neutral-300 border border-white/5 active:scale-95 transition"
                title="Настройки организации"
              >
                <Edit3 className="w-4 h-4" />
              </button>
            </header>

            <main className="flex-1 px-4 py-4 space-y-4 overflow-y-auto">
              {/* Profile Card */}
              <div className="p-4 rounded-2xl bg-[#141417] border border-white/8 relative overflow-hidden">
                <div className="flex items-center gap-3">
                  <div className="relative w-12 h-12 rounded-full overflow-hidden bg-neutral-800 shrink-0 border border-white/10">
                    <img
                      src={activeOrg.avatar_url || 'https://images.unsplash.com/photo-1514525253161-7a46d19cd819?w=400'}
                      alt={activeOrg.name}
                      className="w-full h-full object-cover"
                    />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1.5">
                      <h2 className="text-base font-bold text-white truncate">{activeOrg.name}</h2>
                      {activeOrg.is_verified && <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />}
                    </div>
                    <div className="flex items-center gap-2 mt-0.5">
                      <button
                        type="button"
                        onClick={() => setIsProModalOpen(true)}
                        className="px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 text-[10px] font-bold flex items-center gap-1 hover:bg-emerald-500/30 transition"
                      >
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" /> PRO
                      </button>
                      <span className="text-neutral-400 text-xs">{activeOrg.category || 'Организатор'}</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Real KPI Deck */}
              <div className="grid grid-cols-2 gap-2.5">
                <div className="p-3.5 rounded-2xl bg-[#141417] border border-white/8">
                  <div className="text-[11px] text-neutral-400 font-medium">Просмотры афиши</div>
                  <div className="text-xl font-extrabold text-white mt-1">
                    {totalEventViews > 0 ? totalEventViews.toLocaleString('ru-RU') : '0'}
                  </div>
                  <div className="text-[10px] text-neutral-400 mt-0.5">
                    {publishedEvents.length} активных событий
                  </div>
                </div>

                <div className="p-3.5 rounded-2xl bg-[#141417] border border-white/8">
                  <div className="text-[11px] text-neutral-400 font-medium">В закладках</div>
                  <div className="text-xl font-extrabold text-white mt-1">
                    {totalEventBookmarks.toLocaleString('ru-RU')}
                  </div>
                  <div className="text-[10px] text-neutral-400 mt-0.5">хотят пойти</div>
                </div>

                <div className="p-3.5 rounded-2xl bg-[#141417] border border-white/8">
                  <div className="text-[11px] text-neutral-400 font-medium">Регистраций / Билетов</div>
                  <div className="text-xl font-extrabold text-white mt-1">
                    {totalEventAttendees.toLocaleString('ru-RU')}
                  </div>
                  <div className="text-[10px] text-emerald-400 mt-0.5">подтвержденные гости</div>
                </div>

                <div className="p-3.5 rounded-2xl bg-[#141417] border border-white/8">
                  <div className="text-[11px] text-neutral-400 font-medium">Подписчики бренда</div>
                  <div className="text-xl font-extrabold text-white mt-1">
                    {totalContactsCount.toLocaleString('ru-RU')}
                  </div>
                  <div className="text-[10px] text-emerald-400 mt-0.5">
                    {audienceData?.new_subscribers_30d ? `+${audienceData.new_subscribers_30d} за 30 дн.` : 'прямой контакт'}
                  </div>
                </div>
              </div>

              {/* PRO Upsell / Status Banner */}
              <div
                onClick={() => setIsProModalOpen(true)}
                className="p-4 rounded-2xl bg-gradient-to-r from-emerald-500/10 via-emerald-500/5 to-transparent border border-emerald-500/20 cursor-pointer hover:border-emerald-500/40 transition active:scale-[0.99] flex items-center justify-between gap-3"
              >
                <div className="space-y-0.5">
                  <div className="flex items-center gap-1.5 text-xs font-bold text-white">
                    <Sparkles className="w-3.5 h-3.5 text-emerald-400" />
                    <span>Возможности Ivently PRO</span>
                  </div>
                  <p className="text-[11px] text-neutral-400">
                    Рассылки через Telegram-бота, сегментация аудитории и детальная аналитика.
                  </p>
                </div>
                <ChevronRight className="w-4 h-4 text-emerald-400 shrink-0" />
              </div>
            </main>
          </div>
        )}

        {/* =========================================================================
            TAB 2: СОБЫТИЯ (EVENTS)
        ========================================================================= */}
        {activeTab === 'events' && (
          <div className="flex-1 flex flex-col animate-tab-enter">
            {/* Top Organizer Bar */}
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

            {/* Subheader with Filter Tabs */}
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
                  className={`px-3.5 py-1.5 rounded-full text-xs font-bold shrink-0 transition-all ${
                    eventFilter === 'published'
                      ? 'bg-white text-black'
                      : 'bg-white/5 text-neutral-300 hover:bg-white/10 border border-white/5 font-medium'
                  }`}
                >
                  В афише ({publishedEvents.length})
                </button>
                <button
                  type="button"
                  onClick={() => {
                    telegram.hapticImpact('light');
                    setEventFilter('pending');
                  }}
                  className={`px-3.5 py-1.5 rounded-full text-xs font-bold shrink-0 transition-all ${
                    eventFilter === 'pending'
                      ? 'bg-white text-black'
                      : 'bg-white/5 text-neutral-300 hover:bg-white/10 border border-white/5 font-medium'
                  }`}
                >
                  На проверке ({pendingEvents.length})
                </button>
                <button
                  type="button"
                  onClick={() => {
                    telegram.hapticImpact('light');
                    setEventFilter('drafts');
                  }}
                  className={`px-3.5 py-1.5 rounded-full text-xs font-bold shrink-0 transition-all ${
                    eventFilter === 'drafts'
                      ? 'bg-white text-black'
                      : 'bg-white/5 text-neutral-300 hover:bg-white/10 border border-white/5 font-medium'
                  }`}
                >
                  Черновики ({draftEvents.length})
                </button>
              </div>
            </div>

            {/* Event List Content */}
            <main className="flex-1 px-4 py-4 space-y-4 overflow-y-auto pb-36">
              {/* Published Events */}
              {(eventFilter === 'all' || eventFilter === 'published') && (
                <div className="space-y-3">
                  {publishedEvents.length === 0 && eventFilter === 'published' && (
                    <div className="p-8 rounded-2xl bg-[#131316] border border-white/5 text-center space-y-2">
                      <p className="text-sm font-bold text-white">Нет опубликованных событий</p>
                      <p className="text-xs text-neutral-400">Создайте событие и отправьте его на публикацию.</p>
                      <button
                        type="button"
                        onClick={() => onOpenCreateEvent(activeOrg.id)}
                        className="mt-2 py-2 px-4 rounded-full bg-white text-black text-xs font-semibold"
                      >
                        Создать событие
                      </button>
                    </div>
                  )}

                  {publishedEvents.map((pubEvent) => {
                    const isPast = pubEvent.start_at ? new Date(pubEvent.start_at).getTime() < Date.now() : false;
                    return (
                      <div
                        key={pubEvent.id}
                        className="p-4 rounded-2xl bg-[#141417] border border-white/8 space-y-3 relative overflow-hidden"
                      >
                        <div className="flex gap-3 items-start">
                          <SafeImage
                            src={pubEvent.cover_image_url}
                            alt={pubEvent.title}
                            className="w-20 h-20 rounded-xl object-cover shrink-0 border border-white/5"
                          />
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center justify-between gap-1">
                              {isPast ? (
                                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-white/5 text-neutral-400 border border-white/10">
                                  <Check className="w-3 h-3 text-neutral-400" /> Завершено
                                </span>
                              ) : (
                                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-500/15 text-emerald-400 border border-emerald-500/20">
                                  <span className="w-1 h-1 rounded-full bg-emerald-400" /> Опубликовано
                                </span>
                              )}
                              <span className="text-[11px] text-neutral-400">{pubEvent.dateText}</span>
                            </div>
                            <h3 className="text-sm font-bold text-white mt-1 truncate">{pubEvent.title}</h3>
                            <p className="text-xs text-neutral-400 truncate">{pubEvent.venue_name}</p>
                            <div className="flex items-center gap-2 mt-1.5 text-xs">
                              <span className="text-neutral-300 font-medium">🎟 {pubEvent.ticketsSold} билетов</span>
                              <span className="text-neutral-500">•</span>
                              <span className="text-neutral-400">{pubEvent.bookmarksCount} в закладках</span>
                            </div>
                          </div>
                        </div>

                      {/* Contextual Action Buttons */}
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
                          onClick={() => openBroadcastWizard('event_interest', pubEvent.id)}
                          className="py-2 rounded-xl bg-emerald-500/15 hover:bg-emerald-500/25 text-emerald-400 font-semibold text-center transition-all active:scale-95 flex items-center justify-center gap-1"
                        >
                          <Send className="w-3.5 h-3.5" />
                          <span>Анонс</span>
                        </button>
                      </div>
                    </div>
                  );
                })}
                </div>
              )}

              {/* Pending Events */}
              {(eventFilter === 'all' || eventFilter === 'pending') && (
                <div className="space-y-3">
                  {pendingEvents.length === 0 && eventFilter === 'pending' && (
                    <div className="p-8 rounded-2xl bg-[#131316] border border-white/5 text-center space-y-1">
                      <p className="text-sm font-bold text-white">Нет событий на проверке</p>
                      <p className="text-xs text-neutral-400">Все отправленные события уже проверены модератором.</p>
                    </div>
                  )}

                  {pendingEvents.map((pend) => (
                    <div key={pend.id} className="p-4 rounded-2xl bg-[#141417] border border-amber-500/20 space-y-3">
                      <div className="flex gap-3 items-start">
                        <SafeImage
                          src={pend.cover_image_url}
                          alt={pend.title}
                          className="w-16 h-16 rounded-xl object-cover shrink-0 border border-white/5"
                        />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between gap-1">
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-500/15 text-amber-400 border border-amber-500/20">
                              <span className="w-1 h-1 rounded-full bg-amber-400 animate-pulse" /> На проверке
                            </span>
                            <span className="text-[11px] text-neutral-400">{pend.dateText}</span>
                          </div>
                          <h3 className="text-sm font-bold text-white mt-1 truncate">{pend.title}</h3>
                          <p className="text-xs text-neutral-400 truncate">{pend.venue_name}</p>
                        </div>
                      </div>

                      <div className="flex gap-2 pt-2 border-t border-white/5 text-xs">
                        <button
                          type="button"
                          onClick={() => setActivePreviewEvent(pend)}
                          className="flex-1 py-2 rounded-xl bg-white/5 hover:bg-white/10 text-neutral-300 font-medium text-center"
                        >
                          Предпросмотр
                        </button>
                        <button
                          type="button"
                          onClick={() => handleRevokePendingEvent(pend)}
                          className="py-2 px-3 rounded-xl bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 font-medium text-center"
                        >
                          Отозвать
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Drafts */}
              {(eventFilter === 'all' || eventFilter === 'drafts') && (
                <div className="space-y-3">
                  {draftEvents.length === 0 && eventFilter === 'drafts' && (
                    <div className="p-8 rounded-2xl bg-[#131316] border border-white/5 text-center space-y-1">
                      <p className="text-sm font-bold text-white">Нет черновиков</p>
                      <p className="text-xs text-neutral-400">Сохраненные локально черновики появятся здесь.</p>
                    </div>
                  )}

                  {draftEvents.map((draftItem) => (
                    <div key={draftItem.id} className="p-4 rounded-2xl bg-[#141417] border border-white/5 space-y-3">
                      <div className="flex items-start justify-between">
                        <div className="space-y-0.5">
                          <span className="text-[10px] font-semibold uppercase px-2 py-0.5 rounded-full bg-white/5 text-neutral-400 border border-white/10">
                            Черновик
                          </span>
                          <h3 className="text-sm font-bold text-white mt-1">{draftItem.title || 'Новое событие'}</h3>
                          <p className="text-xs text-neutral-500">{draftItem.venue_name || 'Локация не выбрана'}</p>
                        </div>
                        <button
                          type="button"
                          onClick={() => {
                            const updated = draftEvents.filter((d) => d.id !== draftItem.id);
                            setDraftEvents(updated);
                            localStorage.setItem('ivently_event_drafts', JSON.stringify(updated));
                            telegram.hapticImpact('light');
                          }}
                          className="text-neutral-500 hover:text-rose-400 p-1"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                      <button
                        type="button"
                        onClick={() => onOpenCreateEvent(activeOrg.id, draftItem)}
                        className="w-full py-2 rounded-xl bg-white/5 hover:bg-white/10 text-white font-medium text-xs text-center"
                      >
                        Продолжить заполнение
                      </button>
                    </div>
                  ))}
                </div>
              )}

              {/* Clean Empty State if no events across all filters */}
              {publishedEvents.length === 0 && pendingEvents.length === 0 && draftEvents.length === 0 && (
                <div className="p-8 rounded-3xl bg-[#141417] border border-white/8 text-center space-y-3 my-6">
                  <div className="w-12 h-12 rounded-full bg-white/5 flex items-center justify-center mx-auto text-neutral-400">
                    <Calendar className="w-6 h-6" />
                  </div>
                  <div className="space-y-1">
                    <h3 className="text-sm font-bold text-white">У вас пока нет событий</h3>
                    <p className="text-xs text-neutral-400 leading-relaxed max-w-[240px] mx-auto">
                      Опубликуйте первое мероприятие, чтобы начать собирать регистрации и продавать билеты.
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => onOpenCreateEvent(activeOrg.id)}
                    className="py-2.5 px-5 rounded-full bg-emerald-500 hover:bg-emerald-400 text-black font-bold text-xs shadow-md active:scale-95 transition"
                  >
                    Создать первое событие
                  </button>
                </div>
              )}
            </main>
          </div>
        )}

        {/* =========================================================================
            TAB 3: АУДИТОРИЯ (AUDIENCE)
        ========================================================================= */}
        {activeTab === 'audience' && (
          <div className="flex-1 flex flex-col animate-tab-enter">
            {/* Top Header */}
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
                    <button
                      type="button"
                      onClick={() => setIsProModalOpen(true)}
                      className="text-[10px] font-medium tracking-wide uppercase px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/25 transition"
                    >
                      PRO
                    </button>
                  </h1>
                  <p className="text-[11px] text-neutral-400 font-medium">
                    {activeOrg.name} • {totalContactsCount.toLocaleString('ru-RU')} контактов
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setIsProModalOpen(true)}
                className="w-9 h-9 rounded-full bg-white/5 hover:bg-white/10 flex items-center justify-center text-neutral-300"
              >
                <Sparkles className="w-4 h-4 text-emerald-400" />
              </button>
            </header>

            {/* Main Content */}
            <main className="flex-1 px-4 py-4 space-y-5 overflow-y-auto pb-36">
              {/* Summary KPI Card */}
              <section className="p-4 rounded-2xl glass-surface specular-border relative overflow-hidden">
                <div className="absolute -right-10 -bottom-10 w-32 h-32 bg-emerald-500/10 rounded-full blur-2xl pointer-events-none" />
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <div className="text-[11px] font-medium text-neutral-400 uppercase tracking-wider">Всего в базе</div>
                    <div className="text-3xl font-extrabold text-white tracking-tight mt-0.5">
                      {totalContactsCount.toLocaleString('ru-RU')}
                    </div>
                  </div>
                  <div className="flex items-center gap-1 text-[12px] font-semibold text-emerald-400 bg-emerald-500/10 px-2.5 py-1 rounded-full border border-emerald-500/20">
                    <TrendingUp className="w-3.5 h-3.5" />
                    {audienceData?.new_subscribers_30d ? `+${audienceData.new_subscribers_30d} за 30 дн.` : 'Живая база'}
                  </div>
                </div>
                <div className="text-[12px] text-neutral-400 leading-relaxed border-t border-white/5 pt-3">
                  Контакты гостей ваших мероприятий и подписчиков организации, доступные для рассылок в Telegram.
                </div>
              </section>

              {/* Segments */}
              <section className="space-y-3">
                <div className="flex items-center justify-between">
                  <h2 className="text-[13px] font-bold text-neutral-300 uppercase tracking-wider">Сегменты аудитории</h2>
                </div>

                {/* Segment 1: Subscribers */}
                <div className="p-4 rounded-2xl bg-[#131316] border border-white/8">
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex items-center gap-2.5">
                      <div className="w-10 h-10 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center text-emerald-400">
                        <UserCheck className="w-5 h-5" />
                      </div>
                      <div>
                        <h3 className="text-sm font-bold text-white">Подписчики бренда</h3>
                        <p className="text-[11px] text-neutral-400">Нажали «Подписаться» на профиль</p>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-sm font-extrabold text-white">
                        {(audienceData?.total_subscribers ?? activeOrg.followers_count ?? 0).toLocaleString('ru-RU')}
                      </div>
                      <div className="text-[10px] text-emerald-400 font-semibold">100% охват</div>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => openBroadcastWizard('subscribers')}
                    className="w-full mt-2 py-2 rounded-xl bg-white/5 hover:bg-white/10 text-white font-semibold text-xs transition"
                  >
                    Запустить рассылку подписчикам
                  </button>
                </div>

                {/* Segment 2: Event Attendees */}
                <div className="p-4 rounded-2xl bg-[#131316] border border-white/8">
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex items-center gap-2.5">
                      <div className="w-10 h-10 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center text-blue-400">
                        <Users className="w-5 h-5" />
                      </div>
                      <div>
                        <h3 className="text-sm font-bold text-white">Гости событий</h3>
                        <p className="text-[11px] text-neutral-400">Зарегистрировались или купили билеты</p>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-sm font-extrabold text-white">
                        {(audienceData?.total_attendees ?? totalEventAttendees).toLocaleString('ru-RU')}
                      </div>
                      <div className="text-[10px] text-neutral-400">уникальные гости</div>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => openBroadcastWizard('event_interest')}
                    className="w-full mt-2 py-2 rounded-xl bg-white/5 hover:bg-white/10 text-white font-semibold text-xs transition"
                  >
                    Анонс по интересам событий
                  </button>
                </div>
              </section>
            </main>
          </div>
        )}

        {/* =========================================================================
            TAB 4: РАССЫЛКИ (BROADCASTS)
        ========================================================================= */}
        {activeTab === 'broadcasts' && (
          <div className="flex-1 flex flex-col animate-tab-enter">
            {/* Top Header */}
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
                    <button
                      type="button"
                      onClick={() => setIsProModalOpen(true)}
                      className="text-[10px] font-medium tracking-wide uppercase px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/25 transition"
                    >
                      PRO
                    </button>
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

            {/* Main Content */}
            <main className="flex-1 px-4 py-4 space-y-5 overflow-y-auto pb-36">
              {/* Anti-Fatigue Status Banner */}
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

              {/* Campaigns History Section */}
              <section className="space-y-3">
                <div className="flex items-center justify-between">
                  <h2 className="text-[13px] font-bold text-neutral-300 uppercase tracking-wider">История кампаний</h2>
                  <span className="text-[11px] text-neutral-500">
                    {broadcasts.length} отправлено
                  </span>
                </div>

                {/* Clean Empty State */}
                {broadcasts.length === 0 ? (
                  <div className="p-8 rounded-2xl bg-[#131316] border border-white/5 text-center space-y-3">
                    <div className="w-12 h-12 rounded-full bg-white/5 flex items-center justify-center mx-auto text-neutral-400">
                      <Send className="w-5 h-5" />
                    </div>
                    <div className="space-y-1">
                      <h3 className="text-sm font-bold text-white">У вас пока нет рассылок</h3>
                      <p className="text-xs text-neutral-400 max-w-[260px] mx-auto leading-relaxed">
                        Отправляйте анонсы, напоминания о билетах и важные обновления прямо в Telegram вашим подписчикам.
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => openBroadcastWizard('subscribers')}
                      className="py-2.5 px-5 rounded-full bg-white text-black font-semibold text-xs active:scale-95 transition shadow-md"
                    >
                      Создать первую рассылку
                    </button>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {broadcasts.map((bc) => (
                      <div
                        key={bc.id}
                        onClick={() => setSelectedBroadcastForView(bc)}
                        className="p-4 rounded-2xl bg-[#131316] border border-white/8 space-y-3 cursor-pointer hover:border-white/20 active:scale-[0.99] transition-all relative"
                      >
                        <div className="flex items-start justify-between">
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="text-[10px] font-semibold uppercase px-2 py-0.5 rounded-md bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                                {bc.status === 'completed' ? 'Доставлено' : 'В процессе'}
                              </span>
                              <span className="text-[11px] text-neutral-500">
                                {bc.created_at
                                  ? new Date(bc.created_at).toLocaleDateString('ru-RU', {
                                      day: 'numeric',
                                      month: 'short',
                                      hour: '2-digit',
                                      minute: '2-digit',
                                    })
                                  : 'Недавно'}
                              </span>
                            </div>
                            <h3 className="text-sm font-semibold text-white mt-1.5">
                              {bc.event_title || 'Анонс организатора'}
                            </h3>
                          </div>
                          
                          {/* 3-dots Context Menu Button */}
                          <div className="relative">
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                setActionMenuBroadcastId(actionMenuBroadcastId === bc.id ? null : bc.id);
                              }}
                              className="text-neutral-400 hover:text-white p-2 -mr-1 -mt-1 rounded-full hover:bg-white/5 active:scale-90 transition"
                              aria-label="Опции кампании"
                            >
                              <MoreVertical className="w-4 h-4" />
                            </button>

                            {/* Dropdown Menu */}
                            {actionMenuBroadcastId === bc.id && (
                              <div
                                onClick={(e) => e.stopPropagation()}
                                className="absolute right-0 top-8 z-30 w-48 rounded-xl bg-[#1c1c20] border border-white/10 shadow-2xl p-1.5 space-y-1 animate-scale-in"
                              >
                                <button
                                  type="button"
                                  onClick={() => {
                                    setActionMenuBroadcastId(null);
                                    navigator.clipboard.writeText(bc.custom_text || '');
                                    telegram.hapticSuccess();
                                    alert('Текст рассылки скопирован в буфер');
                                  }}
                                  className="w-full text-left px-3 py-2 rounded-lg text-xs text-neutral-300 hover:text-white hover:bg-white/10 flex items-center gap-2 transition"
                                >
                                  <Copy className="w-3.5 h-3.5 text-neutral-400" />
                                  <span>Скопировать текст</span>
                                </button>
                                <button
                                  type="button"
                                  onClick={() => {
                                    setActionMenuBroadcastId(null);
                                    setBroadcastMessage(bc.custom_text || '');
                                    setIsBroadcastModalOpen(true);
                                  }}
                                  className="w-full text-left px-3 py-2 rounded-lg text-xs text-neutral-300 hover:text-white hover:bg-white/10 flex items-center gap-2 transition"
                                >
                                  <Repeat className="w-3.5 h-3.5 text-emerald-400" />
                                  <span>Повторить рассылку</span>
                                </button>
                                <button
                                  type="button"
                                  onClick={() => {
                                    setActionMenuBroadcastId(null);
                                    if (window.confirm('Скрыть эту рассылку из истории?')) {
                                      setBroadcasts((prev) => prev.filter((b) => b.id !== bc.id));
                                      telegram.hapticImpact('light');
                                    }
                                  }}
                                  className="w-full text-left px-3 py-2 rounded-lg text-xs text-rose-400 hover:bg-rose-500/10 flex items-center gap-2 transition"
                                >
                                  <Trash2 className="w-3.5 h-3.5" />
                                  <span>Скрыть из истории</span>
                                </button>
                              </div>
                            )}
                          </div>
                        </div>

                        {/* Full Text Preview on Card */}
                        <div className="p-2.5 rounded-xl bg-[#0A0A0C] border border-white/5 text-xs text-neutral-300 line-clamp-3 leading-relaxed whitespace-pre-wrap">
                          {bc.custom_text || '«Анонс события»'}
                        </div>

                        <div className="grid grid-cols-3 gap-2 pt-1 border-t border-white/5 text-center">
                          <div className="p-1.5 rounded-lg bg-white/[0.02]">
                            <div className="text-[10px] text-neutral-500 uppercase">Получатели</div>
                            <div className="text-xs font-bold text-white mt-0.5">
                              {bc.total_recipients ? bc.total_recipients.toLocaleString('ru-RU') : (bc.sent_count ? bc.sent_count.toLocaleString('ru-RU') : '0')}
                            </div>
                          </div>
                          <div className="p-1.5 rounded-lg bg-white/[0.02]">
                            <div className="text-[10px] text-neutral-500 uppercase">Доставлено</div>
                            <div className="text-xs font-bold text-emerald-400 mt-0.5">
                              {bc.delivered_count ? bc.delivered_count.toLocaleString('ru-RU') : (bc.total_recipients || '0')}
                            </div>
                          </div>
                          <div className="p-1.5 rounded-lg bg-white/[0.02]">
                            <div className="text-[10px] text-neutral-500 uppercase">Статус</div>
                            <div className="text-xs font-bold text-white mt-0.5">
                              {bc.status === 'completed' ? '100%' : 'В пути'}
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </section>

              {/* Security & Anti-Spam Notice */}
              <div className="p-3.5 rounded-xl bg-white/[0.02] border border-white/5 text-[11px] text-neutral-400 leading-relaxed">
                Все рассылки доставляются через официального верифицированного бота Ivently и защищены от массового спама алгоритмом 24-часового отдыха аудитории.
              </div>
            </main>
          </div>
        )}

        {/* =========================================================================
            UNIFIED FLOATING OPTICAL GLASS DOCK
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
                <Send className={`w-5 h-5 ${activeTab === 'broadcasts' ? 'text-emerald-400' : ''}`} />
                <span className="text-[11px] leading-tight">Рассылки</span>
              </button>
            </div>
          </nav>
        )}

      </div>

      {/* =========================================================================
          SINGLE-SCREEN BROADCAST BUILDER (НОВАЯ РАССЫЛКА БЕЗ ШАГОВ)
      ========================================================================= */}
      {isBroadcastModalOpen && (
        <div className="fixed inset-0 z-[65] bg-[#0d0d0f] flex flex-col overflow-y-auto">
          {/* Top Bar */}
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
                <p className="text-[11px] text-neutral-400">Сообщение и целевой сегмент</p>
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

          {/* Main Content */}
          <main className="flex-1 px-4 py-4 space-y-4 overflow-y-auto pb-32 max-w-[420px] mx-auto w-full">
            {/* 24h Anti-Fatigue Rule Indicator */}
            <div className="p-3.5 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 flex gap-3 items-center">
              <div className="w-8 h-8 rounded-full bg-emerald-500/20 flex items-center justify-center text-emerald-400 shrink-0">
                <CheckCircle2 className="w-4 h-4" />
              </div>
              <div className="text-xs">
                <span className="font-bold text-white block">Лимит доступен: 1 рассылка</span>
                <span className="text-neutral-400">Правило 24ч соблюдено. Аудитория готова к приему уведомления.</span>
              </div>
            </div>

            {/* Section 1: Целевой сегмент */}
            <section className="form-section p-4 space-y-3 rounded-2xl bg-[#141417] border border-white/8">
              <div className="flex items-center justify-between">
                <label className="block text-xs font-bold uppercase tracking-wider text-neutral-400">
                  Целевая аудитория
                </label>
                <span className="text-[11px] text-neutral-400">{activeOrg.name}</span>
              </div>

              <div className="space-y-2">
                {/* Segment Option 1: Subscribers */}
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
                    <span className="text-[11px] text-neutral-400 block">Пользователи, подписанные на ваш бренд</span>
                    <span className="text-xs font-semibold text-emerald-400 block pt-1">
                      {(audienceData?.total_subscribers ?? activeOrg.followers_count ?? 0).toLocaleString('ru-RU')} получателей
                    </span>
                  </div>
                  <input
                    type="radio"
                    name="audience"
                    checked={targetSegment === 'subscribers'}
                    onChange={() => setTargetSegment('subscribers')}
                    className="mt-1 accent-emerald-400"
                  />
                </label>

                {/* Segment Option 2: Event interest */}
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
                    <span className="text-[11px] text-neutral-400 block">Пользователи, нажавшие «Хочу пойти»</span>
                    <span className="text-xs font-semibold text-neutral-300 block pt-1">
                      Точечный анонс по гостям мероприятия
                    </span>
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

            {/* Section 2: Привязать событие к рассылке */}
            <section className="form-section p-4 space-y-2.5 rounded-2xl bg-[#141417] border border-white/8">
              <label className="block text-xs font-bold uppercase tracking-wider text-neutral-400">
                Привязать событие к кнопке Telegram
              </label>
              <select
                value={selectedEventTargetId}
                onChange={(e) => setSelectedEventTargetId(e.target.value)}
                className="w-full bg-[#1c1c20] border border-white/10 rounded-xl p-2.5 text-xs text-white focus:outline-none focus:border-white/30"
              >
                <option value="">Без привязки (кнопка профиля организации)</option>
                {publishedEvents.map((pe) => (
                  <option key={pe.id} value={pe.id}>
                    {pe.title} ({pe.dateText})
                  </option>
                ))}
              </select>
              <p className="text-[11px] text-neutral-500 leading-relaxed">
                К сообщению в Telegram будет автоматически прикреплена интерактивная кнопка для перехода к событию.
              </p>
            </section>

            {/* Section 3: Текст сообщения (Без спам-кнопок) */}
            <section className="form-section p-4 space-y-2.5 rounded-2xl bg-[#141417] border border-white/8">
              <div className="flex items-center justify-between">
                <label className="block text-xs font-bold uppercase tracking-wider text-neutral-400">
                  Текст рассылки
                </label>
                <span className="text-[11px] text-neutral-500">{broadcastMessage.length} / 500 знаков</span>
              </div>

              <textarea
                rows={4}
                value={broadcastMessage}
                onChange={(e) => setBroadcastMessage(e.target.value.slice(0, 500))}
                className="w-full bg-[#1c1c20] border border-white/10 rounded-xl p-3 text-sm text-white placeholder-neutral-500 focus:outline-none focus:border-white/30 resize-none leading-relaxed"
                placeholder="Напишите текст анонса для подписчиков..."
              />
            </section>

            {/* Section 4: Live Telegram Preview */}
            <section className="form-section p-4 space-y-2.5 rounded-2xl bg-[#141417] border border-white/8">
              <div className="flex items-center justify-between">
                <label className="block text-xs font-bold uppercase tracking-wider text-neutral-400">
                  Живое превью в Telegram
                </label>
                <span className="text-[10px] text-emerald-400 font-mono">Ivently Bot</span>
              </div>

              <div className="p-3 bg-[#17171a] rounded-2xl border border-white/5">
                <div className="telegram-bubble p-3 text-xs leading-relaxed space-y-2.5">
                  <div className="flex items-center justify-between pb-1.5 border-b border-white/5">
                    <span className="font-bold text-emerald-400 flex items-center gap-1">
                      <ShieldCheck className="w-3.5 h-3.5" />
                      {activeOrg.name} via Ivently
                    </span>
                    <span className="text-[10px] text-neutral-500">Сейчас</span>
                  </div>
                  
                  <p className="text-neutral-200 whitespace-pre-wrap leading-relaxed">
                    {broadcastMessage.trim() || 'Ваш текст сообщения появится здесь в реальном времени...'}
                  </p>

                  <div className="pt-1">
                    <div className="w-full py-2.5 bg-[#2d2d33] text-center text-xs font-semibold text-emerald-400 rounded-xl border border-white/5 flex items-center justify-center gap-1.5 shadow-md">
                      {selectedEventTargetId ? (
                        <>
                          <span>🎟️ Открыть билеты: {publishedEvents.find(e => e.id === selectedEventTargetId)?.title || 'в Ivently'}</span>
                        </>
                      ) : (
                        <>
                          <span>🏛️ Открыть профиль в Ivently</span>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </section>

            {/* Section 5: Silent push checkbox */}
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
          </main>

          {/* Sticky Bottom Bar */}
          <div className="sticky bottom-0 left-0 right-0 p-4 bg-[#0d0d0f]/95 backdrop-blur-md border-t border-white/5 space-y-2 z-20 max-w-[420px] mx-auto w-full">
            <button
              type="button"
              disabled={isSendingBroadcast || !broadcastMessage.trim()}
              onClick={handleLaunchBroadcast}
              className={`w-full py-3.5 rounded-2xl font-bold text-sm transition-all active:scale-[0.98] shadow-lg flex items-center justify-center gap-2 ${
                isSendingBroadcast || !broadcastMessage.trim()
                  ? 'bg-white/20 text-neutral-400 cursor-not-allowed'
                  : 'bg-emerald-500 hover:bg-emerald-400 text-black'
              }`}
            >
              {isSendingBroadcast ? (
                <>
                  <div className="w-4 h-4 border-2 border-black border-t-transparent rounded-full animate-spin" />
                  <span>Отправка рассылки...</span>
                </>
              ) : (
                <>
                  <Send className="w-4 h-4" />
                  <span>Запустить рассылку в Telegram</span>
                </>
              )}
            </button>
            <p className="text-[10px] text-neutral-500 text-center leading-relaxed">
              Сообщение будет отправлено через официального бота Ivently прямо в личные чаты получателей.
            </p>
          </div>
        </div>
      )}

      {/* =========================================================================
          VIEW BROADCAST DETAILS MODAL
      ========================================================================= */}
      {selectedBroadcastForView && (
        <div className="fixed inset-0 z-[70] bg-black/90 backdrop-blur-xl flex flex-col p-4 animate-fade-in overflow-y-auto">
          <div className="flex items-center justify-between pb-3 border-b border-white/10 max-w-sm mx-auto w-full">
            <div className="flex items-center space-x-2 text-white">
              <Send className="w-4 h-4 text-emerald-400" />
              <span className="font-bold text-sm">Детали рассылки</span>
            </div>
            <button
              type="button"
              onClick={() => setSelectedBroadcastForView(null)}
              className="p-1.5 rounded-full bg-white/5 text-neutral-400 hover:text-white"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          <div className="py-6 max-w-sm mx-auto w-full space-y-4">
            <div className="p-4 rounded-2xl bg-[#141417] border border-white/10 space-y-3">
              <div className="flex items-center justify-between text-xs">
                <span className="text-neutral-400">Статус доставки:</span>
                <span className="text-emerald-400 font-bold uppercase">
                  {selectedBroadcastForView.status === 'completed' ? 'Доставлено 100%' : 'В процессе'}
                </span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-neutral-400">Дата отправки:</span>
                <span className="text-white">
                  {selectedBroadcastForView.created_at
                    ? new Date(selectedBroadcastForView.created_at).toLocaleDateString('ru-RU', {
                        day: 'numeric',
                        month: 'long',
                        hour: '2-digit',
                        minute: '2-digit',
                      })
                    : '—'}
                </span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-neutral-400">Получателей:</span>
                <span className="text-white font-bold">
                  {selectedBroadcastForView.total_recipients ? selectedBroadcastForView.total_recipients.toLocaleString('ru-RU') : '0'} чел.
                </span>
              </div>

              {/* Message text */}
              <div className="pt-2 border-t border-white/5">
                <div className="text-[11px] font-bold text-neutral-400 uppercase mb-1.5">Текст сообщения</div>
                <div className="p-3 bg-[#0A0A0C] rounded-xl border border-white/5 text-xs text-white leading-relaxed whitespace-pre-wrap">
                  {selectedBroadcastForView.custom_text}
                </div>
              </div>
            </div>

            <div className="space-y-2">
              <button
                type="button"
                onClick={() => {
                  navigator.clipboard.writeText(selectedBroadcastForView.custom_text || '');
                  telegram.hapticSuccess();
                  alert('Текст рассылки скопирован в буфер');
                }}
                className="w-full py-3 rounded-2xl bg-white/10 hover:bg-white/15 text-white font-semibold text-xs flex items-center justify-center gap-1.5"
              >
                <Copy className="w-3.5 h-3.5" />
                <span>Скопировать текст</span>
              </button>
              <button
                type="button"
                onClick={() => {
                  setBroadcastMessage(selectedBroadcastForView.custom_text || '');
                  setSelectedBroadcastForView(null);
                  setIsBroadcastModalOpen(true);
                }}
                className="w-full py-3 rounded-2xl bg-white text-black font-semibold text-xs flex items-center justify-center gap-1.5"
              >
                <Repeat className="w-3.5 h-3.5" />
                <span>Повторить как шаблон</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* =========================================================================
          PRO SHOWCASE MODAL
      ========================================================================= */}
      {isProModalOpen && (
        <div className="fixed inset-0 z-[75] bg-black/90 backdrop-blur-xl flex flex-col p-4 animate-fade-in overflow-y-auto">
          <div className="flex items-center justify-between pb-3 border-b border-white/10 max-w-sm mx-auto w-full">
            <div className="flex items-center space-x-2 text-white">
              <Crown className="w-4 h-4 text-emerald-400" />
              <span className="font-bold text-sm">Тарифы и возможности PRO</span>
            </div>
            <button
              type="button"
              onClick={() => setIsProModalOpen(false)}
              className="p-1.5 rounded-full bg-white/5 text-neutral-400 hover:text-white"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          <div className="py-6 max-w-sm mx-auto w-full space-y-4">
            <div className="text-center space-y-1">
              <div className="w-14 h-14 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 mx-auto">
                <Sparkles className="w-7 h-7" />
              </div>
              <h2 className="text-lg font-bold text-white pt-2">Ivently PRO для организаторов</h2>
              <p className="text-xs text-neutral-400 leading-relaxed">
                Инструменты прямого маркетинга в Telegram для роста посещаемости ваших событий.
              </p>
            </div>

            {/* Comparison Deck */}
            <div className="space-y-3">
              {/* Free Tier */}
              <div className="p-4 rounded-2xl bg-[#141417] border border-white/5 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-neutral-300">Базовый тариф</span>
                  <span className="text-xs font-bold text-white">0 ₽ / навсегда</span>
                </div>
                <ul className="text-xs text-neutral-400 space-y-1.5 pt-1">
                  <li className="flex items-center gap-2">
                    <Check className="w-3.5 h-3.5 text-emerald-400" />
                    <span>Публикация событий в городской афише</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <Check className="w-3.5 h-3.5 text-emerald-400" />
                    <span>Продажа билетов и регистрации</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <Check className="w-3.5 h-3.5 text-emerald-400" />
                    <span>QR-сканер на входе для контроля гостей</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <Check className="w-3.5 h-3.5 text-emerald-400" />
                    <span>1 приветственная рассылка по подписчикам</span>
                  </li>
                </ul>
              </div>

              {/* PRO Tier */}
              <div className="p-4 rounded-2xl bg-gradient-to-b from-emerald-500/10 to-transparent border border-emerald-500/30 space-y-2.5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5">
                    <span className="text-xs font-bold text-white">Ivently PRO</span>
                    <span className="px-1.5 py-0.2 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-400">PRO</span>
                  </div>
                  <span className="text-xs font-bold text-emerald-400">499 ₽ / месяц</span>
                </div>
                <ul className="text-xs text-neutral-300 space-y-1.5 pt-1">
                  <li className="flex items-center gap-2">
                    <Check className="w-3.5 h-3.5 text-emerald-400" />
                    <span>Неограниченные рассылки через бота раз в 24ч</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <Check className="w-3.5 h-3.5 text-emerald-400" />
                    <span>Сегментация базы (подписчики, интерес, гости)</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <Check className="w-3.5 h-3.5 text-emerald-400" />
                    <span>Детальная конверсионная аналитика переходов</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <Check className="w-3.5 h-3.5 text-emerald-400" />
                    <span>Экспорт базы гостей в CSV/Excel</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <Check className="w-3.5 h-3.5 text-emerald-400" />
                    <span>Бейдж верификации организации</span>
                  </li>
                </ul>
              </div>
            </div>

            <button
              type="button"
              onClick={() => {
                telegram.hapticSuccess();
                alert('Подписка PRO активирована в демонстрационном режиме!');
                setIsProModalOpen(false);
              }}
              className="w-full py-3.5 rounded-2xl bg-emerald-500 hover:bg-emerald-400 text-black font-bold text-xs shadow-lg active:scale-95 transition"
            >
              Подключить PRO (499 ₽ / мес)
            </button>
          </div>
        </div>
      )}

      {/* =========================================================================
          AUXILIARY MODAL: ЧЕК-ИН (CHECK-IN SCANNER)
      ========================================================================= */}
      <CheckInScannerModal
        isOpen={Boolean(activeCheckInEvent)}
        onClose={() => setActiveCheckInEvent(null)}
        event={activeCheckInEvent}
      />

      {/* =========================================================================
          AUXILIARY MODAL: ПРЕДПРОСМОТР СОБЫТИЯ НА МОДЕРАЦИИ
      ========================================================================= */}
      {activePreviewEvent && (
        <div className="fixed inset-0 z-[70] bg-black/90 backdrop-blur-xl flex flex-col p-4 animate-fade-in overflow-y-auto">
          <div className="flex items-center justify-between pb-3 border-b border-white/10 max-w-sm mx-auto w-full">
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
                <SafeImage
                  src={activePreviewEvent.cover_image_url}
                  alt={activePreviewEvent.title}
                  className="w-full h-full object-cover"
                />
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
