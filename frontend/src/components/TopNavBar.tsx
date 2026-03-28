// frontend/src/components/TopNavBar.tsx
import React, { useEffect, useState, useMemo } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import api from '../api/client';
import * as Icons from 'lucide-react';

export const TopNavBar: React.FC = () => {
    const [menus, setMenus] = useState<any[]>([]);
    const [activeAppId, setActiveAppId] = useState<string | null>(sessionStorage.getItem('active_app_id'));
    const [openDropdown, setOpenDropdown] = useState<string | null>(null);
    
    const location = useLocation();
    const navigate = useNavigate();
    const userName = sessionStorage.getItem('user_name') || 'Admin';

    // 🚀 Lógica para detectar si el usuario volvió al Home o cambió de App
    useEffect(() => {
        const fetchMenus = () => {
            api.get('/ui/menu')
                .then(res => setMenus(res.data || []))
                .catch(err => console.error("Error cargando menús:", err));
        };

        const handleAppChange = () => {
            setActiveAppId(sessionStorage.getItem('active_app_id'));
        };

        fetchMenus();
        
        // Escuchamos el evento personalizado del AppSwitcher o cambios en la ruta
        window.addEventListener('app_changed', handleAppChange);
        return () => window.removeEventListener('app_changed', handleAppChange);
    }, []);

    // Si estamos en la raíz (/app) sin nada más, borramos la app activa
    useEffect(() => {
        if (location.pathname === '/app' || location.pathname === '/app/') {
            sessionStorage.removeItem('active_app_id');
            setActiveAppId(null);
        } else if (!activeAppId && menus.length > 0) {
            // Auto-detectar la app si alguien refresca la página (F5) dentro de un módulo
            const currentAction = location.pathname.split('/')[2];
            const currentMenu = menus.find(m => m.action === currentAction);
            if (currentMenu) {
                // Rastrear hasta la raíz
                let parent = currentMenu.parent_id;
                let rootId = currentMenu.id || currentMenu._id;
                while (parent) {
                    const parentId = Array.isArray(parent) ? parent[0] : parent;
                    rootId = parentId;
                    const parentMenu = menus.find(m => (m.id == parentId || m._id == parentId));
                    parent = parentMenu ? parentMenu.parent_id : null;
                }
                sessionStorage.setItem('active_app_id', String(rootId));
                setActiveAppId(String(rootId));
            }
        }
    }, [location.pathname, menus, activeAppId]);


    // 🚀 HASH MAP ESPACIAL (Reciclado de tu código anterior)
    const getId = (item: any): string | null => {
        if (!item) return null;
        const rawId = item.id || item._id || (Array.isArray(item) ? item[0] : item);
        return rawId != null ? String(rawId) : null;
    };

    const getParentId = (parentField: any): string | null => {
        if (!parentField) return null;
        if (Array.isArray(parentField)) return String(parentField[0]);
        if (typeof parentField === 'object') return String(parentField.id || parentField._id);
        return String(parentField);
    };

    const menuTree = useMemo(() => {
        const tree: Record<string, any[]> = { root: [] };
        menus.forEach(m => {
            const pid = getParentId(m.parent_id);
            const isRoot = m.is_category === true || m.is_category === 'True' || !pid;
            const key = isRoot ? 'root' : pid!;
            if (!tree[key]) tree[key] = [];
            tree[key].push(m);
        });
        Object.keys(tree).forEach(key => {
            tree[key].sort((a, b) => (a.sequence || 100) - (b.sequence || 100));
        });
        return tree;
    }, [menus]);

    const handleLogout = () => {
        sessionStorage.clear();
        navigate('/login');
    };

    // =========================================================================
    // 🎨 RENDERIZADOR DE DROPDOWNS (Odoo Style Top Bar)
    // =========================================================================
    const activeAppMenus = activeAppId ? (menuTree[activeAppId] || []) : [];
    const activeAppDetails = menus.find(m => String(getId(m)) === activeAppId);

    return (
        <header className="h-[46px] w-full bg-[#714B67] flex items-center justify-between px-4 shadow-sm z-50 flex-shrink-0">
            
            {/* ZONA IZQUIERDA: Botón Home y Submenús */}
            <div className="flex items-center h-full gap-2">
                
                {/* Botón Home (App Switcher Trigger) */}
                <Link to="/app" className="p-2 mr-2 text-white/90 hover:text-white hover:bg-white/10 rounded-[3px] transition-colors">
                    <Icons.Grid3X3 size={20} />
                </Link>

                {/* Título de la App Activa */}
                {activeAppDetails && (
                    <span className="text-white font-medium text-[15px] mr-6 hidden sm:block tracking-wide">
                        {activeAppDetails.name}
                    </span>
                )}

                {/* Submenús Horizontales (Solo se muestran si hay una App activa) */}
                {activeAppId && activeAppMenus.map(menu => {
                    const menuId = getId(menu)!;
                    const children = menuTree[menuId] || [];
                    const hasChildren = children.length > 0;

                    // Si NO tiene hijos, es un botón directo en la barra superior
                    if (!hasChildren && menu.action) {
                        return (
                            <Link 
                                key={menuId}
                                to={`/app/${menu.action}/list`}
                                className="h-full px-3 flex items-center text-white/90 text-[13px] hover:bg-white/10 hover:text-white transition-colors"
                            >
                                {menu.name}
                            </Link>
                        );
                    }

                    // Si TIENE hijos, es un Dropdown
                    return (
                        <div 
                            key={menuId} 
                            className="relative h-full flex items-center"
                            onMouseEnter={() => setOpenDropdown(menuId)}
                            onMouseLeave={() => setOpenDropdown(null)}
                        >
                            <button className={`h-full px-3 flex items-center text-[13px] transition-colors ${openDropdown === menuId ? 'bg-white/10 text-white' : 'text-white/90 hover:bg-white/10 hover:text-white'}`}>
                                {menu.name}
                            </button>

                            {/* El Menú Desplegable */}
                            {openDropdown === menuId && (
                                <div className="absolute top-[46px] left-0 min-w-[200px] bg-white shadow-xl border border-[#e5e7eb] rounded-b-[3px] py-1 flex flex-col">
                                    {children.map(child => {
                                        const actionName = child.action || child.model_name;
                                        if (!actionName || actionName === 'null') return null; // Ignoramos niveles 3 por ahora para mantener Odoo Style simple
                                        
                                        return (
                                            <Link
                                                key={getId(child)}
                                                to={`/app/${actionName}/list`}
                                                className="px-4 py-2 text-[13px] text-[#374151] hover:bg-[#f3f4f6] hover:text-[#017e84] transition-colors"
                                                onClick={() => setOpenDropdown(null)}
                                            >
                                                {child.name}
                                            </Link>
                                        );
                                    })}
                                </div>
                            )}
                        </div>
                    );
                })}
            </div>

            {/* ZONA DERECHA: Perfil */}
            <div className="flex items-center h-full">
                <div className="flex items-center gap-2 px-3 h-full hover:bg-white/10 cursor-pointer transition-colors group relative">
                    <div className="w-6 h-6 rounded-full bg-white/20 text-white flex items-center justify-center text-[11px] font-bold">
                        {userName.charAt(0).toUpperCase()}
                    </div>
                    <span className="text-white/90 text-[13px] hidden md:block">
                        {userName}
                    </span>
                    
                    {/* Dropdown del Perfil */}
                    <div className="absolute top-[46px] right-0 w-[150px] bg-white shadow-xl border border-[#e5e7eb] rounded-b-[3px] py-1 hidden group-hover:flex flex-col">
                        <button onClick={handleLogout} className="px-4 py-2 text-[13px] text-[#ef4444] text-left hover:bg-[#f3f4f6] transition-colors flex items-center">
                            <Icons.LogOut size={14} className="mr-2" /> Cerrar Sesión
                        </button>
                    </div>
                </div>
            </div>

        </header>
    );
};