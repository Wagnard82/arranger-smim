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
from typing import Dict, List, Optional, Set, Tuple

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
    estranea: float = 1.0      # nota della melodia fuori dall'accordo
    passaggio: float = 0.15    # ...ma di passaggio o di volta (P5)
    forte: float = 0.3         # priorita' di I, IV, V (P7); meta' per ii
    # costo di un cambio d'accordo secondo la forza del tratto d'arrivo:
    # sul battere poco, a meta' misura di piu', altrove molto (P4)
    cambio: Tuple[float, float, float] = (0.25, 1.4, 1.6)
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

_MOLT_INIZIO = 1.2    # nota che attacca all'inizio del tratto
_PASSAGGIO_IN_ACCORDO = 0.3
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
            peso *= _MOLT_INIZIO
        elif n.inizio > tratto.inizio and abs((n.inizio - tratto.inizio) % 1.0) < 1e-6:
            peso *= 1.2
        # la meta' misura resta un tempo debole rispetto al battere
        debole = n.inizio > tratto.inizio + 1e-6 or tratto.forza < 2
        passa = debole and 0 < i < len(ordinate) - 1 \
            and _di_passaggio(n, ordinate[i - 1], ordinate[i + 1])
        if n.midi % 12 in note_acc:
            # una nota di passaggio non decide l'armonia (P5): conta poco
            # anche quando sta nell'accordo
            s += peso * (_PASSAGGIO_IN_ACCORDO if passa else 1.0)
        elif passa:
            s -= peso * pesi.passaggio
        else:
            s -= peso * pesi.estranea
    return s


# --------------------------------------------------------------------------
# 6. Successioni, cadenze e Viterbi
# --------------------------------------------------------------------------

# Piston, tavola delle successioni abituali (cap. 3) e aggiunte del modo
# minore (cap. 4): grado -> (di solito, a volte, meno spesso)
TAVOLA: Dict[str, Dict[str, Tuple[Tuple[str, ...], ...]]] = {
    "maggiore": {
        "I": (("IV", "V"), ("vi",), ("ii", "iii")),
        "ii": (("V",), ("IV", "vi"), ("I", "iii")),
        "iii": (("vi",), ("IV",), ("I", "ii", "V")),
        "IV": (("V",), ("I", "ii"), ("iii", "vi")),
        "V": (("I",), ("IV", "vi"), ("ii", "iii")),
        "vi": (("ii", "V"), ("iii", "IV"), ("I",)),
        "vii": (("I", "iii"), ("vi",), ("ii", "IV", "V")),
    },
    "minore": {
        "i": (("iv", "V"), ("VI", "VII"), ("ii", "III")),
        "ii": (("V",), ("iv", "VI"), ("i", "III")),
        "III": (("VI",), ("iv", "VII"), ("i", "ii", "V")),
        "iv": (("V",), ("i", "ii"), ("III", "VI")),
        "V": (("i",), ("iv", "VI"), ("ii", "III")),
        "VI": (("ii", "V"), ("III", "iv"), ("i",)),
        "VII": (("III",), ("VI",), ("iv",)),
        "vii": (("i",), (), ()),
    },
}


def _base(grado: str) -> str:
    """Il grado della tavola: V7 vale V."""
    return "V" if grado == "V7" else grado


def costo_successione(da: Candidato, a: Candidato, modo: str, pesi: Pesi) -> float:
    """Costo della successione da -> a secondo la tavola (P6, P12)."""
    if da.secondaria:
        # la dominante secondaria va al suo grado (V/V -> V), altro e' raro
        bersaglio = da.grado.split("/")[1]
        return pesi.abituale if _base(a.grado) == bersaglio else pesi.raro
    if a.secondaria:
        return pesi.a_volte
    solito, a_volte, raro = TAVOLA[modo].get(_base(da.grado), ((), (), ()))
    g = _base(a.grado)
    if g in solito:
        return pesi.abituale
    if g in a_volte:
        return pesi.a_volte
    if g in raro:
        return pesi.raro
    return pesi.assente


def _note_accordo(c: Candidato) -> Set[int]:
    return set(Accordo(inizio=0, durata=1, fondamentale=c.fondamentale,
                       qualita=c.qualita).note_accordo())


