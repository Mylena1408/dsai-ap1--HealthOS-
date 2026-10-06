// Gráfico de linha temporal em SVG (sem dependências).
// Especificação: linhas de 2px, pontos de 8px com anel da cor da superfície, grade em
// hairline, faixa de referência recessiva, rótulo direto só no último ponto, legenda
// apenas com 2+ séries, cruz de leitura + tooltip (mouse e teclado).
const NS = 'http://www.w3.org/2000/svg';
const MARGIN = { top: 16, right: 56, bottom: 28, left: 44 };

function el(name, attrs = {}, parent = null) {
    const node = document.createElementNS(NS, name);
    Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, value));
    if (parent) parent.appendChild(node);
    return node;
}

/** Valores "redondos" para os ticks do eixo Y. */
function niceTicks(min, max, count = 4) {
    const span = max - min || Math.abs(max) || 1;
    const raw = span / count;
    const magnitude = 10 ** Math.floor(Math.log10(raw));
    const step = [1, 2, 2.5, 5, 10].map(m => m * magnitude).find(s => s >= raw);
    const start = Math.floor(min / step) * step;
    const ticks = [];
    for (let v = start; v <= max + step * 0.5; v += step) ticks.push(Number(v.toFixed(6)));
    return ticks;
}

const formatNumber = value => Number(value).toLocaleString('pt-BR', { maximumFractionDigits: 2 });
const formatDay = date => date.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' });

/**
 * series: [{ name, color, points: [{ t: Date, v: number, note?: string }] }]
 * options: { unit, height, reference: { min?, max? }, ariaLabel }
 */
