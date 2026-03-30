// frontend/src/components/views/DataGrid.tsx
import React, { useState, useRef, useEffect } from 'react';
import * as Icons from 'lucide-react';
import api from '../../api/client';
import { WidgetProps } from '../../types/sdui';
import { Badge } from '../widgets/Badge';
import { useOnClickOutside, safeNum, extractDisplayValue, getInitials } from "../fields/Many2OneLookup";

// ============================================================
// 🔍 BARRA DE BÚSQUEDA GENÉRICA
// ============================================================
const AdvancedSearchBar = ({
    onFilterChange,
    hasStateField = false,
}: {
    onFilterChange: (facets: any[]) => void;
    hasStateField?: boolean;
}) => {
    const [isOpen, setIsOpen] = useState(false);
    const [query, setQuery] = useState('');
    const [activeFacets, setActiveFacets] = useState<any[]>([]);
    const ref = useRef(null);
    useOnClickOutside(ref, () => setIsOpen(false));

    const stateFilters = hasStateField ? [
        { id: 'draft',  label: 'Borrador',       domain: ['state', '=', 'draft'] },
        { id: 'sale',   label: 'Orden de venta',  domain: ['state', '=', 'sale'] },
        { id: 'done',   label: 'Completado',      domain: ['state', '=', 'done'] },
        { id: 'cancel', label: 'Cancelado',       domain: ['state', '=', 'cancel'] },
    ] : [];

    useEffect(() => { onFilterChange(activeFacets); }, [activeFacets]);

    const toggleFacet = (item: any, type: string) => {
        const exists = activeFacets.find(f => f.id === item.id && f.type === type);
        if (exists) setActiveFacets(activeFacets.filter(f => !(f.id === item.id && f.type === type)));
        else setActiveFacets([...activeFacets, { ...item, type }]);
    };

    const handleKeyDown = (e: any) => {
        if (e.key === 'Enter' && query.trim() !== '') {
            e.preventDefault();
            setActiveFacets([
                ...activeFacets,
                {
                    id: `search_${Date.now()}`,
                    label: query,
                    type: 'search',
                    domain: ['name', 'ilike', query],
                },
            ]);
            setQuery('');
            setIsOpen(false);
        }
    };

    const showDropdown = stateFilters.length > 0;

    return (
        <div className="relative w-full max-w-[650px]" ref={ref}>
            <div className="flex items-center w-full border border-[#d8dadd] rounded-[3px] bg-white shadow-sm focus-within:border-[#017e84] transition-colors min-h-[32px] py-[2px] pr-1">
                <div className="pl-3 pr-2 text-[#9a9ca5] flex-shrink-0">
                    <Icons.Search size={15} />
                </div>
                <div className="flex items-center flex-wrap gap-1.5 flex-1 h-full pl-1">
                    {activeFacets.map(facet => (
                        <div
                            key={`${facet.type}-${facet.id}`}
                            className="flex items-center bg-[#F9FAFB] border border-[#e7e9ed] text-[#374151] pl-2 pr-1 py-[2px] rounded-[2px] text-[12px] shadow-sm whitespace-nowrap"
                        >
                            <span className="font-medium mr-1">{facet.label}</span>
                            <div
                                className="flex items-center justify-center p-0.5 rounded-[2px] hover:bg-[#d8dadd] cursor-pointer transition-colors text-[#9a9ca5] hover:text-[#d44c59]"
                                onClick={(e) => {
                                    e.stopPropagation();
                                    setActiveFacets(activeFacets.filter(f => !(f.id === facet.id && f.type === facet.type)));
                                }}
                            >
                                <Icons.X size={12} strokeWidth={2.5} />
                            </div>
                        </div>
                    ))}
                    <input
                        type="text"
                        placeholder={activeFacets.length === 0 ? 'Buscar...' : ''}
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        onKeyDown={handleKeyDown}
                        onFocus={() => showDropdown && setIsOpen(true)}
                        className="flex-1 min-w-[100px] outline-none bg-transparent text-[14px] text-[#374151] h-full placeholder:text-[#9a9ca5] py-1 ml-1"
                    />
                </div>
                {showDropdown && (
                    <div
                        className="pl-2 border-l border-[#d8dadd] h-full flex items-center justify-center cursor-pointer hover:bg-[#F9FAFB] text-[#5f636f] rounded-r-[3px] transition-colors py-[6px] flex-shrink-0"
                        onClick={() => setIsOpen(!isOpen)}
                    >
                        <Icons.ChevronDown size={14} strokeWidth={2.5} />
                    </div>
                )}
            </div>

            {isOpen && showDropdown && (
                <div className="absolute left-0 top-full mt-1 w-full min-w-[280px] bg-white border border-[#d8dadd] shadow-2xl rounded-[3px] z-[100] text-[14px] max-h-[400px]">
                    <div className="p-2">
                        <div className="font-bold text-[#374151] flex items-center gap-1.5 mb-2 px-2 py-1.5">
                            <Icons.Filter size={15} className="text-[#9a9ca5]" /> Filtros
                        </div>
                        {stateFilters.map(f => {
                            const isActive = activeFacets.some(act => act.id === f.id && act.type === 'filter');
                            return (
                                <div
                                    key={f.id}
                                    onClick={() => toggleFacet(f, 'filter')}
                                    className="flex items-center px-2 py-1.5 hover:bg-[#F9FAFB] cursor-pointer rounded-[3px] transition-colors"
                                >
                                    <div className="w-5 flex justify-start mr-1">
                                        {isActive && <Icons.Check size={15} className="text-[#017e84]" />}
                                    </div>
                                    <span className={isActive ? 'font-medium text-[#111827]' : 'text-[#374151]'}>
                                        {f.label}
                                    </span>
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}
        </div>
    );
};

// ============================================================
// 📊 DATAGRID PRINCIPAL (CLON ODOO 20)
// ============================================================
export const DataGrid: React.FC<WidgetProps> = ({
    title,
    columns = [],
    data_source,
    onAction,
}) => {
    const currentModel = (() => {
        const parts = window.location.pathname.split('/').filter(Boolean);
        return parts[1] || '';
    })();

    const [rows, setRows] = useState<any[]>([]);
    const [totalRecords, setTotalRecords] = useState(0);
    const [loading, setLoading] = useState(false);
    const [currentPage, setCurrentPage] = useState(1);
    const limit = 40;
    const [sortConfig, setSortConfig] = useState<{ key: string | null; direction: 'asc' | 'desc' | null }>({ key: null, direction: null });
    const [activeDomain, setActiveDomain] = useState<any[]>([]);
    const [colWidths, setColWidths] = useState<Record<string, number>>({});
    const [visibleCols, setVisibleCols] = useState<string[]>([]);
    const [isColMenuOpen, setIsColMenuOpen] = useState(false);
    const colMenuRef = useRef(null);

    useOnClickOutside(colMenuRef, () => setIsColMenuOpen(false));

    const hasStateField = columns.some((c: any) => c.field === 'state');

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
            if (sortConfig.key && sortConfig.direction) {
                order_by = `${sortConfig.key} ${sortConfig.direction}`;
            }
            const payload = { domain: activeDomain, limit, offset, order_by };
            const res = await api.post(`/data/${currentModel}/search`, payload);

            if (Array.isArray(res.data)) {
                setRows(res.data);
                setTotalRecords(res.data.length);
            } else {
                const parsed = typeof res.data === 'string' ? JSON.parse(res.data) : res.data;
                setRows(parsed.data || []);
                setTotalRecords(parsed.total || 0);
            }
        } catch (e) {
            console.error('DataGrid fetch error:', e);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { setCurrentPage(1); }, [currentModel]);
    useEffect(() => { fetchServerData(); }, [currentModel, currentPage, sortConfig, activeDomain]);

    const handleSort = (field: string) => {
        let direction: 'asc' | 'desc' | null = 'asc';
        if (sortConfig.key === field && sortConfig.direction === 'asc') direction = 'desc';
        else if (sortConfig.key === field && sortConfig.direction === 'desc') {
            direction = null;
            field = '';
        }
        setSortConfig({ key: field || null, direction });
    };

    const startResize = (e: any, field: string) => {
        e.preventDefault();
        e.stopPropagation();
        const startX = e.pageX;
        const th = e.target.closest('th');
        const startWidth = th.offsetWidth;
        const onMouseMove = (moveEvent: any) => {
            const newWidth = Math.max(60, startWidth + (moveEvent.pageX - startX));
            th.style.width = `${newWidth}px`;
        };
        const onMouseUp = () => {
            document.removeEventListener('mousemove', onMouseMove);
            document.removeEventListener('mouseup', onMouseUp);
            setColWidths(prev => {
                const nw = { ...prev, [field]: th.offsetWidth };
                localStorage.setItem(`${currentModel}_col_widths`, JSON.stringify(nw));
                return nw;
            });
        };
        document.addEventListener('mousemove', onMouseMove);
        document.addEventListener('mouseup', onMouseUp);
    };

    const toggleColumnVisibility = (field: string) => {
        let newCols = [...visibleCols];
        if (newCols.includes(field)) newCols = newCols.filter(c => c !== field);
        else newCols.push(field);
        setVisibleCols(newCols);
        localStorage.setItem(`${currentModel}_visible_cols`, JSON.stringify(newCols));
    };

    const effectiveColumns = columns.length > 0 ? columns : [];
    const activeColumns = visibleCols.length > 0
        ? effectiveColumns.filter((col: any) => visibleCols.includes(col.field))
        : effectiveColumns;

    const totalPages = Math.max(1, Math.ceil(totalRecords / limit));
    const startIndex = (currentPage - 1) * limit;

    return (
        /* 🎨 FIX 1: bg-transparent para heredar el gris del App.tsx en toda la pantalla */
        <div className="flex flex-col w-full h-full min-h-0 min-w-0 bg-transparent">
            
            {/* Toolbar Principal */}
            <div className="flex justify-between items-center px-4 py-[10px] bg-white border-b border-[#d8dadd] flex-shrink-0 gap-8 z-40 relative">
                <div className="flex items-center gap-4 flex-shrink-0">
                    <button
                        onClick={() => onAction?.('new_record')}
                        className="bg-[#714B67] text-white px-3 py-[6px] rounded-[3px] font-medium shadow-sm hover:bg-[#624159] transition-colors"
                    >
                        Nuevo
                    </button>
                    <div className="text-[18px] text-[#374151] tracking-tight font-medium">
                        {title || 'Registros'}
                    </div>
                </div>

                <div className="flex-1 flex justify-end">
                    <AdvancedSearchBar
                        hasStateField={hasStateField}
                        onFilterChange={(facets) => {
                            setActiveDomain(facets.map(f => f.domain));
                            setCurrentPage(1);
                        }}
                    />
                </div>

                <div className="flex items-center gap-2 text-[#5f636f] flex-shrink-0">
                    <span className="text-[12px] font-medium mr-2">
                        {loading ? 'Cargando...' : `${startIndex + 1}-${Math.min(startIndex + rows.length, totalRecords)} / ${totalRecords}`}
                    </span>
                    <div className="flex gap-1 mr-3">
                        <button onClick={() => setCurrentPage(p => Math.max(1, p - 1))} disabled={currentPage === 1 || loading} className="hover:bg-gray-100 p-1 rounded transition-colors disabled:opacity-30"><Icons.ChevronLeft size={16} /></button>
                        <button onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))} disabled={currentPage === totalPages || loading} className="hover:bg-gray-100 p-1 rounded transition-colors disabled:opacity-30"><Icons.ChevronRight size={16} /></button>
                    </div>
                </div>
            </div>

            {/* 🎨 FIX 2: min-h-[350px] y pb-16. Esto fuerza a que el contenedor tenga espacio y NO CORTARÁ EL MENÚ nunca más */}
            <div className={`relative w-full flex-1 overflow-auto min-h-[350px] pb-16 bg-transparent transition-opacity ${loading ? 'opacity-50 pointer-events-none' : 'opacity-100'}`}>
                
                <table className="min-w-full text-left whitespace-nowrap table-fixed border-collapse text-[14px]">
                    <thead className="bg-[#F9FAFB]">
                        <tr>
                            <th className="w-10 px-4 py-[8px] bg-[#F9FAFB] sticky top-0 z-30 shadow-[inset_0_-1px_0_#d8dadd] text-black font-medium">
                                <input type="checkbox" className="rounded-[2px] cursor-pointer text-[#017e84] border-[#d8dadd]" />
                            </th>
                            {activeColumns.map((col: any) => (
                                <th
                                    key={col.field}
                                    onClick={() => handleSort(col.field)}
                                    style={{ width: colWidths[col.field] ? `${colWidths[col.field]}px` : (col.type === 'MonetaryInput' ? '115px' : 'auto') }}
                                    className={`relative px-3 py-[8px] hover:bg-[#eceef0] cursor-pointer select-none bg-[#F9FAFB] sticky top-0 z-30 group shadow-[inset_0_-1px_0_#d8dadd] text-black font-medium ${col.type === 'MonetaryInput' ? 'text-right' : ''}`}
                                >
                                    <div className={`flex items-center gap-1.5 ${col.type === 'MonetaryInput' ? 'justify-end' : ''}`}>
                                        <span className="truncate">{col.label}</span>
                                        {sortConfig.key === col.field && (sortConfig.direction === 'asc' ? <Icons.ArrowUp size={13} className="text-[#017e84]" /> : <Icons.ArrowDown size={13} className="text-[#017e84]" />)}
                                    </div>
                                    <div onMouseDown={(e) => startResize(e, col.field)} onClick={(e) => e.stopPropagation()} className="absolute right-0 top-0 bottom-0 w-[4px] cursor-col-resize hover:bg-[#d8dadd] opacity-0 group-hover:opacity-100 transition-opacity z-20" />
                                </th>
                            ))}
                            {/* Menú de columnas */}
                            <th className="w-10 px-2 py-[8px] text-right bg-[#F9FAFB] sticky top-0 z-30 shadow-[inset_0_-1px_0_#d8dadd] text-black font-medium">
                                <div ref={colMenuRef} className="relative inline-block text-left">
                                    <button onClick={(e) => { e.stopPropagation(); setIsColMenuOpen(!isColMenuOpen); }} className="p-1 rounded hover:bg-gray-200 text-[#5f636f] transition-colors"><Icons.SlidersHorizontal size={14} /></button>
                                    {isColMenuOpen && (
                                        <div className="absolute right-0 mt-2 w-48 bg-white border border-[#d8dadd] shadow-sm rounded-[3px] py-1 z-[100] text-[13px] text-left font-normal text-[#212529]">
                                            <div className="px-3 py-1.5 text-[11px] font-bold text-[#9a9ca5] uppercase tracking-wider border-b border-gray-50 mb-1">Columnas</div>
                                            <div className="max-h-[300px] overflow-y-auto">
                                                {effectiveColumns.map((col: any) => (
                                                    <label key={col.field} className="flex items-center px-3 py-1.5 hover:bg-[#F9FAFB] cursor-pointer gap-2">
                                                        <input type="checkbox" checked={visibleCols.includes(col.field)} onChange={() => toggleColumnVisibility(col.field)} className="rounded border-[#d8dadd] text-[#017e84]" />
                                                        <span className="truncate">{col.label}</span>
                                                    </label>
                                                ))}
                                            </div>
                                        </div>
                                    )}
                                </div>
                            </th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-[#e7e9ed] bg-white">
                        {rows.length > 0 ? rows.map((row: any, i: number) => (
                            <tr
                                key={row.id || i}
                                onClick={() => window.location.href = `/app/${currentModel}/form/${row.id}`}
                                className="hover:bg-[rgba(0,0,0,0.055)] cursor-pointer group transition-colors bg-white"
                            >
                                <td className="px-4 py-[5px] w-10" onClick={(e) => e.stopPropagation()}>
                                    <input type="checkbox" className="opacity-40 group-hover:opacity-100 cursor-pointer rounded border-[#d8dadd] text-[#017e84] w-[15px] h-[15px]" />
                                </td>
                                {activeColumns.map((col: any, colIdx: number) => {
                                    const rawVal = row[col.field];
                                    let content = extractDisplayValue(rawVal);
                                    const isFirstCol = colIdx === 0;

                                    if (col.field === 'state' || col.type === 'Badge') {
                                        return <td key={col.field} className="px-3 py-[5px]"><Badge name={col.field} data={row} options={col.options || []} /></td>;
                                    }
                                    
                                    if (col.type === 'Avatar' || col.field === 'user_id' || col.field === 'vendedor') {
                                        return (
                                            <td key={col.field} className="px-3 py-[5px]">
                                                <div className="flex items-center gap-2">
                                                    <div className="w-[22px] h-[22px] rounded-[3px] shadow-sm bg-[#e88134] text-white flex items-center justify-center text-[11px] font-bold">{getInitials(String(content))}</div>
                                                    <span className="text-[#374151] group-hover:text-[#017e84] transition-colors truncate max-w-[200px]">{content}</span>
                                                </div>
                                            </td>
                                        );
                                    }

                                    if (col.field === 'activity_ids' || col.label === 'Actividades') {
                                        return <td key={col.field} className="px-3 py-[5px]"><Icons.Clock size={15} className="text-[#9a9ca5] hover:text-[#017e84] transition-colors" /></td>;
                                    }

                                    if (col.type === 'MonetaryInput') {
                                        return <td key={col.field} className="px-3 py-[5px] text-right text-black font-medium truncate">S/ {safeNum(rawVal).toLocaleString('es-PE', { minimumFractionDigits: 2 })}</td>;
                                    }
                                    
                                    if (col.type === 'DateInput' || col.type === 'DateTimeInput' || col.field.includes('date')) {
                                        if (rawVal) {
                                            const d = new Date(rawVal);
                                            content = `${d.toLocaleDateString('es-PE', { day: 'numeric', month: 'short' })}, ${d.toLocaleTimeString('es-PE', { hour: 'numeric', minute: '2-digit', hour12: true }).toLowerCase()}`;
                                        }
                                    }

                                    return (
                                        <td key={col.field} className={`px-3 py-[5px] truncate max-w-[250px] ${isFirstCol ? 'text-black font-medium' : 'text-[#374151]'}`}>
                                            {content || '-'}
                                        </td>
                                    );
                                })}
                                <td />
                            </tr>
                        )) : (
                            <tr><td colSpan={activeColumns.length + 2} className="py-16 text-center text-[#9a9ca5] italic bg-white">No hay registros</td></tr>
                        )}
                    </tbody>
                    {/* 🎨 FIX 3: SIN SHADOW, SIN STICKY BOTTOM. Es un tfoot normal con un borde arriba */}
                    {rows.length > 0 && (
                        <tfoot className="bg-transparent font-medium text-black border-t border-[#d8dadd]">
                            <tr>
                                <td className="px-4 py-[8px]" />
                                {activeColumns.map((col: any, idx: number) =>
                                    col.type === 'MonetaryInput' ? (
                                        <td key={idx} className="px-3 py-[8px] text-right truncate">S/ {rows.reduce((acc, row) => acc + safeNum(row[col.field]), 0).toLocaleString('es-PE', { minimumFractionDigits: 2 })}</td>
                                    ) : <td key={idx} />
                                )}
                                <td />
                            </tr>
                        </tfoot>
                    )}
                </table>
            </div>
        </div>
    );
};