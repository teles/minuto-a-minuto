# Método

O TSE publica o placar da apuração ao vivo, mas não guarda o histórico: cada atualização substitui a anterior. O minuto-a-minuto reconstrói esse histórico a partir dos **boletins de urna** (`bweb_*.zip`), que registram, para cada seção, os votos e o horário em que o boletim foi recebido (`DT_BU_RECEBIDO`).

## Regras

1. **Fontes verificadas.** Os boletins são conferidos contra o `.sha512` publicado pelo TSE. Todo arquivo de fonte tem o hash registrado em `manifestos/<eleicao>.json`; se o TSE regerar um arquivo, o pipeline para.
   - **Extrato.** Do boletim original é gravado um extrato com as linhas do cargo e as colunas usadas (CSV gzip, UTF-8, bytes determinísticos). O build lê o extrato; o manifesto registra o hash do original e o do extrato. Em 2022, o build a partir dos extratos gera exatamente os mesmos arquivos que a partir dos originais.
   - **Formato.** O TSE mudou o boletim entre 2022 e 2026: números sem aspas, `DT_BU_RECEBIDO` em `AAAA-MM-DD HH:MM:SS` (antes `DD/MM/AAAA HH:MM:SS`), `DS_AGREGADAS` renomeada para `DS_SECOES_AGREGADAS` (o extrato usa `DS_AGREGADAS`) e `DS_TIPO_URNA` em caixa mista (`Apurada`, antes `APURADA`; mantido como o TSE publica).
2. **Horário.** `DT_BU_RECEBIDO` está no horário de Brasília em todas as UFs (verificado em 2022 e 2026: os primeiros boletins do AC e do AM chegam depois das 17h de Brasília, como os demais).
3. **Início da divulgação.** Boletins recebidos antes do início da divulgação (17h de Brasília; casos do exterior) entram no placar às 17h. Em 2022, 2º turno: 573 seções.
4. **Ordem.** Seções recebidas no mesmo segundo são ordenadas por (UF, município, zona, seção).
5. **Seções.** O denominador do `pct_secoes` são as seções **instaladas** (as que têm boletim). O TSE usa as seções principais, incluindo as não instaladas, que não têm boletim nem horário. Em 2022, 2º turno, foram 47 de 472.075 (diferença máxima de 0,01 p.p.). As seções agregadas vêm dentro do boletim da seção principal.
6. **Divergências do boletim em relação ao resultado oficial**, configuradas explicitamente por eleição (`pipeline/fontes.py`) e conferidas pelos testes:
   - **Nulos técnicos:** candidato que está na urna mas não no resultado oficial. O TSE conta os votos nele como nulos (`QT_VOTOS_NULOS_TECNICOS`); aqui eles são somados a `nulo` e o candidato não aparece na lista. 2026, 1º turno: nº 28 (LEONARDO AVALANCHE, PRTB), 5.246 votos.
   - **Seção sem boletim:** seção instalada segundo o `detalhe_votacao_munzona`, mas sem nenhuma linha no boletim publicado. Não entra nas séries nem no total de seções. 2026, 1º turno: CIUDAD GUAYANA (Venezuela), 1 seção, 72 aptos, comparecimento 0.
7. **Série por minuto.** O ponto em T inclui todas as seções que entraram até T, de 17:00 até o minuto do último boletim.
8. **Eventos.** `eventos.csv` (por UF) traz uma linha por seção com `recebido` (o `DT_BU_RECEBIDO` do TSE) e `t` (quando entrou no placar, regra 3). As séries são agregações desses eventos.
9. **Série por % apurado.** O ponto p (de 0 a 100, a cada 0,5) é o placar no instante em que o % de seções atingiu p pela primeira vez.

## Diferença em relação ao placar exibido pelo TSE

O placar do TSE mostrava cada seção alguns segundos depois do recebimento do boletim. No 2º turno de 2022, comparando com a série gravada ao vivo por [wcota/br_eleicoes_2022_2T](https://github.com/wcota/br_eleicoes_2022_2T):

- atraso mediano de 22 s (90% até 35 s, máximo 64 s);
- diferença mediana de 0,003 p.p. no % de Lula entre os dois candidatos; a partir de 1% apurado, no máximo 0,75 p.p.

No 1º turno de 2026, comparando com a série gravada por [ntwkst/apuracao-monitor](https://github.com/ntwkst/apuracao-monitor) (que começa às 17:57, com 10,9% apurado):

- alinhando pelo % de seções que a própria gravação registra, a diferença no % dos válidos de Lula e de Flávio Bolsonaro tem mediana de 0,003 p.p. e máximo de 0,089 p.p.;
- alinhar pelo horário não serve para essa gravação: algumas leituras estão defasadas (às 19:14:08 ela registra 64,81% apurado, quando os boletins já somavam 74,5%).

## Conciliação

O build só é aceito se, para o Brasil e para cada UF (incluindo o exterior, `ZZ`):

- os votos de cada candidato, brancos, nulos e o comparecimento forem **idênticos** aos de `votacao_candidato_munzona` e `detalhe_votacao_munzona` (datasets do TSE independentes do boletim);
- os aptos forem idênticos aos oficiais menos os eleitores das seções não instaladas;
- a soma das UFs for igual ao Brasil em todos os minutos;
- as séries nunca diminuírem e respeitarem votos = comparecimento ≤ aptos.

Ver `tests/`.
