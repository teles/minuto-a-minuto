"""Os eventos por UF são a camada de base: reagregá-los precisa reproduzir as séries."""

import csv
import io
from collections import Counter

from tests.util import base, locais


def _ler(texto):
    return list(csv.DictReader(io.StringIO(texto)))


def test_eventos_reproduzem_a_serie_minuto_de_cada_uf(saida, eleicao):
    for sigla, caminho in locais(saida, eleicao):
        if sigla == "BR":
            continue
        eventos = _ler(saida[f"{caminho}/eventos.csv"])
        pontos = saida[f"{caminho}/serie-minuto.json"]["pontos"]
        i = 0
        secoes = comparecimento = 0
        votos = Counter()
        for p in pontos:
            while i < len(eventos) and eventos[i]["t"] <= p["t"]:
                e = eventos[i]
                secoes += 1
                comparecimento += int(e["comparecimento"])
                votos.update({k[6:]: int(v) for k, v in e.items() if k.startswith("votos_")})
                i += 1
            assert (secoes, comparecimento) == (p["secoes"], p["comparecimento"]), (sigla, p["t"])
            assert {k: votos[k] for k in p["votos"]} == p["votos"], (sigla, p["t"])
        assert i == len(eventos), sigla


def test_eventos_ordenados_e_sem_secao_repetida(saida, eleicao):
    vistas = set()
    for sigla, caminho in locais(saida, eleicao):
        if sigla == "BR":
            continue
        eventos = _ler(saida[f"{caminho}/eventos.csv"])
        assert [e["t"] for e in eventos] == sorted(e["t"] for e in eventos), sigla
        for e in eventos:
            assert e["t"] >= e["recebido"] or e["t"].endswith("T17:00:00-03:00"), e
            chave = (e["uf"], e["cd_municipio_tse"], e["zona"], e["secao"])
            assert chave not in vistas, chave
            vistas.add(chave)
    br = saida[f"{base(eleicao)}/resumo.json"]["resultado"]
    assert len(vistas) == br["secoes"]
