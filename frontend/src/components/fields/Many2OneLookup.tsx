// frontend/src/components/fields/Many2OneLookup.tsx
import React, { useState, useRef, useEffect } from 'react';
import * as Icons from 'lucide-react';
import api from '../../api/client';
import { WidgetProps } from '../../types/sdui';

export const useOnClickOutside = (ref: any, handler: any) => {
  useEffect(() => {
    const listener = (event: any) => { if (!ref.current || ref.current.contains(event.target)) return; handler(event); };
    document.addEventListener('mousedown', listener); return () => document.removeEventListener('mousedown', listener);
  }, [ref, handler]);
};

export const safeNum = (val: any, fallback = 0) => {
    if (val === null || val === undefined || val === '') return fallback;
    const n = Number(val);
    return isNaN(n) ? fallback : n;
};

export const extractDisplayValue = (val: any, fallbackName: string = '') => {
    if (val === null || val === undefined || val === '') return fallbackName || '';
    let text = '';
    if (Array.isArray(val)) return String(val[1] || val[0]); 
    else if (typeof val === 'object') text = String(val.name || val.display_name || val.id || '');
    else text = String(val);
    if (/^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-/i.test(text.trim())) return fallbackName ? fallbackName : `[REF-${text.substring(0, 6).toUpperCase()}]`;
    return text;
};

export const getInitials = (name: string) => {
    if (!name) return '';
    const cleanName = Array.isArray(name) ? name[1] : name;
    if (typeof cleanName !== 'string') return '?';
    return cleanName.substring(0, 1).toUpperCase();
};

