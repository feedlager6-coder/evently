import React from 'react';
import type { City, TelegramWebAppUser } from '../types';
import { MapPin, ChevronDown } from 'lucide-react';

interface HeaderProps {
  currentCity?: City;
  onOpenCityModal: () => void;
  user?: TelegramWebAppUser | null;
  isAdmin: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  currentCity,
  onOpenCityModal,
  isAdmin,
}) => {
  return (
    <header data-element="header" className="sticky top-0 z-30 bg-[#0B0D13]/85 backdrop-blur-md border-b border-white/5 px-4 py-3">
      <div className="flex items-center justify-between max-w-lg mx-auto">
        {/* Left Side: Brand Text 'Ivently' in the top-left corner */}
        <div className="flex items-center space-x-2">
          <span className="font-bold text-xl tracking-tight bg-gradient-to-r from-white via-gray-100 to-gray-300 bg-clip-text text-transparent select-none">
            Ivently
          </span>

          {isAdmin && (
            <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-indigo-500/15 text-indigo-400 border border-indigo-500/25">
              Admin
            </span>
          )}
        </div>

        {/* Right Side: City Selector */}
        <div className="flex items-center">
          <button
            data-element="city-selector"
            onClick={onOpenCityModal}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-full bg-[#161A28] border border-white/10 hover:border-indigo-500/40 text-xs font-semibold text-white shadow-sm btn-press transition-all max-w-[155px]"
            aria-label="Выбрать город"
            title={currentCity ? currentCity.name : 'Выбрать город'}
          >
            <MapPin className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
            <span className="truncate text-ellipsis">
              {currentCity ? currentCity.name : 'Город'}
            </span>
            <ChevronDown className="w-3.5 h-3.5 text-gray-400 shrink-0" />
          </button>
        </div>
      </div>
    </header>
  );
};

export default Header;
