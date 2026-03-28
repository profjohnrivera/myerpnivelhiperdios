// frontend/src/components/Login.tsx
import React, { useState } from 'react';
import api from '../api/client';
import { useNavigate } from 'react-router-dom';
import * as Icons from 'lucide-react';

export const Login: React.FC = () => {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);
    const navigate = useNavigate();

    const handleLogin = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');
        setLoading(true);

        try {
            // OAuth2 de FastAPI exige que el payload viaje como formulario (x-www-form-urlencoded)
            const params = new URLSearchParams();
            params.append('username', email);
            params.append('password', password);

            const res = await api.post('/auth/login', params, {
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
            });

            if (res.data && res.data.access_token) {
                // 🛡️ FASE 4: Guardamos en SessionStorage (RAM volátil).
                // Al cerrar la pestaña, la sesión muere. Inmune a ataques XSS persistentes.
                sessionStorage.setItem('token', res.data.access_token);
                sessionStorage.setItem('user_name', res.data.name);
                sessionStorage.setItem('user_id', res.data.uid);
                
                navigate('/app/sale.order/list'); 
            }
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Error de conexión con el servidor. Verifica que FastAPI esté corriendo.');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-[#F9FAFB] flex items-center justify-center p-4 font-sans selection:bg-[#017e84] selection:text-white">
            <div className="w-full max-w-md bg-white rounded-[3px] shadow-2xl border border-[#d8dadd] overflow-hidden">
                
                {/* Cabecera Corporativa */}
                <div className="bg-[#111827] px-8 py-8 text-center relative overflow-hidden">
                    <div className="absolute inset-0 opacity-10 bg-[url('https://www.transparenttextures.com/patterns/cubes.png')]"></div>
                    <div className="flex justify-center mb-3 relative z-10">
                        <div className="bg-[#017e84] text-white p-2.5 rounded-[3px] shadow-lg transform rotate-3 hover:rotate-0 transition-transform">
                            <Icons.Hexagon size={36} strokeWidth={2.5} />
                        </div>
                    </div>
                    <h1 className="text-2xl font-bold text-white tracking-tight relative z-10">HiperDios <span className="text-[#017e84] font-light">ERP</span></h1>
                    <p className="text-[#9a9ca5] text-[13px] mt-1 relative z-10">Ingresa tus credenciales para continuar</p>
                </div>

                <div className="p-8">
                    {error && (
                        <div className="mb-6 bg-[#f8d7da] text-[#721c24] text-[13px] px-4 py-3 rounded-[3px] flex items-center gap-2 border border-[#f5c6cb]">
                            <Icons.AlertCircle size={16} className="flex-shrink-0" />
                            <span>{error}</span>
                        </div>
                    )}

                    <form onSubmit={handleLogin} className="space-y-5">
                        <div>
                            <label className="block text-[12px] font-bold text-[#5f636f] uppercase tracking-wider mb-1.5">Usuario / Correo</label>
                            <div className="relative">
                                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                                    <Icons.User size={16} className="text-[#9a9ca5]" />
                                </div>
                                <input
                                    type="text"
                                    value={email}
                                    onChange={(e) => setEmail(e.target.value)}
                                    className="w-full pl-9 pr-3 py-2 bg-white border border-[#d8dadd] rounded-[3px] text-[#111827] text-[14px] focus:outline-none focus:border-[#017e84] focus:ring-1 focus:ring-[#017e84] transition-colors"
                                    placeholder="admin"
                                    required
                                    autoFocus
                                />
                            </div>
                        </div>

                        <div>
                            <label className="block text-[12px] font-bold text-[#5f636f] uppercase tracking-wider mb-1.5">Contraseña</label>
                            <div className="relative">
                                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                                    <Icons.Lock size={16} className="text-[#9a9ca5]" />
                                </div>
                                <input
                                    type="password"
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    className="w-full pl-9 pr-3 py-2 bg-white border border-[#d8dadd] rounded-[3px] text-[#111827] text-[14px] focus:outline-none focus:border-[#017e84] focus:ring-1 focus:ring-[#017e84] transition-colors"
                                    placeholder="••••••••"
                                    required
                                />
                            </div>
                        </div>

                        <button
                            type="submit"
                            disabled={loading}
                            className="w-full mt-2 bg-[#714B67] text-white py-2.5 rounded-[3px] text-[14px] font-medium hover:bg-[#5A3C52] focus:outline-none transition-colors disabled:opacity-70 flex justify-center items-center gap-2 shadow-sm"
                        >
                            {loading ? <Icons.Loader2 size={16} className="animate-spin" /> : <Icons.LogIn size={16} />}
                            {loading ? 'Validando...' : 'Iniciar Sesión'}
                        </button>
                    </form>
                    
                    <div className="mt-8 pt-4 border-t border-[#e7e9ed] text-center">
                        <p className="text-[11px] text-[#9a9ca5]">HiperDios Architecture © 2026</p>
                    </div>
                </div>
            </div>
        </div>
    );
};