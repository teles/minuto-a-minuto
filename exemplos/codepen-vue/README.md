# Exemplo: Vue 3 + Tailwind no CodePen

Reveja a noite do 2º turno de 2022 arrastando a linha do tempo, por horário ou por % de seções apuradas, para o Brasil ou qualquer UF.

Para montar o pen:

1. Crie um pen novo em https://codepen.io/pen/.
2. Cole o conteúdo de [`pen.html`](pen.html) no painel **HTML**. Ele já carrega Vue 3 e Tailwind por CDN.
3. Cole o conteúdo de [`pen.js`](pen.js) no painel **JS**.

Nenhuma configuração extra é necessária: a API libera CORS para qualquer origem.

O exemplo usa:

- `serie-minuto.json` e `serie-pct.json` do local escolhido;
- os `_links.filhos` do resumo do Brasil para montar a lista de UFs.
