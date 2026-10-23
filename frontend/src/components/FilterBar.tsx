import React from 'react';
import type { Category, DateFilterType } from '../types';
import { Sparkles, Music, Flame, Dumbbell, GraduationCap, Briefcase, Palette, Compass, Drama, Film } from 'lucide-react';
import { haptics } from '../utils/haptics';

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
  cinema: <Film className="w-3.5 h-3.5" />,
  other: <Compass className="w-3.5 h-3.5" />,
};

export const FilterBar: React.FC<FilterBarProps> = ({
  dateFilter,
  onSelectDate,
  categories,
  selectedCategoryId,
  onSelectCategory,
}) => {
  return (
    <div className="space-y-3 pt-1 pb-1">
      {/* Segmented Date Filter Bar */}
      <div className="px-4">
        <div className="flex items-center gap-1 p-1 bg-[#0e0e10]/85 backdrop-blur-xl rounded-full border border-white/8 shadow-[inset_0_1px_1px_rgba(255,255,255,0.05)]">
          {DATE_OPTIONS.map((opt) => {
            const isSelected = dateFilter === opt.id;
            return (
              <button
                key={opt.id}
                type="button"
                onClick={() => {
                  haptics.selectionChanged();
                  onSelectDate(opt.id);
                }}
                className={`flex-1 py-2 px-1 rounded-full text-center text-xs whitespace-nowrap transition-all duration-200 ${
                  isSelected
                    ? 'bg-[#39393b] text-white font-semibold shadow-[inset_0_1px_2px_rgba(255,255,255,0.3),0_2px_8px_rgba(0,0,0,0.4)]'
                    : 'text-[#c4c7c8] hover:text-white font-medium'
                }`}
              >
                {opt.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Horizontal Category Chips */}
      <div className="flex items-center gap-2 overflow-x-auto -mx-4 px-4 no-scrollbar py-0.5">
        {/* 'All' Category Pill */}
        <button
          type="button"
          onClick={() => {
            if (selectedCategoryId) haptics.selectionChanged();
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
                haptics.selectionChanged();
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
