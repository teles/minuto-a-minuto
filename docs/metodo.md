# Método

O TSE publica o placar da apuração ao vivo, mas não guarda o histórico: cada atualização substitui a anterior. O minuto-a-minuto reconstrói esse histórico a partir dos **boletins de urna** (`bweb_*.zip`), que registram, para cada seção, os votos e o horário em que o boletim foi recebido (`DT_BU_RECEBIDO`).

## Regras

1. **Fontes verificadas.** Os boletins são conferidos contra o `.sha512` publicado pelo TSE. Todo arquivo de fonte tem o hash registrado em `manifestos/<eleicao>.json`; se o TSE regerar um arquivo, o pipeline para.
2. **Horário.** `DT_BU_RECEBIDO` está no horário de Brasília em todas as UFs (verificado: os primeiros boletins do AC e do AM chegam às 17h de Brasília, como os demais).
3. **Início da divulgação.** Boletins recebidos antes do início da divulgação (17h de Brasília; casos do exterior) entram no placar às 17h. Em 2022, 2º turno: 573 seções.
4. **Ordem.** Seções recebidas no mesmo segundo são ordenadas por (UF, município, zona, seção).
5. **Seções.** O denominador do `pct_secoes` são as seções **instaladas** (as que têm boletim). O TSE usa as seções principais, incluindo as não instaladas, que não têm boletim nem horário. Em 2022, 2º turno, foram 47 de 472.075 (diferença máxima de 0,01 p.p.). As seções agregadas vêm dentro do boletim da seção principal.
6. **Série por minuto.** O ponto em T inclui todas as seções que entraram até T, de 17:00 até o minuto do último boletim.
7. **Série por % apurado.** O ponto p (de 0 a 100, a cada 0,5) é o placar no instante em que o % de seções atingiu p pela primeira vez.

## Diferença em relação ao placar exibido pelo TSE

O placar do TSE mostrava cada seção alguns segundos depois do recebimento do boletim. No 2º turno de 2022, comparando com a série gravada ao vivo por [wcota/br_eleicoes_2022_2T](https://github.com/wcota/br_eleicoes_2022_2T):

- atraso mediano de 22 s (90% até 35 s, máximo 64 s);
- diferença mediana de 0,003 p.p. no % de Lula entre os dois candidatos; a partir de 1% apurado, no máximo 0,75 p.p.

## Conciliação

O build só é aceito se, para o Brasil e para cada UF (incluindo o exterior, `ZZ`):

- os votos de cada candidato, brancos, nulos e o comparecimento forem **idênticos** aos de `votacao_candidato_munzona` e `detalhe_votacao_munzona` (datasets do TSE independentes do boletim);
- os aptos forem idênticos aos oficiais menos os eleitores das seções não instaladas;
- a soma das UFs for igual ao Brasil em todos os minutos;
- as séries nunca diminuírem e respeitarem votos = comparecimento ≤ aptos.

Ver `tests/`.
