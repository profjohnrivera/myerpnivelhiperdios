// frontend/src/components/views/DataGrid.tsx
import React, { useState, useRef, useEffect } from 'react';
import * as Icons from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import api from '../../api/client'; 
import { WidgetProps } from '../../types/sdui';
import { Badge } from '../widgets/Badge';
import { useOnClickOutside, safeNum, extractDisplayValue, getInitials } from "../fields/Many2OneLookup";

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

  const handleKeyDown = (e: any) => {
    if (e.key === 'Enter' && query.trim() !== '') {
      e.preventDefault();
      setActiveFacets([...activeFacets, { id: `search_${Date.now()}`, label: `Búsqueda: ${query}`, type: 'search', domain: ['name', 'ilike', query] }]);
      setQuery(''); setIsOpen(false);
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
              <div className="flex items-center justify-center p-0.5 rounded-[2px] hover:bg-[#d8dadd] cursor-pointer transition-colors text-[#9a9ca5] hover:text-[#d44c59]" onClick={(e) => { e.stopPropagation(); setActiveFacets(activeFacets.filter(f => !(f.id === facet.id && f.type === facet.type))); }}><Icons.X size={12} strokeWidth={2.5}/></div>
            </div>
          ))}
          <input type="text" placeholder={activeFacets.length === 0 ? "Buscar..." : ""} value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={handleKeyDown} onFocus={() => setIsOpen(true)} className="flex-1 min-w-[100px] outline-none bg-transparent text-[14px] text-[#111827] h-full placeholder:text-[#9a9ca5] py-1 ml-1" />
        </div>
        <div className="pl-2 border-l border-[#d8dadd] h-full flex items-center justify-center cursor-pointer hover:bg-[#F9FAFB] text-[#5f636f] rounded-r-[3px] transition-colors py-[6px] flex-shrink-0" onClick={() => setIsOpen(!isOpen)}><Icons.ChevronDown size={14} strokeWidth={2.5}/></div>
      </div>
      {isOpen && (
        <div className="absolute left-0 top-full mt-1 w-[120%] min-w-[500px] bg-white border border-[#d8dadd] shadow-2xl rounded-[3px] z-[100] flex text-[14px] max-h-[400px]">
          <div className="flex-1 border-r border-[#e7e9ed] p-2 overflow-y-auto">
            <div className="font-bold text-[#111827] flex items-center gap-1.5 mb-2 px-2 py-1.5"><Icons.Filter size={15} className="text-[#9a9ca5]" /> Filtros</div>
            {availableFilters.map(f => {
              const isActive = activeFacets.some(act => act.id === f.id && act.type === 'filter');
              return <div key={f.id} onClick={() => toggleFacet(f, 'filter')} className="flex items-center px-2 py-1.5 hover:bg-[#F9FAFB] cursor-pointer rounded-[3px] transition-colors"><div className="w-5 flex justify-start mr-1">{isActive && <Icons.Check size={15} className="text-[#017e84]" />}</div><span className={isActive ? 'font-medium text-[#111827]' : 'text-[#374151]'}>{f.label}</span></div>;
            })}
          </div>
          <div className="flex-1 border-r border-[#e7e9ed] p-2 overflow-y-auto">
            <div className="font-bold text-[#111827] flex items-center gap-1.5 mb-2 px-2 py-1.5"><Icons.Layers size={15} className="text-[#9a9ca5]" /> Agrupar por</div>
            {availableGroups.map(g => {
              const isActive = activeFacets.some(act => act.id === g.id && act.type === 'group');
              return <div key={g.id} onClick={() => toggleFacet(g, 'group')} className="flex items-center px-2 py-1.5 hover:bg-[#F9FAFB] cursor-pointer rounded-[3px] transition-colors"><div className="w-5 flex justify-start mr-1">{isActive && <Icons.Check size={15} className="text-[#017e84]" />}</div><span className={isActive ? 'font-medium text-[#111827]' : 'text-[#374151]'}>{g.label}</span></div>;
            })}
          </div>
        </div>
      )}
    </div>
  );
};

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
      if (Array.isArray(res.data)) { setRows(res.data); setTotalRecords(res.data.length); } 
      else { setRows(res.data.data || []); setTotalRecords(res.data.total || 0); }
    } catch(e) { console.error("Error:", e); } finally { setLoading(false); }
  };

  useEffect(() => { fetchServerData(); }, [currentModel, currentPage, sortConfig, activeDomain]);

  const handleSort = (field: string) => {
    let direction: 'asc' | 'desc' | null = 'asc';
    if (sortConfig.key === field && sortConfig.direction === 'asc') direction = 'desc';
    else if (sortConfig.key === field && sortConfig.direction === 'desc') { direction = null; field = ''; }
    setSortConfig({ key: field || null, direction });
  };

  const startResize = (e: any, field: string) => {
    e.preventDefault(); e.stopPropagation();
    const startX = e.pageX; const th = e.target.closest('th'); const startWidth = th.offsetWidth;
    const onMouseMove = (moveEvent: any) => { const newWidth = Math.max(60, startWidth + (moveEvent.pageX - startX)); th.style.width = `${newWidth}px`; th.style.minWidth = `${newWidth}px`; };
    const onMouseUp = () => { 
      document.removeEventListener('mousemove', onMouseMove); document.removeEventListener('mouseup', onMouseUp); 
      setColWidths(prev => { const newColWidths = { ...prev, [field]: th.offsetWidth }; localStorage.setItem(`${currentModel}_col_widths`, JSON.stringify(newColWidths)); return newColWidths; });
    };
    document.addEventListener('mousemove', onMouseMove); document.addEventListener('mouseup', onMouseUp);
  };

  const activeColumns = columns.filter((col: any) => visibleCols.includes(col.field));
  const totalPages = Math.max(1, Math.ceil(totalRecords / limit));
  const startIndex = (currentPage - 1) * limit;

  return (
    <div className="flex flex-col w-full h-full min-h-0 min-w-0 bg-white text-[#111827] text-[14px] font-sans">
      <div className="flex justify-between items-center px-4 py-[10px] bg-white border-b border-[#d8dadd] flex-shrink-0 gap-8 z-40">
        <div className="flex items-center gap-4 flex-shrink-0">
          <button onClick={() => onAction?.('new_record')} className="bg-[#714B67] text-white px-3 py-[6px] rounded-[3px] font-medium shadow-sm hover:bg-[#5A3C52] transition-colors">Nuevo</button>
          <div className="text-[18px] text-[#111827] tracking-tight">{title || 'Registros'}</div>
        </div>
        <div className="flex-1 flex justify-end"><AdvancedSearchBar onFilterChange={(facets) => { setActiveDomain(facets.map(f => Array.isArray(f.domain[0]) ? f.domain[0] : f.domain)); setCurrentPage(1); }} /></div>
        <div className="flex items-center gap-2 text-[#5f636f] flex-shrink-0">
          <span className="text-[12px] font-medium mr-2">{loading ? 'Cargando...' : (totalRecords === 0 ? '0 / 0' : `${startIndex + 1}-${Math.min(startIndex + rows.length, totalRecords)} / ${totalRecords}`)}</span>
          <div className="flex gap-1 mr-3">
             <button onClick={() => setCurrentPage(p => Math.max(1, p - 1))} disabled={currentPage === 1 || loading} className="hover:bg-[#F9FAFB] p-1 rounded transition-colors disabled:opacity-30 cursor-pointer"><Icons.ChevronLeft size={16}/></button>
             <button onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))} disabled={currentPage === totalPages || totalRecords === 0 || loading} className="hover:bg-[#F9FAFB] p-1 rounded transition-colors disabled:opacity-30 cursor-pointer"><Icons.ChevronRight size={16}/></button>
          </div>
        </div>
      </div>

      <div className={`relative w-full flex-1 overflow-auto min-h-0 min-w-0 bg-white transition-opacity ${loading ? 'opacity-50 pointer-events-none' : 'opacity-100'}`}>
        <table className="min-w-full text-left whitespace-nowrap table-fixed border-collapse">
          <thead className="border-b-2 border-[#d8dadd]">
            <tr className="text-[#374151] font-bold">
              <th className="w-10 px-4 py-2 bg-white sticky top-0 z-30 shadow-[0_1px_0_#d8dadd]"><input type="checkbox" className="rounded-[2px] cursor-pointer text-[#017e84] border-[#d8dadd]"/></th>
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
                    <button onClick={(e) => { e.stopPropagation(); setIsColMenuOpen(!isColMenuOpen); }} className="p-1 rounded hover:bg-[#F9FAFB] outline-none text-[#212529] hover:text-[#017e84] transition-colors"><Icons.SlidersHorizontal size={14} /></button>
                 </div>
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#e7e9ed]">
            {rows.length > 0 ? rows.map((row: any, i: number) => (
              <tr key={row.id || i} onClick={() => window.location.href = `/app/${currentModel}/form/${row.id}`} className="hover:bg-[#F9FAFB] cursor-pointer group bg-white text-[14px] transition-colors">
                <td className="px-4 py-2 w-10" onClick={(e)=>e.stopPropagation()}><input type="checkbox" className="opacity-40 group-hover:opacity-100 cursor-pointer rounded border-[#d8dadd] text-[#017e84] focus:ring-[#017e84] w-[15px] h-[15px]"/></td>
                {activeColumns.map((col: any) => {
                  let content = extractDisplayValue(row[col.field]);
                  if (col.field === 'state') return <td key={col.field} className="px-3 py-2 text-right"><Badge name={col.field} data={row} /></td>;
                  if (col.type === 'bool' || col.type === 'boolean' || typeof row[col.field] === 'boolean') return <td key={col.field} className="px-3 py-2 text-center">{row[col.field] ? <Icons.CheckSquare className="text-[#017e84] mx-auto" size={16} /> : <Icons.Square className="text-[#d8dadd] mx-auto" size={16} />}</td>;
                  if (col.type === 'Avatar' || col.field === 'user_id') return <td key={col.field} className="px-3 py-2"><div className="flex items-center gap-2"><div className="w-5 h-5 rounded shadow-sm bg-[#5b5b88] text-white flex items-center justify-center text-[10px] font-bold">{getInitials(String(content))}</div><span className="text-[#212529] group-hover:text-[#017e84] transition-colors truncate max-w-[200px]">{content}</span></div></td>;
                  if (col.type === 'MonetaryInput') return <td key={col.field} className="px-3 py-2 text-right font-medium text-[#008784] truncate">S/ {safeNum(content).toLocaleString('en-US', {minimumFractionDigits: 2})}</td>;
                  return <td key={col.field} className="px-3 py-2 truncate max-w-[250px] text-[#212529]">{content || '-'}</td>;
                })}
                <td></td>
              </tr>
            )) : <tr><td colSpan={activeColumns.length + 2} className="py-16 text-center text-[#9a9ca5] italic text-[14px]">No hay registros</td></tr>}
          </tbody>
          {rows.length > 0 && (
            <tfoot className="bg-white font-bold text-[#111827] text-[14px] sticky bottom-0 z-20 shadow-[0_-1px_0_#d8dadd]">
              <tr><td className="px-4 py-3"></td>{activeColumns.map((col: any, idx: number) => col.type === 'MonetaryInput' ? <td key={idx} className="px-3 py-3 text-right truncate">S/ {rows.reduce((acc, row) => acc + safeNum(row[col.field]), 0).toLocaleString('en-US', {minimumFractionDigits: 2})}</td> : <td key={idx}></td>)}<td></td></tr>
            </tfoot>
          )}
        </table>
      </div>
    </div>
  );
};