export const AsyncMany2one = ({ value, onChange, placeholder = "Comience a escribir...", relationModel, onSearchMore, hideControls = false, isTableCell = false, resetOnSelect = false }: any) => {
  const [isOpen, setIsOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState(value || '');
  const [options, setOptions] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const ref = useRef(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useOnClickOutside(ref, () => setIsOpen(false));
  useEffect(() => { if (!resetOnSelect) setSearchTerm(value || ''); }, [value, resetOnSelect]);

  useEffect(() => {
    if (!isOpen || !relationModel || hideControls) return;
    const delayDebounceFn = setTimeout(async () => {
      setLoading(true);
      try {
        const payload = searchTerm ? { domain: [['name', 'ilike', searchTerm]], limit: 7 } : { limit: 7 };
        const res = await api.post(`/data/${relationModel}/search`, payload);
        setOptions(Array.isArray(res.data) ? res.data : (res.data?.data || []));
      } catch (error) { console.error(`❌ Error buscando:`, error); } 
      finally { setLoading(false); }
    }, 300);
    return () => clearTimeout(delayDebounceFn);
  }, [searchTerm, isOpen, relationModel, hideControls]);

  const exactMatch = options.some((opt: any) => (opt.name || '').toLowerCase() === searchTerm.trim().toLowerCase());
  const showCreateOptions = searchTerm.trim().length > 0 && !exactMatch;

  const handleSelection = (id: any, name: string, fullObj: any) => {
    if (resetOnSelect) { setSearchTerm(''); onChange([id, name], fullObj); setTimeout(() => inputRef.current?.focus(), 10); } 
    else { setSearchTerm(name); onChange([id, name], fullObj); }
    setIsOpen(false);
  };

  return (
    <div className="relative w-full" ref={ref}>
      <div className="relative group flex items-center w-full">
        <input ref={inputRef} type="text" value={searchTerm} onChange={(e) => { setSearchTerm(e.target.value); setIsOpen(true); }} onFocus={() => setIsOpen(!hideControls)} onClick={() => setIsOpen(!hideControls)} placeholder={placeholder} readOnly={hideControls} className={`w-full bg-transparent outline-none transition-colors placeholder:text-[#9a9ca5] ${hideControls ? 'cursor-default pointer-events-none' : 'cursor-text'} text-[#111827] m-0 align-middle ${hideControls ? 'border-none' : 'border-b border-transparent hover:border-[#d8dadd] focus:border-[#017e84]'} ${isTableCell ? 'py-0.5 text-[13px] pr-8' : 'py-1 text-[14px] pr-12'}`} />
        {!hideControls && (
          <div className={`absolute right-0 flex items-center opacity-0 group-hover:opacity-100 transition-opacity bg-transparent ${isTableCell ? 'gap-0.5' : 'gap-1.5'}`}>
            {searchTerm && <button onClick={(e) => { e.stopPropagation(); handleSelection(null, '', null); setIsOpen(true); }} className="text-[#9a9ca5] hover:text-[#d44c59] outline-none"><Icons.X size={isTableCell ? 13 : 14} strokeWidth={2.5} /></button>}
            <button onClick={(e) => { e.stopPropagation(); setIsOpen(!isOpen); }} className="text-[#9a9ca5] hover:text-[#111827] outline-none cursor-pointer"><Icons.ChevronDown size={isTableCell ? 13 : 14} strokeWidth={2.5} /></button>
          </div>
        )}
      </div>
      {isOpen && !hideControls && (
        <div className="absolute left-0 top-full w-full min-w-[280px] bg-white border border-[#d8dadd] shadow-xl py-1.5 z-[100] text-[14px] max-h-72 overflow-y-auto rounded-b-[3px]">
          {loading ? <div className="px-3 py-2 text-[#9a9ca5] italic flex items-center gap-2"><Icons.Loader2 size={14} className="animate-spin"/> Buscando...</div> : (
              <>
                {options.map((opt: any) => <div key={opt.id} onClick={() => handleSelection(opt.id, opt.name || opt.id, opt)} className="px-4 py-1.5 hover:bg-[#F9FAFB] cursor-pointer text-[#111827]">{opt.name || opt.id}</div>)}
                {options.length > 0 && showCreateOptions && <div className="border-t border-[#e7e9ed] my-1"></div>}
                {showCreateOptions && (
                  <><div onClick={(e) => { e.stopPropagation(); setLoading(true); api.post(`/data/${relationModel}/create`, { name: searchTerm }).then(res => { if(res.data?.data) handleSelection(res.data.data.id, res.data.data.name, res.data.data); setLoading(false); }).catch(()=> {alert("Error"); setLoading(false);}); }} className="px-4 py-1.5 hover:bg-[#F9FAFB] cursor-pointer text-[#017e84]">Crear <strong className="font-semibold text-[#111827]">"{searchTerm}"</strong></div>
                  <div onClick={(e) => {e.stopPropagation(); setIsOpen(false); window.open(`/app/${relationModel}/form`, '_blank');}} className="px-4 py-1.5 hover:bg-[#F9FAFB] cursor-pointer text-[#017e84]">Crear y editar...</div></>
                )}
              </>
          )}
        </div>
      )}
    </div>
  );
};

export const Many2OneLookup: React.FC<WidgetProps> = ({ label, name, data = {}, relation, onAction, onUpdate, placeholder, readonly }) => {
  // ⚡ SDUI PURO: Leemos el readonly dictado por el motor Evaluator
  const isReadonly = readonly;
  const displayValue = extractDisplayValue(data[name!]);
  const relationTarget = relation || (name === 'partner_id' ? 'res.partner' : name === 'company_id' ? 'res.company' : name === 'user_id' ? 'res.users' : '');

  if (!label) return (
    <div className="w-full flex items-center min-h-[28px] relative mb-2 group">
      {isReadonly ? <span className="w-full py-1 text-[14px] text-[#017e84]">{displayValue}</span> : <AsyncMany2one value={displayValue} onChange={(val: any) => onUpdate?.(name!, val)} relationModel={relationTarget} placeholder={placeholder} onSearchMore={(term: string) => onAction?.('search_relation', { field: name, relation: relationTarget, searchTerm: term, label })} />}
    </div>
  );

  return (
    <div className="flex flex-row w-full mb-2 items-start group">
      <label className="w-[35%] sm:w-[30%] text-[14px] font-medium text-[#4b5058] pt-[4px] select-none pr-3 break-words leading-tight flex-shrink-0">{label}</label>
      <div className="w-[65%] sm:w-[70%] flex items-center min-h-[28px] relative flex-1">
        {isReadonly ? <span className="w-full py-1 text-[14px] text-[#017e84]">{displayValue}</span> : <AsyncMany2one value={displayValue} onChange={(val: any) => onUpdate?.(name!, val)} relationModel={relationTarget} placeholder={placeholder} onSearchMore={(term: string) => onAction?.('search_relation', { field: name, relation: relationTarget, searchTerm: term, label })} />}
      </div>
    </div>
  );
};