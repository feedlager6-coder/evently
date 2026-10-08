import React, { useState, useEffect, useRef } from 'react';
import type {
  EventSummary,
  OrganizationSummary,
  OrganizerAudienceResponse,
  BroadcastItem,
  BroadcastDetail,
  BroadcastPreviewResponse,
  BroadcastTargetType,
  BroadcastType,
  BroadcastTemplateKey,
  OrganizerInsightsResponse,
  OrganizerEntitlementsResponse,
  PaymentConfigResponse,
  PaymentOrder,
} from '../types';
import { SafeAvatar } from './SafeAvatar';
import { telegram } from '../services/telegram';
import { api } from '../services/api';
import { AnimatedSegmentedControl } from './AnimatedSegmentedControl';
import {
  ArrowLeft,
  Plus,
  Building2,
  Calendar,
  Clock,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Users,
  Eye,
  Heart,
  ChevronRight,
  ShieldCheck,
  AlertTriangle,
  Edit3,
  ExternalLink,
  UserPlus,
  UserCheck,
  Info,
  Send,
  X,
  Sparkles,
  Compass,
  Receipt,
  CreditCard,
  Loader2,
} from 'lucide-react';

export type WorkspaceTab = 'overview' | 'events' | 'organizations' | 'audience' | 'broadcasts';
export type EventFilter = 'upcoming' | 'pending' | 'past';

interface OrganizerWorkspaceProps {
  onBack: () => void;
  organizations: OrganizationSummary[];
  events: EventSummary[];
  isLoading: boolean;
  onOpenCreateEvent: (orgId?: string) => void;
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
}

