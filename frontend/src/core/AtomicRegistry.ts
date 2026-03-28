// frontend/src/core/AtomicRegistry.ts
import React, { lazy } from 'react';
import { WidgetProps } from '../types/sdui';

// 🚀 MAGIA SDUI: Función auxiliar para importar dinámicamente exportaciones con nombre (export const)
const lazyComponent = (importFunc: () => Promise<any>, componentName: string) => {
    return lazy(() => importFunc().then(module => ({ default: module[componentName] })));
};

let REGISTRY: Record<string, React.LazyExoticComponent<React.FC<WidgetProps>>> = {
  // --- Estructura y Layout ---  
  "Container": lazyComponent(() => import('../components/LayoutAtoms'), 'Container'),
  "Card": lazyComponent(() => import('../components/LayoutAtoms'), 'Card'),
  "Notebook": lazyComponent(() => import('../components/LayoutAtoms'), 'Notebook'),
  "Divider": lazyComponent(() => import('../components/LayoutAtoms'), 'Divider'),
  "Spacer": lazyComponent(() => import('../components/LayoutAtoms'), 'Spacer'),
  "Group": lazyComponent(() => import('../components/LayoutAtoms'), 'Group'),
    
  // --- Entradas de Datos Básicas ---  
  "TextInput": lazyComponent(() => import('../components/fields/TextInput'), 'TextInput'),
  "TextArea": lazyComponent(() => import('../components/InputAtoms'), 'TextArea'),
  "NumberInput": lazyComponent(() => import('../components/fields/NumberInput'), 'NumberInput'),
  "MonetaryInput": lazyComponent(() => import('../components/fields/MonetaryInput'), 'MonetaryInput'),
  "DateInput": lazyComponent(() => import('../components/InputAtoms'), 'DateInput'),
  "DateTimeInput": lazyComponent(() => import('../components/InputAtoms'), 'DateTimeInput'),
  "SelectInput": lazyComponent(() => import('../components/fields/SelectInput'), 'SelectInput'),
  "BooleanSwitch": lazyComponent(() => import('../components/fields/BooleanSwitch'), 'BooleanSwitch'),
  "RadioGroup": lazyComponent(() => import('../components/InputAtoms'), 'RadioGroup'),
    
  // --- Multimedia y Firmas ---  
  "ImageUploader": lazyComponent(() => import('../components/InputAtoms'), 'ImageUploader'),
  "FileUploader": lazyComponent(() => import('../components/InputAtoms'), 'FileUploader'),
  "SignaturePad": lazyComponent(() => import('../components/InputAtoms'), 'SignaturePad'),
    
  // --- Relacionales y Colecciones (Vistas Maestras) ---  
  "DataGrid": lazyComponent(() => import('../components/views/DataGrid'), 'DataGrid'),
  "KanbanBoard": lazyComponent(() => import('../components/RelationalAtoms'), 'KanbanBoard'),
  "Many2OneLookup": lazyComponent(() => import('../components/fields/Many2OneLookup'), 'Many2OneLookup'),
  
  // 💎 EL FIX CRÍTICO QUE CAUSABA LA PANTALLA BLANCA:
  "One2ManyLines": lazyComponent(() => import('../components/views/One2ManyLines'), 'One2ManyLines'),
  
  "Many2ManyTags": lazyComponent(() => import('../components/RelationalAtoms'), 'Many2ManyTags'),
  "TagSelect": lazyComponent(() => import('../components/RelationalAtoms'), 'TagSelect'),
    
  // --- Visualización, Acción e IA ---  
  "Typography": lazyComponent(() => import('../components/DisplayAtoms'), 'Typography'),
  "Badge": lazyComponent(() => import('../components/DisplayAtoms'), 'Badge'),
  "Icon": lazyComponent(() => import('../components/DisplayAtoms'), 'Icon'),
  "Button": lazyComponent(() => import('../components/DisplayAtoms'), 'Button'),
  "StatButton": lazyComponent(() => import('../components/DisplayAtoms'), 'StatButton'),
  "StatusBar": lazyComponent(() => import('../components/DisplayAtoms'), 'StatusBar'),
  "ProgressBar": lazyComponent(() => import('../components/DisplayAtoms'), 'ProgressBar'),
  "Chatter": lazyComponent(() => import('../components/DisplayAtoms'), 'Chatter'),
  "AIPrediction": lazyComponent(() => import('../components/DisplayAtoms'), 'AIPrediction'),
};

// Carga dinámica de Plugins y Módulos Custom
const customPlugins = import.meta.glob('../../custom_widgets/**/index.tsx', { eager: true });
for (const path in customPlugins) {
    const plugin = customPlugins[path] as any;
    if (plugin && plugin.widgets) {
        REGISTRY = { ...REGISTRY, ...plugin.widgets };
    }
}

export const COMPONENT_MAP = REGISTRY;