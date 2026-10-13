"""Baixa as fontes de uma eleição e confere a integridade.

Uso: uv run python -m pipeline.fetch 2022-2t

- Fontes com `.sha512` do TSE: o arquivo precisa bater com o hash publicado.
- Todas as fontes: o hash fica registrado em manifestos/<eleicao>.json. Se um
  arquivo já registrado mudar (o TSE às vezes regera datasets), o fetch falha
  em vez de seguir com dados diferentes dos que foram conciliados.
"""

import hashlib
import json
import shutil
import sys
import urllib.request
from pathlib import Path

from pipeline.fontes import ELEICOES, Fonte

RAIZ = Path(__file__).resolve().parent.parent
RAW = RAIZ / "data" / "raw"
MANIFESTOS = RAIZ / "manifestos"


class FonteAlterada(Exception):
    pass


def sha512_arquivo(caminho: Path) -> str:
    h = hashlib.sha512()
    with caminho.open("rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def _baixar(url: str, destino: Path) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_suffix(destino.suffix + ".part")
    with urllib.request.urlopen(url, timeout=120) as resp, tmp.open("wb") as f:
        shutil.copyfileobj(resp, f, 1 << 20)
    tmp.rename(destino)


def _sha512_publicado(url: str) -> str:
    with urllib.request.urlopen(url + ".sha512", timeout=60) as resp:
        return resp.read().decode("ascii").split()[0].lower()


def verificar_fonte(fonte: Fonte, registrado: dict | None) -> dict:
    caminho = RAW / fonte.destino
    if not caminho.exists():
        print(f"  baixando {fonte.url}")
        _baixar(fonte.url, caminho)
    sha = sha512_arquivo(caminho)

    if fonte.sha512_tse:
        publicado = _sha512_publicado(fonte.url)
        if sha != publicado:
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
    }


def main(eleicao_id: str) -> None:
    eleicao = ELEICOES[eleicao_id]
    arq_manifesto = MANIFESTOS / f"{eleicao_id}.json"
    anterior = {}
    if arq_manifesto.exists():
        anterior = {f["id"]: f for f in json.loads(arq_manifesto.read_text())["fontes"]}

    fontes = []
    for fonte in eleicao.fontes:
        fontes.append(verificar_fonte(fonte, anterior.get(fonte.id)))
        print(f"  ok {fonte.id}")

    MANIFESTOS.mkdir(exist_ok=True)
    arq_manifesto.write_text(
        json.dumps({"eleicao": eleicao_id, "fontes": fontes}, ensure_ascii=False, indent=2) + "\n"
    )
    print(f"{len(fontes)} fontes verificadas; manifesto em {arq_manifesto.relative_to(RAIZ)}")


if __name__ == "__main__":
    main(sys.argv[1])
