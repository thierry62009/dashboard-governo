# CLAUDE.md — Painel do Governo Federal

> Início de cada sessão: leia também o `STATUS.md` (o que está pronto, o que falta, o que o usuário precisa conferir). Fim de cada sessão: atualize o `STATUS.md`.

## Objetivo
Site estático, público e autoatualizável sobre o governo federal do Brasil. Presidente em exercício: Lula, 3º mandato (desde 01/01/2023). O 4º mandato está previsto para janeiro de 2027. No futuro, o painel deve permitir alternar e comparar mandatos de vários presidentes (por isso os dados são organizados por mandato; ver "Decisões já tomadas").

O site traz:
- indicadores oficiais (BCB/SGS e IBGE/SIDRA) desde 01/01/2023, com gráficos;
- notícias (só título, veículo, data e link);
- resumo do período, só com fatos e com fonte em cada afirmação.

Python coleta os dados; HTML/CSS/JS simples mostra a página. Hospedado no GitHub Pages e atualizado todo dia pelo GitHub Actions.
Site: https://thierry62009.github.io/dashboard-governo/

## Sobre o usuário
Iniciante em programação (~3h por semana). **Prioridade: receber o trabalho pronto, com o mínimo de interferência dele.** Ele ainda quer aprender, então:
- comente o código em português;
- ao fim de cada fase, escreva "Como isso funciona" em poucas linhas, em português simples;
- não use frameworks pesados;
- não peça aprovação de planos nem explique longamente antes de implementar.

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

## Cuidados com o SGS (API do BCB)
- URL: `https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados?formato=json&dataInicial=dd/mm/aaaa&dataFinal=dd/mm/aaaa`
- Séries diárias recusam janelas acima de 10 anos; o endpoint `ultimos/N` aceita no máximo 20 valores.
- A resposta traz `data` como "dd/mm/aaaa" e `valor` como **texto**.
- Erros já observados: código inexistente dá HTTP 404; data inicial depois da final dá HTTP 400.
- O IPCA mensal é uma variação %: para acumular, multiplique os fatores (1+v/100); **nunca some**.

## Decisões já tomadas
- **Hospedagem:** GitHub Pages no modo "GitHub Actions" (não "deploy from branch"). O site publicado contém só `index.html`, `assets/` e `data/`; `scripts/` e `.github/` não ficam públicos.
- **Rotina:** `.github/workflows/atualizar.yml`.
  - Gatilhos: cron `0 12 * * *` (09:00 de Brasília), botão manual e push em `main`.
  - Passos: roda o script, faz commit do JSON (mantém o agendamento ativo), monta `_site` e publica.
  - Se o script falhar, nada é gravado nem publicado.
- **Coleta:** só a biblioteca padrão do Python. O script valida os dados (lista não vazia, meses em ordem, sem repetição) e grava via arquivo `.tmp` + `os.replace`.
- **Formato dos JSON** (`data/xxx.json`):
  ```json
  {
    "serie": {"codigo", "nome", "unidade", "origem", "fonte", "url_fonte", "licenca"},
    "extraido_em": "ISO com fuso -03:00",
    "dados": [{"data": "aaaa-mm", "valor": número}]
  }
  ```
  Esse formato é mantido para todos os indicadores novos.
- **Mandatos:** `data/mandatos.json` lista os mandatos, cada um com `id`, `presidente`, `numero`, `inicio` (aaaa-mm-dd), `fim` (aaaa-mm-dd ou `null`) e `status` (`encerrado`, `em_andamento` ou `futuro`). Hoje: Lula 3º mandato (em andamento, desde 2023-01-01) e Lula 4º mandato (futuro, janeiro de 2027). Os indicadores continuam em um arquivo por série; a página filtra pelo intervalo do mandato escolhido. Para acrescentar um mandato ou presidente, edite só esse arquivo.
- **Página:** `index.html` + `assets/estilo.css` + `assets/painel.js` (lista `INDICADORES`; para um indicador novo, acrescente um item) + `assets/grafico.js` (colunas em SVG com JS puro, sem bibliotecas nem CDN).
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

  - Fontes: Archivo 600–800 (títulos, números e botões; peso 800 em títulos e números) e Manrope 400–700 (texto), pelo Google Fonts.
  - Botão ativo: fundo laranja com **texto escuro**. Texto claro sobre o laranja dá só 2,45:1 e reprova.
- **Estrutura da página:**
  1. cabeçalho com âncoras;
  2. abertura com o selo "Atualizado em";
  3. cartões de destaque;
  4. indicadores com botões de período (Desde 2023, 12 e 6 meses);
  5. notícias;
  6. resumo com abas (Economia, Saúde, Educação, Relações exteriores);
  7. rodapé com fonte e licença.
- **Acessibilidade:**
  - contraste de texto de pelo menos 4,5:1 (o menor atual é 6,4:1);
  - botões e links reais, com altura mínima de 44 px;
  - `aria-label` nos gráficos e tabela com os mesmos números;
  - foco visível;
  - funciona de 360 a 1440 px sem rolagem lateral.
- **Gráfico do IPCA:** colunas a partir do zero, porque é uma variação mensal com meses negativos.

## Como rodar localmente
```
python3 scripts/coletar_ipca.py   # atualiza data/ipca.json (descarte antes do commit)
python3 -m http.server 8000       # abra http://localhost:8000
```
Para testar como no GitHub, monte a pasta do site como o workflow faz (`_site` com `index.html`, `assets/` e `data/`) e sirva essa pasta.
