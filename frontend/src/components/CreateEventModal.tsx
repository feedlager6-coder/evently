import React, { useState, useEffect, useRef } from 'react';
import type { City, Category, EventCreatePayload, LocationSuggestion, OrganizationSummary, EventResponse } from '../types';
import { api } from '../services/api';
import { telegram } from '../services/telegram';
import { 
  X, 
  CheckCircle2, 
  AlertCircle, 
  Loader2, 
  MapPin, 
  Eye
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
  initialEvent?: EventResponse | null;
  onEventUpdated?: (ev: EventResponse) => void;
  onEventDeleted?: (eventId: string) => void;
  onSaveDraft?: (draftData: any) => void;
  initialDraft?: any;
}

const PRESET_IMAGES = [
  { label: 'Концерт', url: 'https://images.unsplash.com/photo-1514525253161-7a46d19cd819?w=800' },
  { label: 'Вечеринка', url: 'https://images.unsplash.com/photo-1492684223066-81342ee5ff30?w=800' },
  { label: 'Спорт', url: 'https://images.unsplash.com/photo-1461896836934-ffe607ba8211?w=800' },
  { label: 'Митап', url: 'https://images.unsplash.com/photo-1540575467063-178a50c2df87?w=800' },
  { label: 'Арт', url: 'https://images.unsplash.com/photo-1508997449629-303059a039c0?w=800' },
];

const STANDARD_CATEGORIES = [
  { id: 'concerts', name: 'Концерты' },
  { id: 'parties', name: 'Вечеринки' },
  { id: 'lectures', name: 'Лекции' },
  { id: 'exhibitions', name: 'Выставки' },
  { id: 'sport', name: 'Спорт' },
  { id: 'other', name: 'Другое' },
];

