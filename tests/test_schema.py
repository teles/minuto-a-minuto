"""Toda a saída do build precisa validar contra os JSON Schemas publicados."""

import jsonschema
import pytest

from pipeline import schemas
from pipeline.build import formatar, gerar_indice, gerar_schemas
from tests.test_conciliacao_2022_2t import pytestmark  # noqa: F401

VALIDADORES = {
    f"minuto-a-minuto/v1/{nome}": jsonschema.Draft202012Validator(
        s, format_checker=jsonschema.Draft202012Validator.FORMAT_CHECKER
    )
    for nome, s in schemas.SCHEMAS.items()
}


def test_schemas_sao_validos():
    for s in schemas.SCHEMAS.values():
        jsonschema.Draft202012Validator.check_schema(s)


def test_toda_saida_valida_contra_o_schema(saida):
    for caminho, obj in saida.items():
        if isinstance(obj, str):  # CSV de eventos
            continue
        erros = list(VALIDADORES[obj["schema"]].iter_errors(obj))
        assert not erros, f"{caminho}: {erros[0].message} em {list(erros[0].absolute_path)}"


def test_indice_valida_e_aponta_para_arquivos_gerados(saida):
    indice = gerar_indice()["/v1/index.json"]
    VALIDADORES[indice["schema"]].validate(indice)
    assert "/v1/eleicoes/2022-2t/index.json" in {e["href"] for e in indice["eleicoes"]}
    assert "/v1/eleicoes/2022-2t/index.json" in saida
    assert {s["href"] for s in indice["_links"]["schemas"]} == set(gerar_schemas())


def test_links_internos_apontam_para_arquivos_gerados(saida):
    publicados = set(saida) | set(gerar_schemas()) | set(gerar_indice())
    for caminho, obj in saida.items():
        if isinstance(obj, str):
            continue
        for nome, alvo in obj["_links"].items():
            for link in alvo if isinstance(alvo, list) else [alvo]:
                if link["href"].startswith("/"):
                    assert link["href"] in publicados, f"{caminho}: link {nome} quebrado"


def test_schema_rejeita_campo_desconhecido(saida):
    obj = saida["/v1/eleicoes/2022-2t/presidente/br/resumo.json"]
    adulterado = {**obj, "resultado": {**obj["resultado"], "extra": 1}}
    with pytest.raises(jsonschema.ValidationError):
        VALIDADORES[obj["schema"]].validate(adulterado)


def test_formatacao_preserva_o_conteudo(saida):
    import json

    jsons = [o for o in saida.values() if isinstance(o, dict)]
    for obj in jsons + list(gerar_schemas().values()):
        assert json.loads(formatar(obj)) == obj
