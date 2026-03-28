// frontend/src/components/views/One2ManyLines.tsx
import React, { useState } from 'react';
import * as Icons from 'lucide-react';
import { WidgetProps } from '../../types/sdui';
import { extractDisplayValue, AsyncMany2one } from '../fields/Many2OneLookup';

export const One2ManyLines: React.FC<WidgetProps> = ({ name, data_source, columns = [], data = {}, onUpdate, onAction, readonly }) => {
  const isReadonly = readonly;
  const targetField = data_source || name || 'order_line';
  const lines = data[targetField] || [];
  
  const [activeRow, setActiveRow] = useState<number | null>(null);

  const handleCellChange = (idx: number, field: string, val: any) => {
    if (isReadonly) return;
    const newLines = [...lines];
    newLines[idx] = { ...newLines[idx], [field]: val };
    onUpdate?.(targetField, newLines);
  };

  const handleAddLine = (type: string | null = null) => {
    const newLine: any = { id: `new_${Date.now()}`, display_type: type, isNew: true };
    columns.forEach((c: any) => { newLine[c.field] = c.field === 'product_uom_qty' ? 1 : (c.field === 'price_unit' ? 0 : ''); });
    onUpdate?.(targetField, [...lines, newLine]);
  };

  return (
    <div className="w-full flex flex-col overflow-visible">
      {/* Odoo 20 quita bordes laterales a la tabla */}
      <table className="min-w-full text-left border-collapse whitespace-nowrap table-fixed overflow-visible">
        <thead className="border-b-2 border-gray-200 bg-white">
          <tr>
            {!isReadonly && <th className="w-8 px-1"></th>}
            {columns.map((col: any, i: number) => {
              // Alinear a la derecha si es número o moneda
              const isRight = col.type?.includes('Number') || col.type?.includes('Monetary');
              return (
                <th key={i} className={`py-3 px-2 font-bold text-gray-800 text-[13px] ${isRight ? 'text-right' : ''}`}>
                  {col.label}
                </th>
              );
            })}
            {!isReadonly && <th className="w-10"></th>}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100 border-b border-gray-200">
          {lines.map((line: any, idx: number) => (
            <tr 
              key={line.id || idx} 
              className={`group transition-colors relative ${line.display_type === 'line_section' ? 'bg-gray-50 font-bold' : 'hover:bg-gray-50'}`}
              style={{ zIndex: activeRow === idx ? 50 : 1 }}
              onMouseEnter={() => setActiveRow(idx)}
              onMouseLeave={() => setActiveRow(null)}
              onFocus={() => setActiveRow(idx)}
            >
              {!isReadonly && <td className="text-center align-middle"><Icons.GripVertical size={14} className="text-gray-300 opacity-0 group-hover:opacity-100 mx-auto cursor-move" /></td>}
              
              {line.display_type ? (
                <td colSpan={columns.length} className="px-2 py-2 align-middle">
                  <input 
                    className={`w-full bg-transparent outline-none border-b border-transparent focus:border-teal-600 text-[13px] ${line.display_type === 'line_section' ? 'font-bold text-gray-900' : 'italic text-gray-500'}`}
                    value={line.name || ''} 
                    onChange={(e) => handleCellChange(idx, 'name', e.target.value)}
                    placeholder={line.display_type === 'line_section' ? "Nombre de la sección" : "Escriba una nota..."}
                    readOnly={isReadonly}
                  />
                </td>
              ) : (
                columns.map((col: any, ci: number) => {
                  const isRight = col.type?.includes('Number') || col.type?.includes('Monetary');
                  return (
                    <td key={ci} className={`px-2 py-2 align-middle overflow-visible relative ${isRight ? 'text-right' : ''}`}>
                      {col.type === 'Many2OneLookup' ? (
                        <AsyncMany2one 
                          value={extractDisplayValue(line[col.field])} 
                          onChange={(val: any) => handleCellChange(idx, col.field, val)}
                          relationModel={col.comodel} isTableCell={true} hideControls={isReadonly}
                        />
                      ) : (
                        <input 
                          type={isRight ? 'number' : 'text'}
                          className={`w-full bg-transparent outline-none border-b border-transparent hover:border-gray-200 focus:border-teal-600 text-[13px] text-gray-800 ${isRight ? 'text-right' : ''}`}
                          value={line[col.field] ?? ''}
                          readOnly={col.readonly || isReadonly}
                          onChange={(e) => handleCellChange(idx, col.field, e.target.value)}
                        />
                      )}
                    </td>
                  )
                })
              )}
              {!isReadonly && (
                <td className="text-center align-middle">
                  <button onClick={() => onUpdate?.(targetField, lines.filter((_:any, i:number) => i !== idx))} className="text-gray-400 hover:text-red-600 opacity-0 group-hover:opacity-100 transition-opacity"><Icons.Trash2 size={16}/></button>
                </td>
              )}
            </tr>
          ))}

          {/* ⚡ LA CEREZA DEL PASTEL: Botones idénticos a Odoo DENTRO de la tabla */}
          {!isReadonly && (
            <tr>
              <td className="w-8 px-1"></td> {/* Espacio del drag-handle */}
              <td colSpan={columns.length + 1} className="py-3 px-2 align-middle">
                <div className="flex items-center gap-4">
                  <button onClick={(e) => { e.preventDefault(); handleAddLine(); }} className="text-[#017e84] text-[13px] font-medium hover:text-[#01656a]">Agregar un producto</button>
                  <button onClick={(e) => { e.preventDefault(); handleAddLine('line_section'); }} className="text-[#017e84] text-[13px] font-medium hover:text-[#01656a]">Agregar una sección</button>
                  <button onClick={(e) => { e.preventDefault(); handleAddLine('line_note'); }} className="text-[#017e84] text-[13px] font-medium hover:text-[#01656a]">Agregar una nota</button>
                  <button onClick={(e) => { e.preventDefault(); }} className="text-[#017e84] text-[13px] font-medium hover:text-[#01656a]">Catálogo</button>
                </div>
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
};