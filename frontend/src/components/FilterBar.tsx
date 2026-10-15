import React, { useRef } from 'react';
import type { Category, DateFilterType } from '../types';
import { Sparkles, Music, Flame, Dumbbell, GraduationCap, Briefcase, Palette, Compass, Drama, Calendar, X } from 'lucide-react';
import { telegram } from '../services/telegram';

interface FilterBarProps {
  dateFilter: DateFilterType;
  onSelectDate: (date: DateFilterType) => void;
  categories: Category[];
  selectedCategoryId?: string;
  onSelectCategory: (categoryId?: string) => void;
}

const DATE_OPTIONS: { id: DateFilterType; label: string }[] = [
  { id: 'all', label: 'Все' },
  { id: 'today', label: 'Сегодня' },
  { id: 'tomorrow', label: 'Завтра' },
  { id: 'weekend', label: 'Выходные' },
];

const CATEGORY_ICONS: Record<string, React.ReactNode> = {
  theatre: <Drama className="w-3.5 h-3.5" />,
  concerts: <Music className="w-3.5 h-3.5" />,
  parties: <Flame className="w-3.5 h-3.5" />,
  sports: <Dumbbell className="w-3.5 h-3.5" />,
  education: <GraduationCap className="w-3.5 h-3.5" />,
  business: <Briefcase className="w-3.5 h-3.5" />,
  exhibitions: <Palette className="w-3.5 h-3.5" />,
  other: <Compass className="w-3.5 h-3.5" />,
};

function formatShortDate(iso: string): string {
  const parts = iso.split('-');
  if (parts.length === 3) {
    const day = parseInt(parts[2], 10);
    const mIdx = parseInt(parts[1], 10) - 1;
    const months = ['янв', 'фев', 'мар', 'апр', 'май', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек'];
    return `${day} ${months[mIdx] || ''}`;
  }
  return iso;
}

export const FilterBar: React.FC<FilterBarProps> = ({
  dateFilter,
  onSelectDate,
  categories,
  selectedCategoryId,
  onSelectCategory,
}) => {
  const dateInputRef = useRef<HTMLInputElement>(null);
  const isCustomDate = /^\d{4}-\d{2}-\d{2}$/.test(dateFilter);

  return (
    <div className="space-y-3 pt-1 pb-1">
      {/* Segmented Date Filter Bar */}
      <div className="px-4">
        <div className="flex items-center gap-1 p-1 bg-[#0e0e10]/85 backdrop-blur-xl rounded-full border border-white/8 shadow-[inset_0_1px_1px_rgba(255,255,255,0.05)] overflow-x-auto no-scrollbar">
          {DATE_OPTIONS.map((opt) => {
            const isSelected = dateFilter === opt.id;
            return (
              <button
                key={opt.id}
                type="button"
                onClick={() => {
                  telegram.hapticImpact('light');
                  onSelectDate(opt.id);
                }}
                className={`flex-1 min-w-[64px] py-2 px-2.5 rounded-full text-center text-xs transition-all duration-200 ${
                  isSelected
                    ? 'bg-[#39393b] text-white font-semibold shadow-[inset_0_1px_2px_rgba(255,255,255,0.3),0_2px_8px_rgba(0,0,0,0.4)]'
                    : 'text-[#c4c7c8] hover:text-white font-medium'
                }`}
              >
                {opt.label}
              </button>
            );
          })}

          {/* Calendar Custom Date Picker Button */}
          <div className="relative shrink-0">
            <input
              ref={dateInputRef}
              type="date"
              value={isCustomDate ? dateFilter : ''}
              onChange={(e) => {
                if (e.target.value) {
                  telegram.hapticImpact('light');
                  onSelectDate(e.target.value);
                }
              }}
              className="sr-only"
            />
            {isCustomDate ? (
              <div className="flex items-center gap-1 py-1.5 px-3 rounded-full bg-[#39393b] text-white font-semibold text-xs shadow-[inset_0_1px_2px_rgba(255,255,255,0.3),0_2px_8px_rgba(0,0,0,0.4)]">
                <Calendar className="w-3 h-3 text-[#308ce8]" />
                <span>{formatShortDate(dateFilter)}</span>
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    telegram.hapticImpact('light');
                    onSelectDate('all');
                  }}
                  className="p-0.5 hover:text-red-400 transition-colors ml-0.5"
                >
                  <X className="w-3 h-3" />
                </button>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => {
                  telegram.hapticImpact('light');
                  const el = dateInputRef.current;
                  if (el) {
                    if (typeof (el as any).showPicker === 'function') {
                      (el as any).showPicker();
                    } else {
                      el.click();
                    }
                  }
                }}
                className="flex items-center gap-1 py-2 px-2.5 rounded-full text-center text-xs text-[#c4c7c8] hover:text-white font-medium transition-all"
              >
                <Calendar className="w-3 h-3 text-[#8e9192]" />
                <span>Дата</span>
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Horizontal Category Chips */}
      <div className="flex items-center gap-2 overflow-x-auto -mx-4 px-4 no-scrollbar py-0.5">
        {/* 'All' Category Pill */}
        <button
          type="button"
          onClick={() => {
            if (selectedCategoryId) telegram.hapticImpact('light');
            onSelectCategory(undefined);
          }}
          className={`flex items-center gap-1.5 px-4 h-9 rounded-full text-xs shrink-0 transition-all active:scale-95 ${
            !selectedCategoryId
              ? 'bg-white text-[#08080a] font-bold shadow-[0_0_14px_rgba(255,255,255,0.2)]'
              : 'bg-[#2a2a2c]/60 text-[#c4c7c8] hover:text-white border border-white/5 font-medium shadow-[inset_0_1px_1px_rgba(255,255,255,0.06)]'
          }`}
        >
          <Sparkles className="w-3.5 h-3.5" />
          <span>Все</span>
        </button>

        {/* Dynamic Category Chips */}
        {categories.map((cat) => {
          const isSelected = selectedCategoryId === cat.id;
          return (
            <button
              key={cat.id}
              type="button"
              onClick={() => {
                telegram.hapticImpact('light');
                onSelectCategory(isSelected ? undefined : cat.id);
              }}
              className={`flex items-center gap-1.5 px-4 h-9 rounded-full text-xs shrink-0 transition-all active:scale-95 ${
                isSelected
                  ? 'bg-white text-[#08080a] font-bold shadow-[0_0_14px_rgba(255,255,255,0.2)]'
                  : 'bg-[#2a2a2c]/60 text-[#c4c7c8] hover:text-white border border-white/5 font-medium shadow-[inset_0_1px_1px_rgba(255,255,255,0.06)]'
              }`}
            >
              <span>{CATEGORY_ICONS[cat.id] || <Sparkles className="w-3.5 h-3.5" />}</span>
              <span>{cat.name}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
};
