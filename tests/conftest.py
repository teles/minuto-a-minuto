import pytest

from pipeline import oficial
from pipeline.build import gerar
from pipeline.fontes import ELEICOES
from tests.util import disponivel, fonte

# Eleições cujas fontes estão em data/raw (uv run python -m pipeline.fetch <eleicao> [--arquivo]).
DISPONIVEIS = [e for e in ELEICOES.values() if disponivel(e)]


@pytest.fixture(scope="session", params=DISPONIVEIS or [None], ids=lambda e: e.id if e else "nenhuma")
def eleicao(request):
    if request.param is None:
        pytest.skip("nenhuma eleição com fontes baixadas")
    return request.param


@pytest.fixture(scope="session")
def saida(eleicao):
    """Saída do build da eleição, gerada uma vez por sessão de testes."""
    return gerar(eleicao)


@pytest.fixture(scope="session")
def oficiais(eleicao):
    return oficial.ler_oficiais(
        fonte(eleicao, "detalhe"), fonte(eleicao, "munzona"), eleicao.ano, eleicao.turno, eleicao.cd_cargo
    )
