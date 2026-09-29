import React, { useState, useEffect, useCallback } from 'react';
import type { UserSubscriptionItem } from '../types';
import { api } from '../services/api';
import { telegram } from '../services/telegram';
import { formatFollowers } from './OrganizationModal';
import {
  X,
  Bookmark,
  Users,
  ShieldCheck,
  Loader2,
  ChevronRight,
  AlertCircle,
} from 'lucide-react';

interface MySubscriptionsModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectOrg: (orgId: string) => void;
}

export const MySubscriptionsModal: React.FC<MySubscriptionsModalProps> = ({
  isOpen,
  onClose,
  onSelectOrg,
}) => {
  const [subscriptions, setSubscriptions] = useState<UserSubscriptionItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadSubscriptions = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const data = await api.getMySubscriptions();
      setSubscriptions(data);
    } catch (err: any) {
      console.error('Failed to load subscriptions:', err);
      setError(err.message || 'Ошибка загрузки подписок');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isOpen) {
      loadSubscriptions();
    } else {
      setSubscriptions([]);
      setError(null);
    }
  }, [isOpen, loadSubscriptions]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex flex-col justify-end sm:justify-center items-center bg-black/80 backdrop-blur-sm backdrop-fade-in p-0 sm:p-4">
      <div
        className="w-full max-w-lg bg-[#0F121C] sm:rounded-3xl rounded-t-[28px] border border-white/10 overflow-hidden shadow-2xl flex flex-col max-h-[90vh] sheet-slide-up"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="p-4 flex items-center justify-between border-b border-white/5 bg-[#141724]/70 backdrop-blur-md shrink-0">
          <button
            onClick={onClose}
            className="p-2 rounded-full bg-white/5 hover:bg-white/10 text-white transition-colors btn-press"
          >
            <X className="w-5 h-5" />
          </button>
          <div className="text-sm font-bold text-white flex items-center space-x-2">
            <Bookmark className="w-4 h-4 text-indigo-400" />
            <span>Мои подписки</span>
          </div>
          <div className="w-9" />
        </div>

        {/* Content Body */}
        <div className="p-5 overflow-y-auto space-y-3 no-scrollbar flex-1">
          {isLoading ? (
            <div className="py-20 flex flex-col items-center justify-center space-y-3 text-gray-400">
              <Loader2 className="w-7 h-7 animate-spin text-indigo-500" />
              <span className="text-xs">Загрузка ваших подписок...</span>
            </div>
          ) : error ? (
            <div className="p-6 text-center rounded-2xl bg-red-500/10 border border-red-500/20 text-red-300 space-y-2">
              <AlertCircle className="w-6 h-6 mx-auto" />
              <div className="text-xs font-semibold">{error}</div>
              <button
                onClick={loadSubscriptions}
                className="px-4 py-2 rounded-xl bg-indigo-600 text-white text-xs font-medium hover:bg-indigo-500 mt-2 btn-press"
              >
                Повторить попытку
              </button>
            </div>
          ) : subscriptions.length === 0 ? (
            <div className="py-16 px-4 text-center rounded-2xl bg-[#141724] border border-white/5 space-y-3">
              <div className="w-12 h-12 rounded-full bg-white/5 flex items-center justify-center mx-auto text-indigo-400">
                <Users className="w-6 h-6" />
              </div>
              <div className="space-y-1">
                <h3 className="font-bold text-sm text-white">У вас пока нет подписок</h3>
                <p className="text-xs text-gray-400 max-w-xs mx-auto">
                  Подписывайтесь на любимые площадки, кафе и клубы, чтобы первыми получать уведомления в Telegram о новых событиях
                </p>
              </div>
            </div>
          ) : (
            <div className="space-y-2.5">
              <div className="text-xs text-gray-400 font-semibold uppercase tracking-wider px-1">
                Организации ({subscriptions.length})
              </div>
              {subscriptions.map((sub) => {
                const org = sub.organization;
                return (
                  <div
                    key={sub.id}
                    onClick={() => {
                      telegram.hapticImpact('light');
                      onClose();
                      onSelectOrg(org.id);
                    }}
                    className="flex items-center space-x-3.5 p-3 rounded-2xl bg-[#141724] border border-white/5 hover:border-indigo-500/30 transition-all cursor-pointer card-press"
                  >
                    <div className="w-12 h-12 rounded-xl overflow-hidden bg-gradient-to-tr from-indigo-900 to-purple-900 border border-indigo-500/30 flex items-center justify-center shrink-0">
                      {org.avatar_url ? (
                        <img
                          src={org.avatar_url}
                          alt={org.name}
                          className="w-full h-full object-cover"
                        />
                      ) : (
                        <span className="text-sm font-bold text-indigo-300">
                          {org.name.slice(0, 2).toUpperCase()}
                        </span>
                      )}
                    </div>

                    <div className="flex-1 min-w-0 space-y-0.5">
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
                        <span>{formatFollowers(org.followers_count)}</span>
                      </div>
                    </div>

                    <ChevronRight className="w-4 h-4 text-gray-500 shrink-0" />
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
