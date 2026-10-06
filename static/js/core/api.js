// Cliente HTTP único para a API do HealthOS.
export const API_BASE = `${window.location.origin}/api/v1`;

function formatErrorDetail(detail) {
    if (Array.isArray(detail)) {
        // Erros de validação do FastAPI: [{loc: ["body", "campo"], msg: "..."}]
        return detail.map(item => {
            const field = Array.isArray(item.loc) ? item.loc.slice(1).join('.') : '';
            return `${field ? `${field}: ` : ''}${item.msg || JSON.stringify(item)}`;
        }).join('; ');
    }
    if (detail && typeof detail === 'object') return JSON.stringify(detail);
    return detail;
}

/**
 * Faz uma requisição JSON. `endpoint` é relativo a /api/v1, a menos que comece
 * com "/" e `{ root: true }` seja informado (ex.: /status, /metrics).
 */
export async function apiCall(endpoint, method = 'GET', body = null, { root = false } = {}) {
    const options = { method, headers: { 'Content-Type': 'application/json' } };
    if (body) options.body = JSON.stringify(body);

    let response;
    try {
        response = await fetch(`${root ? window.location.origin : API_BASE}${endpoint}`, options);
    } catch {
        throw new Error('Não foi possível conectar à API. Verifique sua conexão e tente novamente.');
    }

    if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(formatErrorDetail(err.detail) || `Falha na requisição (HTTP ${response.status})`);
    }
    if (response.status === 204) return null;
    return response.json();
}
