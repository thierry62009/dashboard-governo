# STATUS — Painel do Governo Federal

> Atualize este arquivo ao fim de cada sessão. As regras ficam no `CLAUDE.md`.

## Pronto
- Coleta do IPCA, série SGS 433. Conferido no portal pelo usuário: "Índice nacional de preços ao consumidor-amplo (IPCA)", Var. % mensal, origem IBGE.
- Página com o visual aprovado, publicada e testada no Chromium em 360, 768 e 1440 px.
- Rotina diária no GitHub Actions funcionando nas execuções por push. O robô faz commit a cada execução.

## Roteiro de fases
Cada fase termina com testes, commit, push (regra 8 do `CLAUDE.md`) e este arquivo atualizado.

- **Fase 3a — Mandatos (fazer primeiro).** Criar `data/mandatos.json` (ver "Decisões já tomadas" no `CLAUDE.md`), publicá-lo no `_site`, e fazer a página filtrar os indicadores pelo intervalo do mandato. Com um só mandato "em andamento", a página fica como está hoje; o 4º mandato aparece como "Em breve" até janeiro de 2027.
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
- [ ] (Novos itens entram aqui, com link: códigos de série para conferir, veículos de notícia escolhidos e por quê.)

## Decisões registradas pelo Claude Code
(Uma linha por decisão, com o motivo. Vazio por enquanto.)
