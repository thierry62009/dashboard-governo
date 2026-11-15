"""
Baixa todos os indicadores do painel nas APIs oficiais (BCB/SGS, IBGE/SIDRA
e Ipeadata) e grava um arquivo por indicador em data/, sempre no mesmo formato.

Como rodar (a partir da pasta do projeto):
    python3 scripts/coletar.py              # todos os indicadores
    python3 scripts/coletar.py selic pib    # só os indicadores citados

Usa só a biblioteca padrão do Python: não precisa instalar nada.

Para acrescentar um indicador: copie um bloco da lista INDICADORES, troque os
códigos (só depois de testar na API e conferir nome, unidade e periodicidade
na página oficial da série) e acrescente o item em assets/painel.js.

Se um indicador falhar, o arquivo antigo dele continua como estava e os
outros seguem normalmente. O script só termina com erro se TODOS falharem.
"""

import json
import math
import os
import re
import sys
import time
import urllib.request
import zlib
from datetime import datetime
from zoneinfo import ZoneInfo

# ---------------------------------------------------------------------------
# Configurações gerais (tudo que pode mudar fica aqui em cima)
# ---------------------------------------------------------------------------
MES_INICIAL = "2023-01"          # primeiro mês guardado (início do mandato mais antigo do painel)
DATA_INICIAL_SGS = "01/01/2023"  # o mesmo, no formato que a API do BCB espera
PASTA_SAIDA = "data"
FUSO = ZoneInfo("America/Sao_Paulo")
TENTATIVAS = 3                   # quantas vezes tenta cada pedido antes de desistir
ESPERA_SEGUNDOS = 5              # espera entre tentativas (dobra a cada nova tentativa)

# Endereços das APIs. As chaves {} são preenchidas com .format()
URL_SGS = (
    "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"
    "?formato=json&dataInicial={inicio}&dataFinal={fim}"
)
URL_SIDRA = "https://apisidra.ibge.gov.br/values/t/{tabela}/n1/all/v/{variavel}/p/all{classificacoes}"
URL_IPEA = "https://www.ipeadata.gov.br/api/odata4/ValoresSerie(SERCODIGO='{codigo}')"

# Textos de fonte e licença, iguais para todas as séries de cada origem
FONTES = {
    "sgs": {
        "fonte": "Banco Central do Brasil - SGS (Sistema Gerenciador de Séries Temporais)",
        "fonte_sigla": "BCB/SGS",
        "licenca": "ODbL (Open Database License) - exige citação da fonte",
        "url_licenca": "https://opendatacommons.org/licenses/odbl/",
    },
    "sidra": {
        "fonte": "IBGE - SIDRA (Sistema IBGE de Recuperação Automática)",
        "fonte_sigla": "IBGE/SIDRA",
        # Não há licença formal do IBGE confirmada: o texto só cita a fonte, sem
        # afirmar licença. Sem página oficial que abra para robôs, o link fica vazio
        # (o painel mostra o texto sem link).
        "licenca": "Dados do IBGE (SIDRA); fonte citada conforme orientação do IBGE",
        "url_licenca": "",
    },
    "ipea": {
        "fonte": "Ipeadata (Instituto de Pesquisa Econômica Aplicada)",
        "fonte_sigla": "Ipeadata",
        # Texto conferido em 14/11/2026 na página "Direitos de Uso" do Ipeadata
        "licenca": "Informação pública, que pode ser distribuída e copiada com citação da fonte Ipeadata",
        "url_licenca": "http://www.ipeadata.gov.br/iframe_direitouso.aspx",
    },
}

PAGINA_SGS = "https://www3.bcb.gov.br/sgspub/"
PAGINA_BCB = "https://dadosabertos.bcb.gov.br/dataset/"   # catálogo oficial de dados abertos do BCB
PAGINA_SIDRA = "https://sidra.ibge.gov.br/tabela/"

