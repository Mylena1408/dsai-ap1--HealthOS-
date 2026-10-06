// Barras horizontais em SVG para contagens por categoria e rankings.
// Especificação: barras de até 24px, ponta de dados arredondada (4px) e base reta,
// valor na ponta da barra, uma cor por série (sem legenda: o título identifica),
// tooltip por barra no mouse e no foco.
const NS = 'http://www.w3.org/2000/svg';
const BAR = 20;
const GAP = 12;
const LABEL_WIDTH = 150;
const VALUE_ROOM = 56;  // mínimo; cresce com o rótulo mais longo
const CHAR_WIDTH = 6.6;  // largura média de um caractere a 11px (estimativa conservadora)

function el(name, attrs = {}, parent = null) {
    const node = document.createElementNS(NS, name);
    Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, value));
    if (parent) parent.appendChild(node);
    return node;
}

/** Retângulo com cantos arredondados só na ponta direita (base reta no eixo). */
function barPath(x, y, width, height, radius = 4) {
    const r = Math.min(radius, width, height / 2);
    return `M${x},${y} H${x + width - r} Q${x + width},${y} ${x + width},${y + r} V${y + height - r}
            Q${x + width},${y + height} ${x + width - r},${y + height} H${x} Z`;
}

const fmt = value => Number(value).toLocaleString('pt-BR', { maximumFractionDigits: 1 });

/** items: [{ label, value }]; options: { color, unit, format(value) -> texto, ariaLabel } */
export function renderBarChart(container, items, options = {}) {
    const { color = 'var(--series-1)', unit = '', ariaLabel = 'Gráfico de barras' } = options;
    const formatValue = options.format || (value => `${fmt(value)}${unit ? ` ${unit}` : ''}`);
    container.classList.add('viz-root', 'relative');
    const draw = () => {
        container.replaceChildren();
        if (!items.length) {
            container.innerHTML = '<p class="text-sm text-slate-500">Sem dados no período.</p>';
            return;
        }
        const width = Math.max(container.clientWidth, 280);
        const height = items.length * (BAR + GAP);
        const max = Math.max(...items.map(i => i.value), 1);
        const room = Math.max(VALUE_ROOM, Math.max(...items.map(i => formatValue(i.value).length)) * CHAR_WIDTH + 10);
        const plot = width - LABEL_WIDTH - room;
        const svg = el('svg', { viewBox: `0 0 ${width} ${height}`, width, height, role: 'group', 'aria-label': ariaLabel });
        svg.style.display = 'block';
        el('line', { x1: LABEL_WIDTH, x2: LABEL_WIDTH, y1: 0, y2: height, class: 'viz-grid' }, svg);

        const tooltip = document.createElement('div');
        tooltip.className = 'viz-tooltip';
        tooltip.hidden = true;

        items.forEach((item, index) => {
            const y = index * (BAR + GAP) + GAP / 2;
            const label = el('text', { x: LABEL_WIDTH - 8, y: y + BAR / 2 + 4, 'text-anchor': 'end', class: 'viz-axis-label' }, svg);
            label.textContent = item.label.length > 22 ? `${item.label.slice(0, 21)}…` : item.label;
            const barWidth = Math.max((item.value / max) * plot, item.value > 0 ? 2 : 0);
            const bar = el('path', { d: barPath(LABEL_WIDTH, y, barWidth, BAR), style: `fill: ${color}`,
                                     tabindex: 0, role: 'img', 'aria-label': `${item.label}: ${formatValue(item.value)}` }, svg);
            const value = el('text', { x: LABEL_WIDTH + barWidth + 6, y: y + BAR / 2 + 4, class: 'viz-end-label' }, svg);
            value.textContent = formatValue(item.value);
            // Área de interação maior que a barra (linha inteira), como pede a especificação.
            const hit = el('rect', { x: 0, y: y - GAP / 2, width, height: BAR + GAP, fill: 'transparent' }, svg);
            const show = () => {
                bar.style.opacity = '0.8';
                tooltip.replaceChildren();
                const strong = document.createElement('strong');
                strong.textContent = formatValue(item.value);
                const name = document.createElement('div');
                name.className = 'viz-tooltip-name';
                name.textContent = item.label;
                tooltip.append(strong, name);
                tooltip.hidden = false;
                tooltip.style.left = `${Math.min(LABEL_WIDTH + barWidth + 8, width - 160)}px`;
                tooltip.style.top = `${y + BAR + 4}px`;
            };
            const hide = () => { bar.style.opacity = ''; tooltip.hidden = true; };
            [hit, bar].forEach(node => {
                node.addEventListener('pointerenter', show);
                node.addEventListener('pointerleave', hide);
            });
            bar.addEventListener('focus', show);
            bar.addEventListener('blur', hide);
        });
        container.append(svg, tooltip);
    };
    draw();
    let lastWidth = container.clientWidth;
    new ResizeObserver(() => {
        if (container.clientWidth !== lastWidth) { lastWidth = container.clientWidth; draw(); }
    }).observe(container);
}
