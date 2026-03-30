// frontend/src/components/ModelPlayer.tsx
import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useSDUI } from '../hooks/useSDUI';
import { RenderComponent } from '../core/Renderer';
import { ControlPanel } from '../components/widgets/ControlPanel'; 
import { SDUISchema } from '../types/sdui';
import api from '../api/client'; 
import * as Icons from 'lucide-react';

interface SearchConfig {
  relation: string;
  field: string;
  searchTerm?: string;
  label?: string;
}

const SearchModal: React.FC<{ config: SearchConfig, onClose: () => void, onSelect: (id: string, name: string) => void }> = ({ config, onClose, onSelect }) => {
  const [query, setQuery] = useState(config.searchTerm || '');
  const [results, setResults] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchResults = async (searchStr: string) => {
    setLoading(true);
    try {
      const payload = searchStr ? { domain: [['name', 'ilike', searchStr]], limit: 40 } : { limit: 40 };
      const res = await api.post(`/data/${config.relation}/search`, payload);
      setResults(Array.isArray(res.data) ? res.data : (res.data?.data || []));
    } catch (e) { console.error("Error", e); } 
    finally { setLoading(false); }
  };

  useEffect(() => { fetchResults(query); }, []);
  const handleSearch = (e: React.FormEvent) => { e.preventDefault(); fetchResults(query); };

  const extractColumns = () => {
    if (results.length === 0) return ['name'];
    const first = results[0];
    const keys = Object.keys(first).filter(k => k !== 'id' && !k.endsWith('_id') && !k.startsWith('x_') && typeof first[k] !== 'object');
    return keys.includes('name') ? ['name', ...keys.filter(k => k !== 'name')].slice(0,4) : keys.slice(0,4);
  };
  const cols = extractColumns();

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-[200] flex items-center justify-center p-4 sm:p-6 animate-in fade-in duration-200">
      <div className="bg-white rounded-[8px] shadow-2xl w-full max-w-[850px] max-h-[85vh] flex flex-col overflow-hidden animate-in zoom-in-95 duration-200">
        <div className="flex justify-between items-center px-6 py-4 border-b border-[#e5e7eb]">
          <h3 className="font-normal text-[#111827] text-[1.25rem] tracking-tight">Buscar: {config.label || config.relation}</h3>
          <button onClick={onClose} className="text-[#9ca3af] hover:text-[#111827] hover:bg-gray-100 p-1.5 rounded-[4px] transition-colors focus:outline-none focus:ring-2 focus:ring-[#714B67]/30">
            <Icons.X size={22} strokeWidth={1.5}/>
          </button>
        </div>
        <div className="p-4 border-b border-[#e5e7eb] bg-white">
          <form onSubmit={handleSearch} className="relative w-full">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <Icons.Search size={16} className="text-[#6b7280]" />
            </div>
            <input type="text" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Buscar..." autoFocus className="w-full bg-white border border-[#d1d5db] rounded-[4px] py-2 pl-10 pr-4 text-[14px] text-[#111827] focus:outline-none focus:ring-1 focus:ring-[#714B67] focus:border-[#714B67] transition-shadow shadow-sm" />
          </form>
        </div>
        <div className="flex-1 overflow-y-auto odoo-scrollbar bg-white min-h-[350px]">
          {loading ? ( 
              <div className="flex flex-col items-center justify-center h-full text-[#6b7280] py-20"><Icons.Loader2 size={32} className="animate-spin text-[#714B67] mb-3"/><span className="text-[14px] font-medium">Buscando registros...</span></div> 
          ) : results.length > 0 ? (
             <table className="w-full text-left whitespace-nowrap table-fixed">
                <thead className="border-b-2 border-[#e5e7eb] sticky top-0 bg-[#f9fafb] z-10"><tr>{cols.map(c => <th key={c} className="px-6 py-3 text-[#4b5563] font-bold text-[12px] uppercase tracking-wider">{c}</th>)}</tr></thead>
                <tbody className="divide-y divide-[#e5e7eb]">
                  {results.map((row, i) => (
                    <tr key={row.id || i} onClick={() => onSelect(row.id, row.name || row.id)} className="hover:bg-[#f3f4f6] cursor-pointer transition-colors">
                      {cols.map(c => (<td key={c} className="px-6 py-3 text-[14px] text-[#374151] truncate">{typeof row[c] === 'boolean' ? (row[c] ? <Icons.Check size={16} className="text-[#714B67]"/> : '') : row[c]}</td>))}
                    </tr>
                  ))}
                </tbody>
             </table>
          ) : ( <div className="flex flex-col items-center justify-center py-20 text-[#9ca3af]"><Icons.Inbox size={48} className="mb-3 opacity-30" strokeWidth={1} /><span className="text-[15px]">No se encontraron resultados</span></div> )}
        </div>
        <div className="border-t border-[#e5e7eb] px-6 py-4 flex items-center justify-start gap-2 bg-[#f9fafb]">
          <button onClick={() => window.open(`/app/${config.relation}/form`, '_blank')} className="bg-[#714B67] text-white border border-[#714B67] px-4 py-2 rounded-[4px] text-[14px] font-medium shadow-sm hover:bg-[#5c3d53] hover:border-[#5c3d53] transition-colors focus:ring-2 focus:ring-offset-2 focus:ring-[#714B67]">Crear Nuevo</button>
          <button onClick={onClose} className="bg-white text-[#374151] border border-[#d1d5db] px-4 py-2 rounded-[4px] text-[14px] font-medium shadow-sm hover:bg-[#f3f4f6] transition-colors">Cancelar</button>
        </div>
      </div>
    </div>
  );
};

