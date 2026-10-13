"""Auxiliares compartilhados pelos testes."""

from pipeline.build import PREFIXO
from pipeline.fetch import RAW, usado_no_build
from pipeline.fontes import Eleicao

FUSO = "-03:00"


def base(eleicao: Eleicao) -> str:
    return f"{PREFIXO}/{eleicao.id}/{eleicao.cargo}/br"


def locais(saida: dict, eleicao: Eleicao):
    """(sigla, caminho_base) do Brasil e de cada UF."""
    b = base(eleicao)
    yield "BR", b
    for link in saida[f"{b}/resumo.json"]["_links"]["filhos"]:
        yield link["name"], f"{b}/{link['name'].lower()}"


def fonte(eleicao: Eleicao, tipo: str):
    """Caminho local do arquivo que o build usa para a fonte de um tipo."""
    (f,) = [f for f in eleicao.fontes if f.tipo == tipo]
    return RAW / usado_no_build(f)


def disponivel(eleicao: Eleicao) -> bool:
    return all((RAW / usado_no_build(f)).exists() for f in eleicao.fontes)
