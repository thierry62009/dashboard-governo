/* =========================================================================
   painel.js — lê os JSON da pasta data/ e monta a página.

   Para acrescentar um indicador no futuro: o script Python gera um novo
   data/xxx.json e você acrescenta um item na lista INDICADORES abaixo.
   ========================================================================= */

const INDICADORES = [
  {
    id: "ipca",
    arquivo: "data/ipca.json",
    titulo: "IPCA",                          // nome curto no cartão
    descricao: "IPCA, variação % mensal",    // usado na linha de fonte do rodapé
    unidade: "%",
    casas: 2,
  },
];

const LINK_SGS = "https://www3.bcb.gov.br/sgspub/";
const LICENCA = "ODbL (Open Data Commons Open Database License)";
const LINK_LICENCA = "https://opendatacommons.org/licenses/odbl/";

// Guarda os dados já carregados e o período escolhido nos botões
const carregados = [];   // [{ config, json }]
let periodo = "todos";   // "todos", "12" ou "6"

/* ---------- Pequenas funções de formatação ---------- */

// "2026-09" -> "setembro de 2026"
function mesPorExtenso(aaaaMm) {
  const [ano, mes] = aaaaMm.split("-").map(Number);
  return new Date(ano, mes - 1, 1).toLocaleDateString("pt-BR", { month: "long", year: "numeric" });
}

// "2026-11-10T20:42:19-03:00" -> "10/11/2026 às 20:42"
function dataHora(iso) {
  const d = new Date(iso);
  const opcoes = { timeZone: "America/Sao_Paulo" };
  return d.toLocaleDateString("pt-BR", opcoes) + " às " +
         d.toLocaleTimeString("pt-BR", { ...opcoes, hour: "2-digit", minute: "2-digit" });
}

// Cria um elemento HTML com classe e texto (textContent nunca interpreta HTML)
function criar(tag, classe, texto) {
  const el = document.createElement(tag);
  if (classe) el.className = classe;
  if (texto !== undefined) el.textContent = texto;
  return el;
}

function link(texto, url) {
  const a = criar("a", "", texto);
  a.href = url;
  return a;
}

// Recorta os dados conforme o botão de período
function recortar(dados) {
  return periodo === "todos" ? dados : dados.slice(-Number(periodo));
}

/* ---------- Montagem de cada parte ---------- */

// Linha curta de fonte: série, origem, data de extração, link e licença
function linhaDeFonte(config, json) {
  const s = json.serie;
  const p = criar("p", "fonte-linha");
  p.append(
    "Fonte: ", link("BCB/SGS", LINK_SGS), ", série " + s.codigo + " (origem " + s.origem + ") · ",
    "extraído em " + dataHora(json.extraido_em) + " · ",
    link("dados da consulta", s.url_fonte), " · Licença ", link("ODbL", LINK_LICENCA)
  );
  return p;
}

// Cartão de destaque da abertura (valor mais recente)
function cartaoDestaque(config, json) {
  const ultimo = json.dados[json.dados.length - 1];
  const c = criar("article", "destaque");
  c.append(
    criar("p", "rotulo", config.titulo + " · " + json.serie.unidade),
    criar("p", "numero", numeroBR(ultimo.valor, config.casas) + config.unidade),
    criar("p", "referencia secundario", "Referência: " + mesPorExtenso(ultimo.data)),
    linhaDeFonte(config, json)
  );
  return c;
}

// Cartão da grade de indicadores: título, gráfico, tabela e fonte
function cartaoIndicador(config, json) {
  const dados = recortar(json.dados);
  const primeiro = dados[0], ultimo = dados[dados.length - 1];
  const c = criar("article", "cartao");

  c.append(
    criar("h3", "", config.titulo + " · " + json.serie.unidade),
    criar("p", "subtitulo", json.serie.nome + ", de " + mesPorExtenso(primeiro.data) +
                            " a " + mesPorExtenso(ultimo.data))
  );

  // Texto lido por leitores de tela no lugar do desenho
  const valores = dados.map(d => d.valor);
  const titulo = "Gráfico de colunas: " + config.titulo + ", " + json.serie.unidade +
    ", de " + mesPorExtenso(primeiro.data) + " a " + mesPorExtenso(ultimo.data) +
    ". Menor valor " + numeroBR(Math.min(...valores), config.casas) + config.unidade +
    ", maior valor " + numeroBR(Math.max(...valores), config.casas) + config.unidade +
    ". Os números estão na tabela logo abaixo.";

  const area = criar("div", "grafico");
  c.append(area);

  // Tabela com os mesmos números do gráfico (mais recente primeiro)
  const det = criar("details");
  det.append(criar("summary", "", "Ver os números em tabela"));
  const rolagem = criar("div", "rolagem");
  const tabela = criar("table");
  tabela.innerHTML = "<thead><tr><th scope='col'>Mês</th><th scope='col'>Valor (" +
                     config.unidade + ")</th></tr></thead>";
  const corpo = criar("tbody");
  for (const d of [...dados].reverse()) {
    const tr = criar("tr");
    tr.append(criar("td", "", mesPorExtenso(d.data)), criar("td", "", numeroBR(d.valor, config.casas)));
    corpo.append(tr);
  }
  tabela.append(corpo);
  rolagem.append(tabela);
  det.append(rolagem);
  c.append(det, linhaDeFonte(config, json));

  // O gráfico precisa saber a largura do cartão, então é desenhado depois
  // que o cartão entra na página (ver desenharGraficos).
  c.desenhar = () => desenharColunas(area, dados, { titulo, unidade: config.unidade });
  return c;
}

