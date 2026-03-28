// src/core/components/LayoutAtoms.tsx
import React, { useState } from 'react';
import { WidgetProps } from '../types/sdui';

// ============================================================================
// 📦 CONTENEDOR GENÉRICO
// ============================================================================
export const Container: React.FC<WidgetProps> = ({ layout = 'col', gap = 2, padding = 0, children }) => {
    const layoutClass = layout === 'row' ? 'flex flex-row items-center flex-wrap' : layout === 'grid' ? 'grid grid-cols-1 lg:grid-cols-2 gap-x-8' : 'flex flex-col';
    return <div className={`${layoutClass} gap-${gap} p-${padding} w-full`}>{children}</div>;
};

// ============================================================================
// 📄 CARD / SHEET (La "Hoja" blanca del formulario Odoo 19)
// ============================================================================
export const Card: React.FC<WidgetProps> = ({ title, children, data }) => (
    // 🎨 Fondo exterior: --body-bg: #F9FAFB
    <div className="flex-1 overflow-visible pb-12 pt-4 bg-[#F9FAFB]">
      <div className="max-w-[1140px] w-full mx-auto px-4 lg:px-0">
        {/* 🎨 Fondo interior blanco, Borde: --border-color: #d8dadd */}
        <div className="bg-white shadow-sm border border-[#d8dadd] px-8 py-6 md:px-10 relative flex flex-col min-h-[500px] overflow-visible">
          <div className="mb-6 flex flex-col">
            {/* 🎨 Título H1: 2.1rem (34px) según CSS Odoo, Color: --gray-900: #111827 */}
            <h1 className="text-[34px] font-normal text-[#111827] tracking-tight leading-none mb-1">
                {data?.name || title || 'Nuevo'}
            </h1>
          </div>
          <div className="w-full">
            {children}
          </div>
        </div>
      </div>
    </div>
);

// ============================================================================
// 🧱 GROUP (Agrupación de campos en 2 columnas estilo Odoo)
// ============================================================================
export const Group: React.FC<WidgetProps> = ({ children }) => (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-x-12 gap-y-1 items-start w-full mb-6">
        {children}
    </div>
);

// ============================================================================
// 📑 NOTEBOOK (Pestañas Odoo 19 Enterprise)
// ============================================================================
export const Notebook: React.FC<WidgetProps> = ({ tabs = [], children }) => {
    const [activeTab, setActiveTab] = useState(0);
    const childrenArray = React.Children.toArray(children);
    
    return (
        <div className="w-full mt-4">
            {/* 🎨 Línea base de las pestañas: --border-color: #d8dadd */}
            <div className="flex border-b border-[#d8dadd] mb-0">
                {tabs.map((tab: string, idx: number) => {
                    const isActive = activeTab === idx;
                    return (
                        <button 
                            key={idx} 
                            onClick={() => setActiveTab(idx)} 
                            className={`
                                px-4 py-2.5 text-[13px] font-bold z-10 mb-[-1px] transition-colors focus:outline-none 
                                ${isActive 
                                    // 🎨 Pestaña Activa: Línea superior púrpura (#714B67), bordes laterales gris (#d8dadd), base blanca para tapar la línea del contenedor
                                    ? 'border-t-[3px] border-t-[#714B67] border-x border-x-[#d8dadd] border-b border-b-white bg-white text-[#111827]' 
                                    // 🎨 Pestaña Inactiva: Texto gris muteado (--gray-600: #5f636f), hover oscuro
                                    : 'border-t-[3px] border-transparent text-[#5f636f] hover:text-[#111827]'
                                }
                            `}
                        >
                            {tab}
                        </button>
                    )
                })}
            </div>
            
            {/* Contenido de la pestaña activa */}
            <div className="py-4 w-full bg-white">
                {childrenArray[activeTab]}
            </div>
        </div>
    );
};

// ============================================================================
// ➖ ELEMENTOS AUXILIARES
// ============================================================================

// 🎨 Divider exacto con --border-color: #d8dadd
export const Divider: React.FC = () => <hr className="w-full border-[#d8dadd] my-4" />;

export const Spacer: React.FC = () => <div className="flex-1 min-h-[1rem] min-w-[1rem]" />;