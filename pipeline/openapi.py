"""Descrição OpenAPI 3.1 da API, gerada a partir das eleições configuradas e dos schemas.

Os modelos apontam para os JSON Schemas publicados em /v1/schema/, que são a
fonte única da estrutura de cada arquivo.
"""

from pipeline import schemas
from pipeline.fontes import ELEICOES, UFS

CAMINHO = "/v1/openapi.json"

_UFS = [uf.lower() for uf in UFS]
_COLUNAS_EVENTOS = (
    "`t` (entrada no placar), `recebido` (DT_BU_RECEBIDO do TSE), `uf`, `cd_municipio_tse`, "
    "`municipio`, `zona`, `secao`, `tipo_urna`, `aptos`, `comparecimento` e uma coluna "
    "`votos_<numero>` por candidato, mais `votos_branco` e `votos_nulo`."
)


def _param(nome: str, descricao: str, valores: list[str]) -> dict:
    return {
        "name": nome,
        "in": "path",
        "required": True,
        "description": descricao,
        "schema": {"type": "string", "enum": valores},
    }


def _json(modelo: str, descricao: str) -> dict:
    return {
        "200": {
            "description": descricao,
            "content": {"application/json": {"schema": {"$ref": f"#/components/schemas/{modelo}"}}},
        },
        "404": {"$ref": "#/components/responses/NaoEncontrado"},
    }


def _op(operation_id: str, resumo: str, parametros: list[str], respostas: dict, descricao: str = "") -> dict:
    op = {
        "operationId": operation_id,
        "summary": resumo,
        "parameters": [{"$ref": f"#/components/parameters/{p}"} for p in parametros],
        "responses": respostas,
    }
    if descricao:
        op["description"] = descricao
    return {"get": op}


def gerar() -> dict:
    base = "/v1/eleicoes/{eleicao}/{cargo}/br"
    uf = base + "/{uf}"
    desc_minuto = (
        "Placar acumulado a cada minuto, de 17:00 (início da divulgação) até o último boletim. "
        "O ponto em `t` inclui todas as seções que entraram no placar até `t`."
    )
    desc_pct = "Placar no instante em que o % de seções totalizadas atingiu cada marca (0 a 100, a cada `passo`)."

    return {
        "openapi": "3.1.0",
        "jsonSchemaDialect": "https://json-schema.org/draft/2020-12/schema",
        "info": {
            "title": "minuto-a-minuto",
            "version": "1.0.0",
            "summary": "Séries da apuração das eleições brasileiras, reconstruídas a partir dos boletins de urna do TSE.",
            "description": (
                "API estática (somente GET, arquivos JSON e CSV) com o placar da apuração ao longo da "
                "noite: minuto a minuto e por % de seções apuradas, para o Brasil e cada UF.\n\n"
                "Cada JSON traz `$schema` (o JSON Schema que o descreve), `_links` para navegar entre "
                "os recursos e `_proveniencia` com as fontes do TSE e seus SHA-512.\n\n"
                "Não é um serviço oficial do TSE. CORS liberado para qualquer origem."
            ),
            "license": {"name": "CC BY 4.0 (dados)", "identifier": "CC-BY-4.0"},
            "contact": {"name": "minuto-a-minuto", "url": "https://github.com/teles/minuto-a-minuto"},
        },
        "externalDocs": {
            "description": "Método, regras e limites",
            "url": "https://github.com/teles/minuto-a-minuto/blob/main/docs/metodo.md",
        },
        "servers": [{"url": schemas.URL_PUBLICA}],
        "paths": {
            "/v1/index.json": _op(
                "indice", "Ponto de entrada: eleições disponíveis e schemas", [],
                _json("Indice", "Índice da API"),
            ),
            "/v1/eleicoes/{eleicao}/index.json": _op(
                "eleicao", "Dados de uma eleição e seus candidatos", ["eleicao"],
                _json("Eleicao", "Eleição"),
            ),
            f"{base}/resumo.json": _op(
                "resumoBrasil", "Resultado final no Brasil", ["eleicao", "cargo"],
                _json("Resumo", "Resultado final"),
            ),
            f"{base}/serie-minuto.json": _op(
                "serieMinutoBrasil", "Placar do Brasil minuto a minuto", ["eleicao", "cargo"],
                _json("SerieMinuto", "Série por minuto"), desc_minuto,
            ),
            f"{base}/serie-pct.json": _op(
                "seriePctBrasil", "Placar do Brasil por % de seções apuradas", ["eleicao", "cargo"],
                _json("SeriePct", "Série por % apurado"), desc_pct,
            ),
            f"{uf}/resumo.json": _op(
                "resumoUf", "Resultado final de uma UF", ["eleicao", "cargo", "uf"],
                _json("Resumo", "Resultado final"),
            ),
            f"{uf}/serie-minuto.json": _op(
                "serieMinutoUf", "Placar de uma UF minuto a minuto", ["eleicao", "cargo", "uf"],
                _json("SerieMinuto", "Série por minuto"), desc_minuto,
            ),
            f"{uf}/serie-pct.json": _op(
                "seriePctUf", "Placar de uma UF por % de seções apuradas", ["eleicao", "cargo", "uf"],
                _json("SeriePct", "Série por % apurado"),
                desc_pct + " O % é o da própria UF.",
            ),
            f"{uf}/eventos.csv": _op(
                "eventosUf", "Uma linha por seção, na ordem em que entrou no placar", ["eleicao", "cargo", "uf"],
                {
                    "200": {
                        "description": "CSV (UTF-8, vírgula). Colunas: " + _COLUNAS_EVENTOS,
                        "content": {"text/csv": {"schema": {"type": "string"}}},
                    },
                    "404": {"$ref": "#/components/responses/NaoEncontrado"},
                },
            ),
            "/v1/schema/{nome}.schema.json": _op(
                "schema", "JSON Schema de um tipo de arquivo", ["nome"],
                {
                    "200": {
                        "description": "JSON Schema (draft 2020-12)",
                        "content": {"application/json": {"schema": {"type": "object"}}},
                    },
                    "404": {"$ref": "#/components/responses/NaoEncontrado"},
                },
            ),
        },
        "components": {
            "parameters": {
                "eleicao": _param("eleicao", "Eleição, no formato `<ano>-<turno>t`.", list(ELEICOES)),
                "cargo": _param("cargo", "Cargo.", sorted({e.cargo for e in ELEICOES.values()})),
                "uf": _param("uf", "Sigla da UF em minúsculas; `zz` é o exterior.", _UFS),
                "nome": _param("nome", "Tipo de arquivo.", list(schemas.SCHEMAS)),
            },
            "schemas": {
                "Indice": {"$ref": schemas.url_schema("indice")},
                "Eleicao": {"$ref": schemas.url_schema("eleicao")},
                "Resumo": {"$ref": schemas.url_schema("resumo")},
                "SerieMinuto": {"$ref": schemas.url_schema("serie-minuto")},
                "SeriePct": {"$ref": schemas.url_schema("serie-pct")},
            },
            "responses": {"NaoEncontrado": {"description": "Arquivo inexistente (combinação de parâmetros sem dados)."}},
        },
    }
