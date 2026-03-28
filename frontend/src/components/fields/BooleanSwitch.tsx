// frontend/src/components/fields/BooleanSwitch.tsx
import React from 'react';
import { WidgetProps } from '../../types/sdui';
import { FieldWrapper } from './FieldWrapper';

export const BooleanSwitch: React.FC<WidgetProps> = ({ label, name, data = {}, onUpdate, readonly }) => {
  const isChecked = !!data[name!];

  return (
    <FieldWrapper label={label}>
      <div 
        className={`w-10 h-5 flex items-center rounded-full p-1 cursor-pointer transition-colors ${isChecked ? 'bg-[#017e84]' : 'bg-gray-300'} ${readonly ? 'opacity-70 cursor-not-allowed' : ''}`}
        onClick={() => { if (!readonly) onUpdate?.(name!, !isChecked); }}
      >
        <div className={`bg-white w-4 h-4 rounded-full shadow-md transform transition-transform ${isChecked ? 'translate-x-4' : ''}`} />
      </div>
    </FieldWrapper>
  );
};