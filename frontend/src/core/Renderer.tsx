// frontend/src/core/Renderer.tsx
import React from 'react';
import { COMPONENT_MAP } from './AtomicRegistry';
import { evaluateDomain } from './Evaluator'; // 🛡️ Importamos el motor seguro
import { SDUISchema, WidgetProps } from '../types/sdui';

interface RendererProps {
  schema: SDUISchema;
  data: Record<string, any>;
  onUpdate: (field: string, value: any) => void;
  onAction: (actionName: string, params?: any) => void;
}

export const RenderComponent: React.FC<RendererProps> = ({ schema, data, onUpdate, onAction }) => {
  if (!schema) return null;

  // ========================================================================
  // 🛡️ 1. EVALUACIÓN DE VISIBILIDAD (Cero XSS)
  // Si el backend envía un nodo antiguo <Condition>, lo evaluamos de forma segura
  // ========================================================================
  if (schema.type === 'Condition') {
      const domain = schema.props?.domain || []; 
      const isVisible = evaluateDomain(domain, data);
      
      if (!isVisible) return null; 
      
      return (
          <>
            {schema.children?.map((child, i) => (
                <RenderComponent key={i} schema={child} data={data} onUpdate={onUpdate} onAction={onAction} />
            ))}
          </>
      );
  }

  // ========================================================================
  // 🛡️ 2. EVALUACIÓN DE MODIFICADORES MODERNOS (Estilo Odoo)
  // El backend envía: { type: "Button", props: { modifiers: { invisible: [["state", "=", "done"]] } } }
  // ========================================================================
  if (schema.props?.modifiers?.invisible) {
      const isInvisible = evaluateDomain(schema.props.modifiers.invisible, data);
      if (isInvisible) return null; // Destruimos el nodo en memoria
  }

  // ========================================================================
  // 🔁 3. REPETIDORES (Listas / Tablas)
  // ========================================================================
  if (schema.type === 'Repeater') {
      const dataSourceField = schema.props?.data_source;
      const listData = Array.isArray(data[dataSourceField]) ? data[dataSourceField] : [];
      return (
          <div className="flex flex-col w-full border border-slate-200 rounded-lg overflow-hidden bg-white">
              {listData.map((rowData, rowIndex) => (
                  <div key={rowData.id || rowIndex} className="w-full border-b last:border-0 p-3 hover:bg-slate-50 transition-colors">
                      {schema.children?.map((child, i) => (
                          <RenderComponent 
                              key={i} 
                              schema={child} 
                              data={rowData} 
                              onUpdate={(field, val) => {
                                  const newList = [...listData];
                                  newList[rowIndex] = { ...newList[rowIndex], [field]: val };
                                  onUpdate(dataSourceField, newList);
                              }} 
                              onAction={onAction} 
                          />
                      ))}
                  </div>
              ))}
          </div>
      );
  }

  // ========================================================================
  // 🧩 4. ENSAMBLAJE DE ÁTOMOS
  // ========================================================================
  const Component = COMPONENT_MAP[schema.type];
  
  if (!Component) {
    console.warn(`⚠️ [SDUI] Átomo '${schema.type}' no encontrado.`);
    return <div className="text-red-500 bg-red-50 p-1 border border-red-200 text-xs rounded shadow-sm">Átomo Faltante: {schema.type}</div>;
  }

  // Evaluamos si el campo debe volverse Solo Lectura de forma dinámica
  let isReadonly = schema.props?.readonly || false;
  if (schema.props?.modifiers?.readonly) {
      isReadonly = evaluateDomain(schema.props.modifiers.readonly, data) || isReadonly;
  }

  // 💎 SOLUCIÓN AL ERROR ROJO: Extraemos 'key' explícitamente para que React no se enoje
  const { key, ...restProps } = schema.props || {};

  const widgetProps: WidgetProps = {
      ...restProps,
      readonly: isReadonly, 
      data,
      onUpdate,
      onAction
  };

  return (
    <Component key={key} {...widgetProps}>
      {schema.children && schema.children.map((child, i) => (
        <RenderComponent key={i} schema={child} data={data} onUpdate={onUpdate} onAction={onAction} />
      ))}
    </Component>
  );
};