# ---------------------------------------------------------------------------
# Lista de indicadores
#   tipo "sgs":   série do Banco Central. "diaria": True guarda só o último
#                 dia disponível de cada mês (o dia exato vai no campo "dia").
#   tipo "sidra": tabela do IBGE. "variavel_nome" e "unidade_api" são os textos
#                 que a API devolve; o script confere os dois a cada execução
#                 e recusa os dados se o IBGE mudar a tabela.
# Nome, unidade e periodicidade de cada item foram conferidos na página
# oficial indicada em "pagina" (ver a lista "A conferir" no STATUS.md).
# ---------------------------------------------------------------------------
INDICADORES = [
    # ----- Economia -----
    {
        "id": "ipca", "tipo": "sgs", "codigo": 433,
        "nome": "Índice nacional de preços ao consumidor-amplo (IPCA)",
        "unidade": "Var. % mensal", "origem": "IBGE", "periodicidade": "mensal",
        "pagina": PAGINA_SGS,
    },
    {
        "id": "selic", "tipo": "sgs", "codigo": 432, "diaria": True,
        "nome": "Taxa de juros - Meta Selic definida pelo Copom",
        "unidade": "% ao ano", "origem": "Comitê de Política Monetária (Copom)",
        "periodicidade": "mensal",
        "pagina": PAGINA_BCB + "432-taxa-de-juros---meta-selic-definida-pelo-copom",
        "observacao": "Série diária: o gráfico mostra o valor do último dia disponível de cada mês.",
    },
    {
        "id": "dolar", "tipo": "sgs", "codigo": 1, "diaria": True,
        "nome": "Taxa de câmbio - Livre - Dólar americano (venda) - diário",
        "unidade": "R$ por US$", "origem": "Banco Central (PTAX)",
        "periodicidade": "mensal",
        "pagina": PAGINA_BCB + "1-taxa-de-cambio---livre---dolar-americano-venda---diario",
        "observacao": "Série diária: o gráfico mostra o valor do último dia disponível de cada mês.",
    },
    {
        "id": "pib", "tipo": "sidra", "tabela": 5932, "variavel": 6562,
        "classificacoes": "/c11255/90707",   # 90707 = PIB a preços de mercado
        "variavel_nome": "Taxa acumulada em quatro trimestres (em relação ao mesmo período do ano anterior)",
        "unidade_api": "%",
        "nome": "PIB a preços de mercado - taxa acumulada em quatro trimestres "
                "(em relação ao mesmo período do ano anterior)",
        "unidade": "%", "origem": "IBGE, Contas Nacionais Trimestrais",
        "periodicidade": "trimestral",
        "observacao": "Variação do volume do PIB nos quatro trimestres terminados no trimestre "
                      "indicado, em relação aos quatro trimestres anteriores. Os pontos de "
                      "março, junho e setembro de 2023 incluem trimestres de 2022, porque "
                      "cada ponto cobre quatro trimestres.",
    },
    # ----- Trabalho e renda -----
    {
        "id": "desocupacao", "tipo": "sidra", "tabela": 6381, "variavel": 4099,
        "variavel_nome": "Taxa de desocupação, na semana de referência, das pessoas de 14 anos ou mais de idade",
        "unidade_api": "%",
        "nome": "Taxa de desocupação, na semana de referência, das pessoas de 14 anos ou mais de idade",
        "unidade": "%", "origem": "IBGE, PNAD Contínua",
        "periodicidade": "trimestre_movel",
        "observacao": "Cada ponto se refere a um trimestre móvel: três meses seguidos, "
                      "terminados no mês indicado. Os pontos de janeiro e fevereiro de 2023 "
                      "incluem meses de 2022, porque cada ponto cobre três meses.",
    },
    {
        "id": "renda", "tipo": "sidra", "tabela": 6390, "variavel": 5933,
        "variavel_nome": "Rendimento médio mensal real das pessoas de 14 anos ou mais de idade ocupadas "
                         "na semana de referência com rendimento de trabalho, habitualmente recebido "
                         "em todos os trabalhos",
        "unidade_api": "Reais",
        "nome": "Rendimento médio mensal real das pessoas de 14 anos ou mais de idade ocupadas "
                "na semana de referência com rendimento de trabalho, habitualmente recebido "
                "em todos os trabalhos",
        "unidade": "Reais", "origem": "IBGE, PNAD Contínua",
        "periodicidade": "trimestre_movel",
        "observacao": "Trimestre móvel terminado no mês indicado. Rendimento real: o IBGE corrige "
                      "os valores pela inflação, e a série inteira pode mudar a cada divulgação.",
    },
    {
        "id": "emprego_formal", "tipo": "ipea", "codigo": "CAGED12_SALDONAJU12",
        "nome": "Empregados - saldo - com ajuste - novo Caged",
        "unidade": "Pessoas", "origem": "Novo Caged (Min. Economia/SEPRT, conforme o Ipeadata)",
        "periodicidade": "mensal",
        "pagina": "https://www.ipeadata.gov.br/api/odata4/Metadados('CAGED12_SALDONAJU12')",
        "observacao": "Saldo = admissões menos demissões de empregados com carteira no mês. "
                      "\"Com ajuste\" inclui as declarações entregues fora do prazo, "
                      "por isso os meses recentes podem mudar.",
    },
    # ----- Contas públicas -----
    {
        "id": "divida_bruta", "tipo": "sgs", "codigo": 13762,
        "nome": "Dívida bruta do governo geral (% PIB) - Metodologia utilizada a partir de 2008",
        "unidade": "% do PIB", "origem": "Banco Central do Brasil, Departamento Econômico",
        "periodicidade": "mensal",
        "pagina": PAGINA_BCB + "13762-divida-bruta-do-governo-geral--pib---metodologia-utilizada-a-partir-de-2008",
    },
    {
        "id": "divida_liquida", "tipo": "sgs", "codigo": 4513,
        "nome": "Dívida Líquida do Setor Público (% PIB) - Total - Setor público consolidado",
        "unidade": "% do PIB", "origem": "Banco Central do Brasil, Departamento Econômico",
        "periodicidade": "mensal",
        "pagina": PAGINA_BCB + "4513-divida-liquida-do-setor-publico--pib---total---setor-publico-consolidado",
    },
    {
        "id": "resultado_primario", "tipo": "sgs", "codigo": 5793,
        "nome": "NFSP sem desvalorização cambial (% PIB) - Fluxo acumulado em 12 meses - "
                "Resultado primário - Total - Setor público consolidado",
        "unidade": "% do PIB", "origem": "Banco Central do Brasil, Departamento Econômico",
        "periodicidade": "mensal",
        "pagina": PAGINA_BCB + "5793-nfsp-sem-desvalorizacao-cambial--pib---fluxo-acumulado-em-12-meses---resultado-primario---tota",
        "observacao": "NFSP = necessidade de financiamento do setor público. Pela convenção do "
                      "Banco Central, valor positivo indica déficit e valor negativo indica superávit.",
    },
    # ----- Saúde (indicadores dos Objetivos de Desenvolvimento Sustentável, anuais) -----
    {
        "id": "mortalidade_menores_5", "tipo": "sidra", "tabela": 6695, "variavel": 9731,
        "variavel_nome": "Taxa de mortalidade em menores de 5 anos",
        "unidade_api": "Óbitos por mil nascidos vivos",
        "nome": "Indicador ODS 3.2.1 - Taxa de mortalidade em menores de 5 anos",
        "unidade": "Óbitos por mil nascidos vivos",
        "origem": "IBGE, Objetivos de Desenvolvimento Sustentável", "periodicidade": "anual",
    },
    {
        "id": "mortalidade_materna", "tipo": "sidra", "tabela": 6694, "variavel": 9730,
        "variavel_nome": "Razão de mortalidade materna",
        "unidade_api": "Óbitos por 100 mil nascidos vivos",
        "nome": "Indicador ODS 3.1.1 - Razão de mortalidade materna",
        "unidade": "Óbitos por 100 mil nascidos vivos",
        "origem": "IBGE, Objetivos de Desenvolvimento Sustentável", "periodicidade": "anual",
    },
    # ----- Educação (anuais) -----
    {
        "id": "analfabetismo", "tipo": "sidra", "tabela": 7113, "variavel": 10267,
        "classificacoes": "/c2/6794/c58/2795",   # sexo: total; idade: 15 anos ou mais
        "variavel_nome": "Taxa de analfabetismo das pessoas de 15 anos ou mais de idade",
        "unidade_api": "%",
        "nome": "Taxa de analfabetismo das pessoas de 15 anos ou mais de idade",
        "unidade": "%", "origem": "IBGE, PNAD Contínua anual", "periodicidade": "anual",
    },
    {
        "id": "escolarizacao_15_17", "tipo": "sidra", "tabela": 7138, "variavel": 10276,
        "classificacoes": "/c2/6794/c58/2792",   # sexo: total; idade: 15 a 17 anos
        "variavel_nome": "Taxa de escolarização", "unidade_api": "%",
        "nome": "Taxa de escolarização - 15 a 17 anos",
        "unidade": "%", "origem": "IBGE, PNAD Contínua anual", "periodicidade": "anual",
        "observacao": "Parcela das pessoas de 15 a 17 anos que frequentam escola.",
    },
    {
        "id": "conclusao_ensino_medio", "tipo": "sidra", "tabela": 4731, "variavel": 4721,
        "classificacoes": "/c582/59997",         # ensino médio - pessoas de 20 a 22 anos
        "variavel_nome": "Taxa de conclusão de nível de ensino", "unidade_api": "%",
        "nome": "Indicador ODS 4.1.2 - Taxa de conclusão de nível de ensino - "
                "Ensino médio - Pessoas de 20 a 22 anos",
        "unidade": "%", "origem": "IBGE, Objetivos de Desenvolvimento Sustentável",
        "periodicidade": "anual",
    },
    # ----- Segurança (anual) -----
    {
        "id": "homicidios", "tipo": "sidra", "tabela": 6606, "variavel": 13532,
        "variavel_nome": "Taxa de vítimas de homicídios intencionais",
        "unidade_api": "Óbitos por 100 mil habitantes",
        "nome": "Indicador ODS 16.1.1 - Taxa de vítimas de homicídios intencionais",
        "unidade": "Óbitos por 100 mil habitantes",
        "origem": "IBGE, Objetivos de Desenvolvimento Sustentável", "periodicidade": "anual",
    },
]


