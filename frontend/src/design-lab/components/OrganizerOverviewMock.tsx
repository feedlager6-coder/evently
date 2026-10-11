import React, { useState } from 'react';
import { 
  ArrowLeft, 
  Sparkles, 
  Users, 
  Send, 
  TrendingUp, 
  Calendar
} from 'lucide-react';

interface OrganizerOverviewMockProps {
  onBack?: () => void;
  onOpenBroadcast?: () => void;
}

export const OrganizerOverviewMock: React.FC<OrganizerOverviewMockProps> = ({
  onBack,
  onOpenBroadcast
}) => {
  const [activeTab, setActiveTab] = useState<'overview' | 'events' | 'broadcasts' | 'audience' | 'orgs'>('overview');
  const [isPro, setIsPro] = useState<boolean>(false);

  return (
    <div className="w-full max-w-[430px] rounded-3xl bg-[#08090D] border border-white/10 shadow-2xl overflow-hidden flex flex-col max-h-[85vh]">
      {/* 1. Header Bar */}
      <div className="sticky top-0 z-20 bg-[#0B0D13]/90 backdrop-blur-md border-b border-white/10 px-4 py-3 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2.5">
          {onBack && (
            <button
              type="button"
              onClick={onBack}
              className="p-1.5 -ml-1 rounded-xl bg-white/5 hover:bg-white/10 text-gray-300 hover:text-white transition-colors"
            >
              <ArrowLeft size={18} />
            </button>
          )}
          <div>
            <h1 className="text-sm font-bold text-white tracking-tight leading-none">
              Кабинет организатора
            </h1>
            <p className="text-[10px] text-gray-400 mt-0.5">Управление контентом и аудиторией</p>
          </div>
        </div>

        <span className={`text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full border ${
          isPro 
            ? 'bg-amber-500/20 text-amber-300 border-amber-500/30' 
            : 'bg-white/5 text-gray-400 border-white/10'
        }`}>
          {isPro ? 'PRO PLAN' : 'FREE PLAN'}
        </span>
      </div>

      {/* 2. Workspace 5-Tab Segmented Control */}
      <div className="px-3 pt-3 pb-2 shrink-0">
        <div className="flex items-center p-1 rounded-2xl bg-white/[0.04] border border-white/8 overflow-x-auto no-scrollbar gap-1">
          {[
            { id: 'overview', label: 'Обзор' },
            { id: 'events', label: 'События', count: 4 },
            { id: 'broadcasts', label: 'Рассылки' },
            { id: 'audience', label: 'Аудитория' },
            { id: 'orgs', label: 'Места' },
          ].map((tab) => {
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => {
                  setActiveTab(tab.id as any);
                  if (tab.id === 'broadcasts' && onOpenBroadcast) {
                    onOpenBroadcast();
                  }
                }}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold whitespace-nowrap transition-all ${
                  isActive
                    ? 'bg-white/15 text-white border border-white/20 shadow-sm'
                    : 'text-gray-400 hover:text-gray-200'
                }`}
              >
                <span>{tab.label}</span>
                {tab.count !== undefined && (
                  <span className="px-1.5 py-0.2 rounded-full bg-white/10 text-[9px] font-bold">
                    {tab.count}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* 3. Scrollable Overview Content */}
      <div className="overflow-y-auto px-3.5 pb-6 space-y-3.5 no-scrollbar">
        {/* Grounded Factual Insight Banner */}
        <div className="p-3.5 rounded-2xl bg-gradient-to-r from-emerald-500/15 via-white/[0.04] to-transparent border border-emerald-500/25 flex items-start gap-2.5">
          <Sparkles size={16} className="text-emerald-400 shrink-0 mt-0.5" />
          <div className="min-w-0">
            <div className="text-[10px] font-bold uppercase tracking-wider text-emerald-400">Синтез недели</div>
            <p className="text-xs font-medium text-white leading-snug mt-0.5">
              Конверсия из просмотров в RSVP выросла на <strong>+18.4%</strong> после подключения рассылок в Telegram.
            </p>
          </div>
        </div>

        {/* Pillar 1: Audience Overview */}
        <div className="p-3.5 rounded-2xl bg-[#111319] border border-white/8 space-y-2.5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-white">
              <Users size={16} className="text-amber-400" />
              <span className="text-xs font-bold">База аудитории</span>
            </div>
            <span className="text-[11px] font-semibold text-emerald-400 flex items-center gap-0.5">
              <TrendingUp size={12} />
              <span>+142 за месяц</span>
            </span>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div className="p-2.5 rounded-xl bg-white/[0.03] border border-white/5">
              <div className="text-[10px] text-gray-400">Подписчики площадки</div>
              <div className="text-lg font-bold text-white mt-0.5">1 240</div>
            </div>
            <div className="p-2.5 rounded-xl bg-white/[0.03] border border-white/5">
              <div className="text-[10px] text-gray-400">Уникальные участники</div>
              <div className="text-lg font-bold text-white mt-0.5">3 890</div>
            </div>
          </div>
        </div>

        {/* Pillar 2: Event Funnel Metrics */}
        <div className="p-3.5 rounded-2xl bg-[#111319] border border-white/8 space-y-2.5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-white">
              <Calendar size={16} className="text-sky-400" />
              <span className="text-xs font-bold">Воронка мероприятий</span>
            </div>
            <span className="text-[10px] text-gray-400">Последние 30 дней</span>
          </div>

          <div className="grid grid-cols-3 gap-2">
            <div className="p-2.5 rounded-xl bg-white/[0.03] border border-white/5 text-center">
              <div className="text-[10px] text-gray-400">Просмотры</div>
              <div className="text-base font-bold text-white mt-0.5">14.2K</div>
            </div>
            <div className="p-2.5 rounded-xl bg-white/[0.03] border border-white/5 text-center">
              <div className="text-[10px] text-pink-400">Интерес</div>
              <div className="text-base font-bold text-pink-400 mt-0.5">890</div>
            </div>
            <div className="p-2.5 rounded-xl bg-white/[0.03] border border-white/5 text-center">
              <div className="text-[10px] text-emerald-400">Идут (RSVP)</div>
              <div className="text-base font-bold text-emerald-400 mt-0.5">412</div>
            </div>
          </div>
        </div>

        {/* Pillar 3: Telegram Broadcast Attribution */}
        <div className="p-3.5 rounded-2xl bg-[#111319] border border-white/8 space-y-2.5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-white">
              <Send size={15} className="text-emerald-400" />
              <span className="text-xs font-bold">Рассылки в Telegram</span>
            </div>
            <button
              type="button"
              onClick={onOpenBroadcast}
              className="text-xs text-emerald-400 hover:text-emerald-300 font-semibold"
            >
              + Создать →
            </button>
          </div>

          <div className="grid grid-cols-3 gap-2">
            <div className="p-2 rounded-xl bg-white/[0.03] border border-white/5 text-center">
              <div className="text-[9px] text-gray-400">Доставлено</div>
              <div className="text-xs font-bold text-white mt-0.5">1 180</div>
            </div>
            <div className="p-2 rounded-xl bg-white/[0.03] border border-white/5 text-center">
              <div className="text-[9px] text-gray-400">Открыли</div>
              <div className="text-xs font-bold text-white mt-0.5">74%</div>
            </div>
            <div className="p-2 rounded-xl bg-white/[0.03] border border-white/5 text-center">
              <div className="text-[9px] text-emerald-400">RSVP из рассылок</div>
              <div className="text-xs font-bold text-emerald-400 mt-0.5">+128</div>
            </div>
          </div>
        </div>

        {/* PRO Tier Upsell / Toggle Card */}
        <div className="p-3.5 rounded-2xl bg-gradient-to-r from-amber-950/30 via-white/[0.03] to-transparent border border-amber-500/20 space-y-2.5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-lg bg-amber-500/20 border border-amber-500/30 flex items-center justify-center text-amber-400">
                <Sparkles size={15} />
              </div>
              <div>
                <div className="text-xs font-bold text-white">Тариф PRO для организаторов</div>
                <div className="text-[10px] text-gray-400">Регулярные рассылки и экспорт базы</div>
              </div>
            </div>

            <button
              type="button"
              onClick={() => setIsPro(!isPro)}
              className="px-3 py-1.5 rounded-full text-xs font-bold bg-amber-500 text-black hover:bg-amber-400 shadow-md transition-all"
            >
              {isPro ? 'Отключить PRO' : 'Подключить PRO'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
