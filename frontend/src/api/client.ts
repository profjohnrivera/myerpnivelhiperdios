// frontend/src/core/api/client.ts
import axios from 'axios';

// 🚀 Automáticamente usa la URL de producción si existe, sino usa localhost
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json'
  }
});

// 🛡️ INTERCEPTOR DE REQUEST: Inyecta el Token en cada petición automáticamente
api.interceptors.request.use((config) => {
  // 💎 LA CURA: Leemos estrictamente de la memoria RAM volátil (sessionStorage)
  const token = sessionStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 🛡️ INTERCEPTOR DE RESPONSE: Expulsa al usuario si el token expira o es inválido
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && !error.config.url?.includes('/login')) {
      console.warn("🛡️ [API Client] Acceso denegado. Ejecutando protocolo de expulsión...");
      
      // 💎 LA CURA: Destruimos la sesión en RAM
      sessionStorage.clear();
      
      // Escudo extra: Destruimos cualquier fantasma viejo que haya quedado en el disco duro
      localStorage.clear(); 
      
      window.location.href = '/login'; // Redirección forzada de seguridad
    }
    return Promise.reject(error);
  }
);

export default api;