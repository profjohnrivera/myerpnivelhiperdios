/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        erp: {
          primary: '#2563eb',   // Azul corporativo
          secondary: '#64748b', // Gris profesional
          success: '#10b981',   // Verde para 'Aprobado'
        }
      }
    },
  },
  plugins: [],
}