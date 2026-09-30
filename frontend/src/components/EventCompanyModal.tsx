import React, { useState, useEffect, useCallback } from 'react';
import { 
  X, 
  Users, 
  UserPlus, 
  Eye, 
  Send, 
  MessageCircle, 
  Clock, 
  ShieldCheck, 
  AlertCircle,
  Sparkles,
  ExternalLink
} from 'lucide-react';
import type { 
  EventResponse, 
  CompanyStatusResponse, 
  CompanyMemberItem, 
  CompanyRequestsResponse, 
  CompanyMatchItem 
} from '../types';
import { api, extractErrorMessage } from '../services/api';
import { telegram } from '../services/telegram';
import { SafeAvatar } from './SafeAvatar';

interface EventCompanyModalProps {
  event: EventResponse | null;
  isOpen: boolean;
  onClose: () => void;
  onRequireParticipation?: () => void;
}

export const EventCompanyModal: React.FC<EventCompanyModalProps> = ({
  event,
  isOpen,
  onClose,
  onRequireParticipation,
}) => {
  const [activeTab, setActiveTab] = useState<'members' | 'requests' | 'matches'>('members');
  const [status, setStatus] = useState<CompanyStatusResponse | null>(null);
  const [members, setMembers] = useState<CompanyMemberItem[]>([]);
  const [requests, setRequests] = useState<CompanyRequestsResponse>({ incoming: [], outgoing: [] });
  const [matches, setMatches] = useState<CompanyMatchItem[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [actionLoadingId, setActionLoadingId] = useState<string | number | null>(null);
  
  // Note form state
  const [isEditingNote, setIsEditingNote] = useState<boolean>(false);
  const [noteText, setNoteText] = useState<string>('');
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3500);
  };

  const loadData = useCallback(async (showSpinner = true) => {
    if (!event) return;
    if (showSpinner) setIsLoading(true);
    setErrorMessage(null);

    try {
      const statusRes = await api.getCompanyStatus(event.id);
      setStatus(statusRes);
      setNoteText(statusRes.note || '');

      // Load members, requests, matches in parallel
      const [membersRes, reqsRes, matchesRes] = await Promise.all([
        api.getCompanyMembers(event.id).catch(() => []),
        api.getCompanyRequests(event.id).catch(() => ({ incoming: [], outgoing: [] })),
        api.getCompanyMatches(event.id).catch(() => [])
      ]);

      setMembers(membersRes);
      setRequests(reqsRes);
      setMatches(matchesRes);

      // Default to matches tab if there are new matches and user clicked
      if (matchesRes.length > 0 && activeTab === 'members' && !statusRes.is_active) {
        // keep current
      }
    } catch (err: any) {
      setErrorMessage(extractErrorMessage(err, 'Не удалось загрузить данные поиска компании'));
    } finally {
      if (showSpinner) setIsLoading(false);
    }
  }, [event, activeTab]);

  useEffect(() => {
    if (isOpen && event) {
      loadData(true);
    }
  }, [isOpen, event, loadData]);

  if (!isOpen || !event) return null;

  const isUserParticipating = Boolean(event.is_attending || event.current_user_interested);

  // Opt-in / Update note handler
  const handleOptIn = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!event) return;

    if (!isUserParticipating) {
      showToast('Сначала нажмите «Хочу пойти» или «Я иду»');
      onRequireParticipation?.();
      return;
    }

    setActionLoadingId('opt-in');
    try {
      telegram.hapticImpact('light');
      const updated = await api.updateCompanyProfile(event.id, {
        is_active: true,
        note: noteText.trim() || undefined
      });
      setStatus(updated);
      setIsEditingNote(false);
      telegram.hapticSuccess();
      showToast('Анкета опубликована!');
      await loadData(false);
    } catch (err: any) {
      telegram.hapticError();
      showToast(extractErrorMessage(err, 'Ошибка при публикации анкеты'));
    } finally {
      setActionLoadingId(null);
    }
  };

  // Opt-out handler
  const handleOptOut = async () => {
    if (!event) return;
    setActionLoadingId('opt-out');
    try {
      telegram.hapticImpact('light');
      const updated = await api.optOutCompany(event.id);
      setStatus(updated);
      setIsEditingNote(false);
      showToast('Анкета скрыта');
      await loadData(false);
    } catch (err: any) {
      showToast(extractErrorMessage(err, 'Ошибка при скрытии анкеты'));
    } finally {
      setActionLoadingId(null);
    }
  };

  // Send request
  const handleSendRequest = async (targetUserId: number) => {
    if (!event) return;
    if (!status?.is_active) {
      showToast('Сначала активируйте свою анкету выше');
      return;
    }

    setActionLoadingId(targetUserId);
    try {
      telegram.hapticImpact('medium');
      const res = await api.sendCompanyRequest(event.id, targetUserId);
      if (res.match_created) {
        telegram.hapticSuccess();
        showToast('🎉 Взаимное совпадение! Компания найдена!');
        setActiveTab('matches');
      } else {
        telegram.hapticSuccess();
        showToast('Запрос отправлен!');
      }
      await loadData(false);
    } catch (err: any) {
      telegram.hapticError();
      showToast(extractErrorMessage(err, 'Не удалось отправить запрос'));
    } finally {
      setActionLoadingId(null);
    }
  };

  // Accept request
  const handleAcceptRequest = async (requestId: string) => {
    if (!event) return;
    setActionLoadingId(requestId);
    try {
      telegram.hapticImpact('heavy');
      await api.acceptCompanyRequest(event.id, requestId);
      telegram.hapticSuccess();
      showToast('🎉 Запрос принят! Вы нашли компанию!');
      setActiveTab('matches');
      await loadData(false);
    } catch (err: any) {
      telegram.hapticError();
      showToast(extractErrorMessage(err, 'Не удалось принять запрос'));
    } finally {
      setActionLoadingId(null);
    }
  };

  // Decline request
  const handleDeclineRequest = async (requestId: string) => {
    if (!event) return;
    setActionLoadingId(requestId);
    try {
      telegram.hapticImpact('light');
      await api.declineCompanyRequest(event.id, requestId);
      showToast('Запрос отклонен');
      await loadData(false);
    } catch (err: any) {
      showToast(extractErrorMessage(err, 'Не удалось отклонить запрос'));
    } finally {
      setActionLoadingId(null);
    }
  };

  // Cancel outgoing request
  const handleCancelRequest = async (requestId: string) => {
    if (!event) return;
    setActionLoadingId(requestId);
    try {
      telegram.hapticImpact('light');
      await api.cancelCompanyRequest(event.id, requestId);
      showToast('Запрос отменен');
      await loadData(false);
    } catch (err: any) {
      showToast(extractErrorMessage(err, 'Не удалось отменить запрос'));
    } finally {
      setActionLoadingId(null);
    }
  };

  return (
    <div className="fixed inset-0 z-[70] flex flex-col justify-end sm:justify-center items-center bg-black/85 backdrop-fade-in p-0 sm:p-4">
      {/* Bottom Sheet Modal Container */}
      <div 
        className="w-full max-w-lg bg-[#0F121C] sm:rounded-3xl rounded-t-[28px] border border-white/10 overflow-hidden shadow-2xl flex flex-col max-h-[92vh] sheet-slide-up"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="px-5 py-4 border-b border-white/8 flex items-center justify-between shrink-0 bg-[#131724]">
          <div className="flex items-center space-x-2.5 min-w-0">
            <div className="w-8 h-8 rounded-xl bg-indigo-600/20 text-indigo-400 flex items-center justify-center shrink-0 border border-indigo-500/30">
              <Users className="w-4 h-4" />
            </div>
            <div className="min-w-0">
              <h3 className="text-base font-bold text-white tracking-tight leading-none truncate">
                Найти компанию
              </h3>
              <p className="text-[11px] text-gray-400 truncate mt-1">
                {event.title}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-full bg-white/5 hover:bg-white/10 text-gray-400 hover:text-white transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Toast alert */}
        {toastMessage && (
          <div className="mx-4 mt-3 px-3.5 py-2 rounded-xl bg-indigo-600/90 text-white text-xs font-medium flex items-center space-x-2 animate-fade-in shrink-0">
            <Sparkles className="w-3.5 h-3.5 shrink-0" />
            <span>{toastMessage}</span>
          </div>
        )}

        {/* Error banner */}
        {errorMessage && (
          <div className="mx-4 mt-3 px-3.5 py-2 rounded-xl bg-red-950/60 border border-red-500/30 text-red-200 text-xs flex items-center space-x-2 shrink-0">
            <AlertCircle className="w-3.5 h-3.5 shrink-0 text-red-400" />
            <span>{errorMessage}</span>
          </div>
        )}

        {/* Scrollable Container */}
        <div className="p-4 sm:p-5 overflow-y-auto space-y-4 no-scrollbar">

          {/* Section 1: Opt-in / Status Card */}
          {status?.is_active ? (
            <div className="p-3.5 rounded-2xl bg-emerald-950/30 border border-emerald-500/30 space-y-2.5">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <div className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse" />
                  <span className="text-xs font-bold text-emerald-300">Вы видны другим участникам</span>
                </div>
                <div className="flex items-center space-x-1.5">
                  <button
                    onClick={() => setIsEditingNote(!isEditingNote)}
                    className="text-[11px] font-medium text-indigo-300 hover:text-indigo-200 px-2 py-1 rounded-lg bg-indigo-500/15"
                  >
                    {isEditingNote ? 'Скрыть форму' : 'Изменить заметку'}
                  </button>
                  <button
                    onClick={handleOptOut}
                    disabled={actionLoadingId === 'opt-out'}
                    className="text-[11px] font-medium text-gray-400 hover:text-red-300 px-2 py-1 rounded-lg hover:bg-red-500/10 transition-colors"
                  >
                    Скрыть
                  </button>
                </div>
              </div>

              {status.note && !isEditingNote && (
                <div className="text-xs text-gray-200 italic bg-black/20 p-2.5 rounded-xl border border-white/5">
                  «{status.note}»
                </div>
              )}

              {isEditingNote && (
                <form onSubmit={handleOptIn} className="space-y-2 pt-1">
                  <textarea
                    value={noteText}
                    onChange={(e) => setNoteText(e.target.value.slice(0, 140))}
                    placeholder="Пара слов о себе или компании, которую ищете..."
                    rows={2}
                    className="w-full text-xs p-2.5 rounded-xl bg-black/40 border border-white/10 text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500 transition-colors"
                  />
                  <div className="flex items-center justify-between text-[10px] text-gray-400">
                    <span>{140 - noteText.length} символов</span>
                    <button
                      type="submit"
                      disabled={actionLoadingId === 'opt-in'}
                      className="px-3 py-1 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs transition-colors"
                    >
                      Сохранить
                    </button>
                  </div>
                </form>
              )}
            </div>
          ) : (
            <div className="p-4 rounded-2xl bg-[#171B29] border border-white/8 space-y-3">
              <div className="flex items-start space-x-3">
                <div className="w-8 h-8 rounded-xl bg-indigo-600/20 text-indigo-400 flex items-center justify-center shrink-0 mt-0.5">
                  <UserPlus className="w-4 h-4" />
                </div>
                <div className="min-w-0 flex-1">
                  <h4 className="text-xs font-bold text-white">Ищете с кем пойти?</h4>
                  <p className="text-[11px] text-gray-400 mt-0.5 leading-relaxed">
                    Активируйте анкету, чтобы видеть других участников и знакомиться. Telegram открывается только взаимно.
                  </p>
                </div>
              </div>

              {!isUserParticipating ? (
                <div className="p-2.5 rounded-xl bg-purple-950/40 border border-purple-500/30 text-purple-300 text-xs flex items-center justify-between">
                  <span>Для поиска компании сначала отметьте участие:</span>
                  <button
                    onClick={() => {
                      onClose();
                      onRequireParticipation?.();
                    }}
                    className="ml-2 px-2.5 py-1 rounded-lg bg-purple-600 text-white font-semibold text-xs shrink-0"
                  >
                    Хочу пойти
                  </button>
                </div>
              ) : (
                <div className="space-y-2">
                  <textarea
                    value={noteText}
                    onChange={(e) => setNoteText(e.target.value.slice(0, 140))}
                    placeholder="Пара слов о себе или пожелания (опционально, до 140 симв.)"
                    rows={2}
                    className="w-full text-xs p-2.5 rounded-xl bg-black/30 border border-white/10 text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500 transition-colors"
                  />
                  <button
                    onClick={() => handleOptIn()}
                    disabled={actionLoadingId === 'opt-in'}
                    className="w-full py-2.5 px-4 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs flex items-center justify-center space-x-1.5 transition-colors shadow-lg shadow-indigo-600/25"
                  >
                    <Eye className="w-3.5 h-3.5" />
                    <span>Найти компанию</span>
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Section 2: Tab Navigation */}
          <div className="flex rounded-xl bg-[#141824] p-1 border border-white/5 text-xs font-semibold">
            <button
              onClick={() => setActiveTab('members')}
              className={`flex-1 py-1.5 rounded-lg flex items-center justify-center space-x-1.5 transition-colors ${
                activeTab === 'members'
                  ? 'bg-indigo-600 text-white shadow-sm'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              <span>Участники</span>
              <span className={`text-[10px] px-1.5 py-0.2 rounded-full ${
                activeTab === 'members' ? 'bg-indigo-500/50 text-white' : 'bg-white/10 text-gray-400'
              }`}>
                {members.length}
              </span>
            </button>

            <button
              onClick={() => setActiveTab('requests')}
              className={`flex-1 py-1.5 rounded-lg flex items-center justify-center space-x-1.5 transition-colors relative ${
                activeTab === 'requests'
                  ? 'bg-indigo-600 text-white shadow-sm'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              <span>Запросы</span>
              {requests.incoming.length > 0 && (
                <span className="w-2 h-2 rounded-full bg-red-500 absolute top-1 right-2 animate-ping" />
              )}
              <span className={`text-[10px] px-1.5 py-0.2 rounded-full ${
                activeTab === 'requests' ? 'bg-indigo-500/50 text-white' : 'bg-white/10 text-gray-400'
              }`}>
                {requests.incoming.length}
              </span>
            </button>

            <button
              onClick={() => setActiveTab('matches')}
              className={`flex-1 py-1.5 rounded-lg flex items-center justify-center space-x-1.5 transition-colors ${
                activeTab === 'matches'
                  ? 'bg-indigo-600 text-white shadow-sm'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              <span>Компания</span>
              <span className={`text-[10px] px-1.5 py-0.2 rounded-full ${
                activeTab === 'matches' ? 'bg-indigo-500/50 text-white' : 'bg-white/10 text-gray-400'
              }`}>
                {matches.length}
              </span>
            </button>
          </div>

          {/* Section 3: Tab Content */}
          {isLoading ? (
            <div className="py-12 flex flex-col items-center justify-center space-y-2 text-gray-400">
              <div className="w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
              <span className="text-xs">Загрузка...</span>
            </div>
          ) : activeTab === 'members' ? (
            /* TAB 1: MEMBERS LIST */
            <div className="space-y-2.5">
              {members.length === 0 ? (
                <div className="py-10 text-center space-y-2">
                  <div className="w-12 h-12 rounded-2xl bg-white/5 mx-auto flex items-center justify-center text-gray-400">
                    <Users className="w-6 h-6" />
                  </div>
                  <div className="text-xs font-semibold text-white">Пока никто не ищет компанию</div>
                  <p className="text-[11px] text-gray-400 max-w-xs mx-auto">
                    Станьте первым! Опубликуйте анкету выше, и другие участники смогут вам написать.
                  </p>
                </div>
              ) : (
                members.map((member) => (
                  <div
                    key={member.user_id}
                    className="p-3.5 rounded-2xl bg-[#171B29] border border-white/5 space-y-2.5 hover:border-white/10 transition-colors"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-2.5 min-w-0">
                        <SafeAvatar
                          src={member.avatar_url}
                          name={member.display_name}
                          className="w-9 h-9 rounded-full object-cover shrink-0"
                        />
                        <div className="min-w-0">
                          <div className="text-xs font-bold text-white truncate">
                            {member.display_name}
                          </div>
                          <div className="flex items-center space-x-1.5 text-[10px]">
                            {member.attendance_status === 'going' ? (
                              <span className="text-emerald-400 font-medium">● Идёт</span>
                            ) : (
                              <span className="text-purple-400 font-medium">● Интересуется</span>
                            )}
                          </div>
                        </div>
                      </div>

                      {/* Action Button */}
                      <div>
                        {member.relationship_status === 'matched' ? (
                          <button
                            onClick={() => setActiveTab('matches')}
                            className="px-2.5 py-1 rounded-xl bg-emerald-500/20 text-emerald-300 text-[11px] font-semibold flex items-center space-x-1"
                          >
                            <Sparkles className="w-3 h-3" />
                            <span>В компании</span>
                          </button>
                        ) : member.relationship_status === 'pending_outgoing' ? (
                          <span className="px-2.5 py-1 rounded-xl bg-white/10 text-gray-400 text-[11px] font-medium flex items-center space-x-1">
                            <Clock className="w-3 h-3" />
                            <span>Запрос отправлен</span>
                          </span>
                        ) : member.relationship_status === 'pending_incoming' ? (
                          <button
                            onClick={() => setActiveTab('requests')}
                            className="px-2.5 py-1 rounded-xl bg-indigo-600 text-white text-[11px] font-semibold animate-pulse"
                          >
                            Ответить
                          </button>
                        ) : (
                          <button
                            onClick={() => handleSendRequest(member.user_id)}
                            disabled={actionLoadingId === member.user_id}
                            className="px-3 py-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold flex items-center space-x-1.5 transition-colors disabled:opacity-60"
                          >
                            <Send className="w-3 h-3" />
                            <span>Познакомиться</span>
                          </button>
                        )}
                      </div>
                    </div>

                    {/* Member note if present */}
                    {member.note && (
                      <div className="text-[11px] text-gray-300 bg-black/25 px-2.5 py-1.5 rounded-xl border border-white/5 italic">
                        «{member.note}»
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          ) : activeTab === 'requests' ? (
            /* TAB 2: REQUESTS (INCOMING & OUTGOING) */
            <div className="space-y-4">
              {/* Incoming Section */}
              <div className="space-y-2">
                <div className="text-xs font-bold text-gray-300 flex items-center space-x-1.5">
                  <UserPlus className="w-3.5 h-3.5 text-indigo-400" />
                  <span>Входящие запросы ({requests.incoming.length})</span>
                </div>
                {requests.incoming.length === 0 ? (
                  <div className="p-4 rounded-xl bg-white/5 text-center text-xs text-gray-400">
                    Нет новых входящих запросов
                  </div>
                ) : (
                  requests.incoming.map((req) => (
                    <div
                      key={req.request_id}
                      className="p-3 rounded-2xl bg-[#171B29] border border-white/8 flex items-center justify-between"
                    >
                      <div className="flex items-center space-x-2.5 min-w-0">
                        <SafeAvatar
                          src={req.other_user_avatar_url}
                          name={req.other_user_display_name}
                          className="w-8 h-8 rounded-full object-cover shrink-0"
                        />
                        <div className="min-w-0">
                          <div className="text-xs font-bold text-white truncate">
                            {req.other_user_display_name}
                          </div>
                          <div className="text-[10px] text-gray-400">Хочет пойти вместе</div>
                        </div>
                      </div>
                      <div className="flex items-center space-x-1.5 shrink-0">
                        <button
                          onClick={() => handleAcceptRequest(req.request_id)}
                          disabled={actionLoadingId === req.request_id}
                          className="px-2.5 py-1 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs transition-colors"
                        >
                          Принять
                        </button>
                        <button
                          onClick={() => handleDeclineRequest(req.request_id)}
                          disabled={actionLoadingId === req.request_id}
                          className="px-2 py-1 rounded-xl bg-white/10 hover:bg-white/20 text-gray-300 font-medium text-xs transition-colors"
                        >
                          Отклонить
                        </button>
                      </div>
                    </div>
                  ))
                )}
              </div>

              {/* Outgoing Section */}
              <div className="space-y-2">
                <div className="text-xs font-bold text-gray-300 flex items-center space-x-1.5">
                  <Clock className="w-3.5 h-3.5 text-indigo-400" />
                  <span>Исходящие запросы ({requests.outgoing.length})</span>
                </div>
                {requests.outgoing.length === 0 ? (
                  <div className="p-4 rounded-xl bg-white/5 text-center text-xs text-gray-400">
                    Нет активных исходящих запросов
                  </div>
                ) : (
                  requests.outgoing.map((req) => (
                    <div
                      key={req.request_id}
                      className="p-3 rounded-2xl bg-[#171B29] border border-white/8 flex items-center justify-between"
                    >
                      <div className="flex items-center space-x-2.5 min-w-0">
                        <SafeAvatar
                          src={req.other_user_avatar_url}
                          name={req.other_user_display_name}
                          className="w-8 h-8 rounded-full object-cover shrink-0"
                        />
                        <div className="min-w-0">
                          <div className="text-xs font-bold text-white truncate">
                            {req.other_user_display_name}
                          </div>
                          <div className="text-[10px] text-indigo-300">Ожидает ответа</div>
                        </div>
                      </div>
                      <button
                        onClick={() => handleCancelRequest(req.request_id)}
                        disabled={actionLoadingId === req.request_id}
                        className="px-2.5 py-1 rounded-xl bg-white/10 hover:bg-white/15 text-gray-300 font-medium text-xs transition-colors"
                      >
                        Отменить
                      </button>
                    </div>
                  ))
                )}
              </div>
            </div>
          ) : (
            /* TAB 3: MATCHES / COMPANY */
            <div className="space-y-3">
              {matches.length === 0 ? (
                <div className="py-10 text-center space-y-2">
                  <div className="w-12 h-12 rounded-2xl bg-indigo-600/10 mx-auto flex items-center justify-center text-indigo-400">
                    <Sparkles className="w-6 h-6" />
                  </div>
                  <div className="text-xs font-semibold text-white">Вы пока не нашли компанию</div>
                  <p className="text-[11px] text-gray-400 max-w-xs mx-auto">
                    Отправляйте запросы участникам во вкладке «Участники». Как только согласие будет взаимным, здесь откроются контакты Telegram!
                  </p>
                </div>
              ) : (
                matches.map((match) => (
                  <div
                    key={match.match_id}
                    className="p-4 rounded-2xl bg-gradient-to-r from-emerald-950/30 to-indigo-950/30 border border-emerald-500/30 space-y-3"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-3 min-w-0">
                        <SafeAvatar
                          src={match.partner_avatar_url}
                          name={match.partner_display_name}
                          className="w-10 h-10 rounded-full object-cover shrink-0 border border-emerald-400/40"
                        />
                        <div className="min-w-0">
                          <div className="text-xs font-bold text-white truncate flex items-center space-x-1.5">
                            <span>{match.partner_display_name}</span>
                            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 font-normal">
                              Компания
                            </span>
                          </div>
                          <div className="text-[10px] text-emerald-300">
                            {match.attendance_status === 'going' ? 'Идёт на событие' : 'Интересуется событием'}
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Telegram contact action */}
                    {match.has_telegram_username && match.partner_telegram_url ? (
                      <a
                        href={match.partner_telegram_url}
                        target="_blank"
                        rel="noreferrer"
                        onClick={() => {
                          telegram.hapticImpact('medium');
                          telegram.openTelegramLink(match.partner_telegram_url!);
                        }}
                        className="w-full py-2.5 px-4 rounded-xl bg-gradient-to-r from-indigo-600 to-sky-600 hover:from-indigo-500 hover:to-sky-500 text-white font-semibold text-xs flex items-center justify-center space-x-2 transition-all shadow-md shadow-indigo-600/20"
                      >
                        <MessageCircle className="w-4 h-4 fill-white/20" />
                        <span>Написать: @{match.partner_telegram_username}</span>
                        <ExternalLink className="w-3.5 h-3.5 opacity-70" />
                      </a>
                    ) : (
                      <div className="p-2.5 rounded-xl bg-black/30 border border-white/5 text-[11px] text-gray-400 leading-relaxed">
                        ⚠️ У пользователя нет публичного username в Telegram. Попробуйте связаться через общие группы или дождитесь его сообщения.
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          )}

          {/* Privacy Guarantee Footer */}
          <div className="pt-2 border-t border-white/5 flex items-center space-x-2 text-[10px] text-gray-500">
            <ShieldCheck className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
            <span>Контакты Telegram открываются только при взаимном согласии. Telegram ID защищен.</span>
          </div>

        </div>
      </div>
    </div>
  );
};
