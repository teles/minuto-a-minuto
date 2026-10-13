"""Conciliação do 2º turno de 2022 (presidente).

Estes testes são a garantia de que os JSONs publicados não têm dado inventado ou
perdido: o resultado final de cada local precisa ser idêntico, voto a voto, aos
datasets oficiais do TSE independentes do boletim de urna, e as séries precisam
obedecer às regras básicas de uma apuração.

Requer as fontes em data/raw (uv run python -m pipeline.fetch 2022-2t).
"""

import bisect
import csv
import statistics
from datetime import datetime

import pytest

from pipeline import oficial
from pipeline.build import PREFIXO
from pipeline.fetch import RAW
from pipeline.fontes import ELEICOES

ELEICAO = ELEICOES["2022-2t"]
BASE = f"{PREFIXO}/2022-2t/presidente/br"
FONTES = {f.id: RAW / f.destino for f in ELEICAO.fontes}

pytestmark = pytest.mark.skipif(
    not all(p.exists() for p in FONTES.values()), reason="fontes não baixadas (pipeline.fetch)"
)


@pytest.fixture(scope="session")
def oficiais():
    return oficial.ler_oficiais(
        FONTES["detalhe-2022"], FONTES["munzona-2022"], ELEICAO.ano, ELEICAO.turno, ELEICAO.cd_cargo
    )


def _locais(saida):
    """(sigla, caminho_base) de BR e de cada UF."""
    yield "BR", BASE
    for link in saida[f"{BASE}/resumo.json"]["_links"]["filhos"]:
        yield link["name"], f"{BASE}/{link['name'].lower()}"


def test_todas_as_ufs_e_exterior(saida, oficiais):
    ufs = {sigla for sigla, _ in _locais(saida)} - {"BR"}
    assert ufs == set(oficiais) - {"BR"}
    assert len(ufs) == 28


def test_resultado_final_identico_ao_oficial(saida, oficiais):
    for sigla, caminho in _locais(saida):
        r = saida[f"{caminho}/resumo.json"]["resultado"]
        of = oficiais[sigla]
        assert r["votos"] == {k: of.votos[k] for k in r["votos"]}, sigla
        assert set(of.votos) <= set(r["votos"]), f"{sigla}: votável oficial ausente"
        assert r["comparecimento"] == of.comparecimento, sigla
        # boletim só existe para seções instaladas
        assert r["aptos"] == of.aptos - of.aptos_nao_instaladas, sigla
        assert r["secoes"] == of.secoes_principais - of.secoes_nao_instaladas, sigla
        assert r["pct_secoes"] == 100.0, sigla


def test_soma_das_ufs_igual_ao_brasil_a_cada_minuto(saida):
    br = saida[f"{BASE}/serie-minuto.json"]["pontos"]
    ufs = [saida[f"{c}/serie-minuto.json"]["pontos"] for s, c in _locais(saida) if s != "BR"]
    for ponto in br:
        soma_secoes = soma_lula = soma_comp = 0
        for serie in ufs:
            # último ponto da UF até o instante t (a série da UF pode acabar antes)
            p = max((x for x in serie if x["t"] <= ponto["t"]), key=lambda x: x["t"], default=None)
            if p:
                soma_secoes += p["secoes"]
                soma_lula += p["votos"]["13"]
                soma_comp += p["comparecimento"]
        assert (soma_secoes, soma_lula, soma_comp) == (
            ponto["secoes"],
            ponto["votos"]["13"],
            ponto["comparecimento"],
        ), ponto["t"]


@pytest.mark.parametrize("arquivo", ["serie-minuto.json", "serie-pct.json"])
def test_series_coerentes(saida, arquivo):
    for sigla, caminho in _locais(saida):
        pontos = saida[f"{caminho}/{arquivo}"]["pontos"]
        final = saida[f"{caminho}/resumo.json"]["resultado"]
        anterior = None
        for p in pontos:
            assert sum(p["votos"].values()) == p["comparecimento"], (sigla, p["t"])
            assert p["comparecimento"] <= p["aptos"], (sigla, p["t"])
            if anterior:
                assert p["t"] >= anterior["t"], (sigla, p["t"])
                for campo in ("secoes", "aptos", "comparecimento"):
                    assert p[campo] >= anterior[campo], (sigla, campo, p["t"])
                for k, v in p["votos"].items():
                    assert v >= anterior["votos"][k], (sigla, k, p["t"])
            anterior = p
        instante = {"p", "t", "seg_desde_inicio"}
        assert {k: v for k, v in pontos[-1].items() if k not in instante} == {
            k: v for k, v in final.items() if k not in instante
        }, sigla


def test_serie_pct_atinge_cada_marca(saida):
    for sigla, caminho in _locais(saida):
        pontos = saida[f"{caminho}/serie-pct.json"]["pontos"]
        assert [p["p"] for p in pontos] == [i * 0.5 for i in range(201)], sigla
        for p in pontos:
            assert p["pct_secoes"] >= p["p"], (sigla, p["p"])


def test_serie_minuto_comeca_na_abertura_da_divulgacao(saida):
    pontos = saida[f"{BASE}/serie-minuto.json"]["pontos"]
    assert pontos[0]["t"] == "2022-10-30T17:00:00-03:00"
    # boletins do exterior recebidos antes das 17h entram todos às 17h
    assert pontos[0]["secoes"] == 573


def test_reconstrucao_confere_com_serie_gravada_ao_vivo(saida):
    """Compara com o placar do TSE gravado ao vivo por wcota/br_eleicoes_2022_2T.

    O TSE exibia cada seção alguns segundos depois do recebimento do boletim, e as
    47 seções não instaladas entraram no placar por volta das 19h30; por isso a
    comparação é por tolerância, não igualdade.
    """
    pontos = saida[f"{BASE}/serie-minuto.json"]["pontos"]
    tempos = [datetime.fromisoformat(p["t"]) for p in pontos]

    gravado = {}
    with FONTES["wcota-br"].open() as f:
        for r in csv.DictReader(f):
            if r["date_totalizacao"].strip():
                gravado.setdefault(r["date_totalizacao"], {})[r["cand"]] = int(r["votos"])
    assert len(gravado) > 150

    diferencas = []
    diferencas_com_1pct = []
    for quando, votos in gravado.items():
        t = datetime.fromisoformat(quando + ELEICAO_FUSO)
        nosso = pontos[bisect.bisect_right(tempos, t) - 1]
        if votos["Lula"] + votos["Bolsonaro"] == 0:
            continue
        pct_gravado = 100 * votos["Lula"] / (votos["Lula"] + votos["Bolsonaro"])
        pct_nosso = 100 * nosso["votos"]["13"] / (nosso["votos"]["13"] + nosso["votos"]["22"])
        diferencas.append(abs(pct_nosso - pct_gravado))
        if nosso["pct_secoes"] >= 1:
            diferencas_com_1pct.append(abs(pct_nosso - pct_gravado))

    assert statistics.median(diferencas) < 0.05
    # Abaixo de 1% apurado (poucas centenas de seções), a granularidade de 1 minuto
    # e o atraso de exibição do TSE (~22 s) bastam para mover o placar em mais de
    # 2 p.p. (medido: 2,2 p.p. às 17:05, com 0,15% apurado). A partir de 1%, o
    # desvio máximo medido é 0,75 p.p.
    assert max(diferencas_com_1pct) < 1.0

    final = gravado[max(gravado)]
    assert (final["Lula"], final["Bolsonaro"]) == (
        pontos[-1]["votos"]["13"],
        pontos[-1]["votos"]["22"],
    )


ELEICAO_FUSO = "-03:00"
