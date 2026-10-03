import React, { useState, useMemo } from 'react';
import type { City } from '../types';
import { api, DEFAULT_CITIES } from '../services/api';
import { telegram } from '../services/telegram';
import { MapPin, Check, X, Search, Navigation, Loader2, AlertCircle } from 'lucide-react';

interface CityModalProps {
  isOpen: boolean;
  onClose: () => void;
  cities: City[];
  selectedCityId: string;
  onSelectCity: (cityId: string) => void;
}

const CITY_EMOJIS: Record<string, string> = {
  makhachkala: '🏔️',
  kaspiysk: '🏖️',
  derbent: '🏰',
  khasavyurt: '🥋',
  grozny: '🌙',
  vladikavkaz: '⛰️',
  nalchik: '🌲',
  pyatigorsk: '🗻',
  stavropol: '🌾',
  moscow: '🏛️',
  spb: '🌉',
  kazan: '🕌',
  krasnodar: '☀️',
  sochi: '🌴',
  rostov_on_don: '🌊',
  yekaterinburg: '💎',
  ekaterinburg: '💎',
  novosibirsk: '🌲',
  nizhny_novgorod: '🏰',
  samara: '🚀',
  ufa: '🍯',
  chelyabinsk: '🏭',
  krasnoyarsk: '🏞️',
  voronezh: '⚓',
  perm: '🐻',
  volgograd: '⚔️',
  tyumen: '♨️',
  vladivostok: '⚓',
  kaliningrad: '🏰',
  yaroslavl: '🔔',
  khabarovsk: '🐯',
};

const POPULAR_CITY_IDS = [
  'makhachkala',
  'moscow',
  'spb',
  'kaspiysk',
  'derbent',
  'kazan',
];

const EN_TO_RU_MAP: Record<string, string> = {
  'q': 'й', 'w': 'ц', 'e': 'у', 'r': 'к', 't': 'е', 'y': 'н', 'u': 'г', 'i': 'ш', 'o': 'щ', 'p': 'з', '[': 'х', ']': 'ъ',
  'a': 'ф', 's': 'ы', 'd': 'в', 'f': 'а', 'g': 'п', 'h': 'р', 'j': 'о', 'k': 'л', 'l': 'д', ';': 'ж', "'": 'э',
  'z': 'я', 'x': 'ч', 'c': 'с', 'v': 'м', 'b': 'и', 'n': 'т', 'm': 'ь', ',': 'б', '.': 'ю',
};

function convertKeyboardLayout(text: string): string {
  return text.toLowerCase().split('').map(char => EN_TO_RU_MAP[char] || char).join('');
}

const TRANSLIT_MAP: Record<string, string> = {
  'moscow': 'москва',
  'moskva': 'москва',
  'spb': 'санкт-петербург',
  'saint petersburg': 'санкт-петербург',
  'peterburg': 'санкт-петербург',
  'piter': 'санкт-петербург',
  'makhachkala': 'махачкала',
  'kaspiysk': 'каспийск',
  'derbent': 'дербент',
  'kazan': 'казань',
  'sochi': 'сочи',
  'krasnodar': 'краснодар',
  'rostov': 'ростов-на-дону',
  'grozny': 'грозный',
};

