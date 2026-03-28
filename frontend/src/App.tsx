// frontend/src/App.tsx
import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';

// 🛡️ IMPORTACIÓN CRÍTICA ACTUALIZADA: Ahora apunta a la capa de red
import './api/interceptor';

// 🧱 COMPONENTES
// (Nota: Si moviste TopNavBar dentro de widgets/, ajusta la ruta a './components/widgets/TopNavBar')
import { TopNavBar } from './components/TopNavBar'; 

// 📍 PÁGINAS (Vistas orquestadoras aisladas)
import { AppSwitcher } from './pages/AppSwitcher';
import { ModelPlayer } from './pages/ModelPlayer';
import { Login } from './pages/Login';

// ============================================================================
// 🛑 GUARDIÁN DE RUTAS (El cadenero del club)
// 🛡️ FASE 4: Cambiado a memoria de sesión para blindaje XSS.
// ============================================================================
const ProtectedRoute = ({ children }: { children: JSX.Element }) => {
    const token = sessionStorage.getItem('token');
    
    // Si no hay llave en la memoria RAM volátil, patada directa al login
    if (!token) {
        return <Navigate to="/login" replace />;
    }
    return children;
};

// ============================================================================
// 🚀 APLICACIÓN PRINCIPAL (Arquitectura HiperDios - Odoo 20 Style)
// ============================================================================
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
                            {/* 💎 LAYOUT CORPORATIVO: Columna vertical (100vw x 100vh) */}
                            <div className="flex flex-col h-screen w-screen bg-[#F9FAFB] overflow-hidden font-sans text-[#111827]">
                                
                                {/* 1. LA BARRA SUPERIOR (Fija) */}
                                <TopNavBar />
                                
                                {/* 2. EL LIENZO PRINCIPAL (Desplazable) */}
                                <main className="flex-1 flex flex-col overflow-hidden bg-[#F9FAFB] relative">
                                    <Routes>
                                        {/* Motor principal que lee las vistas */}
                                        <Route path=":modelName/:viewType/:id?" element={<ModelPlayer />} />
                                        
                                        {/* 🚀 HOME: El Selector de Aplicaciones (App Switcher) */}
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