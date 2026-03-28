// src/core/components/RelationalAtoms.tsx
import React, { useState, useRef, useEffect, useMemo } from 'react';
import * as Icons from 'lucide-react';
import api from '../api/client'; 
import { WidgetProps } from '../types/sdui';
import { Badge } from './DisplayAtoms';

const useOnClickOutside = (ref: any, handler: any) => {
  useEffect(() => {
    const listener = (event: any) => { if (!ref.current || ref.current.contains(event.target)) return; handler(event); };
    document.addEventListener('mousedown', listener); return () => document.removeEventListener('mousedown', listener);
  }, [ref, handler]);
};

// ============================================================================
// 🛡️ BLINDAJES MATEMÁTICOS Y VISUALES
// ============================================================================
const safeNum = (val: any, fallback = 0) => {
    if (val === null || val === undefined || val === '') return fallback;
    const n = Number(val);
    return isNaN(n) ? fallback : n;
};

const extractDisplayValue = (val: any, fallbackName: string = '') => {
    if (val === null || val === undefined || val === '') return fallbackName || '';
    let text = '';
    if (Array.isArray(val)) return String(val[1] || val[0]); 
    else if (typeof val === 'object') text = String(val.name || val.display_name || val.id || '');
    else text = String(val);

    if (/^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-/i.test(text.trim())) {
        return fallbackName ? fallbackName : `[REF-${text.substring(0, 6).toUpperCase()}]`;
    }
    return text;
};

const getInitials = (name: string) => {
    if (!name) return '';
    const cleanName = Array.isArray(name) ? name[1] : name;
    if (typeof cleanName !== 'string') return '?';
    return cleanName.substring(0, 1).toUpperCase();
};

