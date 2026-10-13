"""Conciliação de cada eleição com os totais oficiais do TSE.

Estes testes são a garantia de que os JSONs publicados não têm dado inventado ou
perdido: o resultado final de cada local precisa ser idêntico, voto a voto, aos
datasets oficiais do TSE independentes do boletim de urna, e as séries precisam
obedecer às regras básicas de uma apuração.

Rodam para toda eleição com fontes em data/raw (ver tests/conftest.py).
"""

import pytest

from tests.util import FUSO, base, locais


def test_todas_as_ufs_e_exterior(saida, oficiais, eleicao):
    ufs = {sigla for sigla, _ in locais(saida, eleicao)} - {"BR"}
    assert ufs == set(oficiais) - {"BR"}
    assert len(ufs) == 28


def test_candidatos_iguais_aos_do_resultado_oficial(saida, oficiais, eleicao):
    publicados = {c["numero"] for c in saida[f"{base(eleicao)}/resumo.json"]["candidatos"]}
    oficiais_nominais = {k for k in oficiais["BR"].votos if k not in ("branco", "nulo")}
    assert publicados == oficiais_nominais


def test_nulos_tecnicos_configurados_conferem_com_o_oficial(oficiais, eleicao):
    # Sem nulos técnicos no oficial, não pode haver candidato reclassificado, e vice-versa.
    assert bool(eleicao.nulos_tecnicos) == (oficiais["BR"].nulos_tecnicos > 0)


def test_resultado_final_identico_ao_oficial(saida, oficiais, eleicao):
    for sigla, caminho in locais(saida, eleicao):
        r = saida[f"{caminho}/resumo.json"]["resultado"]
        of = oficiais[sigla]
        assert r["votos"] == {k: of.votos[k] for k in r["votos"]}, sigla
        assert set(of.votos) <= set(r["votos"]), f"{sigla}: votável oficial ausente"
        assert r["comparecimento"] == of.comparecimento, sigla
        # boletim só existe para seções instaladas (e não para as listadas em secoes_sem_boletim)
        sem_boletim = [s for s in eleicao.secoes_sem_boletim if sigla in ("BR", s[0])]
        assert r["aptos"] == of.aptos - of.aptos_nao_instaladas - sum(s[3] for s in sem_boletim), sigla
        assert r["secoes"] == of.secoes_principais - of.secoes_nao_instaladas - len(sem_boletim), sigla
        assert r["pct_secoes"] == 100.0, sigla


def test_soma_das_ufs_igual_ao_brasil_a_cada_minuto(saida, eleicao):
    b = base(eleicao)
    br = saida[f"{b}/serie-minuto.json"]["pontos"]
    ufs = [saida[f"{c}/serie-minuto.json"]["pontos"] for s, c in locais(saida, eleicao) if s != "BR"]
    for ponto in br:
        soma_secoes = soma_comp = 0
        soma_votos = {k: 0 for k in ponto["votos"]}
        for serie in ufs:
            # último ponto da UF até o instante t (a série da UF pode acabar antes)
            p = max((x for x in serie if x["t"] <= ponto["t"]), key=lambda x: x["t"], default=None)
            if p:
                soma_secoes += p["secoes"]
                soma_comp += p["comparecimento"]
                for k in soma_votos:
                    soma_votos[k] += p["votos"].get(k, 0)
        assert (soma_secoes, soma_comp, soma_votos) == (
            ponto["secoes"],
            ponto["comparecimento"],
            ponto["votos"],
        ), ponto["t"]


@pytest.mark.parametrize("arquivo", ["serie-minuto.json", "serie-pct.json"])
def test_series_coerentes(saida, eleicao, arquivo):
    for sigla, caminho in locais(saida, eleicao):
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


def test_serie_pct_atinge_cada_marca(saida, eleicao):
    for sigla, caminho in locais(saida, eleicao):
        pontos = saida[f"{caminho}/serie-pct.json"]["pontos"]
        assert [p["p"] for p in pontos] == [i * 0.5 for i in range(201)], sigla
        for p in pontos:
            assert p["pct_secoes"] >= p["p"], (sigla, p["p"])


def test_serie_minuto_comeca_na_abertura_da_divulgacao(saida, eleicao):
    for sigla, caminho in locais(saida, eleicao):
        pontos = saida[f"{caminho}/serie-minuto.json"]["pontos"]
        assert pontos[0]["t"] == f"{eleicao.data}T{eleicao.inicio_divulgacao}{FUSO}", sigla
        assert pontos[0]["seg_desde_inicio"] == 0, sigla
