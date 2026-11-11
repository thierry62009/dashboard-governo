/* =========================================================================
   grafico.js — desenha um gráfico de colunas em SVG, sem bibliotecas.

   Ideia geral: SVG é um "desenho em código". Um retângulo é
   <rect x=".." y=".." width=".." height="..">. Este arquivo calcula onde
   cada coluna fica e cria os elementos um a um.

   Uso:  desenharColunas(elementoDaPagina, dados, opcoes)
         dados  = [{ data: "2026-09", valor: 0.82 }, ...]
         opcoes = { titulo: "texto para leitores de tela", unidade: "%" }
   ========================================================================= */

const SVG_NS = "http://www.w3.org/2000/svg";

// Cria um elemento SVG com os atributos passados num objeto.
function criarSvg(tipo, atributos) {
  const el = document.createElementNS(SVG_NS, tipo);
  for (const nome in atributos) el.setAttribute(nome, atributos[nome]);
  return el;
}

// Escolhe valores "redondos" para as linhas de grade do eixo vertical
// (ex.: -0,5 / 0 / 0,5 / 1,0 em vez de -0,37 / 0,21 / 0,79...).
function marcasDoEixo(minimo, maximo, quantasMais) {
  const bruto = (maximo - minimo) / quantasMais;
  const potencia = Math.pow(10, Math.floor(Math.log10(bruto)));
  // Testa passos 1, 2, 2,5 e 5 (vezes a potência de 10) e pega o primeiro que serve
  const passo = [1, 2, 2.5, 5, 10].map(m => m * potencia).find(p => p >= bruto);
  const marcas = [];
  for (let v = Math.floor(minimo / passo) * passo; v <= maximo + passo * 0.001; v += passo) {
    marcas.push(Math.round(v * 1e6) / 1e6);  // arredonda para evitar 0,30000000004
  }
  // Garante que o último valor cubra o máximo dos dados
  if (marcas[marcas.length - 1] < maximo) marcas.push(marcas[marcas.length - 1] + passo);
  return marcas;
}

// Formata número no padrão brasileiro: 0.82 -> "0,82"
function numeroBR(v, casas) {
  return v.toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });
}

// "2026-09" -> "set/2026"  (e "set" se curto = true)
function mesCurto(aaaaMm, curto) {
  const [ano, mes] = aaaaMm.split("-").map(Number);
  const nome = new Date(ano, mes - 1, 1).toLocaleDateString("pt-BR", { month: "short" }).replace(".", "");
  return curto ? nome : nome + "/" + ano;
}

