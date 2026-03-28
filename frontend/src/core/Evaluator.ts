// frontend/src/core/Evaluator.ts

/**
 * 🛡️ MOTOR DE DOMINIOS SDUI (Safe Evaluator - Cero XSS)
 * Evalúa reglas declarativas (Arrays) enviadas por el backend en lugar de ejecutar JavaScript.
 * Ejemplo de dominio: [["state", "=", "draft"], ["amount", ">", 100]]
 */
export const evaluateDomain = (domain: any[], data: Record<string, any>): boolean => {
    // Si no hay dominio o está vacío, la regla pasa por defecto (ej: es visible)
    if (!domain || !Array.isArray(domain) || domain.length === 0) return true;

    // Evaluación con lógica AND implícita
    for (const leaf of domain) {
        // Ignoramos nodos mal formados
        if (!Array.isArray(leaf) || leaf.length !== 3) continue; 
        
        const [field, operator, value] = leaf;
        const recordValue = data[field];

        let isMatch = false;
        switch (operator) {
            case '=':
            case '==': isMatch = recordValue === value; break;
            case '!=': isMatch = recordValue !== value; break;
            case '>': isMatch = recordValue > value; break;
            case '<': isMatch = recordValue < value; break;
            case '>=': isMatch = recordValue >= value; break;
            case '<=': isMatch = recordValue <= value; break;
            case 'in': isMatch = Array.isArray(value) && value.includes(recordValue); break;
            case 'not in': isMatch = Array.isArray(value) && !value.includes(recordValue); break;
            default: 
                console.warn(`⚠️ Operador desconocido en SDUI: ${operator}`);
                isMatch = false;
        }

        // Si una sola hoja falla, todo el AND falla
        if (!isMatch) return false; 
    }
    
    return true;
};