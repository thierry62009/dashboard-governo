# CLAUDE.md — Painel (não oficial) do Governo Federal

> Início de cada sessão: leia também o `STATUS.md` (o que está pronto, o que falta, o que o usuário precisa conferir). Fim de cada sessão: atualize o `STATUS.md`.

## Objetivo
Site estático, público e autoatualizável sobre o governo federal do Brasil. Presidente em exercício: Lula, 3º mandato (desde 01/01/2023). O 4º mandato está previsto para janeiro de 2027. No futuro, o painel deve permitir alternar e comparar mandatos de vários presidentes (por isso os dados são organizados por mandato; ver "Decisões já tomadas").

O site traz:
- indicadores oficiais (BCB/SGS, IBGE/SIDRA e Ipeadata) desde 01/01/2023, com gráficos, em 6 áreas: economia, trabalho e renda, contas públicas, saúde, educação e segurança;
- notícias (só título, veículo, data e link);
- resumo do período, só com fatos e com fonte em cada afirmação.

O nome do site é "Painel (não oficial) do Governo Federal". Python coleta os dados; HTML/CSS/JS simples mostra a página. Hospedado no GitHub Pages e atualizado todo dia pelo GitHub Actions.
Site: https://thierry62009.github.io/dashboard-governo/

## Sobre o projeto
Projeto de aprendizado.
- Comente o código em português;
- ao fim de cada fase, escreva "Como isso funciona" em poucas linhas, em português simples;
- não use frameworks pesados;
- priorize entregar pronto com o mínimo de interferência do mantenedor.

## Regras de trabalho (obrigatórias)
1. **Teste de verdade** e mostre a evidência: a resposta real das APIs, falhas provocadas de propósito e a página aberta num navegador.
2. **Nunca invente** códigos de série ou tabela, números ou datas. Um código só é usado depois de:
   - (a) testado na API, e
   - (b) confirmado por fonte oficial independente do teste: nome, unidade e periodicidade conferem com a página ou os metadados oficiais da série (portal do BCB, IBGE/SIDRA).
   Se o item (b) não for possível, o indicador **não vai para a página**: fica "Em breve" e entra em "A conferir". O usuário revisa os códigos em lote ao fim de cada fase, e não um a um.
3. **Todo número exibido** mostra série/tabela, data de extração (vinda do JSON, nunca digitada), link da fonte e licença. Dados do BCB têm licença ODbL, que exige citação.
4. **Neutralidade:**
   - indicadores só de fontes oficiais;
   - notícias de veículos variados, sem opinião, só com título, veículo, data e link;
   - **nunca gerar o resumo do governo automaticamente**;
   - evitar cores de partidos em destaque;
   - ao comparar mandatos ou presidentes, usar as mesmas métricas e a mesma janela de tempo.
5. **"A conferir":** registre no `STATUS.md`, com link, tudo o que o usuário precisa checar na fonte.
6. **Nada de números de exemplo** na página publicada. O que ainda não existe fica oculto ou marcado "Em breve".
7. **Autonomia:** execute fases inteiras, em ordem, sem pedir confirmação. Pare só quando:
   - precisar de login, chave ou autorização que só o usuário tem;
   - houver uma decisão política ou editorial que não esteja nestas regras;
   - algo falhar sem solução depois de duas tentativas diferentes;
   - a ação for irreversível ou fora deste repositório.
   Decisões técnicas e escolhas dentro das regras (por exemplo, quais veículos de notícia, desde que variados) são suas: decida e registre o motivo em uma linha no `STATUS.md`.
   Ao fim de cada fase, relate: o que foi feito, como rodar e o próximo passo.
8. **Git:**
   - commit com mensagem clara ao fim de cada tarefa;
   - **push para `main` permitido ao fim de cada fase concluída**, e só se: os testes passaram, o YAML é válido, a pasta `_site` montada como no workflow funciona e nenhum `data/*.json` gerado em teste local está no commit;
   - nunca use force push;
   - o commit de dados é do robô: descarte os JSON gerados em testes locais com `git checkout -- data/`.
