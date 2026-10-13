"""Baixa as fontes de uma eleição e confere a integridade.

Uso:
  uv run python -m pipeline.fetch 2022-2t              # do TSE; atualiza o manifesto
  uv run python -m pipeline.fetch 2022-2t --arquivo    # da cópia arquivada; só confere

- Fontes com `.sha512` do TSE: o arquivo precisa bater com o hash publicado.
- Todas as fontes: o hash fica registrado em manifestos/<eleicao>.json. Se um
  arquivo já registrado mudar (o TSE às vezes regera datasets), o fetch falha
  em vez de seguir com dados diferentes dos que foram conciliados.
- Cópia arquivada: os bytes exatos de cada fonte ficam como anexos da release
  `fontes-<eleicao>` do repositório, para que o build continue reproduzível
  mesmo que o TSE altere ou remova os arquivos.
"""

import argparse
import hashlib
import json
import shutil
import urllib.request
from pathlib import Path

from pipeline.fontes import ELEICOES, Fonte

RAIZ = Path(__file__).resolve().parent.parent
RAW = RAIZ / "data" / "raw"
MANIFESTOS = RAIZ / "manifestos"
ARQUIVO = "https://github.com/teles/minuto-a-minuto/releases/download/fontes-{eleicao}/{nome}"


class FonteAlterada(Exception):
    pass


def sha512_arquivo(caminho: Path) -> str:
    h = hashlib.sha512()
    with caminho.open("rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def nome_arquivado(fonte: Fonte) -> str:
    return Path(fonte.destino).name


def _baixar(url: str, destino: Path) -> dict[str, str | None]:
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_suffix(destino.suffix + ".part")
    with urllib.request.urlopen(url, timeout=120) as resp, tmp.open("wb") as f:
        shutil.copyfileobj(resp, f, 1 << 20)
        cabecalhos = {"etag": resp.headers.get("ETag"), "last_modified": resp.headers.get("Last-Modified")}
    tmp.rename(destino)
    return cabecalhos


def cabecalhos_remotos(url: str) -> dict[str, str | None]:
    req = urllib.request.Request(url, method="HEAD")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return {
            "etag": resp.headers.get("ETag"),
            "last_modified": resp.headers.get("Last-Modified"),
            "bytes": int(resp.headers.get("Content-Length", -1)),
        }


def sha512_publicado(url: str) -> str:
    with urllib.request.urlopen(url + ".sha512", timeout=60) as resp:
        return resp.read().decode("ascii").split()[0].lower()


def verificar_fonte(fonte: Fonte, registrado: dict | None) -> dict:
    caminho = RAW / fonte.destino
    if caminho.exists():
        # arquivo baixado antes: os cabeçalhos registrados continuam valendo
        cabecalhos = (
            {"etag": registrado.get("etag"), "last_modified": registrado.get("last_modified")}
            if registrado and "etag" in registrado
            else {k: v for k, v in cabecalhos_remotos(fonte.url).items() if k != "bytes"}
        )
    else:
        print(f"  baixando {fonte.url}")
        cabecalhos = _baixar(fonte.url, caminho)
    sha = sha512_arquivo(caminho)

    if fonte.sha512_tse and sha != sha512_publicado(fonte.url):
        raise FonteAlterada(f"{fonte.id}: sha512 não bate com o publicado pelo TSE")

    if registrado and registrado["sha512"] != sha:
        raise FonteAlterada(
            f"{fonte.id}: arquivo diferente do registrado no manifesto "
            f"({registrado['sha512'][:16]}… → {sha[:16]}…). Reconcilie antes de aceitar."
        )

    return {
        "id": fonte.id,
        "url": fonte.url,
        "tipo": fonte.tipo,
        "sha512": sha,
        "bytes": caminho.stat().st_size,
        "sha512_publicado_pelo_tse": fonte.sha512_tse,
        **cabecalhos,
    }


def carregar_manifesto(eleicao_id: str) -> dict[str, dict]:
    arq = MANIFESTOS / f"{eleicao_id}.json"
    if not arq.exists():
        return {}
    return {f["id"]: f for f in json.loads(arq.read_text())["fontes"]}


def do_tse(eleicao_id: str) -> None:
    eleicao = ELEICOES[eleicao_id]
    anterior = carregar_manifesto(eleicao_id)
    fontes = []
    for fonte in eleicao.fontes:
        fontes.append(verificar_fonte(fonte, anterior.get(fonte.id)))
        print(f"  ok {fonte.id}")

    MANIFESTOS.mkdir(exist_ok=True)
    arq = MANIFESTOS / f"{eleicao_id}.json"
    arq.write_text(
        json.dumps({"eleicao": eleicao_id, "fontes": fontes}, ensure_ascii=False, indent=2) + "\n"
    )
    print(f"{len(fontes)} fontes verificadas; manifesto em {arq.relative_to(RAIZ)}")


def do_arquivo(eleicao_id: str) -> None:
    eleicao = ELEICOES[eleicao_id]
    manifesto = carregar_manifesto(eleicao_id)
    for fonte in eleicao.fontes:
        caminho = RAW / fonte.destino
        if not caminho.exists():
            url = ARQUIVO.format(eleicao=eleicao_id, nome=nome_arquivado(fonte))
            print(f"  baixando {url}")
            _baixar(url, caminho)
        if sha512_arquivo(caminho) != manifesto[fonte.id]["sha512"]:
            raise FonteAlterada(f"{fonte.id}: cópia arquivada difere do manifesto")
        print(f"  ok {fonte.id}")
    print(f"{len(eleicao.fontes)} fontes conferidas com o manifesto")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("eleicao")
    ap.add_argument("--arquivo", action="store_true", help="baixar da cópia arquivada no GitHub")
    args = ap.parse_args()
    (do_arquivo if args.arquivo else do_tse)(args.eleicao)