function desenharColunas(container, dados, opcoes) {
  container.innerHTML = "";  // apaga o desenho anterior (ao trocar o período)
  if (!dados.length) return;

  // ---- Tamanho: a largura acompanha o cartão; a altura é fixa ----
  const largura = Math.max(container.clientWidth, 280);
  const altura = 240;
  const margem = { topo: 12, direita: 8, base: 28, esquerda: 44 };
  const areaL = largura - margem.esquerda - margem.direita;  // largura útil
  const areaA = altura - margem.topo - margem.base;          // altura útil

  // ---- Escala vertical: converte um valor (%) numa posição y (pixels) ----
  const valores = dados.map(d => d.valor);
  const marcas = marcasDoEixo(Math.min(0, ...valores), Math.max(0, ...valores), 4);
  const vMin = marcas[0], vMax = marcas[marcas.length - 1];
  const y = v => margem.topo + (vMax - v) / (vMax - vMin) * areaA;

  // ---- Escala horizontal: cada mês ocupa uma "faixa" igual ----
  const faixa = areaL / dados.length;
  const vao = Math.max(2, faixa * 0.25);           // espaço entre colunas
  const larguraColuna = Math.max(1, faixa - vao);
  const x = i => margem.esquerda + i * faixa + vao / 2;

  const svg = criarSvg("svg", {
    viewBox: `0 0 ${largura} ${altura}`, width: largura, height: altura,
    role: "img", "aria-label": opcoes.titulo,
  });

  // ---- Linhas de grade e números do eixo vertical ----
  for (const m of marcas) {
    svg.append(criarSvg("line", {
      x1: margem.esquerda, x2: largura - margem.direita, y1: y(m), y2: y(m),
      stroke: m === 0 ? "var(--eixo)" : "var(--borda)", "stroke-width": m === 0 ? 1.5 : 1,
    }));
    const rotulo = criarSvg("text", { x: margem.esquerda - 8, y: y(m) + 4, "text-anchor": "end" });
    // 1 casa decimal (0,5) ou 2 se algum valor precisar (0,25)
    const precisaDuas = marcas.some(v => Math.abs(Math.round(v * 10) - v * 10) > 1e-9);
    rotulo.textContent = numeroBR(m, precisaDuas ? 2 : 1);
    svg.append(rotulo);
  }

  // ---- Colunas ----
  const colunas = dados.map((d, i) => {
    const topo = Math.min(y(d.valor), y(0));
    const alturaColuna = Math.max(1, Math.abs(y(d.valor) - y(0)));
    const rect = criarSvg("rect", {
      x: x(i), y: topo, width: larguraColuna, height: alturaColuna,
      rx: Math.min(2, larguraColuna / 2), fill: "var(--laranja)",
    });
    svg.append(rect);
    return rect;
  });

  // ---- Rótulos do eixo horizontal ----
  // Muitos meses: mostra só o ano em cada janeiro. Poucos: mostra os meses,
  // pulando alguns se não houver espaço (cerca de 44 px por rótulo).
  const muitos = dados.length > 13;
  const pulo = Math.ceil(44 / faixa);
  dados.forEach((d, i) => {
    let texto = null;
    if (muitos && d.data.endsWith("-01")) texto = d.data.slice(0, 4);
    if (!muitos && (dados.length - 1 - i) % pulo === 0) texto = mesCurto(d.data, true);
    if (!texto) return;
    const t = criarSvg("text", { x: x(i) + larguraColuna / 2, y: altura - 8, "text-anchor": muitos ? "start" : "middle" });
    if (muitos) t.setAttribute("x", x(i));
    t.textContent = texto;
    svg.append(t);
  });

  container.append(svg);

  // ---- Dica ao passar o mouse ou o dedo (tooltip) ----
  const dica = document.createElement("div");
  dica.className = "dica";
  dica.hidden = true;
  container.append(dica);

  // Uma área invisível por cima do gráfico captura o movimento do ponteiro
  const captura = criarSvg("rect", {
    x: margem.esquerda, y: margem.topo, width: areaL, height: areaA, fill: "transparent",
  });
  svg.append(captura);

  function mostrar(evento) {
    const caixa = svg.getBoundingClientRect();
    const px = (evento.clientX - caixa.left) * (largura / caixa.width);
    const i = Math.min(dados.length - 1, Math.max(0, Math.floor((px - margem.esquerda) / faixa)));
    const d = dados[i];
    colunas.forEach((c, j) => c.setAttribute("opacity", j === i ? 1 : 0.45));
    dica.innerHTML = "";
    const forte = document.createElement("strong");
    forte.textContent = numeroBR(d.valor, 2) + opcoes.unidade;
    dica.append(mesCurto(d.data) + ": ", forte);
    dica.hidden = false;
    // Centraliza a dica sobre a coluna, mas sem deixá-la sair pelas bordas
    const meia = dica.offsetWidth / 2;
    const centro = (x(i) + larguraColuna / 2) / largura * caixa.width;
    dica.style.left = Math.min(Math.max(centro, meia), caixa.width - meia) + "px";
    dica.style.top = (Math.min(y(d.valor), y(0)) / altura * caixa.height - 8) + "px";
  }
  function esconder() {
    colunas.forEach(c => c.setAttribute("opacity", 1));
    dica.hidden = true;
  }
  captura.addEventListener("pointermove", mostrar);
  captura.addEventListener("pointerdown", mostrar);
  captura.addEventListener("pointerleave", esconder);
}
