# STATUS — Painel do Governo Federal

> Atualize este arquivo ao fim de cada sessão. As regras ficam no `CLAUDE.md`.

## Pronto
- Coleta do IPCA, série SGS 433. Conferido no portal pelo usuário: "Índice nacional de preços ao consumidor-amplo (IPCA)", Var. % mensal, origem IBGE.
- Página com o visual aprovado, publicada e testada no Chromium em 360, 768 e 1440 px.
- Rotina diária no GitHub Actions funcionando nas execuções por push. O robô faz commit a cada execução.
- **Fase 3a — Mandatos (14/11/2026).** `data/mandatos.json` criado e publicado junto com `data/`. A página lê o arquivo, mostra os botões de mandato (o 4º aparece desligado, "Em breve") e filtra indicadores e destaques pelo mandato escolhido. Os indicadores passaram a ser agrupados por área. Testado no Brave sem janela em 360, 768 e 1440 px (sem rolagem lateral, botões com 44 px) e com falha provocada (sem `mandatos.json` a página avisa e mostra os dados sem filtro).
- **Fase 3 — Indicadores de economia (14/11/2026).** Script único `scripts/coletar.py` (substituiu o antigo script só do IPCA; o IPCA sai idêntico). No ar: Selic (meta), dólar (venda), PIB (acumulado em 4 trimestres), taxa de desocupação e rendimento médio real, além do IPCA. Cada código foi testado na API e conferido nos metadados oficiais (catálogo de dados abertos do BCB e serviço de metadados do IBGE). Falhas provocadas: código SGS inexistente (404), variável SIDRA inexistente (400), nome de variável diferente do conferido (recusado), série vazia (recusada), todos falhando (script termina com erro); o arquivo antigo fica intacto.
- **Fase 3b — Outras áreas (14/11/2026).** No ar, com o mesmo teste (API + metadados oficiais): contas públicas (dívida bruta, dívida líquida e resultado primário, do BCB), emprego formal (saldo do Novo Caged, via Ipeadata), saúde (mortalidade de menores de 5 anos e mortalidade materna), educação (analfabetismo, escolarização de 15 a 17 anos e conclusão do ensino médio) e segurança (homicídios por 100 mil habitantes). Total: 16 indicadores em 6 áreas. Página testada em 360, 768 e 1440 px com os 16 cartões, sem rolagem lateral.
- **Limites conhecidos da Fase 3b (não são erros):**
  - Saúde e segurança são indicadores **anuais e com atraso** da fonte: saúde só tem 2023 dentro do mandato; homicídios vão até 2024. Os gráficos têm 1 ou 2 colunas.
  - Segurança ficou com **1 indicador**: não achei outra série nacional de segurança com API oficial estável (os dados do Sinesp/Ministério da Justiça saem em planilhas, sem API).
  - Saúde: cobertura vacinal e outros dados do DataSUS não têm API simples e estável; ficaram de fora.
- **Fase 3c — Verificador (14/11/2026).** `scripts/verificar.py` + `.github/workflows/verificar.yml` (segunda, 12:00 de Brasília, e botão manual; só leitura). Confere metadados oficiais, 3 valores por série, atualização, esquema, consistência da página e mandatos; só aponta, nunca corrige. Falhas provocadas numa cópia temporária, todas detectadas: código inexistente, unidade trocada, valor alterado, série velha, JSON fora da lista do painel, mandato incoerente (inclusive o lembrete de janeiro de 2027, testado com `--hoje 2027-01-10`). Rodar: `python3 scripts/verificar.py`.
- **Site no ar conferido em 14/11/2026 às 16:08:** 16 cartões, 6 destaques, 16 linhas de fonte, nenhum aviso de erro; o robô gerou os 16 arquivos de dados no GitHub (nenhum JSON de teste local foi para o repositório).
- **Próximo passo:** Fase 4 (notícias). Antes, o usuário revisa a lista "A conferir" abaixo.
- **Cuidados de texto e de risco (14/11/2026).** Título, abertura e rodapé dizem "não oficial"; "atualizados todos os dias" virou "verificados todos os dias (cada série muda no ritmo da fonte)"; as abas do resumo agora seguem as seis áreas dos indicadores (saiu "Relações exteriores"); o rodapé ganhou aviso e link para as Issues; nova regra 12 no `CLAUDE.md`. Commit e push em 14/11/2026, depois de testar em 360, 768 e 1440 px (sem rolagem lateral).

