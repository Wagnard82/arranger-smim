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

from .modello import Accordo, Nota, Spartito


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


# --------------------------------------------------------------------------
# Pesi (tarati con banco_armonia.py, vedi docs/principi_arrangiamento.md 5.2)
# --------------------------------------------------------------------------


@dataclass
class Pesi:
    estranea: float = 0.6      # nota della melodia fuori dall'accordo
    passaggio: float = 0.15    # ...ma di passaggio o di volta (P5)
    forte: float = 0.3         # priorita' di I, IV, V (P7); meta' per ii
    # costo di un cambio d'accordo secondo la forza del tratto d'arrivo:
    # sul battere poco, a meta' misura di piu', altrove molto (P4)
    cambio: Tuple[float, float, float] = (0.25, 0.45, 0.8)
    abituale: float = 0.0      # tavola delle successioni (P6)
    a_volte: float = 0.25
    raro: float = 0.6
    assente: float = 1.2
    salto: float = 0.4         # cambio dentro un salto da tempo debole (P3)
    cadenza: float = 1.0       # premio di cadenza a fine frase (P11)

    def costo_cambio(self, forza: int) -> float:
        return self.cambio[2 - max(0, min(2, forza))]


# --------------------------------------------------------------------------
# 3. Accordi candidati
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Candidato:
    fondamentale: int    # classe d'altezza
    qualita: str         # "maj", "min", "dim", "dom7"
    grado: str           # "I", "ii", "V7", "V/V"... per tavola e spiegazioni
    secondaria: bool = False


# (distanza dalla tonica, qualita', grado)
_DIATONICI = {
    "maggiore": ((0, "maj", "I"), (2, "min", "ii"), (4, "min", "iii"),
                 (5, "maj", "IV"), (7, "maj", "V"), (7, "dom7", "V7"),
                 (9, "min", "vi"), (11, "dim", "vii")),
    # Piston cap. 4: V maggiore con la sensibile, III e VII col settimo
    # grado naturale
    "minore": ((0, "min", "i"), (2, "dim", "ii"), (3, "maj", "III"),
               (5, "min", "iv"), (7, "maj", "V"), (7, "dom7", "V7"),
               (8, "maj", "VI"), (10, "maj", "VII"), (11, "dim", "vii")),
}
# dominanti secondarie: (grado tonicizzato, sua distanza dalla tonica, anche
# la triade?). Senza triade quando coincide con un accordo della tonalita'
# (V/IV in maggiore e' il I; V/VI in minore e' il III): resta la settima.
_SECONDARIE = {
    "maggiore": (("ii", 2, True), ("iii", 4, True), ("IV", 5, False),
                 ("V", 7, True), ("vi", 9, True)),
    "minore": (("iv", 5, True), ("V", 7, True), ("VI", 8, False)),
}


def _sensibile_che_sale(note: List[Nota], sensibile: int) -> bool:
    """La nota `sensibile` seguita entro 2 quarti dal semitono sopra (P12)."""
    ordinate = sorted(note, key=lambda n: n.inizio)
    for i, n in enumerate(ordinate):
        if n.midi % 12 != sensibile:
            continue
        for dopo in ordinate[i + 1:]:
            if dopo.inizio - n.inizio > 2.0 + 1e-6:
                break
            if dopo.midi % 12 == (sensibile + 1) % 12:
                return True
    return False


def candidati(tonica: int, modo: str, note: List[Nota]) -> List[Candidato]:
    """
    Gli accordi fra cui scegliere. Le dominanti secondarie entrano solo se
    nel brano la loro sensibile sale al semitono sopra: una nota alterata
    che scende e' cromatismo melodico, non una tonicizzazione (P12).
    """
    fuori = [Candidato((tonica + d) % 12, q, g)
             for d, q, g in _DIATONICI[modo]]
    for grado, d, triade in _SECONDARIE[modo]:
        radice = (tonica + d + 7) % 12
        if not _sensibile_che_sale(note, (radice + 4) % 12):
            continue
        if triade:
            fuori.append(Candidato(radice, "maj", f"V/{grado}", True))
        fuori.append(Candidato(radice, "dom7", f"V7/{grado}", True))
    return fuori


# --------------------------------------------------------------------------
# 4. Punteggio di un candidato su un tratto
# --------------------------------------------------------------------------

_FORTI = {"I": 1.0, "IV": 1.0, "V": 1.0, "V7": 1.0, "i": 1.0, "iv": 1.0,
          "ii": 0.5}


def _di_passaggio(n: Nota, prima: Nota, dopo: Nota) -> bool:
    """Arriva e riparte per grado congiunto, ed e' breve (P5)."""
    return (1 <= abs(n.midi - prima.midi) <= 2 and 1 <= abs(dopo.midi - n.midi) <= 2
            and n.durata <= 1.0 + 1e-6)


def emissione(tratto: Tratto, c: Candidato, melodia: List[Nota], pesi: Pesi) -> float:
    """
    Quanto il candidato `c` spiega le note della melodia nel tratto: le
    note dell'accordo sommano il loro peso (durata, di piu' se attaccano
    all'inizio del tratto o su un movimento), le estranee lo tolgono, meno
    se sono di passaggio o di volta su un tempo debole.
    """
    note_acc = set(Accordo(inizio=0, durata=1, fondamentale=c.fondamentale,
                           qualita=c.qualita).note_accordo())
    ordinate = sorted(melodia, key=lambda n: n.inizio)
    s = pesi.forte * _FORTI.get(c.grado, 0.0)
    for i, n in enumerate(ordinate):
        a, b = max(n.inizio, tratto.inizio), min(n.fine, tratto.fine)
        if b <= a + 1e-6:
            continue
        peso = b - a
        if abs(n.inizio - tratto.inizio) < 1e-6:
            peso *= 1.5
        elif n.inizio > tratto.inizio and abs((n.inizio - tratto.inizio) % 1.0) < 1e-6:
            peso *= 1.2
        if n.midi % 12 in note_acc:
            s += peso
            continue
        debole = n.inizio > tratto.inizio + 1e-6
        if debole and 0 < i < len(ordinate) - 1 \
                and _di_passaggio(n, ordinate[i - 1], ordinate[i + 1]):
            s -= peso * pesi.passaggio
        else:
            s -= peso * pesi.estranea
    return s
