import React, { useState, useEffect, useRef } from 'react';
import type {
  City,
  OrganizationResponse,
  OrganizationCreatePayload,
  OrganizationUpdatePayload,
  LocationSuggestion,
} from '../types';
import { ORGANIZATION_CATEGORIES } from '../types';
import { api, DEFAULT_CITIES } from '../services/api';
import { telegram } from '../services/telegram';
import {
  X,
  Building2,
  MapPin,
  Upload,
  Globe,
  Loader2,
  AlertCircle,
  CheckCircle2,
} from 'lucide-react';

interface CreateOrganizationModalProps {
  isOpen: boolean;
  onClose: () => void;
  cities: City[];
  defaultCityId?: string;
  initialData?: OrganizationResponse | null;
  onSaved: (org: OrganizationResponse) => void;
}

export const CreateOrganizationModal: React.FC<CreateOrganizationModalProps> = ({
  isOpen,
  onClose,
  cities,
  defaultCityId,
  initialData,
  onSaved,
}) => {
  const isEditing = Boolean(initialData?.id);

  const [name, setName] = useState('');
  const [category, setCategory] = useState<string>(ORGANIZATION_CATEGORIES[0]);
  const [description, setDescription] = useState('');
  const [cityId, setCityId] = useState(defaultCityId || 'makhachkala');
  const [address, setAddress] = useState('');
  const [latitude, setLatitude] = useState<number | undefined>(undefined);
  const [longitude, setLongitude] = useState<number | undefined>(undefined);
  const [avatarUrl, setAvatarUrl] = useState('');
  const [website, setWebsite] = useState('');
  const [socialLink, setSocialLink] = useState('');

  // Address autocomplete state
  const [locationSuggestions, setLocationSuggestions] = useState<LocationSuggestion[]>([]);
  const [isLoadingSuggestions, setIsLoadingSuggestions] = useState(false);
  const [showSuggestions, setShowSuggestions] = useState(false);

  // Avatar upload state
  const [isUploadingAvatar, setIsUploadingAvatar] = useState(false);
  const [avatarUploadError, setAvatarUploadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // Form submission state
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Initialize or reset form
  useEffect(() => {
    if (initialData) {
      setName(initialData.name || '');
      setCategory(initialData.category || ORGANIZATION_CATEGORIES[0]);
      setDescription(initialData.description || '');
      setCityId(initialData.city_id || defaultCityId || 'makhachkala');
      setAddress(initialData.address || '');
      setLatitude(initialData.latitude);
      setLongitude(initialData.longitude);
      setAvatarUrl(initialData.avatar_url || '');
      setWebsite(initialData.website || '');
      setSocialLink(initialData.social_link || '');
    } else {
      setName('');
      setCategory(ORGANIZATION_CATEGORIES[0]);
      setDescription('');
      setCityId(defaultCityId || 'makhachkala');
      setAddress('');
      setLatitude(undefined);
      setLongitude(undefined);
      setAvatarUrl('');
      setWebsite('');
      setSocialLink('');
    }
    setError(null);
    setShowSuggestions(false);
  }, [initialData, defaultCityId, isOpen]);

  // Debounced address suggestion lookup
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

  const handleSelectSuggestion = (suggestion: LocationSuggestion) => {
    setAddress(suggestion.address || suggestion.display_name);
    setLatitude(suggestion.latitude);
    setLongitude(suggestion.longitude);
    setShowSuggestions(false);
    setLocationSuggestions([]);
    telegram.hapticImpact('light');
  };

  const handleAvatarFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (file.size > 5 * 1024 * 1024) {
      setAvatarUploadError('Размер файла не должен превышать 5 МБ');
      return;
    }

    const validTypes = ['image/jpeg', 'image/png', 'image/webp'];
    if (!validTypes.includes(file.type)) {
      setAvatarUploadError('Поддерживаются форматы JPEG, PNG, WEBP');
      return;
    }

    try {
      setIsUploadingAvatar(true);
      setAvatarUploadError(null);
      const res = await api.uploadCoverImage(file);
      setAvatarUrl(res.url);
      telegram.hapticSuccess();
    } catch (err: any) {
      setAvatarUploadError(err.message || 'Ошибка загрузки аватара');
      telegram.hapticError();
    } finally {
      setIsUploadingAvatar(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setError('Введите название организации');
      return;
    }

    try {
      setIsLoading(true);
      setError(null);
      telegram.hapticImpact('medium');

      let savedOrg: OrganizationResponse;

      if (isEditing && initialData?.id) {
        const payload: OrganizationUpdatePayload = {
          name: name.trim(),
          category,
          description: description.trim() || undefined,
          city_id: cityId || undefined,
          address: address.trim() || undefined,
          latitude,
          longitude,
          avatar_url: avatarUrl.trim() || undefined,
          website: website.trim() || undefined,
          social_link: socialLink.trim() || undefined,
        };
        savedOrg = await api.updateOrganization(initialData.id, payload);
      } else {
        const payload: OrganizationCreatePayload = {
          name: name.trim(),
          category,
          description: description.trim() || undefined,
          city_id: cityId || undefined,
          address: address.trim() || undefined,
          latitude,
          longitude,
          avatar_url: avatarUrl.trim() || undefined,
          website: website.trim() || undefined,
          social_link: socialLink.trim() || undefined,
        };
        savedOrg = await api.createOrganization(payload);
      }

      telegram.hapticSuccess();
      onSaved(savedOrg);
      onClose();
    } catch (err: any) {
      console.error('Failed to save organization:', err);
      setError(err.message || 'Ошибка сохранения организации');
      telegram.hapticError();
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex flex-col justify-end sm:justify-center items-center bg-black/80 backdrop-blur-sm backdrop-fade-in p-0 sm:p-4">
      <div
        className="w-full max-w-lg bg-[#0F121C] sm:rounded-3xl rounded-t-[28px] border border-white/10 overflow-hidden shadow-2xl flex flex-col max-h-[92vh] sheet-slide-up"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="p-4 flex items-center justify-between border-b border-white/5 bg-[#141724]/70 backdrop-blur-md shrink-0">
          <button
            onClick={onClose}
            className="p-2 rounded-full bg-white/5 hover:bg-white/10 text-white transition-colors btn-press"
          >
            <X className="w-5 h-5" />
          </button>
          <div className="text-sm font-bold text-white flex items-center space-x-2">
            <Building2 className="w-4 h-4 text-indigo-400" />
            <span>{isEditing ? 'Редактировать организацию' : 'Создать организацию'}</span>
          </div>
          <div className="w-9" />
        </div>

        {/* Scrollable Form Body */}
        <form onSubmit={handleSubmit} className="p-5 overflow-y-auto space-y-4 no-scrollbar flex-1">
          {error && (
            <div className="p-3.5 rounded-2xl bg-red-500/10 border border-red-500/20 text-red-300 text-xs flex items-center space-x-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Avatar Upload */}
          <div className="flex flex-col items-center space-y-2 py-1">
            <div
              onClick={() => fileInputRef.current?.click()}
              className="relative w-20 h-20 rounded-2xl overflow-hidden bg-[#171B29] border-2 border-dashed border-indigo-500/40 hover:border-indigo-400 cursor-pointer flex items-center justify-center group transition-all"
            >
              {avatarUrl ? (
                <img src={avatarUrl} alt="Avatar" className="w-full h-full object-cover" />
              ) : (
                <div className="flex flex-col items-center space-y-1 text-gray-400 group-hover:text-indigo-300">
                  <Upload className="w-5 h-5" />
                  <span className="text-[10px]">Логотип</span>
                </div>
              )}
              {isUploadingAvatar && (
                <div className="absolute inset-0 bg-black/60 flex items-center justify-center">
                  <Loader2 className="w-5 h-5 text-indigo-400 animate-spin" />
                </div>
              )}
            </div>
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleAvatarFileChange}
              accept="image/jpeg,image/png,image/webp"
              className="hidden"
            />
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="text-xs text-indigo-400 hover:text-indigo-300 font-medium"
            >
              {avatarUrl ? 'Изменить логотип' : '+ Загрузить логотип / фото'}
            </button>
            {avatarUploadError && (
              <span className="text-[11px] text-red-400">{avatarUploadError}</span>
            )}
          </div>

          {/* Name */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-gray-300">
              Название организации <span className="text-red-400">*</span>
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Например: Coffee Lab, Арт-пространство 05, Dance Studio"
              className="w-full px-3.5 py-2.5 rounded-xl bg-[#171B29] border border-white/10 text-white text-xs placeholder:text-gray-500 focus:outline-none focus:border-indigo-500 transition-colors"
              required
            />
          </div>

          {/* Category */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-gray-300">
              Категория <span className="text-red-400">*</span>
            </label>
            <div className="flex flex-wrap gap-1.5">
              {ORGANIZATION_CATEGORIES.map((cat) => (
                <button
                  key={cat}
                  type="button"
                  onClick={() => setCategory(cat)}
                  className={`px-3 py-1.5 rounded-xl text-xs font-medium transition-all ${
                    category === cat
                      ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/30'
                      : 'bg-[#171B29] text-gray-300 border border-white/5 hover:border-white/20'
                  }`}
                >
                  {cat}
                </button>
              ))}
            </div>
          </div>

          {/* City */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-gray-300">Город</label>
            <select
              value={cityId}
              onChange={(e) => setCityId(e.target.value)}
              className="w-full px-3.5 py-2.5 rounded-xl bg-[#171B29] border border-white/10 text-white text-xs focus:outline-none focus:border-indigo-500 transition-colors"
            >
              {availableCities.map((c) => (
                <option key={c.id} value={c.id} className="bg-[#141724] text-white">
                  {c.name}
                </option>
              ))}
            </select>
          </div>

          {/* Address with suggestions */}
          <div className="space-y-1.5 relative">
            <label className="text-xs font-semibold text-gray-300">Адрес / Локация</label>
            <div className="relative">
              <input
                type="text"
                value={address}
                onChange={(e) => setAddress(e.target.value)}
                onFocus={() => locationSuggestions.length > 0 && setShowSuggestions(true)}
                placeholder="Улица, дом (например, ул. Ленина, 12)"
                className="w-full px-3.5 py-2.5 rounded-xl bg-[#171B29] border border-white/10 text-white text-xs placeholder:text-gray-500 focus:outline-none focus:border-indigo-500 transition-colors pr-8"
              />
              {isLoadingSuggestions ? (
                <Loader2 className="w-4 h-4 text-indigo-400 animate-spin absolute right-2.5 top-1/2 -translate-y-1/2" />
              ) : (
                <MapPin className="w-4 h-4 text-gray-400 absolute right-2.5 top-1/2 -translate-y-1/2" />
              )}
            </div>

            {/* Suggestions dropdown */}
            {showSuggestions && locationSuggestions.length > 0 && (
              <div className="absolute left-0 right-0 z-20 mt-1 max-h-48 overflow-y-auto rounded-xl bg-[#171B29] border border-white/15 shadow-xl divide-y divide-white/5">
                {locationSuggestions.map((sug, idx) => (
                  <div
                    key={idx}
                    onClick={() => handleSelectSuggestion(sug)}
                    className="p-2.5 hover:bg-white/5 cursor-pointer text-xs text-gray-200 transition-colors flex items-start space-x-2"
                  >
                    <MapPin className="w-3.5 h-3.5 text-indigo-400 mt-0.5 shrink-0" />
                    <div>
                      {sug.title && <div className="font-semibold text-white">{sug.title}</div>}
                      <div className="text-[11px] text-gray-400">{sug.display_name}</div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Description */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-gray-300">Описание / О нас</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              placeholder="Расскажите о вашей площадке, миссии, формате мероприятий..."
              className="w-full px-3.5 py-2.5 rounded-xl bg-[#171B29] border border-white/10 text-white text-xs placeholder:text-gray-500 focus:outline-none focus:border-indigo-500 transition-colors resize-none"
            />
          </div>

          {/* Links */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-gray-300">Сайт</label>
              <div className="relative">
                <input
                  type="url"
                  value={website}
                  onChange={(e) => setWebsite(e.target.value)}
                  placeholder="https://mysite.ru"
                  className="w-full px-3.5 py-2.5 rounded-xl bg-[#171B29] border border-white/10 text-white text-xs placeholder:text-gray-500 focus:outline-none focus:border-indigo-500 transition-colors"
                />
                <Globe className="w-4 h-4 text-gray-500 absolute right-2.5 top-1/2 -translate-y-1/2" />
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-gray-300">Канал / соцсеть</label>
              <input
                type="text"
                value={socialLink}
                onChange={(e) => setSocialLink(e.target.value)}
                placeholder="https://t.me/mychannel"
                className="w-full px-3.5 py-2.5 rounded-xl bg-[#171B29] border border-white/10 text-white text-xs placeholder:text-gray-500 focus:outline-none focus:border-indigo-500 transition-colors"
              />
            </div>
          </div>

          {/* Submit Action */}
          <div className="pt-2">
            <button
              type="submit"
              disabled={isLoading || isUploadingAvatar}
              className="w-full py-3.5 px-6 rounded-2xl bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs flex items-center justify-center space-x-2 transition-all shadow-xl shadow-indigo-600/30 btn-press disabled:opacity-70"
            >
              {isLoading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <>
                  <CheckCircle2 className="w-4 h-4" />
                  <span>{isEditing ? 'Сохранить изменения' : 'Создать организацию'}</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