// Linha de fonte do rodapé (texto completo pedido para a licença)
function fonteRodape(config, json) {
  const s = json.serie;
  const li = criar("li");
  li.append(
    "Fonte: ", link("Banco Central do Brasil, SGS", LINK_SGS),
    ", série " + s.codigo + " (" + config.descricao + "; origem " + s.origem + "). ",
    "Extraído em " + dataHora(json.extraido_em) + ". Licença: ",
    link(LICENCA, LINK_LICENCA), "."
  );
  return li;
}

/* ---------- Desenho e eventos ---------- */

function desenharGrade() {
  const grade = document.getElementById("grade-indicadores");
  grade.innerHTML = "";
  const cartoes = carregados.map(({ config, json }) => cartaoIndicador(config, json));
  grade.append(...cartoes);
  cartoes.forEach(c => c.desenhar());
}

// Botões de período: marca o clicado como ativo (aria-pressed) e redesenha
function ligarBotoesDePeriodo() {
  const botoes = document.querySelectorAll(".periodos .botao");
  botoes.forEach(b => b.addEventListener("click", () => {
    periodo = b.dataset.meses;
    botoes.forEach(o => o.setAttribute("aria-pressed", String(o === b)));
    desenharGrade();
  }));
}

// Abas do resumo: clique ou setas do teclado trocam a aba
function ligarAbas() {
  const abas = [...document.querySelectorAll('[role="tab"]')];
  function ativar(aba) {
    abas.forEach(a => {
      const ativa = a === aba;
      a.setAttribute("aria-selected", String(ativa));
      a.tabIndex = ativa ? 0 : -1;
      document.getElementById(a.getAttribute("aria-controls")).hidden = !ativa;
    });
    aba.focus();
  }
  abas.forEach((aba, i) => {
    aba.addEventListener("click", () => ativar(aba));
    aba.addEventListener("keydown", e => {
      if (e.key === "ArrowRight") ativar(abas[(i + 1) % abas.length]);
      if (e.key === "ArrowLeft") ativar(abas[(i - 1 + abas.length) % abas.length]);
    });
  });
}

// Redesenha os gráficos quando a largura da janela muda (girar o celular etc.)
let ultimaLargura = window.innerWidth;
window.addEventListener("resize", () => {
  if (window.innerWidth === ultimaLargura) return;
  ultimaLargura = window.innerWidth;
  clearTimeout(window.__espera);
  window.__espera = setTimeout(desenharGrade, 150);
});

/* ---------- Início: baixa os JSON e preenche a página ---------- */

async function iniciar() {
  ligarBotoesDePeriodo();
  ligarAbas();

  for (const config of INDICADORES) {
    try {
      const resposta = await fetch(config.arquivo, { cache: "no-cache" });
      if (!resposta.ok) throw new Error("HTTP " + resposta.status);
      carregados.push({ config, json: await resposta.json() });
    } catch (erro) {
      const aviso = document.getElementById("aviso-erro");
      aviso.hidden = false;
      aviso.textContent += "Não foi possível carregar " + config.titulo + " (" + erro.message + "). ";
    }
  }
  if (!carregados.length) return;

  // "Atualizado em": a extração mais recente entre os indicadores carregados
  const maisRecente = carregados.map(c => c.json.extraido_em).sort().pop();
  const tempo = document.getElementById("atualizado-em");
  tempo.dateTime = maisRecente;
  tempo.textContent = dataHora(maisRecente);
  document.getElementById("selo-atualizado").hidden = false;
  document.getElementById("rodape-atualizado").textContent =
    "Última atualização dos dados: " + dataHora(maisRecente) + " (horário de Brasília).";

  for (const { config, json } of carregados) {
    document.getElementById("destaques").append(cartaoDestaque(config, json));
    document.getElementById("lista-fontes").append(fonteRodape(config, json));
  }
  desenharGrade();
}

iniciar();
