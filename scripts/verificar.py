"""
Verificador do painel: confere se os indicadores continuam corretos e
atualizados em relação às fontes oficiais.

IMPORTANTE: este script só APONTA problemas. Ele nunca corrige dados,
códigos de série nem arquivos do site, e nunca grava nada em data/ ou assets/.
Quem corrige é o usuário (regra 2 do CLAUDE.md).

Como rodar (a partir da pasta do projeto):
    python3 scripts/verificar.py
    python3 scripts/verificar.py selic pib          # só alguns indicadores
    python3 scripts/verificar.py --hoje 2027-01-10  # finge outra data (testes)
    python3 scripts/verificar.py --raiz /outra/copia # verifica outra cópia do projeto (testes)

Saída: relatório com ERROS, AVISOS e OK por indicador.
Código de saída 1 se houver algum erro; 0 se houver só avisos (ou nada).
No GitHub Actions, o relatório também vai em Markdown para a página da execução.

O que é checado:
  a) metadados oficiais (nome, unidade, periodicidade) contra o que o painel declara;
  b) 3 valores (primeiro, último e um sorteado), buscados de novo por outro
     endereço da API, contra o JSON publicado;
  c) se a série está atualizada (ver ATRASO_MAXIMO_DIAS);
  d) esquema do JSON (campos, tipos, ordem dos meses, fonte, link, licença);
  e) consistência entre data/*.json, scripts/coletar.py e assets/painel.js,
     e se os links url_fonte respondem;
  f) data/mandatos.json (datas, sobreposição, status coerente com hoje).

Usa só a biblioteca padrão do Python.
"""

import argparse
import calendar
import gzip
import importlib.util
import json
import math
import os
import random
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

FUSO = ZoneInfo("America/Sao_Paulo")
TIMEOUT = 40          # segundos por chamada de rede
NOVAS_TENTATIVAS = 2  # além da primeira tentativa
ESPERA = 4            # segundos entre tentativas (dobra a cada vez)

# Atraso máximo aceitável entre o FIM do período do último dado e hoje,
# por periodicidade. Passou disso, o verificador dá um aviso.
# Regra: duração de um período (o dado seguinte ainda não terminou) + prazo
# de divulgação da fonte + folga. Ex.: o PIB do 2º tri (fim 30/06) só é
# substituído pelo do 3º tri no início de dezembro, ~160 dias depois.
ATRASO_MAXIMO_DIAS = {
    "diaria": 7,             # Selic e dólar: dias úteis; folga para feriados prolongados
    "mensal": 75,            # IPCA sai ~10 dias depois do mês; fiscais e Caged ~30-45 dias
    "trimestre_movel": 75,   # PNAD Contínua: ~30 dias depois do fim do trimestre móvel
    "trimestral": 170,       # PIB: 3 meses do trimestre seguinte + ~65 dias de divulgação + folga
    "anual": 1200,           # indicadores ODS e PNAD anual saem com 1 a 3 anos de atraso
}
EXTRAIDO_MAXIMO_DIAS = 3     # extraido_em mais velho que isso = robô parado

# Tolerância na comparação de valores (o JSON guarda o número da API sem arredondar,
# então qualquer diferença acima disto é divergência real).
TOLERANCIA = 1e-6

# Unidades com nomes diferentes que querem dizer a mesma coisa.
# Chave: unidade oficial (minúsculas). Valor: unidades aceitas no painel.
UNIDADES_EQUIVALENTES = {
    "percentual ao ano": {"% ao ano", "% a.a."},
    "percentual": {"%", "% do pib"},
    "taxa unidade monetária corrente/dólar americano": {"r$ por us$"},
    "pessoa": {"pessoas"},
}

# Periodicidades oficiais (como cada fonte escreve) -> como o painel escreve
PERIODICIDADES = {
    "diária": "diaria", "diaria": "diaria", "mensal": "mensal",
    "trimestral móvel": "trimestre_movel", "trimestral": "trimestral", "anual": "anual",
}

