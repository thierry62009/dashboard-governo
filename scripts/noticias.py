"""Coleta de notícias por RSS para o painel (Fase 4).

Grava data/noticias.json com, para cada fonte, os N itens mais recentes:
só título, data e link (nunca o texto da matéria, resumo ou imagem).

Como rodar:
    python3 scripts/noticias.py

Cuidados (o feed é dado de fora, escrito por terceiros):
- só biblioteca padrão; no máximo 2 MB por feed (também depois de descompactar);
- feed com "<!DOCTYPE" ou "<!ENTITY" é recusado inteiro (sem DTD não há
  entidades externas nem a "bomba" de entidades que se multiplicam);
- título exatamente como vem (só sem espaços nas pontas); se tiver mais de
  300 caracteres, o item é descartado, nunca cortado;
- link só https e só dos domínios da própria fonte;
- data obrigatória, com fuso, e nunca no futuro.

Se um feed falhar, ficam os itens da última coleta boa ("desatualizado").
Depois de 7 dias sem coleta boa, a fonte vira "indisponivel" (sem itens).
O script só termina com erro se todas as fontes falharem; no GitHub Actions
o passo tem falha isolada e nunca derruba os indicadores.
"""

import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zlib
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

# Reaproveita do coletar.py: fuso de Brasília, redirecionamento só para https
# e a limpeza de texto antes de imprimir.
from coletar import ABRIDOR, FUSO, FalhaDefinitiva, texto_seguro

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------
ARQUIVO = os.path.join("data", "noticias.json")
N_POR_FONTE = 5                       # o mesmo N para todas as fontes
DIAS_ATE_INDISPONIVEL = 7             # sem coleta boa por mais que isso => "indisponivel"
TAMANHO_MAXIMO = 2 * 1024 * 1024      # 2 MB por feed
LIMITE_TITULO = 300                   # caracteres; acima disso o item é descartado
LIMITE_LINK = 500
TOLERANCIA_RELOGIO = timedelta(minutes=10)   # data "do futuro" só acima disso
TENTATIVAS = 3
ESPERA_SEGUNDOS = 5

# Uma fonte por bloco. Para acrescentar uma fonte, copie um bloco.
# O Planalto ficou de fora em 18/11/2026: o item mais recente do RSS tinha
# mais de 30 dias (ver STATUS.md). A leitura de RSS 1.0 (formato do Planalto)
# já está pronta para quando ele voltar.
FONTES = [
    {
        "id": "agencia_brasil",
        "veiculo": "Agência Brasil (EBC)",
        "selo": "Oficial",
        "url_feed": "https://agenciabrasil.ebc.com.br/rss/politica/feed.xml",
        "dominios": ["agenciabrasil.ebc.com.br"],
        "termos": "Reprodução autorizada mediante indicação da fonte (EBC)",
        "url_termos": "https://agenciabrasil.ebc.com.br/sobre",
    },
]

# Espaços de nomes usados pelo RSS 1.0 (RDF) e pelo Dublin Core (dc:date)
NS_RSS1 = "{http://purl.org/rss/1.0/}"
NS_DC = "{http://purl.org/dc/elements/1.1/}"


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------
def ler_com_limite(resposta):
    """Lê no máximo TAMANHO_MAXIMO; descompacta gzip também com limite."""
    bruto = resposta.read(TAMANHO_MAXIMO + 1)
    if len(bruto) > TAMANHO_MAXIMO:
        raise FalhaDefinitiva("Feed grande demais (mais de 2 MB): recusado.")
    if bruto[:2] == b"\x1f\x8b":
        bruto = zlib.decompressobj(wbits=31).decompress(bruto, TAMANHO_MAXIMO + 1)
        if len(bruto) > TAMANHO_MAXIMO:
            raise FalhaDefinitiva("Feed compactado grande demais (mais de 2 MB): recusado.")
    return bruto


