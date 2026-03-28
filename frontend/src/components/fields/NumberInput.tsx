// frontend/src/components/fields/NumberInput.tsx
import React, { useState, useEffect } from 'react';
import { WidgetProps } from '../../types/sdui';
import { FieldWrapper, inputBaseStyles, readonlyTextStyles } from './FieldWrapper';

export const NumberInput: React.FC<WidgetProps> = ({ label, name, data = {}, onUpdate, readonly }) => {
  const [localVal, setLocalVal] = useState(data[name!] ?? 0);

  useEffect(() => { setLocalVal(data[name!] ?? 0); }, [data[name!]]);

  const handleBlur = () => {
    const num = parseFloat(localVal as string);
    if (!isNaN(num) && num !== (data[name!] ?? 0)) {
      onUpdate?.(name!, num);
    }
  };

  return (
    <FieldWrapper label={label}>
      {readonly ? <span className={readonlyTextStyles}>{data[name!]}</span> : 
      <input 
        type="number" 
        value={localVal} 
        onChange={(e) => setLocalVal(e.target.value)} 
        onBlur={handleBlur}
        className={inputBaseStyles} 
      />}
    </FieldWrapper>
  );
};