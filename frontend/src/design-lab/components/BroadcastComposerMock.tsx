import React, { useState } from 'react';
import { 
  Send, 
  Clock, 
  Sparkles, 
  CheckCircle2, 
  Calendar,
  X
} from 'lucide-react';

interface BroadcastComposerMockProps {
  onClose?: () => void;
}

export const BroadcastComposerMock: React.FC<BroadcastComposerMockProps> = ({
  onClose
}) => {
  const [target, setTarget] = useState<'all' | 'event'>('all');
  const [message, setMessage] = useState<string>(
    'Привет! До концерта «Вечер джаза в оранжерее» остаётся всего 2 дня. Напоминаем, что вход открывается в 19:00. Будем рады видеть вас!'
  );
  const [isSent, setIsSent] = useState<boolean>(false);

  return (
    <div className="w-full max-w-[430px] rounded-3xl bg-[#08090D] border border-white/10 shadow-2xl overflow-hidden flex flex-col max-h-[85vh]">
      {/* 1. Header */}
      <div className="sticky top-0 z-20 bg-[#0B0D13]/90 backdrop-blur-md border-b border-white/10 px-4 py-3 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-emerald-500/20 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
            <Send size={14} />
          </div>
          <div>
            <h1 className="text-sm font-bold text-white tracking-tight">
              Рассылка в Telegram
            </h1>
            <p className="text-[10px] text-gray-400">Прямое уведомление подписчикам бота</p>
          </div>
        </div>

        {onClose && (
          <button
            type="button"
            onClick={onClose}
            className="w-8 h-8 rounded-full bg-white/5 border border-white/10 flex items-center justify-center text-gray-400 hover:text-white"
          >
            <X size={15} />
          </button>
        )}
      </div>

      {/* 2. Scrollable Body */}
      <div className="overflow-y-auto px-4 py-4 space-y-4 no-scrollbar">
        {/* Anti-Fatigue 24-Hour Cooldown Banner */}
        <div className="p-3 rounded-2xl bg-white/[0.04] border border-white/8 flex items-center justify-between">
          <div className="flex items-center gap-2 text-xs">
            <Clock size={15} className="text-emerald-400 shrink-0" />
            <span className="text-gray-300">Интервал анти-спама:</span>
          </div>
          <span className="px-2.5 py-0.5 rounded-full bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 text-[10px] font-bold">
            Готово к отправке (24ч прошло)
          </span>
        </div>

        {/* Target Audience Selector */}
        <div className="space-y-1.5">
          <label className="text-xs font-semibold text-gray-300">Получатели</label>
          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={() => setTarget('all')}
              className={`p-2.5 rounded-xl border text-left text-xs transition-all ${
                target === 'all'
                  ? 'bg-white/10 border-white/20 text-white shadow-sm'
                  : 'bg-white/[0.02] border-white/5 text-gray-400 hover:text-gray-200'
              }`}
            >
              <div className="font-bold">Все подписчики</div>
              <div className="text-[10px] text-gray-400">1 240 человек</div>
            </button>
            <button
              type="button"
              onClick={() => setTarget('event')}
              className={`p-2.5 rounded-xl border text-left text-xs transition-all ${
                target === 'event'
                  ? 'bg-white/10 border-white/20 text-white shadow-sm'
                  : 'bg-white/[0.02] border-white/5 text-gray-400 hover:text-gray-200'
              }`}
            >
              <div className="font-bold">Участники события</div>
              <div className="text-[10px] text-gray-400">42 подтвердили RSVP</div>
            </button>
          </div>
        </div>

        {/* Text Input */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <label className="text-xs font-semibold text-gray-300">Текст сообщения</label>
            <span className="text-[10px] text-gray-500">{message.length} / 1024</span>
          </div>
          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            rows={4}
            className="w-full p-3 rounded-2xl bg-white/[0.03] border border-white/10 text-white text-xs leading-relaxed focus:outline-none focus:border-white/30 resize-none"
            placeholder="Введите текст анонса..."
          />
        </div>

        {/* Telegram Chat Bubble Preview */}
        <div className="space-y-1.5">
          <div className="text-xs font-semibold text-gray-400 flex items-center gap-1.5">
            <Sparkles size={13} className="text-sky-400" />
            <span>Предпросмотр в Telegram</span>
          </div>

          <div className="p-3 rounded-2xl bg-[#17212B] border border-white/5 space-y-2">
            <div className="flex items-center gap-2">
              <div className="w-6 h-6 rounded-full bg-amber-500 flex items-center justify-center font-bold text-[9px] text-black">
                IV
              </div>
              <span className="text-[11px] font-bold text-sky-400">Ivently Bot</span>
            </div>

            <p className="text-xs text-white leading-relaxed whitespace-pre-wrap">
              {message}
            </p>

            {/* Attached Event Card in Bubble */}
            <div className="p-2 rounded-xl bg-black/40 border border-white/10 flex items-center gap-2">
              <Calendar size={15} className="text-emerald-400 shrink-0" />
              <div className="min-w-0 text-[11px]">
                <div className="font-semibold text-white truncate">Вечер джаза в оранжерее</div>
                <div className="text-gray-400 text-[10px]">10 окт., 19:26 • от 1 500 ₽</div>
              </div>
            </div>

            <div className="text-right text-[9px] text-gray-400">14:32</div>
          </div>
        </div>
      </div>

      {/* 3. Sticky Dispatch Action */}
      <div className="p-3 bg-[#0B0D13]/95 backdrop-blur-xl border-t border-white/10 shrink-0">
        <button
          type="button"
          onClick={() => setIsSent(true)}
          disabled={isSent}
          className={`w-full h-12 rounded-2xl font-bold text-xs uppercase tracking-wider flex items-center justify-center gap-2 transition-all ${
            isSent
              ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
              : 'bg-white text-black hover:bg-neutral-200 shadow-xl'
          }`}
        >
          {isSent ? (
            <>
              <CheckCircle2 size={16} />
              <span>Рассылка успешно отправлена!</span>
            </>
          ) : (
            <>
              <Send size={15} />
              <span>Отправить рассылку (1 240 получателей)</span>
            </>
          )}
        </button>
      </div>
    </div>
  );
};