export const CreateEventModal: React.FC<CreateEventModalProps> = ({
  isOpen,
  onClose,
  cities,
  categories: _categories,
  defaultCityId,
  onEventCreated,
  myOrganizations: _myOrganizations = [],
  initialOrganizationId,
  initialEvent,
  onEventUpdated,
  onEventDeleted: _onEventDeleted,
  onSaveDraft,
  initialDraft,
}) => {
  const [selectedOrgId, setSelectedOrgId] = useState<string | undefined>(initialOrganizationId);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [cityId, setCityId] = useState(defaultCityId || (cities && cities[0]?.id) || 'makhachkala');
  const [categoryId, setCategoryId] = useState('concerts');
  
  // Tomorrow at 20:00 default start date
  const tomorrow = new Date();
  tomorrow.setDate(tomorrow.getDate() + 1);
  const pad = (n: number) => n.toString().padStart(2, '0');
  const defaultDateOnly = `${tomorrow.getFullYear()}-${pad(tomorrow.getMonth() + 1)}-${pad(tomorrow.getDate())}`;
  const defaultTimeOnly = '20:00';

  const [eventDate, setEventDate] = useState(defaultDateOnly);
  const [eventTime, setEventTime] = useState(defaultTimeOnly);
  const [venueName, setVenueName] = useState('');
  const [address, setAddress] = useState('');
  const [latitude, setLatitude] = useState<number | undefined>(undefined);
  const [longitude, setLongitude] = useState<number | undefined>(undefined);
  
  // Address autocomplete state
  const [locationSuggestions, setLocationSuggestions] = useState<LocationSuggestion[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);

  // Pricing state
  const [isFree, setIsFree] = useState(false);
  const [priceAmount, setPriceAmount] = useState<string>('1200');
  
  // Cover image state
  const [coverImageUrl, setCoverImageUrl] = useState<string>('');
  const [isUploadingImage, setIsUploadingImage] = useState(false);
  const [imageUploadError, setImageUploadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // Privacy / contact permission state
  const [allowEventContact, setAllowEventContact] = useState(false);

  // Form submission & state
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  // Live preview sheet
  const [isPreviewOpen, setIsPreviewOpen] = useState(false);
  const [draftNotice, setDraftNotice] = useState<string | null>(null);

  // Synchronize form when initialEvent, initialDraft or isOpen changes
  useEffect(() => {
    if (!isOpen) {
      setSuccess(false);
      setError(null);
      setIsPreviewOpen(false);
      setDraftNotice(null);
      return;
    }

    if (initialEvent) {
      setTitle(initialEvent.title || '');
      setDescription(initialEvent.description || '');
      setCityId(initialEvent.city_id || defaultCityId || 'makhachkala');
      setCategoryId(initialEvent.category_id || 'concerts');
      if (initialEvent.start_at) {
        try {
          const d = new Date(initialEvent.start_at);
          setEventDate(`${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`);
          setEventTime(`${pad(d.getHours())}:${pad(d.getMinutes())}`);
        } catch {
          setEventDate(defaultDateOnly);
          setEventTime(defaultTimeOnly);
        }
      }
      setVenueName(initialEvent.venue_name || '');
      setAddress(initialEvent.address || '');
      setLatitude(initialEvent.latitude);
      setLongitude(initialEvent.longitude);
      setIsFree(initialEvent.is_free ?? (initialEvent.price_amount == null || initialEvent.price_amount === 0));
      setPriceAmount(initialEvent.price_amount != null ? String(initialEvent.price_amount) : '1200');
      setCoverImageUrl(initialEvent.cover_image_url || PRESET_IMAGES[0].url);
      setSelectedOrgId(initialEvent.organization_id || undefined);
      setAllowEventContact(Boolean(initialEvent.allow_event_contact));
    } else if (initialDraft) {
      setTitle(initialDraft.title || '');
      setDescription(initialDraft.description || '');
      setCityId(initialDraft.city_id || defaultCityId || 'makhachkala');
      setCategoryId(initialDraft.category_id || 'concerts');
      setEventDate(initialDraft.eventDate || defaultDateOnly);
      setEventTime(initialDraft.eventTime || defaultTimeOnly);
      setVenueName(initialDraft.venue_name || '');
      setAddress(initialDraft.address || '');
      setIsFree(Boolean(initialDraft.is_free));
      setPriceAmount(initialDraft.price_amount != null ? String(initialDraft.price_amount) : '1200');
      setCoverImageUrl(initialDraft.cover_image_url || '');
      setSelectedOrgId(initialDraft.organization_id || initialOrganizationId);
    } else {
      setTitle('');
      setDescription('');
      setCityId(defaultCityId || 'makhachkala');
      setCategoryId('concerts');
      setEventDate(defaultDateOnly);
      setEventTime(defaultTimeOnly);
      setVenueName('');
      setAddress('');
      setLatitude(undefined);
      setLongitude(undefined);
      setIsFree(false);
      setPriceAmount('1200');
      setCoverImageUrl('');
      setSelectedOrgId(initialOrganizationId);
      setAllowEventContact(false);
    }
  }, [isOpen, initialEvent, initialDraft, defaultCityId, initialOrganizationId]);

  // Debounced address search (starts at 2 chars, 300ms)
  useEffect(() => {
    const trimmed = (venueName || address || '').trim().replace(/\.+$/, '');
    if (trimmed.length < 2) {
      setLocationSuggestions([]);
      return;
    }

    const timer = setTimeout(async () => {
      try {
        const results = await api.suggestLocations(trimmed, cityId);
        setLocationSuggestions(results);
        if (results.length > 0) {
          setShowSuggestions(true);
        }
      } catch (err) {
        console.warn('Location suggestion lookup error:', err);
      }
    }, 300);

    return () => clearTimeout(timer);
  }, [venueName, address, cityId]);

  if (!isOpen) return null;

  // Calculate dynamic progress
  let filledPoints = 1; // base 33% (step 1 info)
  if (title.trim()) filledPoints += 1;
  if (venueName.trim() || address.trim()) filledPoints += 1;
  const progressPercent = Math.min(100, Math.round((filledPoints / 3) * 100));

  const handleSaveDraft = () => {
    telegram.hapticImpact('medium');
    const draftData = {
      id: initialEvent?.id || `draft-${Date.now()}`,
      title: title.trim() || 'Новое событие (Черновик)',
      description: description.trim(),
      category_id: categoryId,
      city_id: cityId,
      eventDate,
      eventTime,
      start_at: `${eventDate}T${eventTime}:00`,
      venue_name: venueName.trim() || 'Локация не выбрана',
      address: address.trim(),
      is_free: isFree,
      price_amount: isFree ? 0 : Number(priceAmount) || 0,
      cover_image_url: coverImageUrl,
      organization_id: selectedOrgId,
      status: 'draft',
      completionRate: progressPercent,
      updated_at: new Date().toISOString(),
    };

    try {
      const existingDraftsStr = localStorage.getItem('ivently_event_drafts');
      const existingDrafts: any[] = existingDraftsStr ? JSON.parse(existingDraftsStr) : [];
      const updatedDrafts = [draftData, ...existingDrafts.filter((d: any) => d.id !== draftData.id)];
      localStorage.setItem('ivently_event_drafts', JSON.stringify(updatedDrafts));
    } catch (e) {
      console.warn('Failed to save draft to localStorage:', e);
    }

    if (onSaveDraft) {
      onSaveDraft(draftData);
    }

    setDraftNotice('Черновик успешно сохранён!');
    telegram.hapticSuccess();
    setTimeout(() => {
      onClose();
    }, 600);
  };

  // Handle Cover Photo upload
  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (file.size > 10 * 1024 * 1024) {
      setImageUploadError('Размер файла не должен превышать 10 МБ');
      return;
    }

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
      telegram.hapticNotification('error');
    } finally {
      setIsUploadingImage(false);
    }
  };

  const handleSelectSuggestion = (suggestion: LocationSuggestion) => {
    setAddress(suggestion.address || suggestion.display_name);
    setVenueName(suggestion.title || suggestion.display_name.split(',')[0].trim());
    setLatitude(suggestion.latitude);
    setLongitude(suggestion.longitude);
    setShowSuggestions(false);
    setLocationSuggestions([]);
    telegram.hapticImpact('light');
  };

  const handleSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!title.trim()) {
      setError('Укажите название события');
      telegram.hapticNotification('error');
      return;
    }
    if (!venueName.trim() && !address.trim()) {
      setError('Укажите площадку или адрес события в Махачкале');
      telegram.hapticNotification('error');
      return;
    }

    try {
      setIsLoading(true);
      setError(null);
      telegram.hapticImpact('medium');

      const fullStartAt = `${eventDate}T${eventTime}:00`;
      const payload: EventCreatePayload = {
        title: title.trim(),
        description: description.trim() || 'Без описания',
        city_id: cityId || 'makhachkala',
        category_id: categoryId,
        start_at: new Date(fullStartAt).toISOString(),
        venue_name: venueName.trim() || address.trim() || 'Махачкала',
        address: address.trim() || venueName.trim(),
        latitude: latitude,
        longitude: longitude,
        price_amount: isFree ? undefined : Number(priceAmount) || 0,
        price_currency: 'RUB',
        cover_image_url: coverImageUrl.trim() || PRESET_IMAGES[0].url,
        organization_id: selectedOrgId || undefined,
        allow_event_contact: !selectedOrgId ? allowEventContact : false,
      };

      if (initialEvent) {
        const updated = await api.updateEvent(initialEvent.id, payload);
        telegram.hapticSuccess();
        setSuccess(true);
        if (onEventUpdated) {
          onEventUpdated(updated);
        }
      } else {
        await api.createEvent(payload);
        telegram.hapticSuccess();
        setSuccess(true);
        onEventCreated();
      }
    } catch (err: any) {
      setError(err.message || 'Ошибка отправки события на модерацию');
      telegram.hapticNotification('error');
    } finally {
      setIsLoading(false);
    }
  };

  const selectedCategoryName = STANDARD_CATEGORIES.find((c) => c.id === categoryId)?.name || 'Событие';

  return (
    <div className="fixed inset-0 z-[60] bg-[#0d0d0f] flex flex-col overflow-y-auto">
      {/* Top Navigation Header matching Screen 2 */}
      <header className="pt-4 px-4 pb-3 flex items-center justify-between glass-header sticky top-0 z-30">
        <div className="flex items-center gap-3">
          <button 
            type="button"
            onClick={() => {
              telegram.hapticImpact('light');
              onClose();
            }}
            className="w-9 h-9 rounded-full bg-white/5 hover:bg-white/10 active:scale-95 flex items-center justify-center transition-all border border-white/5 text-neutral-300"
            aria-label="Закрыть"
          >
            <X className="w-5 h-5" />
          </button>
          <div>
            <h1 className="text-base font-bold text-white tracking-tight">
              {initialEvent ? 'Редактирование' : 'Новое событие'}
            </h1>
            <p className="text-[11px] text-neutral-400">
              Основная информация и билеты
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={handleSaveDraft}
          className="text-xs font-semibold text-neutral-400 hover:text-white px-2.5 py-1 rounded-lg hover:bg-white/5 transition-colors active:scale-95"
        >
          Черновик
        </button>
      </header>

      {/* Progress Indicator matching Screen 2 */}
      <div className="w-full h-1 bg-white/5">
        <div 
          className="h-full bg-emerald-400 transition-all duration-300"
          style={{ width: `${progressPercent}%` }}
        />
      </div>

      {draftNotice && (
        <div className="mx-4 mt-3 p-3 rounded-2xl bg-emerald-500/15 border border-emerald-500/30 text-emerald-300 text-xs flex items-center space-x-2 animate-fade-in">
          <CheckCircle2 className="w-4 h-4 shrink-0" />
          <span>{draftNotice}</span>
        </div>
      )}

      {/* Success View */}
      {success ? (
        <div className="flex-1 flex flex-col items-center justify-center px-6 py-12 text-center space-y-5">
          <div className="w-20 h-20 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 flex items-center justify-center mx-auto shadow-[0_0_30px_rgba(16,185,129,0.3)]">
            <CheckCircle2 className="w-10 h-10" />
          </div>
          <div className="space-y-2">
            <h2 className="text-xl font-bold text-white tracking-tight">
              {initialEvent ? 'Изменения сохранены!' : 'Отправлено на модерацию!'}
            </h2>
            <p className="text-xs text-neutral-400 max-w-xs mx-auto leading-relaxed">
              {initialEvent
                ? 'Информация о событии успешно обновлена.'
                : 'Ваше событие успешно создано и отправлено модераторам Ivently. Обычно проверка занимает до 20 минут.'}
            </p>
          </div>
          <button
            type="button"
            onClick={() => {
              telegram.hapticImpact('light');
              onClose();
            }}
            className="w-full max-w-xs py-3.5 rounded-2xl bg-white hover:bg-neutral-200 text-black font-bold text-sm transition-all active:scale-[0.98] shadow-lg"
          >
            Вернуться в кабинет
          </button>
        </div>
      ) : (
        /* Form Body matching Screen 2 */
        <main className="flex-1 px-4 py-4 space-y-4 pb-28">
          {error && (
            <div className="p-3.5 rounded-2xl bg-red-500/10 border border-red-500/20 text-red-300 flex items-center space-x-2 text-xs">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Section 1: Обложка события matching Screen 2 */}
          <section className="form-section p-4 space-y-3">
            <label className="block text-xs font-bold uppercase tracking-wider text-neutral-400">
              Обложка афиши *
            </label>
            
            {coverImageUrl ? (
              <div className="relative rounded-2xl overflow-hidden border border-white/10 group bg-neutral-900 aspect-video max-h-48">
                <img 
                  src={coverImageUrl} 
                  alt="Обложка афиши" 
                  className="w-full h-full object-cover"
                />
                <div className="absolute inset-0 bg-black/40 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    className="px-3.5 py-1.5 rounded-xl bg-white text-black font-semibold text-xs shadow-lg active:scale-95"
                  >
                    Заменить обложку
                  </button>
                </div>
              </div>
            ) : null}

            <div 
              onClick={() => fileInputRef.current?.click()}
              className="border-2 border-dashed border-white/15 hover:border-white/30 rounded-2xl p-6 flex flex-col items-center justify-center text-center cursor-pointer transition-all bg-white/[0.02]"
            >
              <div className="w-12 h-12 rounded-full bg-white/5 flex items-center justify-center text-neutral-300 mb-2">
                {isUploadingImage ? (
                  <Loader2 className="w-6 h-6 animate-spin text-emerald-400" />
                ) : (
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"/>
                  </svg>
                )}
              </div>
              <span className="text-xs font-semibold text-white">
                {isUploadingImage ? 'Загрузка...' : 'Загрузить изображение'}
              </span>
              <span className="text-[11px] text-neutral-500 mt-0.5">
                JPG или PNG до 10 МБ (16:9 или 4:3)
              </span>
              <input 
                ref={fileInputRef}
                type="file" 
                accept="image/jpeg,image/png,image/webp" 
                onChange={handleFileChange}
                className="hidden" 
              />
            </div>

            {imageUploadError && (
              <p className="text-xs text-red-400">{imageUploadError}</p>
            )}

            {/* Quick Preset Selector */}
            <div className="flex gap-2 overflow-x-auto no-scrollbar pt-1">
              {PRESET_IMAGES.map((img) => (
                <button
                  key={img.label}
                  type="button"
                  onClick={() => {
                    setCoverImageUrl(img.url);
                    telegram.hapticImpact('light');
                  }}
                  className={`px-2.5 py-1 rounded-lg text-[11px] shrink-0 border transition-all ${
                    coverImageUrl === img.url
                      ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40 font-semibold'
                      : 'bg-white/5 text-neutral-400 border-white/5 hover:text-white'
                  }`}
                >
                  {img.label}
                </button>
              ))}
            </div>
          </section>

          {/* Section 2: Название и категория matching Screen 2 */}
          <section className="form-section p-4 space-y-3.5">
            <div>
              <label className="block text-xs font-semibold text-neutral-300 mb-1.5">
                Название события *
              </label>
              <input 
                type="text" 
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Например: Акустический концерт на закате" 
                className="input-field w-full px-3.5 py-2.5 rounded-xl text-sm placeholder-neutral-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-neutral-300 mb-1.5">
                Категория *
              </label>
              <div className="grid grid-cols-3 gap-2 text-xs">
                {STANDARD_CATEGORIES.map((cat) => {
                  const isSelected = categoryId === cat.id;
                  return (
                    <button
                      key={cat.id}
                      type="button"
                      onClick={() => {
                        setCategoryId(cat.id);
                        telegram.hapticImpact('light');
                      }}
                      className={`py-2 px-2.5 rounded-xl font-medium text-center transition-all ${
                        isSelected 
                          ? 'bg-white text-black font-bold shadow-md' 
                          : 'bg-white/5 text-neutral-300 border border-white/10 hover:bg-white/10'
                      }`}
                    >
                      {cat.name}
                    </button>
                  );
                })}
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-neutral-300 mb-1.5">
                Описание события
              </label>
              <textarea 
                rows={3} 
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Расскажите о программе, лайн-апе, правилах входа..." 
                className="input-field w-full px-3.5 py-2.5 rounded-xl text-sm placeholder-neutral-500 resize-none"
              />
            </div>
          </section>

          {/* Section 3: Время и Локация matching Screen 2 */}
          <section className="form-section p-4 space-y-3.5">
            <label className="block text-xs font-bold uppercase tracking-wider text-neutral-400">
              Дата, время и место
            </label>
            
            <div className="grid grid-cols-2 gap-2.5">
              <div>
                <label className="block text-[11px] text-neutral-400 mb-1">
                  Дата события *
                </label>
                <input 
                  type="date" 
                  value={eventDate}
                  onChange={(e) => setEventDate(e.target.value)}
                  className="input-field w-full px-3 py-2 rounded-xl text-xs text-white"
                />
              </div>
              <div>
                <label className="block text-[11px] text-neutral-400 mb-1">
                  Начало *
                </label>
                <input 
                  type="time" 
                  value={eventTime}
                  onChange={(e) => setEventTime(e.target.value)}
                  className="input-field w-full px-3 py-2 rounded-xl text-xs text-white"
                />
              </div>
            </div>

            <div className="relative">
              <label className="block text-xs font-semibold text-neutral-300 mb-1.5">
                Площадка в Махачкале *
              </label>
              <input 
                type="text" 
                value={venueName}
                onChange={(e) => {
                  setVenueName(e.target.value);
                  setShowSuggestions(true);
                }}
                onFocus={() => setShowSuggestions(locationSuggestions.length > 0)}
                placeholder="Клуб «Атмосфера», или точный адрес" 
                className="input-field w-full px-3.5 py-2.5 rounded-xl text-sm placeholder-neutral-500"
              />
              
              {/* Autocomplete suggestions dropdown */}
              {showSuggestions && locationSuggestions.length > 0 && (
                <div className="absolute left-0 right-0 top-full mt-1.5 bg-[#17171a] border border-white/10 rounded-2xl p-2 z-50 shadow-2xl max-h-48 overflow-y-auto space-y-1">
                  {locationSuggestions.map((sug, idx) => (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => handleSelectSuggestion(sug)}
                      className="w-full text-left p-2.5 rounded-xl hover:bg-white/5 flex items-start space-x-2 text-xs text-neutral-200 transition-colors"
                    >
                      <MapPin className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                      <div>
                        <div className="font-semibold text-white">{sug.title || sug.display_name.split(',')[0]}</div>
                        <div className="text-[11px] text-neutral-400 line-clamp-1">{sug.address || sug.display_name}</div>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </section>

          {/* Section 4: Вход и Билеты matching Screen 2 */}
          <section className="form-section p-4 space-y-3">
            <label className="block text-xs font-bold uppercase tracking-wider text-neutral-400">
              Условия входа
            </label>

            <div className="flex gap-2">
              <label 
                onClick={() => setIsFree(false)}
                className={`flex-1 p-3 rounded-xl border flex items-center justify-between cursor-pointer transition-all ${
                  !isFree 
                    ? 'border-white/20 bg-white/5' 
                    : 'border-white/5 bg-white/[0.02]'
                }`}
              >
                <div>
                  <span className="text-xs font-bold text-white block">Платный вход</span>
                  <span className="text-[11px] text-neutral-400">Фиксированная цена</span>
                </div>
                <input 
                  type="radio" 
                  name="price_type" 
                  checked={!isFree} 
                  onChange={() => setIsFree(false)}
                  className="accent-emerald-400"
                />
              </label>

              <label 
                onClick={() => setIsFree(true)}
                className={`flex-1 p-3 rounded-xl border flex items-center justify-between cursor-pointer transition-all ${
                  isFree 
                    ? 'border-white/20 bg-white/5' 
                    : 'border-white/5 bg-white/[0.02]'
                }`}
              >
                <div>
                  <span className="text-xs font-bold text-white block">Бесплатно</span>
                  <span className="text-[11px] text-neutral-400">Свободный вход</span>
                </div>
                <input 
                  type="radio" 
                  name="price_type" 
                  checked={isFree} 
                  onChange={() => setIsFree(true)}
                  className="accent-emerald-400"
                />
              </label>
            </div>

            {!isFree && (
              <div>
                <label className="block text-[11px] text-neutral-400 mb-1">
                  Стоимость билета (₽)
                </label>
                <input 
                  type="number" 
                  value={priceAmount}
                  onChange={(e) => setPriceAmount(e.target.value)}
                  placeholder="1 200" 
                  className="input-field w-full px-3.5 py-2 rounded-xl text-sm text-white"
                />
              </div>
            )}
          </section>

          {/* Moderation notice banner matching Screen 2 */}
          <div className="p-3.5 rounded-2xl bg-amber-500/10 border border-amber-500/20 flex gap-2.5 items-start">
            <svg className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
            </svg>
            <p className="text-xs text-neutral-300 leading-relaxed">
              После отправки событие попадает на проверку модераторами Ivently. Обычно публикация занимает <span className="text-white font-medium">до 20 минут</span>.
            </p>
          </div>

          {/* Action Buttons matching Screen 2 */}
          <div className="pt-2 space-y-2">
            <button 
              type="button"
              disabled={isLoading}
              onClick={() => handleSubmit()}
              className="w-full py-3.5 rounded-2xl bg-emerald-500 hover:bg-emerald-400 text-black font-bold text-sm transition-all active:scale-[0.98] shadow-lg flex items-center justify-center space-x-2"
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin text-black" />
                  <span>Отправка на модерацию...</span>
                </>
              ) : (
                <span>Отправить на модерацию</span>
              )}
            </button>
            
            <button 
              type="button"
              onClick={() => {
                telegram.hapticImpact('light');
                setIsPreviewOpen(true);
              }}
              className="w-full py-3 rounded-2xl bg-white/5 hover:bg-white/10 text-neutral-300 font-medium text-xs transition-all border border-white/5 active:scale-98"
            >
              Предпросмотр афиши
            </button>
          </div>
        </main>
      )}

      {/* Live Poster Preview Modal */}
      {isPreviewOpen && (
        <div className="fixed inset-0 z-[70] bg-black/90 backdrop-blur-xl flex flex-col p-4 animate-fade-in overflow-y-auto">
          <div className="flex items-center justify-between pb-3 border-b border-white/10">
            <div className="flex items-center space-x-2 text-white">
              <Eye className="w-4 h-4 text-emerald-400" />
              <span className="font-bold text-sm">Предпросмотр в афише</span>
            </div>
            <button
              type="button"
              onClick={() => setIsPreviewOpen(false)}
              className="p-1.5 rounded-full bg-white/5 text-neutral-400 hover:text-white"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          <div className="py-6 max-w-sm mx-auto w-full space-y-4">
            <div className="rounded-3xl overflow-hidden bg-[#141417] border border-white/10 shadow-2xl space-y-3 pb-4">
              <div className="relative aspect-video w-full bg-neutral-900">
                <img 
                  src={coverImageUrl} 
                  alt={title || 'Превью'} 
                  className="w-full h-full object-cover"
                />
                <div className="absolute top-3 left-3 px-2.5 py-1 rounded-full bg-black/60 backdrop-blur-md text-[10px] font-semibold text-white border border-white/10">
                  {selectedCategoryName}
                </div>
                <div className="absolute bottom-3 right-3 px-2.5 py-1 rounded-full bg-emerald-500/90 text-black font-bold text-xs shadow-md">
                  {isFree ? 'Бесплатно' : `${priceAmount || '1 200'} ₽`}
                </div>
              </div>

              <div className="px-4 space-y-2">
                <div className="text-[11px] text-emerald-400 font-semibold">
                  {eventDate} • {eventTime}
                </div>
                <h3 className="text-base font-bold text-white tracking-tight">
                  {title || 'Название события не указано'}
                </h3>
                <p className="text-xs text-neutral-400 flex items-center space-x-1">
                  <MapPin className="w-3.5 h-3.5 shrink-0 text-neutral-500" />
                  <span>{venueName || 'Махачкала, площадка не указана'}</span>
                </p>
                {description && (
                  <p className="text-xs text-neutral-300 pt-1 line-clamp-3 leading-relaxed border-t border-white/5">
                    {description}
                  </p>
                )}
              </div>
            </div>

            <div className="space-y-2 pt-2">
              <button
                type="button"
                onClick={() => {
                  setIsPreviewOpen(false);
                  handleSubmit();
                }}
                className="w-full py-3.5 rounded-2xl bg-emerald-500 hover:bg-emerald-400 text-black font-bold text-sm shadow-lg active:scale-98"
              >
                Отправить на модерацию
              </button>
              <button
                type="button"
                onClick={() => setIsPreviewOpen(false)}
                className="w-full py-3 rounded-2xl bg-white/5 hover:bg-white/10 text-neutral-300 font-medium text-xs border border-white/5"
              >
                ← Вернуться к редактированию
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