export const OrganizerWorkspace: React.FC<OrganizerWorkspaceProps> = ({
  onBack,
  organizations,
  events,
  isLoading,
  onOpenCreateEvent,
  onOpenCreateOrg,
  onEditOrg,
  onOrgClick,
  onEventClick,
  onOrgDeleted: _onOrgDeleted,
  isAdmin = false,
  paymentReturnOrderId,
  initialTab,
  initialBroadcastEventId,
  initialBroadcastOrgId,
  initialOpenProModal,
}) => {
  const [activeTab, setActiveTab] = useState<WorkspaceTab>(initialTab || 'overview');
  const [eventFilter, setEventFilter] = useState<EventFilter>('upcoming');
  const [audienceData, setAudienceData] = useState<OrganizerAudienceResponse | null>(null);
  const [isLoadingAudience, setIsLoadingAudience] = useState<boolean>(false);
  const [selectedAudienceOrgId, setSelectedAudienceOrgId] = useState<string | null>(null);

  const [insightsData, setInsightsData] = useState<OrganizerInsightsResponse | null>(null);
  const [entitlements, setEntitlements] = useState<OrganizerEntitlementsResponse | null>(null);
  const [isProModalOpen, setIsProModalOpen] = useState<boolean>(false);
  const [isTogglingPlan, setIsTogglingPlan] = useState<boolean>(false);

  // Payment & Pro subscription state
  const [paymentConfig, setPaymentConfig] = useState<PaymentConfigResponse | null>(null);
  const [paymentHistory, setPaymentHistory] = useState<PaymentOrder[]>([]);
  const [isLoadingPayments, setIsLoadingPayments] = useState<boolean>(false);
  const [isPaying, setIsPaying] = useState<boolean>(false);
  const [checkoutEmail, setCheckoutEmail] = useState<string>('');
  const [paymentPollStatus, setPaymentPollStatus] = useState<'checking' | 'success' | 'pending' | 'failed' | null>(null);
  const [activePollOrder, setActivePollOrder] = useState<PaymentOrder | null>(null);

  useEffect(() => {
    api.getPaymentConfig()
      .then((cfg) => setPaymentConfig(cfg))
      .catch((err) => console.error('Failed to load payment config:', err));
  }, []);

  useEffect(() => {
    const orderIdToPoll = paymentReturnOrderId || (typeof window !== 'undefined' ? new URLSearchParams(window.location.search).get('payment_order_id') : null);
    if (!orderIdToPoll) return;

    let isMounted = true;
    let pollCount = 0;
    const maxPolls = 4;
    setPaymentPollStatus('checking');

    const checkStatus = async () => {
      try {
        const order = await api.getPaymentOrder(orderIdToPoll);
        if (!isMounted) return;
        setActivePollOrder(order);

        if (order.status === 'succeeded') {
          setPaymentPollStatus('success');
          telegram.hapticSuccess();
          loadEntitlements();
          return;
        }

        if (order.status === 'canceled' || order.status === 'failed') {
          setPaymentPollStatus('failed');
          telegram.hapticNotification('error');
          return;
        }

        pollCount++;
        if (pollCount < maxPolls) {
          setTimeout(checkStatus, 2000);
        } else {
          setPaymentPollStatus('pending');
        }
      } catch (err) {
        if (!isMounted) return;
        console.error('Error polling payment status:', err);
        setPaymentPollStatus('pending');
      }
    };

    checkStatus();

    return () => {
      isMounted = false;
    };
  }, [paymentReturnOrderId]);

  const handleInitiateProPayment = async () => {
    const orgId = composerOrgId || (organizations.length > 0 ? organizations[0].id : null);
    if (!orgId) {
      alert('Сначала создайте или выберите организацию.');
      return;
    }

    try {
      setIsPaying(true);
      telegram.hapticImpact('medium');

      const emailTrim = checkoutEmail.trim();
      const order = await api.createProPayment({
        organization_id: orgId,
        customer_email: emailTrim || undefined,
      });

      if (order.confirmation_url) {
        telegram.hapticSuccess();
        if (telegram.isAvailable() && typeof (window as any).Telegram?.WebApp?.openLink === 'function') {
          (window as any).Telegram.WebApp.openLink(order.confirmation_url);
        } else {
          window.location.href = order.confirmation_url;
        }
      } else {
        alert('Не удалось получить ссылку на оплату.');
      }
    } catch (err: any) {
      console.error('Payment error:', err);
      telegram.hapticNotification('error');
      alert(err.message || 'Ошибка создания платежа.');
    } finally {
      setIsPaying(false);
    }
  };

  const loadPaymentHistory = async () => {
    const orgId = composerOrgId || (organizations.length > 0 ? organizations[0].id : null);
    if (!orgId) return;
    try {
      setIsLoadingPayments(true);
      const history = await api.getOrganizationPayments(orgId);
      setPaymentHistory(history);
    } catch (err) {
      console.error('Failed to load payment history:', err);
    } finally {
      setIsLoadingPayments(false);
    }
  };

  const loadInsights = () => {
    api.getOrganizerInsights()
      .then((data) => setInsightsData(data))
      .catch((err) => console.error('Failed to load organizer insights:', err));
  };

  const loadEntitlements = (targetOrgId?: string) => {
    const orgId = targetOrgId || composerOrgId || (organizations.length > 0 ? organizations[0].id : undefined);
    api.getOrganizerEntitlements(orgId)
      .then((data) => setEntitlements(data))
      .catch((err) => console.error('Failed to load organizer entitlements:', err));
  };

  const handleAdminTogglePro = async () => {
    const orgId = composerOrgId || (organizations.length > 0 ? organizations[0].id : null);
    if (!orgId) return;
    const newPlan = entitlements?.plan === 'pro' ? 'free' : 'pro';
    try {
      setIsTogglingPlan(true);
      telegram.hapticImpact('medium');
      const updated = await api.adminSetOrganizationPlan(orgId, newPlan);
      setEntitlements(updated);
      telegram.hapticSuccess();
      if (activeTab === 'broadcasts') {
        loadBroadcasts();
      }
    } catch (err: any) {
      console.error('Failed to toggle organization plan:', err);
      alert(err.message || 'Ошибка смены тарифа');
    } finally {
      setIsTogglingPlan(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'overview') {
      loadInsights();
      loadEntitlements();
      loadPaymentHistory();
    }
  }, [activeTab, organizations]);

  useEffect(() => {
    if (activeTab === 'audience') {
      setIsLoadingAudience(true);
      api.getOrganizerAudience(selectedAudienceOrgId || undefined)
        .then((data) => setAudienceData(data))
        .catch((err) => console.error('Failed to load organizer audience:', err))
        .finally(() => setIsLoadingAudience(false));
    }
  }, [activeTab, selectedAudienceOrgId]);

  // Broadcasts state
  const [broadcasts, setBroadcasts] = useState<BroadcastItem[]>([]);
  const [isLoadingBroadcasts, setIsLoadingBroadcasts] = useState<boolean>(false);
  const [isComposerOpen, setIsComposerOpen] = useState<boolean>(false);
  const [selectedBroadcast, setSelectedBroadcast] = useState<BroadcastDetail | null>(null);

  // Composer fields
  const [composerOrgId, setComposerOrgId] = useState<string>('');
  const [composerTargetType, setComposerTargetType] = useState<BroadcastTargetType>('organization_subscribers');
  const [composerBroadcastType, setComposerBroadcastType] = useState<BroadcastType>('marketing');
  const [composerTemplateKey, setComposerTemplateKey] = useState<BroadcastTemplateKey>('event_announcement');
  const [composerEventId, setComposerEventId] = useState<string>('');
  const [composerCustomText, setComposerCustomText] = useState<string>('');
  const [previewData, setPreviewData] = useState<BroadcastPreviewResponse | null>(null);
  const [isLoadingPreview, setIsLoadingPreview] = useState<boolean>(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [isSubmittingBroadcast, setIsSubmittingBroadcast] = useState<boolean>(false);
  const [broadcastNotice, setBroadcastNotice] = useState<{ type: 'success' | 'warning' | 'error'; text: string } | null>(null);


  useEffect(() => {
    if (organizations.length > 0 && !composerOrgId) {
      setComposerOrgId(organizations[0].id);
    }
  }, [organizations, composerOrgId]);

  useEffect(() => {
    if (composerOrgId) {
      loadEntitlements(composerOrgId);
    }
  }, [composerOrgId]);

  const loadBroadcasts = () => {
    setIsLoadingBroadcasts(true);
    api.getOrganizerBroadcasts()
      .then((data) => setBroadcasts(data))
      .catch((err) => console.error('Failed to load broadcasts:', err))
      .finally(() => setIsLoadingBroadcasts(false));
  };

  useEffect(() => {
    if (activeTab === 'broadcasts') {
      loadBroadcasts();
      loadEntitlements();
    }
  }, [activeTab]);

  useEffect(() => {
    if (!isComposerOpen || !composerOrgId) return;

    const orgEvents = events.filter((e) => e.organization_id === composerOrgId);
    let effectiveEventId = composerEventId;
    if (
      (composerTemplateKey === 'event_announcement' ||
        composerTemplateKey === 'event_update' ||
        composerTargetType === 'event_interest') &&
      !effectiveEventId &&
      orgEvents.length > 0
    ) {
      effectiveEventId = orgEvents[0].id;
      setComposerEventId(effectiveEventId);
    }

    if (composerTargetType === 'event_interest' && !effectiveEventId) {
      setPreviewData(null);
      setPreviewError('Выберите событие для рассылки заинтересованным');
      return;
    }

    setIsLoadingPreview(true);
    setPreviewError(null);

    const timer = setTimeout(() => {
      api.previewBroadcast({
        organization_id: composerOrgId,
        target_type: composerTargetType,
        broadcast_type: composerBroadcastType,
        template_key: composerTemplateKey,
        event_id: effectiveEventId || undefined,
        custom_text: composerCustomText || undefined,
      })
        .then((res) => {
          setPreviewData(res);
          setPreviewError(null);
        })
        .catch((err) => {
          setPreviewData(null);
          setPreviewError(err.message || 'Ошибка расчета аудитории');
        })
        .finally(() => {
          setIsLoadingPreview(false);
        });
    }, 250);

    return () => clearTimeout(timer);
  }, [
    isComposerOpen,
    composerOrgId,
    composerTargetType,
    composerBroadcastType,
    composerTemplateKey,
    composerEventId,
    composerCustomText,
    events,
  ]);

  const handleOpenComposer = (targetEventId?: string | React.MouseEvent, targetOrgId?: string) => {
    telegram.hapticImpact('light');
    if (entitlements?.plan !== 'pro') {
      setIsProModalOpen(true);
      return;
    }
    const cleanEventId = typeof targetEventId === 'string' ? targetEventId : undefined;
    const defaultOrgId = targetOrgId || composerOrgId || (organizations[0]?.id ?? '');
    if (defaultOrgId) {
      setComposerOrgId(defaultOrgId);
    }
    if (cleanEventId) {
      setComposerEventId(cleanEventId);
      setComposerTargetType('event_interest');
    } else {
      const orgEvents = events.filter((e) => e.organization_id === defaultOrgId);
      if (orgEvents.length > 0 && !composerEventId) {
        setComposerEventId(orgEvents[0].id);
      }
    }
    setPreviewError(null);
    setIsComposerOpen(true);
  };

  useEffect(() => {
    if (initialOpenProModal) {
      setIsProModalOpen(true);
    }
  }, [initialOpenProModal]);

  const prevInitialTabRef = useRef(initialTab);
  useEffect(() => {
    if (initialTab && initialTab !== prevInitialTabRef.current) {
      prevInitialTabRef.current = initialTab;
      setActiveTab(initialTab);
    }
  }, [initialTab]);

  const handledBroadcastEventRef = useRef<string | null>(null);
  useEffect(() => {
    if (initialBroadcastEventId && handledBroadcastEventRef.current !== initialBroadcastEventId) {
      if (entitlements === null) {
        return;
      }
      handledBroadcastEventRef.current = initialBroadcastEventId;
      setActiveTab('broadcasts');
      handleOpenComposer(initialBroadcastEventId, initialBroadcastOrgId || undefined);
    }
  }, [initialBroadcastEventId, initialBroadcastOrgId, entitlements]);

  const handleSendBroadcast = async () => {
    if (!previewData || previewData.eligible_recipients === 0 || isSubmittingBroadcast) return;

    try {
      setIsSubmittingBroadcast(true);
      telegram.hapticImpact('medium');
      const detail = await api.createBroadcast({
        organization_id: composerOrgId,
        target_type: composerTargetType,
        broadcast_type: composerBroadcastType,
        template_key: composerTemplateKey,
        event_id: composerEventId || undefined,
        custom_text: composerCustomText || undefined,
      });
      setIsComposerOpen(false);
      if (detail.sent_count > 0 && detail.failed_count === 0 && detail.blocked_count === 0) {
        setBroadcastNotice({
          type: 'success',
          text: `Рассылка успешно доставлена в Telegram (${detail.sent_count}/${detail.total_recipients})`
        });
        telegram.hapticSuccess();
      } else if (detail.sent_count > 0) {
        setBroadcastNotice({
          type: 'warning',
          text: `Рассылка частично отправлена: ${detail.sent_count} из ${detail.total_recipients} (не доставлено: ${detail.failed_count + detail.blocked_count})`
        });
        telegram.hapticNotification('warning');
      } else {
        setBroadcastNotice({
          type: 'error',
          text: `Рассылка не доставлена: получатели не начали диалог с ботом или заблокировали его (${detail.failed_count + detail.blocked_count}/${detail.total_recipients})`
        });
        telegram.hapticNotification('error');
      }
      loadBroadcasts();
      loadEntitlements();
      setTimeout(() => setBroadcastNotice(null), 6000);
    } catch (err: any) {
      telegram.hapticImpact('heavy');
      console.error('Failed to send broadcast:', err);
      setPreviewError(err.message || 'Не удалось отправить рассылку');
    } finally {
      setIsSubmittingBroadcast(false);
    }
  };

  const handleViewBroadcastDetail = async (item: BroadcastItem) => {
    telegram.hapticImpact('light');
    try {
      const detail = await api.getBroadcastDetail(item.id);
      setSelectedBroadcast(detail);
    } catch (err) {
      console.error('Failed to load broadcast detail:', err);
    }
  };

  const now = new Date();

  // Segment events
  const upcomingEvents = events.filter(
    (e) => e.status === 'published' && new Date(e.start_at) >= now
  );
  const pendingEvents = events.filter(
    (e) => e.status === 'pending' || e.status === 'rejected'
  );
  const pastEvents = events.filter(
    (e) => (e.status === 'published' && new Date(e.start_at) < now) || e.status === 'cancelled'
  );

  // Aggregated overview metrics (across all organizer events)
  const totalFollowers = organizations.reduce((acc, o) => acc + (o.followers_count || 0), 0);
  const totalAttendees = events.reduce((acc, e) => acc + (e.attendee_count || 0), 0);
  const totalInterests = events.reduce((acc, e) => acc + (e.interest_count || 0), 0);
  const totalViews = events.reduce((acc, e) => acc + (e.views_count || 0), 0);

  // Top upcoming 2 events
  const topUpcoming = upcomingEvents.slice(0, 2);

  // Events requiring attention (rejected or pending)
  const attentionEvents = pendingEvents;

  const handleTabChange = (tab: WorkspaceTab) => {
    if (tab !== activeTab) {
      telegram.hapticImpact('light');
      setActiveTab(tab);
    }
  };

  const handleFilterChange = (filter: EventFilter) => {
    if (filter !== eventFilter) {
      telegram.hapticImpact('light');
      setEventFilter(filter);
    }
  };

  const currentEventsList =
    eventFilter === 'upcoming'
      ? upcomingEvents
      : eventFilter === 'pending'
      ? pendingEvents
      : pastEvents;

  return (
    <div className="space-y-4 pb-20">
      {/* Workspace Header */}
      <div className="sticky top-0 z-20 bg-[#0B0D13]/90 backdrop-blur-md border-b border-white/5 px-4 py-3">
        <div className="flex items-center justify-between max-w-lg mx-auto">
          <div className="flex items-center space-x-2.5">
            <button
              onClick={() => {
                telegram.hapticImpact('light');
                onBack();
              }}
              className="p-1.5 -ml-1 rounded-xl bg-white/5 hover:bg-white/10 text-gray-300 hover:text-white transition-colors btn-press"
              aria-label="Назад"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div>
              <h1 className="text-base font-bold text-white tracking-tight leading-tight">
                Кабинет организатора
              </h1>
              <p className="text-[11px] text-gray-400">Управление контентом и аудиторией</p>
            </div>
          </div>
        </div>
      </div>

      <div className="px-4 space-y-4 max-w-lg mx-auto">
        {/* Navigation Tabs */}
        <AnimatedSegmentedControl
          items={[
            { value: 'overview', label: 'Обзор' },
            { value: 'events', label: 'Мероприятия', count: events.length },
            { value: 'broadcasts', label: 'Рассылки' },
            { value: 'audience', label: 'Аудитория' },
            { value: 'organizations', label: 'Места', count: organizations.length },
          ]}
          value={activeTab}
          onChange={(val) => handleTabChange(val as WorkspaceTab)}
          scrollable
          size="sm"
        />

        {broadcastNotice && (
          <div className={`p-3 rounded-2xl border text-xs flex items-center space-x-2 animate-fade-in ${
            broadcastNotice.type === 'success'
              ? 'bg-emerald-500/15 border-emerald-500/30 text-emerald-300'
              : broadcastNotice.type === 'warning'
              ? 'bg-amber-500/15 border-amber-500/30 text-amber-300'
              : 'bg-red-500/15 border-red-500/30 text-red-300'
          }`}>
            {broadcastNotice.type === 'success' && <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />}
            {broadcastNotice.type === 'warning' && <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />}
            {broadcastNotice.type === 'error' && <AlertCircle className="w-4 h-4 text-red-400 shrink-0" />}
            <span>{broadcastNotice.text}</span>
          </div>
        )}

        <div key={activeTab} className="animate-tab-enter">
        {/* TAB 1: OVERVIEW */}
        {activeTab === 'overview' && (
          <div className="space-y-4">
            {/* Grounded Factual Insight Banner */}
            {insightsData?.fact_sentence && (
              <div className="p-3.5 rounded-2xl bg-gradient-to-r from-indigo-500/15 via-purple-500/10 to-transparent border border-indigo-500/25 flex items-start space-x-2.5">
                <Sparkles className="w-4 h-4 text-indigo-400 shrink-0 mt-0.5" />
                <div className="min-w-0">
                  <div className="text-[10px] font-semibold text-indigo-300 uppercase tracking-wider">Инсайт</div>
                  <div className="text-xs font-medium text-white leading-snug mt-0.5">{insightsData.fact_sentence}</div>
                </div>
              </div>
            )}

            {/* Pillar 1: Audience Growth */}
            <div className="p-3.5 rounded-2xl bg-[#141724] border border-white/5 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2 text-purple-400">
                  <Users className="w-4 h-4" />
                  <span className="text-xs font-semibold text-white">Аудитория</span>
                </div>
                <button
                  onClick={() => handleTabChange('audience')}
                  className="text-[11px] text-indigo-400 hover:text-indigo-300 font-medium flex items-center space-x-0.5 btn-press"
                >
                  <span>Подробнее</span>
                  <ChevronRight className="w-3 h-3" />
                </button>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div className="p-2.5 rounded-xl bg-white/5 space-y-0.5">
                  <div className="text-[10px] text-gray-400">Всего подписчиков</div>
                  <div className="text-base font-bold text-white tracking-tight">
                    {(insightsData?.audience.total_subscribers ?? totalFollowers).toLocaleString('ru-RU')}
                  </div>
                </div>
                <div className="p-2.5 rounded-xl bg-white/5 space-y-0.5">
                  <div className="text-[10px] text-gray-400">Вовлеченный охват</div>
                  <div className="text-base font-bold text-white tracking-tight">
                    {(insightsData?.audience.total_unique_engaged ?? 0).toLocaleString('ru-RU')}
                  </div>
                </div>
                <div className="p-2.5 rounded-xl bg-white/5 space-y-0.5">
                  <div className="text-[10px] text-gray-400">За 7 дней</div>
                  <div className="text-base font-bold text-emerald-400 tracking-tight">
                    +{(insightsData?.audience.new_subscribers_7d ?? 0).toLocaleString('ru-RU')}
                  </div>
                </div>
                <div className="p-2.5 rounded-xl bg-white/5 space-y-0.5">
                  <div className="text-[10px] text-gray-400">За 30 дней</div>
                  <div className="text-base font-bold text-emerald-400 tracking-tight">
                    +{(insightsData?.audience.new_subscribers_30d ?? 0).toLocaleString('ru-RU')}
                  </div>
                </div>
              </div>
            </div>

            {/* Pillar 2: Events Performance */}
            <div className="p-3.5 rounded-2xl bg-[#141724] border border-white/5 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2 text-indigo-400">
                  <Calendar className="w-4 h-4" />
                  <span className="text-xs font-semibold text-white">Статистика всех событий</span>
                </div>
                <span className="text-[10px] text-gray-500 font-medium">По всем событиям</span>
              </div>

              <div className="grid grid-cols-3 gap-2">
                <div className="p-2.5 rounded-xl bg-white/5 space-y-0.5">
                  <div className="text-[10px] text-gray-400">Просмотры</div>
                  <div className="text-base font-bold text-white tracking-tight">
                    {(insightsData?.events.total_views ?? totalViews).toLocaleString('ru-RU')}
                  </div>
                </div>
                <div className="p-2.5 rounded-xl bg-white/5 space-y-0.5">
                  <div className="text-[10px] text-gray-400">Интерес</div>
                  <div className="text-base font-bold text-pink-400 tracking-tight">
                    {(insightsData?.events.total_interest ?? totalInterests).toLocaleString('ru-RU')}
                  </div>
                </div>
                <div className="p-2.5 rounded-xl bg-white/5 space-y-0.5">
                  <div className="text-[10px] text-gray-400">Идут (RSVP)</div>
                  <div className="text-base font-bold text-emerald-400 tracking-tight">
                    {(insightsData?.events.total_rsvps ?? totalAttendees).toLocaleString('ru-RU')}
                  </div>
                </div>
              </div>
            </div>

            {/* Pillar 3: Telegram Broadcasts & Attribution */}
            <div className="p-3.5 rounded-2xl bg-[#141724] border border-white/5 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2 text-sky-400">
                  <Send className="w-4 h-4" />
                  <span className="text-xs font-semibold text-white">Рассылки в Telegram</span>
                </div>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-sky-500/10 text-sky-400 border border-sky-500/20 font-medium">
                  Статистика
                </span>
              </div>

              {(insightsData?.broadcasts.total_broadcasts ?? 0) === 0 ? (
                <div className="p-3 text-center rounded-xl bg-white/5 space-y-1.5">
                  <p className="text-[11px] text-gray-400">Рассылки еще не отправлялись</p>
                  {organizations.length > 0 && (
                    <button
                      onClick={() => {
                        if (entitlements?.plan === 'pro') {
                          handleTabChange('broadcasts');
                          handleOpenComposer();
                        } else {
                          setIsProModalOpen(true);
                        }
                      }}
                      className="text-[11px] text-sky-400 hover:text-sky-300 font-medium btn-press"
                    >
                      {entitlements?.plan === 'pro' ? '+ Создать первую рассылку →' : 'Узнать о рассылках в тарифе Pro →'}
                    </button>
                  )}
                </div>
              ) : (
                <div className="space-y-2.5">
                  <div className="grid grid-cols-3 gap-2">
                    <div className="p-2.5 rounded-xl bg-white/5 space-y-0.5">
                      <div className="text-[10px] text-gray-400">Доставлено</div>
                      <div className="text-sm font-bold text-white">
                        {(insightsData?.broadcasts.total_delivered ?? 0).toLocaleString('ru-RU')}
                      </div>
                    </div>
                    <div className="p-2.5 rounded-xl bg-white/5 space-y-0.5">
                      <div className="text-[10px] text-gray-400">Открыли</div>
                      <div className="text-sm font-bold text-white">
                        {(insightsData?.broadcasts.total_opened ?? 0).toLocaleString('ru-RU')}
                      </div>
                      <div className="text-[9.5px] text-sky-400 font-medium">
                        {insightsData?.broadcasts.overall_open_rate ?? 0}%
                      </div>
                    </div>
                    <div className="p-2.5 rounded-xl bg-white/5 space-y-0.5">
                      <div className="text-[10px] text-gray-400">Идут из рассылок</div>
                      <div className="text-sm font-bold text-emerald-400">
                        {(insightsData?.broadcasts.total_attributed_rsvp ?? 0).toLocaleString('ru-RU')}
                      </div>
                      <div className="text-[9.5px] text-emerald-400 font-medium">
                        {insightsData?.broadcasts.overall_rsvp_conversion ?? 0}%
                      </div>
                    </div>
                  </div>

                  {(insightsData?.broadcasts.total_attributed_interest ?? 0) > 0 && (
                    <div className="text-[10.5px] text-gray-400 px-1 flex items-center justify-between">
                      <span>«Хочу пойти» из рассылок:</span>
                      <span className="font-semibold text-pink-400">
                        +{insightsData?.broadcasts.total_attributed_interest}
                      </span>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Discovery Sources Breakdown */}
            {(insightsData?.sources && insightsData.sources.length > 0) && (
              <div className="p-3.5 rounded-2xl bg-[#141724] border border-white/5 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2 text-indigo-400">
                    <Compass className="w-4 h-4" />
                    <span className="text-xs font-semibold text-white">Источники просмотров</span>
                  </div>
                  <span className="text-[10px] text-gray-500 font-medium">Каналы переходов</span>
                </div>

                <div className="space-y-2">
                  {insightsData.sources.map((src) => (
                    <div key={src.source} className="space-y-1">
                      <div className="flex items-center justify-between text-[11px]">
                        <span className="text-gray-300 font-medium">{src.label}</span>
                        <div className="flex items-center space-x-2 text-gray-400">
                          <span>{src.views_count.toLocaleString('ru-RU')}</span>
                          <span className="text-indigo-400 font-semibold w-10 text-right">{src.percentage}%</span>
                        </div>
                      </div>
                      <div className="w-full h-1.5 rounded-full bg-white/5 overflow-hidden">
                        <div
                          className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-purple-500 transition-all duration-300"
                          style={{ width: `${Math.min(src.percentage, 100)}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Quick Action Buttons */}
            <div className="grid grid-cols-2 gap-2.5">
              <button
                onClick={() => {
                  telegram.hapticImpact('light');
                  onOpenCreateEvent();
                }}
                className="p-3 rounded-2xl bg-indigo-600/15 border border-indigo-500/30 hover:bg-indigo-600/25 flex items-center justify-center space-x-2 text-xs font-semibold text-indigo-300 transition-all btn-press"
              >
                <Plus className="w-4 h-4" />
                <span>Новое событие</span>
              </button>

              <button
                onClick={() => {
                  telegram.hapticImpact('light');
                  onOpenCreateOrg();
                }}
                className="p-3 rounded-2xl bg-white/5 border border-white/10 hover:bg-white/10 flex items-center justify-center space-x-2 text-xs font-semibold text-gray-200 transition-all btn-press"
              >
                <Building2 className="w-4 h-4 text-gray-400" />
                <span>+ Организация</span>
              </button>
            </div>

            {/* Pro Foundation Fake Door Card */}
            <div className="p-3.5 rounded-2xl bg-gradient-to-r from-purple-900/20 via-indigo-900/15 to-[#141724] border border-purple-500/20 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <div className="w-7 h-7 rounded-xl bg-purple-500/20 border border-purple-500/30 flex items-center justify-center text-purple-400 shrink-0">
                    <Sparkles className="w-3.5 h-3.5" />
                  </div>
                  <div>
                    <div className="text-xs font-semibold text-white flex items-center space-x-1.5">
                      <span>Pro для организаторов</span>
                      <span className={`text-[9.5px] px-1.5 py-0.5 rounded-full font-bold uppercase tracking-wider ${
                        entitlements?.plan === 'pro'
                          ? 'bg-purple-500/20 text-purple-300 border border-purple-500/30'
                          : 'bg-white/10 text-gray-300'
                      }`}>
                        {entitlements?.plan === 'pro' ? 'Pro' : 'Free'}
                      </span>
                    </div>
                    <p className="text-[11px] text-gray-400 mt-0.5 leading-snug">
                      Дополнительные возможности для регулярных анонсов, расширенной базы и аналитики
                    </p>
                  </div>
                </div>
              </div>

              <div className="flex items-center justify-between pt-1 border-t border-white/5 text-[11px]">
                <div className="text-gray-400">
                  {entitlements?.plan === 'pro' ? (
                    <span className="text-purple-300 font-medium">Тариф Pro активен для этой площадки</span>
                  ) : (
                    <span>Рассылки доступны в тарифе Pro</span>
                  )}
                </div>
                <button
                  onClick={() => {
                    telegram.hapticImpact('light');
                    setIsProModalOpen(true);
                  }}
                  className="px-3 py-1.5 rounded-xl bg-purple-600/20 hover:bg-purple-600/30 border border-purple-500/30 text-purple-300 font-semibold text-xs transition-all btn-press"
                >
                  {entitlements?.plan === 'pro' ? 'Возможности Pro' : 'Узнать о Pro'}
                </button>
              </div>

              {isAdmin && (
                <div className="pt-2 border-t border-white/5 flex items-center justify-between text-xs">
                  <span className="text-[11px] text-amber-300 font-medium">
                    🔧 <strong>Тест админа:</strong> {entitlements?.plan === 'pro' ? 'Тариф Pro' : 'Тариф Free'}
                  </span>
                  <button
                    onClick={handleAdminTogglePro}
                    disabled={isTogglingPlan}
                    className="px-2.5 py-1 rounded-lg bg-amber-600 hover:bg-amber-500 text-white font-semibold text-[11px] transition-all btn-press shrink-0 ml-2"
                  >
                    {isTogglingPlan ? '...' : entitlements?.plan === 'pro' ? 'Вернуть Free' : 'Включить Pro'}
                  </button>
                </div>
              )}
            </div>

            {/* Payment History Card */}
            <div className="p-3.5 rounded-2xl bg-[#141724] border border-white/5 space-y-2.5">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2 text-white text-xs font-semibold">
                  <Receipt className="w-4 h-4 text-purple-400" />
                  <span>История оплат</span>
                </div>
                <button
                  onClick={loadPaymentHistory}
                  disabled={isLoadingPayments}
                  className="text-[11px] text-purple-400 hover:text-purple-300 font-medium btn-press"
                >
                  {isLoadingPayments ? 'Загрузка...' : 'Обновить'}
                </button>
              </div>

              {paymentHistory.length === 0 ? (
                <div className="text-[11px] text-gray-500 py-0.5">
                  История оплат пока пуста.
                </div>
              ) : (
                <div className="space-y-1.5">
                  {paymentHistory.map((p) => (
                    <div
                      key={p.id}
                      className="p-2.5 rounded-xl bg-white/5 border border-white/5 flex items-center justify-between text-xs"
                    >
                      <div className="space-y-0.5">
                        <div className="font-semibold text-white">
                          {p.amount} {p.currency}
                        </div>
                        <div className="text-[10px] text-gray-400">
                          {new Date(p.created_at).toLocaleDateString('ru-RU')} · {p.service_name}
                        </div>
                      </div>
                      <div className="flex items-center space-x-2">
                        <span className={`text-[10px] px-2 py-0.5 rounded-full font-semibold ${
                          p.status === 'succeeded'
                            ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
                            : p.status === 'pending'
                            ? 'bg-amber-500/15 text-amber-400 border border-amber-500/30'
                            : 'bg-red-500/15 text-red-400 border border-red-500/30'
                        }`}>
                          {p.status === 'succeeded' ? 'Оплачено' : p.status === 'pending' ? 'Ожидает' : 'Отменено'}
                        </span>
                        {p.receipt_url && (
                          <a
                            href={p.receipt_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="p-1 rounded-lg bg-white/10 hover:bg-white/20 text-purple-300"
                            title="Чек"
                          >
                            <Receipt className="w-3.5 h-3.5" />
                          </a>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Requires Attention Section (if any pending/rejected) */}
            {attentionEvents.length > 0 && (
              <div className="space-y-2.5">
                <div className="flex items-center space-x-1.5 px-1">
                  <AlertTriangle className="w-4 h-4 text-amber-400" />
                  <h3 className="text-xs font-semibold text-amber-300 uppercase tracking-wider">
                    Требует внимания ({attentionEvents.length})
                  </h3>
                </div>

                <div className="space-y-2">
                  {attentionEvents.map((ev) => (
                    <div
                      key={ev.id}
                      onClick={() => onEventClick(ev)}
                      className="p-3.5 rounded-2xl bg-[#141724] border border-amber-500/20 hover:border-amber-500/40 transition-all cursor-pointer space-y-2 card-press"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="font-semibold text-xs text-white line-clamp-1">{ev.title}</div>
                        {ev.status === 'pending' ? (
                          <span className="flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/30 shrink-0">
                            <Clock className="w-3 h-3" />
                            <span>На проверке</span>
                          </span>
                        ) : (
                          <span className="flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-red-500/10 text-red-400 border border-red-500/30 shrink-0">
                            <XCircle className="w-3 h-3" />
                            <span>Отклонено</span>
                          </span>
                        )}
                      </div>

                      {ev.rejection_reason && (
                        <div className="p-2.5 rounded-xl bg-red-500/10 border border-red-500/20 text-[11px] text-red-300 space-y-0.5">
                          <span className="font-semibold text-red-200">Причина модератора: </span>
                          <span>{ev.rejection_reason}</span>
                        </div>
                      )}

                      <div className="flex items-center justify-between text-[11px] text-gray-400 pt-1 border-t border-white/5">
                        <span>{ev.venue_name}</span>
                        <span className="text-indigo-400 font-medium flex items-center space-x-0.5">
                          <span>Открыть детали</span>
                          <ChevronRight className="w-3.5 h-3.5" />
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Upcoming Events Preview */}
            <div className="space-y-2.5">
              <div className="flex items-center justify-between px-1">
                <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
                  Ближайшие события
                </h3>
                {upcomingEvents.length > 2 && (
                  <button
                    onClick={() => {
                      setActiveTab('events');
                      setEventFilter('upcoming');
                    }}
                    className="text-xs text-indigo-400 hover:text-indigo-300 font-medium btn-press"
                  >
                    Все ({upcomingEvents.length}) →
                  </button>
                )}
              </div>

              {topUpcoming.length === 0 ? (
                <div className="p-5 text-center rounded-2xl bg-[#141724] border border-white/5 space-y-2">
                  <Calendar className="w-6 h-6 text-gray-500 mx-auto" />
                  <p className="text-xs text-gray-400">Нет опубликованных предстоящих событий</p>
                  <button
                    onClick={() => onOpenCreateEvent()}
                    className="px-3 py-1.5 rounded-xl bg-indigo-600 text-white text-xs font-medium hover:bg-indigo-500 btn-press"
                  >
                    Опубликовать анонс
                  </button>
                </div>
              ) : (
                <div className="space-y-2">
                  {topUpcoming.map((ev) => {
                    const dateStr = new Date(ev.start_at).toLocaleDateString('ru-RU', {
                      day: 'numeric',
                      month: 'short',
                      hour: '2-digit',
                      minute: '2-digit',
                    });

                    return (
                      <div
                        key={ev.id}
                        onClick={() => onEventClick(ev)}
                        className="p-3.5 rounded-2xl bg-[#141724] border border-white/5 hover:border-indigo-500/30 transition-all cursor-pointer space-y-2.5 card-press"
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="font-semibold text-xs text-white line-clamp-1">
                            {ev.title}
                          </div>
                          <span className="flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 shrink-0">
                            <CheckCircle2 className="w-3 h-3" />
                            <span>Опубликовано</span>
                          </span>
                        </div>

                        <div className="flex items-center justify-between text-xs text-gray-400">
                          <div className="flex items-center space-x-1.5">
                            <Calendar className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
                            <span>{dateStr}</span>
                          </div>
                          <div className="flex items-center space-x-2.5 text-[11px]">
                            <span className="flex items-center space-x-1 text-gray-400">
                              <Eye className="w-3 h-3 text-indigo-400" />
                              <span>{ev.views_count || 0}</span>
                            </span>
                            <span className="text-emerald-400 font-medium">
                              ● {ev.attendee_count} идут
                            </span>
                            <span className="text-pink-400 font-medium">
                              ● {ev.interest_count || 0} интерес
                            </span>
                          </div>
                        </div>

                        {((ev.broadcast_opens_count ?? 0) > 0 || (ev.broadcast_rsvp_count ?? 0) > 0 || (ev.broadcast_interest_count ?? 0) > 0) && (
                          <div className="flex items-center space-x-1.5 px-2.5 py-1 rounded-xl bg-sky-500/10 border border-sky-500/20 text-[10px] text-sky-300">
                            <Send className="w-3 h-3 text-sky-400 shrink-0" />
                            <span className="text-gray-400">Из рассылок:</span>
                            <span className="font-semibold text-white">{ev.broadcast_opens_count ?? 0}</span>
                            <span className="text-gray-400">переходов •</span>
                            <span className="font-semibold text-pink-300">{ev.broadcast_interest_count ?? 0}</span>
                            <span className="text-gray-400">интерес •</span>
                            <span className="font-semibold text-emerald-300">{ev.broadcast_rsvp_count ?? 0}</span>
                            <span className="text-gray-400">идут</span>
                          </div>
                        )}

                        {ev.status === 'published' && (ev.interest_count || 0) > 0 && (
                          <div
                            onClick={(e) => {
                              e.stopPropagation();
                              if (entitlements?.plan === 'pro') {
                                handleTabChange('broadcasts');
                                handleOpenComposer(ev.id, ev.organization_id);
                              } else {
                                setIsProModalOpen(true);
                              }
                            }}
                            className="flex items-center justify-between p-2.5 rounded-xl bg-purple-500/10 hover:bg-purple-500/15 border border-purple-500/20 text-[11px] text-purple-300 transition-all btn-press gap-2"
                          >
                            <div className="min-w-0 pr-1">
                              <span className="text-white font-medium">
                                🔥 <strong>{ev.interest_count}</strong> {ev.interest_count === 1 ? 'человек хочет' : 'человек хотят'} пойти
                              </span>
                              <div className="text-[10px] text-gray-400 truncate">
                                Напишите им, чтобы рассказать о деталях или предложить скидку
                              </div>
                            </div>
                            <button
                              type="button"
                              className="px-2.5 py-1 rounded-lg bg-purple-500/20 hover:bg-purple-500/30 text-purple-200 font-semibold text-[11px] shrink-0 border border-purple-500/30 transition-all flex items-center gap-1"
                            >
                              <span>Написать им</span>
                              <span className="text-xs">→</span>
                            </button>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        )}

        {/* TAB 2: EVENTS */}
        {activeTab === 'events' && (
          <div className="space-y-3.5">
            {/* Sub-filter pills */}
            <div className="flex items-center space-x-2 overflow-x-auto no-scrollbar py-0.5">
              <button
                onClick={() => handleFilterChange('upcoming')}
                className={`px-3 py-1.5 rounded-xl text-xs font-semibold whitespace-nowrap transition-all ${
                  eventFilter === 'upcoming'
                    ? 'bg-indigo-600 text-white shadow-sm'
                    : 'bg-[#141724] text-gray-400 border border-white/5 hover:text-white'
                }`}
              >
                Предстоящие ({upcomingEvents.length})
              </button>
              <button
                onClick={() => handleFilterChange('pending')}
                className={`px-3 py-1.5 rounded-xl text-xs font-semibold whitespace-nowrap transition-all ${
                  eventFilter === 'pending'
                    ? 'bg-indigo-600 text-white shadow-sm'
                    : 'bg-[#141724] text-gray-400 border border-white/5 hover:text-white'
                }`}
              >
                На проверке ({pendingEvents.length})
              </button>
              <button
                onClick={() => handleFilterChange('past')}
                className={`px-3 py-1.5 rounded-xl text-xs font-semibold whitespace-nowrap transition-all ${
                  eventFilter === 'past'
                    ? 'bg-indigo-600 text-white shadow-sm'
                    : 'bg-[#141724] text-gray-400 border border-white/5 hover:text-white'
                }`}
              >
                Прошедшие ({pastEvents.length})
              </button>
            </div>

            {/* Event list */}
            {isLoading ? (
              <div className="py-12 text-center text-xs text-gray-400">Загрузка мероприятий...</div>
            ) : currentEventsList.length === 0 ? (
              <div className="py-12 px-4 text-center rounded-2xl bg-[#141724] border border-white/5 space-y-2.5">
                <Calendar className="w-8 h-8 text-gray-500 mx-auto" />
                <div className="text-xs font-semibold text-white">
                  {eventFilter === 'upcoming'
                    ? 'Нет предстоящих событий'
                    : eventFilter === 'pending'
                    ? 'Нет событий на модерации'
                    : 'Нет прошедших событий'}
                </div>
                <p className="text-[11px] text-gray-400 max-w-xs mx-auto">
                  {eventFilter === 'upcoming'
                    ? 'Опубликуйте концерт, вечеринку или митап'
                    : 'Новые события попадают сюда до одобрения модератором'}
                </p>
                {eventFilter === 'upcoming' && (
                  <button
                    onClick={() => onOpenCreateEvent()}
                    className="px-4 py-2 rounded-xl bg-indigo-600 text-white text-xs font-semibold hover:bg-indigo-500 btn-press"
                  >
                    Создать событие
                  </button>
                )}
              </div>
            ) : (
              <div className="space-y-2.5">
                {currentEventsList.map((ev) => {
                  const dateStr = new Date(ev.start_at).toLocaleDateString('ru-RU', {
                    day: 'numeric',
                    month: 'short',
                    hour: '2-digit',
                    minute: '2-digit',
                  });

                  return (
                    <div
                      key={ev.id}
                      onClick={() => onEventClick(ev)}
                      className="p-3.5 rounded-2xl bg-[#141724] border border-white/5 hover:border-indigo-500/30 transition-all cursor-pointer space-y-2.5 card-press"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <div className="font-semibold text-xs text-white truncate">{ev.title}</div>
                          <div className="text-[11px] text-gray-400 truncate">
                            {ev.organization_name ? ev.organization_name : 'Личный профиль'} • {ev.venue_name}
                          </div>
                        </div>

                        {/* Status Pill */}
                        {ev.status === 'pending' && (
                          <span className="flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/30 shrink-0">
                            <Clock className="w-3 h-3" />
                            <span>На проверке</span>
                          </span>
                        )}
                        {ev.status === 'published' && (
                          <span className="flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 shrink-0">
                            <CheckCircle2 className="w-3 h-3" />
                            <span>Опубликовано</span>
                          </span>
                        )}
                        {ev.status === 'rejected' && (
                          <span className="flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-red-500/10 text-red-400 border border-red-500/30 shrink-0">
                            <XCircle className="w-3 h-3" />
                            <span>Отклонено</span>
                          </span>
                        )}
                        {ev.status === 'cancelled' && (
                          <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-gray-500/10 text-gray-400 border border-gray-500/30 shrink-0">
                            Снято
                          </span>
                        )}
                      </div>

                      {ev.status === 'rejected' && ev.rejection_reason && (
                        <div className="p-2.5 rounded-xl bg-red-500/10 border border-red-500/20 text-[11px] text-red-300">
                          <span className="font-semibold text-red-200">Причина отказа: </span>
                          <span>{ev.rejection_reason}</span>
                        </div>
                      )}

                      <div className="flex items-center justify-between text-xs text-gray-400 pt-1 border-t border-white/5">
                        <div className="flex items-center space-x-1">
                          <Calendar className="w-3.5 h-3.5 text-indigo-400" />
                          <span>{dateStr}</span>
                        </div>
                        <div className="flex items-center space-x-2.5 text-[11px]">
                          <span className="flex items-center space-x-1 text-gray-400">
                            <Eye className="w-3 h-3 text-indigo-400" />
                            <span>{ev.views_count || 0}</span>
                          </span>
                          <span className="text-emerald-400 font-medium">
                            ● {ev.attendee_count} идут
                          </span>
                          <span className="text-pink-400 font-medium">
                            ● {ev.interest_count || 0} интерес
                          </span>
                        </div>
                      </div>

                      {((ev.broadcast_opens_count ?? 0) > 0 || (ev.broadcast_rsvp_count ?? 0) > 0 || (ev.broadcast_interest_count ?? 0) > 0) && (
                        <div className="flex items-center space-x-1.5 px-2.5 py-1 rounded-xl bg-sky-500/10 border border-sky-500/20 text-[10px] text-sky-300">
                          <Send className="w-3 h-3 text-sky-400 shrink-0" />
                          <span className="text-gray-400">Из рассылок:</span>
                          <span className="font-semibold text-white">{ev.broadcast_opens_count ?? 0}</span>
                          <span className="text-gray-400">переходов •</span>
                          <span className="font-semibold text-pink-300">{ev.broadcast_interest_count ?? 0}</span>
                          <span className="text-gray-400">интерес •</span>
                          <span className="font-semibold text-emerald-300">{ev.broadcast_rsvp_count ?? 0}</span>
                          <span className="text-gray-400">идут</span>
                        </div>
                      )}

                      {ev.status === 'published' && (ev.interest_count || 0) > 0 && (
                        <div
                          onClick={(e) => {
                            e.stopPropagation();
                            if (entitlements?.plan === 'pro') {
                              handleTabChange('broadcasts');
                              handleOpenComposer(ev.id, ev.organization_id);
                            } else {
                              setIsProModalOpen(true);
                            }
                          }}
                          className="flex items-center justify-between p-2.5 rounded-xl bg-purple-500/10 hover:bg-purple-500/15 border border-purple-500/20 text-[11px] text-purple-300 transition-all btn-press gap-2"
                        >
                          <div className="min-w-0 pr-1">
                            <span className="text-white font-medium">
                              🔥 <strong>{ev.interest_count}</strong> {ev.interest_count === 1 ? 'человек хочет' : 'человек хотят'} пойти
                            </span>
                            <div className="text-[10px] text-gray-400 truncate">
                              Напишите им, чтобы рассказать о деталях или предложить скидку
                            </div>
                          </div>
                          <button
                            type="button"
                            className="px-2.5 py-1 rounded-lg bg-purple-500/20 hover:bg-purple-500/30 text-purple-200 font-semibold text-[11px] shrink-0 border border-purple-500/30 transition-all flex items-center gap-1"
                          >
                            <span>Написать им</span>
                            <span className="text-xs">→</span>
                          </button>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* TAB 3: ORGANIZATIONS */}
        {activeTab === 'organizations' && (
          <div className="space-y-3.5">
            <div className="flex items-center justify-between px-1">
              <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
                Мои организации ({organizations.length})
              </h3>
              <button
                onClick={onOpenCreateOrg}
                className="flex items-center space-x-1 text-xs text-indigo-400 hover:text-indigo-300 font-medium btn-press"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Добавить</span>
              </button>
            </div>

            {organizations.length === 0 ? (
              <div className="p-6 text-center rounded-2xl bg-[#141724] border border-white/5 space-y-3">
                <div className="w-12 h-12 rounded-xl bg-indigo-500/10 text-indigo-400 flex items-center justify-center mx-auto">
                  <Building2 className="w-6 h-6" />
                </div>
                <div className="space-y-1">
                  <h4 className="text-xs font-bold text-white">Профиль площадки или заведения</h4>
                  <p className="text-[11px] text-gray-400 max-w-xs mx-auto">
                    Создайте профиль бара, клуба, лектория или комьюнити, чтобы собирать подписчиков
                  </p>
                </div>
                <button
                  onClick={onOpenCreateOrg}
                  className="px-4 py-2 rounded-xl bg-indigo-600 text-white text-xs font-semibold shadow hover:bg-indigo-500 btn-press"
                >
                  Создать организацию
                </button>
              </div>
            ) : (
              <div className="space-y-3">
                {organizations.map((org) => (
                  <div
                    key={org.id}
                    className="p-4 rounded-2xl bg-[#141724] border border-white/5 space-y-3"
                  >
                    {/* Header info */}
                    <div className="flex items-center space-x-3">
                      <div className="w-12 h-12 rounded-xl overflow-hidden border border-indigo-500/30 flex items-center justify-center shrink-0">
                        <SafeAvatar
                          src={org.avatar_url}
                          name={org.name}
                          className="w-full h-full object-cover"
                        />
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center space-x-1.5">
                          <span className="font-semibold text-xs text-white truncate">
                            {org.name}
                          </span>
                          {org.is_verified && (
                            <ShieldCheck className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
                          )}
                        </div>
                        <div className="flex items-center space-x-2 text-[11px] text-gray-400">
                          <span className="text-indigo-300">{org.category}</span>
                          <span>•</span>
                          <span>{org.city_name || 'Город'}</span>
                        </div>
                      </div>
                    </div>

                    {/* Stats pill */}
                    <div className="flex items-center justify-around py-2 px-3 rounded-xl bg-white/[0.03] border border-white/5 text-center">
                      <div>
                        <div className="text-xs font-bold text-white">{org.followers_count || 0}</div>
                        <div className="text-[10px] text-gray-400">подписчиков</div>
                      </div>
                      <div className="w-px h-6 bg-white/10" />
                      <div>
                        <div className="text-xs font-bold text-white">{org.events_count || 0}</div>
                        <div className="text-[10px] text-gray-400">мероприятий</div>
                      </div>
                    </div>

                    {/* Actions */}
                    <div className="grid grid-cols-3 gap-2 pt-1">
                      <button
                        onClick={() => onEditOrg(org)}
                        className="py-2 px-1 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-[11px] font-medium text-gray-300 flex items-center justify-center space-x-1 btn-press"
                      >
                        <Edit3 className="w-3 h-3 text-gray-400" />
                        <span>Изменить</span>
                      </button>

                      <button
                        onClick={() => onOpenCreateEvent(org.id)}
                        className="py-2 px-1 rounded-xl bg-indigo-600/20 hover:bg-indigo-600/30 border border-indigo-500/30 text-[11px] font-medium text-indigo-300 flex items-center justify-center space-x-1 btn-press"
                      >
                        <Plus className="w-3 h-3 text-indigo-400" />
                        <span>Событие</span>
                      </button>

                      <button
                        onClick={() => onOrgClick(org)}
                        className="py-2 px-1 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-[11px] font-medium text-gray-300 flex items-center justify-center space-x-1 btn-press"
                      >
                        <ExternalLink className="w-3 h-3 text-gray-400" />
                        <span>Страница</span>
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* TAB 4: AUDIENCE */}
        {activeTab === 'audience' && (
          <div className="space-y-4">
            {/* Optional Organization Filter if organizer owns >1 organization */}
            {organizations.length > 1 && (
              <div className="flex items-center space-x-2 overflow-x-auto no-scrollbar py-0.5">
                <button
                  onClick={() => {
                    telegram.hapticImpact('light');
                    setSelectedAudienceOrgId(null);
                  }}
                  className={`px-3 py-1.5 rounded-xl text-xs font-semibold whitespace-nowrap transition-all ${
                    selectedAudienceOrgId === null
                      ? 'bg-indigo-600 text-white shadow-sm'
                      : 'bg-[#141724] text-gray-400 border border-white/5 hover:text-white'
                  }`}
                >
                  Все площадки
                </button>
                {organizations.map((org) => (
                  <button
                    key={org.id}
                    onClick={() => {
                      telegram.hapticImpact('light');
                      setSelectedAudienceOrgId(org.id);
                    }}
                    className={`px-3 py-1.5 rounded-xl text-xs font-semibold whitespace-nowrap transition-all flex items-center space-x-1.5 ${
                      selectedAudienceOrgId === org.id
                        ? 'bg-indigo-600 text-white shadow-sm'
                        : 'bg-[#141724] text-gray-400 border border-white/5 hover:text-white'
                    }`}
                  >
                    <span>{org.name}</span>
                  </button>
                ))}
              </div>
            )}

            {isLoadingAudience && !audienceData ? (
              <div className="py-12 text-center text-xs text-gray-400">
                Загрузка данных аудитории...
              </div>
            ) : audienceData ? (
              <div className="space-y-4">
                {/* Section 1: Main Audience Counters */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between px-1">
                    <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
                      База подписчиков в Telegram
                    </h3>
                    <span className="text-[11px] text-gray-500 font-medium">Канал прямого контакта</span>
                  </div>

                  <div className="p-4 rounded-2xl bg-[#141724] border border-white/5 space-y-3">
                    <div className="flex items-start justify-between">
                      <div className="space-y-1">
                        <div className="flex items-center space-x-2 text-purple-400">
                          <Users className="w-4 h-4" />
                          <span className="text-xs font-semibold">Подписчики заведений</span>
                        </div>
                        <div className="text-3xl font-extrabold text-white tracking-tight">
                          {audienceData.total_subscribers.toLocaleString('ru-RU')}
                        </div>
                      </div>

                      <div className="flex flex-col items-end space-y-1.5 pt-0.5">
                        <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                          <UserPlus className="w-3 h-3" />
                          <span>+{audienceData.new_subscribers_7d} за 7 дней</span>
                        </span>
                        <span className="text-[11px] text-gray-400 font-medium">
                          +{audienceData.new_subscribers_30d} за 30 дней
                        </span>
                      </div>
                    </div>

                    <p className="text-[11px] text-gray-400 pt-2 border-t border-white/5 leading-relaxed">
                      Подписчики получают уведомления о ваших новых событиях прямо в Telegram.
                    </p>
                  </div>
                </div>

                {/* Section 2: Unique Engaged People */}
                <div className="p-4 rounded-2xl bg-[#141724] border border-white/5 space-y-2">
                  <div className="flex items-center space-x-2 text-emerald-400">
                    <UserCheck className="w-4 h-4" />
                    <span className="text-xs font-semibold">Вовлечённая аудитория</span>
                  </div>

                  <div className="flex items-baseline space-x-2">
                    <span className="text-2xl font-bold text-white tracking-tight">
                      {audienceData.total_unique_engaged.toLocaleString('ru-RU')}
                    </span>
                    <span className="text-xs text-gray-400">уникальных участников</span>
                  </div>

                  <p className="text-[11px] text-gray-400 leading-relaxed">
                    Люди, которые подписались на ваши площадки, сохранили события в «Хочу пойти» или зарегистрировались «Я иду».
                  </p>
                </div>

                {/* Section 3: Event Response Activity (Views, Interest, Attendees) */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between px-1">
                    <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
                      Суммарная активность
                    </h3>
                    <span className="text-[11px] text-gray-500 font-medium">По всем событиям</span>
                  </div>

                  <div className="grid grid-cols-3 gap-2">
                    <div className="p-3 rounded-2xl bg-[#141724] border border-white/5 text-center space-y-1">
                      <div className="flex items-center justify-center space-x-1 text-indigo-400">
                        <Eye className="w-3.5 h-3.5" />
                        <span className="text-[11px] font-medium text-gray-400">Просмотры</span>
                      </div>
                      <div className="text-lg font-bold text-white tracking-tight">
                        {audienceData.total_views.toLocaleString('ru-RU')}
                      </div>
                    </div>

                    <div className="p-3 rounded-2xl bg-[#141724] border border-white/5 text-center space-y-1">
                      <div className="flex items-center justify-center space-x-1 text-pink-400">
                        <Heart className="w-3.5 h-3.5" />
                        <span className="text-[11px] font-medium text-gray-400">Интерес</span>
                      </div>
                      <div className="text-lg font-bold text-white tracking-tight">
                        {audienceData.total_interest.toLocaleString('ru-RU')}
                      </div>
                    </div>

                    <div className="p-3 rounded-2xl bg-[#141724] border border-white/5 text-center space-y-1">
                      <div className="flex items-center justify-center space-x-1 text-emerald-400">
                        <Users className="w-3.5 h-3.5" />
                        <span className="text-[11px] font-medium text-gray-400">Гости</span>
                      </div>
                      <div className="text-lg font-bold text-white tracking-tight">
                        {audienceData.total_attendees.toLocaleString('ru-RU')}
                      </div>
                    </div>
                  </div>
                </div>

                {/* Section 4: Breakdown by Organization (if multiple) */}
                {audienceData.organizations.length > 1 && (
                  <div className="space-y-2.5">
                    <div className="flex items-center justify-between px-1">
                      <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
                        Площадки и подписчики
                      </h3>
                    </div>

                    <div className="space-y-2">
                      {audienceData.organizations.map((org) => (
                        <div
                          key={org.id}
                          className="p-3.5 rounded-2xl bg-[#141724] border border-white/5 flex items-center justify-between gap-3"
                        >
                          <div className="min-w-0">
                            <div className="font-semibold text-xs text-white truncate">{org.name}</div>
                            <div className="text-[11px] text-gray-400">
                              {org.category} • {org.events_count} событий
                            </div>
                          </div>

                          <div className="text-right shrink-0">
                            <div className="text-sm font-bold text-white">
                              {org.subscribers_count} <span className="text-[10px] text-gray-400 font-normal">подписчиков</span>
                            </div>
                            <div className="text-[10px] text-emerald-400 font-medium">
                              +{org.new_subscribers_7d} за 7 дней
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Section 5: Events and Audience Response */}
                <div className="space-y-2.5">
                  <div className="flex items-center justify-between px-1">
                    <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
                      Отклик на события ({audienceData.recent_events.length})
                    </h3>
                  </div>

                  {audienceData.recent_events.length === 0 ? (
                    <div className="p-6 text-center rounded-2xl bg-[#141724] border border-white/5 space-y-2">
                      <Calendar className="w-6 h-6 text-gray-500 mx-auto" />
                      <p className="text-xs text-gray-400">Нет событий для анализа отклика</p>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {audienceData.recent_events.map((ev) => {
                        const dateStr = new Date(ev.start_at).toLocaleDateString('ru-RU', {
                          day: 'numeric',
                          month: 'short',
                          hour: '2-digit',
                          minute: '2-digit',
                        });

                        return (
                          <div
                            key={ev.id}
                            className="p-3.5 rounded-2xl bg-[#141724] border border-white/5 space-y-2"
                          >
                            <div className="flex items-start justify-between gap-2">
                              <div className="font-semibold text-xs text-white line-clamp-1">
                                {ev.title}
                              </div>
                              <span className="text-[10px] text-gray-400 shrink-0">{dateStr}</span>
                            </div>

                            <div className="flex items-center justify-between text-xs pt-1 border-t border-white/5">
                              <span className="text-[11px] text-gray-400 truncate max-w-[140px]">
                                {ev.venue_name}
                              </span>

                              <div className="flex items-center space-x-2.5 text-[11px]">
                                <span className="flex items-center space-x-1 text-gray-400">
                                  <Eye className="w-3 h-3 text-indigo-400" />
                                  <span>{ev.views_count}</span>
                                </span>
                                <span className="text-pink-400 font-medium">
                                  ● {ev.interest_count} интерес
                                </span>
                                <span className="text-emerald-400 font-medium">
                                  ● {ev.attendee_count} идут
                                </span>
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>

                {/* Section 6: Real-time Audience Information */}
                <div className="p-3.5 rounded-2xl bg-indigo-950/20 border border-indigo-500/20 flex items-start space-x-2.5 text-[11px] text-indigo-300">
                  <Info className="w-4 h-4 text-indigo-400 shrink-0 mt-0.5" />
                  <p className="leading-relaxed">
                    Здесь отображаются реальные пользователи, подписанные на организацию или отметившие интерес к вашим событиям. Статистика обновляется в реальном времени.
                  </p>
                </div>
              </div>
            ) : (
              <div className="py-12 text-center text-xs text-gray-400">
                Не удалось загрузить данные аудитории
              </div>
            )}
          </div>
        )}

        {/* TAB 5: BROADCASTS */}
        {activeTab === 'broadcasts' && (
          <div className="space-y-4">
            {/* Header Value Banner */}
            <div className="p-4 rounded-2xl bg-[#141724] border border-white/10 space-y-3">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="flex items-center space-x-3 min-w-0">
                  <div className="w-10 h-10 rounded-xl bg-indigo-500/15 border border-indigo-500/20 flex items-center justify-center text-indigo-400 shrink-0">
                    <Send className="w-5 h-5" />
                  </div>
                  <div className="min-w-0">
                    <h2 className="text-sm font-bold text-white tracking-tight">Рассылки в Telegram</h2>
                    <p className="text-[11px] text-gray-400">Общайтесь со своей аудиторией прямо в Telegram.</p>
                  </div>
                </div>

                {entitlements?.plan === 'pro' && (
                  <button
                    onClick={handleOpenComposer}
                    disabled={organizations.length === 0}
                    className="px-3.5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-semibold text-xs shadow-md shadow-indigo-600/30 transition-all btn-press flex items-center justify-center space-x-1.5 shrink-0 self-start sm:self-auto"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    <span>Создать рассылку</span>
                  </button>
                )}
              </div>

              <div className="text-[11px] text-indigo-200/80 leading-relaxed pt-2 border-t border-white/5">
                Отправляйте анонсы событий подписчикам площадок и персональные обновления гостям, нажавшим «Хочу пойти».
              </div>
            </div>

            {/* Pro Gate for Free vs Pro Quota Banner for Pro */}
            {organizations.length === 0 ? (
              <div className="p-6 text-center rounded-2xl bg-[#141724] border border-white/5 space-y-3">
                <Building2 className="w-8 h-8 text-gray-500 mx-auto" />
                <div>
                  <div className="text-xs font-semibold text-white">У вас пока нет созданных организаций</div>
                  <p className="text-[11px] text-gray-400 max-w-xs mx-auto mt-1">
                    {isAdmin
                      ? 'Для тестирования Pro-рассылок создайте организацию, чтобы привязать тариф к ней.'
                      : 'Создайте организацию, чтобы управлять анонсами и собирать базу подписчиков.'}
                  </p>
                </div>
                <button
                  onClick={onOpenCreateOrg}
                  className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold btn-press inline-flex items-center space-x-1.5"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>Создать организацию</span>
                </button>
              </div>
            ) : entitlements?.plan === 'pro' ? (
              <div className="p-3.5 rounded-2xl bg-[#141724] border border-purple-500/20 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="flex items-center space-x-2.5 min-w-0">
                  <div className="w-2.5 h-2.5 rounded-full shrink-0 bg-purple-400 shadow-sm shadow-purple-500/50" />
                  <div className="min-w-0 text-xs text-gray-200">
                    <span>
                      Тариф Pro: отправлено <strong className="text-white">{entitlements?.limits?.broadcasts_used_this_month ?? 0}</strong> из {entitlements?.limits?.broadcasts_per_month ?? 20} анонсов в этом месяце
                      {(entitlements?.limits?.broadcasts_remaining ?? 0) > 0 ? (
                        <span className="text-emerald-400 font-medium"> (осталось {entitlements?.limits?.broadcasts_remaining})</span>
                      ) : (
                        <span className="text-amber-400 font-medium"> (лимит месяца исчерпан)</span>
                      )}
                    </span>
                    {isAdmin && (
                      <button
                        onClick={handleAdminTogglePro}
                        disabled={isTogglingPlan}
                        className="text-[10px] text-amber-400 hover:text-amber-300 underline font-medium ml-2"
                      >
                        {isTogglingPlan ? '...' : '(тест: вернуть Free)'}
                      </button>
                    )}
                  </div>
                </div>
              </div>
            ) : (
              <div className="p-4 rounded-2xl bg-gradient-to-br from-purple-950/40 via-purple-900/20 to-[#141724] border border-purple-500/30 space-y-3.5">
                {isAdmin && (
                  <div className="p-2.5 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-between text-xs">
                    <span className="text-[11px] text-amber-300 font-medium">
                      🔧 <strong>Режим администратора:</strong> включить Pro для этой организации?
                    </span>
                    <button
                      onClick={handleAdminTogglePro}
                      disabled={isTogglingPlan}
                      className="px-2.5 py-1 rounded-lg bg-amber-600 hover:bg-amber-500 text-white font-semibold text-[11px] transition-all btn-press shrink-0 ml-2"
                    >
                      {isTogglingPlan ? '...' : 'Включить Pro'}
                    </button>
                  </div>
                )}

                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2 text-purple-300">
                    <Sparkles className="w-4 h-4 text-purple-400" />
                    <span className="text-xs font-bold uppercase tracking-wider">Pro для организаторов</span>
                  </div>
                  <span className="text-[10px] text-purple-300 font-semibold px-2 py-0.5 rounded-full bg-purple-500/20 border border-purple-500/30">в разработке</span>
                </div>

                <div className="text-xs font-semibold text-white">
                  Расширенные инструменты для работы с аудиторией
                </div>

                <div className="space-y-2 text-[11px] text-gray-300">
                  <div className="flex items-start space-x-2">
                    <span className="text-purple-400 font-bold shrink-0">📣</span>
                    <span><strong>Ручные рассылки в Telegram</strong> — отправка анонсов и новостей подписчикам организации (до 20 в месяц)</span>
                  </div>
                  <div className="flex items-start space-x-2">
                    <span className="text-purple-400 font-bold shrink-0">👥</span>
                    <span><strong>Аудитория гостей</strong> — отправка сообщений пользователям, нажавшим «Хочу пойти» на событие</span>
                  </div>
                  <div className="flex items-start space-x-2">
                    <span className="text-purple-400 font-bold shrink-0">📊</span>
                    <span><strong>Статистика рассылок</strong> — переходы по ссылкам и отклики гостей</span>
                  </div>
                  <div className="flex items-start space-x-2">
                    <span className="text-purple-400 font-bold shrink-0">🔔</span>
                    <span><strong>Автоматические напоминания</strong> <span className="text-[10px] text-purple-300 font-medium">(скоро)</span> — своевременные оповещения гостей перед началом</span>
                  </div>
                  <div className="flex items-start space-x-2">
                    <span className="text-purple-400 font-bold shrink-0">💌</span>
                    <span><strong>Повторные приглашения</strong> <span className="text-[10px] text-purple-300 font-medium">(скоро)</span> — персональные приглашения постоянным посетителям</span>
                  </div>
                  <div className="flex items-start space-x-2">
                    <span className="text-purple-400 font-bold shrink-0">🔁</span>
                    <span><strong>Сегменты аудитории</strong> <span className="text-[10px] text-purple-300 font-medium">(скоро)</span> — таргетинг по частым гостям и категориям</span>
                  </div>
                </div>

                <div className="pt-1">
                  <button
                    onClick={() => {
                      telegram.hapticImpact('light');
                      setIsProModalOpen(true);
                    }}
                    className="w-full py-2.5 px-4 rounded-xl bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white font-semibold text-xs transition-all shadow-md shadow-purple-600/25 flex items-center justify-center space-x-2 btn-press"
                  >
                    <Sparkles className="w-4 h-4" />
                    <span>Узнать о возможностях Pro</span>
                  </button>
                </div>
              </div>
            )}

            {/* Broadcasts History */}
            <div className="space-y-2.5">
              <div className="flex items-center justify-between px-1">
                <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
                  История кампаний ({broadcasts.length})
                </h3>
              </div>

              {isLoadingBroadcasts ? (
                <div className="py-12 text-center text-xs text-gray-400">Загрузка рассылок...</div>
              ) : broadcasts.length === 0 ? (
                <div className="p-6 text-center rounded-2xl bg-[#141724] border border-white/5 space-y-3">
                  <Send className="w-8 h-8 text-indigo-400/50 mx-auto" />
                  <div>
                    <div className="text-xs font-semibold text-white">
                      {entitlements?.plan === 'pro' ? 'Нет отправленных рассылок' : 'История рассылок пуста'}
                    </div>
                    <p className="text-[11px] text-gray-400 max-w-xs mx-auto mt-1">
                      {entitlements?.plan === 'pro'
                        ? 'Создайте свою первую рассылку: анонсируйте новое событие или отправьте новость подписчикам.'
                        : 'Здесь будут отображаться ваши отправленные анонсы и аналитика переходов.'}
                    </p>
                  </div>
                  {entitlements?.plan === 'pro' && (
                    <button
                      onClick={handleOpenComposer}
                      disabled={organizations.length === 0}
                      className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-semibold btn-press inline-flex items-center space-x-1.5"
                    >
                      <Plus className="w-3.5 h-3.5" />
                      <span>Создать рассылку</span>
                    </button>
                  )}
                </div>
              ) : (
                <div className="space-y-2.5">
                  {broadcasts.map((bcast) => {
                    const dateStr = new Date(bcast.created_at).toLocaleDateString('ru-RU', {
                      day: 'numeric',
                      month: 'short',
                      hour: '2-digit',
                      minute: '2-digit',
                    });

                    const targetLabel =
                      bcast.target_type === 'organization_subscribers'
                        ? 'Подписчики площадки'
                        : 'Интерес к событию';

                    return (
                      <div
                        key={bcast.id}
                        onClick={() => handleViewBroadcastDetail(bcast)}
                        className="p-3.5 rounded-2xl bg-[#141724] border border-white/5 hover:border-indigo-500/30 transition-all cursor-pointer space-y-2.5 card-press"
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="min-w-0">
                            <div className="font-semibold text-xs text-white truncate">
                              {bcast.event_title ? bcast.event_title : bcast.organization_name}
                            </div>
                            <div className="text-[11px] text-gray-400 truncate">
                              {bcast.organization_name} • {targetLabel}
                            </div>
                          </div>

                          {/* Status Pill */}
                          {bcast.status === 'completed' && (
                            <span className="flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 shrink-0">
                              <CheckCircle2 className="w-3 h-3" />
                              <span>Доставлено</span>
                            </span>
                          )}
                          {bcast.status === 'partially_failed' && (
                            <span className="flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/30 shrink-0">
                              <AlertTriangle className="w-3 h-3" />
                              <span>Частично</span>
                            </span>
                          )}
                          {(bcast.status === 'processing' || bcast.status === 'queued') && (
                            <span className="flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-indigo-500/10 text-indigo-400 border border-indigo-500/30 shrink-0">
                              <Clock className="w-3 h-3" />
                              <span>Отправка</span>
                            </span>
                          )}
                          {bcast.status === 'failed' && (
                            <span className="flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-red-500/10 text-red-400 border border-red-500/30 shrink-0">
                              <XCircle className="w-3 h-3" />
                              <span>Ошибка</span>
                            </span>
                          )}
                        </div>

                        {/* Delivery Metrics line */}
                        <div className="flex items-center justify-between text-xs pt-1 border-t border-white/5">
                          <div className="flex items-center space-x-2 text-[11px]">
                            <span className="text-white font-medium">
                              {bcast.sent_count}/{bcast.total_recipients} получ.
                            </span>
                            {bcast.blocked_count > 0 && (
                              <span className="text-amber-400">
                                • {bcast.blocked_count} блок
                              </span>
                            )}
                            {bcast.broadcast_type === 'transactional' && (
                              <span className="px-1.5 py-0.2 rounded text-[9px] bg-purple-500/20 text-purple-300">
                                Важное
                              </span>
                            )}
                          </div>
                          <span className="text-[10px] text-gray-500">{dateStr}</span>
                        </div>

                        {/* Attribution Analytics Badge Row */}
                        {((bcast.opened_count || 0) > 0 || (bcast.interest_count || 0) > 0 || (bcast.rsvp_count || 0) > 0) && (
                          <div className="flex items-center space-x-2 text-[10px] text-gray-300 pt-1 border-t border-white/5">
                            <span className="text-indigo-300 font-medium">
                              🧭 {bcast.opened_count || 0} переходов ({bcast.open_rate || 0}%)
                            </span>
                            {(bcast.interest_count || 0) > 0 && (
                              <span className="text-amber-300 font-medium">
                                • ❤️ {bcast.interest_count}
                              </span>
                            )}
                            {(bcast.rsvp_count || 0) > 0 && (
                              <span className="text-emerald-400 font-medium">
                                • 🎟 {bcast.rsvp_count}
                              </span>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        )}
        </div>
      </div>

      {/* COMPOSER MODAL */}
      {isComposerOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-fade-in overflow-y-auto">
          <div className="bg-[#121522] border border-white/10 rounded-3xl w-full max-w-lg p-5 space-y-4 max-h-[90vh] overflow-y-auto shadow-2xl">
            {/* Header */}
            <div className="flex items-center justify-between pb-3 border-b border-white/5">
              <div className="flex items-center space-x-2">
                <Send className="w-4 h-4 text-indigo-400" />
                <h3 className="text-sm font-bold text-white">Новая рассылка</h3>
              </div>
              <button
                onClick={() => setIsComposerOpen(false)}
                className="p-1 rounded-xl bg-white/5 hover:bg-white/10 text-gray-400 hover:text-white transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* 1. Organization selector */}
            {organizations.length > 1 && (
              <div className="space-y-1.5">
                <label className="text-[11px] font-semibold text-gray-300">Площадка</label>
                <select
                  value={composerOrgId}
                  onChange={(e) => {
                    setComposerOrgId(e.target.value);
                    const orgEvs = events.filter((ev) => ev.organization_id === e.target.value);
                    if (orgEvs.length > 0) setComposerEventId(orgEvs[0].id);
                  }}
                  className="w-full bg-[#181C2E] border border-white/10 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500"
                >
                  {organizations.map((org) => (
                    <option key={org.id} value={org.id}>
                      {org.name}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {/* Step 1: Что хотите отправить? */}
            <div className="space-y-2">
              <label className="text-[11px] font-semibold text-gray-300">Шаг 1. Что хотите отправить?</label>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => {
                    setComposerBroadcastType('marketing');
                    setComposerTemplateKey('event_announcement');
                  }}
                  className={`p-3 rounded-2xl border text-left transition-all ${
                    composerTemplateKey === 'event_announcement'
                      ? 'bg-purple-600/20 border-purple-500 text-white'
                      : 'bg-white/5 border-white/5 text-gray-400 hover:border-white/10'
                  }`}
                >
                  <div className="text-xs font-semibold flex items-center space-x-1.5">
                    <span>📣</span>
                    <span>Анонс события</span>
                  </div>
                  <div className="text-[10px] opacity-75 mt-1 leading-snug">
                    Рассказать подписчикам о новом или предстоящем событии
                  </div>
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setComposerBroadcastType('marketing');
                    setComposerTemplateKey('custom_update');
                    setComposerTargetType('organization_subscribers');
                  }}
                  className={`p-3 rounded-2xl border text-left transition-all ${
                    composerTemplateKey === 'custom_update'
                      ? 'bg-purple-600/20 border-purple-500 text-white'
                      : 'bg-white/5 border-white/5 text-gray-400 hover:border-white/10'
                  }`}
                >
                  <div className="text-xs font-semibold flex items-center space-x-1.5">
                    <span>📰</span>
                    <span>Новость организации</span>
                  </div>
                  <div className="text-[10px] opacity-75 mt-1 leading-snug">
                    Поделиться новостью площадки, анонсом сезона или дайджестом
                  </div>
                </button>
              </div>

              <div className="p-2.5 rounded-xl bg-purple-500/10 border border-purple-500/20 text-[10.5px] text-purple-200/90 leading-snug">
                Рассылка подписчикам в Telegram (тариф Pro). Не чаще 1 раза в 24 часа одному получателю. Сервисные уведомления об изменениях событий отправляются системой автоматически.
              </div>
            </div>

            {/* Step 2: Выберите событие (if event-linked) */}
            {composerTemplateKey !== 'custom_update' && (
              <div className="space-y-2">
                <label className="text-[11px] font-semibold text-gray-300">Шаг 2. Выберите событие</label>
                {events.filter((e) => e.organization_id === composerOrgId).length === 0 ? (
                  <div className="p-2.5 rounded-xl bg-amber-500/10 border border-amber-500/20 text-[11px] text-amber-300">
                    У этой организации пока нет опубликованных событий.
                  </div>
                ) : (
                  <select
                    value={composerEventId}
                    onChange={(e) => setComposerEventId(e.target.value)}
                    className="w-full bg-[#181C2E] border border-white/10 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500"
                  >
                    {events
                      .filter((e) => e.organization_id === composerOrgId)
                      .map((ev) => (
                        <option key={ev.id} value={ev.id}>
                          {ev.title}
                        </option>
                      ))}
                  </select>
                )}

                {/* Event Context Card */}
                {(() => {
                  const selectedEvent = events.find((e) => e.id === composerEventId);
                  if (!selectedEvent) return null;
                  return (
                    <div className="p-3 rounded-2xl bg-indigo-950/40 border border-indigo-500/30 space-y-2">
                      <div className="flex items-center justify-between text-[11px]">
                        <span className="font-semibold text-indigo-300 flex items-center gap-1.5">
                          🎟 Карточка в сообщении
                        </span>
                        <span className="text-[10px] text-indigo-200/70">
                          Кнопка: «Открыть событие»
                        </span>
                      </div>
                      <div className="p-2.5 rounded-xl bg-[#141724]/90 border border-white/5 space-y-1">
                        <div className="text-xs font-bold text-white truncate">
                          {selectedEvent.title}
                        </div>
                        <div className="flex items-center space-x-2 text-[11px] text-gray-400">
                          <span className="text-indigo-400 font-medium">
                            {new Date(selectedEvent.start_at).toLocaleDateString('ru-RU', {
                              day: 'numeric',
                              month: 'short',
                              hour: '2-digit',
                              minute: '2-digit',
                            })}
                          </span>
                          <span>•</span>
                          <span className="truncate">{selectedEvent.venue_name}</span>
                        </div>
                      </div>
                      <div className="text-[10.5px] text-gray-300 leading-snug">
                        {composerTargetType === 'event_interest' ? (
                          <span>
                            ❤️ Получат только пользователи, отметившие это событие (
                            {previewData ? previewData.eligible_recipients : (selectedEvent.interest_count || 0)} чел.
                            {previewData && previewData.total_audience > previewData.eligible_recipients && (
                              <span className="opacity-75"> из {previewData.total_audience}</span>
                            )}
                            )
                          </span>
                        ) : (
                          <span>👥 Сообщение будет содержать карточку события и кнопку быстрого перехода</span>
                        )}
                      </div>
                    </div>
                  );
                })()}
              </div>
            )}

            {/* Step 3: Кому отправить? */}
            <div className="space-y-1.5">
              <label className="text-[11px] font-semibold text-gray-300">
                {composerTemplateKey === 'custom_update' ? 'Получатели' : 'Шаг 3. Кому отправить?'}
              </label>
              {composerTemplateKey === 'custom_update' ? (
                <div className="p-2.5 rounded-xl bg-white/5 border border-white/5 text-[11px] text-gray-300 flex items-center space-x-2">
                  <Users className="w-4 h-4 text-indigo-400 shrink-0" />
                  <span>Новости организации отправляются всем подписчикам вашей страницы в Ivently.</span>
                </div>
              ) : (
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => setComposerTargetType('organization_subscribers')}
                    className={`p-2.5 rounded-xl border text-left transition-all ${
                      composerTargetType === 'organization_subscribers'
                        ? 'bg-indigo-600/20 border-indigo-500 text-white'
                        : 'bg-white/5 border-white/5 text-gray-400 hover:border-white/10'
                    }`}
                  >
                    <div className="text-xs font-semibold">👥 Подписчики</div>
                    <div className="text-[10px] opacity-70 mt-0.5">Все подписчики страницы организации</div>
                  </button>
                  <button
                    type="button"
                    onClick={() => setComposerTargetType('event_interest')}
                    className={`p-2.5 rounded-xl border text-left transition-all ${
                      composerTargetType === 'event_interest'
                        ? 'bg-indigo-600/20 border-indigo-500 text-white'
                        : 'bg-white/5 border-white/5 text-gray-400 hover:border-white/10'
                    }`}
                  >
                    <div className="text-xs font-semibold">❤️ «Хочу пойти»</div>
                    <div className="text-[10px] opacity-70 mt-0.5">Кто добавил это событие в избранное</div>
                  </button>
                </div>
              )}
            </div>

            {/* Step 4: Текст сообщения */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <label className="text-[11px] font-semibold text-gray-300">
                  {composerTemplateKey === 'custom_update'
                    ? 'Текст новости *'
                    : 'Комментарий к событию (опционально)'}
                </label>
                <span className="text-[10px] text-gray-500">{composerCustomText.length}/500</span>
              </div>
              <textarea
                value={composerCustomText}
                maxLength={500}
                rows={3}
                onChange={(e) => setComposerCustomText(e.target.value)}
                placeholder={
                  composerTemplateKey === 'custom_update'
                    ? 'Расскажите о новости площадки...'
                    : 'Дополнительные подробности или комментарий...'
                }
                className="w-full bg-[#181C2E] border border-white/10 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500 resize-none min-h-[68px]"
              />
            </div>

            {/* 5. Audience Preview Calculations */}
            <div className="p-3.5 rounded-2xl bg-[#181C2E] border border-white/5 space-y-2">
              <div className="text-[11px] font-semibold text-gray-300 uppercase tracking-wider">
                Оценка аудитории
              </div>
              {isLoadingPreview ? (
                <div className="text-xs text-gray-400 py-1">Выполняется расчёт получателей...</div>
              ) : previewError ? (
                <div className="space-y-2">
                  <div className="text-xs text-amber-300 py-1">{previewError}</div>
                  {(previewError.includes('Pro') || previewError.includes('лимит') || previewError.includes('ENTITLEMENT')) && (
                    <button
                      type="button"
                      onClick={() => {
                        telegram.hapticImpact('light');
                        setIsProModalOpen(true);
                      }}
                      className="text-xs font-semibold text-purple-300 hover:text-purple-200 flex items-center space-x-1.5 py-1 px-2.5 rounded-lg bg-purple-500/20 border border-purple-500/30 btn-press"
                    >
                      <Sparkles className="w-3.5 h-3.5 text-purple-400" />
                      <span>Узнать о возможностях Pro</span>
                    </button>
                  )}
                </div>
              ) : previewData ? (
                <div className="space-y-1.5 text-xs">
                  <div className="flex items-center justify-between">
                    <span className="text-gray-400">Всего в сегменте:</span>
                    <span className="font-semibold text-white">{previewData.total_audience} чел.</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-gray-400">Получат сообщение:</span>
                    <span className="font-bold text-emerald-400">{previewData.eligible_recipients} чел.</span>
                  </div>
                  {previewData.disabled_notifications_count > 0 && (
                    <div className="flex items-center justify-between text-[11px] text-gray-400">
                      <span>Отключили уведомления:</span>
                      <span className="text-gray-300">{previewData.disabled_notifications_count} чел.</span>
                    </div>
                  )}
                  {previewData.fatigued_recipients_count > 0 && (
                    <div className="flex items-center justify-between text-[11px] text-amber-300/90">
                      <span>Лимит отправки (уже получали за 24 ч):</span>
                      <span className="font-semibold">{previewData.fatigued_recipients_count} чел.</span>
                    </div>
                  )}
                </div>
              ) : null}
            </div>

            {/* 6. Message Preview Bubble */}
            {previewData && (
              <div className="space-y-1.5">
                <div className="text-[11px] font-semibold text-gray-300 uppercase tracking-wider">
                  Предпросмотр в Telegram
                </div>
                <div className="p-3.5 rounded-2xl bg-[#0E121E] border border-indigo-500/20 space-y-2.5 max-w-full overflow-hidden shadow-inner">
                  {previewData.cover_image_url && (
                    <div className="w-full h-36 rounded-xl overflow-hidden bg-black/40 border border-white/5">
                      <img
                        src={previewData.cover_image_url}
                        alt={previewData.event_title || 'Афиша'}
                        className="w-full h-full object-cover"
                        loading="lazy"
                      />
                    </div>
                  )}
                  <div
                    className="text-xs text-gray-200 whitespace-pre-wrap leading-relaxed break-words [overflow-wrap:break-word] [word-break:normal] max-w-full"
                    dangerouslySetInnerHTML={{ __html: previewData.preview_text }}
                  />
                  <div className="pt-2 border-t border-white/5">
                    <div className="w-full py-2 px-3 rounded-xl bg-indigo-600/30 border border-indigo-500/30 text-center text-xs font-semibold text-indigo-200 truncate">
                      {previewData.preview_button_text}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Error display with Pro CTA */}
            {previewError && (
              <div className="p-3 rounded-2xl bg-amber-500/10 border border-amber-500/20 space-y-2">
                <div className="text-xs text-amber-300 leading-snug">{previewError}</div>
                {(previewError.includes('Pro') || previewError.includes('лимит') || previewError.includes('ENTITLEMENT')) && (
                  <button
                    type="button"
                    onClick={() => {
                      telegram.hapticImpact('light');
                      setIsProModalOpen(true);
                    }}
                    className="text-xs font-semibold text-purple-300 hover:text-purple-200 flex items-center space-x-1.5 py-1 px-2.5 rounded-lg bg-purple-500/20 border border-purple-500/30 btn-press"
                  >
                    <Sparkles className="w-3.5 h-3.5 text-purple-400" />
                    <span>Узнать о возможностях Pro</span>
                  </button>
                )}
              </div>
            )}

            {/* Actions */}
            <div className="pt-2 flex items-center space-x-2.5">
              <button
                type="button"
                onClick={() => setIsComposerOpen(false)}
                className="flex-1 py-2.5 rounded-xl bg-white/5 hover:bg-white/10 text-xs font-semibold text-gray-300 transition-colors"
              >
                Отмена
              </button>
              <button
                type="button"
                onClick={handleSendBroadcast}
                disabled={!previewData || previewData.eligible_recipients === 0 || isSubmittingBroadcast}
                className="flex-1 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 disabled:hover:bg-indigo-600 text-xs font-semibold text-white shadow-md shadow-indigo-600/30 transition-all btn-press flex items-center justify-center space-x-1.5"
              >
                {isSubmittingBroadcast ? (
                  <span>Отправка...</span>
                ) : (
                  <>
                    <Send className="w-3.5 h-3.5" />
                    <span>Отправить ({previewData?.eligible_recipients || 0})</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* DETAIL MODAL */}
      {selectedBroadcast && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-fade-in overflow-y-auto">
          <div className="bg-[#121522] border border-white/10 rounded-3xl w-full max-w-lg p-5 space-y-4 max-h-[90vh] overflow-y-auto shadow-2xl">
            <div className="flex items-center justify-between pb-3 border-b border-white/5">
              <h3 className="text-sm font-bold text-white">Детали рассылки</h3>
              <button
                onClick={() => setSelectedBroadcast(null)}
                className="p-1 rounded-xl bg-white/5 hover:bg-white/10 text-gray-400 hover:text-white transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div className="p-3.5 rounded-2xl bg-[#181C2E] border border-white/5 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-gray-400">Площадка:</span>
                  <span className="font-semibold text-white">{selectedBroadcast.organization_name}</span>
                </div>
                {selectedBroadcast.event_title && (
                  <div className="flex items-center justify-between">
                    <span className="text-gray-400">Событие:</span>
                    <span className="font-semibold text-white">{selectedBroadcast.event_title}</span>
                  </div>
                )}
                <div className="flex items-center justify-between">
                  <span className="text-gray-400">Сегмент:</span>
                  <span className="font-medium text-indigo-300">
                    {selectedBroadcast.target_type === 'organization_subscribers'
                      ? 'Подписчики площадки'
                      : 'Интерес к событию'}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-gray-400">Статус:</span>
                  <span className={`font-semibold ${
                    selectedBroadcast.status === 'completed'
                      ? 'text-emerald-400'
                      : selectedBroadcast.status === 'partially_failed'
                      ? 'text-amber-400'
                      : selectedBroadcast.status === 'failed'
                      ? 'text-red-400'
                      : 'text-indigo-400'
                  }`}>
                    {selectedBroadcast.status === 'completed'
                      ? 'Доставлено'
                      : selectedBroadcast.status === 'partially_failed'
                      ? 'Частично доставлено'
                      : selectedBroadcast.status === 'failed'
                      ? 'Не доставлено'
                      : selectedBroadcast.status === 'processing'
                      ? 'В процессе...'
                      : selectedBroadcast.status}
                  </span>
                </div>
                <div className="flex items-center justify-between pt-1 border-t border-white/5">
                  <span className="text-gray-400">Доставлено:</span>
                  <span className="font-bold text-white">
                    {selectedBroadcast.sent_count} из {selectedBroadcast.total_recipients}
                  </span>
                </div>
                {selectedBroadcast.blocked_count > 0 && (
                  <div className="flex items-center justify-between text-amber-300">
                    <span>Заблокировали бота:</span>
                    <span>{selectedBroadcast.blocked_count} чел.</span>
                  </div>
                )}
                {selectedBroadcast.failed_count > 0 && (
                  <div className="flex items-center justify-between text-red-400">
                    <span>Не доставлено (не начат диалог):</span>
                    <span>{selectedBroadcast.failed_count} чел.</span>
                  </div>
                )}
              </div>

              {/* Attribution Analytics Card */}
              <div className="p-3.5 rounded-2xl bg-[#181C2E] border border-white/5 space-y-2.5">
                <div className="flex items-center justify-between">
                  <div className="text-[11px] font-semibold text-gray-300 uppercase tracking-wider">
                    Результат рассылки
                  </div>
                  <span className="text-[10px] text-gray-400">По этой рассылке</span>
                </div>

                <div className="grid grid-cols-3 gap-2 text-center">
                  <div className="p-2.5 rounded-xl bg-white/5 border border-white/5">
                    <div className="text-[10px] text-gray-400 mb-0.5">Переходы</div>
                    <div className="text-sm font-bold text-white">
                      {selectedBroadcast.opened_count || 0}
                    </div>
                    <div className="text-[10px] text-indigo-300 font-medium mt-0.5">
                      {selectedBroadcast.open_rate || 0}%
                    </div>
                  </div>

                  <div className="p-2.5 rounded-xl bg-white/5 border border-white/5">
                    <div className="text-[10px] text-gray-400 mb-0.5">Хочу пойти</div>
                    <div className="text-sm font-bold text-amber-300">
                      {selectedBroadcast.interest_count || 0}
                    </div>
                    <div className="text-[10px] text-amber-300/80 font-medium mt-0.5">
                      {selectedBroadcast.interest_conversion || 0}%
                    </div>
                  </div>

                  <div className="p-2.5 rounded-xl bg-white/5 border border-white/5">
                    <div className="text-[10px] text-gray-400 mb-0.5">Я иду</div>
                    <div className="text-sm font-bold text-emerald-400">
                      {selectedBroadcast.rsvp_count || 0}
                    </div>
                    <div className="text-[10px] text-emerald-400/80 font-medium mt-0.5">
                      {selectedBroadcast.rsvp_conversion || 0}%
                    </div>
                  </div>
                </div>
              </div>

              {/* Message preview */}
              <div className="space-y-1.5">
                <div className="text-[11px] font-semibold text-gray-300 uppercase tracking-wider">
                  Отправленный текст
                </div>
                <div className="p-3.5 rounded-2xl bg-[#0E121E] border border-white/5 space-y-2">
                  <div
                    className="text-xs text-gray-200 whitespace-pre-wrap leading-relaxed"
                    dangerouslySetInnerHTML={{ __html: selectedBroadcast.message_text }}
                  />
                  <div className="pt-2 border-t border-white/5">
                    <div className="w-full py-1.5 px-3 rounded-xl bg-indigo-600/20 text-center text-xs font-semibold text-indigo-300">
                      {selectedBroadcast.button_text}
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div className="pt-2">
              <button
                type="button"
                onClick={() => setSelectedBroadcast(null)}
                className="w-full py-2.5 rounded-xl bg-white/5 hover:bg-white/10 text-xs font-semibold text-gray-300 transition-colors"
              >
                Закрыть
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Ivently Pro Checkout Modal */}
      {isProModalOpen && (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4 bg-black/75 backdrop-blur-sm animate-fade-in">
          <div className="w-full max-w-md bg-[#141724] border border-white/10 rounded-t-3xl sm:rounded-3xl p-5 space-y-4 shadow-2xl animate-sheet-slide-up max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2.5">
                <div className="w-8 h-8 rounded-xl bg-purple-500/20 border border-purple-500/30 flex items-center justify-center text-purple-400">
                  <Sparkles className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-white tracking-tight">Ivently Pro</h3>
                  <p className="text-[11px] text-gray-400">Для регулярных организаторов</p>
                </div>
              </div>
              <button
                onClick={() => setIsProModalOpen(false)}
                className="p-1.5 rounded-full hover:bg-white/10 text-gray-400 hover:text-white transition-colors"
                aria-label="Закрыть"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* If Pro is already active */}
            {entitlements?.plan === 'pro' ? (
              <div className="p-4 rounded-2xl bg-gradient-to-br from-purple-950/40 via-purple-900/20 to-[#141724] border border-purple-500/30 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-purple-300 uppercase tracking-wider flex items-center space-x-1.5">
                    <Sparkles className="w-3.5 h-3.5 text-purple-400" />
                    <span>Тариф Pro активен</span>
                  </span>
                  <span className="text-[10px] text-emerald-400 font-semibold px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/30">
                    Активен
                  </span>
                </div>
                <div className="text-[11px] text-gray-300 space-y-1">
                  <div>
                    Срок действия:{' '}
                    <strong className="text-white">
                      {entitlements.expires_at
                        ? new Date(entitlements.expires_at).toLocaleDateString('ru-RU')
                        : 'Бессрочно'}
                    </strong>
                  </div>
                  <div>
                    Маркетинговые рассылки:{' '}
                    <strong className="text-white">
                      {entitlements.limits.broadcasts_used_this_month} из {entitlements.limits.broadcasts_per_month}
                    </strong>{' '}
                    в этом месяце
                  </div>
                </div>

                <div className="pt-2 border-t border-white/10">
                  <p className="text-[11px] text-gray-400 mb-2">
                    Вы можете продлить тариф заранее. Новый период (+30 дней) добавится к текущему сроку действия.
                  </p>
                  <button
                    onClick={handleInitiateProPayment}
                    disabled={isPaying || !(paymentConfig?.payments_enabled ?? false)}
                    className="w-full py-2.5 rounded-xl bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white font-semibold text-xs transition-all btn-press flex items-center justify-center space-x-2"
                  >
                    {isPaying ? (
                      <>
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        <span>Создаём платёж...</span>
                      </>
                    ) : (
                      <>
                        <CreditCard className="w-3.5 h-3.5" />
                        <span>Продлить на 30 дней ({paymentConfig?.pro_monthly_price_rub ?? 499} ₽)</span>
                      </>
                    )}
                  </button>
                </div>
              </div>
            ) : (
              /* Upgrade to Pro Flow */
              <div className="space-y-3 pt-1">
                {/* Price & Period Badge */}
                <div className="p-4 rounded-2xl bg-gradient-to-br from-purple-950/40 via-purple-900/20 to-[#141724] border border-purple-500/30 text-center space-y-1">
                  <div className="text-2xl font-black text-white tracking-tight">
                    {paymentConfig?.pro_monthly_price_rub ?? 499} ₽
                    <span className="text-xs font-normal text-purple-300 ml-1.5">
                      / {paymentConfig?.pro_days ?? 30} дней
                    </span>
                  </div>
                  <div className="text-[11px] text-gray-300 font-medium">
                    Разовая оплата на 30 дней. Автопродления нет.
                  </div>
                </div>

                {/* What's included */}
                <div className="p-3.5 rounded-2xl bg-white/5 border border-white/5 space-y-2">
                  <div className="text-xs font-bold text-purple-300 uppercase tracking-wider flex items-center space-x-1.5">
                    <Sparkles className="w-3.5 h-3.5 text-purple-400" />
                    <span>В тариф Pro входит</span>
                  </div>
                  <div className="space-y-1.5 text-[11px] text-gray-200">
                    <div className="flex items-center space-x-2">
                      <span className="text-purple-400 font-bold">✓</span>
                      <span><strong>Ручные рассылки в Telegram</strong> (до 20 в месяц)</span>
                    </div>
                    <div className="flex items-center space-x-2">
                      <span className="text-purple-400 font-bold">✓</span>
                      <span><strong>Расширенная аналитика рассылок</strong> (доставка, переходы, отклики «Хочу пойти» и «Я иду»)</span>
                    </div>
                    <div className="flex items-center space-x-2">
                      <span className="text-purple-400 font-bold">✓</span>
                      <span><strong>Таргетинг по аудитории</strong> (подписчики площадки или гости с интересом к событию)</span>
                    </div>
                    <div className="flex items-center space-x-2">
                      <span className="text-emerald-400 font-bold">✓</span>
                      <span><strong>Транзакционные уведомления</strong> об изменениях всегда бесплатны</span>
                    </div>
                  </div>
                </div>

                {/* Email for receipt */}
                <div className="space-y-1.5">
                  <label className="text-[11px] font-medium text-gray-300 flex items-center justify-between">
                    <span>Email для чека</span>
                    <span className="text-[10px] text-gray-500">электронный чек</span>
                  </label>
                  <input
                    type="email"
                    value={checkoutEmail}
                    onChange={(e) => setCheckoutEmail(e.target.value)}
                    placeholder="you@example.com"
                    className="w-full px-3 py-2 rounded-xl bg-white/5 border border-white/10 text-white text-xs placeholder:text-gray-600 focus:outline-none focus:border-purple-500/50 transition-colors"
                  />
                  <p className="text-[10px] text-gray-500">
                    Для плательщиков НПД электронный чек формируется после зачисления платежа.
                  </p>
                </div>

                {/* CTA Action */}
                {paymentConfig?.payments_enabled ? (
                  <button
                    onClick={handleInitiateProPayment}
                    disabled={isPaying}
                    className="w-full py-3 rounded-2xl bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white font-bold text-xs transition-all btn-press shadow-lg shadow-purple-600/30 flex items-center justify-center space-x-2"
                  >
                    {isPaying ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        <span>Создаём платёж...</span>
                      </>
                    ) : (
                      <>
                        <CreditCard className="w-4 h-4" />
                        <span>Оплатить {paymentConfig?.pro_monthly_price_rub ?? 499} ₽</span>
                      </>
                    )}
                  </button>
                ) : (
                  <div className="space-y-1.5">
                    <button
                      disabled
                      className="w-full py-3 rounded-2xl bg-white/5 border border-white/10 text-gray-400 font-semibold text-xs cursor-not-allowed text-center"
                    >
                      Оплата Pro пока недоступна
                    </button>
                    <p className="text-[10px] text-gray-500 text-center">
                      Мы готовим запуск онлайн-оплаты через ЮKassa.
                    </p>
                  </div>
                )}
              </div>
            )}

            <button
              onClick={() => setIsProModalOpen(false)}
              className="w-full py-2.5 rounded-xl bg-white/5 hover:bg-white/10 text-white text-xs font-semibold transition-colors btn-press"
            >
              Закрыть
            </button>
          </div>
        </div>
      )}

      {/* Payment Return Status Polling Modal */}
      {paymentPollStatus !== null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-fade-in">
          <div className="w-full max-w-sm bg-[#141724] border border-white/15 rounded-3xl p-5 space-y-4 shadow-2xl text-center">
            {paymentPollStatus === 'checking' && (
              <div className="space-y-3 py-4">
                <div className="flex justify-center">
                  <Loader2 className="w-10 h-10 text-purple-400 animate-spin" />
                </div>
                <h3 className="text-base font-bold text-white">Проверяем оплату...</h3>
                <p className="text-xs text-gray-400">
                  Пожалуйста, подождите, связываемся со шлюзом ЮKassa для подтверждения транзакции.
                </p>
              </div>
            )}

            {paymentPollStatus === 'success' && (
              <div className="space-y-3 py-2">
                <div className="flex justify-center">
                  <CheckCircle2 className="w-12 h-12 text-emerald-400" />
                </div>
                <h3 className="text-base font-bold text-white">Pro успешно активирован 🎉</h3>
                <p className="text-xs text-gray-300">
                  {activePollOrder?.expires_at ? (
                    <>Тариф Pro активен до <strong>{new Date(activePollOrder.expires_at).toLocaleDateString('ru-RU')}</strong>.</>
                  ) : (
                    <>Тариф Pro активен на 30 дней.</>
                  )}
                  <br />
                  Вам доступно до 20 маркетинговых рассылок в месяц.
                </p>
                {activePollOrder?.receipt_url && (
                  <div className="pt-2">
                    <a
                      href={activePollOrder.receipt_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-xl bg-purple-500/20 text-purple-300 text-xs font-medium"
                    >
                      <Receipt className="w-3.5 h-3.5" />
                      <span>Открыть электронный чек</span>
                    </a>
                  </div>
                )}
                <button
                  onClick={() => {
                    setPaymentPollStatus(null);
                    loadEntitlements();
                  }}
                  className="w-full py-2.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold transition-colors btn-press mt-2"
                >
                  Отлично
                </button>
              </div>
            )}

            {paymentPollStatus === 'pending' && (
              <div className="space-y-3 py-2">
                <div className="flex justify-center">
                  <Clock className="w-12 h-12 text-amber-400" />
                </div>
                <h3 className="text-base font-bold text-white">Платёж ещё обрабатывается</h3>
                <p className="text-xs text-gray-400">
                  Банк обрабатывает операцию. Мы автоматически активируем Pro сразу после подтверждения зачисления.
                </p>
                <div className="flex space-x-2 pt-2">
                  <button
                    onClick={() => {
                      if (activePollOrder?.id) {
                        setPaymentPollStatus('checking');
                        api.getPaymentOrder(activePollOrder.id)
                          .then((ord) => {
                            setActivePollOrder(ord);
                            if (ord.status === 'succeeded') {
                              setPaymentPollStatus('success');
                              loadEntitlements();
                            } else {
                              setPaymentPollStatus('pending');
                            }
                          })
                          .catch(() => setPaymentPollStatus('pending'));
                      }
                    }}
                    className="flex-1 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold btn-press"
                  >
                    Проверить снова
                  </button>
                  <button
                    onClick={() => setPaymentPollStatus(null)}
                    className="px-3 py-2 rounded-xl bg-white/10 hover:bg-white/15 text-gray-300 text-xs font-semibold btn-press"
                  >
                    Закрыть
                  </button>
                </div>
              </div>
            )}

            {paymentPollStatus === 'failed' && (
              <div className="space-y-3 py-2">
                <div className="flex justify-center">
                  <XCircle className="w-12 h-12 text-red-400" />
                </div>
                <h3 className="text-base font-bold text-white">Оплата не завершена</h3>
                <p className="text-xs text-gray-400">
                  Платёж был отменён или прерван. Средства не были списаны.
                </p>
                <div className="flex space-x-2 pt-2">
                  <button
                    onClick={() => {
                      setPaymentPollStatus(null);
                      setIsProModalOpen(true);
                    }}
                    className="flex-1 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold btn-press"
                  >
                    Попробовать снова
                  </button>
                  <button
                    onClick={() => setPaymentPollStatus(null)}
                    className="px-3 py-2 rounded-xl bg-white/10 hover:bg-white/15 text-gray-300 text-xs font-semibold btn-press"
                  >
                    Закрыть
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

