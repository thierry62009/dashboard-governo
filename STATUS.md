# STATUS — Painel do Governo Federal

> Atualize este arquivo ao fim de cada sessão. As regras ficam no `CLAUDE.md`.

## Pronto
- Coleta do IPCA, série SGS 433. Conferido no portal pelo usuário: "Índice nacional de preços ao consumidor-amplo (IPCA)", Var. % mensal, origem IBGE.
- Página com o visual aprovado, publicada e testada no Chromium em 360, 768 e 1440 px.
- Rotina diária no GitHub Actions funcionando nas execuções por push. O robô faz commit a cada execução.
- **Fase 3a — Mandatos (14/11/2026).** `data/mandatos.json` criado e publicado junto com `data/`. A página lê o arquivo, mostra os botões de mandato (o 4º aparece desligado, "Em breve") e filtra indicadores e destaques pelo mandato escolhido. Os indicadores passaram a ser agrupados por área. Testado no Brave sem janela em 360, 768 e 1440 px (sem rolagem lateral, botões com 44 px) e com falha provocada (sem `mandatos.json` a página avisa e mostra os dados sem filtro).

## Roteiro de fases
Cada fase termina com testes, commit, push (regra 8 do `CLAUDE.md`) e este arquivo atualizado.

- ~~Fase 3a — Mandatos~~ **concluída em 14/11/2026** (ver "Pronto"). Texto original: Criar `data/mandatos.json` (ver "Decisões já tomadas" no `CLAUDE.md`), publicá-lo no `_site`, e fazer a página filtrar os indicadores pelo intervalo do mandato. Com um só mandato "em andamento", a página fica como está hoje; o 4º mandato aparece como "Em breve" até janeiro de 2027.
- **Fase 3 — Indicadores de economia.** Um de cada vez, na ordem: Selic, dólar, desocupação (PNAD Contínua), PIB, renda média. Cada um segue a regra 2 (testar na API e confirmar por fonte oficial independente; sem isso, fica "Em breve").
- **Fase 3b — Outras áreas** (o usuário pediu estas áreas): contas públicas (por exemplo dívida pública e resultado primário), emprego formal (saldo de vagas), e 2 a 3 indicadores de saúde, educação e segurança com fonte oficial aberta e atualização regular. Se uma área não tiver fonte confiável, registre o motivo aqui e siga adiante. Não invente códigos: pesquise e teste.
- **Fase 4 — Notícias:** RSS da Agência Brasil e do Planalto, mais 2 ou 3 veículos privados de linhas diferentes (checar o RSS e os termos de uso de cada um). Selo "Oficial" ou "Imprensa". Só título, veículo, data e link. Atualização diária.
- **Fase 5 — Resumo do período:** fatos com fonte em cada afirmação, escrito e revisado **com o usuário**, nunca gerado automaticamente. Esta fase não é autônoma: o Claude Code pode no máximo preparar a lista de fatos candidatos com fonte, para o usuário aprovar.
- **Fase 6 — Comparação entre mandatos e presidentes (futura):** seletor para alternar e comparar mandatos de vários presidentes, com as mesmas métricas e a mesma janela de tempo. Exige estender a coleta para antes de 2023 (atenção ao limite de 10 anos das séries diárias do SGS). Começar só depois da Fase 3 completa.

## Pendências abertas (A conferir — só o usuário pode fazer)
- [ ] **Teste de 7 dias da rotina agendada (de 11/11 a 17/11/2026).** 1ª execução por `schedule`: 11/11, iniciou 19:29 UTC (atraso de ~7h30 do GitHub em relação às 12:00), sucesso. Confira em https://github.com/thierry62009/dashboard-governo/actions
- [ ] Texto de citação exigido pelo BCB para a ODbL: https://dadosabertos.bcb.gov.br/
- [ ] Comparar valores do gráfico com o SGS (fev/2025 = 1,31; ago/2026 = −0,32): https://www3.bcb.gov.br/sgspub/
- [ ] O usuário deve conferir se o título e a frase de apoio da abertura estão neutros.
- [ ] O usuário deve ver o visual no próprio celular.
- [ ] Confirmar no próximo commit do robô que a mensagem sai no horário de Brasília (formato "Dados atualizados em dd/mm/aaaa às hh:mm (Brasília)", alterado em 11/11).
- [ ] Atenção: o `ubuntu-latest` está migrando para o Ubuntu 26. Se o passo "Instalar Python" falhar, ajuste a versão do Python no workflow.
- [ ] **Data de início do 4º mandato em `data/mandatos.json`: 05/01/2027.** Usei a Emenda Constitucional 111/2021 (posse do presidente em 5 de janeiro a partir de 2027). Confira o art. 82 em https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc111.htm — se estiver diferente, mude só o campo `inicio`.
- [ ] Em janeiro de 2027, edite `data/mandatos.json`: no 3º mandato, ponha `fim` (último dia) e `status: "encerrado"`; no 4º, `status: "em_andamento"`.

## Decisões registradas pelo Claude Code
(Uma linha por decisão, com o motivo.)
- 14/11 — Mês de transição entre mandatos: o mês conta para quem estava em exercício no dia 15 (dados são mensais; evita o mesmo mês em dois mandatos).
- 14/11 — `mandatos.json` ganhou o campo extra `nome_curto` (texto do botão) e `_como_editar` (instruções); o 3º mandato fica com `fim: null` enquanto está em andamento.
- 14/11 — Botões "12 meses" e "6 meses" passaram a contar meses do calendário a partir do dado mais recente (antes contavam pontos), para valer igual em séries mensais, trimestrais e anuais.
- 14/11 — Teste de navegador feito com o Brave (flatpak) em modo sem janela, o único navegador instalado nesta máquina.
