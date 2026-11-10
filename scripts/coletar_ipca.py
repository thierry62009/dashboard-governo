"""
Baixa o IPCA mensal (variação %) do Banco Central (SGS) desde 01/01/2023
e salva em data/ipca.json, junto com a fonte e a data de extração.

Como rodar (a partir da pasta do projeto):
    python3 scripts/coletar_ipca.py

Usa só a biblioteca padrão do Python: não precisa instalar nada.
"""

import json
import os
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

# ---------------------------------------------------------------------------
# Configurações (tudo que pode mudar fica aqui em cima)
# ---------------------------------------------------------------------------
CODIGO_SERIE = 433              # IPCA mensal no SGS (conferido no portal em 10/11/2026)
DATA_INICIAL = "01/01/2023"     # formato que a API do BCB espera: dd/mm/aaaa
ARQUIVO_SAIDA = os.path.join("data", "ipca.json")
FUSO = ZoneInfo("America/Sao_Paulo")

# Endereço da API. As chaves {} são preenchidas mais abaixo com .format()
URL_API = (
    "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"
    "?formato=json&dataInicial={inicio}&dataFinal={fim}"
)


def baixar_serie(codigo, data_inicial, data_final):
    """Pede a série à API do BCB e devolve a lista crua (como veio da API)."""
    url = URL_API.format(codigo=codigo, inicio=data_inicial, fim=data_final)
    print(f"Baixando: {url}")

    # Um "User-Agent" identifica quem está pedindo; alguns servidores
    # recusam pedidos sem ele.
    pedido = urllib.request.Request(url, headers={"User-Agent": "dashboard-governo/0.1"})

    # timeout=30: se a API não responder em 30 segundos, desiste com erro.
    with urllib.request.urlopen(pedido, timeout=30) as resposta:
        texto = resposta.read().decode("utf-8")

    return json.loads(texto)  # transforma o texto JSON em lista do Python


def converter(lista_crua):
    """
    Converte cada item {"data": "01/09/2026", "valor": "0.82"}
    em {"data": "2026-09", "valor": 0.82}.
    """
    dados = []
    for item in lista_crua:
        dia, mes, ano = item["data"].split("/")   # "01/09/2026" -> "01", "09", "2026"
        valor = float(item["valor"])              # "0.82" (texto) -> 0.82 (número)
        dados.append({"data": f"{ano}-{mes}", "valor": valor})
    return dados


def validar(dados):
    """Para o script com erro se os dados parecerem errados."""
    if not dados:
        raise ValueError("A API devolveu uma lista vazia.")

    datas = [d["data"] for d in dados]
    # Como "aaaa-mm" ordena igual a texto, basta comparar com a versão ordenada.
    if datas != sorted(datas):
        raise ValueError("As datas não estão em ordem.")
    if len(datas) != len(set(datas)):
        raise ValueError("Há meses repetidos.")


def salvar(dados, url_fonte, extraido_em):
    """Grava o JSON final. Primeiro num arquivo temporário, depois troca."""
    conteudo = {
        "serie": {
            "codigo": CODIGO_SERIE,
            # Nome, unidade e origem conferidos no portal SGS em 10/11/2026
            "nome": "Índice nacional de preços ao consumidor-amplo (IPCA)",
            "unidade": "Var. % mensal",
            "origem": "IBGE",  # quem produz o dado; o BCB só o disponibiliza no SGS
            "fonte": "Banco Central do Brasil - SGS (Sistema Gerenciador de Séries Temporais)",
            "url_fonte": url_fonte,
            "licenca": "ODbL (Open Database License) - exige citação da fonte",
        },
        "extraido_em": extraido_em,
        "dados": dados,
    }

    os.makedirs(os.path.dirname(ARQUIVO_SAIDA), exist_ok=True)

    # Escrever num ".tmp" e só no fim renomear garante que, se algo der
    # errado no meio, o ipca.json antigo continua inteiro.
    temporario = ARQUIVO_SAIDA + ".tmp"
    with open(temporario, "w", encoding="utf-8") as f:
        json.dump(conteudo, f, ensure_ascii=False, indent=2)
    os.replace(temporario, ARQUIVO_SAIDA)


def main():
    agora = datetime.now(FUSO)
    data_final = agora.strftime("%d/%m/%Y")

    lista_crua = baixar_serie(CODIGO_SERIE, DATA_INICIAL, data_final)
    dados = converter(lista_crua)
    validar(dados)

    url_fonte = URL_API.format(codigo=CODIGO_SERIE, inicio=DATA_INICIAL, fim=data_final)
    salvar(dados, url_fonte, agora.isoformat(timespec="seconds"))

    print(f"OK: {len(dados)} meses salvos em {ARQUIVO_SAIDA}")
    print(f"Primeiro: {dados[0]}  |  Último: {dados[-1]}")


# Só roda o main() quando o arquivo é executado diretamente
# (e não quando é importado por outro script).
if __name__ == "__main__":
    main()
