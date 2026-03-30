// frontend/src/pages/AppSwitcher.tsx
// ============================================================
// FIX 1: Doble "VENTAS" — El AppSwitcher solo muestra menús
//   raíz (is_category=True). La deduplicación real ocurre en
//   el backend (endpoints.py). Aquí filtramos correctamente.
//
// FIX 2: Páginas en blanco al clicar Contactos/Productos —
//   Cuando un menú raíz NO tiene action directa (es una
//   categoría que agrupa sub-menús), el AppSwitcher buscaba
//   una acción y al no encontrarla navegaba a /app/dashboard
//   → pantalla blanca.
//   SOLUCIÓN: Navegar al primer hijo que SÍ tenga action.
// ============================================================
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/client';
import * as Icons from 'lucide-react';

export const AppSwitcher: React.FC = () => {
    const [allMenus, setAllMenus] = useState<any[]>([]);
    const navigate = useNavigate();

    useEffect(() => {
        api.get('/ui/menu')
            .then(res => setAllMenus(res.data || []))
            .catch(err => console.error("Error cargando menús:", err));
    }, []);

    // Solo mostramos menús raíz (categorías de nivel 0)
    const rootApps = allMenus
        .filter((m: any) => m.is_category === true || m.is_category === 'True' || !m.parent_id)
        .sort((a: any, b: any) => (a.sequence || 100) - (b.sequence || 100));

    // Construir mapa de hijos por parent_id para navegación
    const getId = (m: any): string | null => {
        const rawId = m.id || m._id;
        return rawId != null ? String(rawId) : null;
    };

    const childrenOf = (parentId: string): any[] => {
        return allMenus.filter((m: any) => {
            const pid = m.parent_id;
            if (!pid) return false;
            const resolvedPid = Array.isArray(pid) ? String(pid[0]) : String(pid);
            return resolvedPid === parentId;
        }).sort((a: any, b: any) => (a.sequence || 100) - (b.sequence || 100));
    };

    // Encuentra el primer action navegable en el árbol de un nodo
    const findFirstAction = (menuId: string): string | null => {
        const children = childrenOf(menuId);
        for (const child of children) {
            const action = child.action;
            if (action && action !== 'null' && action !== 'undefined') {
                return action;
            }
            // Buscar recursivamente en nietos
            const childId = getId(child);
            if (childId) {
                const deeper = findFirstAction(childId);
                if (deeper) return deeper;
            }
        }
        return null;
    };

    const handleAppClick = (app: any) => {
        const appId = getId(app);
        if (!appId) return;

        sessionStorage.setItem('active_app_id', appId);
        window.dispatchEvent(new Event('app_changed'));

        // FIX 2: Si el menú raíz tiene acción directa, úsala.
        // Si no (es una categoría que agrupa sub-menús), busca el primer hijo con acción.
        const directAction = app.action && app.action !== 'null' && app.action !== 'undefined'
            ? app.action
            : null;

        const targetAction = directAction || findFirstAction(appId);

        if (targetAction) {
            navigate(`/app/${targetAction}/list`);
        } else {
            // Último recurso: mostrar el AppSwitcher interno (no dashboard vacío)
            // Solo navega al home del módulo — el TopNavBar mostrará sus sub-menús
            navigate('/app');
        }
    };

    return (
        <div className="flex-1 flex flex-col h-full bg-[#F3F4F6] overflow-y-auto">
            <div className="pt-12 pb-8 px-8 text-center">
                <h1 className="text-3xl font-bold text-[#111827] tracking-tight">
                    Hola, {sessionStorage.getItem('user_name') || 'Administrador'}
                </h1>
                <p className="text-[#6b7280] mt-2 text-sm">¿Qué quieres gestionar hoy?</p>
            </div>

            <div className="max-w-5xl mx-auto w-full px-8 pb-12">
                <div className="grid grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-6">
                    {rootApps.map(app => {
                        const IconComponent = (Icons as any)[app.icon] || Icons.Box;
                        return (
                            <button
                                key={app.id || app.name}
                                onClick={() => handleAppClick(app)}
                                className="flex flex-col items-center justify-center p-4 group transition-all"
                            >
                                <div className="w-[84px] h-[84px] rounded-2xl bg-white shadow-sm border border-[#e5e7eb] flex items-center justify-center mb-3 group-hover:shadow-sm group-hover:border-[#017e84] group-hover:-translate-y-1 transition-all duration-100">
                                    <IconComponent size={36} className="text-[#4b5563] group-hover:text-[#017e84] transition-colors" strokeWidth={1.5} />
                                </div>
                                <span className="text-[13px] font-medium text-[#374151] group-hover:text-[#111827] text-center">
                                    {app.name}
                                </span>
                            </button>
                        );
                    })}
                </div>
            </div>
        </div>
    );
};