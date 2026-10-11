import React from 'react';
import type { City, TelegramWebAppUser } from '../types';
import { Bell, ChevronDown, User } from 'lucide-react';
import { BrandIcon } from './BrandIcon';
import { SafeAvatar } from './SafeAvatar';

interface HeaderProps {
  currentCity?: City;
  onOpenCityModal: () => void;
  user?: TelegramWebAppUser | null;
  isAdmin: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  currentCity,
  onOpenCityModal,
  user,
  isAdmin
}) => {
  return (
    <header className="sticky top-0 z-40 bg-[#08080A]/85 backdrop-blur-xl border-b border-white/8 px-4 py-2.5 shadow-[0_1px_12px_rgba(0,0,0,0.4)]">
      <div className="flex items-center justify-between max-w-[480px] mx-auto">
        {/* Brand & City */}
        <div className="flex items-center space-x-2.5 min-w-0">
          <BrandIcon className="w-8 h-8 rounded-xl bg-[#1c1b1e] border border-white/12 p-1.5" iconClassName="w-4 h-4 text-white" />
          <div className="flex flex-col min-w-0">
            <div className="flex items-center space-x-1.5">
              <span className="font-bold text-base tracking-tight text-white leading-none">
                Ivently
              </span>
              {isAdmin && (
                <span className="text-[9px] uppercase font-bold tracking-wider px-1.5 py-0.5 rounded-full bg-[#10b981]/20 text-[#4edea3] border border-[#10b981]/30 leading-none">
                  Admin
                </span>
              )}
            </div>

            {/* City Selector Pill */}
            <button
              onClick={onOpenCityModal}
              className="flex items-center space-x-1 text-[#c4c7c8] hover:text-white transition-colors text-xs pt-0.5 text-left group"
              aria-label="Выбрать город"
              title={currentCity ? currentCity.name : 'Выбрать город'}
            >
              <span className="max-w-[120px] truncate font-medium text-[11px] text-[#c4c7c8] group-hover:text-white">
                {currentCity ? currentCity.name : 'Выбрать город'}
              </span>
              <ChevronDown className="w-3 h-3 text-[#8e9192] group-hover:text-white transition-colors shrink-0" />
            </button>
          </div>
        </div>

        {/* Right Actions: Notification Bell + Avatar matching Stitch */}
        <div className="flex items-center space-x-2.5 shrink-0">
          <button
            type="button"
            className="w-9 h-9 rounded-full bg-[#1c1b1e]/80 border border-white/10 hover:border-white/20 flex items-center justify-center text-[#c4c7c8] hover:text-white transition-all active:scale-95 shadow-[inset_0_1px_1px_rgba(255,255,255,0.08)] relative"
            aria-label="Уведомления"
          >
            <Bell className="w-4 h-4" />
            <span className="absolute top-2 right-2 w-1.5 h-1.5 rounded-full bg-[#10b981] shadow-[0_0_6px_#10b981]" />
          </button>

          <div className="w-9 h-9 rounded-full overflow-hidden border border-white/15 shadow-sm shrink-0 ring-1 ring-white/10 bg-[#1c1b1e] flex items-center justify-center">
            {user ? (
              <SafeAvatar
                name={user.first_name || user.username || 'U'}
                type="user"
                className="w-full h-full object-cover"
              />
            ) : (
              <div className="w-full h-full bg-[#2a2a2c] flex items-center justify-center text-zinc-300">
                <User className="w-4 h-4 text-zinc-300" />
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  );
};

