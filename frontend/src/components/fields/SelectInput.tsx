// frontend/src/components/fields/SelectInput.tsx
import React from 'react';
import { WidgetProps } from '../../types/sdui';
import { FieldWrapper, inputBaseStyles, readonlyTextStyles } from './FieldWrapper';

export const SelectInput: React.FC<WidgetProps> = ({ label, name, options = [], data = {}, onUpdate, readonly }) => {
  const value = data[name!] || '';

  if (readonly) {
    const selectedOption = options.find(opt => opt[0] === value);
    return (
      <FieldWrapper label={label}>
        <span className={readonlyTextStyles}>{selectedOption ? selectedOption[1] : value}</span>
      </FieldWrapper>
    );
  }

  return (
    <FieldWrapper label={label}>
      <select 
        value={value} 
        onChange={(e) => onUpdate?.(name!, e.target.value)}
        className={`${inputBaseStyles} cursor-pointer`}
      >
        <option value="" disabled>Seleccione...</option>
        {options.map((opt: any, idx: number) => (
          <option key={idx} value={opt[0]}>{opt[1]}</option>
        ))}
      </select>
    </FieldWrapper>
  );
};