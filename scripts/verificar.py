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
     e se todos os links que o leitor pode clicar respondem (seção "Links da página");
  f) data/mandatos.json (datas, sobreposição, status coerente com hoje);
  g) data/noticias.json (esquema, títulos, datas e formato dos links; os links
     das matérias não são abertos, porque mudam todo dia).

Usa só a biblioteca padrão do Python.
"""

import argparse
import calendar
import glob
import importlib.util
import json
import math
import os
import random
import re
import socket
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
import zlib
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
# Pode ficar vazio (mas precisa existir): o IBGE não tem página oficial de licença
# que abra para robôs, então o link da licença fica em branco e o painel mostra só o texto.
CAMPOS_PODEM_FICAR_VAZIOS = {"url_licenca"}


# ---------------------------------------------------------------------------
# Rede
# ---------------------------------------------------------------------------
class ErroDeRede(Exception):
    """A rede ou o servidor falhou (não é culpa do dado)."""


# Servidores que já falharam por rede nesta execução: não insiste neles de novo
# (o serviço de metadados do IBGE não responde aos servidores do GitHub, e cada
# insistência custava ~2 minutos).
SERVIDORES_FORA = set()


TAMANHO_MAXIMO = 20 * 1024 * 1024   # 20 MB: a maior resposta real tem menos de 1 MB


class FalhaDefinitiva(ValueError):
    """Falha que não adianta repetir: redirecionamento recusado ou resposta grande demais."""


class _SoHttps(urllib.request.HTTPRedirectHandler):
    """Recusa redirecionamentos para endereços que não sejam https."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not newurl.lower().startswith("https://"):
            raise FalhaDefinitiva(f"Redirecionamento recusado (não é https): {newurl[:200]}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


ABRIDOR = urllib.request.build_opener(_SoHttps)


def ler_com_limite(resposta):
    """Lê a resposta até TAMANHO_MAXIMO e descompacta (gzip) também com limite."""
    bruto = resposta.read(TAMANHO_MAXIMO + 1)
    if len(bruto) > TAMANHO_MAXIMO:
        raise FalhaDefinitiva("Resposta grande demais (mais de 20 MB): recusada.")
    if bruto[:2] == b"\x1f\x8b":            # resposta compactada (o IBGE faz isso mesmo sem pedir)
        # max_length impede uma "bomba" de gzip: um arquivo pequeno que vira gigante
        bruto = zlib.decompressobj(wbits=31).decompress(bruto, TAMANHO_MAXIMO + 1)
        if len(bruto) > TAMANHO_MAXIMO:
            raise FalhaDefinitiva("Resposta compactada grande demais (mais de 20 MB): recusada.")
    return bruto


def texto_seguro(texto, limite=300):
    """Tira quebras de linha e "::" de um texto de fora antes de imprimir.
    (No GitHub Actions, uma linha começando com "::" é lida como comando.)"""
    limpo = " ".join(str(texto).split()).replace("::", ": :")
    return limpo[:limite] + ("…" if len(limpo) > limite else "")


# Só estes servidores podem ser abertos a partir de um endereço lido de data/*.json
SERVIDORES_DAS_FONTES = {"api.bcb.gov.br", "apisidra.ibge.gov.br", "www.ipeadata.gov.br"}


def baixar(url, como_json=True):
    """Baixa um endereço com timeout e até NOVAS_TENTATIVAS novas tentativas."""
    servidor = urllib.parse.urlsplit(url).netloc
    if servidor in SERVIDORES_FORA:
        raise ErroDeRede(f"{servidor} já não respondeu antes nesta execução")
    pedido = urllib.request.Request(url, headers={"User-Agent": "painel-verificador/1.0 (python-urllib)"})
    espera = ESPERA
    for tentativa in range(NOVAS_TENTATIVAS + 1):
        try:
            with ABRIDOR.open(pedido, timeout=TIMEOUT) as r:
                bruto = ler_com_limite(r)
            return json.loads(bruto.decode("utf-8-sig")) if como_json else bruto
        except urllib.error.HTTPError as e:
            if 400 <= e.code < 500:               # pedido errado: repetir não adianta
                raise
            ultimo = e
        except FalhaDefinitiva as e:              # repetir não adianta; o servidor não é marcado como fora
            raise ErroDeRede(f"{texto_seguro(e)} (falha definitiva, sem nova tentativa)")
        except Exception as e:                    # timeout, conexão caiu etc.
            ultimo = e
        if tentativa < NOVAS_TENTATIVAS:
            time.sleep(espera)
            espera *= 2
    SERVIDORES_FORA.add(servidor)
    raise ErroDeRede(f"{type(ultimo).__name__}: {texto_seguro(ultimo)} (depois de {NOVAS_TENTATIVAS + 1} tentativas)")


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
            r.ok.append(f"Tabela oficial: {texto_seguro(m['nome'])} (pesquisa: {texto_seguro(m['pesquisa'])}).")
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
                    r.erros.append(f"Categoria {cat} não existe na classificação {cls} ({texto_seguro(c[0]['nome'])}).")
                else:
                    nome_cat = [x for x in c[0]["categorias"] if str(x["id"]) == cat][0]["nome"]
                    r.ok.append(f"Filtro {cls}/{cat} = {texto_seguro(c[0]['nome'])}: {texto_seguro(nome_cat)}.")
        else:  # ipea
            v = baixar(METADADOS_IPEA.format(codigo=urllib.parse.quote(ind["codigo"])))["value"]
            if not v:
                r.erros.append(f"Série {ind['codigo']} não existe no Ipeadata.")
                return
            nome, unidade, per = v[0]["SERNOME"], v[0]["UNINOME"], v[0]["PERNOME"]
            if v[0].get("SERSTATUS") != "A":
                r.avisos.append(f"Ipeadata marca a série como inativa (SERSTATUS={texto_seguro(v[0].get('SERSTATUS'))}).")
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
        if campo not in s or s[campo] is None:
            r.erros.append(f"Campo serie.{campo} ausente.")
        elif s[campo] == "" and campo not in CAMPOS_PODEM_FICAR_VAZIOS:
            r.erros.append(f"Campo serie.{campo} vazio.")
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
               if f.endswith(".json") and f not in ("mandatos.json", "noticias.json")}
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
        # Mandato em andamento ou futuro precisa dizer de onde vem a data (texto + link https).
        # Só o formato é conferido: o site do TSE recusa acessos automáticos (HTTP 403).
        if m.get("status") in ("em_andamento", "futuro"):
            if not (isinstance(m.get("fonte"), str) and m["fonte"].strip()):
                r.erros.append(f"Mandato {nome}: falta o campo 'fonte' (texto dizendo de onde vem a data).")
            link = urllib.parse.urlsplit(str(m.get("url_fonte") or ""))
            if link.scheme != "https" or not link.netloc:
                r.erros.append(f"Mandato {nome}: 'url_fonte' ausente ou não é um link https: "
                               f"{texto_seguro(m.get('url_fonte'))!r}.")
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
# g) Links da página
# ---------------------------------------------------------------------------
# Servidores que a página pode citar. Um link para outro servidor vira ERRO e não é
# aberto: confira o link na mão e, se estiver certo, acrescente o servidor aqui.
SERVIDORES_DOS_LINKS = {
    "api.bcb.gov.br", "dadosabertos.bcb.gov.br", "www3.bcb.gov.br",   # Banco Central
    "apisidra.ibge.gov.br", "sidra.ibge.gov.br",                      # IBGE
    "www.ipeadata.gov.br",                                            # Ipea
    "opendatacommons.org",                                            # texto da licença ODbL
    "www12.senado.leg.br", "www.tse.jus.br",                          # fontes dos mandatos
    "github.com",                                                     # canal de contato (Issues)
}
# Sites que recusam qualquer acesso automático (HTTP 403 também no navegador sem
# janela, conferido em 17/11/2026). Para eles, um 403 não conta como link quebrado.
BLOQUEIAM_ROBOS = {"www.tse.jus.br"}
TIMEOUT_LINK = 20   # segundos por tentativa