export function renderLineChart(container, series, options = {}) {
    const { unit = '', height = 180, reference = null, ariaLabel = 'Gráfico de evolução' } = options;
    container.classList.add('viz-root', 'relative');
    const draw = () => {
        container.replaceChildren();
        const width = Math.max(container.clientWidth, 260);
        const all = series.flatMap(s => s.points);
        if (!all.length) return;

        const times = all.map(p => p.t.getTime());
        let [tMin, tMax] = [Math.min(...times), Math.max(...times)];
        if (tMin === tMax) { tMin -= 86400000; tMax += 86400000; }
        const values = all.map(p => p.v).concat(reference ? [reference.min, reference.max].filter(v => v != null) : []);
        const ticks = niceTicks(Math.min(...values), Math.max(...values));
        const [vMin, vMax] = [ticks[0], ticks[ticks.length - 1]];

        const plotW = width - MARGIN.left - MARGIN.right;
        const plotH = height - MARGIN.top - MARGIN.bottom;
        const x = t => MARGIN.left + ((t - tMin) / (tMax - tMin)) * plotW;
        const y = v => MARGIN.top + (1 - (v - vMin) / (vMax - vMin || 1)) * plotH;

        const svg = el('svg', { viewBox: `0 0 ${width} ${height}`, width, height, role: 'img', 'aria-label': ariaLabel });
        svg.style.display = 'block';

        // Faixa de referência (recessiva) atrás de tudo.
        if (reference && (reference.min != null || reference.max != null)) {
            const top = y(Math.min(reference.max ?? vMax, vMax));
            const bottom = y(Math.max(reference.min ?? vMin, vMin));
            el('rect', { x: MARGIN.left, y: top, width: plotW, height: Math.max(bottom - top, 0), class: 'viz-band' }, svg);
        }

        // Grade horizontal e rótulos do eixo Y.
        ticks.forEach(tick => {
            el('line', { x1: MARGIN.left, x2: MARGIN.left + plotW, y1: y(tick), y2: y(tick), class: 'viz-grid' }, svg);
            const label = el('text', { x: MARGIN.left - 6, y: y(tick) + 4, 'text-anchor': 'end', class: 'viz-axis-label' }, svg);
            label.textContent = formatNumber(tick);
        });
        // Eixo X: até 5 datas.
        const xTicks = Math.min(5, new Set(times).size);
        for (let i = 0; i < xTicks; i++) {
            const t = xTicks === 1 ? (tMin + tMax) / 2 : tMin + (i * (tMax - tMin)) / (xTicks - 1);
            const label = el('text', { x: x(t), y: height - 8, 'text-anchor': 'middle', class: 'viz-axis-label' }, svg);
            label.textContent = formatDay(new Date(t));
        }

        // Linhas, pontos e rótulo direto do último valor.
        series.forEach(s => {
            const points = [...s.points].sort((a, b) => a.t - b.t);
            if (points.length > 1) {
                el('path', {
                    d: points.map((p, i) => `${i ? 'L' : 'M'}${x(p.t.getTime())},${y(p.v)}`).join(' '),
                    fill: 'none', style: `stroke: ${s.color}`, 'stroke-width': 2, 'stroke-linejoin': 'round', 'stroke-linecap': 'round',
                }, svg);
            }
            // style (e não o atributo fill) para aceitar tokens CSS como var(--series-1).
            points.forEach(p => el('circle', { cx: x(p.t.getTime()), cy: y(p.v), r: 4, style: `fill: ${s.color}`, class: 'viz-dot' }, svg));
            const last = points[points.length - 1];
            const label = el('text', { x: x(last.t.getTime()) + 8, y: y(last.v) + 4, class: 'viz-end-label' }, svg);
            label.textContent = `${formatNumber(last.v)}${unit ? ` ${unit}` : ''}`;
        });

        // Cruz de leitura + tooltip (mouse e teclado).
        const moments = [...new Set(times)].sort((a, b) => a - b);
        const crosshair = el('line', { y1: MARGIN.top, y2: MARGIN.top + plotH, class: 'viz-crosshair', visibility: 'hidden' }, svg);
        const overlay = el('rect', { x: MARGIN.left, y: MARGIN.top, width: plotW, height: plotH, fill: 'transparent', tabindex: 0 }, svg);
        overlay.setAttribute('aria-label', `${ariaLabel}: use as setas para percorrer as medições`);
        const tooltip = document.createElement('div');
        tooltip.className = 'viz-tooltip';
        tooltip.hidden = true;

        let index = moments.length - 1;
        const show = i => {
            index = Math.max(0, Math.min(moments.length - 1, i));
            const t = moments[index];
            crosshair.setAttribute('x1', x(t));
            crosshair.setAttribute('x2', x(t));
            crosshair.setAttribute('visibility', 'visible');
            tooltip.replaceChildren();
            const title = document.createElement('div');
            title.className = 'viz-tooltip-title';
            title.textContent = new Date(t).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' });
            tooltip.appendChild(title);
            series.forEach(s => {
                const point = s.points.find(p => p.t.getTime() === t);
                if (!point) return;
                const row = document.createElement('div');
                row.className = 'viz-tooltip-row';
                const key = document.createElement('span');
                key.className = 'viz-line-key';
                key.style.background = s.color;
                const value = document.createElement('strong');
                value.textContent = `${formatNumber(point.v)}${unit ? ` ${unit}` : ''}`;
                const name = document.createElement('span');
                name.className = 'viz-tooltip-name';
                name.textContent = point.note ? `${s.name} · ${point.note}` : s.name;
                row.append(key, value, name);
                tooltip.appendChild(row);
            });
            tooltip.hidden = false;
            const left = Math.min(x(t) + 12, width - tooltip.offsetWidth - 4);
            tooltip.style.left = `${Math.max(left, 4)}px`;
            tooltip.style.top = `${MARGIN.top}px`;
        };
        const hide = () => { tooltip.hidden = true; crosshair.setAttribute('visibility', 'hidden'); };
        const nearest = clientX => {
            const box = svg.getBoundingClientRect();
            const t = tMin + ((clientX - box.left) * (width / box.width) - MARGIN.left) / plotW * (tMax - tMin);
            return moments.reduce((best, m, i) => (Math.abs(m - t) < Math.abs(moments[best] - t) ? i : best), 0);
        };
        overlay.addEventListener('pointermove', event => show(nearest(event.clientX)));
        overlay.addEventListener('pointerleave', hide);
        overlay.addEventListener('focus', () => show(index));
        overlay.addEventListener('blur', hide);
        overlay.addEventListener('keydown', event => {
            if (event.key === 'ArrowLeft') { event.preventDefault(); show(index - 1); }
            if (event.key === 'ArrowRight') { event.preventDefault(); show(index + 1); }
        });

        container.append(svg, tooltip);

        // Legenda apenas com duas ou mais séries (com uma, o título já identifica).
        if (series.length > 1) {
            const legend = document.createElement('div');
            legend.className = 'viz-legend';
            series.forEach(s => {
                const item = document.createElement('span');
                const key = document.createElement('span');
                key.className = 'viz-line-key';
                key.style.background = s.color;
                item.append(key, document.createTextNode(s.name));
                legend.appendChild(item);
            });
            container.appendChild(legend);
        }
    };

    draw();
    // Redesenha ao mudar a largura do contêiner (layout responsivo).
    let lastWidth = container.clientWidth;
    new ResizeObserver(() => {
        if (container.clientWidth !== lastWidth) { lastWidth = container.clientWidth; draw(); }
    }).observe(container);
}