CATALOGO_BCB = "https://dadosabertos.bcb.gov.br/api/3/action/package_search?rows=20&q=codigo_sgs:{codigo}"
METADADOS_IBGE = "https://servicodados.ibge.gov.br/api/v3/agregados/{tabela}/metadados"
METADADOS_IPEA = "https://www.ipeadata.gov.br/api/odata4/Metadados('{codigo}')"
# Endereços "independentes" para os valores: diferentes dos usados na coleta
VALOR_SGS = ("https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"
             "?formato=json&dataInicial={inicio}&dataFinal={fim}")      # janela curta, só o período
VALOR_SIDRA = "https://apisidra.ibge.gov.br/values/t/{tabela}/n1/all/v/{variavel}/p/{periodo}{classificacoes}"
VALOR_IPEA = "https://www.ipeadata.gov.br/api/odata4/Metadados('{codigo}')/Valores"

CAMPOS_SERIE = ["codigo", "identificacao", "nome", "unidade", "periodicidade", "origem",
                "fonte", "fonte_sigla", "licenca", "url_licenca", "url_fonte", "url_pagina"]


# ---------------------------------------------------------------------------
# Rede
# ---------------------------------------------------------------------------
class ErroDeRede(Exception):
    """A rede ou o servidor falhou (não é culpa do dado)."""


def baixar(url, como_json=True):
    """Baixa um endereço com timeout e até NOVAS_TENTATIVAS novas tentativas."""
    pedido = urllib.request.Request(url, headers={"User-Agent": "painel-verificador/1.0 (python-urllib)"})
    espera = ESPERA
    for tentativa in range(NOVAS_TENTATIVAS + 1):
        try:
            with urllib.request.urlopen(pedido, timeout=TIMEOUT) as r:
                bruto = r.read()
            if bruto[:2] == b"\x1f\x8b":          # resposta compactada (IBGE faz isso)
                bruto = gzip.decompress(bruto)
            return json.loads(bruto.decode("utf-8-sig")) if como_json else bruto
        except urllib.error.HTTPError as e:
            if 400 <= e.code < 500:               # pedido errado: repetir não adianta
                raise
            ultimo = e
        except Exception as e:                    # timeout, conexão caiu etc.
            ultimo = e
        if tentativa < NOVAS_TENTATIVAS:
            time.sleep(espera)
            espera *= 2
    raise ErroDeRede(f"{type(ultimo).__name__}: {ultimo} (depois de {NOVAS_TENTATIVAS + 1} tentativas)")


# ---------------------------------------------------------------------------
# Pequenas ajudas
# ---------------------------------------------------------------------------
def normalizar(texto):
    """Minúsculas, sem acento e sem espaços repetidos (para comparar nomes)."""
    t = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", t).strip().lower()


def unidades_batem(oficial, painel):
    o, p = str(oficial).strip().lower(), str(painel).strip().lower()
    return o == p or p in UNIDADES_EQUIVALENTES.get(o, set())


def fim_do_periodo(ponto, periodicidade):
    """Último dia do período a que o ponto se refere."""
    if ponto.get("dia"):
        return date.fromisoformat(ponto["dia"])
    ano, mes = map(int, ponto["data"].split("-"))
    return date(ano, mes, calendar.monthrange(ano, mes)[1])


def codigo_periodo_sidra(aaaa_mm, periodicidade):
    """Inverso do que o coletor faz: "2026-06" -> "202602" (trimestral) etc."""
    ano, mes = aaaa_mm.split("-")
    if periodicidade == "anual":
        return ano
    if periodicidade == "trimestral":
        return f"{ano}{int(mes) // 3:02d}"
    return f"{ano}{mes}"


class Resultado:
    """Guarda ERROS, AVISOS e OK de uma parte do relatório."""
    def __init__(self, titulo):
        self.titulo, self.erros, self.avisos, self.ok = titulo, [], [], []