def links_da_pagina(raiz):
    """Junta, sem repetir, os links que o leitor pode clicar e diz onde cada um aparece."""
    links = {}

    def anotar(url, onde):
        if isinstance(url, str) and url.strip():
            links.setdefault(url.strip(), []).append(onde)

    for caminho in sorted(glob.glob(os.path.join(raiz, "data", "*.json"))):
        nome = os.path.basename(caminho)
        try:
            j = json.load(open(caminho, encoding="utf-8"))
        except (OSError, ValueError):
            continue          # arquivo ilegível já é apontado em outra parte do relatório
        if not isinstance(j, dict):
            continue
        serie = j.get("serie")
        if isinstance(serie, dict):
            for campo in ("url_fonte", "url_pagina", "url_licenca"):
                anotar(serie.get(campo), f"{nome} ({campo})")
        for m in j.get("mandatos") or []:
            if isinstance(m, dict):
                anotar(m.get("url_fonte"), f"{nome} ({m.get('id')})")
    for rel in ("index.html", os.path.join("assets", "painel.js")):
        try:
            conteudo = open(os.path.join(raiz, rel), encoding="utf-8").read()
        except OSError:
            continue
        for url in re.findall(r"https?://[^\s\"'<>`)]+", conteudo):
            anotar(url, rel)
    return links


