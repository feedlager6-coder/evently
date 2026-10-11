import React, { useRef, useEffect, useState } from 'react';
import { Sparkles, Music, Flame, Dumbbell, GraduationCap, Palette } from 'lucide-react';

export interface DateOption {
  id: string;
  label: string;
}

export interface CategoryOption {
  id: string;
  label: string;
  icon?: React.ComponentType<{ className?: string; size?: number }>;
}

export const DATE_OPTIONS: DateOption[] = [
  { id: 'all', label: 'Все даты' },
  { id: 'today', label: 'Сегодня' },
  { id: 'tomorrow', label: 'Завтра' },
  { id: 'weekend', label: 'Выходные' },
];

export const CATEGORY_OPTIONS: CategoryOption[] = [
  { id: 'all', label: 'Все категории', icon: Sparkles },
  { id: 'concerts', label: 'Концерты', icon: Music },
  { id: 'exhibitions', label: 'Выставки', icon: Palette },
  { id: 'parties', label: 'Вечеринки', icon: Flame },
  { id: 'sports', label: 'Спорт', icon: Dumbbell },
  { id: 'education', label: 'Образование', icon: GraduationCap },
];

export interface EditorialControlsProps {
  selectedDate: string;
  onDateChange: (id: string) => void;
  selectedCategory: string;
  onCategoryChange: (id: string) => void;
  className?: string;
}

export const EditorialControls: React.FC<EditorialControlsProps> = ({
  selectedDate,
  onDateChange,
  selectedCategory,
  onCategoryChange,
  className = '',
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [lensStyle, setLensStyle] = useState({ left: 0, width: 0 });

  useEffect(() => {
    if (!containerRef.current) return;
    const activeEl = containerRef.current.querySelector(`[data-date-id="${selectedDate}"]`) as HTMLElement;
    if (activeEl) {
      setLensStyle({
        left: activeEl.offsetLeft,
        width: activeEl.offsetWidth,
      });
    }
  }, [selectedDate]);

  return (
    <div
      role="region"
      aria-label="Фильтры событий по датам и категориям"
      className={`flex flex-col gap-3 w-full ${className}`}
    >

      {/* 1. Date Segmented Control with Liquid Glass Lens */}
      <div className="px-4">
        <div
          ref={containerRef}
          role="radiogroup"
          aria-label="Фильтр по датам"
          className="relative flex items-center p-1 rounded-full bg-[#0A0B0F]/90 border border-white/[0.08] backdrop-blur-md overflow-hidden"
        >
          {/* Sliding Optical Lens Indicator */}
          <div
            className="dock-lens-indicator"
            style={{
              transform: `translateX(${lensStyle.left}px)`,
              width: `${lensStyle.width}px`,
            }}
            aria-hidden="true"
          />

          {DATE_OPTIONS.map((opt) => {
            const isActive = selectedDate === opt.id;
            return (
              <button
                key={opt.id}
                data-date-id={opt.id}
                role="radio"
                aria-checked={isActive}
                onClick={() => onDateChange(opt.id)}
                className={`relative z-10 flex-1 py-1.5 px-2 text-center text-xs font-semibold rounded-full transition-colors duration-200 outline-none cursor-pointer ${
                  isActive ? 'text-white' : 'text-neutral-400 hover:text-neutral-200'
                }`}
              >
                {opt.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* 2. Horizontal Scrollable Category Pills */}
      <div className="flex items-center gap-2 overflow-x-auto no-scrollbar px-4 pb-1">
        {CATEGORY_OPTIONS.map((cat) => {
          const isActive = selectedCategory === cat.id;
          const Icon = cat.icon;

          return (
            <button
              key={cat.id}
              role="checkbox"
              aria-checked={isActive}
              onClick={() => onCategoryChange(cat.id)}
              className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs font-medium whitespace-nowrap transition-all duration-200 cursor-pointer outline-none ${
                isActive
                  ? 'liquid-lens text-white shadow-md'
                  : 'bg-[#0E1017] text-neutral-400 border border-white/[0.06] hover:text-neutral-200 hover:border-white/10'
              }`}
            >
              {Icon && <Icon size={14} className={isActive ? 'text-white' : 'text-neutral-400'} />}
              <span>{cat.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
};
