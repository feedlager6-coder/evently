import React, { useState } from 'react';
import type { City, Category, EventCreatePayload } from '../types';
import { api } from '../services/api';
import { telegram } from '../services/telegram';
import { X, Calendar, PlusCircle, CheckCircle2, AlertCircle, Loader2, Image } from 'lucide-react';

interface CreateEventModalProps {
  isOpen: boolean;
  onClose: () => void;
  cities: City[];
  categories: Category[];
  defaultCityId?: string;
  onEventCreated: () => void;
}

const PRESET_IMAGES = [
  { label: 'Концерт', url: 'https://images.unsplash.com/photo-1514525253161-7a46d19cd819?w=800' },
  { label: 'Вечеринка', url: 'https://images.unsplash.com/photo-1492684223066-81342ee5ff30?w=800' },
  { label: 'Спорт', url: 'https://images.unsplash.com/photo-1461896836934-ffe607ba8211?w=800' },
  { label: 'Митап', url: 'https://images.unsplash.com/photo-1540575467063-178a50c2df87?w=800' },
  { label: 'Арт', url: 'https://images.unsplash.com/photo-1508997449629-303059a039c0?w=800' },
];

export const CreateEventModal: React.FC<CreateEventModalProps> = ({
  isOpen,
  onClose,
  cities,
  categories,
  defaultCityId,
  onEventCreated,
}) => {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [cityId, setCityId] = useState(defaultCityId || 'warsaw');
  const [categoryId, setCategoryId] = useState('concerts');
  
  // Tomorrow at 19:00 default start date
  const tomorrow = new Date();
  tomorrow.setDate(tomorrow.getDate() + 1);
  tomorrow.setHours(19, 0, 0, 0);
  const defaultDateStr = tomorrow.toISOString().slice(0, 16);

  const [startAt, setStartAt] = useState(defaultDateStr);
  const [venueName, setVenueName] = useState('');
  const [address, setAddress] = useState('');
  const [isFree, setIsFree] = useState(false);
  const [priceAmount, setPriceAmount] = useState<string>('50');
  const [coverImageUrl, setCoverImageUrl] = useState(PRESET_IMAGES[0].url);

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  if (!isOpen) return null;

  const currentCity = cities.find((c) => c.id === cityId);
  const currency = currentCity?.currency || 'PLN';

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || !description.trim() || !venueName.trim() || !startAt) {
      setError('Пожалуйста, заполните все обязательные поля');
      return;
    }

    try {
      setIsLoading(true);
      setError(null);
      telegram.hapticImpact('medium');

      const payload: EventCreatePayload = {
        title: title.trim(),
        description: description.trim(),
        city_id: cityId,
        category_id: categoryId,
        start_at: new Date(startAt).toISOString(),
        venue_name: venueName.trim(),
        address: address.trim() || undefined,
        price_amount: isFree ? undefined : Number(priceAmount) || 0,
        price_currency: isFree ? undefined : currency,
        cover_image_url: coverImageUrl.trim() || undefined,
      };

      await api.createEvent(payload);
      telegram.hapticSuccess();
      setSuccess(true);
      onEventCreated();
    } catch (err: any) {
      setError(err.message || 'Ошибка создания мероприятия');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-black/80 backdrop-blur-sm animate-fade-in overflow-y-auto">
      <div 
        className="w-full max-w-lg rounded-3xl bg-[#121522] border border-white/10 p-5 shadow-2xl space-y-4 my-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between pb-2 border-b border-white/5">
          <div className="flex items-center space-x-2">
            <div className="p-2 rounded-xl bg-indigo-500/10 text-indigo-400">
              <PlusCircle className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-white">Создать мероприятие</h3>
              <p className="text-xs text-gray-400">Публикация после модерации</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-white/5 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {success ? (
          <div className="py-8 text-center space-y-4">
            <div className="w-16 h-16 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center mx-auto">
              <CheckCircle2 className="w-8 h-8" />
            </div>
            <div className="space-y-1">
              <h4 className="text-lg font-bold text-white">Отправлено на модерацию!</h4>
              <p className="text-xs text-gray-300 max-w-xs mx-auto">
                Ваше событие успешно создано и отправлено администраторам. Как только его одобрят, оно станет доступно в афише Evently.
              </p>
            </div>
            <button
              onClick={onClose}
              className="px-6 py-2.5 rounded-xl bg-indigo-600 text-white font-semibold text-xs shadow-lg hover:bg-indigo-500 transition-colors"
            >
              Отлично, понятно
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4 text-xs">
            {error && (
              <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-300 flex items-center space-x-2">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            {/* Title */}
            <div className="space-y-1">
              <label className="text-gray-300 font-medium">Название события *</label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="например: Sunset Rooftop Party"
                className="w-full px-3.5 py-2.5 rounded-xl bg-[#1A1E2E] border border-white/10 text-white focus:outline-none focus:border-indigo-500 placeholder-gray-500"
                required
              />
            </div>

            {/* City & Category Selectors */}
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-gray-300 font-medium">Город *</label>
                <select
                  value={cityId}
                  onChange={(e) => setCityId(e.target.value)}
                  className="w-full px-3 py-2.5 rounded-xl bg-[#1A1E2E] border border-white/10 text-white focus:outline-none focus:border-indigo-500"
                >
                  {cities.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-1">
                <label className="text-gray-300 font-medium">Категория *</label>
                <select
                  value={categoryId}
                  onChange={(e) => setCategoryId(e.target.value)}
                  className="w-full px-3 py-2.5 rounded-xl bg-[#1A1E2E] border border-white/10 text-white focus:outline-none focus:border-indigo-500"
                >
                  {categories.map((cat) => (
                    <option key={cat.id} value={cat.id}>
                      {cat.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Start Date & Time */}
            <div className="space-y-1">
              <label className="text-gray-300 font-medium flex items-center space-x-1.5">
                <Calendar className="w-3.5 h-3.5 text-indigo-400" />
                <span>Дата и время начала *</span>
              </label>
              <input
                type="datetime-local"
                value={startAt}
                onChange={(e) => setStartAt(e.target.value)}
                className="w-full px-3.5 py-2 rounded-xl bg-[#1A1E2E] border border-white/10 text-white focus:outline-none focus:border-indigo-500"
                required
              />
            </div>

            {/* Venue & Address */}
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-gray-300 font-medium">Место / Площадка *</label>
                <input
                  type="text"
                  value={venueName}
                  onChange={(e) => setVenueName(e.target.value)}
                  placeholder="The View Rooftop"
                  className="w-full px-3 py-2 rounded-xl bg-[#1A1E2E] border border-white/10 text-white focus:outline-none focus:border-indigo-500 placeholder-gray-500"
                  required
                />
              </div>

              <div className="space-y-1">
                <label className="text-gray-300 font-medium">Адрес</label>
                <input
                  type="text"
                  value={address}
                  onChange={(e) => setAddress(e.target.value)}
                  placeholder="ул. Тварда 18"
                  className="w-full px-3 py-2 rounded-xl bg-[#1A1E2E] border border-white/10 text-white focus:outline-none focus:border-indigo-500 placeholder-gray-500"
                />
              </div>
            </div>

            {/* Price Config */}
            <div className="space-y-1 p-3 rounded-xl bg-[#171B2A] border border-white/5">
              <div className="flex items-center justify-between">
                <span className="font-medium text-gray-200">Бесплатный вход?</span>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={isFree}
                    onChange={(e) => setIsFree(e.target.checked)}
                    className="sr-only peer"
                  />
                  <div className="w-9 h-5 bg-gray-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-emerald-500"></div>
                </label>
              </div>

              {!isFree && (
                <div className="pt-2 flex items-center space-x-2">
                  <input
                    type="number"
                    min="0"
                    step="1"
                    value={priceAmount}
                    onChange={(e) => setPriceAmount(e.target.value)}
                    placeholder="Цена"
                    className="flex-1 px-3 py-1.5 rounded-lg bg-[#1A1E2E] border border-white/10 text-white focus:outline-none focus:border-indigo-500"
                  />
                  <span className="text-gray-400 font-semibold px-2">{currency}</span>
                </div>
              )}
            </div>

            {/* Image Presets */}
            <div className="space-y-1.5">
              <label className="text-gray-300 font-medium flex items-center space-x-1.5">
                <Image className="w-3.5 h-3.5 text-indigo-400" />
                <span>Обложка (выберите шаблон или укажите URL)</span>
              </label>
              <div className="flex space-x-1.5 overflow-x-auto no-scrollbar pb-1">
                {PRESET_IMAGES.map((preset) => (
                  <button
                    key={preset.label}
                    type="button"
                    onClick={() => setCoverImageUrl(preset.url)}
                    className={`px-2.5 py-1 rounded-lg text-[11px] whitespace-nowrap border transition-all ${
                      coverImageUrl === preset.url
                        ? 'bg-indigo-600/30 border-indigo-500 text-white font-semibold'
                        : 'bg-[#1A1E2E] border-white/5 text-gray-400'
                    }`}
                  >
                    {preset.label}
                  </button>
                ))}
              </div>
              <input
                type="url"
                value={coverImageUrl}
                onChange={(e) => setCoverImageUrl(e.target.value)}
                placeholder="https://images.unsplash.com/..."
                className="w-full px-3 py-1.5 rounded-xl bg-[#1A1E2E] border border-white/10 text-white focus:outline-none focus:border-indigo-500 placeholder-gray-500 text-[11px]"
              />
            </div>

            {/* Description */}
            <div className="space-y-1">
              <label className="text-gray-300 font-medium">Описание события *</label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={3}
                placeholder="Расскажите подробнее о программе, спикерах или формате..."
                className="w-full px-3.5 py-2 rounded-xl bg-[#1A1E2E] border border-white/10 text-white focus:outline-none focus:border-indigo-500 placeholder-gray-500"
                required
              />
            </div>

            {/* Submit */}
            <button
              type="submit"
              disabled={isLoading}
              className="w-full py-3 rounded-2xl bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs shadow-lg shadow-indigo-600/30 flex items-center justify-center space-x-2 transition-all active:scale-[0.98] disabled:opacity-50"
            >
              {isLoading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <>
                  <PlusCircle className="w-4 h-4" />
                  <span>Отправить на модерацию</span>
                </>
              )}
            </button>
          </form>
        )}
      </div>
    </div>
  );
};