def abrir_link(url):
    """Abre o link como um leitor faria. Devolve (código HTTP, None) ou (None, motivo da falha)."""
    pedido = urllib.request.Request(url, headers={
        "User-Agent": "painel-verificador/1.0 (python-urllib)",
        "Accept": "text/html,application/json;q=0.9,*/*;q=0.8"})
    motivo = None
    for tentativa in range(2):                 # uma nova tentativa, para não acusar um soluço
        try:
            with ABRIDOR.open(pedido, timeout=TIMEOUT_LINK) as resposta:
                resposta.read(64 * 1024)       # basta o começo: só queremos saber se abre
                return resposta.status, None
        except urllib.error.HTTPError as e:
            if 400 <= e.code < 500:            # 4xx: repetir não muda nada
                return e.code, None
            motivo = f"HTTP {e.code}"
        except FalhaDefinitiva as e:
            return None, texto_seguro(e)
        except Exception as e:                 # tempo esgotado, conexão recusada etc.
            motivo = f"{type(e).__name__}: {texto_seguro(e, 120)}"
        if tentativa == 0:
            time.sleep(ESPERA)
    return None, motivo


def enderecos_sem_resposta(servidor, porta):
    """Um nome pode apontar para vários servidores, e o navegador escolhe um deles.
    Testa a conexão com cada endereço IPv4 e devolve (todos, os que não respondem)."""
    try:
        todos = sorted({a[4][0] for a in socket.getaddrinfo(servidor, porta, socket.AF_INET,
                                                             socket.SOCK_STREAM)})
    except OSError:
        return [], []                          # sem nome na rede: o teste do link já acusa
    fora = []
    for ip in todos:
        try:
            socket.create_connection((ip, porta), timeout=10).close()
        except OSError:
            fora.append(ip)
    return todos, fora


def checar_links(raiz, r):
    links = links_da_pagina(raiz)
    servidores = {}   # servidor -> porta a testar (a do https, se houver)
    bons = 0
    for url, onde in sorted(links.items()):
        lugares = ", ".join(onde[:3]) + (f" e mais {len(onde) - 3}" if len(onde) > 3 else "")
        partes = urllib.parse.urlsplit(url)
        if partes.scheme not in ("http", "https") or partes.netloc not in SERVIDORES_DOS_LINKS:
            r.erros.append(f"Link para servidor fora da lista conferida (não foi aberto): "
                           f"{texto_seguro(url)} — em {lugares}. Confira na mão e, se estiver "
                           "certo, acrescente o servidor em SERVIDORES_DOS_LINKS.")
            continue
        # Regra mais estreita para url_fonte: só os três servidores de dados oficiais
        if any(o.endswith("(url_fonte)") for o in onde) and (
                partes.scheme != "https" or partes.netloc not in SERVIDORES_DAS_FONTES):
            r.erros.append(f"url_fonte não aponta para uma das fontes oficiais (https): "
                           f"{texto_seguro(url)} — em {lugares}.")
            continue
        porta = 443 if partes.scheme == "https" else 80
        servidores[partes.netloc] = min(porta, servidores.get(partes.netloc, porta), key=lambda p: p != 443)
        codigo, motivo = abrir_link(url)
        if codigo is not None and 200 <= codigo < 300:
            bons += 1
        elif codigo == 403 and partes.netloc in BLOQUEIAM_ROBOS:
            r.ok.append(f"Não testável por robô (o site recusa acessos automáticos, HTTP 403); "
                        f"abra no navegador de vez em quando: {url}")
        else:
            r.erros.append(f"Link quebrado ({f'HTTP {codigo}' if codigo else motivo}): {url} — em {lugares}.")
    for servidor, porta in sorted(servidores.items()):
        todos, fora = enderecos_sem_resposta(servidor, porta)
        if fora:
            r.avisos.append(f"{servidor} aponta para {len(todos)} servidor(es) e {len(fora)} não "
                            f"responde(m) ({', '.join(fora)}). Quem cair nele vê demora ou falha "
                            "de conexão. O problema é do site da fonte, não do painel.")
    r.ok.append(f"{bons} de {len(links)} links responderam (em data/*.json, index.html e painel.js).")


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
                # Mensagens podem conter texto vindo das fontes (nomes, unidades):
                # passam por texto_seguro para não virar comando do GitHub Actions.
                linhas += [f"    - {texto_seguro(x, 2000)}" for x in itens]
    return "\n".join(linhas)


