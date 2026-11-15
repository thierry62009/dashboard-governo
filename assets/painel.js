/* =========================================================================
   painel.js — lê os JSON da pasta data/ e monta a página.

   Para acrescentar um indicador: o script Python (scripts/coletar.py) gera
   um novo data/xxx.json e você acrescenta um item na lista INDICADORES.
   Para acrescentar um mandato ou presidente: edite só data/mandatos.json.
   ========================================================================= */

// Áreas da seção "Indicadores", na ordem em que aparecem na página.
// Uma área só aparece se tiver pelo menos um indicador na lista abaixo.
const AREAS = [
  { id: "economia", titulo: "Economia" },
  { id: "trabalho", titulo: "Trabalho e renda" },
  { id: "contas", titulo: "Contas públicas" },
  { id: "saude", titulo: "Saúde" },
  { id: "educacao", titulo: "Educação" },
  { id: "seguranca", titulo: "Segurança" },
];

// Cada item: arquivo de dados, área, nome curto e como escrever o número
// (casas decimais, prefixo e sufixo). "destaque: true" põe o indicador
// também nos cartões grandes da abertura.
const INDICADORES = [
  // ----- Economia -----
  { id: "ipca", arquivo: "data/ipca.json", area: "economia", titulo: "IPCA",
    casas: 2, sufixo: "%", destaque: true },
  { id: "selic", arquivo: "data/selic.json", area: "economia", titulo: "Selic (meta)",
    casas: 2, sufixo: "%", destaque: true },
  { id: "dolar", arquivo: "data/dolar.json", area: "economia", titulo: "Dólar (venda)",
    casas: 4, prefixo: "R$ ", destaque: true },
  { id: "pib", arquivo: "data/pib.json", area: "economia", titulo: "PIB, acumulado em 4 trimestres",
    casas: 1, sufixo: "%", destaque: true },
  // ----- Trabalho e renda -----
  { id: "desocupacao", arquivo: "data/desocupacao.json", area: "trabalho", titulo: "Taxa de desocupação",
    casas: 1, sufixo: "%", destaque: true },
  { id: "renda", arquivo: "data/renda.json", area: "trabalho", titulo: "Rendimento médio real do trabalho",
    casas: 0, prefixo: "R$ " },
  { id: "emprego_formal", arquivo: "data/emprego_formal.json", area: "trabalho",
    titulo: "Emprego formal, saldo do mês (Novo Caged)", casas: 0 },
  // ----- Contas públicas -----
  { id: "divida_bruta", arquivo: "data/divida_bruta.json", area: "contas",
    titulo: "Dívida bruta do governo geral", casas: 2, sufixo: "%", destaque: true },
  { id: "divida_liquida", arquivo: "data/divida_liquida.json", area: "contas",
    titulo: "Dívida líquida do setor público", casas: 2, sufixo: "%" },
  { id: "resultado_primario", arquivo: "data/resultado_primario.json", area: "contas",
    titulo: "Resultado primário (NFSP), acumulado em 12 meses", casas: 2, sufixo: "%" },
  // ----- Saúde -----
  { id: "mortalidade_menores_5", arquivo: "data/mortalidade_menores_5.json", area: "saude",
    titulo: "Mortalidade de menores de 5 anos", casas: 1 },
  { id: "mortalidade_materna", arquivo: "data/mortalidade_materna.json", area: "saude",
    titulo: "Mortalidade materna", casas: 1 },
  // ----- Educação -----
  { id: "analfabetismo", arquivo: "data/analfabetismo.json", area: "educacao",
    titulo: "Analfabetismo (15 anos ou mais)", casas: 1, sufixo: "%" },
  { id: "escolarizacao_15_17", arquivo: "data/escolarizacao_15_17.json", area: "educacao",
    titulo: "Escolarização de 15 a 17 anos", casas: 1, sufixo: "%" },
  { id: "conclusao_ensino_medio", arquivo: "data/conclusao_ensino_medio.json", area: "educacao",
    titulo: "Conclusão do ensino médio (20 a 22 anos)", casas: 1, sufixo: "%" },
  // ----- Segurança -----
  { id: "homicidios", arquivo: "data/homicidios.json", area: "seguranca",
    titulo: "Homicídios intencionais", casas: 2 },
];

