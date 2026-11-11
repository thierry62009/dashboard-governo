# dashboard-governo

Dashboard autoatualizável do governo federal: indicadores oficiais desde 01/01/2023.

## Como funciona
1. `scripts/coletar_ipca.py` baixa o IPCA da API do Banco Central e grava `data/ipca.json`.
2. `index.html` é a página. O visual está em `assets/estilo.css`; `assets/painel.js`
   lê os JSON de `data/` e monta os cartões; `assets/grafico.js` desenha os gráficos
   em SVG, sem bibliotecas.
3. `.github/workflows/atualizar.yml` roda o script todo dia às 09:00 (Brasília),
   faz commit do JSON e publica o site (`index.html`, `assets/` e `data/`) no GitHub Pages.

## Rodar no seu computador
```
python3 scripts/coletar_ipca.py      # atualiza data/ipca.json
python3 -m http.server 8000          # depois abra http://localhost:8000
```
Abrir o `index.html` direto (duplo clique) não funciona: o navegador bloqueia a leitura do JSON fora de um servidor.

## Fontes e licença dos dados
- IPCA (variação % mensal), série SGS 433. Origem: IBGE. Fonte: Banco Central do Brasil,
  Sistema Gerenciador de Séries Temporais (https://www3.bcb.gov.br/sgspub/).
  Dados disponibilizados sob a licença ODbL (Open Database License).
