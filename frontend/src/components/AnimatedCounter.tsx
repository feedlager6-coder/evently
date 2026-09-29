import React, { useEffect, useState, useRef } from 'react';

interface AnimatedCounterProps {
  value: number;
  suffix?: string;
  className?: string;
}

export const AnimatedCounter: React.FC<AnimatedCounterProps> = ({
  value,
  suffix = '',
  className = '',
}) => {
  const [displayValue, setDisplayValue] = useState(value);
  const [isAnimating, setIsAnimating] = useState(false);
  const [direction, setDirection] = useState<'up' | 'down'>('up');
  const prevValueRef = useRef(value);

  useEffect(() => {
    if (prevValueRef.current !== value) {
      setDirection(value > prevValueRef.current ? 'up' : 'down');
      setIsAnimating(true);
      setDisplayValue(value);
      prevValueRef.current = value;

      const timer = setTimeout(() => {
        setIsAnimating(false);
      }, 350);

      return () => clearTimeout(timer);
    }
  }, [value]);

  return (
    <span className={`inline-flex items-center overflow-hidden h-[1.35em] align-middle ${className}`}>
      <span
        key={displayValue}
        className={`inline-block transition-transform duration-300 ease-[cubic-bezier(0.16,1,0.3,1)] ${
          isAnimating
            ? direction === 'up'
              ? 'animate-slide-up-in text-emerald-400 font-semibold'
              : 'animate-slide-down-in text-indigo-400 font-semibold'
            : ''
        }`}
      >
        {displayValue}
      </span>
      {suffix && <span className="ml-1">{suffix}</span>}
    </span>
  );
};
