import pytest

from pipeline.build import gerar
from pipeline.fontes import ELEICOES


@pytest.fixture(scope="session")
def saida():
    """Saída do build de 2022-2t, gerada uma vez por sessão de testes."""
    return gerar(ELEICOES["2022-2t"])
