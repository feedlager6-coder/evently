import React from 'react';
import { Compass, PlusCircle, Calendar, Shield } from 'lucide-react';

import { telegram } from '../services/telegram';

export type TabType = 'feed' | 'create' | 'organizer' | 'admin';

interface NavigationProps {
  currentTab: TabType;
  onChangeTab: (tab: TabType) => void;
  isAdmin: boolean;
}

export const Navigation: React.FC<NavigationProps> = ({
  currentTab,
  onChangeTab,
  isAdmin,
}) => {
  const handleTabClick = (tab: TabType) => {
    if (tab !== currentTab) {
      telegram.hapticImpact('light');
    }
    onChangeTab(tab);
  };

  return (
    <nav className="fixed bottom-0 inset-x-0 z-40 bg-[#0E101A]/92 backdrop-blur-md border-t border-white/8 nav-safe-bottom px-4">
      <div className="flex items-center justify-around max-w-lg mx-auto">
        {/* Feed Tab */}
        <button
          onClick={() => handleTabClick('feed')}
          className={`flex flex-col items-center py-1.5 px-3.5 rounded-xl btn-press transition-all ${
            currentTab === 'feed'
              ? 'text-indigo-400 font-bold bg-indigo-500/10 border border-indigo-500/20 shadow-sm shadow-indigo-500/20'
              : 'text-gray-400 hover:text-gray-200 border border-transparent'
          }`}
          aria-label="Афиша"
        >
          <Compass className="w-5 h-5 mb-0.5" />
          <span className="text-[10px] tracking-tight">Афиша</span>
        </button>

        {/* Create Event Tab */}
        <button
          onClick={() => handleTabClick('create')}
          className={`flex flex-col items-center py-1.5 px-3.5 rounded-xl btn-press transition-all ${
            currentTab === 'create'
              ? 'text-indigo-400 font-bold bg-indigo-500/10 border border-indigo-500/20 shadow-sm shadow-indigo-500/20'
              : 'text-gray-400 hover:text-gray-200 border border-transparent'
          }`}
          aria-label="Создать"
        >
          <PlusCircle className="w-5 h-5 mb-0.5" />
          <span className="text-[10px] tracking-tight">Создать</span>
        </button>

        {/* Organizer Tab */}
        <button
          onClick={() => handleTabClick('organizer')}
          className={`flex flex-col items-center py-1.5 px-3.5 rounded-xl btn-press transition-all ${
            currentTab === 'organizer'
              ? 'text-indigo-400 font-bold bg-indigo-500/10 border border-indigo-500/20 shadow-sm shadow-indigo-500/20'
              : 'text-gray-400 hover:text-gray-200 border border-transparent'
          }`}
          aria-label="Мои события"
        >
          <Calendar className="w-5 h-5 mb-0.5" />
          <span className="text-[10px] tracking-tight">Мои события</span>
        </button>

        {/* Admin Tab (only if admin) */}
        {isAdmin && (
          <button
            onClick={() => handleTabClick('admin')}
            className={`flex flex-col items-center py-1.5 px-3.5 rounded-xl btn-press transition-all ${
              currentTab === 'admin'
                ? 'text-indigo-400 font-bold bg-indigo-500/10 border border-indigo-500/20 shadow-sm shadow-indigo-500/20'
                : 'text-gray-400 hover:text-gray-200 border border-transparent'
            }`}
            aria-label="Модерация"
          >
            <Shield className="w-5 h-5 mb-0.5" />
            <span className="text-[10px] tracking-tight">Модерация</span>
          </button>
        )}
      </div>
    </nav>
  );
};
