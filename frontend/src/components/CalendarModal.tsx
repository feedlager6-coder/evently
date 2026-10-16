import React, { useState } from 'react';
import { ChevronLeft, ChevronRight, X, Calendar as CalendarIcon, RotateCcw } from 'lucide-react';
import { telegram } from '../services/telegram';
import { haptics } from '../utils/haptics';

interface CalendarModalProps {
  isOpen: boolean;
  onClose: () => void;
  selectedDate: string;
  onSelectDate: (dateStr: string) => void;
}

const MONTH_NAMES = [
  'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
  'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'
];

const WEEKDAYS = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];

export const CalendarModal: React.FC<CalendarModalProps> = ({
  isOpen,
  onClose,
  selectedDate,
  onSelectDate,
}) => {
  // Parse initial month from selectedDate or use current date
  const getInitialDate = () => {
    if (/^\d{4}-\d{2}-\d{2}$/.test(selectedDate)) {
      const [y, m, d] = selectedDate.split('-').map(Number);
      return new Date(y, m - 1, d);
    }
    return new Date();
  };

  const [viewDate, setViewDate] = useState<Date>(getInitialDate);

  if (!isOpen) return null;

  const currentYear = viewDate.getFullYear();
  const currentMonth = viewDate.getMonth();

  // Navigation handlers
  const handlePrevMonth = () => {
    haptics.selectionChanged();
    setViewDate(new Date(currentYear, currentMonth - 1, 1));
  };

  const handleNextMonth = () => {
    haptics.selectionChanged();
    setViewDate(new Date(currentYear, currentMonth + 1, 1));
  };

  // Calendar math for grid
  const daysInMonth = new Date(currentYear, currentMonth + 1, 0).getDate();
  const firstDayOfWeek = (new Date(currentYear, currentMonth, 1).getDay() + 6) % 7; // 0 = Mon, 6 = Sun

  const today = new Date();
  const todayStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;

  const handleDayClick = (day: number) => {
    haptics.selectionChanged();
    const isoString = `${currentYear}-${String(currentMonth + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
    onSelectDate(isoString);
    onClose();
  };

  const handleReset = () => {
    haptics.selectionChanged();
    onSelectDate('all');
    onClose();
  };

  const handleToday = () => {
    haptics.selectionChanged();
    onSelectDate(todayStr);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4 bg-black/70 backdrop-blur-sm animate-in fade-in duration-200">
      <div 
        className="w-full max-w-sm rounded-t-3xl sm:rounded-3xl bg-[#141416] border border-white/10 p-5 shadow-2xl flex flex-col gap-4 text-white animate-in slide-in-from-bottom duration-250"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header with Title and Close */}
        <div className="flex items-center justify-between pb-1 border-b border-white/10">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-full bg-[#10b981]/20 flex items-center justify-center text-[#4edea3]">
              <CalendarIcon className="w-4 h-4" />
            </div>
            <h3 className="font-bold text-base text-white">Выбор даты</h3>
          </div>
          <button
            type="button"
            onClick={() => {
              telegram.hapticImpact('light');
              onClose();
            }}
            className="w-8 h-8 rounded-full bg-white/5 flex items-center justify-center text-white/70 hover:text-white transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Month Selector */}
        <div className="flex items-center justify-between px-1">
          <button
            type="button"
            onClick={handlePrevMonth}
            className="w-8 h-8 rounded-full bg-white/5 flex items-center justify-center text-white/70 hover:text-white transition-colors active:scale-90"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
          <span className="font-semibold text-sm text-white">
            {MONTH_NAMES[currentMonth]} {currentYear}
          </span>
          <button
            type="button"
            onClick={handleNextMonth}
            className="w-8 h-8 rounded-full bg-white/5 flex items-center justify-center text-white/70 hover:text-white transition-colors active:scale-90"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>

        {/* Weekday headers */}
        <div className="grid grid-cols-7 gap-1 text-center text-[11px] font-semibold text-[#8e9192]">
          {WEEKDAYS.map((wd, idx) => (
            <div key={wd} className={idx >= 5 ? 'text-[#ffb95f]' : ''}>
              {wd}
            </div>
          ))}
        </div>

        {/* Days grid */}
        <div className="grid grid-cols-7 gap-1 text-center">
          {/* Empty padding cells before first day */}
          {Array.from({ length: firstDayOfWeek }).map((_, idx) => (
            <div key={`empty-${idx}`} className="h-9" />
          ))}

          {/* Days of month */}
          {Array.from({ length: daysInMonth }).map((_, idx) => {
            const dayNum = idx + 1;
            const dateStr = `${currentYear}-${String(currentMonth + 1).padStart(2, '0')}-${String(dayNum).padStart(2, '0')}`;
            const isSelected = selectedDate === dateStr;
            const isToday = todayStr === dateStr;
            const dayOfWeek = (firstDayOfWeek + idx) % 7;
            const isWeekend = dayOfWeek >= 5;

            return (
              <button
                key={dayNum}
                type="button"
                onClick={() => handleDayClick(dayNum)}
                className={`h-9 rounded-xl flex items-center justify-center text-xs font-semibold transition-all duration-150 active:scale-90 ${
                  isSelected
                    ? 'bg-[#4edea3] text-[#08080a] font-extrabold shadow-[0_2px_12px_rgba(78,222,163,0.4)]'
                    : isToday
                    ? 'bg-white/15 text-white border border-[#4edea3]/60'
                    : isWeekend
                    ? 'text-[#ffb95f] hover:bg-white/10'
                    : 'text-white hover:bg-white/10'
                }`}
              >
                {dayNum}
              </button>
            );
          })}
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-2 pt-2 border-t border-white/10">
          <button
            type="button"
            onClick={handleToday}
            className="flex-1 py-2.5 rounded-full bg-white/10 hover:bg-white/15 text-white text-xs font-semibold transition-all active:scale-95"
          >
            Сегодня
          </button>
          <button
            type="button"
            onClick={handleReset}
            className="flex-1 py-2.5 rounded-full bg-[#201f22] hover:bg-[#28272b] text-[#c4c7c8] hover:text-white text-xs font-semibold transition-all active:scale-95 flex items-center justify-center gap-1.5"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>Все даты</span>
          </button>
        </div>
      </div>
    </div>
  );
};