# ---------------------------------------------------------------------------
# Proteções de rede (as respostas das APIs são dados de fora: não confiamos nelas)
# ---------------------------------------------------------------------------
TAMANHO_MAXIMO = 20 * 1024 * 1024   # 20 MB: a maior resposta real tem menos de 1 MB


class _SoHttps(urllib.request.HTTPRedirectHandler):
    """Recusa redirecionamentos para endereços que não sejam https."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not newurl.lower().startswith("https://"):
            raise ValueError(f"Redirecionamento recusado (não é https): {newurl[:200]}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


ABRIDOR = urllib.request.build_opener(_SoHttps)


def ler_com_limite(resposta):
    """Lê a resposta até TAMANHO_MAXIMO e descompacta (gzip) também com limite."""
    bruto = resposta.read(TAMANHO_MAXIMO + 1)
    if len(bruto) > TAMANHO_MAXIMO:
        raise ValueError("Resposta grande demais (mais de 20 MB): recusada.")
    if bruto[:2] == b"\x1f\x8b":            # resposta compactada (o IBGE faz isso mesmo sem pedir)
        # max_length impede uma "bomba" de gzip: um arquivo pequeno que vira gigante
        bruto = zlib.decompressobj(wbits=31).decompress(bruto, TAMANHO_MAXIMO + 1)
        if len(bruto) > TAMANHO_MAXIMO:
            raise ValueError("Resposta compactada grande demais (mais de 20 MB): recusada.")
    return bruto


def texto_seguro(texto, limite=300):
    """Tira quebras de linha e "::" de um texto de fora antes de imprimir.
    (No GitHub Actions, uma linha começando com "::" é lida como comando.)"""
    limpo = " ".join(str(texto).split()).replace("::", ": :")
    return limpo[:limite] + ("…" if len(limpo) > limite else "")


# ---------------------------------------------------------------------------
# Funções de apoio
# ---------------------------------------------------------------------------
def baixar_json(url):
    """Pede um endereço e devolve o JSON já convertido. Tenta algumas vezes."""
    print(f"  Baixando: {url}")
    # Um "User-Agent" identifica quem está pedindo; alguns servidores
    # recusam pedidos sem ele.
    pedido = urllib.request.Request(url, headers={"User-Agent": "painel-indicadores/1.0 (python-urllib)"})
    espera = ESPERA_SEGUNDOS
    for tentativa in range(1, TENTATIVAS + 1):
        try:
            # timeout=60: se a API não responder em 60 segundos, desiste com erro.
            with ABRIDOR.open(pedido, timeout=60) as resposta:
                bruto = ler_com_limite(resposta)
            # "utf-8-sig" ignora a marca invisível que o Ipeadata põe no início.
            return json.loads(bruto.decode("utf-8-sig"))
        except Exception as erro:
            # Erro 4xx é pedido errado (código inexistente etc.): repetir não adianta.
            definitivo = getattr(erro, "code", 0) in range(400, 500)
            if definitivo or tentativa == TENTATIVAS:
                raise
            print(f"  Tentativa {tentativa} falhou ({texto_seguro(erro)}); esperando {espera}s...")
            time.sleep(espera)
            espera *= 2


def coletar_sgs(ind, agora):
    """Série do BCB. Devolve (dados, endereço consultado, identificação)."""
    url = URL_SGS.format(codigo=ind["codigo"], inicio=DATA_INICIAL_SGS, fim=agora.strftime("%d/%m/%Y"))
    hoje = agora.strftime("%Y-%m-%d")
    por_mes = {}
    for item in baixar_json(url):
        dia, mes, ano = item["data"].split("/")       # "01/09/2026" -> "01", "09", "2026"
        data_iso = f"{ano}-{mes}-{dia}"
        # A meta Selic já vem com datas futuras (até a próxima reunião do Copom):
        # o que passa de hoje fica de fora.
        if data_iso > hoje:
            continue
        ponto = {"data": f"{ano}-{mes}", "valor": float(item["valor"])}   # "0.82" (texto) -> 0.82
        if ind.get("diaria"):
            ponto["dia"] = data_iso
            # Série diária: fica só o último dia disponível de cada mês
            if f"{ano}-{mes}" in por_mes and por_mes[f"{ano}-{mes}"]["dia"] > data_iso:
                continue
        elif f"{ano}-{mes}" in por_mes:
            raise ValueError(f"Mês repetido na série mensal: {ano}-{mes}")
        por_mes[f"{ano}-{mes}"] = ponto
    return list(por_mes.values()), url, f"série {ind['codigo']}"


def periodo_sidra(codigo, periodicidade):
    """Converte o código de período do SIDRA em "aaaa-mm"."""
    if periodicidade == "anual":            # "2025" -> "2025-12" (a página mostra só o ano)
        return f"{codigo}-12"
    ano, numero = codigo[:4], int(codigo[4:])
    if periodicidade == "trimestral":       # "202602" = 2º trimestre -> último mês: "2026-06"
        return f"{ano}-{numero * 3:02d}"
    return f"{ano}-{numero:02d}"            # trimestre móvel: "202609" termina em setembro


def coletar_sidra(ind, agora):
    """Tabela do IBGE. Devolve (dados, endereço consultado, identificação)."""
    url = URL_SIDRA.format(tabela=ind["tabela"], variavel=ind["variavel"],
                           classificacoes=ind.get("classificacoes", ""))
    linhas = baixar_json(url)
    dados = []
    # A primeira linha é o cabeçalho (nomes das colunas); os dados vêm depois.
    for linha in linhas[1:]:
        # Confere se a tabela ainda é a mesma que foi conferida na fonte
        if linha["D2N"] != ind["variavel_nome"] or linha["MN"] != ind["unidade_api"]:
            raise ValueError(f"O IBGE mudou a variável ou a unidade: {linha['D2N']!r} [{linha['MN']!r}]")
        if linha["D1C"] != "1":
            raise ValueError(f"Veio um território que não é o Brasil: {linha['D1N']!r}")
        data = periodo_sidra(linha["D3C"], ind["periodicidade"])
        # O SIDRA usa "...", "-" ou "X" quando não há valor: esses períodos ficam de fora.
        try:
            valor = float(linha["V"])
        except ValueError:
            continue
        dados.append({"data": data, "valor": valor})
    identificacao = f"tabela {ind['tabela']}, variável {ind['variavel']}"
    return dados, url, identificacao


def coletar_ipea(ind, agora):
    """Série do Ipeadata. Devolve (dados, endereço consultado, identificação)."""
    url = URL_IPEA.format(codigo=ind["codigo"])
    dados = []
    # Cuidado: código inexistente NÃO dá erro no Ipeadata; vem uma lista vazia
    # (a função validar recusa lista vazia).
    for item in baixar_json(url)["value"]:
        if item["VALVALOR"] is None:
            continue
        dados.append({"data": item["VALDATA"][:7], "valor": float(item["VALVALOR"])})   # "2026-09-01T..." -> "2026-09"
    return dados, url, f"série {ind['codigo']}"


COLETORES = {"sgs": coletar_sgs, "sidra": coletar_sidra, "ipea": coletar_ipea}


FORMATO_MES = re.compile(r"\d{4}-(0[1-9]|1[0-2])")
FORMATO_DIA = re.compile(r"\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])")


def validar(dados, agora, anual=False):
    """Para com erro se os dados parecerem errados."""
    if not dados:
        raise ValueError("Nenhum dado a partir de " + MES_INICIAL + " (lista vazia).")
    datas = [d["data"] for d in dados]
    # Como "aaaa-mm" ordena igual a texto, basta comparar com a versão ordenada.
    if datas != sorted(datas):
        raise ValueError("As datas não estão em ordem.")
    if len(datas) != len(set(datas)):
        raise ValueError("Há períodos repetidos.")
    # Formato exato: "aaaa-mm" (e "aaaa-mm-dd" no campo "dia"). Qualquer outro
    # texto vindo da API é recusado antes de chegar ao arquivo.
    for d in dados:
        if not FORMATO_MES.fullmatch(d["data"]):
            raise ValueError(f"Data fora do formato aaaa-mm: {d['data']!r}")
        if "dia" in d and not (FORMATO_DIA.fullmatch(d["dia"]) and d["dia"].startswith(d["data"])):
            raise ValueError(f"Dia fora do formato aaaa-mm-dd: {d['dia']!r}")
    # Séries anuais são guardadas como "aaaa-12": para elas vale só o ano.
    if datas[-1] > agora.strftime("%Y-%m") and not (anual and datas[-1][:4] <= agora.strftime("%Y")):
        raise ValueError(f"Há dado com data no futuro: {datas[-1]}")
    if any(not math.isfinite(d["valor"]) for d in dados):
        raise ValueError("Há valor que não é um número válido.")


def salvar(ind, dados, url_fonte, identificacao, extraido_em):
    """Grava o JSON final. Primeiro num arquivo temporário, depois troca."""
    serie = {
        "codigo": ind.get("codigo", ind.get("tabela")),
        "identificacao": identificacao,
        "nome": ind["nome"],
        "unidade": ind["unidade"],
        "periodicidade": ind["periodicidade"],
        "origem": ind["origem"],   # quem produz o dado
        **FONTES[ind["tipo"]],     # fonte, sigla e licença de quem disponibiliza
        "url_fonte": url_fonte,
        "url_pagina": ind.get("pagina") or PAGINA_SIDRA + str(ind.get("tabela")),
    }
    if ind.get("observacao"):
        serie["observacao"] = ind["observacao"]
    conteudo = {"serie": serie, "extraido_em": extraido_em, "dados": dados}

    os.makedirs(PASTA_SAIDA, exist_ok=True)
    arquivo = os.path.join(PASTA_SAIDA, ind["id"] + ".json")
    # Escrever num ".tmp" e só no fim renomear garante que, se algo der
    # errado no meio, o arquivo antigo continua inteiro.
    temporario = arquivo + ".tmp"
    with open(temporario, "w", encoding="utf-8") as f:
        json.dump(conteudo, f, ensure_ascii=False, indent=2)
    os.replace(temporario, arquivo)
    return arquivo


def coletar_um(ind):
    """Baixa, confere e grava um indicador."""
    agora = datetime.now(FUSO)
    dados, url, identificacao = COLETORES[ind["tipo"]](ind, agora)
    # Fica só com o que é de MES_INICIAL em diante, em ordem de data
    dados = sorted((d for d in dados if d["data"] >= MES_INICIAL), key=lambda d: d["data"])
    validar(dados, agora, anual=ind["periodicidade"] == "anual")
    arquivo = salvar(ind, dados, url, identificacao, agora.isoformat(timespec="seconds"))
    print(f"  OK: {len(dados)} períodos em {arquivo} | primeiro {dados[0]} | último {dados[-1]}")


def main():
    pedidos = sys.argv[1:]
    conhecidos = [ind["id"] for ind in INDICADORES]
    for nome in pedidos:
        if nome not in conhecidos:
            sys.exit(f"Indicador desconhecido: {nome}. Opções: {', '.join(conhecidos)}")
    escolhidos = [ind for ind in INDICADORES if not pedidos or ind["id"] in pedidos]

    falhas = []
    for ind in escolhidos:
        print(f"[{ind['id']}]")
        try:
            coletar_um(ind)
        except Exception as erro:
            falhas.append(ind["id"])
            motivo = texto_seguro(erro)   # o texto do erro pode conter dados da API
            print(f"  FALHOU: {type(erro).__name__}: {motivo} (o arquivo antigo, se existir, foi mantido)")
            # No GitHub Actions, esta linha vira um aviso amarelo na página da execução
            if os.environ.get("GITHUB_ACTIONS"):
                print(f"::warning title=Indicador não atualizado::{ind['id']}: {motivo}")

    print(f"\nResumo: {len(escolhidos) - len(falhas)} de {len(escolhidos)} indicadores atualizados.")
    if falhas:
        print("Não atualizados: " + ", ".join(falhas))
    if len(falhas) == len(escolhidos):
        sys.exit("Nenhum indicador pôde ser atualizado.")


# Só roda o main() quando o arquivo é executado diretamente
# (e não quando é importado por outro script).
if __name__ == "__main__":
    main()
