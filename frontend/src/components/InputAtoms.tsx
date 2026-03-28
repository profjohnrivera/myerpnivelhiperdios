// src/core/components/InputAtoms.tsx
import React, { useState, useEffect } from 'react';
import * as Icons from 'lucide-react';
import { WidgetProps } from '../types/sdui';

// 🎨 LIMPIEZA HIPERDIOS: Usamos text-[14px] (0.875rem) y colores nativos de Odoo
const inputBaseStyles = "w-full bg-transparent border-b border-transparent hover:border-[#d8dadd] focus:border-[#017e84] py-1 text-[14px] text-[#111827] outline-none transition-colors";
const readonlyTextStyles = "w-full py-1 text-[14px] text-[#111827]";

const FieldWrapper: React.FC<{label?: string, children: React.ReactNode}> = ({ label, children }) => {
  // Si no hay label (Ej: El título gigante del registro), ocupamos el 100% del ancho
  if (!label) return <div className="w-full mb-1.5">{children}</div>;

  return (
    // 🔴 FORZAMOS flex-row SIEMPRE, idéntico al .o_inner_group de Odoo
    <div className="flex flex-row w-full mb-2 items-start group">
      {/* 🔴 Label: 30% del ancho, color gris plomo de Odoo */}
      <label className="w-[35%] sm:w-[30%] text-[14px] font-medium text-[#4b5058] pt-[4px] select-none pr-3 break-words leading-tight flex-shrink-0">
        {label}
      </label>
      {/* 🔴 Input: 70% restante */}
      <div className="w-[65%] sm:w-[70%] flex items-center min-h-[28px] relative flex-1">
        {children}
      </div>
    </div>
  );
};

export const TextInput: React.FC<WidgetProps> = ({ label, name, data = {}, onUpdate, className }) => {
  // 💎 FIX: Agregamos 'sale' al candado de Solo Lectura
  const isReadonly = ['sale', 'done', 'cancel'].includes(data?.state);
  
  // 🏎️ ESTADO LOCAL: Velocidad de escritura a 60fps
  const [localVal, setLocalVal] = useState(data[name!] ?? '');

  // 🔄 SINCRONIZACIÓN: Si el servidor o un @compute cambian el dato, actualizamos el input
  useEffect(() => {
    setLocalVal(data[name!] ?? '');
  }, [data[name!]]);

  // 🎯 NOTIFICACIÓN AL ERP: Solo cuando el usuario termina de escribir
  const handleBlur = () => {
    if (localVal !== (data[name!] ?? '')) {
      onUpdate?.(name!, localVal);
    }
  };

  return (
    <FieldWrapper label={label}>
      {isReadonly ? <span className={`${readonlyTextStyles} ${className || ''}`}>{data[name!] || ''}</span> : 
      <input 
        type="text" 
        value={localVal} 
        onChange={(e) => setLocalVal(e.target.value)} 
        onBlur={handleBlur}
        className={`${inputBaseStyles} ${className || ''}`} 
        placeholder={label ? "" : "e.g. Lumber Inc"} // Solo muestra placeholder si es título grande (sin label)
      />}
    </FieldWrapper>
  );
};

