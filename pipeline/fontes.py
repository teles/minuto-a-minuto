"""Fontes de dados de cada eleição.

Toda fonte tem URL pública. As do TSE que publicam `.sha512` ao lado do arquivo
são verificadas contra ele; as demais têm o hash fixado no manifesto
(`manifestos/<eleicao>.json`) na primeira vez em que são baixadas.
"""

from dataclasses import dataclass

UFS = [
    "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT", "PA",
    "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO", "ZZ",
]


@dataclass(frozen=True)
class Fonte:
    id: str
    url: str
    destino: str  # caminho relativo a data/raw
    tipo: str  # "bweb" | "detalhe" | "munzona" | "terceiro"
    sha512_tse: bool  # o TSE publica <url>.sha512


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


def _bweb_2022_2t() -> list[Fonte]:
    base = "https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes2022/buweb"
    return [
        Fonte(
            id=f"bweb-{uf}",
            url=f"{base}/bweb_2t_{uf}_311020221535.zip",
            destino=f"2022-2t/bweb/bweb_2t_{uf}_311020221535.zip",
            tipo="bweb",
            sha512_tse=True,
        )
        for uf in UFS
    ]


_WCOTA_COMMIT = "f2a869e104fa5a2e3fdcdb594a9ad66326db2605"

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
            *_bweb_2022_2t(),
            Fonte(
                id="detalhe-2022",
                url="https://cdn.tse.jus.br/estatistica/sead/odsele/detalhe_votacao_munzona/detalhe_votacao_munzona_2022.zip",
                destino="2022/detalhe/detalhe_votacao_munzona_2022.zip",
                tipo="detalhe",
                sha512_tse=False,
            ),
            Fonte(
                id="munzona-2022",
                url="https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_candidato_munzona/votacao_candidato_munzona_2022.zip",
                destino="2022/munzona/votacao_candidato_munzona_2022.zip",
                tipo="munzona",
                sha512_tse=False,
            ),
            # Série gravada ao vivo por terceiros; usada só para validar a reconstrução.
            Fonte(
                id="wcota-br",
                url=f"https://raw.githubusercontent.com/wcota/br_eleicoes_2022_2T/{_WCOTA_COMMIT}/br.csv",
                destino=f"terceiros/wcota-2022-2t/{_WCOTA_COMMIT}/br.csv",
                tipo="terceiro",
                sha512_tse=False,
            ),
        ),
    ),
}
