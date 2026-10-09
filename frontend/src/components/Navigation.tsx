import React from 'react';
import { Compass, Calendar, Shield } from 'lucide-react';
import { telegram } from '../services/telegram';

export type TabType = 'feed' | 'my_events' | 'admin' | 'organizer';

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

  const isMyEventsActive = currentTab === 'my_events' || currentTab === 'organizer';

  return (
    <nav data-element="navigation" className="fixed bottom-0 inset-x-0 z-40 bg-[#0E101A]/92 backdrop-blur-md border-t border-white/8 nav-safe-bottom px-4">
      <div className="flex items-center justify-around max-w-lg mx-auto">
        {/* Feed Tab */}
        <button
          data-element={currentTab === 'feed' ? 'nav-tab-active' : undefined}
          onClick={() => handleTabClick('feed')}
          className={`flex flex-col items-center py-1.5 px-4 rounded-full btn-press transition-colors duration-150 ${
            currentTab === 'feed'
              ? 'text-indigo-400 font-semibold'
              : 'text-gray-400 hover:text-gray-200'
          }`}
          aria-label="Афиша"
        >
          <Compass
            className={`w-5 h-5 mb-0.5 transition-transform duration-150 ${
              currentTab === 'feed' ? 'scale-105 stroke-[2.25]' : 'stroke-2'
            }`}
          />
          <span className="text-[10px] tracking-tight">Афиша</span>
        </button>

        {/* My Events Tab (Personal Hub) */}
        <button
          data-element={isMyEventsActive ? 'nav-tab-active' : undefined}
          onClick={() => handleTabClick('my_events')}
          className={`flex flex-col items-center py-1.5 px-4 rounded-full btn-press transition-colors duration-150 ${
            isMyEventsActive
              ? 'text-indigo-400 font-semibold'
              : 'text-gray-400 hover:text-gray-200'
          }`}
          aria-label="Мои события"
        >
          <Calendar
            className={`w-5 h-5 mb-0.5 transition-transform duration-150 ${
              isMyEventsActive ? 'scale-105 stroke-[2.25]' : 'stroke-2'
            }`}
          />
          <span className="text-[10px] tracking-tight">Мои события</span>
        </button>

        {/* Admin Tab (only if admin) */}
        {isAdmin && (
          <button
            data-element={currentTab === 'admin' ? 'nav-tab-active' : undefined}
            onClick={() => handleTabClick('admin')}
            className={`flex flex-col items-center py-1.5 px-4 rounded-full btn-press transition-colors duration-150 ${
              currentTab === 'admin'
                ? 'text-indigo-400 font-semibold'
                : 'text-gray-400 hover:text-gray-200'
            }`}
            aria-label="Модерация"
          >
            <Shield
              className={`w-5 h-5 mb-0.5 transition-transform duration-150 ${
                currentTab === 'admin' ? 'scale-105 stroke-[2.25]' : 'stroke-2'
              }`}
            />
            <span className="text-[10px] tracking-tight">Модерация</span>
          </button>
        )}
      </div>
    </nav>
  );
};
