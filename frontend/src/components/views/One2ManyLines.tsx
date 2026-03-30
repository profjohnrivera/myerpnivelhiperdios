// frontend/src/components/views/One2ManyLines.tsx
// ============================================================
// FIX 1: CÁLCULO AUTOMÁTICO (como Odoo 20)
//
// ANTES: handleCellChange solo actualizaba el estado local.
//   Precio unitario y subtotal nunca se recalculaban.
//
// AHORA:
//   - Cuando cambia product_id → llama /data/sale.order.line/onchange
//     → el backend retorna {price_unit, name, price_subtotal}
//   - Cuando cambia qty o price_unit → calcula price_subtotal
//     localmente (qty * price_unit) sin llamada al backend
//   - Después de cualquier cambio en una línea → recalcula
//     amount_total del padre sumando todos los subtotales
//
// FIX 2: DISEÑO PIXEL-PERFECT ODOO 20
//   - Columnas con anchos exactos
//   - Filas inline-editable con inputs sin borde hasta focus
//   - Botones de acción idénticos al original
//   - Totales con formato S/ correcto
// ============================================================
import React, { useState, useCallback } from 'react';
import * as Icons from 'lucide-react';
import { WidgetProps } from '../../types/sdui';
import { extractDisplayValue, AsyncMany2one } from '../fields/Many2OneLookup';
import api from '../../api/client';

// ── Helpers ──────────────────────────────────────────────────────────────────

const toFloat = (v: any): number => {
    if (v === null || v === undefined || v === '') return 0;
    const n = parseFloat(String(v));
    return isNaN(n) ? 0 : n;
};

