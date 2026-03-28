// frontend/src/components/DisplayAtoms.tsx
import React from 'react';
import * as Icons from 'lucide-react';
import { WidgetProps } from '../types/sdui';

export const StatusBar: React.FC<WidgetProps> = ({ field, name, data = {}, options = [], onUpdate, onAction }) => {
  const targetField = field || name || 'state';
  const state = data[targetField] || 'draft';
  
  // ⚡ SDUI PURO: Cero contingencias. Renderizamos exactamente lo que envía el backend.
  const safeOptions = options || [];

  return (
    <div className="flex flex-col-reverse md:flex-row items-start md:items-center justify-between px-4 py-2.5 w-full bg-white border-b border-[#d8dadd] mb-6">
      
      {/* 🛠️ BOTONES (Para el SDUI Perfecto, estos deberían venir como Nodos hijos en el futuro, pero los mantenemos para no romper tu UI actual) */}
      <div className="flex gap-1.5 mt-2 md:mt-0">
        {(state === 'draft' || state === 'sent') && (
          <>
            <button 
              onClick={() => onAction?.('action_confirm')} 
              className="bg-[#714B67] text-white px-3 py-1.5 rounded-[3px] text-[14px] font-medium hover:bg-[#624159] transition-colors shadow-sm"
            >
              Confirmar
            </button>
            <button 
              onClick={() => onAction?.('action_confirm_async')} 
              className="bg-[#017e84] text-white px-3 py-1.5 rounded-[3px] text-[14px] font-medium hover:bg-[#01585c] transition-colors shadow-sm flex items-center gap-1"
            >
              <Icons.Zap size={14} /> Confirmar Masivo (Background)
            </button>

            <button 
              onClick={() => onAction?.('action_send_email')} 
              className="bg-[#e7e9ed] text-[#111827] px-3 py-1.5 rounded-[3px] text-[14px] font-medium hover:bg-[#d8dadd] transition-colors"
            >
              Enviar por correo
            </button>
            <button 
              onClick={() => onAction?.('action_cancel')} 
              className="bg-[#e7e9ed] text-[#111827] px-3 py-1.5 rounded-[3px] text-[14px] font-medium hover:bg-[#d8dadd] transition-colors"
            >
              Cancelar
            </button>
          </>
        )}

        {state === 'sale' && (
          <>
            <button 
              onClick={() => onAction?.('action_create_invoice')} 
              className="bg-[#714B67] text-white px-3 py-1.5 rounded-[3px] text-[14px] font-medium hover:bg-[#624159] transition-colors shadow-sm"
            >
              Crear factura
            </button>
            <button 
              onClick={() => onAction?.('action_send_email')} 
              className="bg-[#e7e9ed] text-[#111827] px-3 py-1.5 rounded-[3px] text-[14px] font-medium hover:bg-[#d8dadd] transition-colors"
            >
              Enviar por correo
            </button>
          </>
        )}

        {state === 'cancel' && (
          <button 
            onClick={() => onAction?.('action_draft')} 
            className="bg-[#e7e9ed] text-[#111827] px-3 py-1.5 rounded-[3px] text-[14px] font-medium hover:bg-[#d8dadd] transition-colors"
          >
            Volver a borrador
          </button>
        )}
      </div>
      
      {/* 🟢 BREADCRUMBS DE PROGRESO */}
      <div className="flex">
        <style>{`
          .odoo-ribbon {
            position: relative;
            display: flex;
            align-items: center;
            height: 32px;
            padding: 0 12px 0 24px;
            background-color: #F9FAFB;
            color: #5f636f;
            font-size: 13px;
            margin-left: -12px;
            cursor: default;
          }
          .odoo-ribbon:first-child {
            margin-left: 0;
            padding-left: 16px;
            border-top-left-radius: 3px;
            border-bottom-left-radius: 3px;
          }
          .odoo-ribbon:last-child {
            border-top-right-radius: 3px;
            border-bottom-right-radius: 3px;
            padding-right: 16px;
          }
          .odoo-ribbon::before, .odoo-ribbon::after {
            content: "";
            position: absolute;
            top: 0;
            border-style: solid;
            border-width: 16px 0 16px 12px;
          }
          .odoo-ribbon::before {
            right: -12px;
            border-color: transparent transparent transparent #F9FAFB;
            z-index: 10;
          }
          .odoo-ribbon::after {
            right: -13px;
            border-color: transparent transparent transparent #ffffff;
            z-index: 9;
          }
          .odoo-ribbon:last-child::before, .odoo-ribbon:last-child::after {
            display: none;
          }
          .odoo-ribbon.active {
            background-color: #e6f2f3;
            color: #111827;
            border-top: 1px solid #017e84;
            border-bottom: 1px solid #017e84;
          }
          .odoo-ribbon.active:first-child { border-left: 1px solid #017e84; }
          .odoo-ribbon.active:last-child { border-right: 1px solid #017e84; }
          .odoo-ribbon.active::before {
            border-left-color: #e6f2f3;
          }
        `}</style>
        <ul className="flex list-none p-0 m-0">
          {safeOptions.map((opt: any, idx: number) => {
            const optValue = Array.isArray(opt) ? opt[0] : opt.value;
            const optLabel = Array.isArray(opt) ? opt[1] : opt.label;
            const isActive = state === optValue;
            
            return (
              <li 
                key={optValue} 
                style={{ zIndex: safeOptions.length - idx }} 
                className={`odoo-ribbon ${isActive ? 'active font-medium' : ''}`}
              >
                {optLabel}
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
};

export const Badge: React.FC<WidgetProps> = ({ field, name, data = {}, options = [] }) => {
    const targetField = field || name;
    const rawValue = data[targetField!];
    if (!rawValue) return null;

    // ⚡ SDUI PURO: Cero adivinanzas. Leemos las opciones del esquema y el color enviado por backend.
    let displayLabel = String(rawValue);
    let colorClass = 'bg-[#e7e9ed] text-[#111827]'; // default
    
    if (options && options.length > 0) {
        const match = options.find((opt: any) => (Array.isArray(opt) ? opt[0] : opt.value) === rawValue);
        if (match) {
             displayLabel = Array.isArray(match) ? match[1] : match.label;
             if (!Array.isArray(match) && match.color) {
                 if (match.color === 'success') colorClass = 'bg-[#28a745] text-white';
                 if (match.color === 'info') colorClass = 'bg-[#17a2b8] text-white';
                 if (match.color === 'danger') colorClass = 'bg-[#d44c59] text-white';
             }
        }
    }

    return (
        <span 
            className={`inline-block px-[8px] py-[3px] text-[11.5px] font-medium leading-none tracking-tight min-w-[3ch] whitespace-nowrap overflow-hidden text-ellipsis rounded-[100px] border-0 align-middle transition-none ${colorClass}`}
            style={{ userSelect: 'none' }}
        >
            {displayLabel}
        </span>
    );
};

// ============================================================================
// 📊 OTROS COMPONENTES INTACTOS
// ============================================================================

export const Typography: React.FC<WidgetProps> = ({ content, field, data = {}, variant = 'body' }) => {
    const text = field ? data[field] : content;
    const sizeClass = variant === 'h1' ? 'text-[36px] tracking-tight leading-tight text-[#212529] font-normal' : variant === 'h2' ? 'text-xl font-medium' : 'text-[14px]';
    return <span className={`${sizeClass} block mb-1`}>{text}</span>;
};

export const Icon: React.FC<WidgetProps> = ({ icon_name, size = 16, color = "slate-500" }) => {
    const LucideIcon = (Icons as any)[icon_name] || Icons.HelpCircle;
    return <LucideIcon size={size} className={`text-${color} inline-block`} />;
};

export const Button: React.FC<WidgetProps & { method?: string, action?: string }> = ({ label, action_id, name, method, action, onAction, variant = 'primary', icon, invisible }) => {
    if (invisible === true || invisible === 'True') return null;

    const targetAction = action_id || name || method || action;
    const LucideIcon = icon ? (Icons as any)[icon] : null;
    const bgClass = variant === 'primary' ? 'bg-[#714B67] text-white hover:bg-[#624159] border-transparent' : 'bg-[#F9FAFB] text-[#212529] border border-[#d8dadd] hover:bg-[#e7e9ed]';
    
    return (
        <button 
            onClick={(e) => {
                e.preventDefault();
                if (targetAction) {
                    if (onAction) {
                        onAction(targetAction);
                    } else {
                        window.dispatchEvent(new CustomEvent('sdui_orphan_action', { 
                            detail: { action: targetAction } 
                        }));
                    }
                } else {
                    console.warn("⚠️ Botón sin acción detectada:", label);
                }
            }} 
            className={`flex items-center justify-center gap-2 px-3 py-1.5 rounded-[3px] text-[14px] font-medium transition-all shadow-sm ${bgClass}`}
        >
            {LucideIcon && <LucideIcon size={14} />}
            {label}
        </button>
    );
};

export const StatButton: React.FC<WidgetProps & { method?: string, action?: string }> = ({ label, icon, field, data = {}, action_id, name, method, action, onAction, invisible }) => {
    if (invisible === true || invisible === 'True') return null;
    
    const targetAction = action_id || name || method || action;
    const LucideIcon = icon ? (Icons as any)[icon] : Icons.Activity;
    
    return (
        <button 
            onClick={(e) => { 
                e.preventDefault(); 
                if (targetAction) {
                    if (onAction) {
                        onAction(targetAction);
                    } else {
                        window.dispatchEvent(new CustomEvent('sdui_orphan_action', { 
                            detail: { action: targetAction } 
                        }));
                    }
                } 
            }} 
            className="flex items-center gap-3 p-3 bg-white border border-[#d8dadd] rounded-[3px] hover:bg-[#F9FAFB] transition-all shadow-sm h-[60px] min-w-[140px]"
        >
            <LucideIcon size={20} className="text-[#714B67]" />
            <div className="flex flex-col items-start leading-tight">
                <span className="font-bold text-lg text-[#111827]">{data[field!] || 0}</span>
                <span className="text-[10px] font-bold text-[#5f636f] uppercase tracking-tighter">{label}</span>
            </div>
        </button>
    );
};

export const ProgressBar: React.FC<WidgetProps> = ({ label, field, data = {} }) => {
    const progress = Number(data[field!]) || 0;
    return (
        <div className="w-full flex flex-col gap-1 mb-4">
            <div className="flex justify-between text-[11px] font-bold text-[#5f636f] uppercase">
                <span>{label}</span>
                <span>{progress}%</span>
            </div>
            <div className="w-full bg-[#e7e9ed] rounded-full h-2 overflow-hidden shadow-inner">
                <div className="bg-[#714B67] h-2 rounded-full transition-all duration-500" style={{ width: `${progress}%` }}></div>
            </div>
        </div>
    );
};

export const Chatter: React.FC<WidgetProps> = () => (
    <div className="w-full mt-8 border-t border-[#d8dadd] pt-6">
        <h3 className="font-bold text-[#111827] text-[14px] mb-4 flex items-center gap-2"><Icons.MessageSquare size={16}/> Historial y Comunicación</h3>
        <div className="bg-[#F9FAFB] border border-[#d8dadd] rounded-[3px] p-4 flex flex-col gap-4">
            <div className="flex gap-3">
                <div className="w-8 h-8 rounded-full bg-[#714B67] text-white flex items-center justify-center font-bold text-xs shadow-sm">SYS</div>
                <div className="bg-white p-3 rounded-[3px] border border-[#d8dadd] shadow-sm w-full">
                    <p className="text-[14px] text-[#111827]">Cambios sincronizados en el servidor.</p>
                    <span className="text-[11px] text-[#5f636f]">Recién actualizado</span>
                </div>
            </div>
            <div className="relative mt-2">
                <input type="text" placeholder="Escribe un mensaje..." className="w-full bg-white border border-[#d8dadd] rounded-[3px] py-2 pl-3 pr-10 text-[14px] focus:outline-none focus:border-[#017e84] shadow-sm transition-colors"/>
                <button className="absolute right-2 top-1/2 -translate-y-1/2 text-[#9a9ca5] hover:text-[#017e84] transition-colors"><Icons.Send size={16}/></button>
            </div>
        </div>
    </div>
);

export const AIPrediction: React.FC<WidgetProps> = ({ message }) => (
    <div className="w-full mb-4 bg-[#f8f0f6] border border-[#e0c8d6] rounded-[3px] p-3 flex items-start gap-3 shadow-sm">
        <Icons.Sparkles size={16} className="text-[#714B67] mt-0.5 animate-pulse" />
        <div>
            <h4 className="text-[11px] font-bold text-[#714B67] uppercase tracking-tight mb-0.5">Sugerencia HiperDios AI</h4>
            <p className="text-[13px] text-[#4a3244]">{message || "Analizando el contexto del registro..."}</p>
        </div>
    </div>
);