- **Textos de licença e observações (14/11/2026).** IBGE sem afirmar licença (texto de citação, sem link); Ipeadata com o texto conferido na página de direitos de uso; BCB continua ODbL. README ganhou a seção "Licença dos dados" (código do projeto: licença a definir). PIB e desocupação explicam que os primeiros pontos incluem períodos de 2022. Selic e dólar mostram "mês em andamento, até dd/mm" no destaque, na nota do gráfico, na dica da coluna e na tabela (comparando o mês do último ponto com o mês de `extraido_em`, ambos do JSON). Verificador aceita `url_licenca` vazio. Testado em 360 e 1440 px.

## Roteiro de fases
Cada fase termina com testes, commit, push (regra 8 do `CLAUDE.md`) e este arquivo atualizado.

- ~~Fase 3a — Mandatos~~ **concluída em 14/11/2026** (ver "Pronto"). Texto original: Criar `data/mandatos.json` (ver "Decisões já tomadas" no `CLAUDE.md`), publicá-lo no `_site`, e fazer a página filtrar os indicadores pelo intervalo do mandato. Com um só mandato "em andamento", a página fica como está hoje; o 4º mandato aparece como "Em breve" até janeiro de 2027.
- ~~Fase 3 — Indicadores de economia~~ **concluída em 14/11/2026** (ver "Pronto"). Texto original: Um de cada vez, na ordem: Selic, dólar, desocupação (PNAD Contínua), PIB, renda média. Cada um segue a regra 2 (testar na API e confirmar por fonte oficial independente; sem isso, fica "Em breve").
- ~~Fase 3b — Outras áreas~~ **concluída em 14/11/2026** (ver "Pronto"). Texto original: contas públicas (por exemplo dívida pública e resultado primário), emprego formal (saldo de vagas), e 2 a 3 indicadores de saúde, educação e segurança com fonte oficial aberta e atualização regular. Se uma área não tiver fonte confiável, registre o motivo aqui e siga adiante. Não invente códigos: pesquise e teste.
- **Fase 4 — Notícias:** RSS da Agência Brasil e do Planalto, mais 2 ou 3 veículos privados de linhas diferentes (checar o RSS e os termos de uso de cada um). Selo "Oficial" ou "Imprensa". Só título, veículo, data e link. Atualização diária.
- **Fase 5 — Resumo do período:** fatos com fonte em cada afirmação, escrito e revisado **com o usuário**, nunca gerado automaticamente. Esta fase não é autônoma: o Claude Code pode no máximo preparar a lista de fatos candidatos com fonte, para o usuário aprovar.
- **Fase 6 — Comparação entre mandatos e presidentes (futura):** seletor para alternar e comparar mandatos de vários presidentes, com as mesmas métricas e a mesma janela de tempo. Exige estender a coleta para antes de 2023 (atenção ao limite de 10 anos das séries diárias do SGS). Começar só depois da Fase 3 completa.