9. **Não quebre a rotina diária.** Depois de cada mudança, confirme que o script roda, que o YAML é válido e que a pasta `_site` montada como no workflow funciona. **Não altere gatilhos nem horário do cron antes de 17/11/2026** (fim do teste de 7 dias).
10. **Economize uso:** não releia arquivos sem necessidade e não repita buscas já feitas. Se perceber que o limite de uso está acabando, termine a tarefa atual em estado consistente (testada e com commit), atualize o `STATUS.md` e pare.
11. **Aprenda e registre:** ao descobrir um cuidado novo de uma API, acrescente-o na seção de cuidados abaixo.
12. **Cuidados com texto e risco jurídico** (o site é público e trata de política):
    - todo texto novo é descritivo: diz o que o dado mede, de onde vem e de quando é, sem adjetivos de juízo ("queda histórica", "preocupante"), sem relação de causa e efeito e sem atribuir intenção ou culpa a pessoas ou órgãos;
    - o título, a abertura e o rodapé sempre dizem que o projeto é pessoal e **não oficial**; não use brasão, logotipo do governo nem fotos de pessoas;
    - notícias: só título, veículo, data e link, nunca o texto da matéria;
    - o resumo do período (Fase 5) traz só fatos, cada um com fonte, escrito e aprovado pelo usuário;
    - mantenha o canal de contato do rodapé e corrija os erros confirmados na fonte;
    - nunca publique e-mail, telefone ou outros dados pessoais do usuário no site nem no repositório.

## Cuidados com o SGS (API do BCB)
- URL: `https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados?formato=json&dataInicial=dd/mm/aaaa&dataFinal=dd/mm/aaaa`
- Séries diárias recusam janelas acima de 10 anos; o endpoint `ultimos/N` aceita no máximo 20 valores.
- A resposta traz `data` como "dd/mm/aaaa" e `valor` como **texto**.
- Erros já observados: código inexistente dá HTTP 404; data inicial depois da final dá HTTP 400.
- O IPCA mensal é uma variação %: para acumular, multiplique os fatores (1+v/100); **nunca some**.
- A série 432 (meta Selic) já vem com **datas futuras** (até a próxima reunião do Copom): descarte o que passar de hoje.
- O endpoint `ultimos/N` não garante a ordem (algumas séries vêm da mais nova para a mais antiga): ordene sempre.
- O portal antigo `www3.bcb.gov.br/sgspub` costuma dar HTTP 502 para robôs. Para conferir nome, unidade e periodicidade, use o catálogo `https://dadosabertos.bcb.gov.br/api/3/action/package_search?q=codigo_sgs:{codigo}` (filtre pelo campo `codigo_sgs` exato). Nem toda série está no catálogo (a 433 não está); sem ficha oficial, a série não entra.

## Cuidados com o SIDRA (API do IBGE)
- Dados: `https://apisidra.ibge.gov.br/values/t/{tabela}/n1/all/v/{variavel}/p/all` (acrescente `/c{classificacao}/{categoria}` quando a tabela tiver classificações). A primeira linha da resposta é o cabeçalho; `V` é **texto** e pode vir `...`, `-` ou `X` quando não há valor.
- Metadados oficiais (nome, unidade, periodicidade): `https://servicodados.ibge.gov.br/api/v3/agregados/{tabela}/metadados`. Essa resposta vem **compactada (gzip)** mesmo sem pedir.
- Códigos de período: `aaaamm` no trimestre móvel (mês em que o trimestre termina), `aaaa0t` no trimestral (t = trimestre) e `aaaa` no anual.
- Erros já observados: tabela ou variável inexistente dá HTTP 400 com texto explicativo.
- O script confere, a cada execução, se o nome da variável e a unidade continuam iguais aos conferidos; se mudarem, recusa os dados.
- O serviço de metadados (`servicodados.ibge.gov.br`) **não responde aos servidores do GitHub Actions** (tempo esgotado); a API de dados (`apisidra`) responde. No GitHub, os metadados do IBGE ficam como aviso; confira-os rodando o verificador no seu computador.
- Séries "reais" (rendimento) são recalculadas pelo IBGE a cada divulgação: os valores antigos mudam.

## Cuidados com o Ipeadata
- Dados: `https://www.ipeadata.gov.br/api/odata4/ValoresSerie(SERCODIGO='{codigo}')`; metadados em `.../Metadados('{codigo}')` (o `$filter` com `contains` dá HTTP 400).
- Código inexistente **não dá erro**: vem HTTP 200 com lista vazia. A resposta começa com uma marca invisível (BOM): leia como `utf-8-sig`.
- O nome `www.ipeadata.gov.br` aponta para **dois servidores**, e um deles (177.15.137.13, visto em 17/11/2026) não responde: quem cair nele espera ~40 s ou recebe falha de conexão. Não é erro do painel; use tempo-limite e novas tentativas.

