// frontend/src/components/fields/MonetaryInput.tsx
import React, { useState, useEffect } from 'react';
import { WidgetProps } from '../../types/sdui';
import { FieldWrapper, inputBaseStyles, readonlyTextStyles } from './FieldWrapper';

export const MonetaryInput: React.FC<WidgetProps> = ({ label, name, data = {}, onUpdate, readonly }) => {
  const [localVal, setLocalVal] = useState(data[name!] ?? 0.0);

  useEffect(() => { setLocalVal(data[name!] ?? 0.0); }, [data[name!]]);

  const handleBlur = () => {
    const num = parseFloat(localVal as string);
    if (!isNaN(num) && num !== (data[name!] ?? 0.0)) {
      onUpdate?.(name!, num);
    }
  };

  return (
    <FieldWrapper label={label}>
      {readonly ? <span className={readonlyTextStyles}>S/ {parseFloat(data[name!] || 0).toFixed(2)}</span> : 
      <div className="relative w-full flex items-center">
        <span className="absolute left-0 text-[#4b5058] text-[14px]">S/</span>
        <input 
          type="number" 
          step="0.01"
          value={localVal} 
          onChange={(e) => setLocalVal(e.target.value)} 
          onBlur={handleBlur}
          className={`${inputBaseStyles} pl-5`} 
        />
      </div>}
    </FieldWrapper>
  );
};