# ---------------------------------------------------------------------------
# a) Metadados oficiais
# ---------------------------------------------------------------------------
def checar_metadados(ind, r):
    tipo = ind["tipo"]
    per_painel = "diaria" if ind.get("diaria") else ind["periodicidade"]
    try:
        if tipo == "sgs":
            achados = [p for p in baixar(CATALOGO_BCB.format(codigo=ind["codigo"]))["result"]["results"]
                       if str(p.get("codigo_sgs")) == str(ind["codigo"])]
            if not achados:
                # Sem ficha no catálogo: ao menos confirma se o código existe na API
                try:
                    baixar(f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{ind['codigo']}/dados/ultimos/1?formato=json")
                except urllib.error.HTTPError as e:
                    r.erros.append(f"SGS {ind['codigo']} não existe (API respondeu HTTP {e.code}) "
                                   "e não tem ficha no catálogo do BCB.")
                    return
                r.avisos.append(f"SGS {ind['codigo']} não tem ficha no catálogo de dados abertos do BCB: "
                                "nome, unidade e periodicidade não puderam ser conferidos automaticamente.")
                return
            p = achados[0]
            nome, unidade, per = p["title"], p.get("unidade_medida", ""), p.get("periodicidade", "")
        elif tipo == "sidra":
            m = baixar(METADADOS_IBGE.format(tabela=ind["tabela"]))
            var = [v for v in m["variaveis"] if v["id"] == ind["variavel"]]
            if not var:
                r.erros.append(f"Variável {ind['variavel']} não existe na tabela {ind['tabela']} do IBGE.")
                return
            nome, unidade, per = var[0]["nome"], var[0]["unidade"], m["periodicidade"]["frequencia"]
            r.ok.append(f"Tabela oficial: {m['nome']} (pesquisa: {m['pesquisa']}).")
            if ind.get("variavel_nome") and ind["variavel_nome"] != nome:
                r.erros.append(f"Nome da variável que o coletor exige ({ind['variavel_nome']!r}) "
                               f"difere do oficial ({nome!r}): a coleta vai recusar os dados.")
            # Classificações usadas no filtro (ex.: /c2/6794/c58/2795) precisam existir
            partes = [x for x in ind.get("classificacoes", "").split("/") if x]
            for cls, cat in zip(partes[::2], partes[1::2]):
                c = [x for x in m["classificacoes"] if f"c{x['id']}" == cls]
                if not c:
                    r.erros.append(f"Classificação {cls} não existe na tabela {ind['tabela']}.")
                elif not [x for x in c[0]["categorias"] if str(x["id"]) == cat]:
                    r.erros.append(f"Categoria {cat} não existe na classificação {cls} ({c[0]['nome']}).")
                else:
                    nome_cat = [x for x in c[0]["categorias"] if str(x["id"]) == cat][0]["nome"]
                    r.ok.append(f"Filtro {cls}/{cat} = {c[0]['nome']}: {nome_cat}.")
        else:  # ipea
            v = baixar(METADADOS_IPEA.format(codigo=urllib.parse.quote(ind["codigo"])))["value"]
            if not v:
                r.erros.append(f"Série {ind['codigo']} não existe no Ipeadata.")
                return
            nome, unidade, per = v[0]["SERNOME"], v[0]["UNINOME"], v[0]["PERNOME"]
            if v[0].get("SERSTATUS") != "A":
                r.avisos.append(f"Ipeadata marca a série como inativa (SERSTATUS={v[0].get('SERSTATUS')}).")
    except ErroDeRede as e:
        r.avisos.append(f"Metadados não conferidos: a rede falhou ({e}).")
        return
    except urllib.error.HTTPError as e:
        r.erros.append(f"Metadados: a fonte respondeu HTTP {e.code} (código ou tabela inexistente?).")
        return

    # Comparações
    lado = f"nome no painel: {ind['nome']!r} | nome oficial: {nome!r}"
    if normalizar(nome) == normalizar(ind["nome"]):
        r.ok.append("Nome confere. " + lado)
    else:
        r.avisos.append("Nome diferente do oficial (pode ser só um nome mais amigável). " + lado)
    if unidades_batem(unidade, ind["unidade"]):
        r.ok.append(f"Unidade confere: painel {ind['unidade']!r} | oficial {unidade!r}.")
    else:
        r.erros.append(f"Unidade diverge: painel {ind['unidade']!r} | oficial {unidade!r}.")
    per_oficial = PERIODICIDADES.get(str(per).strip().lower(), str(per))
    if per_oficial == per_painel:
        r.ok.append(f"Periodicidade confere: {per!r}.")
    else:
        r.erros.append(f"Periodicidade diverge: painel {per_painel!r} | oficial {per!r}.")


# ---------------------------------------------------------------------------
# b) Valores
# ---------------------------------------------------------------------------
def valor_oficial(ind, ponto):
    """Busca um único ponto por um endereço diferente do usado na coleta."""
    if ind["tipo"] == "sgs":
        if ponto.get("dia"):
            dia = date.fromisoformat(ponto["dia"])
            inicio = fim = dia.strftime("%d/%m/%Y")
        else:
            ano, mes = map(int, ponto["data"].split("-"))
            inicio = f"01/{mes:02d}/{ano}"
            fim = f"{calendar.monthrange(ano, mes)[1]:02d}/{mes:02d}/{ano}"
        lista = baixar(VALOR_SGS.format(codigo=ind["codigo"], inicio=inicio, fim=fim))
        return float(lista[-1]["valor"]) if lista else None
    if ind["tipo"] == "sidra":
        url = VALOR_SIDRA.format(tabela=ind["tabela"], variavel=ind["variavel"],
                                 periodo=codigo_periodo_sidra(ponto["data"], ind["periodicidade"]),
                                 classificacoes=ind.get("classificacoes", ""))
        linhas = baixar(url)
        try:
            return float(linhas[1]["V"]) if len(linhas) > 1 else None
        except ValueError:
            return None
    for item in baixar(VALOR_IPEA.format(codigo=urllib.parse.quote(ind["codigo"])))["value"]:
        if item["VALDATA"][:7] == ponto["data"] and item["VALVALOR"] is not None:
            return float(item["VALVALOR"])
    return None


def checar_valores(ind, dados, r, sorteio):
    if not dados:
        return
    indices = sorted({0, len(dados) - 1, sorteio.randrange(len(dados))})
    for i in indices:
        p = dados[i]
        rotulo = p["data"] + (f" (dia {p['dia']})" if p.get("dia") else "")
        try:
            oficial = valor_oficial(ind, p)
        except ErroDeRede as e:
            r.avisos.append(f"Valor de {rotulo} não conferido: a rede falhou ({e}).")
            continue
        except urllib.error.HTTPError as e:
            r.erros.append(f"Valor de {rotulo}: a fonte respondeu HTTP {e.code}.")
            continue
        if oficial is None:
            r.erros.append(f"Valor de {rotulo}: a fonte não tem mais esse período (no painel: {p['valor']}).")
        elif abs(oficial - p["valor"]) > TOLERANCIA * max(1, abs(oficial)):
            r.erros.append(f"Valor de {rotulo} diverge: painel {p['valor']} | fonte {oficial}.")
        else:
            r.ok.append(f"Valor de {rotulo} confere: {p['valor']}.")


# ---------------------------------------------------------------------------
# c) Atualização
# ---------------------------------------------------------------------------
def checar_atualizacao(ind, json_, r, hoje):
    dados = json_.get("dados") or []
    if dados and isinstance(dados[-1], dict) and "data" in dados[-1]:
        per = "diaria" if ind.get("diaria") else ind["periodicidade"]
        try:
            atraso = (hoje - fim_do_periodo(dados[-1], per)).days
            limite = ATRASO_MAXIMO_DIAS[per]
            if atraso > limite:
                r.avisos.append(f"Série parada: último dado {dados[-1].get('dia') or dados[-1]['data']}, "
                                f"{atraso} dias atrás (limite para {per}: {limite} dias).")
            else:
                r.ok.append(f"Último dado em dia ({dados[-1].get('dia') or dados[-1]['data']}; "
                            f"{atraso} de no máximo {limite} dias).")
        except (ValueError, KeyError):
            pass  # data malformada já vira erro no esquema
    try:
        extraido = datetime.fromisoformat(json_["extraido_em"])
        dias = (hoje - extraido.astimezone(FUSO).date()).days
        if dias > EXTRAIDO_MAXIMO_DIAS:
            r.avisos.append(f"extraido_em é de {json_['extraido_em']} ({dias} dias): a rotina diária parou?")
        else:
            r.ok.append(f"Extraído em {json_['extraido_em']}.")
    except (KeyError, TypeError, ValueError):
        pass


# ---------------------------------------------------------------------------
# d) Esquema do JSON
# ---------------------------------------------------------------------------
def checar_esquema(json_, r, diaria):
    s = json_.get("serie")
    if not isinstance(s, dict):
        r.erros.append("Falta o bloco 'serie'.")
        return
    for campo in CAMPOS_SERIE:
        if campo not in s or s[campo] in (None, ""):
            r.erros.append(f"Campo serie.{campo} ausente ou vazio.")
    if not isinstance(s.get("codigo"), (int, str)):
        r.erros.append("serie.codigo deveria ser número ou texto.")
    for campo in ("url_fonte", "url_pagina", "url_licenca"):
        if s.get(campo) and not str(s[campo]).startswith(("http://", "https://")):
            r.erros.append(f"serie.{campo} não é um link: {s[campo]!r}.")
    if s.get("periodicidade") not in ATRASO_MAXIMO_DIAS:
        r.erros.append(f"serie.periodicidade inválida: {s.get('periodicidade')!r}.")
    try:
        datetime.fromisoformat(json_["extraido_em"])
        if not str(json_["extraido_em"]).endswith("-03:00"):
            r.avisos.append(f"extraido_em sem o fuso -03:00: {json_['extraido_em']!r}.")
    except (KeyError, TypeError, ValueError):
        r.erros.append(f"extraido_em ausente ou fora do formato ISO: {json_.get('extraido_em')!r}.")
    dados = json_.get("dados")
    if not isinstance(dados, list) or not dados:
        r.erros.append("'dados' ausente ou vazio.")
        return
    datas = []
    for i, d in enumerate(dados):
        if not isinstance(d, dict) or not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", str(d.get("data"))):
            r.erros.append(f"dados[{i}].data fora do formato aaaa-mm: {d!r}.")
            return
        v = d.get("valor")
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
            r.erros.append(f"dados[{i}].valor não é número: {v!r}.")
        if diaria and not (isinstance(d.get("dia"), str) and d["dia"][:7] == d["data"]):
            r.erros.append(f"dados[{i}].dia ausente ou de outro mês: {d.get('dia')!r}.")
        datas.append(d["data"])
    if datas != sorted(datas):
        r.erros.append("Os períodos não estão em ordem.")
    if len(datas) != len(set(datas)):
        r.erros.append("Há períodos repetidos.")
    if not r.erros:
        r.ok.append(f"Esquema do JSON correto ({len(datas)} períodos).")


# ---------------------------------------------------------------------------
# e) Consistência da página
# ---------------------------------------------------------------------------
def checar_pagina(raiz, indicadores, r):
    painel = open(os.path.join(raiz, "assets", "painel.js"), encoding="utf-8").read()
    no_painel = set(re.findall(r'arquivo:\s*"data/([\w-]+)\.json"', painel))
    em_data = {f[:-5] for f in os.listdir(os.path.join(raiz, "data"))
               if f.endswith(".json") and f != "mandatos.json"}
    no_coletor = {ind["id"] for ind in indicadores}
    for nome in sorted(em_data - no_painel):
        r.erros.append(f"data/{nome}.json existe mas não está na lista INDICADORES do painel.js.")
    for nome in sorted(no_painel - em_data):
        r.erros.append(f"painel.js lista data/{nome}.json, mas o arquivo não existe.")
    for nome in sorted(no_coletor - no_painel):
        r.erros.append(f"'{nome}' está em scripts/coletar.py mas não no painel.js.")
    for nome in sorted(no_painel - no_coletor):
        r.erros.append(f"'{nome}' está no painel.js mas não em scripts/coletar.py.")
    if no_painel == em_data == no_coletor:
        r.ok.append(f"Os {len(em_data)} indicadores batem entre data/, coletar.py e painel.js.")


def checar_link(json_, r):
    url = (json_.get("serie") or {}).get("url_fonte")
    if not url:
        return
    try:
        baixar(url, como_json=False)
        r.ok.append("Link url_fonte responde.")
    except urllib.error.HTTPError as e:
        r.avisos.append(f"Link url_fonte respondeu HTTP {e.code}: {url}")
    except ErroDeRede as e:
        r.avisos.append(f"Link url_fonte não respondeu ({e}): {url}")


# ---------------------------------------------------------------------------
# f) Mandatos
# ---------------------------------------------------------------------------
def checar_mandatos(raiz, r, hoje):
    try:
        lista = json.load(open(os.path.join(raiz, "data", "mandatos.json"), encoding="utf-8"))["mandatos"]
    except Exception as e:
        r.erros.append(f"data/mandatos.json ilegível: {e}")
        return
    validos = []
    for m in lista:
        nome = f"{m.get('id')!r}"
        for campo in ("id", "presidente", "numero", "inicio", "status"):
            if campo not in m:
                r.erros.append(f"Mandato {nome}: falta o campo {campo}.")
        if m.get("status") not in ("encerrado", "em_andamento", "futuro"):
            r.erros.append(f"Mandato {nome}: status inválido {m.get('status')!r}.")
        try:
            ini = date.fromisoformat(m["inicio"])
            fim = date.fromisoformat(m["fim"]) if m.get("fim") else None
        except (KeyError, TypeError, ValueError):
            r.erros.append(f"Mandato {nome}: data inválida (inicio={m.get('inicio')!r}, fim={m.get('fim')!r}).")
            continue
        if fim and fim < ini:
            r.erros.append(f"Mandato {nome}: fim ({fim}) antes do início ({ini}).")
        validos.append((ini, fim, m))
    validos.sort(key=lambda x: x[0])
    for (ini1, fim1, m1), (ini2, _, m2) in zip(validos, validos[1:]):
        if fim1 and fim1 >= ini2:
            r.erros.append(f"Mandatos {m1['id']!r} e {m2['id']!r} se sobrepõem ({fim1} ≥ {ini2}).")
    for i, (ini, fim, m) in enumerate(validos):
        proximo = validos[i + 1][0] if i + 1 < len(validos) else None
        st = m.get("status")
        if st == "futuro" and hoje >= ini:
            r.erros.append(f"Mandato {m['id']!r} começou em {ini}, mas ainda está como 'futuro'. "
                           "Mude para 'em_andamento' (e encerre o anterior).")
        if st == "em_andamento" and ((fim and hoje > fim) or (proximo and hoje >= proximo)):
            r.erros.append(f"Mandato {m['id']!r} está 'em_andamento', mas já terminou "
                           f"(fim {fim or 'vazio'}; o seguinte começou em {proximo}). "
                           "Ponha 'fim' e status 'encerrado'.")
        if st == "em_andamento" and hoje < ini:
            r.erros.append(f"Mandato {m['id']!r} está 'em_andamento', mas só começa em {ini}.")
        if st == "encerrado" and (not fim or hoje <= fim):
            r.erros.append(f"Mandato {m['id']!r} está 'encerrado' sem 'fim' no passado.")
    if not r.erros:
        r.ok.append(f"{len(lista)} mandatos com datas válidas, sem sobreposição e status coerente com {hoje}.")


# ---------------------------------------------------------------------------
# Relatório
# ---------------------------------------------------------------------------
def texto(resultados):
    linhas = []
    for r in resultados:
        situacao = "ERRO" if r.erros else ("AVISO" if r.avisos else "OK")
        linhas.append(f"\n=== {r.titulo} — {situacao} ===")
        for rotulo, itens in (("ERROS", r.erros), ("AVISOS", r.avisos), ("OK", r.ok)):
            if itens:
                linhas.append(f"  {rotulo}:")
                linhas += [f"    - {x}" for x in itens]
    return "\n".join(linhas)


def markdown(resultados, hoje):
    e = sum(len(r.erros) for r in resultados)
    a = sum(len(r.avisos) for r in resultados)
    md = [f"# Verificação do painel ({hoje})", "", f"**{e} erro(s), {a} aviso(s).** "
          "O verificador só aponta; nada foi corrigido.", "",
          "| Parte | Situação | Erros | Avisos |", "|---|---|---|---|"]
    for r in resultados:
        sit = "❌ erro" if r.erros else ("⚠️ aviso" if r.avisos else "✅ ok")
        md.append(f"| {r.titulo} | {sit} | {len(r.erros)} | {len(r.avisos)} |")
    for r in resultados:
        if r.erros or r.avisos:
            md += ["", f"## {r.titulo}"]
            md += [f"- ❌ {x}" for x in r.erros] + [f"- ⚠️ {x}" for x in r.avisos]
    return "\n".join(md) + "\n"


def carregar_coletor(raiz):
    """Lê a lista INDICADORES de scripts/coletar.py (fonte única dos códigos)."""
    caminho = os.path.join(raiz, "scripts", "coletar.py")
    spec = importlib.util.spec_from_file_location("coletar_verificado", caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)   # só define funções e listas; não coleta nada
    return modulo.INDICADORES


def main():
    sys.dont_write_bytecode = True    # não deixa __pycache__ para trás
    ap = argparse.ArgumentParser(description="Confere os indicadores do painel com as fontes oficiais.")
    ap.add_argument("ids", nargs="*", help="só estes indicadores (padrão: todos)")
    ap.add_argument("--raiz", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    help="pasta do projeto a verificar")
    ap.add_argument("--hoje", help="data de hoje no formato aaaa-mm-dd (para testes)")
    ap.add_argument("--semente", type=int, help="semente do sorteio do ponto do meio (para repetir um teste)")
    args = ap.parse_args()

    hoje = date.fromisoformat(args.hoje) if args.hoje else datetime.now(FUSO).date()
    sorteio = random.Random(args.semente)
    indicadores = carregar_coletor(args.raiz)
    escolhidos = [i for i in indicadores if not args.ids or i["id"] in args.ids]
    desconhecidos = set(args.ids) - {i["id"] for i in indicadores}
    if desconhecidos:
        sys.exit("Indicador desconhecido: " + ", ".join(sorted(desconhecidos)))

    resultados = []
    for ind in escolhidos:
        print(f"Verificando {ind['id']}...", flush=True)
        r = Resultado(f"{ind['id']} ({ind['tipo'].upper()} {ind.get('codigo', ind.get('tabela'))})")
        resultados.append(r)
        caminho = os.path.join(args.raiz, "data", ind["id"] + ".json")
        try:
            json_ = json.load(open(caminho, encoding="utf-8"))
        except FileNotFoundError:
            r.erros.append(f"Arquivo {caminho} não existe.")
            json_ = None
        except json.JSONDecodeError as e:
            r.erros.append(f"Arquivo {caminho} não é um JSON válido: {e}")
            json_ = None
        checar_metadados(ind, r)
        if json_ is not None:
            checar_esquema(json_, r, bool(ind.get("diaria")))
            checar_atualizacao(ind, json_, r, hoje)
            dados_ok = [d for d in json_.get("dados") or [] if isinstance(d, dict) and "data" in d
                        and isinstance(d.get("valor"), (int, float))]
            checar_valores(ind, dados_ok, r, sorteio)
            checar_link(json_, r)

    pagina = Resultado("Página (data/, coletar.py e painel.js)")
    checar_pagina(args.raiz, indicadores, pagina)
    mandatos = Resultado("Mandatos (data/mandatos.json)")
    checar_mandatos(args.raiz, mandatos, hoje)
    resultados += [pagina, mandatos]

    print(texto(resultados))
    erros = sum(len(r.erros) for r in resultados)
    avisos = sum(len(r.avisos) for r in resultados)
    print(f"\nRESUMO: {erros} erro(s), {avisos} aviso(s) em {len(resultados)} partes. "
          "Nada foi corrigido: o verificador só aponta.")

    # No GitHub Actions, o relatório vai também para a página da execução
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(markdown(resultados, hoje))
    sys.exit(1 if erros else 0)


if __name__ == "__main__":
    main()
