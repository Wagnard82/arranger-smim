"""
MODULO 4b - Esportazione LilyPond.

Converte una `Partitura` in sorgente `.ly` pronto per l'incisione, come
alternativa/complemento al MusicXML: e' il punto di aggancio per una pipeline
di generazione PDF gia' esistente.

Caratteristiche coperte:
  * anacrusi con \\partial
  * PianoStaff con graffa e due righi
  * DrumStaff per le percussioni non intonate
  * strumenti traspositori: si scrivono le altezze SCRITTE e l'armatura
    trasposta, coerentemente con l'export MusicXML
  * terzine (\\tuplet 3/2), legature di valore ai cambi di misura, punti
  * sigle accordali su ChordNames per la chitarra
  * articolazioni: staccato, accento, tenuto, tremolo, pizz.
  * nomi degli strumenti a inizio accollatura + abbreviazioni

Nomenclatura italiana (\\language "italiano"): do, re, mi, fa, sol, la, si.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import Dict, List, Optional, Tuple

from .esportatore import DIV, fifths_scritti, scomponi, taglia_su_misura
from .modello import Evento, Misura, Parte, Partitura
from .strumenti import PERC_MIDI, strumento

# --------------------------------------------------------------------------

NOMI_LY = ["do", "dod", "re", "mib", "mi", "fa", "fad", "sol", "sold", "la",
           "sib", "si"]
NOMI_LY_BEMOLLE = ["do", "reb", "re", "mib", "mi", "fa", "solb", "sol", "lab",
                   "la", "sib", "si"]

TIPI_LY = {"whole": "1", "half": "2", "quarter": "4", "eighth": "8",
           "16th": "16", "32nd": "32"}

TONICHE = {0: "do", 1: "sol", 2: "re", 3: "la", 4: "mi", 5: "si", 6: "fad",
           7: "dod", -1: "fa", -2: "sib", -3: "mib", -4: "lab", -5: "reb",
           -6: "solb", -7: "dob"}

DRUM_LY = {PERC_MIDI["grancassa"]: "bd", PERC_MIDI["rullante"]: "sn",
           PERC_MIDI["charleston"]: "hh", PERC_MIDI["charleston_aperto"]: "hho",
           PERC_MIDI["ride"]: "cymr", PERC_MIDI["piatto"]: "cymc",
           PERC_MIDI["tom"]: "tomml", PERC_MIDI["claves"]: "cl",
           PERC_MIDI["tamburello"]: "tamb"}

ARTICOLAZIONI = {"staccato": "-.", "accent": "->", "tenuto": "--"}


def _versione() -> str:
    from .versione import VERSIONE
    return VERSIONE


def altezza_ly(midi: int, fifths: int = 0) -> str:
    tavola = NOMI_LY_BEMOLLE if fifths < 0 else NOMI_LY
    nome = tavola[midi % 12]
    ottava = midi // 12 - 4          # do' = do centrale (MIDI 60)
    if ottava > 0:
        nome += "'" * ottava
    elif ottava < 0:
        nome += "," * (-ottava)
    return nome


def _frazione(quarti: float) -> Tuple[int, int]:
    """Durata in quarti -> frazione di semibreve (1.5 -> 3/8)."""
    from fractions import Fraction
    f = Fraction(quarti).limit_denominator(64) / 4
    return f.numerator, f.denominator


def _durata_ly(tipo: str, punti: int) -> str:
    return TIPI_LY.get(tipo, "4") + "." * punti


# --------------------------------------------------------------------------


class EsportatoreLilyPond:
    def __init__(self, part: Partitura, versione: str = "2.24.0"):
        self.p = part
        self.versione = versione

    # ------------------------------------------------------------------ API
    def sorgente(self) -> str:
        blocchi = [self._intestazione()]
        for i, parte in enumerate(self.p.parti):
            blocchi.append(self._musica_parte(parte, i))
        blocchi.append(self._partitura())
        return "\n".join(blocchi)

    def scrivi(self, percorso: str) -> str:
        with open(percorso, "w", encoding="utf-8") as f:
            f.write(self.sorgente())
        return percorso

    # --------------------------------------------------------- intestazione
    def _intestazione(self) -> str:
        titolo = self.p.titolo.replace('"', "'")
        sotto = (self.p.sottotitolo or "").replace('"', "'")
        comp = (self.p.compositore or "").replace('"', "'")
        return (f'\\version "{self.versione}"\n'
                '\\language "italiano"\n\n'
                "\\header {\n"
                f'  title = "{titolo}"\n'
                f'  subtitle = "{sotto}"\n'
                f'  composer = "{comp}"\n'
                f'  arranger = "Arranger SMIM {_versione()}"\n'
                '  tagline = ##f\n'
                "}\n\n"
                "\\paper {\n"
                "  indent = 22\\mm\n"
                "  short-indent = 14\\mm\n"
                "  ragged-last-bottom = ##t\n"
                "}\n")

    # ------------------------------------------------------------- musica
    def _var(self, parte: Parte, indice: int, suffisso: str = "") -> str:
        base = "".join(c for c in parte.id if c.isalpha())
        numero = "".join(c for c in parte.id if c.isdigit()) or "I"
        romani = {"1": "I", "2": "II", "3": "III", "4": "IV", "5": "V", "6": "VI"}
        return f"{base}{romani.get(numero, numero)}{suffisso}"

    def _musica_parte(self, parte: Parte, indice: int) -> str:
        st = strumento(parte.strumento)
        fuori = []
        if parte.righi == 2:
            for rigo in (1, 2):
                fuori.append(f"{self._var(parte, indice, 'Su' if rigo == 1 else 'Giu')} = "
                             "{\n" + self._corpo(parte, rigo) + "\n}\n")
        else:
            fuori.append(f"{self._var(parte, indice)} = " + "{\n"
                         + self._corpo(parte, 1) + "\n}\n")
        if parte.mostra_sigle:
            fuori.append(f"{self._var(parte, indice, 'Sigle')} = \\chordmode {{\n"
                         + self._sigle(parte) + "\n}\n")
        return "\n".join(fuori)

    def _corpo(self, parte: Parte, rigo: int) -> str:
        st = strumento(parte.strumento)
        misure = self.p.misure or [Misura(1, 0.0, 4.0)]
        armatura = fifths_scritti(misure[0].tonalita, parte.trasposizione)
        righe: List[str] = ["  \\set Staff.instrumentName = "
                            f'\\markup {{ "{parte.nome}" }}',
                            "  \\set Staff.shortInstrumentName = "
                            f'\\markup {{ "{parte.abbrev}" }}']
        if not st.percussione:
            righe.append(f"  \\key {TONICHE.get(armatura, 'do')} \\major")
        righe.append(f"  \\time {misure[0].num}/{misure[0].den}")
        if parte is self.p.parti[0]:
            righe.append(f"  \\tempo 4 = {int(self.p.bpm)}")
            if self.p.swing:
                righe.append('  \\mark \\markup { \\italic "Swing (crome in terzina)" }')
        if misure and misure[0].anacrusi:
            righe.append(f"  \\partial {self._partial(misure[0].durata)}")

        eventi = [e for e in parte.eventi if e.rigo == rigo] if parte.righi == 2 \
            else parte.eventi
        lunghezza_corrente: Optional[Tuple[int, int]] = None
        for i, m in enumerate(misure):
            # misure parziali interne (levare di sezione, battute spezzate):
            # LilyPond ha bisogno che la lunghezza della misura sia dichiarata,
            # altrimenti il controllo di battuta fallisce e tutto slitta
            if i > 0 and m.parziale:
                num, den = _frazione(m.durata)
                righe.append(f"  \\set Timing.measureLength = #(ly:make-moment {num}/{den})")
                lunghezza_corrente = (num, den)
            elif lunghezza_corrente is not None:
                righe.append(f"  \\set Timing.measureLength = "
                             f"#(ly:make-moment {m.num}/{m.den})")
                lunghezza_corrente = None
            righe.append("  " + self._misura(eventi, m, parte, armatura))
        return "\n".join(righe)

    def _partial(self, durata: float) -> str:
        frammenti = scomponi(int(round(durata * DIV)))
        if not frammenti:
            return "4"
        tipo, punti, _tm, _u = frammenti[0]
        return _durata_ly(tipo, punti)

    def _misura(self, eventi: List[Evento], m: Misura, parte: Parte,
                armatura: int) -> str:
        st = strumento(parte.strumento)
        pezzi = taglia_su_misura(eventi, m)
        fuori: List[str] = []
        terzina_aperta = False
        terzina_unita = 0        # per chiudere il gruppo sul movimento

        for e, legato_prima, legato_dopo in pezzi:
            frammenti = scomponi(int(round(e.durata * DIV)))
            for k, (tipo, punti, tm, _u) in enumerate(frammenti):
                ultimo = (k == len(frammenti) - 1)
                if tm and not terzina_aperta:
                    fuori.append("\\tuplet 3/2 {")
                    terzina_aperta, terzina_unita = True, 0
                elif terzina_aperta and not tm:
                    fuori.append("}")
                    terzina_aperta = False
                if tm:
                    terzina_unita += _u

                dur = _durata_ly(tipo, punti)
                if e.pausa:
                    fuori.append("r" + dur)
                    if terzina_aperta and terzina_unita % DIV == 0:
                        fuori.append("}")
                        terzina_aperta, terzina_unita = False, 0
                    continue

                if st.percussione:
                    nomi = [DRUM_LY.get(a, "sn") for a in e.altezze]
                elif len(e.altezze) > 1:
                    nomi = [altezza_ly(a + parte.trasposizione, armatura)
                            for a in sorted(e.altezze)]
                else:
                    nomi = [altezza_ly(e.altezze[0] + parte.trasposizione, armatura)]

                testa = nomi[0] if len(nomi) == 1 else "<" + " ".join(nomi) + ">"
                nota = testa + dur
                if k == 0 and e.articolazione:
                    if e.articolazione in ARTICOLAZIONI:
                        nota += ARTICOLAZIONI[e.articolazione]
                    elif e.articolazione == "tremolo":
                        nota += ":32"
                    elif e.articolazione == "pizzicato":
                        nota += '^\\markup { \\italic "pizz." }'
                if k == 0 and e.dinamica:
                    nota += f"\\{e.dinamica}"
                if k == 0 and e.gradazione:
                    nota += "\\<" if e.gradazione == "crescendo" else "\\>"
                if ultimo and e.fine_gradazione:
                    nota += "\\!"
                if (not ultimo) or legato_dopo:
                    nota += "~"
                fuori.append(nota)
                # una terzina per movimento: piu' leggibile di un'unica parentesi
                if terzina_aperta and terzina_unita % DIV == 0:
                    fuori.append("}")
                    terzina_aperta, terzina_unita = False, 0

        if terzina_aperta:
            fuori.append("}")
        return " ".join(fuori) + " |"

    def _sigle(self, parte: Parte) -> str:
        """Riga di sigle accordali (ChordNames) ricavata dagli eventi."""
        misure = self.p.misure or []
        fuori: List[str] = []
        corrente: Optional[str] = None
        accumulo = 0.0
        for m in misure:
            for e, _lp, _ld in taglia_su_misura(parte.eventi, m):
                sigla = e.sigla if not e.pausa else None
                if sigla == corrente:
                    accumulo += e.durata
                    continue
                if corrente is not None and accumulo > 0:
                    fuori.append(self._sigla_ly(corrente, accumulo))
                elif accumulo > 0:
                    fuori.append("s" + self._partial(accumulo))
                corrente, accumulo = sigla, e.durata
        if accumulo > 0:
            fuori.append(self._sigla_ly(corrente, accumulo) if corrente
                         else "s" + self._partial(accumulo))
        return "  " + " ".join(fuori)

    def _sigla_ly(self, sigla: str, durata: float) -> str:
        """'Gm7/D' -> 'sol:m7/re' in sintassi \\chordmode italiana."""
        import re
        m = re.match(r"^([A-G])([#b]?)(.*)$", sigla or "")
        if not m:
            return "s" + self._partial(durata)
        pc = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}[m.group(1)]
        if m.group(2) == "#":
            pc += 1
        elif m.group(2) == "b":
            pc -= 1
        resto = m.group(3)
        basso = None
        if "/" in resto:
            resto, b = resto.split("/", 1)
            bm = re.match(r"^([A-G])([#b]?)", b)
            if bm:
                bp = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}[bm.group(1)]
                bp += 1 if bm.group(2) == "#" else (-1 if bm.group(2) == "b" else 0)
                basso = NOMI_LY[bp % 12]
        qualita = {"": "", "m": ":m", "7": ":7", "m7": ":m7", "maj7": ":maj7",
                   "dim": ":dim", "aug": ":aug", "sus4": ":sus4", "6": ":6",
                   "m6": ":m6", "dim7": ":dim7", "m7b5": ":m7.5-"}.get(resto, "")
        testo = NOMI_LY[pc % 12] + self._partial(durata) + qualita
        if basso:
            testo += "/" + basso
        return testo

    # ------------------------------------------------------------ \score
    def _partitura(self) -> str:
        righe = ["\\score {", "  <<"]
        gruppi: Dict[str, List[Tuple[int, Parte]]] = {}
        for i, parte in enumerate(self.p.parti):
            gruppi.setdefault(strumento(parte.strumento).famiglia, []).append((i, parte))

        for famiglia in ("fiati", "ottoni", "percussioni", "tastiere", "corde", "archi"):
            membri = gruppi.get(famiglia)
            if not membri:
                continue
            multiplo = len(membri) > 1
            if multiplo:
                righe.append("    \\new StaffGroup <<")
            for i, parte in membri:
                righe.extend("      " + r for r in self._rigo(parte, i))
            if multiplo:
                righe.append("    >>")

        righe.append("  >>")
        righe.append("  \\layout { }")
        righe.append(f"  \\midi {{ \\tempo 4 = {int(self.p.bpm)} }}")
        righe.append("}")
        return "\n".join(righe)

    def _rigo(self, parte: Parte, indice: int) -> List[str]:
        st = strumento(parte.strumento)
        v = self._var(parte, indice)
        if st.percussione:
            return [f"\\new DrumStaff \\drummode {{ \\{v} }}"]
        if parte.righi == 2:
            return ["\\new PianoStaff <<",
                    f'  \\new Staff = "su" {{ \\clef treble \\{v}Su }}',
                    f'  \\new Staff = "giu" {{ \\clef bass \\{v}Giu }}',
                    ">>"]
        clef = {"F": "bass", "C": "alto"}.get(parte.chiave, "treble")
        if parte.ottava_chiave == -1:
            clef = '"treble_8"'
        blocco = []
        if parte.mostra_sigle:
            blocco.append("\\new ChordNames { \\" + v + "Sigle }")
        blocco.append(f"\\new Staff {{ \\clef {clef} \\{v} }}")
        return blocco


# --------------------------------------------------------------------------


def esporta_lilypond(part: Partitura, percorso: str) -> str:
    return EsportatoreLilyPond(part).scrivi(percorso)


def incidi_pdf(percorso_ly: str, cartella: Optional[str] = None,
               eseguibile: str = "lilypond", timeout: int = 180) -> str:
    """
    Lancia LilyPond sul sorgente e restituisce il percorso del PDF.
    Solleva RuntimeError se l'eseguibile non e' installato o l'incisione fallisce.
    """
    binario = shutil.which(eseguibile)
    if binario is None:
        raise RuntimeError(
            "LilyPond non trovato nel PATH. Installalo da lilypond.org "
            "oppure passa il percorso completo dell'eseguibile.")
    cartella = cartella or os.path.dirname(os.path.abspath(percorso_ly))
    base = os.path.splitext(os.path.basename(percorso_ly))[0]
    esito = subprocess.run(
        [binario, "-o", os.path.join(cartella, base), percorso_ly],
        capture_output=True, text=True, timeout=timeout)
    pdf = os.path.join(cartella, base + ".pdf")
    if esito.returncode != 0 or not os.path.exists(pdf):
        raise RuntimeError("Incisione fallita:\n" + (esito.stderr or esito.stdout)[-2000:])
    return pdf