export const NumberInput: React.FC<WidgetProps> = ({ label, name, data = {}, onUpdate }) => {
  // 💎 FIX: Agregamos 'sale' al candado de Solo Lectura
  const isReadonly = ['sale', 'done', 'cancel'].includes(data?.state);
  const [localVal, setLocalVal] = useState(data[name!] ?? '');

  useEffect(() => {
    setLocalVal(data[name!] ?? '');
  }, [data[name!]]);

  const handleBlur = () => {
    const numVal = Number(localVal);
    if (numVal !== Number(data[name!] ?? 0)) {
      onUpdate?.(name!, numVal);
    }
  };

  return (
    <FieldWrapper label={label}>
      {isReadonly ? <span className={readonlyTextStyles}>{data[name!] || 0}</span> : 
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

export const TextArea: React.FC<WidgetProps> = ({ label, name, data = {}, onUpdate }) => {
  // 💎 FIX: Agregamos 'sale' al candado de Solo Lectura
  const isReadonly = ['sale', 'done', 'cancel'].includes(data?.state);
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
      {isReadonly ? <span className={`${readonlyTextStyles} whitespace-pre-wrap`}>{data[name!] || ''}</span> : 
      <textarea 
        rows={2} 
        value={localVal} 
        onChange={(e) => setLocalVal(e.target.value)} 
        onBlur={handleBlur}
        className={`${inputBaseStyles} resize-y min-h-[30px]`} 
      />}
    </FieldWrapper>
  );
};

export const MonetaryInput: React.FC<WidgetProps> = ({ label, name, data = {}, onUpdate }) => {
  // 💎 FIX: Agregamos 'sale' al candado de Solo Lectura
  const isReadonly = ['sale', 'done', 'cancel'].includes(data?.state);
  const [localVal, setLocalVal] = useState(data[name!] ?? '');

  useEffect(() => {
    setLocalVal(data[name!] ?? '');
  }, [data[name!]]);

  const handleBlur = () => {
    const parsedVal = parseFloat(String(localVal));
    if (!isNaN(parsedVal) && parsedVal !== parseFloat(data[name!] ?? 0)) {
      onUpdate?.(name!, parsedVal);
    } else if (localVal === '') {
      onUpdate?.(name!, 0);
    }
  };

  return (
    <FieldWrapper label={label}>
      <div className="relative w-full flex items-center group">
        <span className="absolute left-0 text-[#111827] text-[14px]">$</span>
        {isReadonly ? <span className={`${readonlyTextStyles} pl-3 text-left`}>{Number(data[name!] || 0).toLocaleString('en-US', {minimumFractionDigits: 2})}</span> : 
        <input 
          type="number" 
          step="0.01" 
          value={localVal} 
          onChange={(e) => setLocalVal(e.target.value)} 
          onBlur={handleBlur}
          className={`${inputBaseStyles} pl-3 text-right group-hover:pr-1`} 
        />}
      </div>
    </FieldWrapper>
  );
};

// =====================================================================
// ⚡ COMPONENTES DE ACCIÓN INMEDIATA (No requieren Debounce/onBlur)
// =====================================================================

export const BooleanSwitch: React.FC<WidgetProps> = ({ label, name, data = {}, onUpdate }) => {
  const active = Boolean(data[name!]);
  // 💎 FIX: Agregamos 'sale' al candado de Solo Lectura
  const isReadonly = ['sale', 'done', 'cancel'].includes(data?.state);
  
  return (
    <FieldWrapper label={label}>
      <div onClick={() => !isReadonly && onUpdate?.(name!, !active)} className={`flex items-center py-1 w-full ${isReadonly ? 'cursor-default opacity-70' : 'cursor-pointer'}`}>
        {/* 🎨 El switch activo usa el color de link #017e84 y el inactivo #d8dadd */}
        <div className={`w-[34px] h-[20px] flex items-center rounded-full p-0.5 transition-all duration-300 ${active ? 'bg-[#017e84]' : 'bg-[#d8dadd]'}`}>
          <div className={`bg-white w-4 h-4 rounded-full shadow-sm transform transition-transform duration-300 ${active ? 'translate-x-[14px]' : ''}`} />
        </div>
      </div>
    </FieldWrapper>
  );
};

export const SelectInput: React.FC<WidgetProps> = ({ label, name, options = [], data = {}, onUpdate }) => {
  // 💎 FIX: Agregamos 'sale' al candado de Solo Lectura
  const isReadonly = ['sale', 'done', 'cancel'].includes(data?.state);
  const normalizedOptions = options.map(opt => Array.isArray(opt) ? { value: opt[0], label: opt[1] } : { value: opt, label: opt });
  const currentOption = normalizedOptions.find(opt => String(opt.value) === String(data[name!]));

  return (
    <FieldWrapper label={label}>
      {isReadonly ? <span className={readonlyTextStyles}>{currentOption ? currentOption.label : ''}</span> : 
        <div className="relative w-full group">
          <select value={data[name!] ?? ''} onChange={(e) => onUpdate?.(name!, e.target.value)} className={`${inputBaseStyles} appearance-none cursor-pointer pr-6`}>
            <option value=""></option>
            {normalizedOptions.map((opt, idx) => <option key={idx} value={opt.value}>{opt.label}</option>)}
          </select>
          <Icons.ChevronDown className="absolute right-1 top-1/2 -translate-y-1/2 text-gray-400 opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity" size={14} />
        </div>
      }
    </FieldWrapper>
  );
};

export const DateInput: React.FC<WidgetProps> = ({ label, name, data = {}, onUpdate }) => {
  // 💎 FIX: Agregamos 'sale' al candado de Solo Lectura
  const isReadonly = ['sale', 'done', 'cancel'].includes(data?.state);
  
  return (
    <FieldWrapper label={label}>
      {isReadonly ? <span className={readonlyTextStyles}>{data[name!] || ''}</span> : 
      <input type="date" value={data[name!] ?? ''} onChange={(e) => onUpdate?.(name!, e.target.value)} className={`${inputBaseStyles} cursor-text`} />}
    </FieldWrapper>
  );
};

// ============================================================================
// 🚀 NUEVOS ÁTOMOS PARA LA MASTER TEMPLATE (ERP HiperDios)
// ============================================================================

export const DateTimeInput: React.FC<WidgetProps> = ({ label, name, data = {}, onUpdate }) => {
  const isReadonly = ['sale', 'done', 'cancel'].includes(data?.state);
  
  return (
    <FieldWrapper label={label}>
      {isReadonly ? <span className={readonlyTextStyles}>{data[name!] ? new Date(data[name!]).toLocaleString() : ''}</span> : 
      <input 
        type="datetime-local" 
        value={data[name!] || ''} 
        onChange={(e) => onUpdate?.(name!, e.target.value)} 
        className={`${inputBaseStyles} cursor-text`} 
      />}
    </FieldWrapper>
  );
};

export const FileUploader: React.FC<WidgetProps> = ({ label, name, data = {} }) => {
  const isReadonly = ['sale', 'done', 'cancel'].includes(data?.state);
  
  return (
    <FieldWrapper label={label}>
       <input 
          type="file" 
          disabled={isReadonly} 
          className="w-full text-[13px] text-[#5f636f] file:mr-4 file:py-1.5 file:px-4 file:border-0 file:rounded-[3px] file:text-[13px] file:font-medium file:bg-[#F9FAFB] file:text-[#374151] hover:file:bg-[#e7e9ed] transition-colors cursor-pointer outline-none border-b border-transparent hover:border-[#d8dadd] disabled:opacity-50 disabled:cursor-not-allowed"
       />
    </FieldWrapper>
  );
};

export const ImageUploader: React.FC<WidgetProps> = ({ label, name, data = {} }) => {
  const isReadonly = ['sale', 'done', 'cancel'].includes(data?.state);
  // Simulador de Avatar clásico de Odoo (Cuadrado a la izquierda)
  // No usamos FieldWrapper aquí para que mantenga el estilo de "tarjeta" lateral
  return (
    <div className={`flex flex-col items-center justify-center w-[90px] h-[90px] bg-[#F9FAFB] border border-[#d8dadd] border-dashed rounded-[3px] text-[#9a9ca5] ${isReadonly ? 'cursor-default opacity-70' : 'hover:text-[#017e84] hover:border-[#017e84] hover:bg-[#f0f9fa] cursor-pointer'} transition-all relative overflow-hidden group shadow-sm mr-4 mb-2`}>
       <Icons.Camera size={26} className={`mb-1 ${isReadonly ? 'opacity-30' : 'opacity-50 group-hover:opacity-100 group-hover:scale-110 transition-transform'}`} />
       {!isReadonly && <span className="text-[9px] font-bold uppercase tracking-wider opacity-70 group-hover:opacity-100">Subir</span>}
    </div>
  );
};

// Componentes vacíos (Stubs) para evitar advertencias de componentes no encontrados en el Registry
export const RadioGroup: React.FC<WidgetProps> = () => null;
export const SignaturePad: React.FC<WidgetProps> = () => null;