def para_markdown(x):
    return texto_seguro(x, 1000).replace("<", "&lt;")


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
            # Os textos podem citar nomes vindos das APIs: vão sem quebras de linha nem "<"
            md += [f"- ❌ {para_markdown(x)}" for x in r.erros] + [f"- ⚠️ {para_markdown(x)}" for x in r.avisos]
    return "\n".join(md) + "\n"


# ---------------------------------------------------------------------------
# g) Notícias
# ---------------------------------------------------------------------------
SELOS = {"Oficial", "Imprensa"}
SITUACOES_NOTICIAS = {"ok", "desatualizado", "indisponivel"}


def carregar_fontes_de_noticias(raiz):
    """Lê a lista FONTES de scripts/noticias.py (domínios permitidos de cada fonte)."""
    pasta = os.path.join(raiz, "scripts")
    sys.path.insert(0, pasta)        # noticias.py importa funções do coletar.py
    try:
        spec = importlib.util.spec_from_file_location("noticias_verificado", os.path.join(pasta, "noticias.py"))
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)   # só define funções e listas; não baixa nada
        return {f["id"]: f for f in modulo.FONTES}, modulo.N_POR_FONTE, modulo.LIMITE_TITULO
    finally:
        sys.path.remove(pasta)


def data_iso_com_fuso(x):
    """Devolve o datetime se x for data ISO com fuso; senão None."""
    if not isinstance(x, str):
        return None
    try:
        d = datetime.fromisoformat(x)
    except ValueError:
        return None
    return d if d.tzinfo else None


def link_https_de(url, dominios):
    if not isinstance(url, str) or not url.startswith("https://") or len(url) > 500:
        return False
    if any(c.isspace() or ord(c) < 32 for c in url):
        return False
    partes = urllib.parse.urlsplit(url)
    return partes.scheme == "https" and (dominios is None or partes.netloc in dominios)