def armonizza(sp: Spartito, melodia: List[Nota],
              pesi: Optional[Pesi] = None) -> List[Accordo]:
    """
    L'armonia proposta per la sola melodia: un Accordo per ogni tratto in
    cui l'accordo cambia. Viterbi su tutto il brano: emissione delle note
    (fase 4), costo dei cambi secondo la posizione e la tavola, premi di
    cadenza a fine frase (fase 6), poi i rivolti (fase 7).
    """
    from .analizzatore import rileva_frasi     # qui: import circolare
    pesi = pesi or Pesi()
    tratti = griglia(sp)
    if not tratti:
        return []
    note = sorted(melodia, key=lambda n: n.inizio)
    frasi = rileva_frasi(sp, note) if note else []
    tonica, modo = tonalita_della_melodia(sp, note, frasi)
    cands = candidati(tonica, modo, note)
    k_c = len(cands)

    # emissioni; i tratti senza melodia non dicono niente (0 a tutti): il
    # costo di cambio tiene l'accordo precedente
    emissioni: List[List[float]] = []
    for t in tratti:
        vicine = [n for n in note if n.fine > t.inizio - 4 and n.inizio < t.fine + 4]
        dentro = any(n.inizio < t.fine - 1e-6 and n.fine > t.inizio + 1e-6 for n in vicine)
        emissioni.append([emissione(t, c, vicine, pesi) if dentro else 0.0
                          for c in cands])

    def indici(*gradi: str) -> List[int]:
        return [j for j, c in enumerate(cands) if c.grado in gradi]
    tonali = indici("I", "i")
    dominanti = indici("V", "V7")
    sottodom = indici("IV", "iv")

    # il brano comincia sulla tonica, se la melodia non dice altro
    for j in tonali:
        emissioni[0][j] += pesi.cadenza * 0.5

    # cadenze a fine frase (P11)
    def ultimo_tratto(b: float) -> int:
        return max((k for k, t in enumerate(tratti) if t.inizio < b - 1e-6), default=0)
    for f, (_a, b) in enumerate(frasi):
        finali = [n for n in note if n.inizio < b - 1e-6]
        if not finali:
            continue
        ultima = finali[-1]
        grado = (ultima.midi - tonica) % 12
        k = ultimo_tratto(b)
        ultima_frase = f == len(frasi) - 1
        premio = pesi.cadenza * (2.0 if ultima_frase else 1.0)
        if grado == 0 and (ultima.durata >= 1.0 - 1e-6 or ultima_frase):
            for j in tonali:
                emissioni[k][j] += premio
            if k > 0:
                for j in dominanti:
                    emissioni[k - 1][j] += premio
                for j in sottodom:
                    emissioni[k - 1][j] += premio * 0.5
        elif grado in (2, 11) or (modo == "minore" and grado == 11):
            for j in dominanti:
                emissioni[k][j] += premio
        elif grado == 7:
            for j in dominanti + tonali:
                emissioni[k][j] += premio * 0.5

    # salti (P3): una sola armonia per le due note del salto, a meno che la
    # prima cada su un tempo debole; e le note tenute oltre il confine
    salto_su: Set[int] = set()
    tenute: Dict[int, Set[int]] = defaultdict(set)
    for k in range(1, len(tratti)):
        confine = tratti[k].inizio
        for i, n in enumerate(note):
            if n.inizio < confine - 1e-6 < n.fine - 2e-6:
                tenute[k].add(n.midi % 12)
            if abs(n.inizio - confine) < 1e-6 and i > 0:
                prima = note[i - 1]
                if abs(n.midi - prima.midi) > 2 \
                        and abs(prima.inizio - tratti[k - 1].inizio) < 1e-6:
                    salto_su.add(k)
    note_acc = [_note_accordo(c) for c in cands]
    successioni = [[costo_successione(cands[p], cands[j], modo, pesi)
                    for j in range(k_c)] for p in range(k_c)]

    punti = [emissioni[0][:]]
    da: List[List[int]] = [[0] * k_c]
    for k in range(1, len(tratti)):
        cambio = pesi.costo_cambio(tratti[k].forza) \
            + (pesi.salto if k in salto_su else 0.0)
        riga, prov = [], []
        for j in range(k_c):
            migliore, origine = punti[-1][j], j          # stesso accordo
            for p in range(k_c):
                if p == j:
                    continue
                costo = cambio + successioni[p][j]
                if tenute[k] & note_acc[p] & note_acc[j]:
                    costo -= cambio * 0.5
                valore = punti[-1][p] - costo
                if valore > migliore:
                    migliore, origine = valore, p
            riga.append(migliore + emissioni[k][j])
            prov.append(origine)
        punti.append(riga)
        da.append(prov)

    j = max(range(k_c), key=lambda x: punti[-1][x])
    scelte = [j]
    for k in range(len(tratti) - 1, 0, -1):
        j = da[k][j]
        scelte.append(j)
    scelte.reverse()

    accordi: List[Accordo] = []
    for t, j in zip(tratti, scelte):
        c = cands[j]
        if accordi and (accordi[-1].fondamentale, accordi[-1].qualita) \
                == (c.fondamentale, c.qualita):
            accordi[-1].durata = t.fine - accordi[-1].inizio
            continue
        accordi.append(Accordo(inizio=t.inizio, durata=t.fine - t.inizio,
                               fondamentale=c.fondamentale, qualita=c.qualita,
                               confidenza=0.5))
    return scegli_bassi(accordi, note, pesi)


