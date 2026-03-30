// frontend/src/App.tsx
import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';

// 🛡️ CAPA DE RED
import './api/interceptor';

// 🧱 COMPONENTES
import { TopNavBar } from './components/TopNavBar'; 

// 📍 PÁGINAS (Vistas orquestadoras)
import { AppSwitcher } from './pages/AppSwitcher';
import { ModelPlayer } from './pages/ModelPlayer';
import { Login } from './pages/Login';

/**
 * 🛑 GUARDIÁN DE RUTAS
 * Seguridad basada en memoria de sesión (sessionStorage).
 */
const ProtectedRoute = ({ children }: { children: JSX.Element }) => {
    const token = sessionStorage.getItem('token');
    if (!token) {
        return <Navigate to="/login" replace />;
    }
    return children;
};

/**
 * 🚀 APLICACIÓN PRINCIPAL (Nivel HiperDios - Réplica Odoo 20)
 * * Cambios realizados para la perfección visual:
 * 1. bg-odoo-gray-100: Fondo oficial #F9FAFB (Gris nube).
 * 2. text-odoo-gray-700: Color de texto body oficial #374151.
 * 3. text-[14px]: Tamaño base que heredarán todos los formularios y tablas.
 * 4. Antialiased: Suavizado de fuente para máxima legibilidad.
 */
export const App: React.FC = () => {
    return (
        <BrowserRouter>
            <Routes>
                {/* 🔓 RUTA PÚBLICA */}
                <Route path="/login" element={<Login />} />

                {/* 🔒 RUTAS PROTEGIDAS (La Bóveda del ERP) */}
                <Route 
                    path="/app/*" 
                    element={
                        <ProtectedRoute>
                            {/* 💎 LAYOUT CORPORATIVO: Inyección de herencia global */}
                            <div className="flex flex-col h-screen w-screen bg-transparent overflow-hidden font-sans text-[14px] text-odoo-gray-700 antialiased">
                                
                                {/* 1. NAVEGACIÓN SUPERIOR (Fija) */}
                                <TopNavBar />
                                
                                {/* 2. EL LIENZO PRINCIPAL (Gris Nube) */}
                                <main className="flex-1 flex flex-col overflow-hidden bg-odoo-gray-100 relative">
                                    <Routes>
                                        {/* Motor principal de lectura de modelos y vistas */}
                                        <Route path=":modelName/:viewType/:id?" element={<ModelPlayer />} />
                                        
                                        {/* Home / Selector de Apps */}
                                        <Route path="" element={<AppSwitcher />} />
                                    </Routes>
                                </main>
                                
                            </div>
                        </ProtectedRoute>
                    } 
                />

                {/* 🔄 REDIRECCIÓN MAESTRA */}
                <Route path="*" element={<Navigate to="/app" replace />} />
            </Routes>
        </BrowserRouter>
    );
};

export default App;