import React, { useState } from 'react';
import type { EventSummary, EventStatus } from '../types';
import { api } from '../services/api';
import { telegram } from '../services/telegram';
import { Shield, Check, X, Ban, Calendar, MapPin, Loader2, AlertCircle } from 'lucide-react';

interface AdminTabProps {
  events: EventSummary[];
  isLoading: boolean;
  activeStatus: EventStatus;
  onStatusChange: (status: EventStatus) => void;
  onRefresh: () => void;
  onEventClick: (event: EventSummary) => void;
}

export const AdminTab: React.FC<AdminTabProps> = ({
  events,
  isLoading,
  activeStatus,
  onStatusChange,
  onRefresh,
  onEventClick,
}) => {
  const [rejectingId, setRejectingId] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState('Несоответствие правилам публикации событий');
  const [actionLoadingId, setActionLoadingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handlePublish = async (e: React.MouseEvent, eventId: string) => {
    e.stopPropagation();
    try {
      setActionLoadingId(eventId);
      setError(null);
      await api.adminPublishEvent(eventId);
      telegram.hapticSuccess();
      onRefresh();
    } catch (err: any) {
      setError(err.message || 'Ошибка публикации события');
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleConfirmReject = async (e: React.FormEvent, eventId: string) => {
    e.preventDefault();
    e.stopPropagation();
    try {
      setActionLoadingId(eventId);
      setError(null);
      await api.adminRejectEvent(eventId, rejectReason);
      telegram.hapticSuccess();
      setRejectingId(null);
      onRefresh();
    } catch (err: any) {
      setError(err.message || 'Ошибка отклонения события');
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleCancel = async (e: React.MouseEvent, eventId: string) => {
    e.stopPropagation();
    if (!confirm('Вы уверены, что хотите снять событие с публикации?')) return;
    try {
      setActionLoadingId(eventId);
      setError(null);
      await api.adminCancelEvent(eventId);
      telegram.hapticImpact('medium');
      onRefresh();
    } catch (err: any) {
      setError(err.message || 'Ошибка отмены публикации');
    } finally {
      setActionLoadingId(null);
    }
  };

  return (
    <div className="space-y-4 px-4 py-2">
      {/* Admin Header */}
      <div className="p-4 rounded-2xl bg-[#171A29] border border-indigo-500/30 flex items-center justify-between">
        <div className="flex items-center space-x-2.5">
          <div className="w-8 h-8 rounded-xl bg-indigo-500/20 text-indigo-400 flex items-center justify-center">
            <Shield className="w-4 h-4" />
          </div>
          <div>
            <h3 className="font-bold text-sm text-white">Модерация Ivently</h3>

            <p className="text-[11px] text-gray-400">Проверка и управление событиями</p>
          </div>
        </div>
      </div>

      {error && (
        <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-300 flex items-center space-x-2 text-xs">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Status Segmented Control */}
      <div className="flex bg-[#141724] p-1 rounded-xl border border-white/5 text-xs">
        <button
          onClick={() => onStatusChange('pending')}
          className={`flex-1 py-1.5 font-medium rounded-lg transition-all ${
            activeStatus === 'pending'
              ? 'bg-indigo-600 text-white shadow'
              : 'text-gray-400 hover:text-white'
          }`}
        >
          На проверке
        </button>
        <button
          onClick={() => onStatusChange('published')}
          className={`flex-1 py-1.5 font-medium rounded-lg transition-all ${
            activeStatus === 'published'
              ? 'bg-indigo-600 text-white shadow'
              : 'text-gray-400 hover:text-white'
          }`}
        >
          Опубликованные
        </button>
        <button
          onClick={() => onStatusChange('rejected')}
          className={`flex-1 py-1.5 font-medium rounded-lg transition-all ${
            activeStatus === 'rejected'
              ? 'bg-indigo-600 text-white shadow'
              : 'text-gray-400 hover:text-white'
          }`}
        >
          Отклонённые
        </button>
      </div>

      {/* Queue items */}
      <div className="space-y-3">
        {isLoading ? (
          <div className="py-12 text-center text-xs text-gray-400">Загрузка очереди...</div>
        ) : events.length === 0 ? (
          <div className="p-8 text-center rounded-2xl bg-[#141724] border border-white/5 text-xs text-gray-400">
            В этой категории нет событий
          </div>
        ) : (
          events.map((ev) => {
            const isActing = actionLoadingId === ev.id;
            const isRejecting = rejectingId === ev.id;
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
                className="p-4 rounded-2xl bg-[#141724] border border-white/8 hover:border-white/15 transition-all space-y-3 cursor-pointer"
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <span className="text-[10px] font-semibold text-indigo-400 uppercase tracking-wider">
                      {ev.category_name} · {ev.city_name}
                    </span>
                    <h4 className="font-bold text-sm text-white leading-tight mt-0.5">{ev.title}</h4>
                  </div>
                </div>

                <div className="flex items-center space-x-3 text-xs text-gray-400">
                  <div className="flex items-center space-x-1">
                    <Calendar className="w-3.5 h-3.5 text-indigo-400" />
                    <span>{dateStr}</span>
                  </div>
                  <div className="flex items-center space-x-1 truncate">
                    <MapPin className="w-3.5 h-3.5 text-gray-500" />
                    <span className="truncate">{ev.venue_name}</span>
                  </div>
                </div>

                {/* Reject Input Dialog */}
                {isRejecting ? (
                  <form
                    onSubmit={(e) => handleConfirmReject(e, ev.id)}
                    onClick={(e) => e.stopPropagation()}
                    className="p-3 rounded-xl bg-red-500/10 border border-red-500/20 space-y-2 text-xs"
                  >
                    <label className="font-semibold text-red-300">Причина отклонения:</label>
                    <input
                      type="text"
                      value={rejectReason}
                      onChange={(e) => setRejectReason(e.target.value)}
                      className="w-full px-2.5 py-1.5 rounded-lg bg-[#141724] border border-white/10 text-white"
                      required
                    />
                    <div className="flex space-x-2">
                      <button
                        type="submit"
                        disabled={isActing}
                        className="px-3 py-1 rounded-lg bg-red-600 text-white font-semibold"
                      >
                        Подтвердить отказ
                      </button>
                      <button
                        type="button"
                        onClick={() => setRejectingId(null)}
                        className="px-3 py-1 rounded-lg bg-white/10 text-gray-300"
                      >
                        Отмена
                      </button>
                    </div>
                  </form>
                ) : (
                  /* Action Buttons */
                  <div className="pt-2 border-t border-white/5 flex items-center justify-end space-x-2">
                    {ev.status === 'pending' && (
                      <>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setRejectingId(ev.id);
                          }}
                          disabled={isActing}
                          className="flex items-center space-x-1 px-3 py-1.5 rounded-xl bg-red-500/10 hover:bg-red-500/20 text-red-400 font-semibold text-xs border border-red-500/20 transition-colors"
                        >
                          <X className="w-3.5 h-3.5" />
                          <span>Отклонить</span>
                        </button>
                        <button
                          onClick={(e) => handlePublish(e, ev.id)}
                          disabled={isActing}
                          className="flex items-center space-x-1 px-3.5 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs shadow-md shadow-emerald-600/20 transition-all active:scale-95"
                        >
                          {isActing ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          ) : (
                            <>
                              <Check className="w-3.5 h-3.5" />
                              <span>Опубликовать</span>
                            </>
                          )}
                        </button>
                      </>
                    )}

                    {ev.status === 'published' && (
                      <button
                        onClick={(e) => handleCancel(e, ev.id)}
                        disabled={isActing}
                        className="flex items-center space-x-1 px-3 py-1.5 rounded-xl bg-white/5 hover:bg-white/10 text-gray-400 hover:text-white text-xs border border-white/5 transition-colors"
                      >
                        <Ban className="w-3.5 h-3.5" />
                        <span>Снять с публикации</span>
                      </button>
                    )}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