// Valores usados quando o JSON não traz o campo (formato antigo, só do BCB)
const PADRAO_FONTE = {
  sigla: "BCB/SGS",
  pagina: "https://www3.bcb.gov.br/sgspub/",
  licenca: "ODbL (Open Data Commons Open Database License)",
  linkLicenca: "https://opendatacommons.org/licenses/odbl/",
};

// Estado da página: o que já foi carregado e o que está escolhido nos botões
const carregados = [];    // [{ config, json }]
let mandatos = [];        // lista vinda de data/mandatos.json
let mandatoAtual = null;  // mandato escolhido (null = sem filtro)
let periodo = "todos";    // "todos", "12" ou "6" (meses)

/* ---------- Pequenas funções de formatação ---------- */

const MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];

// "2026-09" -> "setembro de 2026"
function mesPorExtenso(aaaaMm) {
  const [ano, mes] = aaaaMm.split("-").map(Number);
  return new Date(ano, mes - 1, 1).toLocaleDateString("pt-BR", { month: "long", year: "numeric" });
}

// "2026-11-13" -> "13/11/2026"
function diaBR(aaaaMmDd) {
  const [ano, mes, dia] = aaaaMmDd.split("-");
  return dia + "/" + mes + "/" + ano;
}

// "2026-11-10T20:42:19-03:00" -> "10/11/2026 às 20:42"
function dataHora(iso) {
  const d = new Date(iso);
  const opcoes = { timeZone: "America/Sao_Paulo" };
  return d.toLocaleDateString("pt-BR", opcoes) + " às " +
         d.toLocaleTimeString("pt-BR", { ...opcoes, hour: "2-digit", minute: "2-digit" });
}

// Nome do período de um ponto, conforme a periodicidade da série.
//   estilo "longo" = frase ("setembro de 2026"), "curto" = dica do gráfico
//   ("set/2026") e "eixo" = rótulo embaixo do gráfico ("set").
function nomeDoPeriodo(d, periodicidade, estilo) {
  const [ano, mes] = d.data.split("-").map(Number);
  if (periodicidade === "anual") return String(ano);
  if (periodicidade === "trimestral") {
    // O arquivo guarda o último mês do trimestre: 03, 06, 09 ou 12
    const tri = Math.ceil(mes / 3) + "º";
    if (estilo === "longo") return tri + " trimestre de " + ano;
    return estilo === "eixo" ? tri + " tri" : tri + " tri/" + ano;
  }
  if (periodicidade === "trimestre_movel") {
    // Trimestre móvel do IBGE: três meses seguidos, terminando no mês guardado
    const tres = [mes - 3, mes - 2, mes - 1].map(i => MESES[(i + 12) % 12]).join("-");
    if (estilo === "longo") return "trimestre " + tres + " de " + ano;
    return estilo === "eixo" ? MESES[mes - 1] : tres + "/" + ano;
  }
  // Mensal (e séries diárias guardadas como "último dia de cada mês")
  if (estilo === "longo") return mesPorExtenso(d.data);
  return mesCurto(d.data, estilo === "eixo");
}

