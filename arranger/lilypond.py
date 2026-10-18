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

from .esportatore import (DIV, cambi_di_sigla, fifths_scritti, scomponi,
                          sigla_scritta, taglia_su_misura)
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
                from .lingua import t as testo
                righe.append('  \\mark \\markup { \\italic "'
                             + testo("swing", self.p.lingua) + '" }')
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
        """
        Riga di sigle accordali (ChordNames) dalla griglia armonica.

        Si scrive misura per misura: ogni tratto si scompone in valori
        scrivibili, la sigla va sul primo e gli altri sono spazi (la sigla
        vale finche' non cambia). Prima si sommavano le durate anche oltre
        la stanghetta e se ne scriveva solo il primo frammento: la riga
        delle sigle perdeva tempo e scivolava rispetto alla musica.
        """
        misure = self.p.misure or []
        cambi = cambi_di_sigla(self.p.armonia)
        fuori: List[str] = []

        def tratto(sigla: Optional[str], durata: float) -> None:
            frammenti = scomponi(int(round(durata * DIV)))
            for k, (tipo, punti, _tm, _u) in enumerate(frammenti):
                valore = _durata_ly(tipo, punti)
                if k == 0 and sigla:
                    fuori.append(self._sigla_ly(sigla, durata, valore))
                else:
                    fuori.append("s" + valore)

        for m in misure:
            punti_m = sorted({m.inizio, m.fine}
                             | {c[0] for c in cambi if m.inizio < c[0] < m.fine}
                             | {c[1] for c in cambi if m.inizio < c[1] < m.fine})
            for a, b in zip(punti_m, punti_m[1:]):
                if b - a <= 1e-6:
                    continue
                attivo = next((c for c in cambi
                               if c[0] - 1e-6 <= a < c[1] - 1e-6), None)
                # la sigla si scrive dove l'accordo comincia, non a ogni misura
                nuovo = attivo is not None and abs(attivo[0] - a) < 1e-6
                tratto(sigla_scritta(attivo[2], m.tonalita) if nuovo else None,
                       b - a)
        return "  " + " ".join(fuori)

    def _sigla_ly(self, sigla: str, durata: float,
                  valore: Optional[str] = None) -> str:
        """'Gm7/D' -> 'sol:m7/re' in sintassi \\chordmode italiana."""
        import re
        m = re.match(r"^([A-G])([#b]?)(.*)$", sigla or "")
        if not m:
            return "s" + self._partial(durata)
        # il nome si ricava lettera per lettera, cosi' la grafia (Ab o G#)
        # resta quella della sigla, scelta secondo l'armatura
        lettere = {"C": "do", "D": "re", "E": "mi", "F": "fa", "G": "sol",
                   "A": "la", "B": "si"}
        alterazioni = {"#": "d", "b": "b", "": ""}
        radice = lettere[m.group(1)] + alterazioni[m.group(2)]
        resto = m.group(3)
        basso = None
        if "/" in resto:
            resto, b = resto.split("/", 1)
            bm = re.match(r"^([A-G])([#b]?)", b)
            if bm:
                basso = lettere[bm.group(1)] + alterazioni[bm.group(2)]
        qualita = {"": "", "m": ":m", "7": ":7", "m7": ":m7", "maj7": ":maj7",
                   "dim": ":dim", "aug": ":aug", "sus4": ":sus4", "6": ":6",
                   "m6": ":m6", "dim7": ":dim7", "m7b5": ":m7.5-"}.get(resto, "")
        testo = radice + (valore or self._partial(durata)) + qualita
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