// ============================================================================
// ⚡ BUSCADOR ASÍNCRONO NIVEL ODOO ENTERPRISE
// ============================================================================
const AsyncMany2one = ({ value, onChange, placeholder = "Comience a escribir...", relationModel, onSearchMore, hideControls = false, isTableCell = false, resetOnSelect = false }: any) => {
  const [isOpen, setIsOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState(value || '');
  const [options, setOptions] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const ref = useRef(null);
  
  const inputRef = useRef<HTMLInputElement>(null);

  useOnClickOutside(ref, () => setIsOpen(false));

  useEffect(() => {
     if (!resetOnSelect) {
         setSearchTerm(value || '');
     }
  }, [value, resetOnSelect]);

  useEffect(() => {
    if (!isOpen || !relationModel) return;
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
  }, [searchTerm, isOpen, relationModel]);

  const exactMatch = options.some((opt: any) => (opt.name || '').toLowerCase() === searchTerm.trim().toLowerCase());
  const showCreateOptions = searchTerm.trim().length > 0 && !exactMatch;

  const handleSelection = (id: any, name: string, fullObj: any) => {
    if (resetOnSelect) {
      setSearchTerm(''); 
      onChange([id, name], fullObj); 
      setTimeout(() => inputRef.current?.focus(), 10); 
    } else {
      setSearchTerm(name);
      onChange([id, name], fullObj);
    }
    setIsOpen(false);
  };

  const handleQuickCreate = async (e: any) => {
    e.stopPropagation();
    setLoading(true);
    try {
      const res = await api.post(`/data/${relationModel}/create`, { name: searchTerm });
      if (res.data && res.data.data) {
         const newRecord = res.data.data;
         handleSelection(newRecord.id, newRecord.name, newRecord);
      }
    } catch(err) { alert("Error al crear el registro."); } 
    finally { setLoading(false); }
  };

  const handleCreateAndEdit = (e: any) => {
    e.stopPropagation();
    setIsOpen(false);
    window.open(`/app/${relationModel}/form`, '_blank');
  };

  return (
    <div className="relative w-full" ref={ref}>
      <div className="relative group flex items-center w-full">
        <input 
          ref={inputRef} 
          type="text" 
          value={searchTerm} 
          onChange={(e) => { setSearchTerm(e.target.value); setIsOpen(true); }} 
          onFocus={() => setIsOpen(true)} onClick={() => setIsOpen(true)} 
          placeholder={placeholder} 
          className={`w-full bg-transparent outline-none transition-colors placeholder:text-[#9a9ca5] cursor-text text-[#111827] m-0 align-middle ${hideControls ? 'border-none' : 'border-b border-transparent hover:border-[#d8dadd] focus:border-[#017e84]'} ${isTableCell ? 'py-0.5 text-[13px] pr-8' : 'py-1 text-[14px] pr-12'}`} 
        />
        
        {!hideControls && (
          <div className={`absolute right-0 flex items-center opacity-0 group-hover:opacity-100 transition-opacity bg-transparent ${isTableCell ? 'gap-0.5' : 'gap-1.5'}`}>
            {searchTerm && (
              <button onClick={(e) => { e.stopPropagation(); handleSelection(null, '', null); setIsOpen(true); }} className="text-[#9a9ca5] hover:text-[#d44c59] outline-none">
                <Icons.X size={isTableCell ? 13 : 14} strokeWidth={2.5} />
              </button>
            )}
            <button onClick={(e) => { e.stopPropagation(); setIsOpen(!isOpen); }} className="text-[#9a9ca5] hover:text-[#111827] outline-none cursor-pointer">
              <Icons.ChevronDown size={isTableCell ? 13 : 14} strokeWidth={2.5} />
            </button>
          </div>
        )}
      </div>
      
      {isOpen && (
        <div className="absolute left-0 top-full w-full min-w-[280px] bg-white border border-[#d8dadd] shadow-xl py-1.5 z-[100] text-[14px] max-h-72 overflow-y-auto rounded-b-[3px]">
          {loading ? (
             <div className="px-3 py-2 text-[#9a9ca5] italic flex items-center gap-2"><Icons.Loader2 size={14} className="animate-spin"/> Buscando...</div>
          ) : (
             <>
                {options.map((opt: any) => (
                  <div key={opt.id} onClick={() => handleSelection(opt.id, opt.name || opt.id, opt)} className="px-4 py-1.5 hover:bg-[#F9FAFB] cursor-pointer text-[#111827]">
                    {opt.name || opt.id}
                  </div>
                ))}
                {options.length > 0 && showCreateOptions && <div className="border-t border-[#e7e9ed] my-1"></div>}
                {showCreateOptions && (
                  <>
                    <div onClick={handleQuickCreate} className="px-4 py-1.5 hover:bg-[#F9FAFB] cursor-pointer text-[#017e84]">
                      Crear <strong className="font-semibold text-[#111827]">"{searchTerm}"</strong>
                    </div>
                    <div onClick={handleCreateAndEdit} className="px-4 py-1.5 hover:bg-[#F9FAFB] cursor-pointer text-[#017e84]">Crear y editar...</div>
                  </>
                )}
                <div className="border-t border-[#e7e9ed] my-1"></div>
                <div onClick={(e) => { e.stopPropagation(); setIsOpen(false); onSearchMore && onSearchMore(searchTerm); }} className="px-4 py-1.5 hover:bg-[#F9FAFB] cursor-pointer text-[#017e84] flex items-center gap-1.5">
                  Buscar más...
                </div>
             </>
          )}
        </div>
      )}
    </div>
  );
};

export const Many2OneLookup: React.FC<WidgetProps> = ({ label, name, data = {}, relation, onAction, onUpdate, placeholder }) => {
  const isReadonly = ['sale', 'done', 'cancel'].includes(data?.state);
  const displayValue = extractDisplayValue(data[name!]);
  const relationTarget = relation || (name === 'partner_id' ? 'res.partner' : name === 'company_id' ? 'res.company' : name === 'user_id' ? 'res.users' : '');

  if (!label) {
    return (
      <div className="w-full flex items-center min-h-[28px] relative mb-2 group">
        {isReadonly ? <span className="w-full py-1 text-[14px] text-[#017e84] hover:text-[#01585c] cursor-pointer transition-colors">{displayValue}</span> : 
        <AsyncMany2one value={displayValue} onChange={(val: any) => onUpdate?.(name!, val)} relationModel={relationTarget} placeholder={placeholder} onSearchMore={(term: string) => onAction?.('search_relation', { field: name, relation: relationTarget, searchTerm: term, label })} />}
      </div>
    );
  }

  return (
    <div className="flex flex-row w-full mb-2 items-start group">
      <label className="w-[35%] sm:w-[30%] text-[14px] font-medium text-[#4b5058] pt-[4px] select-none pr-3 break-words leading-tight flex-shrink-0">
        {label}
      </label>
      <div className="w-[65%] sm:w-[70%] flex items-center min-h-[28px] relative flex-1">
        {isReadonly ? <span className="w-full py-1 text-[14px] text-[#017e84] hover:text-[#01585c] cursor-pointer transition-colors">{displayValue}</span> : 
        <AsyncMany2one 
            value={displayValue} 
            onChange={(val: any) => onUpdate?.(name!, val)} 
            relationModel={relationTarget} 
            placeholder={placeholder} 
            onSearchMore={(term: string) => onAction?.('search_relation', { field: name, relation: relationTarget, searchTerm: term, label })} 
        />}
      </div>
    </div>
  );
};

export const TagSelect: React.FC<WidgetProps> = () => null; 

// ============================================================================
// 🏷️ MANY2MANY TAGS
// ============================================================================
const ODOO_TAG_COLORS: { [key: number]: string } = {
  0: "bg-[#e2e3e5] text-[#495057] border-[#d6d8db]", 
  1: "bg-[#d4edda] text-[#155724] border-[#c3e6cb]", 
  2: "bg-[#f8d7da] text-[#721c24] border-[#f5c6cb]", 
  3: "bg-[#fff3cd] text-[#856404] border-[#ffeeba]", 
  4: "bg-[#cce5ff] text-[#004085] border-[#b8daff]", 
  5: "bg-[#e2d9f3] text-[#563d7c] border-[#d6c9eb]", 
  6: "bg-[#d1ecf1] text-[#0c5460] border-[#bee5eb]", 
  7: "bg-[#f3d9f0] text-[#7b3f72] border-[#ebcae6]", 
  8: "bg-[#e6f3d9] text-[#5e7c3d] border-[#dcedca]", 
  9: "bg-[#fbe6d9] text-[#855132] border-[#f7d6c3]", 
  10: "bg-[#d9f3e6] text-[#3d7c5e] border-[#caf1dc]", 
};

const getOdooColorClass = (colorIndex: any, tagId: any) => {
  if (typeof colorIndex === 'number' && ODOO_TAG_COLORS[colorIndex]) {
      return ODOO_TAG_COLORS[colorIndex];
  }
  if (!tagId) return ODOO_TAG_COLORS[0]; 

  const strId = String(tagId);
  let hash = 0;
  for (let i = 0; i < strId.length; i++) {
    hash = strId.charCodeAt(i) + ((hash << 5) - hash);
  }
  const index = (Math.abs(hash) % 10) + 1; 
  return ODOO_TAG_COLORS[index] || ODOO_TAG_COLORS[1];
};

export const Many2ManyTags: React.FC<WidgetProps> = ({ label, name, data = {}, relation, comodel, onAction, onUpdate, placeholder = "Añadir..." }) => {
  const isReadonly = ['sale', 'done', 'cancel'].includes(data?.state);
  const relationTarget = relation || comodel || 'test.tag'; 
  const tags = Array.isArray(data[name!]) ? data[name!] : [];

  const handleRemove = (idxToRemove: number) => {
    if (isReadonly) return;
    const newTags = tags.filter((_, idx) => idx !== idxToRemove);
    onUpdate?.(name!, newTags);
  };

  const handleAdd = (val: any, fullRecord: any) => {
    if (isReadonly || !val || !val[0]) return;
    const exists = tags.find((t: any) => {
        const tId = typeof t === 'object' && t !== null ? (t.id || t[0]) : t;
        return tId === val[0];
    });
    if (!exists) {
      onUpdate?.(name!, [...tags, fullRecord || { id: val[0], name: val[1] }]);
    }
  };

  return (
    <div className="flex flex-row w-full mb-3 items-start group">
      <label className="w-[35%] sm:w-[30%] text-[14px] font-medium text-[#4b5058] pt-[5px] select-none pr-3 break-words leading-tight flex-shrink-0">
        {label}
      </label>
      
      <div className="w-[65%] sm:w-[70%] flex flex-wrap items-center gap-x-1.5 gap-y-1.5 min-h-[30px] relative flex-1 border-b border-transparent hover:border-[#d8dadd] focus-within:border-[#017e84] transition-colors pb-1">
        {tags.map((tag: any, idx: number) => {
          const tagId = typeof tag === 'object' && tag !== null ? (tag.id || tag[0]) : tag;
          const tagName = typeof tag === 'object' && tag !== null ? (tag.name || tag.display_name || tag[1]) : tag;
          const tagColorIndex = typeof tag === 'object' && tag !== null ? tag.color : null;
          const colorClass = getOdooColorClass(tagColorIndex, tagId);
          
          return (
            <span key={tagId || idx} className={`inline-flex items-center pl-2.5 pr-1.5 py-0.5 rounded-full text-[12px] font-medium border shadow-sm select-none ${colorClass}`}>
              <span className="leading-none pt-px">{tagName}</span>
              {!isReadonly && (
                <button type="button" onClick={(e) => { e.stopPropagation(); handleRemove(idx); }} className="ml-1 flex items-center justify-center text-inherit opacity-60 hover:opacity-100 hover:text-[#d44c59] focus:outline-none transition-all rounded-full p-0.5">
                  <Icons.X size={12} strokeWidth={3} />
                </button>
              )}
            </span>
          );
        })}
        
        {!isReadonly && (
          <div className="flex-1 min-w-[80px] -my-1">
            <AsyncMany2one 
                value="" 
                onChange={handleAdd} 
                relationModel={relationTarget} 
                placeholder={tags.length === 0 ? placeholder : ""} 
                onSearchMore={(term: string) => onAction?.('search_relation', { field: name, relation: relationTarget, searchTerm: term, label })} 
                hideControls={true} 
                isTableCell={true}   
                resetOnSelect={true} 
            />
          </div>
        )}
      </div>
    </div>
  );
};

// ============================================================================
// 🔎 BARRA DE BÚSQUEDA AVANZADA 
// ============================================================================
const AdvancedSearchBar = ({ onFilterChange }: { onFilterChange: (facets: any[]) => void }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [activeFacets, setActiveFacets] = useState<any[]>([]);
  const ref = useRef(null);
  useOnClickOutside(ref, () => setIsOpen(false));

  const availableFilters = [
    { id: 'draft', label: 'Cotizaciones', domain: ['state', '=', 'draft'] },
    { id: 'sale', label: 'Órdenes de venta', domain: ['state', '=', 'sale'] },
    { id: 'cancel', label: 'Cancelados', domain: ['state', '=', 'cancel'] },
  ];

  const availableGroups = [
    { id: 'partner_id', label: 'Cliente', groupBy: 'partner_id' },
    { id: 'state', label: 'Estado', groupBy: 'state' },
  ];

  useEffect(() => { onFilterChange(activeFacets); }, [activeFacets]);

  const toggleFacet = (item: any, type: string) => {
    const exists = activeFacets.find(f => f.id === item.id && f.type === type);
    if (exists) setActiveFacets(activeFacets.filter(f => !(f.id === item.id && f.type === type)));
    else setActiveFacets([...activeFacets, { ...item, type }]);
  };

  const removeFacet = (id: string, type: string, e: any) => {
    e.stopPropagation();
    setActiveFacets(activeFacets.filter(f => !(f.id === id && f.type === type)));
  };

  const handleKeyDown = (e: any) => {
    if (e.key === 'Enter' && query.trim() !== '') {
      e.preventDefault();
      const newFacet = { id: `search_${Date.now()}`, label: `Búsqueda: ${query}`, type: 'search', domain: ['name', 'ilike', query] };
      setActiveFacets([...activeFacets, newFacet]);
      setQuery('');
      setIsOpen(false);
    }
  };

  return (
    <div className="relative w-full max-w-[650px]" ref={ref}>
      <div className="flex items-center w-full border border-[#d8dadd] rounded-[3px] bg-white shadow-sm focus-within:border-[#017e84] transition-colors min-h-[32px] py-[2px] pr-1">
        <div className="pl-3 pr-2 text-[#9a9ca5] flex-shrink-0"><Icons.Search size={15} /></div>
        <div className="flex items-center flex-wrap gap-1.5 flex-1 h-full pl-1">
          {activeFacets.map(facet => (
            <div key={`${facet.type}-${facet.id}`} className="flex items-center bg-[#F9FAFB] border border-[#e7e9ed] text-[#111827] pl-2 pr-1 py-[2px] rounded-[2px] text-[12px] shadow-sm whitespace-nowrap">
              <span className="font-medium mr-1">{facet.label}</span>
              <div 
                  className="flex items-center justify-center p-0.5 rounded-[2px] hover:bg-[#d8dadd] cursor-pointer transition-colors text-[#9a9ca5] hover:text-[#d44c59]"
                  onClick={(e) => removeFacet(facet.id, facet.type, e)}
              >
                  <Icons.X size={12} strokeWidth={2.5}/>
              </div>
            </div>
          ))}
          <input
            type="text" placeholder={activeFacets.length === 0 ? "Buscar..." : ""}
            value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={handleKeyDown}
            onFocus={() => setIsOpen(true)}
            className="flex-1 min-w-[100px] outline-none bg-transparent text-[14px] text-[#111827] h-full placeholder:text-[#9a9ca5] py-1 ml-1"
          />
        </div>
        <div className="pl-2 border-l border-[#d8dadd] h-full flex items-center justify-center cursor-pointer hover:bg-[#F9FAFB] text-[#5f636f] rounded-r-[3px] transition-colors py-[6px] flex-shrink-0" onClick={() => setIsOpen(!isOpen)}>
          <Icons.ChevronDown size={14} strokeWidth={2.5}/>
        </div>
      </div>
      {isOpen && (
        <div className="absolute left-0 top-full mt-1 w-[120%] min-w-[500px] bg-white border border-[#d8dadd] shadow-2xl rounded-[3px] z-[100] flex text-[14px] max-h-[400px]">
          <div className="flex-1 border-r border-[#e7e9ed] p-2 overflow-y-auto">
            <div className="font-bold text-[#111827] flex items-center gap-1.5 mb-2 px-2 py-1.5"><Icons.Filter size={15} className="text-[#9a9ca5]" /> Filtros</div>
            {availableFilters.map(f => {
              const isActive = activeFacets.some(act => act.id === f.id && act.type === 'filter');
              return (
                <div key={f.id} onClick={() => toggleFacet(f, 'filter')} className="flex items-center px-2 py-1.5 hover:bg-[#F9FAFB] cursor-pointer rounded-[3px] transition-colors">
                  <div className="w-5 flex justify-start mr-1">{isActive && <Icons.Check size={15} className="text-[#017e84]" />}</div>
                  <span className={isActive ? 'font-medium text-[#111827]' : 'text-[#374151]'}>{f.label}</span>
                </div>
              );
            })}
          </div>
          <div className="flex-1 border-r border-[#e7e9ed] p-2 overflow-y-auto">
            <div className="font-bold text-[#111827] flex items-center gap-1.5 mb-2 px-2 py-1.5"><Icons.Layers size={15} className="text-[#9a9ca5]" /> Agrupar por</div>
            {availableGroups.map(g => {
              const isActive = activeFacets.some(act => act.id === g.id && act.type === 'group');
              return (
                <div key={g.id} onClick={() => toggleFacet(g, 'group')} className="flex items-center px-2 py-1.5 hover:bg-[#F9FAFB] cursor-pointer rounded-[3px] transition-colors">
                  <div className="w-5 flex justify-start mr-1">{isActive && <Icons.Check size={15} className="text-[#017e84]" />}</div>
                  <span className={isActive ? 'font-medium text-[#111827]' : 'text-[#374151]'}>{g.label}</span>
                </div>
              );
            })}
          </div>
          <div className="flex-1 p-2 overflow-y-auto bg-[#F9FAFB]">
            <div className="font-bold text-[#111827] flex items-center gap-1.5 mb-2 px-2 py-1.5"><Icons.Star size={15} className="text-[#eab308]" /> Favoritos</div>
            <div className="px-2 py-1.5 hover:bg-[#e7e9ed] cursor-pointer text-[#374151] rounded-[3px] transition-colors">Guardar búsqueda actual</div>
          </div>
        </div>
      )}
    </div>
  );
};

// ============================================================================
// 🟢 SERVER-SIDE DATAGRID (DOM Manipulation Pura / Zero-Lag Resize)
// ============================================================================
export const DataGrid: React.FC<WidgetProps> = ({ title, columns = [], data = {}, data_source, onAction }) => {
  const currentModel = window.location.pathname.split('/')[2];
  
  const [rows, setRows] = useState<any[]>([]);
  const [totalRecords, setTotalRecords] = useState(0);
  const [loading, setLoading] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const limit = 40; 

  const [sortConfig, setSortConfig] = useState<{key: string | null, direction: 'asc' | 'desc' | null}>({ key: null, direction: null });
  const [activeDomain, setActiveDomain] = useState<any[]>([]);
  
  const [colWidths, setColWidths] = useState<Record<string, number>>({});
  const [visibleCols, setVisibleCols] = useState<string[]>([]);
  const [isColMenuOpen, setIsColMenuOpen] = useState(false);
  const [menuCoords, setMenuCoords] = useState({ top: 0, right: 0 });
  const colMenuRef = useRef(null);

  useOnClickOutside(colMenuRef, () => setIsColMenuOpen(false));

  useEffect(() => {
    const savedWidths = localStorage.getItem(`${currentModel}_col_widths`);
    if (savedWidths) setColWidths(JSON.parse(savedWidths));

    const savedCols = localStorage.getItem(`${currentModel}_visible_cols`);
    if (savedCols) setVisibleCols(JSON.parse(savedCols));
    else setVisibleCols(columns.map((c: any) => c.field));
  }, [currentModel, columns]);

  const fetchServerData = async () => {
    if (!currentModel) return;
    setLoading(true);
    try {
      const offset = (currentPage - 1) * limit;
      let order_by = undefined;
      if (sortConfig.key && sortConfig.direction) order_by = `${sortConfig.key} ${sortConfig.direction}`; 
      const payload = { domain: activeDomain, limit, offset, order_by };
      
      const res = await api.post(`/data/${currentModel}/search`, payload);
      if (Array.isArray(res.data)) {
        setRows(res.data);
        setTotalRecords(res.data.length);
      } else {
        setRows(res.data.data || []);
        setTotalRecords(res.data.total || 0);
      }
    } catch(e) { console.error("Error cargando grid:", e); } 
    finally { setLoading(false); }
  };

  useEffect(() => { fetchServerData(); }, [currentModel, currentPage, sortConfig, activeDomain]);

  const handleFilterChange = (facets: any[]) => {
    const newDomain: any[] = [];
    facets.forEach(f => { if(f.type === 'filter' || f.type === 'search') newDomain.push(f.domain); });
    setActiveDomain(newDomain.length > 0 ? newDomain.map(d => Array.isArray(d[0]) ? d[0] : d) : []);
    setCurrentPage(1);
  };

  const handleSort = (field: string) => {
    let direction: 'asc' | 'desc' | null = 'asc';
    if (sortConfig.key === field && sortConfig.direction === 'asc') direction = 'desc';
    else if (sortConfig.key === field && sortConfig.direction === 'desc') { direction = null; field = ''; }
    setSortConfig({ key: field || null, direction });
  };

  // 🚀 LA MAGIA ANTI-LAG: DOM Mutation Directa
  const startResize = (e: any, field: string) => {
    e.preventDefault(); 
    e.stopPropagation();
    
    const startX = e.pageX;
    const th = e.target.closest('th');
    const startWidth = th.offsetWidth;

    const onMouseMove = (moveEvent: any) => {
      const newWidth = Math.max(60, startWidth + (moveEvent.pageX - startX));
      // Manipulación pura de DOM: React no se entera de esto, consumiendo 0 CPU
      th.style.width = `${newWidth}px`;
      th.style.minWidth = `${newWidth}px`;
    };

    const onMouseUp = () => { 
      document.removeEventListener('mousemove', onMouseMove); 
      document.removeEventListener('mouseup', onMouseUp); 
      // Al soltar el ratón, notificamos a React 1 sola vez para persistencia
      setColWidths(prev => {
         const newColWidths = { ...prev, [field]: th.offsetWidth };
         localStorage.setItem(`${currentModel}_col_widths`, JSON.stringify(newColWidths));
         return newColWidths;
      });
    };
    
    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
  };

  const toggleColumnVisibility = (field: string) => {
      const newCols = visibleCols.includes(field) ? visibleCols.filter(c => c !== field) : [...visibleCols, field];
      if (newCols.length > 0) { 
          setVisibleCols(newCols);
          localStorage.setItem(`${currentModel}_visible_cols`, JSON.stringify(newCols));
      }
  };

  const handleColMenuToggle = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!isColMenuOpen) {
      const rect = e.currentTarget.getBoundingClientRect();
      setMenuCoords({ top: rect.bottom + 4, right: window.innerWidth - rect.right });
    }
    setIsColMenuOpen(!isColMenuOpen);
  };

  const totalPages = Math.max(1, Math.ceil(totalRecords / limit));
  const startIndex = (currentPage - 1) * limit;
  const endIndex = Math.min(startIndex + rows.length, totalRecords);

  useEffect(() => {
    if (rows.length > 0) sessionStorage.setItem(`${currentModel}_list_ids`, JSON.stringify(rows.map(r => r.id)));
    else sessionStorage.removeItem(`${currentModel}_list_ids`);
  }, [rows, currentModel]);

  const handlePrevPage = () => setCurrentPage(p => Math.max(1, p - 1));
  const handleNextPage = () => setCurrentPage(p => Math.min(totalPages, p + 1));

  const activeColumns = columns.filter((col: any) => visibleCols.includes(col.field));

  return (
    <div className="flex flex-col w-full h-full min-h-0 min-w-0 bg-white text-[#111827] text-[14px] font-sans">
      <div className="flex justify-between items-center px-4 py-[10px] bg-white border-b border-[#d8dadd] flex-shrink-0 gap-8 z-40">
        <div className="flex items-center gap-4 flex-shrink-0">
          <button onClick={() => onAction?.('new_record')} className="bg-[#714B67] text-white px-3 py-[6px] rounded-[3px] font-medium shadow-sm hover:bg-[#5A3C52] transition-colors">Nuevo</button>
          <div className="text-[18px] text-[#111827] tracking-tight">{title || 'Registros'}</div>
        </div>
        <div className="flex-1 flex justify-end"><AdvancedSearchBar onFilterChange={handleFilterChange} /></div>
        <div className="flex items-center gap-2 text-[#5f636f] flex-shrink-0">
          <span className="text-[12px] font-medium mr-2">{loading ? 'Cargando...' : (totalRecords === 0 ? '0 / 0' : `${startIndex + 1}-${endIndex} / ${totalRecords}`)}</span>
          <div className="flex gap-1 mr-3">
             <button onClick={handlePrevPage} disabled={currentPage === 1 || loading} className="hover:bg-[#F9FAFB] p-1 rounded transition-colors disabled:opacity-30 cursor-pointer"><Icons.ChevronLeft size={16}/></button>
             <button onClick={handleNextPage} disabled={currentPage === totalPages || totalRecords === 0 || loading} className="hover:bg-[#F9FAFB] p-1 rounded transition-colors disabled:opacity-30 cursor-pointer"><Icons.ChevronRight size={16}/></button>
          </div>
          <div className="flex bg-[#F9FAFB] rounded-[3px] border border-[#d8dadd]">
             <button className="p-1.5 bg-white shadow-sm rounded-[3px] text-[#714B67]"><Icons.List size={16}/></button>
             <button className="p-1.5 hover:text-[#111827]"><Icons.LayoutGrid size={16}/></button>
          </div>
        </div>
      </div>

      <div className={`relative w-full flex-1 overflow-auto min-h-0 min-w-0 bg-white transition-opacity ${loading ? 'opacity-50 pointer-events-none' : 'opacity-100'}`}>
        <table className="min-w-full text-left whitespace-nowrap table-fixed border-collapse">
          <thead className="border-b-2 border-[#d8dadd]">
            <tr className="text-[#374151] font-bold">
              <th className="w-10 px-4 py-2 bg-white sticky top-0 z-30 shadow-[0_1px_0_#d8dadd]">
                  <input type="checkbox" className="rounded-[2px] cursor-pointer text-[#017e84] focus:ring-[#017e84] border-[#d8dadd]"/>
              </th>
              
              {activeColumns.map((col: any) => (
                <th key={col.field} onClick={() => handleSort(col.field)} style={{ width: colWidths[col.field] ? `${colWidths[col.field]}px` : (col.type === 'MonetaryInput' ? '120px' : 'auto') }} className={`relative px-3 py-2 hover:bg-[#F9FAFB] cursor-pointer select-none bg-white sticky top-0 z-30 group text-[13px] shadow-[0_1px_0_#d8dadd] ${col.type === 'MonetaryInput' ? 'text-right' : ''}`}>
                  <div className={`flex items-center gap-1.5 ${col.type === 'MonetaryInput' ? 'justify-end' : ''}`}>
                    <span className="truncate">{col.label}</span>
                    {sortConfig.key === col.field && (sortConfig.direction === 'asc' ? <Icons.ArrowUp size={13} className="text-[#017e84]" /> : <Icons.ArrowDown size={13} className="text-[#017e84]" />)}
                  </div>
                  <div onMouseDown={(e) => startResize(e, col.field)} onClick={(e) => e.stopPropagation()} className="absolute right-0 top-0 bottom-0 w-[4px] cursor-col-resize hover:bg-[#d8dadd] opacity-0 group-hover:opacity-100 transition-opacity z-20"/>
                </th>
              ))}

              <th className="w-10 px-2 py-2 text-right bg-white sticky top-0 z-30 shadow-[0_1px_0_#d8dadd]">
                 <div ref={colMenuRef}>
                    <button onClick={handleColMenuToggle} className="p-1 rounded hover:bg-[#F9FAFB] outline-none text-[#212529] hover:text-[#017e84] transition-colors"><Icons.SlidersHorizontal size={14} /></button>
                    {isColMenuOpen && (
                        <div className="fixed w-52 bg-white border border-[#d8dadd] shadow-2xl rounded-[3px] z-[9999] text-[14px] text-left font-normal cursor-default flex flex-col" style={{ top: `${menuCoords.top}px`, right: `${menuCoords.right}px`, maxHeight: '350px' }} onClick={(e) => e.stopPropagation()}>
                           <div className="px-3 py-2 text-[11px] font-bold text-[#9a9ca5] uppercase tracking-wider bg-[#F9FAFB] border-b border-[#e7e9ed] flex-shrink-0">Columnas Opcionales</div>
                           <div className="py-1 overflow-y-auto flex-1">
                               {columns.map((col: any) => {
                                  if (!col.label) return null; 
                                  const isVisible = visibleCols.includes(col.field);
                                  return (
                                     <div key={col.field} onClick={(e) => { e.stopPropagation(); toggleColumnVisibility(col.field); }} className="flex items-center px-3 py-1.5 hover:bg-[#F9FAFB] cursor-pointer transition-colors">
                                        <div className="w-5 flex justify-start mr-1">{isVisible && <Icons.Check size={14} className="text-[#017e84]" />}</div>
                                        <span className={isVisible ? 'font-medium text-[#111827]' : 'text-[#5f636f]'}>{col.label}</span>
                                     </div>
                                  );
                               })}
                           </div>
                        </div>
                    )}
                 </div>
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#e7e9ed]">
            {rows.length > 0 ? rows.map((row: any, i: number) => (
              <tr key={row.id || i} onClick={() => window.location.href = `/app/${currentModel}/form/${row.id}`} className="hover:bg-[#F9FAFB] cursor-pointer group bg-white text-[14px] transition-colors">
                <td className="px-4 py-2 w-10" onClick={(e)=>e.stopPropagation()}><input type="checkbox" className="opacity-40 group-hover:opacity-100 cursor-pointer rounded border-[#d8dadd] text-[#017e84] focus:ring-[#017e84] w-[15px] h-[15px]"/></td>
                {activeColumns.map((col: any) => {
                  const rawVal = row[col.field];
                  let content = extractDisplayValue(rawVal);
                  
                  if (col.field === 'state') return <td key={col.field} className="px-3 py-2 text-right"><Badge field={col.field} data={row} /></td>;
                  
                  if (col.type === 'bool' || col.type === 'boolean' || typeof rawVal === 'boolean' || rawVal === true || rawVal === false) {
                      const isTrue = rawVal === true || String(rawVal).toLowerCase() === 'true';
                      return (
                          <td key={col.field} className="px-3 py-2 text-center">
                              {isTrue ? <Icons.CheckSquare className="text-[#017e84] mx-auto" size={16} /> : <Icons.Square className="text-[#d8dadd] mx-auto" size={16} />}
                          </td>
                      );
                  }

                  if (col.type === 'Avatar' || col.field === 'user_id') {
                      return (
                          <td key={col.field} className="px-3 py-2">
                              <div className="flex items-center gap-2">
                                  <div className="w-5 h-5 rounded shadow-sm bg-[#5b5b88] text-white flex items-center justify-center text-[10px] font-bold">{getInitials(String(content))}</div>
                                  <span className="text-[#212529] group-hover:text-[#017e84] transition-colors truncate max-w-[200px]">{content || 'Mitchell Admin'}</span>
                              </div>
                          </td>
                      );
                  }
                  
                  if (col.type === 'Activity') return <td key={col.field} className="px-3 py-2"><div className="flex items-center gap-1"><Icons.Clock size={15} className="text-[#9a9ca5]"/></div></td>;
                  
                  if (col.type === 'MonetaryInput') {
                      const numVal = safeNum(content);
                      return <td key={col.field} className="px-3 py-2 text-right font-medium text-[#008784] truncate">S/ {numVal.toLocaleString('en-US', {minimumFractionDigits: 2})}</td>;
                  }
                  
                  if (col.type === 'DateInput' && content) {
                      content = new Date(content).toLocaleDateString('es-ES', { day: 'numeric', month: 'short', hour: 'numeric', minute: 'numeric' });
                  }

                  if (Array.isArray(rawVal) && rawVal.length > 0 && (Array.isArray(rawVal[0]) || typeof rawVal[0] === 'object')) {
                      content = rawVal.map((v: any) => extractDisplayValue(v)).join(', ');
                  }

                  return <td key={col.field} className="px-3 py-2 truncate max-w-[250px] text-[#212529]">{content || '-'}</td>;
                })}
                <td></td>
              </tr>
            )) : <tr><td colSpan={activeColumns.length + 2} className="py-16 text-center text-[#9a9ca5] italic text-[14px]">{loading ? 'Cargando...' : 'No hay registros que coincidan'}</td></tr>}
          </tbody>
          {rows.length > 0 && (
            <tfoot className="bg-white font-bold text-[#111827] text-[14px] sticky bottom-0 z-20 shadow-[0_-1px_0_#d8dadd]">
              <tr>
                <td className="px-4 py-3"></td>
                {activeColumns.map((col: any, idx: number) => {
                  if (col.type === 'MonetaryInput') {
                     const totalSum = rows.reduce((acc, row) => acc + safeNum(row[col.field]), 0);
                     return <td key={idx} className="px-3 py-3 text-right truncate">S/ {totalSum.toLocaleString('en-US', {minimumFractionDigits: 2})}</td>;
                  }
                  if (idx === activeColumns.length - 2) return <td key={idx} className="px-3 py-3 text-right">Suma Pantalla</td>;
                  return <td key={idx}></td>;
                })}
                <td></td>
              </tr>
            </tfoot>
          )}
        </table>
      </div>
    </div>
  );
};

