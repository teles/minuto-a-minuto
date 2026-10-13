"""Leitor dos boletins de urna (bweb_*.zip) do TSE.

Cada linha do CSV é uma combinação seção × cargo × votável. Este módulo agrega
as linhas de um cargo em uma `Secao` por seção principal. Qualquer coisa fora do
esperado (tipo de votável desconhecido, aptos divergentes entre linhas da mesma
seção, votável repetido) levanta exceção: o pipeline não tenta adivinhar.

Extrato: os boletins do 1º turno trazem todos os cargos e somam gigabytes. O
`extrair` grava só as linhas de um cargo, com as colunas usadas aqui, num CSV
gzip determinístico (mesmos bytes a cada execução). O build lê o extrato ou o
ZIP original indistintamente.
"""

import csv
import gzip
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
    # 2022: "30/10/2022 17:34:43"; 2026: "2026-10-04 18:25:49"
    formato = "%Y-%m-%d %H:%M:%S" if texto[4:5] == "-" else "%d/%m/%Y %H:%M:%S"
    return datetime.strptime(texto, formato)


# Colunas do boletim que o pipeline usa; são as únicas mantidas no extrato.
COLUNAS = [
    "SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO", "NR_ZONA", "NR_SECAO", "CD_CARGO_PERGUNTA",
    "DT_BU_RECEBIDO", "QT_APTOS", "QT_COMPARECIMENTO", "DS_TIPO_URNA", "CD_TIPO_VOTAVEL",
    "DS_TIPO_VOTAVEL", "NR_VOTAVEL", "NM_VOTAVEL", "SG_PARTIDO", "QT_VOTOS", "DS_AGREGADAS",
]


# Colunas renomeadas pelo TSE entre eleições → nome usado no extrato.
_ALIASES = {"DS_SECOES_AGREGADAS": "DS_AGREGADAS"}


def _normalizar_cabecalho(cabecalho: list[str]) -> list[str]:
    return [_ALIASES.get(c, c) for c in cabecalho]


def _linhas_zip(caminho: Path):
    with zipfile.ZipFile(caminho) as zf:
        csvs = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        if len(csvs) != 1:
            raise BwebInvalido(f"{caminho.name}: esperado 1 CSV, encontrado {csvs}")
        with zf.open(csvs[0]) as f:
            leitor = csv.reader(io.TextIOWrapper(f, encoding="latin1"), delimiter=";")
            cabecalho = _normalizar_cabecalho(next(leitor))
            for valores in leitor:
                yield dict(zip(cabecalho, valores))


def _linhas_extrato(caminho: Path):
    with gzip.open(caminho, "rt", encoding="utf-8", newline="") as f:
        yield from csv.DictReader(f, delimiter=";")


def _linhas_do_cargo(zip_bweb: Path, cd_cargo: str):
    """Linhas de um cargo, com pré-filtro em bytes.

    Os boletins do 1º turno têm centenas de milhões de linhas, quase todas de
    outros cargos. O pré-filtro olha a coluna do cargo sem interpretar o CSV; as
    linhas que passam são interpretadas normalmente. Se o pré-filtro errasse,
    a conciliação com os totais oficiais acusaria a diferença.
    """
    alvos = {cd_cargo.encode(), b'"' + cd_cargo.encode() + b'"'}  # 2022 com aspas, 2026 sem
    with zipfile.ZipFile(zip_bweb) as zf:
        csvs = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        if len(csvs) != 1:
            raise BwebInvalido(f"{zip_bweb.name}: esperado 1 CSV, encontrado {csvs}")
        with zf.open(csvs[0]) as f:
            cabecalho = _normalizar_cabecalho(
                next(csv.reader([f.readline().decode("latin1")], delimiter=";"))
            )
            i = cabecalho.index("CD_CARGO_PERGUNTA")
            for bruta in f:
                campos = bruta.split(b";", i + 1)
                if len(campos) <= i or campos[i] not in alvos:
                    continue
                valores = next(csv.reader([bruta.decode("latin1")], delimiter=";"))
                linha = dict(zip(cabecalho, valores))
                if linha["CD_CARGO_PERGUNTA"] != cd_cargo:
                    raise BwebInvalido(f"{zip_bweb.name}: pré-filtro inconsistente")
                yield linha


def extrair(zip_bweb: Path, cd_cargo: str, destino: Path) -> int:
    """Grava o extrato de um cargo; retorna o número de linhas."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_suffix(destino.suffix + ".part")
    n = 0
    with tmp.open("wb") as bruto:
        # mtime=0 e sem nome de arquivo no cabeçalho: gzip byte a byte reproduzível
        with gzip.GzipFile(filename="", mode="wb", fileobj=bruto, mtime=0) as gz:
            texto = io.TextIOWrapper(gz, encoding="utf-8", newline="")
            w = csv.writer(texto, delimiter=";", lineterminator="\n")
            w.writerow(COLUNAS)
            for linha in _linhas_do_cargo(zip_bweb, cd_cargo):
                w.writerow([linha[c] for c in COLUNAS])
                n += 1
            texto.flush()
            texto.detach()
    tmp.rename(destino)
    return n


def ler_zip(
    caminho: Path, cd_cargo: str, nulos_tecnicos: frozenset[str] = frozenset()
) -> tuple[list[Secao], dict[str, Candidato]]:
    """Lê um ZIP original do TSE ou um extrato (.csv.gz).

    `nulos_tecnicos`: números de candidatos que estão na urna mas não no resultado
    oficial; o TSE conta os votos neles como nulos (técnicos). Esses votos são
    somados a "nulo" e o candidato não entra na lista.
    """
    secoes: dict[tuple, Secao] = {}
    candidatos: dict[str, Candidato] = {}

    linhas = _linhas_extrato(caminho) if caminho.name.endswith(".csv.gz") else _linhas_zip(caminho)
    for linha in linhas:
        if linha["CD_CARGO_PERGUNTA"] != cd_cargo:
            continue
        _agregar_linha(linha, secoes, candidatos, caminho.name, nulos_tecnicos)

    for secao in secoes.values():
        if _NULO_TECNICO in secao.votos:
            secao.votos["nulo"] = secao.votos.get("nulo", 0) + secao.votos.pop(_NULO_TECNICO)
    return list(secoes.values()), candidatos


_NULO_TECNICO = "nulo_tecnico"  # chave interna, somada a "nulo" ao fim da leitura


def _agregar_linha(
    linha: dict, secoes: dict, candidatos: dict, origem: str, nulos_tecnicos: frozenset[str]
) -> None:
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
    if tipo == _NOMINAL and linha["NR_VOTAVEL"] in nulos_tecnicos:
        votavel = _NULO_TECNICO
    elif tipo == _NOMINAL:
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


def ler_varios(
    caminhos: list[Path], cd_cargo: str, nulos_tecnicos: frozenset[str] = frozenset()
) -> tuple[list[Secao], dict[str, Candidato]]:
    todas: list[Secao] = []
    candidatos: dict[str, Candidato] = {}
    vistas: set[tuple] = set()
    for caminho in caminhos:
        secoes, cands = ler_zip(caminho, cd_cargo, nulos_tecnicos)
        for s in secoes:
            if s.chave in vistas:
                raise BwebInvalido(f"seção {s.chave} aparece em mais de um arquivo")
            vistas.add(s.chave)
        todas.extend(secoes)
        for numero, cand in cands.items():
            if candidatos.setdefault(numero, cand) != cand:
                raise BwebInvalido(f"candidato {numero} com dados divergentes entre UFs")
    return todas, candidatos