const fmt = (n: number): string =>
    n.toLocaleString('es-PE', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

// Llama al endpoint onchange del hijo y retorna los campos actualizados
async function callLineOnchange(
    model: string,
    lineData: Record<string, any>,
    changedFields: string[]
): Promise<Record<string, any>> {
    try {
        const payload = { id: lineData.id, data: lineData, changed_fields: changedFields };
        const res = await api.post(`/data/${model}/onchange`, payload);
        return res.data || {};
    } catch {
        return {};
    }
}

// ── Componente principal ─────────────────────────────────────────────────────

export const One2ManyLines: React.FC<WidgetProps> = ({
    name,
    data_source,
    columns = [],
    data = {},
    onUpdate,
    onAction,
    readonly,
    comodel = 'sale.order.line',
}) => {
    const isReadonly = readonly;
    const targetField = data_source || name || 'order_line';
    const lines: any[] = data[targetField] || [];
    const [loadingRow, setLoadingRow] = useState<number | null>(null);
    const [activeRow, setActiveRow] = useState<number | null>(null);

    // Recalcular amount_total del padre a partir de los subtotales de líneas
    const recalcParentTotal = useCallback(
        (updatedLines: any[]) => {
            const total = updatedLines.reduce((sum, l) => {
                if (l.display_type) return sum;
                return sum + toFloat(l.price_subtotal);
            }, 0);
            onUpdate?.('amount_total', total);
        },
        [onUpdate]
    );

    const updateLines = useCallback(
        (updatedLines: any[]) => {
            onUpdate?.(targetField, updatedLines);
            recalcParentTotal(updatedLines);
        },
        [onUpdate, targetField, recalcParentTotal]
    );

    // Cambio en una celda cualquiera
    const handleCellChange = useCallback(
        async (idx: number, field: string, val: any) => {
            if (isReadonly) return;

            const newLines = lines.map((l, i) => (i === idx ? { ...l, [field]: val } : l));
            const line = newLines[idx];

            // ── CASO 1: Cambio de producto → onchange backend ──────────────
            if (field === 'product_id') {
                setLoadingRow(idx);
                try {
                    const linePayload = { ...line, product_id: Array.isArray(val) ? val[0] : val };
                    const result = await callLineOnchange(comodel, linePayload, ['product_id']);

                    // Aplicar campos retornados por el backend
                    const updated = { ...line };
                    if (result.price_unit !== undefined) updated.price_unit = result.price_unit;
                    if (result.name !== undefined && result.name) updated.name = result.name;
                    if (result.product_uom_qty !== undefined) updated.product_uom_qty = result.product_uom_qty;

                    // Calcular subtotal con el precio actualizado
                    const qty = toFloat(updated.product_uom_qty ?? 1);
                    const price = toFloat(updated.price_unit ?? 0);
                    updated.price_subtotal = qty * price;

                    newLines[idx] = updated;
                } finally {
                    setLoadingRow(null);
                }
            }
            // ── CASO 2: Cambio de cantidad o precio → cálculo local ─────────
            else if (field === 'product_uom_qty' || field === 'price_unit') {
                const qty   = field === 'product_uom_qty' ? toFloat(val) : toFloat(line.product_uom_qty ?? 1);
                const price = field === 'price_unit'      ? toFloat(val) : toFloat(line.price_unit ?? 0);
                newLines[idx] = { ...line, [field]: val, price_subtotal: qty * price };
            }

            updateLines(newLines);
        },
        [lines, isReadonly, comodel, updateLines]
    );

    const handleAddLine = (type: string | null = null) => {
        const newLine: any = {
            id: `new_${Date.now()}`,
            display_type: type,
            isNew: true,
            product_uom_qty: 1,
            price_unit: 0,
            price_subtotal: 0,
        };
        columns.forEach((c: any) => {
            if (!(c.field in newLine)) newLine[c.field] = '';
        });
        updateLines([...lines, newLine]);
    };

    const handleRemoveLine = (idx: number) => {
        updateLines(lines.filter((_, i) => i !== idx));
    };

    // ── Totales del pie ───────────────────────────────────────────────────────
    const subtotal = lines.reduce((s, l) => (!l.display_type ? s + toFloat(l.price_subtotal) : s), 0);
    const tax      = toFloat(data.amount_tax ?? 0);
    const total    = toFloat(data.amount_total ?? subtotal);

    // ── Estilos ───────────────────────────────────────────────────────────────
    const cellInput = (right = false) =>
        `w-full bg-transparent outline-none text-[13px] text-[#212529] py-1
         border-b border-transparent hover:border-[#b5b9c4] focus:border-[#017e84]
         transition-colors ${right ? 'text-right' : ''}`;

    return (
        <div className="w-full flex flex-col">
            {/* ── TABLA ─────────────────────────────────────────────────────── */}
            <table className="w-full text-left border-collapse">
                <thead>
                    <tr className="border-b-2 border-[#dee2e6]">
                        {/* drag handle */}
                        {!isReadonly && <th className="w-7" />}

                        {columns.map((col: any, i: number) => {
                            const right =
                                col.type === 'NumberInput' ||
                                col.type === 'MonetaryInput' ||
                                col.field === 'price_subtotal' ||
                                col.field === 'price_unit' ||
                                col.field === 'product_uom_qty';
                            return (
                                <th
                                    key={i}
                                    className={`py-2 px-2 font-bold text-[#212529] text-[13px] ${right ? 'text-right' : ''}`}
                                >
                                    {col.label}
                                </th>
                            );
                        })}

                        {/* delete btn col */}
                        {!isReadonly && <th className="w-9" />}
                    </tr>
                </thead>

                <tbody className="divide-y divide-[#dee2e6]">
                    {lines.map((line: any, idx: number) => (
                        <tr
                            key={line.id || idx}
                            className={`group relative transition-colors
                                ${line.display_type === 'line_section'
                                    ? 'bg-[#f8f9fa] font-semibold'
                                    : 'hover:bg-[#f8f9fa]'}`}
                            style={{ zIndex: activeRow === idx ? 50 : 1 }}
                            onMouseEnter={() => setActiveRow(idx)}
                            onMouseLeave={() => setActiveRow(null)}
                        >
                            {/* drag handle */}
                            {!isReadonly && (
                                <td className="w-7 text-center align-middle py-2 px-1">
                                    <Icons.GripVertical
                                        size={14}
                                        className="text-[#ced4da] opacity-0 group-hover:opacity-100 mx-auto cursor-move"
                                    />
                                </td>
                            )}

                            {/* Sección / nota */}
                            {line.display_type ? (
                                <td colSpan={columns.length} className="px-2 py-2 align-middle">
                                    <input
                                        className={`w-full bg-transparent outline-none border-b border-transparent
                                            focus:border-[#017e84] text-[13px] transition-colors
                                            ${line.display_type === 'line_section'
                                                ? 'font-semibold text-[#212529]'
                                                : 'italic text-[#6c757d]'}`}
                                        value={line.name || ''}
                                        onChange={(e) => handleCellChange(idx, 'name', e.target.value)}
                                        placeholder={
                                            line.display_type === 'line_section'
                                                ? 'Nombre de la sección'
                                                : 'Escriba una nota...'
                                        }
                                        readOnly={isReadonly}
                                    />
                                </td>
                            ) : (
                                columns.map((col: any, ci: number) => {
                                    const right =
                                        col.type === 'NumberInput' ||
                                        col.type === 'MonetaryInput' ||
                                        col.field === 'price_subtotal' ||
                                        col.field === 'price_unit' ||
                                        col.field === 'product_uom_qty';
                                    const isLoading = loadingRow === idx && col.field === 'price_unit';

                                    return (
                                        <td
                                            key={ci}
                                            className={`px-2 py-1.5 align-middle overflow-visible relative
                                                ${right ? 'text-right' : ''}`}
                                        >
                                            {col.type === 'Many2OneLookup' ? (
                                                <div className="relative overflow-visible">
                                                    <AsyncMany2one
                                                        value={extractDisplayValue(line[col.field])}
                                                        onChange={(val: any) =>
                                                            handleCellChange(idx, col.field, val)
                                                        }
                                                        relationModel={col.comodel}
                                                        isTableCell
                                                        hideControls={isReadonly}
                                                    />
                                                </div>
                                            ) : col.readonly || col.field === 'price_subtotal' ? (
                                                // Subtotal: solo lectura, formateado
                                                <span className="text-[13px] text-[#212529] block py-1 text-right">
                                                    {fmt(toFloat(line[col.field]))}
                                                </span>
                                            ) : (
                                                <div className="relative">
                                                    {isLoading && (
                                                        <Icons.Loader2
                                                            size={12}
                                                            className="absolute right-0 top-1/2 -translate-y-1/2 animate-spin text-[#017e84]"
                                                        />
                                                    )}
                                                    <input
                                                        type={right ? 'number' : 'text'}
                                                        className={cellInput(right)}
                                                        value={line[col.field] ?? ''}
                                                        readOnly={isReadonly}
                                                        onChange={(e) =>
                                                            handleCellChange(idx, col.field, e.target.value)
                                                        }
                                                        onBlur={(e) => {
                                                            // Al salir del campo qty/price, forzar recálculo
                                                            if (
                                                                col.field === 'product_uom_qty' ||
                                                                col.field === 'price_unit'
                                                            ) {
                                                                handleCellChange(idx, col.field, e.target.value);
                                                            }
                                                        }}
                                                    />
                                                </div>
                                            )}
                                        </td>
                                    );
                                })
                            )}

                            {/* delete */}
                            {!isReadonly && (
                                <td className="w-9 text-center align-middle py-2">
                                    <button
                                        onClick={() => handleRemoveLine(idx)}
                                        className="text-[#ced4da] hover:text-[#dc3545] opacity-0 group-hover:opacity-100 transition-all"
                                        title="Eliminar línea"
                                    >
                                        <Icons.Trash2 size={15} />
                                    </button>
                                </td>
                            )}
                        </tr>
                    ))}

                    {/* ── Botones de acción bajo la tabla ─────────────────── */}
                    {!isReadonly && (
                        <tr>
                            <td />
                            <td colSpan={columns.length} className="pt-3 pb-1 px-2">
                                <div className="flex items-center gap-4 flex-wrap">
                                    <button
                                        onClick={(e) => { e.preventDefault(); handleAddLine(); }}
                                        className="text-[#017e84] text-[13px] font-medium hover:text-[#01585c] transition-colors"
                                    >
                                        Agregar un producto
                                    </button>
                                    <button
                                        onClick={(e) => { e.preventDefault(); handleAddLine('line_section'); }}
                                        className="text-[#017e84] text-[13px] font-medium hover:text-[#01585c] transition-colors"
                                    >
                                        Agregar una sección
                                    </button>
                                    <button
                                        onClick={(e) => { e.preventDefault(); handleAddLine('line_note'); }}
                                        className="text-[#017e84] text-[13px] font-medium hover:text-[#01585c] transition-colors"
                                    >
                                        Agregar una nota
                                    </button>
                                    <button
                                        onClick={(e) => { e.preventDefault(); }}
                                        className="text-[#017e84] text-[13px] font-medium hover:text-[#01585c] transition-colors"
                                    >
                                        Catálogo
                                    </button>
                                </div>
                            </td>
                            <td />
                        </tr>
                    )}
                </tbody>
            </table>

            {/* ── BLOQUE DE TOTALES (pixel-perfect Odoo 20) ─────────────── */}
            <div className="flex justify-end mt-4 mb-2 px-2">
                <table className="text-[14px]" style={{ minWidth: 280 }}>
                    <tbody>
                        <tr>
                            <td className="text-[#6c757d] pr-8 py-[3px] text-right">Subtotal:</td>
                            <td className="text-right font-medium text-[#212529] min-w-[100px]">
                                S/ {fmt(subtotal)}
                            </td>
                        </tr>
                        {tax > 0 && (
                            <tr>
                                <td className="text-[#6c757d] pr-8 py-[3px] text-right">Impuestos:</td>
                                <td className="text-right font-medium text-[#212529]">
                                    S/ {fmt(tax)}
                                </td>
                            </tr>
                        )}
                        <tr className="border-t border-[#dee2e6]">
                            <td className="text-[#212529] font-semibold pr-8 pt-2 pb-1 text-right">
                                Total:
                            </td>
                            <td className="text-right font-bold text-[#212529] text-[15px] pt-2 pb-1">
                                S/ {fmt(tax > 0 ? total : subtotal)}
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>
    );
};