export const ModelPlayer: React.FC = () => {
  const { modelName, viewType, id } = useParams<{ modelName: string, viewType: string, id?: string }>(); 
  const navigate = useNavigate();
  const { schema, data, loading, updateField, refresh } = useSDUI(modelName!, viewType, id);
  const [lookupConfig, setLookupConfig] = useState<SearchConfig | null>(null); 

  const listIdsRaw = sessionStorage.getItem(`${modelName}_list_ids`);
  const listIds = listIdsRaw ? JSON.parse(listIdsRaw) : [];
  let currentPagerIndex = 1;
  let totalPagerRecords = listIds.length || 1;
  let prevId: string | null = null;
  let nextId: string | null = null;

  if (id && listIds.length > 0) {
      const idx = listIds.indexOf(id);
      if (idx !== -1) {
          currentPagerIndex = idx + 1;
          if (idx > 0) prevId = listIds[idx - 1];
          if (idx < listIds.length - 1) nextId = listIds[idx + 1];
      }
  }

  const handlePrevRecord = prevId ? () => navigate(`/app/${modelName}/form/${prevId}`) : undefined;
  const handleNextRecord = nextId ? () => navigate(`/app/${modelName}/form/${nextId}`) : undefined;

  const handleStateUpdate = (key: string, value: any) => {
    if (typeof key === 'string' && key.includes('.')) {
      const parts = key.split('.');
      if (parts.length === 3) {
        const [arrayName, indexStr, fieldName] = parts;
        const index = parseInt(indexStr, 10);
        const currentArray = Array.isArray(data[arrayName]) ? [...data[arrayName]] : [];
        if (currentArray[index]) {
          currentArray[index] = { ...currentArray[index], [fieldName]: value };
          updateField(arrayName, currentArray);
          return;
        }
      }
    }
    updateField(key, value);
  };

  const sanitizePayload = (rawData: any) => {
    const cleaned = { ...rawData };
    Object.keys(cleaned).forEach(key => {
        const val = cleaned[key];
        if (Array.isArray(val) && val.length === 2 && (typeof val[0] === 'string' || typeof val[0] === 'number')) {
            cleaned[key] = String(val[0]); 
        } 
        else if (Array.isArray(val) && val.length > 0 && typeof val[0] === 'object') {
            cleaned[key] = val
                .filter((line: any) => line.product_id || line.name?.trim() || line.display_type)
                .map((line: any) => {
                    const newLine = { ...line };
                    Object.keys(newLine).forEach(lineKey => {
                        const lineVal = newLine[lineKey];
                        if (Array.isArray(lineVal) && lineVal.length === 2 && (typeof lineVal[0] === 'string' || typeof lineVal[0] === 'number')) {
                            newLine[lineKey] = String(lineVal[0]);
                        }
                    });
                    return newLine;
                });
        }
    });
    return cleaned;
  };

  const handleAction = async (actionName: string, params: any = {}) => {
    if (actionName === 'new_record') return navigate(`/app/${modelName}/form`); 
    if (actionName === 'open_record') return navigate(`/app/${modelName}/form/${params.id}`); 
    if (actionName === 'back' || actionName === 'discard') {
      if (id) window.location.reload(); else navigate(`/app/${modelName}/list`);
      return;
    }
    if (actionName === 'search_relation') return setLookupConfig(params);
    if (actionName === 'search_records') return refresh(params);
    
    if (actionName === 'add_line') {
      const fieldName = params.field;
      const currentLines = Array.isArray(data[fieldName]) ? [...data[fieldName]] : [];
      updateField(fieldName, [...currentLines, { id: `new_${Date.now()}`, isNew: true, product_uom_qty: 1.0, price_unit: 0.0, product_id: '' }]);
      return;
    }

    if (actionName === 'remove_line') {
      const { field, index, line } = params;
      const executeDelete = async () => {
        if (line && line.id && !String(line.id).startsWith('new_')) {
           const lineModel = field === 'order_line' ? 'sale.order.line' : '';
           if (lineModel) {
              try { await api.delete(`/data/${lineModel}/${line.id}`); } catch(e) { console.error("Error al borrar línea", e) }
           }
        }
        const currentLines = Array.isArray(data[field]) ? [...data[field]] : [];
        currentLines.splice(index, 1);
        updateField(field, currentLines);
      };
      executeDelete();
      return;
    }

    if (actionName === 'duplicate') {
       if (window.confirm("¿Deseas duplicar este registro?")) {
          const payloadToSave = sanitizePayload(data);
          delete payloadToSave.id;
          delete payloadToSave.name; 

          Object.keys(payloadToSave).forEach(key => {
             if (Array.isArray(payloadToSave[key]) && payloadToSave[key].length > 0 && typeof payloadToSave[key][0] === 'object') {
                 payloadToSave[key] = payloadToSave[key].map((line: any) => {
                     delete line.id; 
                     return line;
                 });
             }
          });

          try {
             const res = await api.post(`/data/${modelName}/create`, payloadToSave);
             if (res.data && res.data.data && res.data.data.id) {
                navigate(`/app/${modelName}/form/${res.data.data.id}`);
             }
          } catch (e: any) { alert(`❌ Error al duplicar: ${e.response?.data?.detail || e.message}`); }
       }
       return;
    }

    const performSave = async () => {
      const payloadToSave = sanitizePayload(data); 
      
      const endpoint = data?.id ? `/data/${modelName}/${data.id}/write` : `/data/${modelName}/create`; 
      const res = await api.post(endpoint, payloadToSave);
      if (res.data && res.data.status === 'error') throw new Error(res.data.detail);
      
      if (res.data?.data) {
        if (res.data.data.name) updateField('name', res.data.data.name);
        if (!id && res.data.data.id) navigate(`/app/${modelName}/form/${res.data.data.id}`, { replace: true });
      }
      return res.data;
    };

    if (actionName === 'save') {
      try { 
        await performSave(); 
        refresh(); 
      } catch (e) { 
        alert(`❌ Error al guardar. Revisa la consola para más detalles.`); 
      }
      return;
    }

    try {
      const saveResult = await performSave();
      const finalRecordId = saveResult?.data?.id || data?.id || id;
      
      if (finalRecordId && finalRecordId !== 'new') {
         const res = await api.post(`/data/${modelName}/${finalRecordId}/call/${actionName}`, params);
         const actionDict = res.data;

         if (actionDict && typeof actionDict === 'object' && actionDict.type) {
           switch (actionDict.type) {
             case 'ir.actions.act_window':
               navigate(`/app/${actionDict.res_model}/${actionDict.view_mode}/${actionDict.res_id || ''}`);
               break;
             case 'notification':
               alert(`✅ ${actionDict.title}: ${actionDict.message}`);
               refresh();
               break;
             case 'ir.actions.client':
               if (actionDict.tag === 'reload') refresh();
               else if (actionDict.tag === 'history_back') navigate(-1);
               break;
             default:
               refresh();
           }
         } else {
           refresh(); 
         }
      }
    } catch (err: any) { 
      const errorMsg = err.response?.data?.detail || err.message || "Error ejecutando acción de negocio";
      alert(`❌ Acción fallida: ${errorMsg}`);
      refresh(); 
    }
  };

  const handleDelete = async () => {
    if (window.confirm(`¿Estás seguro de eliminar este registro?`)) {
      try {
        await api.delete(`/data/${modelName}/${id}`);
        navigate(`/app/${modelName}/list`);
      } catch (error) { alert(`❌ Error al eliminar.`); }
    }
  };

  useEffect(() => {
    const interceptor = (e: any) => {
        if (e.detail?.action) {
            handleAction(e.detail.action, { id: data?.id || id });
        }
    };
    window.addEventListener('sdui_orphan_action', interceptor);
    return () => window.removeEventListener('sdui_orphan_action', interceptor);
  }, [data, id]);

  if (loading) return (
    <div className="flex-1 flex flex-col items-center justify-center bg-transparent min-h-screen w-full">
        <Icons.Loader2 size={40} className="animate-spin text-[#714B67] mb-4" />
        <span className="text-[#6b7280] text-[14px]">Cargando...</span>
    </div>
  );

  const currentId = data?.id || id;
  if (currentId === 'new') return (
      <div className="flex flex-col items-center justify-center h-screen w-full bg-transparent">
          <Icons.Loader2 size={40} className="animate-spin text-[#714B67] mb-4" />
      </div>
  );

  return (
    <div className="flex flex-col flex-1 h-full bg-[#F9FAFB] relative w-full text-[#111827] overflow-hidden">
      {viewType === 'form' && (
        <div className="flex-shrink-0 w-full bg-white z-20 border-b border-[#e5e7eb]">
            <ControlPanel 
              title={data?.name || data?.display_name || 'Nuevo'}
              isNew={!currentId}
              onSave={() => handleAction('save')}
              onDiscard={() => handleAction('discard')}
              onNew={() => handleAction('new_record')}
              onDelete={handleDelete}
              onDuplicate={() => handleAction('duplicate')} 
              state={data?.state}
              customActions={schema?.actions?.map((act: any) => ({ 
                  label: act.label, 
                  name: act.name,
                  variant: act.variant, 
                  handler: () => {
                      const actionMethod = act.name || act.method || act.action;
                      handleAction(actionMethod, { id: currentId });
                  }
              })) || []}
              onPrev={handlePrevRecord}
              onNext={handleNextRecord}
              currentPagerIndex={currentPagerIndex}
              totalPagerRecords={totalPagerRecords}
            />
        </div>
      )}
      
      {/* 🚀 FIX 1: bg-transparent cuando NO es form para dejar pasar el gris. */}
      <div className={`flex-1 overflow-y-auto odoo-scrollbar w-full animate-in fade-in duration-300 ${
          viewType === 'form' ? 'bg-[#F9FAFB] p-0 md:p-6 pb-24' : 'bg-transparent p-0'
      }`}>
         {/* 🚀 FIX 2: bg-transparent en vistas genericas (como lista). 
             Y para form view: Odoo 20 es flat, así que cambié shadow-[0_1px_3px_rgba(0,0,0,0.1)] por shadow-none y un borde del color exacto de odoo */}
         <div className={
            viewType === 'form' 
            ? "w-full md:max-w-[1140px] md:mx-auto bg-white md:rounded-[4px] md:shadow-none md:border border-[#d8dadd] min-h-full md:min-h-0" 
            : "w-full h-full bg-transparent"
         }>
            {schema && (
               <React.Suspense fallback={<div className="p-10 flex flex-col items-center justify-center text-[#9ca3af] animate-pulse"><Icons.Loader2 size={24} className="animate-spin text-[#714B67] mb-2"/><span>Ensamblando vista...</span></div>}>
                   <RenderComponent schema={schema} data={data} onUpdate={handleStateUpdate} onAction={handleAction} />
               </React.Suspense>
            )}
         </div>
      </div>
      
      {lookupConfig && (
        <SearchModal config={lookupConfig} onClose={() => setLookupConfig(null)} onSelect={(selectedId, selectedName) => { handleStateUpdate(lookupConfig.field, [selectedId, selectedName]); setLookupConfig(null); }} />
      )}
    </div>
  );
};