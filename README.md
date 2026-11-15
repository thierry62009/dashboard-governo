# dashboard-governo

Dashboard autoatualizável do governo federal: indicadores oficiais desde 01/01/2023.

## Como funciona
1. `scripts/coletar.py` baixa os indicadores das APIs oficiais (Banco Central, IBGE e Ipeadata)
   e grava um arquivo por indicador em `data/`.
2. `index.html` é a página. O visual está em `assets/estilo.css` (as fontes Archivo e Manrope
   ficam em `assets/fontes/`, com licença SIL Open Font License); `assets/painel.js`
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

## Fontes dos dados
Cada número da página mostra a série ou tabela, a data de extração, o link da fonte e a licença ou o texto de citação.
- Banco Central do Brasil, SGS (https://dadosabertos.bcb.gov.br/).
- IBGE, SIDRA (https://sidra.ibge.gov.br/).
- Ipeadata (http://www.ipeadata.gov.br/).

## Licença dos dados
- **Séries do Banco Central (BCB/SGS):** os dados do BCB são publicados sob a
  [ODbL (Open Database License)](https://opendatacommons.org/licenses/odbl/). Os arquivos
  `data/*.json` gerados a partir dessas séries são uma base derivada e seguem a mesma ODbL:
  quem reutilizar deve atribuir a fonte ao Banco Central do Brasil e manter a base derivada
  sob a mesma licença.
- **Tabelas do IBGE (SIDRA):** não há licença formal confirmada para esses dados. Os arquivos
  trazem a fonte citada ("Dados do IBGE (SIDRA); fonte citada conforme orientação do IBGE"),
  sem afirmar licença.
- **Séries do Ipeadata:** os arquivos trazem a fonte citada. A página
  [Direitos de Uso do Ipeadata](http://www.ipeadata.gov.br/iframe_direitouso.aspx) diz que o
  conteúdo é informação pública que pode ser distribuída e copiada, com citação da fonte Ipeadata.
- **Código do projeto** (`scripts/`, `assets/`, `index.html`, `.github/`): licença a definir.
