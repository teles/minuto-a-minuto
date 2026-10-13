"""Gera os JSONs estáticos da API para uma eleição.

Uso: uv run python -m pipeline.build 2022-2t

Saída em dist/v1/. Não grava carimbo de data/hora: o mesmo commit com as mesmas
fontes gera exatamente os mesmos bytes.
"""

import csv
import io
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from pipeline import bweb, schemas, series
from pipeline.fetch import MANIFESTOS, RAIZ, RAW
from pipeline.fontes import ELEICOES, Eleicao

DIST = RAIZ / "dist"
# Arquivos cuja mudança altera a saída; o commit registrado é o último que mexeu neles.
CODIGO = ["pipeline", "pyproject.toml", "uv.lock"]
PREFIXO = "/v1/eleicoes"
FUSO = "-03:00"  # horário de Brasília (sem horário de verão desde 2019)
PASSO_PCT = 0.5
LICENCA = {
    "id": "CC-BY-4.0",
    "url": "https://creativecommons.org/licenses/by/4.0/deed.pt-br",
    "atribuicao": "Dados: minuto-a-minuto (github.com/teles/minuto-a-minuto), a partir de dados públicos do TSE.",
}

NOMES_UF = {
    "AC": "Acre", "AL": "Alagoas", "AM": "Amazonas", "AP": "Amapá", "BA": "Bahia",
    "CE": "Ceará", "DF": "Distrito Federal", "ES": "Espírito Santo", "GO": "Goiás",
    "MA": "Maranhão", "MG": "Minas Gerais", "MS": "Mato Grosso do Sul", "MT": "Mato Grosso",
    "PA": "Pará", "PB": "Paraíba", "PE": "Pernambuco", "PI": "Piauí", "PR": "Paraná",
    "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte", "RO": "Rondônia", "RR": "Roraima",
    "RS": "Rio Grande do Sul", "SC": "Santa Catarina", "SE": "Sergipe", "SP": "São Paulo",
    "TO": "Tocantins", "ZZ": "Exterior",
}


def _iso(t: datetime) -> str:
    return t.isoformat() + FUSO


def _ordem_votos(votos, candidatos) -> dict[str, int]:
    chaves = sorted(candidatos, key=int) + ["branco", "nulo"]
    return {k: votos.get(k, 0) for k in chaves}


def _ponto(
    placar: series.Placar, t: datetime, inicio: datetime, total_instaladas: int, candidatos
) -> dict:
    return {
        "t": _iso(t),
        "seg_desde_inicio": int((t - inicio).total_seconds()),
        "secoes": placar.secoes,
        "pct_secoes": round(100 * placar.secoes / total_instaladas, 4),
        "aptos": placar.aptos,
        "comparecimento": placar.comparecimento,
        "votos": _ordem_votos(placar.votos, candidatos),
    }


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=RAIZ, capture_output=True, text=True, check=True
    ).stdout.strip()


def _eventos_csv(ordenadas: list[bweb.Secao], inicio: datetime, candidatos) -> str:
    """Uma linha por seção, na ordem em que entraram no placar.

    `recebido` é o DT_BU_RECEBIDO do TSE; `t` é quando a seção entrou no placar
    (o mesmo instante, ou o início da divulgação se o boletim chegou antes).
    """
    votaveis = sorted(candidatos, key=int) + ["branco", "nulo"]
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(
        ["t", "recebido", "uf", "cd_municipio_tse", "municipio", "zona", "secao",
         "tipo_urna", "aptos", "comparecimento", *(f"votos_{v}" for v in votaveis)]
    )
    for sec in ordenadas:
        w.writerow(
            [_iso(series.instante(sec, inicio)), _iso(sec.recebido), sec.uf, sec.cd_municipio,
             sec.nm_municipio, sec.zona, sec.secao, sec.tipo_urna, sec.aptos, sec.comparecimento,
             *(sec.votos.get(v, 0) for v in votaveis)]
        )
    return buf.getvalue()


