"""Leitores dos totais oficiais do TSE usados na conciliação.

- detalhe_votacao_munzona: seções, aptos, comparecimento, brancos e nulos.
- votacao_candidato_munzona: votos por candidato.

São datasets independentes do boletim de urna; o build só publica se os
totais reconstruídos a partir dos boletins forem idênticos a estes.
"""

import csv
import io
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class TotaisOficiais:
    secoes_principais: int = 0
    secoes_agregadas: int = 0
    secoes_nao_instaladas: int = 0
    aptos: int = 0
    aptos_nao_instaladas: int = 0  # eleitores das seções não instaladas (não há boletim)
    nulos_tecnicos: int = 0  # já incluídos em votos["nulo"]
    comparecimento: int = 0
    votos: Counter = field(default_factory=Counter)  # mesmo formato de Secao.votos


def _linhas(zip_path: Path, membro: str):
    with zipfile.ZipFile(zip_path) as zf, zf.open(membro) as f:
        yield from csv.DictReader(io.TextIOWrapper(f, encoding="latin1"), delimiter=";")


def ler_oficiais(
    detalhe_zip: Path, munzona_zip: Path, ano: int, turno: int, cd_cargo: str
) -> dict[str, TotaisOficiais]:
    """Totais por UF (inclui "ZZ", exterior) e "BR" (soma de todas)."""
    por_uf: dict[str, TotaisOficiais] = defaultdict(TotaisOficiais)

    for r in _linhas(detalhe_zip, f"detalhe_votacao_munzona_{ano}_BR.csv"):
        if r["NR_TURNO"] != str(turno) or r["CD_CARGO"] != cd_cargo:
            continue
        t = por_uf[r["SG_UF"]]
        t.secoes_principais += int(r["QT_SECOES_PRINCIPAIS"])
        t.secoes_agregadas += int(r["QT_SECOES_AGREGADAS"])
        t.secoes_nao_instaladas += int(r["QT_SECOES_NAO_INSTALADAS"])
        t.aptos += int(r["QT_APTOS"])
        t.aptos_nao_instaladas += int(r["QT_ELEITORES_SECOES_NAO_INSTALADAS"])
        t.comparecimento += int(r["QT_COMPARECIMENTO"])
        t.votos["branco"] += int(r["QT_VOTOS_BRANCOS"])
        t.votos["nulo"] += int(r["QT_TOTAL_VOTOS_NULOS"])
        t.nulos_tecnicos += int(r["QT_VOTOS_NULOS_TECNICOS"])

    for r in _linhas(munzona_zip, f"votacao_candidato_munzona_{ano}_BR.csv"):
        if r["NR_TURNO"] != str(turno) or r["CD_CARGO"] != cd_cargo:
            continue
        por_uf[r["SG_UF"]].votos[r["NR_CANDIDATO"]] += int(r["QT_VOTOS_NOMINAIS"])

    br = TotaisOficiais()
    for t in por_uf.values():
        br.secoes_principais += t.secoes_principais
        br.secoes_agregadas += t.secoes_agregadas
        br.secoes_nao_instaladas += t.secoes_nao_instaladas
        br.aptos += t.aptos
        br.aptos_nao_instaladas += t.aptos_nao_instaladas
        br.nulos_tecnicos += t.nulos_tecnicos
        br.comparecimento += t.comparecimento
        br.votos.update(t.votos)
    return {**por_uf, "BR": br}
