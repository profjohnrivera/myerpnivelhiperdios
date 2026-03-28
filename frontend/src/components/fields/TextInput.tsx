// frontend/src/components/fields/TextInput.tsx
import React, { useState, useEffect } from 'react';
import { WidgetProps } from '../../types/sdui';
import { FieldWrapper, inputBaseStyles, readonlyTextStyles } from './FieldWrapper';

export const TextInput: React.FC<WidgetProps> = ({ label, name, data = {}, onUpdate, className, readonly }) => {
  const [localVal, setLocalVal] = useState(data[name!] ?? '');

  useEffect(() => {
    setLocalVal(data[name!] ?? '');
  }, [data[name!]]);

  const handleBlur = () => {
    if (localVal !== (data[name!] ?? '')) {
      onUpdate?.(name!, localVal);
    }
  };

  return (
    <FieldWrapper label={label}>
      {readonly ? <span className={`${readonlyTextStyles} ${className || ''}`}>{data[name!] || ''}</span> : 
      <input 
        type="text" 
        value={localVal} 
        onChange={(e) => setLocalVal(e.target.value)} 
        onBlur={handleBlur}
        className={`${inputBaseStyles} ${className || ''}`} 
        placeholder={label ? "" : "e.g. Lumber Inc"} 
      />}
    </FieldWrapper>
  );
};