## Cuidados com os RSS de notícias
- A Agência Brasil responde **HTTP 500** a qualquer User-Agent que contenha "python" (o padrão do urllib): use `painel-indicadores/1.0`.
- O RSS do Planalto é RSS 1.0 (RDF), embora o servidor o declare como Atom; os itens não vêm em ordem de data e incluem pastas (ex.: "2023") que não são notícias.
- Os feeds trazem resumo (`description`): ele é sempre descartado.

## Decisões já tomadas
- **Hospedagem:** GitHub Pages no modo "GitHub Actions" (não "deploy from branch"). O site publicado contém só `index.html`, `assets/` e `data/`; `scripts/` e `.github/` não ficam públicos.
- **Verificador:** `scripts/verificar.py` lê a lista de `scripts/coletar.py` (fonte única dos códigos) e confere metadados oficiais, 3 valores por série (por um endereço diferente do da coleta), atualização, esquema dos JSON, consistência com `painel.js` e `mandatos.json`, e se **todos os links da página** abrem (os de `data/*.json`, `index.html` e `painel.js`; só servidores da lista `SERVIDORES_DOS_LINKS`; link quebrado é erro; servidor com endereço morto é aviso; o TSE recusa robôs e fica de fora). Só aponta: nunca corrige nem grava em `data/` ou `assets/`. Sai com código 1 se houver erro. Roda toda segunda às 12:00 de Brasília por `.github/workflows/verificar.yml` (só leitura, sem commit) e pelo botão manual.
- **Segurança:**
  - Actions sempre fixadas pelo hash completo do commit (versão em comentário); o Dependabot (`.github/dependabot.yml`) propõe as atualizações. Permissões declaradas por job, com `permissions: {}` no topo.
  - Respostas das APIs são dados de fora: limite de 20 MB (também ao descompactar), sem redirecionamento para fora de https, datas só no formato `aaaa-mm`, e texto de erro passa por `texto_seguro` antes de ser impresso.
  - A página tem CSP em `<meta>` (só carrega arquivos do próprio site): nada de script ou estilo escrito dentro do HTML, nada de CDN. Texto vindo do JSON entra sempre por `textContent`; links passam pela função `link` (só http/https).
- **Rotina:** `.github/workflows/atualizar.yml`.
  - Gatilhos: cron `0 12 * * *` (09:00 de Brasília), botão manual e push em `main`.
  - Passos: roda o script, faz commit do JSON (mantém o agendamento ativo), monta `_site` e publica.
  - Se o script terminar com erro (todos os indicadores falharam), nada é gravado nem publicado. Falha de um indicador só vira aviso amarelo na execução.
- **Coleta:** um script só, `scripts/coletar.py`, com a lista `INDICADORES` (um bloco por indicador). Só a biblioteca padrão do Python. O script valida os dados (lista não vazia, períodos em ordem, sem repetição, sem data futura) e grava via arquivo `.tmp` + `os.replace`. Se um indicador falhar (3 tentativas), o arquivo antigo dele é mantido e os outros seguem; o script só termina com erro se todos falharem.
- **Formato dos JSON** (`data/xxx.json`):
  ```json
  {
    "serie": {"codigo", "identificacao", "nome", "unidade", "periodicidade", "origem",
              "fonte", "fonte_sigla", "licenca", "url_licenca", "url_fonte", "url_pagina",
              "observacao" (opcional)},
    "extraido_em": "ISO com fuso -03:00",
    "dados": [{"data": "aaaa-mm", "valor": número, "dia": "aaaa-mm-dd" (só séries diárias)}]
  }
  ```
  Esse formato é mantido para todos os indicadores novos.
  - `url_licenca` vazio = sem página oficial de licença confirmada (hoje, o IBGE): o painel mostra o texto de `licenca` sem link, e o rodapé diz "Uso dos dados:" em vez de "Licença:". Nunca afirme uma licença sem fonte oficial.
  - `periodicidade`: `mensal`, `trimestre_movel` (data = mês em que o trimestre termina), `trimestral` (data = último mês do trimestre) ou `anual` (data = `aaaa-12`).
  - Séries diárias (Selic, dólar) guardam só o último dia disponível de cada mês, com o dia exato em `dia`. Nenhum número é calculado pelo painel (nada de médias próprias).
