# minuto-a-minuto

Séries da apuração das eleições brasileiras ao longo da noite, minuto a minuto e por % de seções apuradas, reconstruídas a partir dos boletins de urna publicados pelo TSE.

O TSE divulga o placar ao vivo, mas cada atualização substitui a anterior. Este projeto reconstrói o histórico e o publica como arquivos JSON estáticos, para qualquer pessoa usar.

**API:** https://minutoaminuto.pages.dev/v1/index.json · **Documentação:** https://minutoaminuto.pages.dev/docs/ · **OpenAPI:** https://minutoaminuto.pages.dev/v1/openapi.json

> Não é um serviço oficial do TSE. Os dados vêm exclusivamente de arquivos públicos do TSE, e cada arquivo gerado aponta para as fontes usadas e seus hashes.

## Dados disponíveis

| Eleição | Cargo | Níveis |
|---|---|---|
| 2022, 2º turno | Presidente | Brasil, UFs e exterior |

## Estrutura

```
/v1/index.json                                       ponto de entrada: eleições e schemas
/v1/eleicoes/{eleicao}/index.json
/v1/eleicoes/{eleicao}/{cargo}/br/resumo.json        resultado final
/v1/eleicoes/{eleicao}/{cargo}/br/serie-minuto.json  placar acumulado a cada minuto
/v1/eleicoes/{eleicao}/{cargo}/br/serie-pct.json     placar a cada 0,5% de seções apuradas
/v1/eleicoes/{eleicao}/{cargo}/br/{uf}/...           o mesmo por UF (zz = exterior)
/v1/eleicoes/{eleicao}/{cargo}/br/{uf}/eventos.csv   uma linha por seção, na ordem em que entrou no placar
/v1/schema/*.schema.json                             JSON Schema de cada arquivo
/v1/openapi.json                                     descrição OpenAPI 3.1
```

Os arquivos ficam em [`dist/`](dist/). Cada JSON indica em `$schema` a URL do JSON Schema que o descreve, e traz `_links` para navegar entre os recursos e `_proveniencia` com as URLs e os SHA-512 das fontes do TSE.

## Garantias

Os dados são gerados por código, nunca editados à mão, e só são aceitos se passarem na conciliação (`tests/`):

- resultado final de cada local **idêntico, voto a voto,** aos datasets oficiais `votacao_candidato_munzona` e `detalhe_votacao_munzona`;
- soma das UFs igual ao Brasil em todos os minutos;
- séries que nunca diminuem e com votos = comparecimento ≤ aptos;
- os eventos por seção reagregados reproduzem exatamente as séries;
- reconstrução conferida com o placar gravado ao vivo na noite da eleição;
- toda a saída válida contra o JSON Schema;
- descrição OpenAPI válida e com correspondência exata aos arquivos publicados (todo caminho documentado existe e todo arquivo está documentado);
- build reproduzível: as mesmas fontes e o mesmo código geram os mesmos bytes.

Regras e limites do método: [`docs/metodo.md`](docs/metodo.md).

## Fontes e verificação contínua

- Uma cópia exata das fontes usadas fica nas releases `fontes-<eleicao>` deste repositório. O build continua reproduzível mesmo que o TSE altere ou remova os arquivos originais.
- Em cada push, a CI baixa essa cópia, confere os SHA-512 com o manifesto, roda a conciliação e confirma que o `dist/` commitado é exatamente a saída do build.
- A API publicada é a branch `publicado`. A CI só avança essa branch até um commit do `main` depois que a conciliação e a reprodutibilidade passam nele; a Cloudflare publica a partir dela.
- Diariamente, um workflow verifica se as fontes mudaram no TSE (hash publicado, ETag, data de modificação e boletins novos no portal) e abre uma issue se algo mudou.

## Como gerar

```sh
uv run python -m pipeline.fetch 2022-2t             # baixa do TSE e confere os hashes
uv run python -m pipeline.fetch 2022-2t --arquivo   # ou: baixa a cópia arquivada
uv run python -m pipeline.build 2022-2t             # gera dist/
uv run pytest                                       # conciliação
```

## Licença

Código sob [MIT](LICENSE). Dados sob [CC BY 4.0](LICENSE-DADOS.md), com atribuição ao minuto-a-minuto e ao TSE.
