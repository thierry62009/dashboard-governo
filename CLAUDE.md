# CLAUDE.md — Painel do Governo Federal

## Objetivo
Site estático, público e autoatualizável sobre o governo federal do Brasil (presidente em exercício: Lula, terceiro mandato, desde 01/01/2023), com:
- indicadores oficiais (BCB/SGS e IBGE/SIDRA) desde 01/01/2023, com gráficos;
- notícias (só título, veículo, data e link);
- resumo do período, só com fatos e com fonte em cada afirmação.

Python coleta os dados; HTML/CSS/JS simples mostra a página. Hospedado no GitHub Pages e atualizado todo dia pelo GitHub Actions.
Site: https://thierry62009.github.io/dashboard-governo/

## Sobre o usuário
Iniciante em programação (~3h por semana) que quer **aprender**, não só receber código pronto. Escreva em português simples: explique o raciocínio em poucas linhas antes de implementar, comente o código em português e não use frameworks pesados.

## Regras de trabalho (obrigatórias)
1. **Teste de verdade** e mostre a evidência: a resposta real das APIs, falhas provocadas de propósito e a página aberta num navegador.
2. **Nunca invente** códigos de série ou tabela, números ou datas. Um código só é usado depois de testado na API e confirmado pelo usuário no portal oficial.
3. **Todo número exibido** mostra série/tabela, data de extração (vinda do JSON, nunca digitada), link da fonte e licença. Dados do BCB têm licença ODbL, que exige citação.
4. **Neutralidade:**
   - indicadores só de fontes oficiais;
   - notícias de veículos variados, sem opinião, só com título, veículo, data e link;
   - **nunca gerar o resumo do governo automaticamente**;
   - evitar cores de partidos em destaque.
5. **"A conferir":** liste, com link, tudo o que o usuário precisa checar na fonte.
6. **Nada de números de exemplo** na página publicada. O que ainda não existe fica oculto ou marcado "Em breve".
7. **Ritmo:** pode executar etapas inteiras. Pare só quando:
   - precisar de login ou autorização;
   - houver uma decisão que é do usuário;
   - algo falhar sem solução.
   
   Ao fim de cada etapa, diga o que foi feito, como rodar e qual é o próximo passo.
8. **Git:** faça commit com mensagem clara ao fim de cada tarefa. **Push só quando o usuário pedir.** O commit de dados é do robô: não faça commit de `data/*.json` gerado em testes locais (descarte com `git checkout -- data/`).
9. **Não quebre a rotina diária.** Depois de cada mudança, confirme que o script roda, que o YAML é válido e que a pasta `_site` montada como no workflow funciona.

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

## Pronto
- Coleta do IPCA, série SGS 433. Conferido no portal pelo usuário: "Índice nacional de preços ao consumidor-amplo (IPCA)", Var. % mensal, origem IBGE.
- Página com o visual aprovado, publicada e testada no Chromium em 360, 768 e 1440 px.
- Rotina diária no GitHub Actions funcionando nas execuções por push. O robô faz commit a cada execução.

## Falta
- **Fase 3 — indicadores** (esperar o usuário confirmar cada código antes de usar):
  - Selic
  - dólar
  - desocupação (PNAD Contínua)
  - PIB
  - renda média
- **Fase 4 — notícias:** RSS da Agência Brasil e do Planalto, mais 2 ou 3 veículos privados de linhas diferentes (checar o RSS e os termos de uso de cada um). Selo "Oficial" ou "Imprensa".
- **Fase 5 — resumo do período:** fatos com fonte em cada afirmação, escrito e revisado com o usuário, nunca gerado automaticamente.

## Pendências abertas (A conferir)
- [ ] **Teste de 7 dias da rotina agendada (de 11/11 a 17/11/2026).** 1ª execução por `schedule`: 11/11, iniciou 19:29 UTC (atraso de ~7h30 do GitHub em relação às 12:00), sucesso. Confira em https://github.com/thierry62009/dashboard-governo/actions
- [ ] Texto de citação exigido pelo BCB para a ODbL: https://dadosabertos.bcb.gov.br/
- [ ] Comparar valores do gráfico com o SGS (fev/2025 = 1,31; ago/2026 = −0,32): https://www3.bcb.gov.br/sgspub/
- [ ] O usuário deve conferir se o título e a frase de apoio da abertura estão neutros.
- [ ] O usuário deve ver o visual no próprio celular.
- [ ] Confirmar no próximo commit do robô que a mensagem sai no horário de Brasília (formato "Dados atualizados em dd/mm/aaaa às hh:mm (Brasília)", alterado em 11/11).
- [ ] Atenção: o `ubuntu-latest` está migrando para o Ubuntu 26. Se o passo "Instalar Python" falhar, ajuste a versão do Python no workflow.

## Como rodar localmente
```
python3 scripts/coletar_ipca.py   # atualiza data/ipca.json (descarte antes do commit)
python3 -m http.server 8000       # abra http://localhost:8000
```
Para testar como no GitHub, monte a pasta do site como o workflow faz (`_site` com `index.html`, `assets/` e `data/`) e sirva essa pasta.