## Pendências abertas (A conferir — só o usuário pode fazer)
- [ ] **Teste de 7 dias da rotina agendada (de 11/11 a 17/11/2026).** 1ª execução por `schedule`: 11/11, iniciou 19:29 UTC (atraso de ~7h30 do GitHub em relação às 12:00), sucesso. Confira em https://github.com/thierry62009/dashboard-governo/actions
- [ ] Texto de citação exigido pelo BCB para a ODbL: https://dadosabertos.bcb.gov.br/
- [ ] Comparar valores do gráfico com o SGS (fev/2025 = 1,31; ago/2026 = −0,32): https://www3.bcb.gov.br/sgspub/
- [ ] O usuário deve conferir se o título e a frase de apoio da abertura estão neutros.
- [ ] O usuário deve ver o visual no próprio celular.
- [x] (Conferido em 14/11: "Dados atualizados em 14/11/2026 às 16:08 (Brasília)".) Confirmar no próximo commit do robô que a mensagem sai no horário de Brasília (formato "Dados atualizados em dd/mm/aaaa às hh:mm (Brasília)", alterado em 11/11).
- [ ] Atenção: o `ubuntu-latest` está migrando para o Ubuntu 26. Se o passo "Instalar Python" falhar, ajuste a versão do Python no workflow.
- [ ] **Data de início do 4º mandato em `data/mandatos.json`: 05/01/2027.** Usei a Emenda Constitucional 111/2021 (posse do presidente em 5 de janeiro a partir de 2027). Confira o art. 82 em https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc111.htm — se estiver diferente, mude só o campo `inicio`.
- [ ] **Códigos da Fase 3 (revisão em lote).** Abra cada link e confira nome, unidade e periodicidade:
  - Selic — SGS 432, "Taxa de juros - Meta Selic definida pelo Copom", diária, % a.a.: https://dadosabertos.bcb.gov.br/dataset/432-taxa-de-juros---meta-selic-definida-pelo-copom
  - Dólar — SGS 1, "Taxa de câmbio - Livre - Dólar americano (venda) - diário", diária, R$/US$: https://dadosabertos.bcb.gov.br/dataset/1-taxa-de-cambio---livre---dolar-americano-venda---diario
  - PIB — SIDRA tabela 5932, variável 6562 "Taxa acumulada em quatro trimestres (em relação ao mesmo período do ano anterior)", categoria 90707 "PIB a preços de mercado", trimestral, %: https://sidra.ibge.gov.br/tabela/5932
  - Desocupação — SIDRA tabela 6381, variável 4099, trimestre móvel, %: https://sidra.ibge.gov.br/tabela/6381
  - Rendimento — SIDRA tabela 6390, variável 5933 (rendimento médio mensal **real**, habitualmente recebido, todos os trabalhos), trimestre móvel, Reais: https://sidra.ibge.gov.br/tabela/6390
- [ ] **Códigos da Fase 3b (revisão em lote).** Abra cada link e confira nome, unidade e periodicidade:
  - Dívida bruta — SGS 13762, "Dívida bruta do governo geral (% PIB) - Metodologia utilizada a partir de 2008", mensal: https://dadosabertos.bcb.gov.br/dataset/13762-divida-bruta-do-governo-geral--pib---metodologia-utilizada-a-partir-de-2008
  - Dívida líquida — SGS 4513, "Dívida Líquida do Setor Público (% PIB) - Total - Setor público consolidado", mensal: https://dadosabertos.bcb.gov.br/dataset/4513-divida-liquida-do-setor-publico--pib---total---setor-publico-consolidado
  - Resultado primário — SGS 5793, "NFSP sem desvalorização cambial (% PIB) - Fluxo acumulado em 12 meses - Resultado primário - Total - Setor público consolidado", mensal: https://dadosabertos.bcb.gov.br/dataset/5793-nfsp-sem-desvalorizacao-cambial--pib---fluxo-acumulado-em-12-meses---resultado-primario---tota
  - Emprego formal — Ipeadata CAGED12_SALDONAJU12, "Empregados - saldo - com ajuste - novo Caged", mensal, Pessoa: https://www.ipeadata.gov.br/api/odata4/Metadados('CAGED12_SALDONAJU12') — vale comparar um mês com o painel do Ministério do Trabalho: http://pdet.mte.gov.br/novo-caged
  - Mortalidade de menores de 5 anos — SIDRA tabela 6695, variável 9731, anual: https://sidra.ibge.gov.br/tabela/6695
  - Mortalidade materna — SIDRA tabela 6694, variável 9730, anual: https://sidra.ibge.gov.br/tabela/6694
  - Analfabetismo — SIDRA tabela 7113, variável 10267 (sexo: total; 15 anos ou mais), anual: https://sidra.ibge.gov.br/tabela/7113
  - Escolarização de 15 a 17 anos — SIDRA tabela 7138, variável 10276 (sexo: total; 15 a 17 anos), anual: https://sidra.ibge.gov.br/tabela/7138
  - Conclusão do ensino médio — SIDRA tabela 4731, variável 4721 (ensino médio, 20 a 22 anos), anual: https://sidra.ibge.gov.br/tabela/4731
  - Homicídios — SIDRA tabela 6606, variável 13532, anual: https://sidra.ibge.gov.br/tabela/6606