export const CityModal: React.FC<CityModalProps> = ({
  isOpen,
  onClose,
  cities,
  selectedCityId,
  onSelectCity,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [isLocating, setIsLocating] = useState(false);
  const [locationError, setLocationError] = useState<string | null>(null);

  const allCities = useMemo(() => {
    return cities && cities.length > 0 ? cities : DEFAULT_CITIES;
  }, [cities]);

  const filteredCities = useMemo(() => {
    const rawQ = searchQuery.toLowerCase().trim();
    if (!rawQ) return allCities.slice(0, 40);

    const convertedQ = convertKeyboardLayout(rawQ);
    const translitQ = TRANSLIT_MAP[rawQ] || '';

    return allCities.filter((c) => {
      const name = c.name.toLowerCase();
      const id = c.id.toLowerCase();
      return (
        name.includes(rawQ) ||
        id.includes(rawQ) ||
        name.includes(convertedQ) ||
        id.includes(convertedQ) ||
        (translitQ && (name.includes(translitQ) || id.includes(translitQ)))
      );
    }).slice(0, 40);
  }, [allCities, searchQuery]);

  if (!isOpen) return null;

  const handleDetectLocation = async () => {
    try {
      setIsLocating(true);
      setLocationError(null);
      telegram.hapticImpact('light');

      const loc = await telegram.requestLocation();
      if (!loc) {
        throw new Error('Location unavailable');
      }
      const nearest = await api.getNearestCity(loc.latitude, loc.longitude);
      
      telegram.hapticSuccess();
      onSelectCity(nearest.id);
      onClose();
    } catch (err: any) {
      console.warn('Geolocation detection error:', err);
      setLocationError('Не удалось определить геопозицию. Выберите город из списка.');
      telegram.hapticError();
    } finally {
      setIsLocating(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[60] flex flex-col justify-end sm:justify-center items-center p-0 sm:p-4 bg-black/80 backdrop-fade-in">
      <div 
        className="w-full max-w-sm max-h-[85vh] rounded-t-[28px] sm:rounded-3xl bg-[#131722] border border-white/10 p-5 shadow-2xl flex flex-col space-y-3 sheet-slide-up"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between pb-1">
          <div className="flex items-center space-x-2">
            <div className="p-2 rounded-xl bg-indigo-500/10 text-indigo-400">
              <MapPin className="w-5 h-5" />
            </div>
            <h3 className="text-base font-bold text-white">Выберите город</h3>
          </div>
          <button 
            onClick={onClose}
            className="p-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-white/5 btn-press transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Location Detection Button */}
        <button
          onClick={handleDetectLocation}
          disabled={isLocating}
          className="w-full flex items-center justify-center space-x-2 p-2.5 rounded-xl bg-indigo-600/15 border border-indigo-500/30 text-indigo-300 hover:bg-indigo-600/25 hover:border-indigo-500/50 btn-press transition-all font-semibold text-xs disabled:opacity-60"
        >
          {isLocating ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin text-indigo-400" />
              <span>Определяем город...</span>
            </>
          ) : (
            <>
              <Navigation className="w-4 h-4 text-indigo-400" />
              <span>📍 Определить мой город</span>
            </>
          )}
        </button>

        {locationError && (
          <div className="p-2 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-300 text-[11px] flex items-center space-x-1.5">
            <AlertCircle className="w-3.5 h-3.5 shrink-0" />
            <span>{locationError}</span>
          </div>
        )}

        {/* Popular Cities Chips */}
        {!searchQuery.trim() && (
          <div className="space-y-1.5 pt-0.5">
            <div className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">
              Популярные города
            </div>
            <div className="flex flex-wrap gap-1.5">
              {POPULAR_CITY_IDS.map((popId) => {
                const city = allCities.find((c) => c.id === popId);
                if (!city) return null;
                const isSelected = city.id === selectedCityId;
                return (
                  <button
                    key={popId}
                    type="button"
                    onClick={() => {
                      telegram.hapticImpact('light');
                      onSelectCity(city.id);
                      onClose();
                    }}
                    className={`px-2.5 py-1 rounded-xl text-xs font-medium transition-all flex items-center space-x-1 btn-press ${
                      isSelected
                        ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/30'
                        : 'bg-[#1C2030] text-gray-300 border border-white/5 hover:border-white/20 hover:text-white'
                    }`}
                  >
                    <span>{CITY_EMOJIS[city.id] || '📍'}</span>
                    <span>{city.name}</span>
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* Search Input */}
        <div className="relative">
          <Search className="w-3.5 h-3.5 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Поиск города..."
            className="w-full pl-8 pr-3 py-2 rounded-xl bg-[#1C2030] border border-white/8 text-white placeholder-gray-400 text-xs focus:outline-none focus:border-indigo-500/60"
          />
        </div>

        {/* Cities list */}
        <div className="space-y-1.5 overflow-y-auto max-h-[260px] pr-0.5 custom-scrollbar">
          {filteredCities.length === 0 ? (
            <div className="py-6 text-center text-xs text-gray-400">
              Город не найден
            </div>
          ) : (
            filteredCities.map((city) => {
              const isSelected = city.id === selectedCityId;
              return (
                <button
                  key={city.id}
                  onClick={() => {
                    telegram.hapticImpact('light');
                    onSelectCity(city.id);
                    onClose();
                  }}
                  className={`w-full flex items-center justify-between p-2.5 rounded-xl border btn-press transition-all ${
                    isSelected
                      ? 'bg-indigo-600/20 border-indigo-500/60 text-white shadow-sm'
                      : 'bg-[#1C2030]/40 border-white/5 text-gray-300 hover:bg-[#1C2030] hover:text-white'
                  }`}
                >
                  <div className="flex items-center space-x-2.5">
                    <span className="text-xl">{CITY_EMOJIS[city.id] || '📍'}</span>
                    <div className="text-left">
                      <div className="font-semibold text-xs text-white">{city.name}</div>
                      <div className="text-[10px] text-gray-400">{city.country}</div>
                    </div>
                  </div>
                  {isSelected && (
                    <div className="w-5 h-5 rounded-full bg-indigo-500 flex items-center justify-center text-white shrink-0 shadow-sm animate-scale-pop">
                      <Check className="w-3 h-3 stroke-[3]" />
                    </div>
                  )}
                </button>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
};