def baixar_feed(url):
    """Baixa o feed e devolve os bytes. Tenta algumas vezes."""
    print(f"  Baixando: {url}")
    # A Agência Brasil responde HTTP 500 a qualquer User-Agent com "python":
    # por isso este nome não cita a linguagem.
    pedido = urllib.request.Request(url, headers={"User-Agent": "painel-indicadores/1.0"})
    espera = ESPERA_SEGUNDOS
    for tentativa in range(1, TENTATIVAS + 1):
        try:
            with ABRIDOR.open(pedido, timeout=30) as resposta:
                return ler_com_limite(resposta)
        except Exception as erro:
            # 4xx, redirecionamento recusado e feed grande demais: repetir não adianta
            definitivo = getattr(erro, "code", 0) in range(400, 500) or isinstance(erro, FalhaDefinitiva)
            if definitivo or tentativa == TENTATIVAS:
                raise
            print(f"  Tentativa {tentativa} falhou ({texto_seguro(erro)}); esperando {espera}s...")
            time.sleep(espera)
            espera *= 2


# ---------------------------------------------------------------------------
# Validação de cada campo
# ---------------------------------------------------------------------------
def titulo_valido(texto):
    """Devolve o título exato (sem espaços nas pontas) ou None se não servir."""
    if texto is None:
        return None
    titulo = texto.strip()
    if not titulo or len(titulo) > LIMITE_TITULO:
        return None          # descartado, nunca cortado
    return titulo


def link_valido(url, dominios):
    """Só https, só dos domínios da fonte, sem usuário/senha nem porta."""
    if not url:
        return None
    url = url.strip()
    if len(url) > LIMITE_LINK or not url.startswith("https://"):
        return None
    partes = urllib.parse.urlsplit(url)
    if partes.scheme != "https" or partes.netloc not in dominios:
        return None          # netloc com "@" (usuário) ou ":" (porta) nunca bate com a lista
    if any(c.isspace() or ord(c) < 32 for c in url):
        return None
    return url


def data_valida(texto, agora):
    """Lê a data (RFC 822 ou ISO 8601) e devolve em ISO com fuso de Brasília.
    Sem data, sem fuso ou no futuro => None."""
    if not texto:
        return None
    texto = texto.strip()
    try:
        if re.match(r"\d{4}-\d{2}-\d{2}", texto):                # ISO 8601 (dc:date)
            quando = datetime.fromisoformat(texto.replace("Z", "+00:00"))
        else:                                                   # RFC 822 (pubDate)
            quando = parsedate_to_datetime(texto)
    except (ValueError, TypeError, IndexError):
        return None
    if quando.tzinfo is None:
        # O RFC 822 usa "-0000" para "hora em UTC"; qualquer outra data sem fuso é recusada
        if not texto.endswith("-0000"):
            return None
        quando = quando.replace(tzinfo=timezone.utc)
    quando = quando.astimezone(FUSO)
    if quando > agora + TOLERANCIA_RELOGIO:
        return None
    return quando.isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Leitura do feed
# ---------------------------------------------------------------------------
def ler_itens(bruto, fonte, agora):
    """Recusa DTD, lê o XML e devolve (itens válidos, quantos descartados)."""
    # Usamos o leitor de XML da biblioteca padrão (regra do projeto: sem pacotes
    # de fora, como o defusedxml). A proteção equivalente é recusar qualquer DTD:
    # sem <!DOCTYPE> não existem entidades, nem externas nem "bomba de entidades".
    # Byte nulo indica UTF-16/32, que esconderia o "<!DOCTYPE" desta busca: recusado.
    minusculo = bruto.lower()
    if b"\x00" in bruto or b"<!doctype" in minusculo or b"<!entity" in minusculo:
        raise FalhaDefinitiva("Feed com DOCTYPE/ENTITY (ou em UTF-16/32): recusado.")
    raiz = ET.fromstring(bruto)

    # RSS 2.0: <rss><channel><item>; RSS 1.0: <rdf:RDF><item> (com espaço de nomes)
    brutos = raiz.findall("./channel/item") or raiz.findall(f"./{NS_RSS1}item")
    if not brutos:
        raise ValueError("Feed sem nenhum item.")

    itens, descartados, vistos = [], 0, set()
    for it in brutos:
        titulo = titulo_valido(it.findtext("title") or it.findtext(f"{NS_RSS1}title"))
        link = link_valido(it.findtext("link") or it.findtext(f"{NS_RSS1}link"), fonte["dominios"])
        data = data_valida(it.findtext("pubDate") or it.findtext(f"{NS_DC}date"), agora)
        # Itens sem título, link ou data (ex.: a pasta "2023" do Planalto) ficam de fora
        if not (titulo and link and data) or link in vistos:
            descartados += 1
            continue
        vistos.add(link)
        itens.append({"titulo": titulo, "data": data, "link": link})
    if not itens:
        raise ValueError(f"Nenhum item válido no feed ({descartados} descartados).")
    # Os N mais recentes por data; sem filtro por palavra-chave e sem ranking
    itens.sort(key=lambda i: i["data"], reverse=True)
    return itens[:N_POR_FONTE], descartados


