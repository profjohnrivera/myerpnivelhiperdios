// frontend/src/components/widgets/ControlPanel.tsx
import React, { useState, useRef, useEffect } from 'react';
import * as Icons from 'lucide-react';

export const ControlPanel = ({ 
  title, 
  isNew, 
  onSave, 
  onDiscard, 
  onNew, 
  onDelete,
  onDuplicate,
  customActions = [], 
  readonly = false, 
  onPrev,
  onNext,
  currentPagerIndex = 1,
  totalPagerRecords = 1
}: any) => {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: any) => {
      if (menuRef.current && !menuRef.current.contains(event.target)) setIsMenuOpen(false);
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // ⚡ SDUI PURO: El backend dice qué hace la acción (toggle_active), no cómo se llama en la UI.
  const archiveAction = customActions.find((act: any) => act.name === 'toggle_active' || act.action === 'toggle_active');

  const isReadonly = readonly;

  return (
    <div className="flex flex-col w-full bg-white border-b border-[#d8dadd] sticky top-0 z-40 shadow-sm">
      <div className="flex items-center justify-between px-4 py-2 border-b border-gray-100">
        <div className="flex items-center gap-2 text-[14px]">
          <span className="text-[#714B67] font-semibold cursor-pointer hover:underline tracking-tight">Registros</span>
          <span className="text-gray-400">/</span>
          <span className="text-gray-800 font-bold tracking-tight">{isNew ? 'Nuevo' : title || 'Sin Nombre'}</span>
        </div>

        <div className="flex items-center gap-2">
          {!isNew && (
            <button onClick={onNew} className="text-gray-500 hover:text-[#714B67] p-1.5 rounded hover:bg-gray-100 transition-colors" title="Crear Nuevo">
              <Icons.Plus size={18} />
            </button>
          )}
          
          {!isNew && (
            <div className="relative ml-1" ref={menuRef}>
              <button 
                onClick={() => setIsMenuOpen(!isMenuOpen)} 
                className={`p-1.5 rounded transition-colors focus:outline-none flex items-center gap-1 ${isMenuOpen ? 'bg-gray-200 text-gray-900' : 'text-gray-500 hover:text-[#714B67] hover:bg-gray-100'}`}
              >
                <Icons.Settings size={18} />
              </button>
              
              {isMenuOpen && (
                <div className="absolute right-0 mt-1 w-44 bg-white border border-gray-200 shadow-xl rounded-[3px] py-1 z-50 text-[13px]">
                  <div className="px-4 py-1.5 text-[11px] font-bold text-gray-400 uppercase tracking-wider mb-1">Acciones</div>
                  {onDelete && (
                    <button onClick={() => { setIsMenuOpen(false); onDelete(); }} className="w-full text-left px-4 py-1.5 text-red-600 hover:bg-red-50 flex items-center gap-2 transition-colors">
                      <Icons.Trash2 size={14} /> Eliminar
                    </button>
                  )}
                  {archiveAction && (
                    <button onClick={() => { setIsMenuOpen(false); archiveAction.handler(); }} className="w-full text-left px-4 py-1.5 text-gray-700 hover:bg-gray-100 flex items-center gap-2 transition-colors">
                      <Icons.Archive size={14} /> {archiveAction.label || 'Archivar'}
                    </button>
                  )}
                  <button onClick={() => { setIsMenuOpen(false); onDuplicate?.(); }} className="w-full text-left px-4 py-1.5 text-gray-700 hover:bg-gray-100 flex items-center gap-2 transition-colors">
                    <Icons.Copy size={14} /> Duplicar
                  </button>
                </div>
              )}
            </div>
          )}

          {!isNew && (
            <div className="flex items-center text-gray-500 gap-1 ml-2 border-l border-gray-200 pl-3">
              <span className="text-[13px] mr-2 font-medium">{currentPagerIndex} / {totalPagerRecords}</span>
              <button onClick={onPrev} disabled={!onPrev} className="hover:bg-gray-100 p-1 rounded transition-colors disabled:opacity-30 cursor-pointer"><Icons.ChevronLeft size={18}/></button>
              <button onClick={onNext} disabled={!onNext} className="hover:bg-gray-100 p-1 rounded transition-colors disabled:opacity-30 cursor-pointer"><Icons.ChevronRight size={18}/></button>
            </div>
          )}
        </div>
      </div>

      {!isReadonly && (
        <div className="flex items-center px-4 py-2.5 bg-white">
          <div className="flex items-center gap-2">
              <button onClick={onSave} className="bg-[#714B67] text-white px-3 py-1.5 rounded-[3px] text-[13px] font-medium shadow-sm hover:bg-[#5A3C52] transition-colors flex items-center gap-1.5">
                 Guardar
              </button>
              <button onClick={onDiscard} className="bg-white text-gray-700 border border-[#d8dadd] px-3 py-1.5 rounded-[3px] text-[13px] font-medium hover:bg-gray-50 transition-colors flex items-center gap-1.5 shadow-sm">
                 Descartar
              </button>
          </div>
        </div>
      )}
    </div>
  );
};