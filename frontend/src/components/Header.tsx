import React from 'react';
import type { City, TelegramWebAppUser } from '../types';
import { MapPin, ChevronDown, Ticket, Sparkles } from 'lucide-react';

interface HeaderProps {
  currentCity?: City;
  onOpenCityModal: () => void;
  user: TelegramWebAppUser | null;
  isAdmin: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  currentCity,
  onOpenCityModal,
  user,
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

        {/* City Selector Pill */}
        <button
          onClick={onOpenCityModal}
          className="flex items-center space-x-1.5 px-3 py-1.5 rounded-full bg-[#181C2A] border border-white/10 hover:border-indigo-500/50 hover:bg-[#202538] transition-all text-xs font-medium text-gray-200 shadow-sm"
        >
          <MapPin className="w-3.5 h-3.5 text-indigo-400" />
          <span>{currentCity ? currentCity.name : 'Выбрать город'}</span>
          <ChevronDown className="w-3.5 h-3.5 text-gray-400" />
        </button>

        {/* User avatar / badge */}
        <div className="flex items-center">
          {user ? (
            <div className="flex items-center space-x-1.5 text-xs text-gray-300 bg-white/5 py-1 px-2.5 rounded-full border border-white/5">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              <span className="font-medium max-w-[80px] truncate">{user.first_name}</span>
            </div>
          ) : (
            <div className="flex items-center space-x-1 text-xs text-indigo-400 bg-indigo-500/10 px-2 py-1 rounded-full border border-indigo-500/20">
              <Sparkles className="w-3 h-3" />
              <span>Гость</span>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