// ============================================================================
// 📑 ONE2MANY LINES
// ============================================================================
export const One2ManyLines: React.FC<WidgetProps> = ({ name, data_source, columns = [], data = {}, onUpdate, onAction }) => {
  const isReadonly = ['sale', 'done', 'cancel'].includes(data?.state);
  const targetField = data_source || name || 'order_line';
  const lines = data[targetField] || [];

  if (columns && columns.length > 0) {
      const handleDynamicRemove = (idx: number) => {
          if (onAction) onAction('remove_line', { field: targetField, index: idx, line: lines[idx] });
          else {
              const newLines = [...lines];
              newLines.splice(idx, 1);
              onUpdate?.(targetField, newLines);
          }
      };

      const handleDynamicAdd = () => {
          const newLine: any = { id: `new_${Date.now()}`, isNew: true };
          columns.forEach((c: any) => newLine[c.field] = '');
          onUpdate?.(targetField, [...lines, newLine]);
      };

      const handleDynamicChange = (idx: number, field: string, val: any) => {
          const newLines = [...lines];
          newLines[idx] = { ...newLines[idx], [field]: val };
          onUpdate?.(targetField, newLines);
      };

      const renderGridCell = (col: any, val: any, rowIndex: number) => {
        if (isReadonly) {
            if (col.type === 'BooleanSwitch') return <Icons.Check size={14} className={val ? "text-[#017e84] mx-auto" : "text-transparent mx-auto"}/>;
            return <div className="py-1 text-[13px] text-[#111827]">{extractDisplayValue(val)}</div>;
        }

        switch(col.type) {
            case 'Many2OneLookup':
                return (
                    <div className="flex items-center w-full">
                        <AsyncMany2one 
                            value={extractDisplayValue(val)} 
                            onChange={(newVal: any) => handleDynamicChange(rowIndex, col.field, newVal)} 
                            relationModel={col.relation || col.comodel} 
                            onSearchMore={(term: string) => onAction?.('search_relation', { field: `${targetField}.${rowIndex}.${col.field}`, relation: col.relation || col.comodel, searchTerm: term, label: col.label })}
                            isTableCell={true} 
                        />
                    </div>
                );
            case 'BooleanSwitch':
                return <input type="checkbox" checked={Boolean(val)} onChange={(e) => handleDynamicChange(rowIndex, col.field, e.target.checked)} className="rounded-[2px] cursor-pointer text-[#017e84] focus:ring-[#017e84] border-[#d8dadd] w-3.5 h-3.5 m-0 align-middle block mx-auto"/>;
            case 'SelectInput':
                const opts = col.options || [];
                return (
                    <select value={val || ''} onChange={(e) => handleDynamicChange(rowIndex, col.field, e.target.value)} className="w-full bg-transparent outline-none border-b border-transparent hover:border-[#d8dadd] focus:border-[#017e84] text-[#111827] py-0.5 text-[13px] cursor-pointer m-0 align-middle appearance-none">
                        <option value=""></option>
                        {opts.map((o:any) => {
                            const v = Array.isArray(o) ? o[0] : o;
                            const l = Array.isArray(o) ? o[1] : o;
                            return <option key={v} value={v}>{l}</option>;
                        })}
                    </select>
                );
            default: // TextInput, NumberInput, MonetaryInput
                return (
                    <input 
                        type={col.type === 'NumberInput' || col.type === 'MonetaryInput' ? 'number' : 'text'}
                        step={col.type === 'MonetaryInput' ? '0.01' : '1'}
                        value={typeof val === 'object' && val !== null ? (val[1] || val.name || '') : (val || '')}
                        onChange={(e) => handleDynamicChange(rowIndex, col.field, e.target.value)}
                        className={`w-full bg-transparent outline-none border-b border-transparent hover:border-[#d8dadd] focus:border-[#017e84] transition-colors text-[#111827] py-0.5 text-[13px] m-0 align-middle ${col.type === 'NumberInput' || col.type === 'MonetaryInput' ? 'text-right' : 'text-left'}`}
                    />
                );
        }
      };

      return (
          <div className="col-span-full w-full">
              <div className="w-full flex flex-col pt-0 overflow-x-auto">
                  <table className="min-w-full text-left border-collapse whitespace-nowrap table-fixed">
                      <thead className="border-b border-[#d8dadd] bg-white">
                          <tr>
                              {!isReadonly && <th className="w-6 py-2 px-1"></th>}
                              {columns.map((col: any, idx: number) => (
                                  <th key={idx} className={`py-2 px-2 font-semibold text-[#4b5058] text-[13px] align-middle ${col.type === 'NumberInput' || col.type === 'MonetaryInput' ? 'text-right' : 'text-left'}`}>
                                      {col.label}
                                  </th>
                              ))}
                              {!isReadonly && <th className="w-8 py-2 px-1"></th>}
                          </tr>
                      </thead>
                      <tbody className="divide-y divide-[#e7e9ed]">
                          {lines.length === 0 ? (
                              <tr>
                                  <td colSpan={columns.length + 2} className="py-8 text-center text-[#9a9ca5] italic text-[14px]">
                                      Haz clic en "Agregar línea" para comenzar.
                                  </td>
                              </tr>
                          ) : (
                              lines.map((row: any, rowIndex: number) => (
                                  <tr key={row.id || rowIndex} className="hover:bg-[#f9fafb] border-b border-[#e7e9ed] last:border-0 group transition-colors">
                                      
                                      {!isReadonly && (
                                          <td className="w-6 px-1 text-center align-middle cursor-move py-1">
                                              <Icons.GripVertical size={14} className="text-[#d1d5db] opacity-0 group-hover:opacity-100 mx-auto transition-opacity" />
                                          </td>
                                      )}
                                      
                                      {columns.map((col: any, colIndex: number) => (
                                          <td key={colIndex} className={`px-2 py-1 align-middle relative text-[13px] text-[#111827] ${col.type === 'NumberInput' || col.type === 'MonetaryInput' ? 'text-right' : 'text-left'}`}>
                                              {renderGridCell(col, row[col.field], rowIndex)}
                                          </td>
                                      ))}

                                      {!isReadonly && (
                                          <td className="w-8 px-1 text-center align-middle py-1">
                                              <button className="text-[#a8aab0] hover:text-[#d44c59] opacity-0 group-hover:opacity-100 outline-none transition-colors" onClick={() => handleDynamicRemove(rowIndex)}>
                                                  <Icons.Trash2 size={15}/>
                                              </button>
                                          </td>
                                      )}
                                  </tr>
                              ))
                          )}
                          {!isReadonly && (
                              <tr>
                                  <td colSpan={columns.length + 2} className="py-2 px-2">
                                      <button onClick={handleDynamicAdd} className="text-[#017e84] text-[13px] font-medium hover:text-[#01585c] focus:outline-none transition-colors">
                                          Agregar línea
                                      </button>
                                  </td>
                              </tr>
                          )}
                      </tbody>
                  </table>
              </div>
          </div>
      );
  }

  const subtotal = lines.reduce((acc: number, line: any) => {
    if (line.display_type === 'line_section' || line.display_type === 'line_note') return acc;
    const rawTotal = safeNum(line.price_subtotal, null);
    if (rawTotal !== null) return acc + rawTotal;
    const lineQty = safeNum(line.product_uom_qty, 1);
    const linePrice = safeNum(line.price_unit, 0);
    return acc + (lineQty * linePrice);
  }, 0);

  useEffect(() => {
    if (isReadonly || !onUpdate) return;
    if (safeNum(data.amount_untaxed) !== subtotal) {
        onUpdate('amount_untaxed', subtotal);
        onUpdate('amount_total', subtotal); 
    }
  }, [subtotal, isReadonly, onUpdate, data.amount_untaxed]);

  const handleCellChange = async (idx: number, field: string, val: any, fullRecord: any = null) => { 
    if (onUpdate && !isReadonly) { 
      const newLines = [...lines]; 
      newLines[idx] = { ...newLines[idx], [field]: val }; 
      
      if (field === 'product_id') {
          if (Array.isArray(val) && !newLines[idx].name) newLines[idx].name = val[1];
          else if (typeof val === 'string' && !newLines[idx].name) newLines[idx].name = val;

          let priceToSet = null;
          if (fullRecord && (fullRecord.list_price !== undefined || fullRecord.price !== undefined)) {
              priceToSet = safeNum(fullRecord.list_price ?? fullRecord.price, 0);
          } 
          else if (Array.isArray(val) && val[0]) {
              try {
                  const res = await api.post(`/data/product.product/search`, { domain: [['id', '=', val[0]]], limit: 1 });
                  if (res.data && res.data.data?.length > 0) {
                      priceToSet = safeNum(res.data.data[0].list_price ?? res.data.data[0].price, 0);
                  } else if (Array.isArray(res.data) && res.data.length > 0) {
                      priceToSet = safeNum(res.data[0].list_price ?? res.data[0].price, 0);
                  }
              } catch (e) {}
          }

          if (priceToSet !== null) {
              newLines[idx].price_unit = priceToSet;
              const q = safeNum(newLines[idx].product_uom_qty, 1);
              newLines[idx].price_subtotal = q * priceToSet;
          }
      }

      if (field === 'product_uom_qty' || field === 'price_unit') {
         const q = field === 'product_uom_qty' ? safeNum(val, 0) : safeNum(newLines[idx].product_uom_qty, 1);
         const p = field === 'price_unit' ? safeNum(val, 0) : safeNum(newLines[idx].price_unit, 0);
         newLines[idx].price_subtotal = q * p;
      }
      
      onUpdate(targetField, newLines); 
    } 
  };

  const handleAddLine = (type: string | null) => {
    onUpdate?.(targetField, [...lines, { 
      id: `new_${Date.now()}`, 
      display_type: type, 
      product_uom_qty: type ? 0 : 1, 
      price_unit: 0, 
      price_subtotal: 0,
      name: type === 'line_section' ? 'Nueva Sección' : type === 'line_note' ? 'Nueva Nota...' : '', 
      isNew: true 
    }]);
  };

  return (
    <div className="col-span-full w-full">
      <div className="w-full flex flex-col pt-0 overflow-x-auto">
        <table className="min-w-full text-left border-collapse whitespace-nowrap table-fixed">
          <thead className="border-b border-[#d8dadd] bg-white">
            <tr>
              {!isReadonly && <th className="w-6 py-2 px-1"></th>}
              <th className="py-2 px-2 font-semibold text-[#4b5058] text-[13px] align-middle w-[40%]">Producto</th>
              <th className="py-2 px-2 text-right font-semibold text-[#4b5058] text-[13px] align-middle w-16">Cantidad</th>
              <th className="py-2 px-2 text-right font-semibold text-[#4b5058] text-[13px] align-middle w-16">Entregado</th>
              <th className="py-2 px-2 text-right font-semibold text-[#4b5058] text-[13px] align-middle w-16">Facturado</th>
              <th className="py-2 px-2 text-right font-semibold text-[#4b5058] text-[13px] align-middle w-24">Precio unitario</th>
              <th className="py-2 px-2 text-left font-semibold text-[#4b5058] text-[13px] align-middle w-20">Impuestos</th>
              <th className="py-2 px-2 text-right font-semibold text-[#4b5058] text-[13px] align-middle w-24">Importe</th>
              {!isReadonly && <th className="w-8 py-2 px-1"></th>}
            </tr>
          </thead>
          <tbody className="divide-y divide-[#e7e9ed]">
            {lines.map((line: any, idx: number) => {
              if (line.display_type) {
                return (
                  <tr key={line.id || idx} className={line.display_type === 'line_section' ? "bg-[#F9FAFB] group border-b border-[#e7e9ed]" : "group border-b border-[#e7e9ed]"}>
                    <td colSpan={isReadonly ? 7 : 9} className="py-1 px-2 align-middle relative text-[13px]">
                       <div className="flex items-center gap-2">
                           {!isReadonly && <Icons.GripVertical size={14} className="text-[#d1d5db] opacity-0 group-hover:opacity-100 cursor-move" />}
                          <input type="text" value={line.name || ''} onChange={(e) => handleCellChange(idx, 'name', e.target.value)} readOnly={isReadonly} placeholder={line.display_type === 'line_section' ? 'Nombre de la sección' : 'Escriba una nota...'} className={`w-full bg-transparent outline-none border-b border-transparent focus:border-[#017e84] py-0.5 m-0 align-middle ${line.display_type === 'line_section' ? 'font-bold text-[#111827]' : 'italic text-[#7c7f89]'}`} />
                       </div>
                    </td>
                  </tr>
                );
              }

              let displayProduct = extractDisplayValue(line.product_id || line.product, line.name);
              const rawTotal = safeNum(line.price_subtotal, null);
              const lineQty = safeNum(line.product_uom_qty, 1);
              const linePrice = safeNum(line.price_unit, 0);
              const lineTotal = rawTotal !== null ? rawTotal : (lineQty * linePrice);

              return (
                <tr key={line.id || idx} className="hover:bg-[#f9fafb] border-b border-[#e7e9ed] last:border-0 group transition-colors">
                  
                  {!isReadonly && (
                      <td className="w-6 px-1 text-center align-middle cursor-move py-1">
                          <Icons.GripVertical size={14} className="text-[#d1d5db] opacity-0 group-hover:opacity-100 mx-auto transition-opacity" />
                      </td>
                  )}

                  <td className="px-2 py-1 align-middle relative text-[13px]">
                    {isReadonly ? (
                        <div className="text-[#017e84] font-medium w-full truncate">{displayProduct}</div>
                    ) : (
                        <AsyncMany2one 
                           value={displayProduct} 
                           onChange={(val: any, fullRecord?: any) => handleCellChange(idx, 'product_id', val, fullRecord)} 
                           relationModel="product.product"
                           placeholder="Buscar un producto..."
                           onSearchMore={(term: string) => onAction?.('search_relation', { field: `${targetField}.${idx}.product_id`, relation: 'product.product', searchTerm: term, label: 'Producto' })}
                           isTableCell={true} 
                        />
                    )}
                  </td>
                  
                  <td className="px-2 py-1 text-right align-middle">
                      <input type="number" 
                             className="w-full bg-transparent text-right outline-none border-b border-transparent hover:border-[#d8dadd] focus:border-[#017e84] text-[#111827] py-0.5 m-0 align-middle text-[13px]" 
                             value={line.product_uom_qty !== undefined ? line.product_uom_qty : 1} 
                             onChange={(e) => handleCellChange(idx, 'product_uom_qty', Number(e.target.value))} 
                             readOnly={isReadonly} />
                  </td>
                  <td className="px-2 py-1 text-right text-[#7c7f89] align-middle text-[13px]">{line.qty_delivered || '0.00'}</td>
                  <td className="px-2 py-1 text-right text-[#7c7f89] align-middle text-[13px]">{line.qty_invoiced || '0.00'}</td>
                  
                  <td className="px-2 py-1 text-right align-middle">
                      <input type="number" step="0.01" 
                             className="w-full bg-transparent text-right outline-none border-b border-transparent hover:border-[#d8dadd] focus:border-[#017e84] text-[#111827] py-0.5 m-0 align-middle text-[13px]" 
                             value={line.price_unit !== undefined ? line.price_unit : 0} 
                             onChange={(e) => handleCellChange(idx, 'price_unit', Number(e.target.value))} 
                             readOnly={isReadonly} />
                  </td>
                  <td className="px-2 py-1 text-left text-[#9a9ca5] align-middle text-[13px]"></td> 
                  <td className="px-2 py-1 text-right font-medium text-[#111827] align-middle text-[13px]">S/ {lineTotal.toLocaleString('en-US', {minimumFractionDigits: 2})}</td>
                  {!isReadonly && (
                    <td className="w-8 px-1 text-center align-middle py-1">
                      <button 
                        onClick={(e) => { 
                          e.stopPropagation();
                          if (onAction) onAction('remove_line', { field: targetField, index: idx, line: line });
                          else { const newLines = [...lines]; newLines.splice(idx, 1); onUpdate?.(targetField, newLines); }
                        }} 
                        className="text-[#a8aab0] hover:text-[#d44c59] opacity-0 group-hover:opacity-100 outline-none transition-colors"
                      >
                        <Icons.Trash2 size={15} />
                      </button>
                    </td>
                  )}
                </tr>
              );
            })}
            {!isReadonly && (
              <tr>
                <td colSpan={9} className="py-2 px-2">
                  <div className="flex gap-4">
                    <button onClick={() => handleAddLine(null)} className="text-[#017e84] text-[13px] font-medium hover:text-[#01585c] focus:outline-none transition-colors">Agregar un producto</button>
                    <button onClick={() => handleAddLine('line_section')} className="text-[#017e84] text-[13px] font-medium hover:text-[#01585c] focus:outline-none transition-colors">Agregar una sección</button>
                    <button onClick={() => handleAddLine('line_note')} className="text-[#017e84] text-[13px] font-medium hover:text-[#01585c] focus:outline-none transition-colors">Agregar una nota</button>
                  </div>
                </td>
              </tr>
            )}
          </tbody>
        </table>
        
        <div className="flex justify-between mt-auto border-t border-[#d8dadd] pt-4 px-2">
          <div className="w-1/2">
            <textarea placeholder="Términos y condiciones..." value={data.note || ''} onChange={(e) => onUpdate && onUpdate('note', e.target.value)} className="w-full bg-transparent outline-none border-b border-transparent focus:border-[#017e84] text-[14px] text-[#7c7f89] resize-y min-h-[60px] transition-colors" readOnly={isReadonly}></textarea>
          </div>
          <div className="w-full md:w-[35%] lg:w-[25%] text-[14px]">
            <div className="flex justify-between text-[#5f636f] mb-1"><span>Subtotal:</span> <span className="font-bold text-[#111827]">S/ {(!isNaN(subtotal) ? subtotal : 0).toLocaleString('en-US', {minimumFractionDigits: 2})}</span></div>
            <div className="flex justify-between text-[#111827] pt-1 text-[16px]"><span className="font-medium">Total:</span> <span className="font-bold">S/ {(!isNaN(subtotal) ? subtotal : 0).toLocaleString('en-US', {minimumFractionDigits: 2})}</span></div>
          </div>
        </div>
      </div>
    </div>
  );
};