// Escreve o número do jeito de cada indicador: "0,82%", "R$ 3.790", "5,65"
function valorFormatado(config, v) {
  return (config.prefixo || "") + numeroBR(v, config.casas) + (config.sufixo || "");
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

/* ---------- Mandatos e períodos ---------- */

// Um mandato começa e termina em dias quaisquer, mas os dados são mensais.
// Regra: o mês conta para o mandato que estava em exercício no dia 15.
function primeiroMes(inicio) {            // "2027-01-05" -> "2027-01"
  const [ano, mes, dia] = inicio.split("-").map(Number);
  if (dia <= 15) return inicio.slice(0, 7);
  return mes === 12 ? (ano + 1) + "-01" : ano + "-" + String(mes + 1).padStart(2, "0");
}
function ultimoMes(fim) {                 // "2027-01-04" -> "2026-12"
  const [ano, mes, dia] = fim.split("-").map(Number);
  if (dia >= 15) return fim.slice(0, 7);
  return mes === 1 ? (ano - 1) + "-12" : ano + "-" + String(mes - 1).padStart(2, "0");
}

// Fica só com os pontos que caem dentro do mandato escolhido
function noMandato(dados) {
  if (!mandatoAtual) return dados;
  const de = primeiroMes(mandatoAtual.inicio);
  const ate = mandatoAtual.fim ? ultimoMes(mandatoAtual.fim) : "9999-12";
  return dados.filter(d => d.data >= de && d.data <= ate);   // "aaaa-mm" compara como texto
}

// Recorta pelos botões de período: os últimos N meses contados a partir do
// ponto mais recente (assim funciona igual para série mensal, trimestral ou anual)
function recortar(dados) {
  if (periodo === "todos" || !dados.length) return dados;
  const [ano, mes] = dados[dados.length - 1].data.split("-").map(Number);
  const total = ano * 12 + (mes - 1) - Number(periodo);      // mês limite (não entra)
  const limite = Math.floor(total / 12) + "-" + String(total % 12 + 1).padStart(2, "0");
  return dados.filter(d => d.data > limite);
}

function nomeDoMandato(m) {
  return (m.nome_curto || m.presidente) + " · " + m.numero + "º mandato";
}

// Botões de mandato. Mandato "futuro" aparece desligado, com "Em breve".
function desenharMandatos() {
  const caixa = document.getElementById("mandatos");
  caixa.innerHTML = "";
  if (!mandatos.length) { document.getElementById("linha-mandatos").hidden = true; return; }
  for (const m of mandatos) {
    const futuro = m.status === "futuro";
    const b = criar("button", "botao", nomeDoMandato(m) + (futuro ? " · Em breve" : ""));
    b.type = "button";
    b.disabled = futuro;
    b.setAttribute("aria-pressed", String(m === mandatoAtual));
    b.addEventListener("click", () => { mandatoAtual = m; periodo = "todos"; desenharTudo(); });
    caixa.append(b);
  }
  document.getElementById("linha-mandatos").hidden = false;
}

/* ---------- Montagem de cada parte ---------- */

// Junta os campos de fonte do JSON (com valores padrão para o formato antigo)
function dadosDaFonte(json) {
  const s = json.serie;
  return {
    sigla: s.fonte_sigla || PADRAO_FONTE.sigla,
    pagina: s.url_pagina || PADRAO_FONTE.pagina,
    identificacao: s.identificacao || "série " + s.codigo,
    licenca: s.licenca || PADRAO_FONTE.licenca,
    // Campo ausente = formato antigo (BCB). Campo vazio = a fonte não tem página
    // oficial de licença confirmada (IBGE): o texto aparece sem link.
    linkLicenca: "url_licenca" in s ? s.url_licenca : PADRAO_FONTE.linkLicenca,
  };
}

// Um ponto de série diária é de "mês em andamento" quando é do mesmo mês da
// extração (as duas datas vêm do JSON; nada é calculado sobre os valores).
function mesEmAndamento(d, json) {
  return Boolean(d.dia) && d.data === json.extraido_em.slice(0, 7);
}

// "mês em andamento, até 14/11"
function textoEmAndamento(d) {
  return "mês em andamento, até " + diaBR(d.dia).slice(0, 5);
}

// Linha curta de fonte: série, origem, data de extração, link e licença
function linhaDeFonte(json) {
  const s = json.serie, f = dadosDaFonte(json);
  const p = criar("p", "fonte-linha");
  p.append(
    "Fonte: ", link(f.sigla, f.pagina), ", " + f.identificacao + " (origem " + s.origem + ") · ",
    "extraído em " + dataHora(json.extraido_em) + " · ",
    link("dados da consulta", s.url_fonte), " · ",
    // Sem página de licença: mostra o texto de citação (ex.: IBGE)
    f.linkLicenca ? link("licença", f.linkLicenca) : f.licenca
  );
  return p;
}

// Cartão de destaque da abertura (valor mais recente dentro do mandato)
function cartaoDestaque(config, json) {
  const dados = noMandato(json.dados);
  if (!dados.length) return null;
  const ultimo = dados[dados.length - 1];
  // Séries diárias guardam o dia exato em "dia"; as outras, só o período
  let referencia = ultimo.dia ? diaBR(ultimo.dia)
                              : nomeDoPeriodo(ultimo, json.serie.periodicidade, "longo");
  if (mesEmAndamento(ultimo, json)) referencia += " (" + textoEmAndamento(ultimo) + ")";
  const c = criar("article", "destaque");
  c.append(
    criar("p", "rotulo", config.titulo + " · " + json.serie.unidade),
    criar("p", "numero", valorFormatado(config, ultimo.valor)),
    criar("p", "referencia secundario", "Referência: " + referencia),
    linhaDeFonte(json)
  );
  return c;
}

// Cartão da grade de indicadores: título, gráfico, tabela e fonte
function cartaoIndicador(config, json) {
  const per = json.serie.periodicidade;
  const dados = recortar(noMandato(json.dados));
  const c = criar("article", "cartao");
  c.append(criar("h4", "", config.titulo + " · " + json.serie.unidade));
  c.desenhar = () => {};

  if (!dados.length) {
    c.append(criar("p", "subtitulo", json.serie.nome),
             criar("p", "secundario", "A fonte ainda não publicou dados para este mandato."),
             linhaDeFonte(json));
    return c;
  }

  const primeiro = dados[0], ultimo = dados[dados.length - 1];
  const intervalo = dados.length === 1
    ? nomeDoPeriodo(ultimo, per, "longo")
    : "de " + nomeDoPeriodo(primeiro, per, "longo") + " a " + nomeDoPeriodo(ultimo, per, "longo");
  c.append(criar("p", "subtitulo", json.serie.nome + ", " + intervalo));
  // Observação que vem junto com os dados (ex.: como ler o sinal do número)
  if (json.serie.observacao) c.append(criar("p", "nota", json.serie.observacao));

  // Texto lido por leitores de tela no lugar do desenho
  const valores = dados.map(d => d.valor);
  const titulo = "Gráfico de colunas: " + config.titulo + ", " + json.serie.unidade + ", " + intervalo +
    ". Menor valor " + valorFormatado(config, Math.min(...valores)) +
    ", maior valor " + valorFormatado(config, Math.max(...valores)) +
    ". Os números estão na tabela logo abaixo.";

  const area = criar("div", "grafico");
  c.append(area);
  // Último mês ainda não terminou (Selic, dólar): avisa embaixo do gráfico
  if (mesEmAndamento(ultimo, json)) {
    c.append(criar("p", "nota", "A última coluna (" + nomeDoPeriodo(ultimo, per, "curto") +
      ") é do " + textoEmAndamento(ultimo) + "/" + ultimo.dia.slice(0, 4) + "."));
  }

  // Tabela com os mesmos números do gráfico (mais recente primeiro)
  const det = criar("details");
  det.append(criar("summary", "", "Ver os números em tabela"));
  const rolagem = criar("div", "rolagem");
  const tabela = criar("table");
  const cabeca = criar("thead"), linhaCabeca = criar("tr");
  for (const texto of ["Período", "Valor (" + json.serie.unidade + ")"]) {
    const th = criar("th", "", texto);
    th.scope = "col";
    linhaCabeca.append(th);
  }
  cabeca.append(linhaCabeca);
  const corpo = criar("tbody");
  for (const d of [...dados].reverse()) {
    const tr = criar("tr");
    const nome = nomeDoPeriodo(d, per, "longo") +
      (d.dia ? " (dia " + diaBR(d.dia) + (mesEmAndamento(d, json) ? ", mês em andamento" : "") + ")" : "");
    tr.append(criar("td", "", nome), criar("td", "", numeroBR(d.valor, config.casas)));
    corpo.append(tr);
  }
  tabela.append(cabeca, corpo);
  rolagem.append(tabela);
  det.append(rolagem);
  c.append(det, linhaDeFonte(json));

  // O gráfico precisa saber a largura do cartão, então é desenhado depois
  // que o cartão entra na página (ver desenharGrade).
  c.desenhar = () => desenharColunas(area, dados, {
    titulo,
    formatar: v => valorFormatado(config, v),
    // Na dica do gráfico, o mês em andamento ganha o aviso "até dd/mm"
    rotulo: (d, estilo) => nomeDoPeriodo(d, per, estilo) +
      (estilo === "curto" && mesEmAndamento(d, json) ? " (" + textoEmAndamento(d) + ")" : ""),
  });
  return c;
}

// Linha de fonte do rodapé (texto completo pedido para a licença)
function fonteRodape(config, json) {
  const s = json.serie, f = dadosDaFonte(json);
  const li = criar("li");
  li.append(
    criar("strong", "", config.titulo + ": "),
    link(s.fonte, f.pagina), ", " + f.identificacao + " (" + s.nome + "; " + s.unidade +
    "; origem " + s.origem + "). Extraído em " + dataHora(json.extraido_em) + ". ",
    // Com página de licença: "Licença: <link>". Sem (IBGE): "Uso dos dados: <texto>"
    f.linkLicenca ? "Licença: " : "Uso dos dados: ",
    f.linkLicenca ? link(f.licenca, f.linkLicenca) : f.licenca, "."
  );
  return li;
}

/* ---------- Desenho e eventos ---------- */

// Cartões de destaque da abertura
function desenharDestaques() {
  const caixa = document.getElementById("destaques");
  caixa.innerHTML = "";
  for (const { config, json } of carregados) {
    if (!config.destaque) continue;
    const cartao = cartaoDestaque(config, json);
    if (cartao) caixa.append(cartao);
  }
}

// Grade de indicadores, separada por área (Economia, Saúde...)
function desenharGrade() {
  const caixa = document.getElementById("areas");
  caixa.innerHTML = "";
  const cartoes = [];
  for (const area of AREAS) {
    const daArea = carregados.filter(c => c.config.area === area.id);
    if (!daArea.length) continue;
    const secao = criar("section", "area");
    const h3 = criar("h3", "", area.titulo);
    h3.id = "area-" + area.id;
    secao.setAttribute("aria-labelledby", h3.id);
    const grade = criar("div", "grade");
    for (const { config, json } of daArea) {
      const cartao = cartaoIndicador(config, json);
      grade.append(cartao);
      cartoes.push(cartao);
    }
    secao.append(h3, grade);
    caixa.append(secao);
  }
  cartoes.forEach(c => c.desenhar());
}

// Marca o botão de período ativo e escreve "Desde 2023" conforme o mandato
function desenharPeriodos() {
  document.querySelectorAll(".botao[data-meses]").forEach(b => {
    b.setAttribute("aria-pressed", String(b.dataset.meses === periodo));
    if (b.dataset.meses === "todos" && mandatoAtual) {
      b.textContent = mandatoAtual.fim ? "Mandato inteiro" : "Desde " + mandatoAtual.inicio.slice(0, 4);
    }
  });
}

function desenharTudo() {
  desenharMandatos();
  desenharPeriodos();
  desenharDestaques();
  desenharGrade();
}

// Botões de período: guardam a escolha e redesenham os gráficos
function ligarBotoesDePeriodo() {
  document.querySelectorAll(".botao[data-meses]").forEach(b => b.addEventListener("click", () => {
    periodo = b.dataset.meses;
    desenharPeriodos();
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

async function baixarJson(arquivo) {
  const resposta = await fetch(arquivo, { cache: "no-cache" });
  if (!resposta.ok) throw new Error("HTTP " + resposta.status);
  return resposta.json();
}

function avisar(texto) {
  const aviso = document.getElementById("aviso-erro");
  aviso.hidden = false;
  aviso.textContent += texto + " ";
}

async function iniciar() {
  ligarBotoesDePeriodo();
  ligarAbas();

  // 1) Mandatos: escolhe o que está em andamento. Se o arquivo falhar,
  //    a página mostra todos os dados, sem filtro, e avisa.
  try {
    mandatos = (await baixarJson("data/mandatos.json")).mandatos;
    mandatoAtual = mandatos.find(m => m.status === "em_andamento") ||
                   [...mandatos].reverse().find(m => m.status === "encerrado") || null;
  } catch (erro) {
    avisar("Não foi possível carregar a lista de mandatos (" + erro.message + ").");
  }

  // 2) Indicadores: baixa todos ao mesmo tempo; um que falhe não derruba os outros
  const respostas = await Promise.allSettled(INDICADORES.map(c => baixarJson(c.arquivo)));
  respostas.forEach((r, i) => {
    const config = INDICADORES[i];
    if (r.status === "fulfilled") carregados.push({ config, json: r.value });
    else avisar("Não foi possível carregar " + config.titulo + " (" + r.reason.message + ").");
  });
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
    document.getElementById("lista-fontes").append(fonteRodape(config, json));
  }
  desenharTudo();
}

iniciar();
