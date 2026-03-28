// frontend/src/components/Sidebar.tsx
import React, { useEffect, useState, useMemo } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import api from '../api/client';
import * as Icons from 'lucide-react';

export const Sidebar: React.FC = () => {
    const [menus, setMenus] = useState<any[]>([]);
    const location = useLocation();
    const navigate = useNavigate();
    
    const userName = sessionStorage.getItem('user_name') || 'Administrador';

    useEffect(() => {
        api.get('/ui/menu')
            .then(res => setMenus(res.data || []))
            .catch(err => console.error("Error cargando menús:", err));
    }, []);

    const getId = (item: any): string | null => {
        if (!item) return null;
        const rawId = item.id || item._id || (Array.isArray(item) ? item[0] : item);
        return rawId != null ? String(rawId) : null;
    };

    const getParentId = (parentField: any): string | null => {
        if (!parentField) return null;
        if (Array.isArray(parentField)) return String(parentField[0]);
        if (typeof parentField === 'object') {
            const rawId = parentField.id || parentField._id;
            return rawId != null ? String(rawId) : null;
        }
        return String(parentField);
    };

    const handleLogout = () => {
        sessionStorage.clear();
        navigate('/login');
    };

    // 🚀 HASH MAP ESPACIAL O(1) (Fase 2: Rendimiento Nivel Dios)
    // Pre-procesamos la jerarquía completa 1 sola vez cuando los menús cambian
    const menuTree = useMemo(() => {
        const tree: Record<string, any[]> = { root: [] };
        
        menus.forEach(m => {
            const pid = getParentId(m.parent_id);
            // Si es categoría o no tiene padre, va a la raíz
            const isRoot = m.is_category === true || m.is_category === 'True' || !pid;
            const key = isRoot ? 'root' : pid!;
            
            if (!tree[key]) tree[key] = [];
            tree[key].push(m);
        });

        // Ordenamos cada nodo previamente para no gastar CPU durante el render
        Object.keys(tree).forEach(key => {
            tree[key].sort((a, b) => (a.sequence || 100) - (b.sequence || 100));
        });

        return tree;
    }, [menus]);

    const rootCategories = menuTree['root'] || [];

    // --- 🏗️ MOTOR DE JERARQUÍA O(1) ---
    const renderMenuLevel = (parentId: string, level: number = 1) => {
        // 💎 Ya no iteramos TODO el array. Solo sacamos los hijos del Hash Map instantáneamente.
        const children = menuTree[parentId] || [];

        if (children.length === 0) return null;

        return (
            <div className={level === 1 ? "space-y-0.5" : "ml-4 mt-1 border-l border-[#1f2937] space-y-0.5 pl-1"}>
                {children.map(child => {
                    const actionName = child.action || child.model_name;

                    // 📁 SI NO TIENE ACCIÓN, ES UNA CARPETA (Nivel 2 o más)
                    if (!actionName || actionName === 'null' || actionName === 'undefined') {
                        const grandChildren = renderMenuLevel(getId(child)!, level + 1);
                        if (!grandChildren) return null; 

                        return (
                            <div key={getId(child)} className="mb-2 mt-2">
                                <div className="px-5 py-1 text-[11px] font-bold text-[#6b7280] flex items-center tracking-wide uppercase">
                                    <Icons.ChevronRight size={12} className="mr-2 opacity-50" />
                                    {child.name}
                                </div>
                                {grandChildren}
                            </div>
                        );
                    }

                    // 📄 SI TIENE ACCIÓN, ES UN LINK (Nivel Hoja)
                    const targetPath = `/app/${actionName}/list`;
                    const IconComponent = (Icons as any)[child.icon] || Icons.Circle;
                    const isActive = location.pathname.includes(`/app/${actionName}/`);

                    return (
                        <Link 
                            key={getId(child)} 
                            to={targetPath}
                            className={`w-full flex items-center px-5 py-2 text-[13px] transition-all duration-200 group border-l-[3px] ${
                                isActive 
                                    ? 'bg-[#1f2937] text-white font-medium border-[#017e84] shadow-inner' 
                                    : 'hover:bg-[#1f2937]/50 hover:text-white border-transparent text-[#9a9ca5]'
                            }`}
                        >
                            <IconComponent 
                                size={15} 
                                className={`mr-3 transition-colors ${isActive ? 'text-[#017e84]' : 'text-[#4b5563] group-hover:text-[#9a9ca5]'}`} 
                            />
                            <span className="truncate">{child.name}</span>
                            {isActive && (
                                <div className="ml-auto w-1.5 h-1.5 rounded-full bg-[#017e84]" />
                            )}
                        </Link>
                    );
                })}
            </div>
        );
    };

    return (
        <div className="w-[260px] h-screen bg-[#111827] text-[#9a9ca5] flex flex-col flex-shrink-0 shadow-2xl border-r border-[#1f2937] transition-all overflow-hidden">
            
            {/* 🔝 CABECERA: Identidad Corporativa */}
            <div className="h-[60px] flex items-center px-5 bg-[#0b0f19] border-b border-[#1f2937] text-white flex-shrink-0">
                <Icons.Hexagon size={24} className="text-[#017e84] mr-3 animate-pulse" />
                <span className="font-bold tracking-tight text-[16px]">
                    HiperDios <span className="font-light text-[#017e84]">ERP</span>
                </span>
            </div>

            {/* 🧭 NAVEGACIÓN DINÁMICA */}
            <nav className="flex-1 overflow-y-auto py-4 odoo-scrollbar">
                {rootCategories.map(category => {
                    const categoryId = getId(category);
                    const treeHtml = renderMenuLevel(categoryId!); 
                    
                    if (!treeHtml) return null; 

                    return (
                        <div key={categoryId || Math.random()} className="mb-6">
                            <h3 className="px-5 text-[10px] font-bold text-[#4b5563] uppercase tracking-[0.15em] mb-2.5">
                                {category.name}
                            </h3>
                            {treeHtml}
                        </div>
                    );
                })}

                {/* 🚨 ESCUDO DE DEPURACIÓN */}
                {rootCategories.length === 0 && menus.length > 0 && (
                    <div className="bg-[#1a1111] p-4 rounded-[3px] mx-4 mt-4 border border-[#442323]">
                        <p className="text-[10px] font-bold text-[#ef4444] mb-2 uppercase tracking-wider flex items-center gap-2">
                            <Icons.AlertTriangle size={12} /> Error de Jerarquía
                        </p>
                    </div>
                )}
            </nav>

            {/* 👤 PERFIL Y ACCIONES DE SESIÓN */}
            <div className="p-4 bg-[#0b0f19] border-t border-[#1f2937] flex-shrink-0">
                <div className="flex items-center justify-between">
                    <div className="flex items-center group cursor-pointer">
                        <div className="w-9 h-9 rounded-full bg-[#714B67] text-white flex items-center justify-center text-[13px] font-bold shadow-lg ring-2 ring-transparent group-hover:ring-[#017e84] transition-all mr-3">
                            {userName.charAt(0).toUpperCase()}
                        </div>
                        <div className="flex flex-col">
                            <span className="text-white text-[13px] font-medium leading-tight truncate max-w-[120px]">
                                {userName}
                            </span>
                            <span className="text-[#017e84] text-[10px] font-bold uppercase tracking-tighter">
                                Online
                            </span>
                        </div>
                    </div>
                    <button 
                        onClick={handleLogout} 
                        className="text-[#4b5563] hover:text-[#ef4444] hover:bg-[#ef4444]/10 rounded-lg transition-all p-2.5" 
                        title="Finalizar Sesión"
                    >
                        <Icons.LogOut size={18} />
                    </button>
                </div>
            </div>

        </div>
    );
};