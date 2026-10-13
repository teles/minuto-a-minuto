"""Fontes de dados de cada eleição.

Toda fonte tem URL pública. As do TSE que publicam `.sha512` ao lado do arquivo
são verificadas contra ele; as demais têm o hash fixado no manifesto
(`manifestos/<eleicao>.json`) na primeira vez em que são baixadas.

Boletins de urna (`bweb`) têm também um extrato: só as linhas do cargo, num CSV
gzip determinístico. O build e a CI usam o extrato; o original fica registrado
no manifesto como a origem dele.
"""

from dataclasses import dataclass
from pathlib import PurePosixPath

UFS = [
    "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT", "PA",
    "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO", "ZZ",
]

_ODSELE = "https://cdn.tse.jus.br/estatistica/sead/odsele"


@dataclass(frozen=True)
class Fonte:
    id: str
    url: str
    destino: str  # caminho relativo a data/raw
    tipo: str  # "bweb" | "detalhe" | "munzona" | "terceiro"
    sha512_tse: bool  # o TSE publica <url>.sha512
    extrato: str | None = None  # bweb: caminho do extrato, relativo a data/raw


@dataclass(frozen=True)
class Eleicao:
    id: str
    ano: int
    turno: int
    data: str  # AAAA-MM-DD
    cd_eleicao_tse: str  # eleição de presidente no TSE
    cd_cargo: str
    cargo: str
    inicio_divulgacao: str  # horário de Brasília em que o TSE começa a divulgar
    fontes: tuple[Fonte, ...]
    # Candidatos na urna que não constam do resultado oficial: o TSE conta os votos
    # neles como nulos técnicos (QT_VOTOS_NULOS_TECNICOS no detalhe_votacao_munzona).
    nulos_tecnicos: tuple[str, ...] = ()
    # Seções instaladas segundo o detalhe_votacao_munzona, mas sem boletim publicado
    # (comparecimento zero): (UF, CD_MUNICIPIO, NR_ZONA, aptos). Não entram nas séries.
    secoes_sem_boletim: tuple[tuple[str, str, int, int], ...] = ()


def _bweb(eleicao_id: str, ano: int, turno: int, carimbo: str, cargo: str) -> list[Fonte]:
    """Boletins de urna por UF; `carimbo` é a data/hora no nome dos arquivos do TSE."""
    base = f"https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes{ano}/buweb"
    fontes = []
    for uf in UFS:
        nome = f"bweb_{turno}t_{uf}_{carimbo}"
        fontes.append(
            Fonte(
                id=f"bweb-{uf}",
                url=f"{base}/{nome}.zip",
                destino=f"{eleicao_id}/bweb/{nome}.zip",
                tipo="bweb",
                sha512_tse=True,
                extrato=f"{eleicao_id}/extratos/{nome}-{cargo}.csv.gz",
            )
        )
    return fontes


def _oficiais(ano: int) -> list[Fonte]:
    """Datasets do TSE independentes do boletim, usados na conciliação."""
    return [
        Fonte(
            id=f"detalhe-{ano}",
            url=f"{_ODSELE}/detalhe_votacao_munzona/detalhe_votacao_munzona_{ano}.zip",
            destino=f"{ano}/detalhe/detalhe_votacao_munzona_{ano}.zip",
            tipo="detalhe",
            sha512_tse=False,
        ),
        Fonte(
            id=f"munzona-{ano}",
            url=f"{_ODSELE}/votacao_candidato_munzona/votacao_candidato_munzona_{ano}.zip",
            destino=f"{ano}/munzona/votacao_candidato_munzona_{ano}.zip",
            tipo="munzona",
            sha512_tse=False,
        ),
    ]


def _terceiro(id_: str, url: str, eleicao_id: str) -> Fonte:
    """Série gravada ao vivo por terceiros, fixada por commit; usada só para validar a reconstrução."""
    caminho = PurePosixPath(url.split("githubusercontent.com/", 1)[1])
    return Fonte(
        id=id_,
        url=url,
        destino=f"terceiros/{eleicao_id}/{caminho}",
        tipo="terceiro",
        sha512_tse=False,
    )


ELEICOES = {
    "2022-2t": Eleicao(
        id="2022-2t",
        ano=2022,
        turno=2,
        data="2022-10-30",
        cd_eleicao_tse="545",
        cd_cargo="1",
        cargo="presidente",
        inicio_divulgacao="17:00:00",
        fontes=(
            *_bweb("2022-2t", 2022, 2, "311020221535", "presidente"),
            *_oficiais(2022),
            _terceiro(
                "wcota-br",
                "https://raw.githubusercontent.com/wcota/br_eleicoes_2022_2T/f2a869e104fa5a2e3fdcdb594a9ad66326db2605/br.csv",
                "2022-2t",
            ),
        ),
    ),
    "2026-1t": Eleicao(
        id="2026-1t",
        ano=2026,
        turno=1,
        data="2026-10-04",
        cd_eleicao_tse="6257",
        cd_cargo="1",
        cargo="presidente",
        inicio_divulgacao="17:00:00",
        fontes=(
            *_bweb("2026-1t", 2026, 1, "051020261403", "presidente"),
            *_oficiais(2026),
            _terceiro(
                "ntwkst-br",
                "https://raw.githubusercontent.com/ntwkst/apuracao-monitor/c3a4a364f95614955cf03f81321d0c462338e5f3/data/linha-do-tempo-t1-2026.csv",
                "2026-1t",
            ),
        ),
        # 28 = LEONARDO AVALANCHE (PRTB): está nos boletins, mas não no resultado
        # oficial; os 5.246 votos nele são nulos técnicos no detalhe_votacao_munzona.
        nulos_tecnicos=("28",),
        # CIUDAD GUAYANA (Venezuela), zona 1: 1 seção instalada, 72 aptos, comparecimento 0,
        # sem nenhuma linha no bweb_1t_ZZ.
        secoes_sem_boletim=(("ZZ", "29564", 1, 72),),
    ),
}
