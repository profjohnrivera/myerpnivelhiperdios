// frontend/src/components/fields/FieldWrapper.tsx
import React from 'react';

// Constantes de diseño globales para los inputs
export const inputBaseStyles = "w-full bg-transparent border-b border-transparent hover:border-[#d8dadd] focus:border-[#017e84] py-1 text-[14px] text-[#111827] outline-none transition-colors";
export const readonlyTextStyles = "w-full py-1 text-[14px] text-[#111827]";

export const FieldWrapper: React.FC<{label?: string, children: React.ReactNode}> = ({ label, children }) => {
  if (!label) return <div className="w-full mb-1.5">{children}</div>;

  return (
    <div className="flex flex-row w-full mb-2 items-start group">
      <label className="w-[35%] sm:w-[30%] text-[14px] font-medium text-[#4b5058] pt-[4px] select-none pr-3 break-words leading-tight flex-shrink-0">
        {label}
      </label>
      <div className="w-[65%] sm:w-[70%] flex items-center min-h-[28px] relative flex-1">
        {children}
      </div>
    </div>
  );
};