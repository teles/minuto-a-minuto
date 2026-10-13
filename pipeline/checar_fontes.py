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
import urllib.error
import urllib.request

from pipeline.fetch import cabecalhos_remotos, carregar_manifesto, sha512_publicado
from pipeline.fontes import ELEICOES, Eleicao

CKAN = "https://dadosabertos.tse.jus.br/api/3/action/package_show?id=resultados-{ano}-boletim-de-urna"


def _checar_fonte(fonte, registrado: dict) -> str | None:
    """Descrição da mudança, ou None se nada mudou."""
    try:
        if fonte.sha512_tse:
            publicado = sha512_publicado(fonte.url)
            if publicado != registrado["sha512"]:
                return f"SHA-512 publicado mudou: `{registrado['sha512'][:16]}…` → `{publicado[:16]}…`"
            return None
        atual = cabecalhos_remotos(fonte.url)
    except urllib.error.HTTPError as e:
        return f"arquivo indisponível no TSE (HTTP {e.code})"

    mudancas = [
        f"{campo}: `{registrado.get(campo)}` → `{atual[campo]}`"
        for campo in ("etag", "last_modified", "bytes")
        if atual[campo] != registrado.get(campo)
    ]
    return "; ".join(mudancas) or None


def _boletins_novos(eleicao: Eleicao) -> list[str]:
    with urllib.request.urlopen(CKAN.format(ano=eleicao.ano), timeout=60) as resp:
        recursos = json.load(resp)["result"]["resources"]
    padrao = re.compile(rf"/bweb_{eleicao.turno}t_[A-Z]{{2}}_\d+\.zip$")
    conhecidas = {f.url for f in eleicao.fontes}
    return sorted(
        r["url"] for r in recursos if padrao.search(r["url"]) and r["url"] not in conhecidas
    )


def main() -> int:
    linhas = ["# Verificação das fontes do TSE", ""]
    mudou = False
    for eleicao in ELEICOES.values():
        manifesto = carregar_manifesto(eleicao.id)
        linhas.append(f"## {eleicao.id}")
        for fonte in eleicao.fontes:
            if fonte.tipo == "terceiro":  # fixado por commit; não muda
                continue
            mudanca = _checar_fonte(fonte, manifesto[fonte.id])
            if mudanca:
                mudou = True
                linhas.append(f"- **{fonte.id}** ({fonte.url}): {mudanca}")
        novos = _boletins_novos(eleicao)
        if novos:
            mudou = True
            linhas.append("- **boletins novos no portal**, não usados pelo build:")
            linhas.extend(f"  - {u}" for u in novos)
        if linhas[-1] == f"## {eleicao.id}":
            linhas.append("- sem mudanças")
        linhas.append("")

    if mudou:
        linhas.append(
            "Próximo passo: baixar as fontes novas, rodar build e conciliação e comparar o "
            "`dist/`. Se os dados gerados forem idênticos, foi só uma regeração do arquivo; "
            "atualize o manifesto e a release de fontes. Se mudaram, revise o diff antes de publicar."
        )
    print("\n".join(linhas))
    return 1 if mudou else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # rede, portal fora do ar etc.
        print(f"erro na verificação: {e!r}")
        sys.exit(2)