- [ ] **Sinal do resultado primário.** O cartão diz: "valor positivo indica déficit e valor negativo indica superávit" (convenção das tabelas do BCB para a NFSP). Confira nas notas de estatísticas fiscais do BCB, por exemplo: https://www.bcb.gov.br/content/estatisticas/hist_estatisticasfiscais/202603_Texto_de_estatisticas_fiscais.pdf e no manual https://www.bcb.gov.br/ftp/infecon/estatisticasfiscais.pdf
- [ ] **Emprego formal vem do Ipeadata, não direto do Ministério do Trabalho** (que só publica planilhas). O Ipeadata é do Ipea, órgão federal, e ainda chama a fonte de "Min. Economia/SEPRT". Decida se aceita essa fonte intermediária; se não, é só apagar o bloco `emprego_formal` em `scripts/coletar.py` e em `assets/painel.js`.
- [x] ~~Licença do Ipeadata~~ — conferida em 14/11/2026 na página "Direitos de Uso" (http://www.ipeadata.gov.br/iframe_direitouso.aspx): o conteúdo "é considerado informação pública que pode ser livremente distribuída e copiada, resguardando-se a obrigatoriedade de citação da fonte Ipeadata". Texto no painel: "Informação pública, que pode ser distribuída e copiada com citação da fonte Ipeadata".
- [ ] Origem dos indicadores de saúde, conclusão do ensino médio e homicídios: aparecem como "IBGE, Objetivos de Desenvolvimento Sustentável" porque os metadados do SIDRA não dizem qual ministério produz o dado. Se quiser citar o órgão produtor, confira nas notas de cada tabela (links acima).
- [ ] A frase de apoio da abertura mudou para "Dados do Banco Central, do IBGE e do Ipeadata…" (entra na conferência de neutralidade já pedida).
- [ ] **Verificador no GitHub (execução manual de 14/11, sucesso, 0 erros):** os metadados das 9 tabelas do IBGE não puderam ser conferidos lá, porque o serviço de metadados do IBGE não responde aos servidores do GitHub. Valores, atualização, esquema e mandatos foram conferidos normalmente. Para conferir os metadados do IBGE, rode `python3 scripts/verificar.py` no seu computador de vez em quando (lá funciona). Resultado: https://github.com/thierry62009/dashboard-governo/actions/runs/43635007510
- [ ] **Avisos do verificador (primeira execução, 14/11):** o IPCA (SGS 433) não tem ficha no catálogo de dados abertos do BCB, então o verificador não confere nome/unidade dele (você já conferiu no portal em 10/11). Os demais avisos são nomes do painel mais detalhados que o oficial (PIB, saúde, escolarização, conclusão do ensino médio, homicídios): confira se aceita.
- [ ] **Decisão sobre o texto do IBGE.** Sem licença formal confirmada, o painel agora diz só "Dados do IBGE (SIDRA); fonte citada conforme orientação do IBGE", sem link (no rodapé aparece como "Uso dos dados:", não "Licença:"). O site do IBGE devolve erro 403 para robôs, então não consegui abrir nenhuma página oficial de uso dos dados. Se você achar uma (ex.: https://biblioteca.ibge.gov.br/biblioteca-servicos.html, que uma sessão anterior citou), confira o texto e me passe o link para eu pôr em `url_licenca` no bloco "sidra" de `scripts/coletar.py`; ou aprove o texto como está.
- [ ] Frases de "observação" que aparecem nos cartões (Selic, dólar, PIB, desocupação, rendimento): confira se estão claras e neutras. Ficam no campo `observacao` de `scripts/coletar.py`.
- [ ] Em janeiro de 2027, edite `data/mandatos.json`: no 3º mandato, ponha `fim` (último dia) e `status: "encerrado"`; no 4º, `status: "em_andamento"`.
- [x] (Feito em 14/11.) **Commit e push dos cuidados de texto** (`index.html`, `CLAUDE.md`, `STATUS.md`). Antes, veja a página localmente (`python3 -m http.server 8000`) em 360 px e confirme que as 6 abas do resumo não causam rolagem lateral. O robô também faz commits: use `git pull --rebase` antes do push.
- [ ] **Habilitar as Issues do repositório** (GitHub > Settings > General > Features > Issues), porque o rodapé manda o leitor para lá. Se preferir outro canal de contato, troque o link em `index.html` (e não coloque e-mail pessoal sem querer).
- [ ] Reler o aviso do rodapé ("projeto pessoal e não oficial...") e decidir se quer uma orientação jurídica específica (advogado ou núcleo de prática jurídica de faculdade de Direito).
- [ ] Fase 5: o resumo tem uma aba por área de indicadores. "Relações exteriores" saiu por não ter indicador; reintroduza só com critério e fonte.

## Decisões registradas pelo Claude Code
(Uma linha por decisão, com o motivo.)
- 14/11 — Mês de transição entre mandatos: o mês conta para quem estava em exercício no dia 15 (dados são mensais; evita o mesmo mês em dois mandatos).
- 14/11 — `mandatos.json` ganhou o campo extra `nome_curto` (texto do botão) e `_como_editar` (instruções); o 3º mandato fica com `fim: null` enquanto está em andamento.
- 14/11 — Botões "12 meses" e "6 meses" passaram a contar meses do calendário a partir do dado mais recente (antes contavam pontos), para valer igual em séries mensais, trimestrais e anuais.
- 14/11 — Um script só (`coletar.py`) para todos os indicadores, em vez de um por série: menos código repetido e um único passo no workflow.
- 14/11 — Falha de um indicador não derruba a rotina: o arquivo de ontem é mantido e a execução mostra um aviso; só para tudo se todos falharem (com 6+ APIs, parar tudo por uma falha deixaria o site inteiro parado). Cada cartão mostra a sua própria data de extração.
- 14/11 — Selic: série 432 (meta do Copom), e não a taxa efetiva, por ser a taxa que o Copom anuncia. Dólar: série 1 (venda, diária), porque as séries mensais de dólar (3696/3698) não têm ficha no catálogo oficial e não puderam ser conferidas.
- 14/11 — Séries diárias mostram o último dia disponível de cada mês (sem médias calculadas pelo painel: nenhum número exibido é conta nossa).
- 14/11 — PIB: taxa acumulada em 4 trimestres (variável 6562), por ser a menos sujeita a efeitos sazonais e a mais fácil de comparar entre mandatos.
- 14/11 — Áreas da seção de indicadores: Economia, Trabalho e renda, Contas públicas, Saúde, Educação e Segurança. Destaques da abertura: IPCA, Selic, dólar, PIB e desocupação.
- 14/11 — Contas públicas pelo BCB (setor público consolidado e governo geral, em % do PIB), por serem as séries com ficha oficial e atualização mensal.
- 14/11 — Emprego formal: série "com ajuste" do Novo Caged (inclui declarações fora do prazo), via Ipeadata, única API oficial encontrada; a série que eu lembrava no SGS (28763) era estoque, não saldo, e não tem ficha no catálogo: descartada.
- 14/11 — Saúde, educação e segurança: tabelas nacionais do SIDRA (PNAD Contínua anual e indicadores ODS), por terem API estável e metadados oficiais. Escolarização: faixa de 15 a 17 anos (idade do ensino médio).
- 14/11 — Indicadores anuais são guardados como `aaaa-12` e a página mostra só o ano.
- 14/11 — Verificador: atraso máximo por periodicidade = duração do período + prazo de divulgação + folga (diária 7 dias, mensal e trimestre móvel 75, trimestral 170, anual 1200). O limite do PIB começou em 120 e deu falso alarme na primeira execução (o PIB do 3º tri só sai em dezembro); corrigido para 170 no próprio verificador, sem tocar em dados.
- 14/11 — "Mês em andamento" = ponto de série diária cujo mês é o mesmo de `extraido_em` (as duas datas vêm do JSON; nenhum valor é calculado).
- 14/11 — `url_licenca` vazio significa "sem página oficial de licença confirmada": o painel mostra o texto sem link e o rodapé usa "Uso dos dados:" em vez de "Licença:".
- 14/11 — Verificador: valores conferidos por outro endereço da API (SGS por janela curta do período; SIDRA pelo código do período; Ipeadata por `Metadados('código')/Valores`). Nome diferente do oficial é só aviso; unidade/periodicidade diferente ou código inexistente é erro.
- 14/11 — Teste de navegador feito com o Brave (flatpak) em modo sem janela, o único navegador instalado nesta máquina.
