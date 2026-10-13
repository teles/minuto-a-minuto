"""A descrição OpenAPI precisa ser válida e corresponder exatamente aos arquivos publicados."""

import itertools
import re
import socket

import pytest
from jsonschema_path import SchemaPath
from openapi_spec_validator import OpenAPIV31SpecValidator

from pipeline import openapi, schemas
from pipeline.build import gerar_indice, gerar_openapi, gerar_schemas
from tests.test_conciliacao_2022_2t import pytestmark  # noqa: F401

SPEC = openapi.gerar()


@pytest.fixture
def sem_rede(monkeypatch):
    def bloquear(*_):
        raise RuntimeError("o teste tentou acessar a rede")

    monkeypatch.setattr(socket.socket, "connect", bloquear)


def test_spec_valida_sem_rede(sem_rede):
    # $ref externos apontam para os schemas publicados; aqui resolvem para os gerados localmente.
    locais = {schemas.url_schema(n): s for n, s in schemas.SCHEMAS.items()}
    caminho = SchemaPath.from_dict(SPEC, handlers={"https": lambda uri: locais[uri]})
    OpenAPIV31SpecValidator(caminho).validate()


def _publicados(saida):
    return set(saida) | set(gerar_schemas()) | set(gerar_indice()) | set(gerar_openapi())


def _expandir(template: str, so_eleicoes: set[str]):
    nomes = re.findall(r"{(\w+)}", template)
    valores = []
    for nome in nomes:
        enum = SPEC["components"]["parameters"][nome]["schema"]["enum"]
        valores.append([v for v in enum if nome != "eleicao" or v in so_eleicoes])
    for combinacao in itertools.product(*valores):
        caminho = template
        for nome, valor in zip(nomes, combinacao):
            caminho = caminho.replace("{" + nome + "}", valor)
        yield caminho


def test_todo_caminho_documentado_existe(saida):
    publicados = _publicados(saida)
    for template in SPEC["paths"]:
        for caminho in _expandir(template, {"2022-2t"}):
            assert caminho in publicados, f"{template} → {caminho} não é gerado"


def test_todo_arquivo_publicado_esta_documentado(saida):
    padroes = [
        re.compile("^" + "[^/]+".join(re.escape(parte) for parte in re.split(r"{\w+}", t)) + "$")
        for t in SPEC["paths"]
    ]
    fora_da_api = {openapi.CAMINHO, "/docs/index.html"}  # a própria descrição e a página que a exibe
    for caminho in _publicados(saida) - fora_da_api:
        assert any(p.match(caminho) for p in padroes), f"{caminho} não está na descrição OpenAPI"