# --------------------------------------------------------------------------
# 7. Rivolti: il basso come linea (P8)
# --------------------------------------------------------------------------

_RIVOLTO = 0.15          # a parita' di altro vince lo stato fondamentale
_CONTRARIO = 0.2         # premio per il moto contrario alla melodia
_RIPETUTO = 0.2          # stesso basso di prima su un accordo diverso


def _moto(da: int, a: int) -> int:
    """Il moto piu' breve fra due classi d'altezza, con il segno (-6..6)."""
    d = (a - da) % 12
    return d - 12 if d > 6 else d


def _costo_moto(d: int) -> float:
    d = abs(d)
    if d <= 2:
        return 0.0          # grado congiunto (o nota ripetuta)
    if d <= 4:
        return 0.3          # terza
    if d == 5:
        return 0.6          # quarta o quinta
    return 1.0              # tritono


def scegli_bassi(accordi: List[Accordo], melodia: List[Nota],
                 pesi: Pesi) -> List[Accordo]:
    """
    Sceglie per ogni accordo lo stato fondamentale o il primo rivolto,
    trattando il basso come una seconda melodia: grado congiunto e moto
    contrario alla melodia, niente basso fermo su accordi diversi. Il V e
    il I della cadenza finale restano in stato fondamentale. Il risultato
    va in `Accordo.basso` (slash chord) quando il basso non e' la
    fondamentale.

    Semplificazioni rispetto a Piston, da rivedere col docente: la quarta e
    sesta di cadenza e il limite delle tre seste parallele non sono ancora
    gestiti.
    """
    if not accordi:
        return []
    note = sorted(melodia, key=lambda n: n.inizio)

    def prima_nota(a: Accordo) -> Optional[int]:
        dentro = [n for n in note if a.inizio - 1e-6 <= n.inizio < a.fine - 1e-6]
        return dentro[0].midi if dentro else None

    def ultima_nota(a: Accordo) -> Optional[int]:
        dentro = [n for n in note if n.inizio < a.fine - 1e-6 and n.fine > a.inizio + 1e-6]
        return dentro[-1].midi if dentro else None

    def opzioni(i: int) -> List[int]:
        a = accordi[i]
        radice = a.fondamentale
        n = len(accordi)
        # cadenza finale: V - I in stato fondamentale (P11)
        if i == n - 1 or (i == n - 2 and (accordi[-1].fondamentale - radice) % 12 == 5):
            return [radice]
        pc = a.note_accordo()
        return [radice, pc[1]] if len(pc) > 1 else [radice]

    costi: List[Dict[int, float]] = [{b: (0.0 if b == accordi[0].fondamentale else _RIVOLTO)
                                      for b in opzioni(0)}]
    da: List[Dict[int, int]] = [{}]
    for i in range(1, len(accordi)):
        a, prec = accordi[i], accordi[i - 1]
        m1, m0 = prima_nota(a), ultima_nota(prec)
        riga, prov = {}, {}
        for b in opzioni(i):
            migliore, origine = None, None
            for bp, cp in costi[-1].items():
                d = _moto(bp, b)
                c = cp + _costo_moto(d)
                if b != a.fondamentale:
                    c += _RIVOLTO
                if d == 0 and (a.fondamentale, a.qualita) != (prec.fondamentale, prec.qualita):
                    c += _RIPETUTO
                if m1 is not None and m0 is not None and d != 0 and m1 != m0 \
                        and (d > 0) != (m1 > m0):
                    c -= _CONTRARIO
                if migliore is None or c < migliore:
                    migliore, origine = c, bp
            riga[b], prov[b] = migliore, origine
        costi.append(riga)
        da.append(prov)

    b = min(costi[-1], key=lambda x: costi[-1][x])
    bassi = [b]
    for i in range(len(accordi) - 1, 0, -1):
        b = da[i][b]
        bassi.append(b)
    bassi.reverse()
    return [Accordo(inizio=a.inizio, durata=a.durata, fondamentale=a.fondamentale,
                    qualita=a.qualita, confidenza=a.confidenza,
                    basso=None if b == a.fondamentale else b)
            for a, b in zip(accordi, bassi)]
