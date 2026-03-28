// frontend/src/core/interceptor.ts
import axios from 'axios';

// 1. INYECCIÓN ANTES DE QUE SALGA LA PETICIÓN
axios.interceptors.request.use(
    (config) => {
        // 🛡️ SEGURIDAD NIVEL 5: Extraemos la llave de la memoria RAM (sessionStorage)
        const token = sessionStorage.getItem('token');
        if (token) {
            // 🛡️ FIX: Compatibilidad absoluta con todas las versiones de Axios
            if (config.headers && typeof config.headers.set === 'function') {
                config.headers.set('Authorization', `Bearer ${token}`);
            } else {
                config.headers['Authorization'] = `Bearer ${token}`;
            }
        }
        return config;
    },
    (error) => Promise.reject(error)
);

// 2. VIGILANCIA DE LA RESPUESTA DEL SERVIDOR
axios.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response && error.response.status === 401 && !error.config.url.includes('/login')) {
            console.warn("🛡️ Acceso denegado o sesión expirada. Ejecutando protocolo de expulsión...");
            
            // 💎 Destrucción total de la sesión en RAM
            sessionStorage.clear();
            
            // Redirección forzada
            window.location.href = '/login';
        }
        return Promise.reject(error);
    }
);

export default axios;