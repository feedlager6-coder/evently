import React, { useState, useEffect, useRef } from 'react';
import type { City, Category, EventCreatePayload, LocationSuggestion, OrganizationSummary } from '../types';
import { api, DEFAULT_CITIES } from '../services/api';
import { telegram } from '../services/telegram';
import { 
  X, 
  Calendar, 
  PlusCircle, 
  CheckCircle2, 
  AlertCircle, 
  Loader2, 
  Image as ImageIcon, 
  Upload, 
  MapPin, 
  Check,
  Building2
} from 'lucide-react';

interface CreateEventModalProps {
  isOpen: boolean;
  onClose: () => void;
  cities: City[];
  categories: Category[];
  defaultCityId?: string;
  onEventCreated: () => void;
  myOrganizations?: OrganizationSummary[];
  initialOrganizationId?: string;
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
  myOrganizations = [],
  initialOrganizationId,
}) => {
  const [selectedOrgId, setSelectedOrgId] = useState<string | undefined>(initialOrganizationId);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [cityId, setCityId] = useState(defaultCityId || 'makhachkala');
  const [categoryId, setCategoryId] = useState('concerts');
  
  // Tomorrow at 19:00 default start date
  const tomorrow = new Date();
  tomorrow.setDate(tomorrow.getDate() + 1);
  tomorrow.setHours(19, 0, 0, 0);
  const defaultDateStr = tomorrow.toISOString().slice(0, 16);

  const [startAt, setStartAt] = useState(defaultDateStr);
  const [venueName, setVenueName] = useState('');
  const [address, setAddress] = useState('');
  const [latitude, setLatitude] = useState<number | undefined>(undefined);
  const [longitude, setLongitude] = useState<number | undefined>(undefined);
  
  // Address autocomplete state
  const [locationSuggestions, setLocationSuggestions] = useState<LocationSuggestion[]>([]);
  const [isLoadingSuggestions, setIsLoadingSuggestions] = useState(false);
  const [showSuggestions, setShowSuggestions] = useState(false);

  // Pricing state
  const [isFree, setIsFree] = useState(false);
  const [priceAmount, setPriceAmount] = useState<string>('500');
  
  // Cover image state
  const [coverImageUrl, setCoverImageUrl] = useState(PRESET_IMAGES[0].url);
  const [isUploadingImage, setIsUploadingImage] = useState(false);
  const [imageUploadError, setImageUploadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // Form submission state
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  // Synchronize cityId when defaultCityId changes
  useEffect(() => {
    if (defaultCityId) {
      setCityId(defaultCityId);
    }
  }, [defaultCityId]);

  // Debounced address search (starts at 2 chars, 300ms)
  useEffect(() => {
    const trimmed = (address || '').trim().replace(/\.+$/, '');
    if (trimmed.length < 2) {
      setLocationSuggestions([]);
      return;
    }

    const timer = setTimeout(async () => {
      try {
        setIsLoadingSuggestions(true);
        const results = await api.suggestLocations(trimmed, cityId);
        setLocationSuggestions(results);
        if (results.length > 0) {
          setShowSuggestions(true);
        }
      } catch (err) {
        console.warn('Location suggestion lookup error:', err);
      } finally {
        setIsLoadingSuggestions(false);
      }
    }, 300);

    return () => clearTimeout(timer);
  }, [address, cityId]);


  if (!isOpen) return null;

  const availableCities = cities && cities.length > 0 ? cities : DEFAULT_CITIES;
  const currentCity = availableCities.find((c) => c.id === cityId);
  const currency = currentCity?.currency || 'RUB';

  // Handle Cover Photo upload
  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Validate size (5MB max)
    if (file.size > 5 * 1024 * 1024) {
      setImageUploadError('Размер файла не должен превышать 5 МБ');
      return;
    }

    // Validate type
    const validTypes = ['image/jpeg', 'image/png', 'image/webp'];
    if (!validTypes.includes(file.type)) {
      setImageUploadError('Поддерживаются только форматы JPEG, PNG и WEBP');
      return;
    }

    try {
      setIsUploadingImage(true);
      setImageUploadError(null);
      const res = await api.uploadCoverImage(file);
      setCoverImageUrl(res.url);
      telegram.hapticSuccess();
    } catch (err: any) {
      setImageUploadError(err.message || 'Ошибка загрузки обложки');
      telegram.hapticError();
    } finally {
      setIsUploadingImage(false);
    }
  };

  const handleSelectSuggestion = (suggestion: LocationSuggestion) => {
    setAddress(suggestion.address || suggestion.display_name);
    if (!venueName.trim() && suggestion.title) {
      setVenueName(suggestion.title);
    } else if (!venueName.trim()) {
      const placeName = suggestion.display_name.split(',')[0].trim();
      setVenueName(placeName);
    }
    setLatitude(suggestion.latitude);
    setLongitude(suggestion.longitude);
    setShowSuggestions(false);
    setLocationSuggestions([]);
    telegram.hapticImpact('light');
  };


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
        latitude: latitude,
        longitude: longitude,
        price_amount: isFree ? undefined : Number(priceAmount) || 0,
        price_currency: isFree ? undefined : currency,
        cover_image_url: coverImageUrl.trim() || undefined,
        organization_id: selectedOrgId || undefined,
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
        onClick={(e) => {
          e.stopPropagation();
        }}
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
                Ваше событие успешно создано и отправлено администраторам. Как только его одобрят, оно станет доступно в афише Ivently.
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

            {/* Organizer selector */}
            {myOrganizations && myOrganizations.length > 0 && (
              <div className="space-y-1.5 p-3 rounded-2xl bg-[#141724] border border-white/5">
                <label className="text-gray-300 font-medium">Организатор (от чьего имени)</label>
                <div className="flex flex-wrap gap-2 pt-0.5">
                  <button
                    type="button"
                    onClick={() => setSelectedOrgId(undefined)}
                    className={`px-3 py-1.5 rounded-xl text-xs font-medium transition-all ${
                      !selectedOrgId
                        ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/30'
                        : 'bg-[#1A1E2E] text-gray-300 border border-white/5 hover:border-white/20'
                    }`}
                  >
                    Личный профиль
                  </button>
                  {myOrganizations.map((org) => (
                    <button
                      key={org.id}
                      type="button"
                      onClick={() => setSelectedOrgId(org.id)}
                      className={`px-3 py-1.5 rounded-xl text-xs font-medium transition-all flex items-center space-x-1.5 ${
                        selectedOrgId === org.id
                          ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/30'
                          : 'bg-[#1A1E2E] text-gray-300 border border-white/5 hover:border-white/20'
                      }`}
                    >
                      <Building2 className="w-3.5 h-3.5" />
                      <span>{org.name}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Title */}
            <div className="space-y-1">
              <label className="text-gray-300 font-medium">Название события *</label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="например: Концерт в горах или Джазовый вечер"
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
                  {availableCities.map((c) => (
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

            {/* Venue & Address with Autocomplete */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-gray-300 font-medium">Место / Площадка *</label>
                <input
                  type="text"
                  value={venueName}
                  onChange={(e) => setVenueName(e.target.value)}
                  placeholder="Дом культуры или Арена"
                  className="w-full px-3 py-2 rounded-xl bg-[#1A1E2E] border border-white/10 text-white focus:outline-none focus:border-indigo-500 placeholder-gray-500"
                  required
                />
              </div>

              <div className="space-y-1 relative">
                <label className="text-gray-300 font-medium flex items-center justify-between">
                  <span>Адрес</span>
                  {latitude && longitude && (
                    <span className="text-[10px] text-emerald-400 flex items-center space-x-1">
                      <Check className="w-2.5 h-2.5" />
                      <span>Координаты сохранены</span>
                    </span>
                  )}
                </label>
                <div className="relative">
                  <input
                    type="text"
                    value={address}
                    onChange={(e) => {
                      setAddress(e.target.value);
                      setShowSuggestions(true);
                    }}
                    onFocus={() => {
                      if (locationSuggestions.length > 0) {
                        setShowSuggestions(true);
                      }
                    }}
                    onClick={(e) => {
                      e.stopPropagation();
                      if (locationSuggestions.length > 0) {
                        setShowSuggestions(true);
                      }
                    }}
                    placeholder="Начните ввод адреса..."
                    className="w-full px-3 py-2 pr-7 rounded-xl bg-[#1A1E2E] border border-white/10 text-white focus:outline-none focus:border-indigo-500 placeholder-gray-500"
                  />
                  <div className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400">
                    {isLoadingSuggestions ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin text-indigo-400" />
                    ) : (
                      <MapPin className="w-3.5 h-3.5" />
                    )}
                  </div>
                </div>

                {/* Suggestions Dropdown */}
                {showSuggestions && locationSuggestions.length > 0 && (
                  <div 
                    className="absolute z-50 top-full left-0 right-0 mt-1 rounded-xl bg-[#181C2B] border border-white/10 shadow-2xl overflow-hidden max-h-48 overflow-y-auto custom-scrollbar"
                    onClick={(e) => e.stopPropagation()}
                  >
                    {locationSuggestions.map((item, idx) => (
                      <button
                        key={`${item.display_name}-${idx}`}
                        type="button"
                        onMouseDown={(e) => {
                          e.preventDefault();
                          handleSelectSuggestion(item);
                        }}
                        onClick={() => handleSelectSuggestion(item)}
                        className="w-full p-2.5 text-left border-b border-white/5 last:border-0 hover:bg-white/5 transition-colors flex items-start space-x-2"
                      >
                        <MapPin className="w-3.5 h-3.5 text-indigo-400 shrink-0 mt-0.5" />
                        <div className="flex-1 min-w-0">
                          <div className="font-semibold text-white text-xs truncate">
                            {item.title || item.display_name.split(',')[0]}
                          </div>
                          <div className="text-[10px] text-gray-400 line-clamp-1">
                            {item.address || item.display_name}
                          </div>
                        </div>
                      </button>
                    ))}
                  </div>
                )}
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

            {/* Cover Image Upload & Presets */}
            <div className="space-y-2 p-3 rounded-xl bg-[#171B2A] border border-white/5">
              <div className="flex items-center justify-between">
                <label className="text-gray-300 font-medium flex items-center space-x-1.5">
                  <ImageIcon className="w-3.5 h-3.5 text-indigo-400" />
                  <span>Обложка мероприятия</span>
                </label>

                {/* Upload Button */}
                <input
                  type="file"
                  ref={fileInputRef}
                  onChange={handleFileChange}
                  accept="image/jpeg,image/png,image/webp"
                  className="hidden"
                />
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={isUploadingImage}
                  className="flex items-center space-x-1 px-2.5 py-1 rounded-lg bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 border border-indigo-500/30 font-medium text-[11px] transition-colors disabled:opacity-50"
                >
                  {isUploadingImage ? (
                    <>
                      <Loader2 className="w-3 h-3 animate-spin" />
                      <span>Загрузка...</span>
                    </>
                  ) : (
                    <>
                      <Upload className="w-3 h-3" />
                      <span>Загрузить фото</span>
                    </>
                  )}
                </button>
              </div>

              {imageUploadError && (
                <div className="p-2 rounded-lg bg-red-500/10 text-red-300 text-[10px] flex items-center space-x-1">
                  <AlertCircle className="w-3 h-3 shrink-0" />
                  <span>{imageUploadError}</span>
                </div>
              )}

              {/* Cover Preview */}
              {coverImageUrl && (
                <div className="relative h-24 rounded-lg overflow-hidden border border-white/10">
                  <img
                    src={coverImageUrl}
                    alt="Предпросмотр обложки"
                    className="w-full h-full object-cover"
                    onError={(e) => {
                      (e.target as HTMLImageElement).src = PRESET_IMAGES[0].url;
                    }}
                  />
                  <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent flex items-end p-2">
                    <span className="text-[10px] text-white/80">Текущая обложка</span>
                  </div>
                </div>
              )}

              {/* Preset buttons */}
              <div className="space-y-1">
                <span className="text-[10px] text-gray-400">Или выберите готовую тему:</span>
                <div className="flex space-x-1.5 overflow-x-auto no-scrollbar pb-1">
                  {PRESET_IMAGES.map((preset) => (
                    <button
                      key={preset.label}
                      type="button"
                      onClick={() => setCoverImageUrl(preset.url)}
                      className={`px-2.5 py-1 rounded-lg text-[11px] whitespace-nowrap border transition-all ${
                        coverImageUrl === preset.url
                          ? 'bg-indigo-600/30 border-indigo-500 text-white font-semibold'
                          : 'bg-[#1A1E2E] border-white/5 text-gray-400 hover:text-white'
                      }`}
                    >
                      {preset.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Description */}
            <div className="space-y-1">
              <label className="text-gray-300 font-medium">Описание события *</label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={3}
                placeholder="Расскажите подробнее о программе, артистах или формате..."
                className="w-full px-3.5 py-2 rounded-xl bg-[#1A1E2E] border border-white/10 text-white focus:outline-none focus:border-indigo-500 placeholder-gray-500"
                required
              />
            </div>

            {/* Submit */}
            <button
              type="submit"
              disabled={isLoading || isUploadingImage}
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
