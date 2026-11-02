"""
Armonizzazione di una melodia nuda: un lead sheet senza sigle.

Si usa SOLO quando il file porta la sola melodia. Se ci sono sigle o il
pianoforte, l'armonia del file vince sempre (vedi `analizzatore.analizza`).

Il procedimento segue Piston, *Armonia*, cap. 9 ("Armonizzazione di una
melodia"), con le regole dei capitoli 3, 4, 11, 12 e 16; i principi sono
riassunti nella sezione 5 di docs/principi_arrangiamento.md e citati qui
come P1-P12:

  1. tonalita' e modo, dalla chiusura delle frasi (P2);
  2. griglia del ritmo armonico: dove l'accordo PUO' cambiare (P3, P4);
  3. accordi candidati, dominanti secondarie solo se la melodia porta la
     loro sensibile (P12);
  4. punteggio di ogni candidato sulle note del tratto;
  5. frasi (rileva_frasi, senza armonia);
  6. Viterbi: tavola delle successioni (P6, P7) e premi di cadenza (P11);
  7. rivolti: il basso come linea (P8).

L'obiettivo, deciso col docente il 2/11/2026, e' avvicinarsi agli accordi
veri del brano: si misura con banco_armonia.py sui brani con le sigle.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Tuple

from .modello import Nota, Spartito


# --------------------------------------------------------------------------
# 2. Griglia del ritmo armonico
# --------------------------------------------------------------------------


@dataclass
class Tratto:
    """Un tratto della griglia: dentro, l'accordo non cambia."""

    inizio: float
    fine: float
    forza: int       # 2 = battere della misura, 1 = meta' misura, 0 = altro


def _tratti_per_misura(num: int, den: int) -> int:
    # nel pop l'accordo cambia spesso ogni due movimenti: in 4/4 si valuta
    # ogni mezza misura; nei metri brevi o ternari una volta per misura
    if (num, den) in ((4, 4), (2, 2), (12, 8)):
        return 2
    if (num, den) == (9, 8):
        return 3
    return 1


def griglia(sp: Spartito) -> List[Tratto]:
    """I punti in cui l'accordo puo' cambiare, misura per misura."""
    tratti: List[Tratto] = []
    for m in sp.misure:
        if m.parziale:
            # anacrusi e levare di sezione: un tratto solo, in levare
            tratti.append(Tratto(m.inizio, m.fine, 1))
            continue
        n = _tratti_per_misura(m.num, m.den)
        passo = m.durata / n
        for k in range(n):
            forza = 2 if k == 0 else (1 if n == 2 else 0)
            tratti.append(Tratto(m.inizio + k * passo,
                                 m.inizio + (k + 1) * passo, forza))
    return tratti


# --------------------------------------------------------------------------
# 1. Tonalita' e modo
# --------------------------------------------------------------------------


def _armatura_prevalente(sp: Spartito) -> int:
    durate: Dict[int, float] = defaultdict(float)
    for m in sp.misure:
        durate[m.tonalita] += m.durata
    return max(durate, key=lambda f: durate[f]) if durate else 0


def _forte(sp: Spartito, n: Nota) -> bool:
    """Nota lunga (almeno una minima) o sul battere / meta' misura."""
    if n.durata >= 2.0 - 1e-6:
        return True
    m = sp.misura_a(n.inizio)
    if m is None:
        return False
    rel = n.inizio - m.inizio
    return abs(rel) < 1e-6 or abs(rel - m.durata_piena / 2) < 1e-6


def tonalita_della_melodia(sp: Spartito, melodia: List[Nota],
                           frasi: List[Tuple[float, float]]) -> Tuple[int, str]:
    """
    (tonica come classe d'altezza, "maggiore" | "minore").

    Fra il maggiore dell'armatura e la sua relativa minore decide la
    chiusura (Piston P2): la nota finale del brano e delle frasi, la
    sensibile alzata del minore, le note lunghe o in battere che stanno
    nell'una o nell'altra triade di tonica. Nel dubbio vince il maggiore.
    """
    maggiore = (_armatura_prevalente(sp) * 7) % 12
    minore = (maggiore + 9) % 12
    if not melodia:
        return maggiore, "maggiore"
    note = sorted(melodia, key=lambda n: n.inizio)

    def punti(tonica: int, terza: int) -> float:
        p = 0.0
        ultima = note[-1].midi % 12
        if ultima == tonica:
            p += 2.0
        elif ultima == (tonica + 7) % 12:
            p += 1.0
        for _a, b in frasi:
            dentro = [n for n in note if n.inizio < b - 1e-6]
            if dentro and dentro[-1].midi % 12 == tonica:
                p += 1.0
        triade = {tonica, (tonica + terza) % 12, (tonica + 7) % 12}
        forti = [n for n in note if _forte(sp, n)]
        totale = sum(n.durata for n in forti) or 1.0
        p += sum(n.durata for n in forti if n.midi % 12 in triade) / totale
        return p

    p_magg = punti(maggiore, 4)
    p_min = punti(minore, 3)
    # la sensibile alzata (Sol# in La minore) e' il segno piu' chiaro del
    # minore: nel maggiore relativo quella nota non c'e'
    if any(n.midi % 12 == (minore - 1) % 12 for n in note):
        p_min += 1.5
    if p_min - p_magg > 1.0:
        return minore, "minore"
    return maggiore, "maggiore"
