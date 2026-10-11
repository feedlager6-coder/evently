import React, { useState, useEffect } from 'react';
import { Compass } from 'lucide-react';

const DEFAULT_EVENT_FALLBACK = 'https://images.unsplash.com/photo-1501281668745-f7f57925c3b4?w=800';

interface SafeImageProps {
  src?: string | null;
  alt: string;
  fallbackSrc?: string;
  className?: string;
  loading?: 'lazy' | 'eager';
}

export const SafeImage: React.FC<SafeImageProps> = ({
  src,
  alt,
  fallbackSrc = DEFAULT_EVENT_FALLBACK,
  className = 'w-full h-full object-cover',
  loading = 'eager',
}) => {
  const [currentSrc, setCurrentSrc] = useState<string>(src || fallbackSrc);
  const [isError, setIsError] = useState(false);

  useEffect(() => {
    setCurrentSrc(src && src.trim() ? src.trim() : fallbackSrc);
    setIsError(false);
  }, [src, fallbackSrc]);

  const handleError = () => {
    console.warn('[Ivently Media] Image failed to load:', currentSrc);
    if (currentSrc !== fallbackSrc) {
      setCurrentSrc(fallbackSrc);
    } else {
      setIsError(true);
    }
  };

  if (isError) {
    return (
      <div className={`w-full h-full bg-[#1c1b1e] flex items-center justify-center text-zinc-600 ${className}`}>
        <Compass className="w-8 h-8 opacity-30 text-white" />
      </div>
    );
  }

  return (
    <img
      src={currentSrc}
      alt={alt}
      loading={loading}
      onError={handleError}
      className={className}
    />
  );
};
