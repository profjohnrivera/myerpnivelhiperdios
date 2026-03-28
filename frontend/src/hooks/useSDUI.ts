// frontend/src/hooks/useSDUI.ts
import { useState, useEffect, useCallback } from 'react';
import { SDUISchema } from '../types/sdui';

// 🛡️ IMPORTACIÓN CRÍTICA: Usamos el cliente unificado que lee de sessionStorage
import api from '../api/client'; 

// 💎 DICCIONARIO DE MUTACIÓN ESTRUCTURAL (Zero-Regex)
const componentMap: Record<string, string> = {
  "TableView": "DataGrid",
  "SubTable": "One2ManyLines",
  "Switch": "BooleanSwitch",
  "Monetary": "MonetaryInput",
  "LookupField": "Many2OneLookup",
  "Date": "DateInput",
  "Textarea": "TextArea"
};

// 💎 MUTADOR DE AST: Recorre el árbol de objetos y transforma los nodos de forma quirúrgica
const mutateAST = (node: any) => {
  if (!node || typeof node !== 'object') return;
  
  // Si el nodo tiene un tipo que está en nuestro diccionario, lo traducimos
  if (node.type && componentMap[node.type]) {
    node.type = componentMap[node.type];
  }
  
  // Exploramos recursivamente todas las ramas (children, pages, tabs, etc.)
  Object.keys(node).forEach(key => {
    if (Array.isArray(node[key])) {
      node[key].forEach(mutateAST);
    } else if (typeof node[key] === 'object' && node[key] !== null) {
      mutateAST(node[key]);
    }
  });
};

export const useSDUI = (modelName: string, viewType: string = 'list', recordId: string | undefined = undefined) => {
  const [schema, setSchema] = useState<SDUISchema | null>(null);
  const [data, setData] = useState<any>({});
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async (searchParams: any = {}) => {
    setLoading(true);
    try {
      // 🚀 Usamos la instancia 'api' para que el JWT se inyecte automáticamente
      const schemaRes = await api.get(`/ui/view/${modelName}?view_type=${viewType}`);
      
      // 🛠️ TRADUCTOR AUTOMÁTICO SEGURO (Fase 1: Estabilidad)
      const parsedSchema = schemaRes.data;
      mutateAST(parsedSchema); // Mutación pura en memoria sin tocar strings
      setSchema(parsedSchema);

      if (viewType === 'list') {
        const payload = { limit: 40, offset: 0, domain: [], ...searchParams };
        const dataRes = await api.post(`/data/${modelName}/search`, payload);
        setData({ data: dataRes.data });
      } else if (viewType === 'form' && recordId) {
        const dataRes = await api.get(`/data/${modelName}/${recordId}`);
        setData(dataRes.data || {});
      } else { 
        setData({}); 
      }
    } catch (e) { 
      console.error(e); 
    } finally { 
      setLoading(false); 
    }
  }, [modelName, viewType, recordId]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const updateField = (field: string, value: any) => { 
    setData((prev: any) => ({ ...prev, [field]: value })); 
  };

  const saveData = async (payloadOverride: any = null) => {
    const payloadToSave = JSON.parse(JSON.stringify(payloadOverride || data));
    
    // 🛡️ EL ESCUDO: Protege los textos de ser amputados
    const cleanValue = (val: any) => {
      if (Array.isArray(val)) {
          if (typeof val[0] === 'string' && val[0].length === 1 && String(val[1]).length > 1) return val[1];
          return val[0]; 
      }
      return val; 
    };

    Object.keys(payloadToSave).forEach(key => {
      if (Array.isArray(payloadToSave[key]) && typeof payloadToSave[key][0] === 'object') {
        payloadToSave[key] = payloadToSave[key].map((line: any) => {
          const cl = { ...line };
          Object.keys(cl).forEach(lk => { cl[lk] = cleanValue(cl[lk]); });
          return cl;
        });
      } else {
        payloadToSave[key] = cleanValue(payloadToSave[key]);
      }
    });

    const url = recordId ? `/${recordId}/write` : `/create`;
    // 🚀 Usamos la instancia 'api' para guardar datos con seguridad
    const res = await api.post(`/data/${modelName}${url}`, payloadToSave);
    return res.data;
  };

  return { schema, data, loading, updateField, refresh: fetchData, saveData };
};