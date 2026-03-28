// src/core/sdui.ts
import { ReactNode } from 'react';

export interface SDUISchema {
  type: string;
  props?: Record<string, any>;
  children?: SDUISchema[];
}

export interface WidgetProps {
  label?: string;
  name?: string;
  data?: Record<string, any>;
  options?: any[]; 
  readonly?: boolean;
  placeholder?: string;
  onUpdate?: (field: string, value: any) => void;
  onAction?: (actionName: string, params?: Record<string, any>) => void;
  children?: ReactNode;
  [key: string]: any; 
}

export interface PluginManifest {
  widgets: Record<string, React.FC<WidgetProps>>;
}