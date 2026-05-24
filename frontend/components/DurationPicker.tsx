'use client';
import React, { useEffect, useRef, useState } from 'react';

interface DurationPickerProps {
  value: number;
  onChange: (value: number) => void;
  min?: number;
  max?: number;
  step?: number;
}

const DurationPicker: React.FC<DurationPickerProps> = ({
  value,
  onChange,
  min = 5,
  max = 120,
  step = 5,
}) => {
  const scrollRef = useRef<HTMLDivElement>(null);
  const itemHeight = 48; // Each item is 48px high (h-12)
  const [internalValue, setInternalValue] = useState(value);

  const options: number[] = [];
  for (let i = min; i <= max; i += step) {
    options.push(i);
  }

  // Initialize scroll position
  useEffect(() => {
    if (scrollRef.current) {
      const index = options.indexOf(value);
      if (index !== -1) {
        scrollRef.current.scrollTop = index * itemHeight;
      }
    }
  }, []);

  // Update scroll if value changed from outside (optional, but good for state sync)
  useEffect(() => {
    if (scrollRef.current && value !== internalValue) {
      const index = options.indexOf(value);
      if (index !== -1) {
        scrollRef.current.scrollTo({
          top: index * itemHeight,
          behavior: 'smooth'
        });
        setInternalValue(value);
      }
    }
  }, [value]);

  const handleScroll = () => {
    if (!scrollRef.current) return;
    
    const index = Math.round(scrollRef.current.scrollTop / itemHeight);
    const newValue = options[index];
    
    if (newValue !== undefined && newValue !== internalValue) {
      setInternalValue(newValue);
      onChange(newValue);
    }
  };

  return (
    <div className="flex flex-col items-center">
      <div className="relative w-64 h-[192px] bg-slate-900/80 rounded-3xl border border-white/10 overflow-hidden group">
        {/* Selection Overlay (Glass effect) */}
        <div className="absolute top-[72px] left-2 right-2 h-[48px] bg-indigo-500/20 border border-indigo-500/40 rounded-xl pointer-events-none z-10 shadow-[0_0_20px_rgba(99,102,241,0.2)]" />
        
        {/* Top/Bottom Fades */}
        <div className="absolute top-0 left-0 right-0 h-16 bg-gradient-to-b from-slate-900 to-transparent z-10 pointer-events-none" />
        <div className="absolute bottom-0 left-0 right-0 h-16 bg-gradient-to-t from-slate-900 to-transparent z-10 pointer-events-none" />

        {/* Scrollable Area */}
        <div 
          ref={scrollRef}
          onScroll={handleScroll}
          className="h-full overflow-y-auto scroll-smooth snap-y snap-mandatory no-scrollbar"
          style={{ 
            scrollSnapType: 'y mandatory',
            msOverflowStyle: 'none',
            scrollbarWidth: 'none'
          }}
        >
          {/* Top spacer to center the first item */}
          <div className="h-[72px]" />
          
          <div className="flex flex-col">
            {options.map((opt) => (
              <div 
                key={opt}
                className={`h-[48px] flex items-center px-8 snap-center transition-all duration-300 ${
                  internalValue === opt 
                    ? 'text-white text-3xl font-black' 
                    : 'text-slate-600 text-lg font-medium opacity-40'
                }`}
              >
                <div className="flex-1 text-right pr-4">{opt}</div>
                <div className="flex-1 text-left text-sm uppercase tracking-widest text-slate-500">mins</div>
              </div>
            ))}
          </div>

          {/* Bottom spacer to center the last item */}
          <div className="h-[72px]" />
        </div>
      </div>
      
      {/* Selected Indicator */}
      <div className="mt-6 flex items-center bg-indigo-500/10 px-4 py-2 rounded-full border border-indigo-500/20">
        <span className="text-slate-400 text-sm font-medium mr-2">Duration:</span>
        <span className="text-indigo-400 font-bold text-lg">{internalValue} minutes</span>
      </div>

      <style jsx global>{`
        .no-scrollbar::-webkit-scrollbar {
          display: none;
        }
      `}</style>
    </div>
  );
};

export default DurationPicker;
