# Exemplo: Vue 3 + Tailwind no CodePen

Reveja a noite da apuração arrastando a linha do tempo, por horário ou por % de seções apuradas, para o Brasil ou qualquer UF, no 2º turno de 2022 ou no 1º turno de 2026.

- o primeiro colocado no instante escolhido fica sempre à esquerda;
- o gráfico mostra o % dos válidos de qualquer candidato (botões acima dele);
- barras de progresso mostram quanto cada região já tinha apurado naquele minuto.

Para montar o pen:

1. Crie um pen novo em https://codepen.io/pen/.
2. Cole o conteúdo de [`pen.html`](pen.html) no painel **HTML**. Ele já carrega Vue 3 e Tailwind por CDN.
3. Cole o conteúdo de [`pen.js`](pen.js) no painel **JS**.

Nenhuma configuração extra é necessária: a API libera CORS para qualquer origem.

O exemplo usa:

- `/v1/index.json` para listar as eleições;
- `serie-minuto.json` e `serie-pct.json` do local escolhido;
- os `_links.filhos` do resumo do Brasil para listar as UFs;
- a `serie-minuto.json` de cada UF para calcular o progresso por região (soma das seções apuradas das UFs da região até aquele minuto).
