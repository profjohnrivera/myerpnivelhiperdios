// frontend/src/components/AppSwitcher.tsx
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/client';
import * as Icons from 'lucide-react';

export const AppSwitcher: React.FC = () => {
    const [apps, setApps] = useState<any[]>([]);
    const navigate = useNavigate();

    useEffect(() => {
        api.get('/ui/menu')
            .then(res => {
                const menus = res.data || [];
                const rootApps = menus.filter((m: any) => 
                    m.is_category === true || m.is_category === 'True' || !m.parent_id
                );
                rootApps.sort((a: any, b: any) => (a.sequence || 100) - (b.sequence || 100));
                setApps(rootApps);
            })
            .catch(err => console.error("Error cargando aplicaciones:", err));
    }, []);

    const handleAppClick = (app: any) => {
        const appId = app.id || app._id || (Array.isArray(app) ? app[0] : app);
        sessionStorage.setItem('active_app_id', String(appId));
        
        // ⚡ SDUI PURO: Cero recursividad adivinadora. El backend debe proveer el punto de entrada.
        // Si no hay acción directa, abrimos el menú lateral por defecto y cargamos un dashboard vacío.
        const targetAction = app.action && app.action !== 'null' && app.action !== 'undefined' ? app.action : null;

        if (targetAction) {
            navigate(`/app/${targetAction}/list`);
        } else {
            // El backend no proveyó acción, dejamos que el layout pinte el menú lateral
            window.dispatchEvent(new Event('app_changed')); 
            navigate(`/app/dashboard`); // Ruta fallback genérica
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
                    {apps.map(app => {
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
                                <span className="text-[13px] font-medium text-[#374151] group-hover:text-[#111827]">
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