def itens_anteriores(anterior, fonte, agora):
    """Itens da última coleta boa, validados de novo com as mesmas regras."""
    bons = []
    for i in (anterior or {}).get("itens", []):
        if not isinstance(i, dict):
            continue
        titulo = titulo_valido(i.get("titulo") if isinstance(i.get("titulo"), str) else None)
        link = link_valido(i.get("link") if isinstance(i.get("link"), str) else None, fonte["dominios"])
        data = data_valida(i.get("data") if isinstance(i.get("data"), str) else None, agora)
        if titulo and link and data:
            bons.append({"titulo": titulo, "data": data, "link": link})
    return bons[:N_POR_FONTE]


def ler_arquivo_anterior():
    """Lê o noticias.json de ontem (se existir) e devolve {id: bloco}."""
    try:
        with open(ARQUIVO, encoding="utf-8") as f:
            return {b["id"]: b for b in json.load(f).get("fontes", []) if isinstance(b, dict) and "id" in b}
    except (OSError, ValueError, AttributeError, TypeError, KeyError):
        return {}


# ---------------------------------------------------------------------------
# Programa principal
# ---------------------------------------------------------------------------
def coletar_fonte(fonte, anterior, agora):
    """Devolve (bloco para o JSON, deu_certo)."""
    bloco = {k: fonte[k] for k in ("id", "veiculo", "selo", "url_feed", "termos", "url_termos")}
    print(f"\n=== {fonte['veiculo']} ===")
    try:
        itens, descartados = ler_itens(baixar_feed(fonte["url_feed"]), fonte, agora)
        bloco.update(situacao="ok", extraido_em=agora.isoformat(timespec="seconds"), itens=itens)
        print(f"  OK: {len(itens)} itens (descartados no feed: {descartados}).")
        return bloco, True
    except Exception as erro:
        motivo = f"{type(erro).__name__}: {texto_seguro(erro)}"
        print(f"::warning title=Notícias não atualizadas::{fonte['id']}: {motivo}")
        extraido = (anterior or {}).get("extraido_em")
        try:
            quando = datetime.fromisoformat(extraido) if isinstance(extraido, str) else None
        except ValueError:
            quando = None
        itens = itens_anteriores(anterior, fonte, agora) if quando else []
        if quando and quando.tzinfo and agora - quando <= timedelta(days=DIAS_ATE_INDISPONIVEL) and itens:
            bloco.update(situacao="desatualizado", extraido_em=quando.isoformat(timespec="seconds"), itens=itens)
            print(f"  Mantidos {len(itens)} itens da última coleta boa ({bloco['extraido_em']}).")
        else:
            bloco.update(situacao="indisponivel",
                         extraido_em=quando.isoformat(timespec="seconds") if quando and quando.tzinfo else None,
                         itens=[])
            print("  Sem coleta boa nos últimos 7 dias: fonte marcada como indisponível.")
        return bloco, False


def main():
    agora = datetime.now(FUSO)
    anteriores = ler_arquivo_anterior()
    blocos, acertos = [], 0
    for fonte in FONTES:
        bloco, ok = coletar_fonte(fonte, anteriores.get(fonte["id"]), agora)
        blocos.append(bloco)
        acertos += ok

    saida = {"gerado_em": agora.isoformat(timespec="seconds"), "n_por_fonte": N_POR_FONTE, "fontes": blocos}
    # Grava num arquivo temporário e troca de uma vez: nunca fica um JSON pela metade
    os.makedirs("data", exist_ok=True)
    temporario = ARQUIVO + ".tmp"
    with open(temporario, "w", encoding="utf-8") as f:
        json.dump(saida, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(temporario, ARQUIVO)
    print(f"\nGravado {ARQUIVO}: {acertos} de {len(FONTES)} fonte(s) atualizada(s).")
    if acertos == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