def _commit_do_codigo() -> str | None:
    """Último commit que alterou o código do pipeline, ou None se há mudanças não commitadas.

    Não usamos HEAD: o commit que adiciona os dados gerados não pode conter o
    próprio hash, e commits só de dados não mudam a saída.
    """
    try:
        if _git("status", "--porcelain", "--", *CODIGO):
            print("aviso: código do pipeline com mudanças não commitadas; commit = null")
            return None
        return _git("log", "-1", "--format=%H", "--", *CODIGO) or None
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _fontes(manifesto: dict, ids: set[str]) -> list[dict]:
    return [
        {"url": f["url"], "sha512": f["sha512"]} for f in manifesto["fontes"] if f["id"] in ids
    ]


def gerar(eleicao: Eleicao) -> dict[str, dict | str]:
    """Retorna {caminho_publicado: objeto_json ou texto CSV}."""
    manifesto = json.loads((MANIFESTOS / f"{eleicao.id}.json").read_text())
    fontes_bweb = {f.id: RAW / f.destino for f in eleicao.fontes if f.tipo == "bweb"}

    secoes, candidatos = bweb.ler_varios(list(fontes_bweb.values()), eleicao.cd_cargo)
    inicio = datetime.fromisoformat(f"{eleicao.data} {eleicao.inicio_divulgacao}")
    commit = _commit_do_codigo()

    cands_json = [
        {"numero": c.numero, "nome_urna": c.nome_urna, "partido": c.partido}
        for c in sorted(candidatos.values(), key=lambda c: int(c.numero))
    ]
    eleicao_json = {
        "id": eleicao.id,
        "ano": eleicao.ano,
        "turno": eleicao.turno,
        "data": eleicao.data,
        "cargo": eleicao.cargo,
        "cd_eleicao_tse": eleicao.cd_eleicao_tse,
        "inicio_divulgacao": _iso(inicio),
    }
    base = f"{PREFIXO}/{eleicao.id}/{eleicao.cargo}"

    por_uf: dict[str, list] = {}
    for s in secoes:
        por_uf.setdefault(s.uf, []).append(s)

    locais = [("br", "BR", "Brasil", secoes, set(fontes_bweb))]
    for uf in sorted(por_uf):
        locais.append(("uf", uf, NOMES_UF[uf], por_uf[uf], {f"bweb-{uf}"}))

    saida: dict[str, dict | str] = {}
    for nivel, sigla, nome, subset, ids_fonte in locais:
        caminho = f"{base}/br" if nivel == "br" else f"{base}/br/{sigla.lower()}"
        ordenadas = series.ordenar(subset, inicio)
        total = len(ordenadas)  # seções instaladas = seções com boletim

        minuto = series.serie_minuto(ordenadas, inicio)
        pct = series.serie_pct(ordenadas, inicio, total, PASSO_PCT)
        final = minuto[-1]

        links = {
            "self": {"href": f"{caminho}/resumo.json"},
            "serie-minuto": {"href": f"{caminho}/serie-minuto.json"},
            "serie-pct": {"href": f"{caminho}/serie-pct.json"},
            "eleicao": {"href": f"{PREFIXO}/{eleicao.id}/index.json"},
            "fonte-tse": [{"href": f["url"]} for f in _fontes(manifesto, ids_fonte)],
        }
        if nivel == "br":
            links["filhos"] = [
                {"href": f"{caminho}/{uf.lower()}/resumo.json", "name": uf} for uf in sorted(por_uf)
            ]
            links["eventos"] = [
                {"href": f"{caminho}/{uf.lower()}/eventos.csv", "name": uf} for uf in sorted(por_uf)
            ]
        else:
            links["parent"] = {"href": f"{base}/br/resumo.json"}
            links["eventos"] = {"href": f"{caminho}/eventos.csv"}
            # eventos só por UF: o do Brasil seria a concatenação de todos
            saida[f"{caminho}/eventos.csv"] = _eventos_csv(ordenadas, inicio, candidatos)

        comum = {
            "eleicao": eleicao_json,
            "local": {"nivel": nivel, "sigla": sigla, "nome": nome},
            "candidatos": cands_json,
        }
        proveniencia = {
            "fontes": _fontes(manifesto, ids_fonte),
            "gerado_por": {"repositorio": "minuto-a-minuto", "commit": commit},
            "licenca": LICENCA,
        }

        saida[f"{caminho}/resumo.json"] = {
            "schema": "minuto-a-minuto/v1/resumo",
            **comum,
            "resultado": _ponto(final.placar, final.t, inicio, total, candidatos),
            "_links": links,
            "_proveniencia": proveniencia,
        }
        saida[f"{caminho}/serie-minuto.json"] = {
            "schema": "minuto-a-minuto/v1/serie-minuto",
            **comum,
            "pontos": [_ponto(p.placar, p.t, inicio, total, candidatos) for p in minuto],
            "_links": {**links, "self": {"href": f"{caminho}/serie-minuto.json"}},
            "_proveniencia": proveniencia,
        }
        saida[f"{caminho}/serie-pct.json"] = {
            "schema": "minuto-a-minuto/v1/serie-pct",
            **comum,
            "passo": PASSO_PCT,
            "pontos": [
                {"p": p, **_ponto(pt.placar, pt.t, inicio, total, candidatos)} for p, pt in pct
            ],
            "_links": {**links, "self": {"href": f"{caminho}/serie-pct.json"}},
            "_proveniencia": proveniencia,
        }

    saida[f"{PREFIXO}/{eleicao.id}/index.json"] = {
        "schema": "minuto-a-minuto/v1/eleicao",
        "eleicao": eleicao_json,
        "candidatos": cands_json,
        "_links": {
            "self": {"href": f"{PREFIXO}/{eleicao.id}/index.json"},
            eleicao.cargo: {"href": f"{base}/br/resumo.json"},
        },
    }
    return saida


