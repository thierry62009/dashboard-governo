# dashboard-governo

Dashboard autoatualizável do governo federal: indicadores oficiais desde 01/01/2023.

## Como funciona
1. `scripts/coletar.py` baixa os indicadores das APIs oficiais (Banco Central, IBGE e Ipeadata)
   e grava um arquivo por indicador em `data/`.
2. `index.html` é a página. O visual está em `assets/estilo.css`; `assets/painel.js`
   lê os JSON de `data/` e monta os cartões; `assets/grafico.js` desenha os gráficos
   em SVG, sem bibliotecas. `data/mandatos.json` (editado à mão) define os mandatos.
3. `.github/workflows/atualizar.yml` roda o script todo dia às 09:00 (Brasília),
   faz commit dos JSON e publica o site (`index.html`, `assets/` e `data/`) no GitHub Pages.

## Rodar no seu computador
```
python3 scripts/coletar.py           # atualiza os data/*.json
python3 -m http.server 8000          # depois abra http://localhost:8000
```
Abrir o `index.html` direto (duplo clique) não funciona: o navegador bloqueia a leitura do JSON fora de um servidor.

## Fontes e licença dos dados
Cada número da página mostra a série ou tabela, a data de extração, o link e a licença.
- Banco Central do Brasil, SGS (https://www3.bcb.gov.br/sgspub/ e https://dadosabertos.bcb.gov.br/):
  licença ODbL (Open Database License), que exige citação da fonte.
- IBGE, SIDRA (https://sidra.ibge.gov.br/): uso com citação da fonte.
- Ipeadata (http://www.ipeadata.gov.br/): uso público com citação da fonte.
