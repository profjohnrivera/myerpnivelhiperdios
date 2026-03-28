// frontend/src/components/widgets/Badge.tsx
import React from 'react';
import { WidgetProps } from '../../types/sdui';

// ============================================================================
// 🏷️ BADGE (Odoo 19 Enterprise Style + Traductor Inteligente)
// ============================================================================
export const Badge: React.FC<WidgetProps> = ({ field, name, data = {}, options = [] }) => {
    // 🐛 FIX: Soporta tanto 'field' como 'name' para que nunca más vuelva a desaparecer
    const targetField = field || name;
    const rawValue = data[targetField!];
    
    if (!rawValue) return null;

    // 1. TRADUCTOR INTELIGENTE: De valor BD a Etiqueta Humana
    let displayLabel = String(rawValue);
    
    if (options && options.length > 0) {
        const match = options.find((opt: any) => (Array.isArray(opt) ? opt[0] : opt.value) === rawValue);
        if (match) displayLabel = Array.isArray(match) ? match[1] : match.label;
    } else {
        // Diccionario universal por si el backend no envía las opciones
        const odooDictionary: Record<string, string> = {
            'draft': 'Cotización',
            'sent': 'Cotización enviada',
            'sale': 'Orden de venta',
            'done': 'Bloqueado',
            'cancel': 'Cancelado'
        };
        displayLabel = odooDictionary[String(rawValue)] || displayLabel;
    }

    // 2. PALETA DE COLORES EXACTA ODOO 19 ENTERPRISE
    const getOdooColor = (val: string) => {
        const key = String(val).toLowerCase();
        if (['sale', 'done'].includes(key)) 
            return 'bg-[#28a745] text-white'; // --success
        if (['draft', 'sent'].includes(key)) 
            return 'bg-[#17a2b8] text-white'; // --info
        if (['cancel'].includes(key)) 
            return 'bg-[#d44c59] text-white'; // --danger
        return 'bg-[#e7e9ed] text-[#111827]'; // --secondary-bg
    };

    return (
        <span 
            className={`
                inline-block 
                px-[8px] py-[3px] 
                text-[11.5px] font-medium 
                leading-none tracking-tight
                min-w-[3ch] 
                whitespace-nowrap 
                overflow-hidden 
                text-ellipsis 
                rounded-[100px] 
                border-0 
                align-middle
                transition-none
                ${getOdooColor(rawValue)}
            `}
            style={{ userSelect: 'none' }}
        >
            {displayLabel}
        </span>
    );
};