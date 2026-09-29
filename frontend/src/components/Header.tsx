import React from 'react';
import type { City, TelegramWebAppUser } from '../types';
import { MapPin, ChevronDown, Ticket } from 'lucide-react';

interface HeaderProps {
  currentCity?: City;
  onOpenCityModal: () => void;
  user?: TelegramWebAppUser | null;
  isAdmin: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  currentCity,
  onOpenCityModal,
  isAdmin
}) => {
  return (
    <header className="sticky top-0 z-30 bg-[#0B0D13]/85 backdrop-blur-md border-b border-white/5 px-4 py-3">
      <div className="flex items-center justify-between max-w-lg mx-auto">
        {/* Brand */}
        <div className="flex items-center space-x-2">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-indigo-600 to-purple-600 flex items-center justify-center shadow-lg shadow-indigo-500/25">
            <Ticket className="w-4 h-4 text-white" />
          </div>
          <span className="font-bold text-lg tracking-tight bg-gradient-to-r from-white via-gray-200 to-gray-400 bg-clip-text text-transparent">
            Evently
          </span>
          {isAdmin && (
            <span className="text-[10px] uppercase font-bold tracking-wider px-1.5 py-0.5 rounded bg-indigo-500/20 text-indigo-400 border border-indigo-500/30">
              Admin
            </span>
          )}
        </div>

        {/* Prominent City Selector on the right */}
        <button
          onClick={onOpenCityModal}
          className="flex items-center space-x-1.5 px-3.5 py-1.5 rounded-full bg-[#181C2A] border border-indigo-500/30 hover:border-indigo-500 hover:bg-[#202538] transition-all text-xs font-semibold text-white shadow-sm active:scale-95"
          aria-label="Выбрать город"
        >
          <MapPin className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
          <span className="max-w-[140px] truncate">
            {currentCity ? currentCity.name : 'Выбрать город'}
          </span>
          <ChevronDown className="w-3.5 h-3.5 text-gray-400 shrink-0" />
        </button>
      </div>
    </header>
  );
};