def formatar(obj: dict) -> str:
    """JSON indentado, mas com cada item de "pontos" numa linha só.

    Assim um diff no git mostra exatamente quais pontos da série mudaram.
    """
    partes = []
    for chave, valor in obj.items():
        if chave == "pontos":
            linhas = ",\n".join(
                "    " + json.dumps(p, ensure_ascii=False, separators=(",", ":")) for p in valor
            )
            texto = "[\n" + linhas + "\n  ]"
        else:
            texto = json.dumps(valor, ensure_ascii=False, indent=2).replace("\n", "\n  ")
        partes.append(f"  {json.dumps(chave)}: {texto}")
    return "{\n" + ",\n".join(partes) + "\n}\n"


def escrever(saida: dict[str, dict | str], dist: Path = DIST) -> None:
    for caminho, obj in saida.items():
        arq = dist / caminho.lstrip("/")
        arq.parent.mkdir(parents=True, exist_ok=True)
        arq.write_text(obj if isinstance(obj, str) else formatar(obj))


def gerar_schemas() -> dict[str, dict]:
    return {f"{schemas.URL_BASE}/{nome}.schema.json": s for nome, s in schemas.SCHEMAS.items()}


def gerar_indice() -> dict[str, dict]:
    """Ponto de entrada da API: lista as eleições configuradas e os schemas."""
    return {
        "/v1/index.json": {
            "schema": "minuto-a-minuto/v1/indice",
            "eleicoes": [
                {"id": e.id, "cargos": [e.cargo], "href": f"{PREFIXO}/{e.id}/index.json"}
                for e in ELEICOES.values()
            ],
            "_links": {
                "self": {"href": "/v1/index.json"},
                "schemas": [
                    {"href": f"{schemas.URL_BASE}/{nome}.schema.json", "name": nome}
                    for nome in schemas.SCHEMAS
                ],
                "licenca": {"href": LICENCA["url"]},
                "codigo": {"href": "https://github.com/teles/minuto-a-minuto"},
            },
        }
    }


def main(eleicao_id: str) -> None:
    saida = gerar(ELEICOES[eleicao_id])
    destino = DIST / PREFIXO.lstrip("/") / eleicao_id
    if destino.exists():
        shutil.rmtree(destino)
    escrever(saida)
    escrever(gerar_schemas())
    escrever(gerar_indice())
    print(f"{len(saida)} arquivos gerados em {destino.relative_to(RAIZ)}")


if __name__ == "__main__":
    main(sys.argv[1])
