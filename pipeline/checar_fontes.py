"""Verifica se as fontes do TSE mudaram desde que foram registradas no manifesto.

Uso: uv run python -m pipeline.checar_fontes > relatorio.md

Não baixa os arquivos grandes:
- fontes com `.sha512` publicado: compara o hash publicado com o do manifesto;
- demais fontes do TSE: compara ETag, Last-Modified e tamanho (HEAD);
- procura no Portal de Dados Abertos boletins novos para a eleição (o TSE já
  publicou versões substitutas com outro nome de arquivo).

Saída: relatório em Markdown. Código de saída 0 = nada mudou, 1 = algo mudou,
2 = erro na verificação (rede, portal fora do ar).
"""

import json
import re
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse

from pipeline.fetch import cabecalhos_remotos, carregar_manifesto, sha512_publicado
from pipeline.fontes import ELEICOES, Eleicao

TENTATIVAS = 3


class ErroDeRede(Exception):
    pass


def _com_retentativas(f, url: str):
    for i in range(TENTATIVAS):
        try:
            return f()
        except urllib.error.HTTPError:
            raise
        except (urllib.error.URLError, OSError) as e:
            if i == TENTATIVAS - 1:
                raise ErroDeRede(f"{urlparse(url).netloc}: {e!r}") from e
            time.sleep(5 * (i + 1))


CKAN = "https://dadosabertos.tse.jus.br/api/3/action/package_show?id=resultados-{ano}-boletim-de-urna"


def _checar_fonte(fonte, registrado: dict) -> str | None:
    """Descrição da mudança, ou None se nada mudou."""
    try:
        if fonte.sha512_tse:
            publicado = _com_retentativas(lambda: sha512_publicado(fonte.url), fonte.url)
            if publicado != registrado["sha512"]:
                return f"SHA-512 publicado mudou: `{registrado['sha512'][:16]}…` → `{publicado[:16]}…`"
            return None
        atual = _com_retentativas(lambda: cabecalhos_remotos(fonte.url), fonte.url)
    except urllib.error.HTTPError as e:
        return f"arquivo indisponível no TSE (HTTP {e.code})"

    mudancas = [
        f"{campo}: `{registrado.get(campo)}` → `{atual[campo]}`"
        for campo in ("etag", "last_modified", "bytes")
        if atual[campo] != registrado.get(campo)
    ]
    return "; ".join(mudancas) or None


def _boletins_novos(eleicao: Eleicao) -> list[str]:
    url = CKAN.format(ano=eleicao.ano)

    def ler():
        with urllib.request.urlopen(url, timeout=60) as resp:
            return json.load(resp)["result"]["resources"]

    recursos = _com_retentativas(ler, url)
    padrao = re.compile(rf"/bweb_{eleicao.turno}t_[A-Z]{{2}}_\d+\.zip$")
    conhecidas = {f.url for f in eleicao.fontes}
    return sorted(
        r["url"] for r in recursos if padrao.search(r["url"]) and r["url"] not in conhecidas
    )


def main() -> int:
    linhas = ["# Verificação das fontes do TSE", ""]
    mudou = False
    erros: list[str] = []
    for eleicao in ELEICOES.values():
        manifesto = carregar_manifesto(eleicao.id)
        linhas.append(f"## {eleicao.id}")
        erros_antes = len(erros)
        for fonte in eleicao.fontes:
            if fonte.tipo == "terceiro":  # fixado por commit; não muda
                continue
            try:
                mudanca = _checar_fonte(fonte, manifesto[fonte.id])
            except ErroDeRede as e:
                erros.append(f"- {fonte.id}: {e}")
                continue
            if mudanca:
                mudou = True
                linhas.append(f"- **{fonte.id}** ({fonte.url}): {mudanca}")
        try:
            novos = _boletins_novos(eleicao)
        except ErroDeRede as e:
            erros.append(f"- portal de dados abertos: {e}")
            novos = []
        if novos:
            mudou = True
            linhas.append("- **boletins novos no portal**, não usados pelo build:")
            linhas.extend(f"  - {u}" for u in novos)
        if linhas[-1] == f"## {eleicao.id}":
            linhas.append("- sem mudanças" if len(erros) == erros_antes else "- verificação incompleta")
        linhas.append("")

    if mudou:
        linhas.append(
            "Próximo passo: baixar as fontes novas, rodar build e conciliação e comparar o "
            "`dist/`. Se os dados gerados forem idênticos, foi só uma regeração do arquivo; "
            "atualize o manifesto e a release de fontes. Se mudaram, revise o diff antes de publicar."
        )
    if erros:
        linhas += ["## Não foi possível verificar", "", *erros, ""]
    print("\n".join(linhas))
    if mudou:
        return 1
    return 2 if erros else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # rede, portal fora do ar etc.
        print(f"erro na verificação: {e!r}")
        sys.exit(2)
