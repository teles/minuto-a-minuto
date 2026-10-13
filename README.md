# minuto-a-minuto

Séries da apuração das eleições brasileiras ao longo da noite, minuto a minuto e por % de seções apuradas, reconstruídas a partir dos boletins de urna publicados pelo TSE.

O TSE divulga o placar ao vivo, mas cada atualização substitui a anterior. Este projeto reconstrói o histórico e o publica como arquivos JSON estáticos, para qualquer pessoa usar.

> Não é um serviço oficial do TSE. Os dados vêm exclusivamente de arquivos públicos do TSE, e cada arquivo gerado aponta para as fontes usadas e seus hashes.

## Dados disponíveis

| Eleição | Cargo | Níveis |
|---|---|---|
| 2022, 2º turno | Presidente | Brasil, UFs e exterior |

## Estrutura

```
/v1/eleicoes/{eleicao}/index.json
/v1/eleicoes/{eleicao}/{cargo}/br/resumo.json        resultado final
/v1/eleicoes/{eleicao}/{cargo}/br/serie-minuto.json  placar acumulado a cada minuto
/v1/eleicoes/{eleicao}/{cargo}/br/serie-pct.json     placar a cada 0,5% de seções apuradas
/v1/eleicoes/{eleicao}/{cargo}/br/{uf}/...           o mesmo por UF (zz = exterior)
/v1/schema/*.schema.json                             JSON Schema de cada arquivo
```

Os arquivos ficam em [`dist/`](dist/). Cada um traz `_links` para navegar entre os recursos e `_proveniencia` com as URLs e os SHA-512 das fontes do TSE.

## Garantias

Os dados são gerados por código, nunca editados à mão, e só são aceitos se passarem na conciliação (`tests/`):

- resultado final de cada local **idêntico, voto a voto,** aos datasets oficiais `votacao_candidato_munzona` e `detalhe_votacao_munzona`;
- soma das UFs igual ao Brasil em todos os minutos;
- séries que nunca diminuem e com votos = comparecimento ≤ aptos;
- reconstrução conferida com o placar gravado ao vivo na noite da eleição;
- toda a saída válida contra o JSON Schema;
- build reproduzível: as mesmas fontes e o mesmo código geram os mesmos bytes.

Regras e limites do método: [`docs/metodo.md`](docs/metodo.md).

## Como gerar

```sh
uv run python -m pipeline.fetch 2022-2t   # baixa as fontes e confere os hashes
uv run python -m pipeline.build 2022-2t   # gera dist/
uv run pytest                             # conciliação
```
