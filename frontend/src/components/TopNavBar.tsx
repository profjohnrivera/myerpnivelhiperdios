// frontend/src/components/TopNavBar.tsx
import React, { useEffect, useState, useMemo, useRef } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import api from '../api/client';
import * as Icons from 'lucide-react';

// Hook auxiliar para cerrar al hacer clic fuera
const useOnClickOutside = (ref: any, handler: any) => {
    useEffect(() => {
        const listener = (event: any) => {
            if (!ref.current || ref.current.contains(event.target)) return;
            handler(event);
        };
        document.addEventListener('mousedown', listener);
        return () => document.removeEventListener('mousedown', listener);
    }, [ref, handler]);
};

export const TopNavBar: React.FC = () => {
    const [menus, setMenus] = useState<any[]>([]);
    const [activeAppId, setActiveAppId] = useState<string | null>(sessionStorage.getItem('active_app_id'));
    const [openDropdown, setOpenDropdown] = useState<string | null>(null);
    const navRef = useRef(null); // Ref para englobar la navegación y cerrar dropdowns
    
    const location = useLocation();
    const navigate = useNavigate();
    const userName = sessionStorage.getItem('user_name') || 'Admin';

    // Cierra el dropdown si se hace click fuera
    useOnClickOutside(navRef, () => setOpenDropdown(null));

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
        window.addEventListener('app_changed', handleAppChange);
        return () => window.removeEventListener('app_changed', handleAppChange);
    }, []);

    useEffect(() => {
        if (location.pathname === '/app' || location.pathname === '/app/') {
            sessionStorage.removeItem('active_app_id');
            setActiveAppId(null);
        } else if (!activeAppId && menus.length > 0) {
            const currentAction = location.pathname.split('/')[2];
            const currentMenu = menus.find(m => m.action === currentAction);
            if (currentMenu) {
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

    const activeAppMenus = activeAppId ? (menuTree[activeAppId] || []) : [];
    const activeAppDetails = menus.find(m => String(getId(m)) === activeAppId);

    return (
        <header className="h-[46px] w-full bg-[#714B67] flex items-center justify-between px-4 shadow-sm z-50 flex-shrink-0">
            
            <div className="flex items-center h-full gap-2" ref={navRef}>
                <Link to="/app" className="p-2 mr-2 text-white/90 hover:text-white hover:bg-white/10 rounded-[3px] transition-colors">
                    {/* SVG Odoo Original */}
                    <svg xmlns="http://www.w3.org/2000/svg" width="14px" height="14px" viewBox="0 0 14 14">
                        <g fill="currentColor">
                            <rect width="3" height="3" x="0" y="0"></rect><rect width="3" height="3" x="5" y="0"></rect><rect width="3" height="3" x="10" y="0"></rect>
                            <rect width="3" height="3" x="0" y="5"></rect><rect width="3" height="3" x="5" y="5"></rect><rect width="3" height="3" x="10" y="5"></rect>
                            <rect width="3" height="3" x="0" y="10"></rect><rect width="3" height="3" x="5" y="10"></rect><rect width="3" height="3" x="10" y="10"></rect>
                        </g>
                    </svg>
                </Link>

                {activeAppDetails && (
                    <span className="text-white font-semibold text-[15px] mr-6 hidden sm:block tracking-wide uppercase">
                        {activeAppDetails.name}
                    </span>
                )}

                {activeAppId && activeAppMenus.map(menu => {
                    const menuId = getId(menu)!;
                    const children = menuTree[menuId] || [];
                    const hasChildren = children.length > 0;

                    if (!hasChildren && menu.action) {
                        return (
                            <Link 
                                key={menuId}
                                to={`/app/${menu.action}/list`}
                                className="h-full px-3 flex items-center text-white/90 text-[14px] hover:bg-white/10 hover:text-white transition-colors"
                            >
                                {menu.name}
                            </Link>
                        );
                    }

                    // 🚀 ODOO 20 DROPDOWN: Se abre por CLICK, fondo blanco cuando está activo
                    return (
                        <div key={menuId} className="relative h-full flex items-center">
                            <button 
                                onClick={() => setOpenDropdown(openDropdown === menuId ? null : menuId)}
                                className={`h-full px-3 flex items-center text-[14px] transition-colors outline-none
                                    ${openDropdown === menuId 
                                        ? 'bg-white text-[#111827]' 
                                        : 'text-white/90 hover:bg-white/10 hover:text-white'
                                    }`}
                            >
                                {menu.name}
                            </button>

                            {openDropdown === menuId && (
                                // 🚀 MENÚ DESPLEGABLE: Fondo blanco, pegado al botón
                                <div className="absolute top-[46px] left-0 min-w-[200px] bg-white shadow-lg border border-[#d8dadd] border-t-0 rounded-b-[3px] py-1 flex flex-col z-[9999]">
                                    {children.map(child => {
                                        const actionName = child.action || child.model_name;
                                        if (!actionName || actionName === 'null') return null; 
                                        
                                        return (
                                            <Link
                                                key={getId(child)}
                                                to={`/app/${actionName}/list`}
                                                className="px-5 py-1.5 text-[14px] text-[#111827] hover:bg-[#F9FAFB] transition-colors whitespace-nowrap"
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

            {/* SECCIÓN DERECHA (Usuario) */}
            <div className="flex items-center h-full">
                <div className="flex items-center gap-2 px-3 h-full hover:bg-white/10 cursor-pointer transition-colors group relative">
                    <div className="w-6 h-6 rounded bg-[#e88134] text-white flex items-center justify-center text-[12px] font-bold shadow-sm">
                        {userName.charAt(0).toUpperCase()}
                    </div>
                    <span className="text-white/90 text-[13px] hidden md:block">
                        {userName}
                    </span>
                    
                    <div className="absolute top-[46px] right-0 w-[150px] bg-white shadow-lg border border-[#d8dadd] border-t-0 rounded-b-[3px] py-1 hidden group-hover:flex flex-col z-[9999]">
                        <button onClick={handleLogout} className="px-4 py-2 text-[14px] text-[#d44c59] text-left hover:bg-[#F9FAFB] transition-colors flex items-center">
                            <Icons.LogOut size={14} className="mr-2" /> Cerrar Sesión
                        </button>
                    </div>
                </div>
            </div>
        </header>
    );
};