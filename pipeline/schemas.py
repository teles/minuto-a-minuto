"""JSON Schema (draft 2020-12) dos arquivos da API v1.

Fonte única dos schemas: o build os publica em /v1/schema/ e os testes validam
toda a saída contra eles.
"""

URL_BASE = "/v1/schema"

_INT = {"type": "integer", "minimum": 0}
_HREF = {
    "type": "object",
    "required": ["href"],
    "properties": {"href": {"type": "string"}, "name": {"type": "string"}},
    "additionalProperties": False,
}

DEFS = {
    "eleicao": {
        "type": "object",
        "required": ["id", "ano", "turno", "data", "cargo", "cd_eleicao_tse", "inicio_divulgacao"],
        "properties": {
            "id": {"type": "string", "pattern": "^[0-9]{4}-[12]t$"},
            "ano": {"type": "integer"},
            "turno": {"enum": [1, 2]},
            "data": {"type": "string", "format": "date"},
            "cargo": {"type": "string"},
            "cd_eleicao_tse": {"type": "string"},
            "inicio_divulgacao": {
                "type": "string",
                "format": "date-time",
                "description": "Instante em que o TSE começa a divulgar resultados; origem de seg_desde_inicio.",
            },
        },
        "additionalProperties": False,
    },
    "local": {
        "type": "object",
        "required": ["nivel", "sigla", "nome"],
        "properties": {
            "nivel": {"enum": ["br", "uf"]},
            "sigla": {"type": "string"},
            "nome": {"type": "string"},
        },
        "additionalProperties": False,
    },
    "candidatos": {
        "type": "array",
        "items": {
            "type": "object",
            "required": ["numero", "nome_urna", "partido"],
            "properties": {
                "numero": {"type": "string"},
                "nome_urna": {"type": "string"},
                "partido": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
    "placar": {
        "type": "object",
        "description": "Placar acumulado até o instante t (inclusive).",
        "required": ["t", "seg_desde_inicio", "secoes", "pct_secoes", "aptos", "comparecimento", "votos"],
        "properties": {
            "t": {"type": "string", "format": "date-time", "description": "Horário de Brasília."},
            "seg_desde_inicio": {
                "type": "integer",
                "minimum": 0,
                "description": "Segundos desde eleicao.inicio_divulgacao; eixo para comparar eleições pelo tempo decorrido.",
            },
            "secoes": {**_INT, "description": "Seções instaladas já totalizadas."},
            "pct_secoes": {
                "type": "number",
                "minimum": 0,
                "maximum": 100,
                "description": "secoes / total de seções instaladas × 100, arredondado em 4 casas. Calcule a partir dos inteiros se precisar de exatidão.",
            },
            "aptos": _INT,
            "comparecimento": _INT,
            "votos": {
                "type": "object",
                "description": "Votos por número de candidato, mais 'branco' e 'nulo'.",
                "required": ["branco", "nulo"],
                "propertyNames": {"pattern": "^([0-9]+|branco|nulo)$"},
                "additionalProperties": _INT,
            },
        },
        # sem additionalProperties aqui: a série por % acrescenta "p" ao placar.
        # Quem usa o placar fecha o objeto com unevaluatedProperties.
    },
    "links": {
        "type": "object",
        "required": ["self"],
        "additionalProperties": {
            "oneOf": [_HREF, {"type": "array", "items": _HREF}],
        },
    },
    "proveniencia": {
        "type": "object",
        "required": ["fontes", "gerado_por", "licenca"],
        "properties": {
            "licenca": {
                "type": "object",
                "required": ["id", "url", "atribuicao"],
                "properties": {
                    "id": {"const": "CC-BY-4.0"},
                    "url": {"type": "string"},
                    "atribuicao": {"type": "string"},
                },
                "additionalProperties": False,
            },
            "fontes": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "required": ["url", "sha512"],
                    "properties": {
                        "url": {"type": "string"},
                        "sha512": {"type": "string", "pattern": "^[0-9a-f]{128}$"},
                    },
                    "additionalProperties": False,
                },
            },
            "gerado_por": {
                "type": "object",
                "required": ["repositorio", "commit"],
                "properties": {
                    "repositorio": {"type": "string"},
                    "commit": {
                        "type": ["string", "null"],
                        "description": "Último commit que alterou o código do pipeline; null se gerado com código não commitado.",
                    },
                },
                "additionalProperties": False,
            },
        },
        "additionalProperties": False,
    },
}


def _schema(nome: str, propriedades: dict, obrigatorias: list[str]) -> dict:
    props = {"schema": {"const": f"minuto-a-minuto/v1/{nome}"}, **propriedades}
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"{URL_BASE}/{nome}.schema.json",
        "title": f"minuto-a-minuto v1: {nome}",
        "type": "object",
        "required": ["schema", *obrigatorias],
        "properties": props,
        "additionalProperties": False,
        "$defs": DEFS,
    }


_COMUM = {
    "eleicao": {"$ref": "#/$defs/eleicao"},
    "local": {"$ref": "#/$defs/local"},
    "candidatos": {"$ref": "#/$defs/candidatos"},
    "_links": {"$ref": "#/$defs/links"},
    "_proveniencia": {"$ref": "#/$defs/proveniencia"},
}
_OBRIG_COMUM = ["eleicao", "local", "candidatos", "_links", "_proveniencia"]
_PLACAR = {"$ref": "#/$defs/placar", "unevaluatedProperties": False}

SCHEMAS = {
    "resumo": _schema(
        "resumo", {**_COMUM, "resultado": _PLACAR}, [*_OBRIG_COMUM, "resultado"]
    ),
    "serie-minuto": _schema(
        "serie-minuto",
        {**_COMUM, "pontos": {"type": "array", "minItems": 1, "items": _PLACAR}},
        [*_OBRIG_COMUM, "pontos"],
    ),
    "serie-pct": _schema(
        "serie-pct",
        {
            **_COMUM,
            "passo": {"type": "number", "exclusiveMinimum": 0},
            "pontos": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "allOf": [{"$ref": "#/$defs/placar"}],
                    "properties": {"p": {"type": "number", "minimum": 0, "maximum": 100}},
                    "required": ["p"],
                    "unevaluatedProperties": False,
                },
            },
        },
        [*_OBRIG_COMUM, "passo", "pontos"],
    ),
    "indice": _schema(
        "indice",
        {
            "eleicoes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["id", "cargos", "href"],
                    "properties": {
                        "id": {"type": "string"},
                        "cargos": {"type": "array", "items": {"type": "string"}},
                        "href": {"type": "string"},
                    },
                    "additionalProperties": False,
                },
            },
            "_links": {"$ref": "#/$defs/links"},
        },
        ["eleicoes", "_links"],
    ),
    "eleicao": _schema(
        "eleicao",
        {
            "eleicao": {"$ref": "#/$defs/eleicao"},
            "candidatos": {"$ref": "#/$defs/candidatos"},
            "_links": {"$ref": "#/$defs/links"},
        },
        ["eleicao", "candidatos", "_links"],
    ),
}
