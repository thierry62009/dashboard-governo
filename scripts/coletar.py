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

import gzip
import json
import math
import os
import sys
import time
import urllib.request
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
        "licenca": "Uso livre com citação da fonte (IBGE)",
        "url_licenca": "https://biblioteca.ibge.gov.br/biblioteca-servicos.html",
    },
    "ipea": {
        "fonte": "Ipeadata (Instituto de Pesquisa Econômica Aplicada)",
        "fonte_sigla": "Ipeadata",
        "licenca": "Uso público com citação da fonte (Ipeadata)",
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
                      "indicado, em relação aos quatro trimestres anteriores.",
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
                      "terminados no mês indicado.",
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
]


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
            with urllib.request.urlopen(pedido, timeout=60) as resposta:
                bruto = resposta.read()
            # Algumas APIs do governo respondem compactadas (gzip) mesmo sem pedir.
            if bruto[:2] == b"\x1f\x8b":
                bruto = gzip.decompress(bruto)
            # "utf-8-sig" ignora a marca invisível que o Ipeadata põe no início.
            return json.loads(bruto.decode("utf-8-sig"))
        except Exception as erro:
            # Erro 4xx é pedido errado (código inexistente etc.): repetir não adianta.
            definitivo = getattr(erro, "code", 0) in range(400, 500)
            if definitivo or tentativa == TENTATIVAS:
                raise
            print(f"  Tentativa {tentativa} falhou ({erro}); esperando {espera}s...")
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


def validar(dados, agora):
    """Para com erro se os dados parecerem errados."""
    if not dados:
        raise ValueError("Nenhum dado a partir de " + MES_INICIAL + " (lista vazia).")
    datas = [d["data"] for d in dados]
    # Como "aaaa-mm" ordena igual a texto, basta comparar com a versão ordenada.
    if datas != sorted(datas):
        raise ValueError("As datas não estão em ordem.")
    if len(datas) != len(set(datas)):
        raise ValueError("Há períodos repetidos.")
    if datas[-1][:4] > agora.strftime("%Y"):
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
    validar(dados, agora)
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
            print(f"  FALHOU: {type(erro).__name__}: {erro} (o arquivo antigo, se existir, foi mantido)")
            # No GitHub Actions, esta linha vira um aviso amarelo na página da execução
            if os.environ.get("GITHUB_ACTIONS"):
                print(f"::warning title=Indicador não atualizado::{ind['id']}: {erro}")

    print(f"\nResumo: {len(escolhidos) - len(falhas)} de {len(escolhidos)} indicadores atualizados.")
    if falhas:
        print("Não atualizados: " + ", ".join(falhas))
    if len(falhas) == len(escolhidos):
        sys.exit("Nenhum indicador pôde ser atualizado.")


# Só roda o main() quando o arquivo é executado diretamente
# (e não quando é importado por outro script).
if __name__ == "__main__":
    main()
