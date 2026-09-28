import React from 'react';
import type { Category, DateFilterType } from '../types';
import { Sparkles, Music, Flame, Dumbbell, GraduationCap, Briefcase, Palette, Compass } from 'lucide-react';

interface FilterBarProps {
  dateFilter: DateFilterType;
  onSelectDate: (date: DateFilterType) => void;
  categories: Category[];
  selectedCategoryId?: string;
  onSelectCategory: (categoryId?: string) => void;
}

const DATE_OPTIONS: { id: DateFilterType; label: string }[] = [
  { id: 'all', label: 'Все даты' },
  { id: 'today', label: 'Сегодня' },
  { id: 'tomorrow', label: 'Завтра' },
  { id: 'weekend', label: 'Выходные' },
];

const CATEGORY_ICONS: Record<string, React.ReactNode> = {
  concerts: <Music className="w-3.5 h-3.5" />,
  parties: <Flame className="w-3.5 h-3.5" />,
  sports: <Dumbbell className="w-3.5 h-3.5" />,
  education: <GraduationCap className="w-3.5 h-3.5" />,
  business: <Briefcase className="w-3.5 h-3.5" />,
  exhibitions: <Palette className="w-3.5 h-3.5" />,
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
    <div className="space-y-3 py-2">
      {/* Date Quick Segmented Control */}
      <div className="flex bg-[#141724] p-1 rounded-xl border border-white/5 mx-4">
        {DATE_OPTIONS.map((opt) => {
          const isSelected = dateFilter === opt.id;
          return (
            <button
              key={opt.id}
              onClick={() => onSelectDate(opt.id)}
              className={`flex-1 py-1.5 text-xs font-medium rounded-lg transition-all text-center ${
                isSelected
                  ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/30'
                  : 'text-gray-400 hover:text-gray-200'
              }`}
            >
              {opt.label}
            </button>
          );
        })}
      </div>

      {/* Horizontal Category Scroll Pills */}
      <div className="flex items-center space-x-2 overflow-x-auto no-scrollbar px-4 pb-1">
        {/* 'All' Category Pill */}
        <button
          onClick={() => onSelectCategory(undefined)}
          className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-full text-xs font-medium whitespace-nowrap transition-all border ${
            !selectedCategoryId
              ? 'bg-white text-gray-900 border-white shadow-sm'
              : 'bg-[#181C2A] text-gray-300 border-white/5 hover:border-white/20'
          }`}
        >
          <Sparkles className="w-3.5 h-3.5" />
          <span>Все категории</span>
        </button>

        {/* Dynamic Category Pills */}
        {categories.map((cat) => {
          const isSelected = selectedCategoryId === cat.id;
          return (
            <button
              key={cat.id}
              onClick={() => onSelectCategory(isSelected ? undefined : cat.id)}
              className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-full text-xs font-medium whitespace-nowrap transition-all border ${
                isSelected
                  ? 'bg-indigo-600 text-white border-indigo-500 shadow-md shadow-indigo-600/20'
                  : 'bg-[#181C2A] text-gray-300 border-white/5 hover:border-white/20'
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
