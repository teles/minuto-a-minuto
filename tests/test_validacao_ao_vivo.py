"""Compara a reconstrução com placares do TSE gravados ao vivo por terceiros.

O TSE exibia cada seção alguns segundos depois do recebimento do boletim, e as
seções não instaladas entram no placar oficial em algum momento da noite; por
isso a comparação é por tolerância, não igualdade. Os limites foram medidos e
estão documentados em docs/metodo.md.
"""

import bisect
import csv
import io
import statistics
from datetime import datetime

from tests.util import FUSO, base, fonte, locais


def _pct(votos: dict, a: str, b: str) -> float:
    return 100 * votos[a] / (votos[a] + votos[b])


def _nosso_em(pontos: list[dict], t: datetime) -> dict:
    tempos = [datetime.fromisoformat(p["t"]) for p in pontos]
    return pontos[bisect.bisect_right(tempos, t) - 1]


def _validar_2022_2t(saida, eleicao, oficiais):
    """Série nacional gravada por wcota/br_eleicoes_2022_2T (votos absolutos)."""
    pontos = saida[f"{base(eleicao)}/serie-minuto.json"]["pontos"]
    # boletins do exterior recebidos antes das 17h entram todos às 17h
    assert pontos[0]["secoes"] == 573

    gravado = {}
    with fonte(eleicao, "terceiro").open() as f:
        for r in csv.DictReader(f):
            if r["date_totalizacao"].strip():
                gravado.setdefault(r["date_totalizacao"], {})[r["cand"]] = int(r["votos"])
    assert len(gravado) > 150

    diferencas, diferencas_com_1pct = [], []
    for quando, votos in gravado.items():
        if votos["Lula"] + votos["Bolsonaro"] == 0:
            continue
        nosso = _nosso_em(pontos, datetime.fromisoformat(quando + FUSO))
        d = abs(_pct(nosso["votos"], "13", "22") - _pct(votos, "Lula", "Bolsonaro"))
        diferencas.append(d)
        if nosso["pct_secoes"] >= 1:
            diferencas_com_1pct.append(d)

    assert statistics.median(diferencas) < 0.05
    # Abaixo de 1% apurado (poucas centenas de seções), a granularidade de 1 minuto
    # e o atraso de exibição do TSE (~22 s) bastam para mover o placar em mais de
    # 2 p.p. (medido: 2,2 p.p. às 17:05, com 0,15% apurado). A partir de 1%, o
    # desvio máximo medido é 0,75 p.p.
    assert max(diferencas_com_1pct) < 1.0

    final = gravado[max(gravado)]
    assert (final["Lula"], final["Bolsonaro"]) == (pontos[-1]["votos"]["13"], pontos[-1]["votos"]["22"])


def _validar_2026_1t(saida, eleicao, oficiais):
    """Série nacional gravada por ntwkst/apuracao-monitor (% com 2 casas, só horário).

    Algumas leituras dessa gravação estão defasadas: às 19:14:08 ela registra 64,81%
    apurado, quando os boletins já somavam 74,5%. Por isso a comparação alinha pelo
    % de seções que a própria gravação registra, e não pelo horário. Alinhado assim,
    o desvio máximo medido é 0,089 p.p. (mediana 0,003).
    """
    eventos = []
    for sigla, caminho in locais(saida, eleicao):
        if sigla != "BR":
            eventos += csv.DictReader(io.StringIO(saida[f"{caminho}/eventos.csv"]))
    eventos.sort(key=lambda e: (e["t"], e["uf"], int(e["cd_municipio_tse"]), int(e["zona"]), int(e["secao"])))

    acumulado, lula, flavio, validos = [], 0, 0, 0
    for e in eventos:
        lula += int(e["votos_13"])
        flavio += int(e["votos_22"])
        validos += sum(int(v) for k, v in e.items() if k.startswith("votos_") and k not in ("votos_branco", "votos_nulo"))
        acumulado.append({"13": lula, "22": flavio, "validos": validos})

    principais = oficiais["BR"].secoes_principais  # denominador do % exibido pelo TSE
    diferencas = []
    with fonte(eleicao, "terceiro").open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["Origem"] != "Nacional TSE":
                continue
            pct = float(r["% Seções totalizadas"].rstrip("%"))
            nosso = acumulado[max(1, min(len(acumulado), round(pct / 100 * principais))) - 1]
            for numero, coluna in (("13", "% LULA (13)"), ("22", "% FLAVIO BOLSONARO (22)")):
                diferencas.append(abs(100 * nosso[numero] / nosso["validos"] - float(r[coluna].rstrip("%"))))
    assert len(diferencas) > 600

    assert statistics.median(diferencas) < 0.01
    assert max(diferencas) < 0.15


VALIDACOES = {"2022-2t": _validar_2022_2t, "2026-1t": _validar_2026_1t}


def test_reconstrucao_confere_com_serie_gravada_ao_vivo(saida, eleicao, oficiais):
    VALIDACOES[eleicao.id](saida, eleicao, oficiais)