def checar_noticias(raiz, r, agora):
    caminho = os.path.join(raiz, "data", "noticias.json")
    if not os.path.exists(caminho):
        r.avisos.append("data/noticias.json não existe (o robô ainda não rodou a coleta de notícias?).")
        return
    try:
        j = json.load(open(caminho, encoding="utf-8"))
        fontes_cfg, n_max, limite_titulo = carregar_fontes_de_noticias(raiz)
    except Exception as e:
        r.erros.append(f"data/noticias.json ou scripts/noticias.py ilegível: {texto_seguro(e)}")
        return
    if not isinstance(j, dict) or not isinstance(j.get("fontes"), list):
        r.erros.append("data/noticias.json: falta a lista 'fontes'.")
        return
    if not data_iso_com_fuso(j.get("gerado_em")):
        r.erros.append(f"gerado_em ausente ou fora do formato ISO com fuso: {j.get('gerado_em')!r}.")
    if j.get("n_por_fonte") != n_max:
        r.erros.append(f"n_por_fonte = {j.get('n_por_fonte')!r}, mas scripts/noticias.py usa {n_max}.")

    ids = [f.get("id") for f in j["fontes"] if isinstance(f, dict)]
    for falta in sorted(set(fontes_cfg) - set(ids)):
        r.erros.append(f"A fonte {falta!r} está em scripts/noticias.py mas não em data/noticias.json.")
    for sobra in sorted(set(ids) - set(fontes_cfg), key=str):
        r.erros.append(f"A fonte {sobra!r} está em data/noticias.json mas não em scripts/noticias.py.")

    for f in j["fontes"]:
        if not isinstance(f, dict):
            r.erros.append("data/noticias.json: uma fonte não é um objeto.")
            continue
        nome = f"Notícias {f.get('id')!r}"
        cfg = fontes_cfg.get(f.get("id"))
        dominios = set(cfg["dominios"]) if cfg else None
        for campo in ("veiculo", "termos"):
            if not isinstance(f.get(campo), str) or not f[campo].strip():
                r.erros.append(f"{nome}: campo {campo} ausente ou vazio.")
        if f.get("selo") not in SELOS:
            r.erros.append(f"{nome}: selo inválido {f.get('selo')!r} (use Oficial ou Imprensa).")
        for campo in ("url_feed", "url_termos"):
            if not link_https_de(f.get(campo), None):
                r.erros.append(f"{nome}: {campo} não é um link https: {f.get(campo)!r}.")
        situacao = f.get("situacao")
        if situacao not in SITUACOES_NOTICIAS:
            r.erros.append(f"{nome}: situacao inválida {situacao!r}.")
        extraido = data_iso_com_fuso(f.get("extraido_em"))
        if f.get("extraido_em") is not None and not extraido:
            r.erros.append(f"{nome}: extraido_em fora do formato ISO com fuso: {f.get('extraido_em')!r}.")
        if situacao in ("ok", "desatualizado") and not extraido:
            r.erros.append(f"{nome}: situacao {situacao!r} exige extraido_em.")

        itens = f.get("itens")
        if not isinstance(itens, list):
            r.erros.append(f"{nome}: falta a lista 'itens'.")
            continue
        if situacao == "indisponivel" and itens:
            r.erros.append(f"{nome}: fonte indisponível não pode ter itens.")
        if situacao in ("ok", "desatualizado") and not itens:
            r.erros.append(f"{nome}: situacao {situacao!r} sem nenhum item.")
        if len(itens) > n_max:
            r.erros.append(f"{nome}: {len(itens)} itens (o máximo é {n_max}).")
        datas, links = [], set()
        for i, it in enumerate(itens):
            if not isinstance(it, dict) or set(it) != {"titulo", "data", "link"}:
                r.erros.append(f"{nome}: item {i} deve ter só titulo, data e link.")
                continue
            titulo = it["titulo"]
            if not isinstance(titulo, str) or not titulo.strip() or len(titulo) > limite_titulo:
                r.erros.append(f"{nome}: item {i} com título vazio ou com mais de {limite_titulo} caracteres.")
            d = data_iso_com_fuso(it["data"])
            if not d:
                r.erros.append(f"{nome}: item {i} com data fora do formato ISO com fuso: {it['data']!r}.")
            elif d > agora + timedelta(minutes=10):
                r.erros.append(f"{nome}: item {i} com data no futuro ({it['data']}).")
            else:
                datas.append(d)
            if not link_https_de(it["link"], dominios):
                r.erros.append(f"{nome}: item {i} com link que não é https do domínio da fonte: {it['link']!r}.")
            if it["link"] in links:
                r.erros.append(f"{nome}: item {i} repete um link.")
            links.add(it["link"])
        if datas != sorted(datas, reverse=True):
            r.erros.append(f"{nome}: itens fora da ordem de data (do mais novo para o mais antigo).")

        if situacao == "ok" and extraido and agora - extraido > timedelta(days=2):
            r.avisos.append(f"{nome}: extraído em {f.get('extraido_em')} (mais de 2 dias): a rotina diária parou?")
        elif situacao == "desatualizado":
            r.avisos.append(f"{nome}: feed falhou; a página mostra os itens de {f.get('extraido_em')} "
                            "com 'não atualizado desde'.")
        elif situacao == "indisponivel":
            r.avisos.append(f"{nome}: sem coleta boa há mais de 7 dias; a página mostra 'Indisponível'.")
        else:
            r.ok.append(f"{nome}: {len(itens)} itens, extraídos em {f.get('extraido_em')}.")


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
    comeco = time.monotonic()
    for ind in escolhidos:
        print(f"Verificando {ind['id']}... ({time.monotonic() - comeco:.0f} s desde o início)", flush=True)
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

    pagina = Resultado("Página (data/, coletar.py e painel.js)")
    checar_pagina(args.raiz, indicadores, pagina)
    mandatos = Resultado("Mandatos (data/mandatos.json)")
    checar_mandatos(args.raiz, mandatos, hoje)
    noticias = Resultado("Notícias (data/noticias.json)")
    checar_noticias(args.raiz, noticias, datetime.now(FUSO))
    print("Verificando os links da página...", flush=True)
    links = Resultado("Links da página")
    checar_links(args.raiz, links)
    resultados += [pagina, mandatos, noticias, links]

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
