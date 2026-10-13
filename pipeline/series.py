"""Reconstrução da apuração ao longo do tempo a partir dos boletins de urna.

Regras (documentadas em docs/metodo.md):
- Uma seção entra no placar no instante `max(DT_BU_RECEBIDO, início da divulgação)`:
  boletins recebidos antes das 17h (exterior) só aparecem quando o TSE abre a divulgação.
- Empates no mesmo segundo são ordenados por (UF, município, zona, seção), para que
  o resultado seja determinístico.
- Série por minuto: o ponto no instante T inclui todas as seções que entraram até T.
- Série por % apurado: o ponto p é o placar no momento em que o % de seções
  totalizadas atingiu p pela primeira vez.
"""

import math
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from pipeline.bweb import Secao


@dataclass
class Placar:
    secoes: int = 0
    aptos: int = 0
    comparecimento: int = 0
    votos: Counter = field(default_factory=Counter)

    def somar(self, s: Secao) -> None:
        self.secoes += 1
        self.aptos += s.aptos
        self.comparecimento += s.comparecimento
        self.votos.update(s.votos)

    def copia(self) -> "Placar":
        return Placar(self.secoes, self.aptos, self.comparecimento, Counter(self.votos))


@dataclass
class Ponto:
    t: datetime
    placar: Placar


def instante(s: Secao, inicio: datetime) -> datetime:
    return max(s.recebido, inicio)


def ordenar(secoes: list[Secao], inicio: datetime) -> list[Secao]:
    return sorted(secoes, key=lambda s: (instante(s, inicio), s.chave))


def serie_minuto(ordenadas: list[Secao], inicio: datetime) -> list[Ponto]:
    if not ordenadas:
        return [Ponto(inicio, Placar())]
    ultimo = instante(ordenadas[-1], inicio)
    minutos = math.ceil((ultimo - inicio).total_seconds() / 60)
    pontos: list[Ponto] = []
    placar = Placar()
    i = 0
    for m in range(minutos + 1):
        t = inicio + timedelta(minutes=m)
        while i < len(ordenadas) and instante(ordenadas[i], inicio) <= t:
            placar.somar(ordenadas[i])
            i += 1
        pontos.append(Ponto(t, placar.copia()))
    return pontos


def serie_pct(
    ordenadas: list[Secao], inicio: datetime, total_secoes: int, passo: float = 0.5
) -> list[tuple[float, Ponto]]:
    """Retorna (p, ponto) para p = 0, passo, 2·passo… até o maior % atingido."""
    resultado: list[tuple[float, Ponto]] = []
    placar = Placar()
    i = 0
    n_passos = round(100 / passo)
    for k in range(n_passos + 1):
        p = k * passo
        alvo = math.ceil(p * total_secoes / 100)
        while placar.secoes < alvo and i < len(ordenadas):
            placar.somar(ordenadas[i])
            i += 1
        if placar.secoes < alvo:
            break
        t = instante(ordenadas[i - 1], inicio) if i else inicio
        resultado.append((p, Ponto(t, placar.copia())))
    return resultado
