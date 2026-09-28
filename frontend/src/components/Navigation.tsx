import React from 'react';
import { Compass, PlusCircle, Calendar, Shield } from 'lucide-react';

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
  return (
    <nav className="fixed bottom-0 inset-x-0 z-40 bg-[#0E101A]/95 backdrop-blur-md border-t border-white/8 py-2 px-4">
      <div className="flex items-center justify-around max-w-lg mx-auto">
        {/* Feed Tab */}
        <button
          onClick={() => onChangeTab('feed')}
          className={`flex flex-col items-center py-1 px-3 rounded-xl transition-all ${
            currentTab === 'feed'
              ? 'text-indigo-400 font-bold scale-105'
              : 'text-gray-400 hover:text-gray-200'
          }`}
        >
          <Compass className="w-5 h-5 mb-0.5" />
          <span className="text-[10px]">Афиша</span>
        </button>

        {/* Create Event Tab */}
        <button
          onClick={() => onChangeTab('create')}
          className={`flex flex-col items-center py-1 px-3 rounded-xl transition-all ${
            currentTab === 'create'
              ? 'text-indigo-400 font-bold scale-105'
              : 'text-gray-400 hover:text-gray-200'
          }`}
        >
          <PlusCircle className="w-5 h-5 mb-0.5" />
          <span className="text-[10px]">Создать</span>
        </button>

        {/* Organizer Tab */}
        <button
          onClick={() => onChangeTab('organizer')}
          className={`flex flex-col items-center py-1 px-3 rounded-xl transition-all ${
            currentTab === 'organizer'
              ? 'text-indigo-400 font-bold scale-105'
              : 'text-gray-400 hover:text-gray-200'
          }`}
        >
          <Calendar className="w-5 h-5 mb-0.5" />
          <span className="text-[10px]">Мои события</span>
        </button>

        {/* Admin Tab (only if admin) */}
        {isAdmin && (
          <button
            onClick={() => onChangeTab('admin')}
            className={`flex flex-col items-center py-1 px-3 rounded-xl transition-all ${
              currentTab === 'admin'
                ? 'text-indigo-400 font-bold scale-105'
                : 'text-gray-400 hover:text-gray-200'
            }`}
          >
            <Shield className="w-5 h-5 mb-0.5" />
            <span className="text-[10px]">Модерация</span>
          </button>
        )}
      </div>
    </nav>
  );
};
