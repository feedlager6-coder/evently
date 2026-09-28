import React from 'react';
import type { City } from '../types';
import { MapPin, Check, X } from 'lucide-react';

interface CityModalProps {
  isOpen: boolean;
  onClose: () => void;
  cities: City[];
  selectedCityId: string;
  onSelectCity: (cityId: string) => void;
}

const CITY_EMOJIS: Record<string, string> = {
  warsaw: '🇵🇱',
  makhachkala: '🏔️',
  moscow: '🏛️',
};

export const CityModal: React.FC<CityModalProps> = ({
  isOpen,
  onClose,
  cities,
  selectedCityId,
  onSelectCity,
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fade-in">
      <div 
        className="w-full max-w-sm rounded-2xl bg-[#141722] border border-white/10 p-5 shadow-2xl space-y-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <div className="p-2 rounded-xl bg-indigo-500/10 text-indigo-400">
              <MapPin className="w-5 h-5" />
            </div>
            <h3 className="text-lg font-semibold text-white">Выберите город</h3>
          </div>
          <button 
            onClick={onClose}
            className="p-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-white/5 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <p className="text-xs text-gray-400">
          События и фильтры по датам будут настроены по местному часовому поясу города.
        </p>

        <div className="space-y-2 pt-1">
          {cities.map((city) => {
            const isSelected = city.id === selectedCityId;
            return (
              <button
                key={city.id}
                onClick={() => {
                  onSelectCity(city.id);
                  onClose();
                }}
                className={`w-full flex items-center justify-between p-3.5 rounded-xl border transition-all ${
                  isSelected
                    ? 'bg-indigo-600/15 border-indigo-500/60 text-white'
                    : 'bg-[#1C2030]/50 border-white/5 text-gray-300 hover:bg-[#1C2030] hover:text-white'
                }`}
              >
                <div className="flex items-center space-x-3">
                  <span className="text-2xl">{CITY_EMOJIS[city.id] || '📍'}</span>
                  <div className="text-left">
                    <div className="font-medium text-sm text-white">{city.name}</div>
                    <div className="text-xs text-gray-400">{city.country} · {city.currency}</div>
                  </div>
                </div>
                {isSelected && (
                  <div className="w-6 h-6 rounded-full bg-indigo-500 flex items-center justify-center text-white">
                    <Check className="w-3.5 h-3.5 stroke-[3]" />
                  </div>
                )}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
};
