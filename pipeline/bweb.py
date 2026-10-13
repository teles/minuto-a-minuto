"""Leitor dos boletins de urna (bweb_*.zip) do TSE.

Cada linha do CSV é uma combinação seção × cargo × votável. Este módulo agrega
as linhas de um cargo em uma `Secao` por seção principal. Qualquer coisa fora do
esperado (tipo de votável desconhecido, aptos divergentes entre linhas da mesma
seção, votável repetido) levanta exceção: o pipeline não tenta adivinhar.
"""

import csv
import io
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# CD_TIPO_VOTAVEL → chave usada nos votos. Nominal usa o número do candidato.
_NOMINAL = "1"
_TIPOS_VOTAVEL = {"2": "branco", "3": "nulo"}


@dataclass
class Secao:
    uf: str
    cd_municipio: str
    nm_municipio: str
    zona: int
    secao: int
    recebido: datetime  # DT_BU_RECEBIDO, horário de Brasília
    tipo_urna: str  # DS_TIPO_URNA (APURADA, ANULADA…)
    aptos: int
    comparecimento: int
    votos: dict[str, int] = field(default_factory=dict)

    @property
    def chave(self) -> tuple[str, str, int, int]:
        return (self.uf, self.cd_municipio, self.zona, self.secao)


@dataclass(frozen=True)
class Candidato:
    numero: str
    nome_urna: str
    partido: str


class BwebInvalido(Exception):
    pass


def _data_hora(texto: str) -> datetime:
    return datetime.strptime(texto, "%d/%m/%Y %H:%M:%S")


def ler_zip(caminho: Path, cd_cargo: str) -> tuple[list[Secao], dict[str, Candidato]]:
    secoes: dict[tuple, Secao] = {}
    candidatos: dict[str, Candidato] = {}

    with zipfile.ZipFile(caminho) as zf:
        csvs = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        if len(csvs) != 1:
            raise BwebInvalido(f"{caminho.name}: esperado 1 CSV, encontrado {csvs}")
        with zf.open(csvs[0]) as f:
            leitor = csv.DictReader(io.TextIOWrapper(f, encoding="latin1"), delimiter=";")
            for linha in leitor:
                if linha["CD_CARGO_PERGUNTA"] != cd_cargo:
                    continue
                _agregar_linha(linha, secoes, candidatos, caminho.name)

    return list(secoes.values()), candidatos


def _agregar_linha(linha: dict, secoes: dict, candidatos: dict, origem: str) -> None:
    chave = (linha["SG_UF"], linha["CD_MUNICIPIO"], int(linha["NR_ZONA"]), int(linha["NR_SECAO"]))
    aptos = int(linha["QT_APTOS"])
    comparecimento = int(linha["QT_COMPARECIMENTO"])
    recebido = _data_hora(linha["DT_BU_RECEBIDO"])

    secao = secoes.get(chave)
    if secao is None:
        secao = Secao(
            uf=chave[0],
            cd_municipio=chave[1],
            nm_municipio=linha["NM_MUNICIPIO"],
            zona=chave[2],
            secao=chave[3],
            recebido=recebido,
            tipo_urna=linha["DS_TIPO_URNA"],
            aptos=aptos,
            comparecimento=comparecimento,
        )
        secoes[chave] = secao
    elif (secao.aptos, secao.comparecimento, secao.recebido, secao.tipo_urna) != (
        aptos,
        comparecimento,
        recebido,
        linha["DS_TIPO_URNA"],
    ):
        raise BwebInvalido(f"{origem}: dados da seção divergem entre linhas em {chave}")

    tipo = linha["CD_TIPO_VOTAVEL"]
    if tipo == _NOMINAL:
        votavel = linha["NR_VOTAVEL"]
        cand = Candidato(votavel, linha["NM_VOTAVEL"], linha["SG_PARTIDO"])
        if candidatos.setdefault(votavel, cand) != cand:
            raise BwebInvalido(f"{origem}: candidato {votavel} com dados divergentes")
    elif tipo in _TIPOS_VOTAVEL:
        votavel = _TIPOS_VOTAVEL[tipo]
    else:
        raise BwebInvalido(f"{origem}: tipo de votável desconhecido {tipo} ({linha['DS_TIPO_VOTAVEL']})")

    if votavel in secao.votos:
        raise BwebInvalido(f"{origem}: votável {votavel} repetido na seção {chave}")
    secao.votos[votavel] = int(linha["QT_VOTOS"])


def ler_varios(caminhos: list[Path], cd_cargo: str) -> tuple[list[Secao], dict[str, Candidato]]:
    todas: list[Secao] = []
    candidatos: dict[str, Candidato] = {}
    vistas: set[tuple] = set()
    for caminho in caminhos:
        secoes, cands = ler_zip(caminho, cd_cargo)
        for s in secoes:
            if s.chave in vistas:
                raise BwebInvalido(f"seção {s.chave} aparece em mais de um arquivo")
            vistas.add(s.chave)
        todas.extend(secoes)
        for numero, cand in cands.items():
            if candidatos.setdefault(numero, cand) != cand:
                raise BwebInvalido(f"candidato {numero} com dados divergentes entre UFs")
    return todas, candidatos
