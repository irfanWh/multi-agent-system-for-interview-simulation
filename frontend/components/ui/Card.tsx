import React from 'react';

export const Card = ({ className = '', children }: { className?: string, children: React.ReactNode }) => (
  <div className={`rounded-xl border border-slate-200 bg-white text-slate-950 shadow-sm ${className}`}>
    {children}
  </div>
);

export const CardHeader = ({ className = '', children }: { className?: string, children: React.ReactNode }) => (
  <div className={`flex flex-col space-y-1.5 p-6 ${className}`}>
    {children}
  </div>
);

export const CardTitle = ({ className = '', children }: { className?: string, children: React.ReactNode }) => (
  <h3 className={`font-semibold leading-none tracking-tight text-xl ${className}`}>
    {children}
  </h3>
);

export const CardContent = ({ className = '', children }: { className?: string, children: React.ReactNode }) => (
  <div className={`p-6 pt-0 ${className}`}>
    {children}
  </div>
);