- **Mandatos:** `data/mandatos.json` lista os mandatos, cada um com `id`, `presidente`, `numero`, `inicio` (aaaa-mm-dd), `fim` (aaaa-mm-dd ou `null`), `status` (`encerrado`, `em_andamento` ou `futuro`) e, obrigatórios nos mandatos em andamento e futuros, `fonte` (texto) e `url_fonte` (link https de página oficial que diz de onde vem a data). Hoje: Lula 3º mandato (em andamento, desde 2023-01-01) e Lula 4º mandato (futuro, janeiro de 2027). Os indicadores continuam em um arquivo por série; a página filtra pelo intervalo do mandato escolhido. Para acrescentar um mandato ou presidente, edite só esse arquivo.
- **Página:** `index.html` + `assets/estilo.css` + `assets/painel.js` (listas `AREAS` e `INDICADORES`; para um indicador novo, acrescente um item) + `assets/grafico.js` (colunas em SVG com JS puro, sem bibliotecas nem CDN).
- **Visual:** tema escuro, sem fundo branco.
  - Cores (variáveis no topo do `estilo.css`):

    | Uso | Cor |
    |---|---|
    | Fundo da página | #101216 |
    | Cabeçalho, abertura e rodapé | #15171C |
    | Cartões | #1A1D24 |
    | Cartões de destaque | #1E2128 |
    | Bordas e grade | #2C303A |
    | Eixo | #3A3F4B |
    | Texto | #F3EFE8 |
    | Texto secundário | #A9A399 |
    | Laranja (só detalhe) | #F97316 |
    | Links | #FDBA74 |
    | Contorno do botão inativo | #6B7180 (3,8:1) |

  - Fontes: Archivo 600–800 (títulos, números e botões; peso 800 em títulos e números) e Manrope 400–700 (texto), hospedadas no próprio site (`assets/fontes/`, licença OFL), sem Google Fonts.
  - Botão ativo: fundo laranja com **texto escuro**. Texto claro sobre o laranja dá só 2,45:1 e reprova.
- **Estrutura da página:**
  1. cabeçalho com âncoras;
  2. abertura com o selo "Atualizado em";
  3. cartões de destaque;
  4. indicadores com botões de período (Desde 2023, 12 e 6 meses) e de mandato, agrupados por área;
  5. notícias;
  6. resumo com abas, uma por área dos indicadores (Economia, Trabalho e renda, Contas públicas, Saúde, Educação, Segurança);
  7. rodapé com fonte e licença.
- **Acessibilidade:**
  - contraste de texto de pelo menos 4,5:1 (o menor atual é 6,4:1);
  - botões e links reais, com altura mínima de 44 px;
  - `aria-label` nos gráficos e tabela com os mesmos números;
  - foco visível;
  - funciona de 360 a 1440 px sem rolagem lateral.
- **Notícias:** `scripts/noticias.py` (lista `FONTES`, um bloco por fonte) grava `data/noticias.json` com `gerado_em`, `n_por_fonte` e, por fonte, `id`, `veiculo`, `selo` (`Oficial` ou `Imprensa`), `url_feed`, `termos`, `url_termos`, `situacao` (`ok`, `desatualizado` ou `indisponivel`), `extraido_em` (última coleta boa) e `itens` (só `titulo`, `data` ISO com fuso e `link`). Os 5 mais recentes por fonte, por data, sem filtro nem ranking. Recusa DTD, limite de 2 MB, título acima de 300 caracteres descartado (nunca cortado), link só https do domínio da fonte, sem data futura. No workflow, o passo "Coletar notícias" tem `continue-on-error`.
- **Gráficos:** sempre colunas a partir do zero (não exagera variações e aceita valores negativos), em todos os indicadores.

## Como rodar localmente
```
python3 scripts/coletar.py        # atualiza todos os data/*.json (descarte antes do commit)
python3 scripts/coletar.py selic  # só os indicadores citados
python3 scripts/noticias.py       # atualiza data/noticias.json (descarte antes do commit)
python3 scripts/verificar.py      # confere tudo com as fontes oficiais (só aponta; não grava nada)
python3 -m http.server 8000       # abra http://localhost:8000
```
Para testar como no GitHub, monte a pasta do site como o workflow faz (`_site` com `index.html`, `assets/` e `data/`) e sirva essa pasta.
