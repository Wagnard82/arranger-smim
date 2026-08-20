"""
MODULO 4 - Esportazione.

Assembla le parti validate in una Full Score e genera MusicXML 4.0 partwise
(apribile in Dorico, Sibelius, MuseScore, Finale) + un MIDI di anteprima.

Scritto su stdlib: nessuna dipendenza esterna, output deterministico.
"""

from __future__ import annotations

import struct
from typing import Dict, List, Optional, Tuple
from xml.sax.saxutils import escape

from .modello import Evento, Misura, Parte, Partitura
from .strumenti import strumento

DIV = 24  # divisioni per quarto: consente 32esimi (3) e terzine di croma (8)

# unita' -> (tipo, punti, time-modification)
TABELLA: List[Tuple[int, str, int, Optional[Tuple[int, int]]]] = [
    (96, "whole", 0, None),
    (72, "half", 1, None),
    (48, "half", 0, None),
    (36, "quarter", 1, None),
    (24, "quarter", 0, None),
    (18, "eighth", 1, None),
    (16, "quarter", 0, (3, 2)),
    (12, "eighth", 0, None),
    (9, "16th", 1, None),
    (8, "eighth", 0, (3, 2)),
    (6, "16th", 0, None),
    (4, "16th", 0, (3, 2)),
    (3, "32nd", 0, None),
]

PASSI = ["C", "C", "D", "D", "E", "F", "F", "G", "G", "A", "A", "B"]
ALTER_DIESIS = [0, 1, 0, 1, 0, 0, 1, 0, 1, 0, 1, 0]
PASSI_BEM = ["C", "D", "D", "E", "E", "F", "G", "G", "A", "A", "B", "B"]
ALTER_BEM = [0, -1, 0, -1, 0, 0, -1, 0, -1, 0, -1, 0]

PERC_DISPLAY = {36: ("F", 4), 35: ("F", 4), 38: ("C", 5), 40: ("C", 5),
                42: ("G", 5), 46: ("G", 5), 51: ("F", 5), 49: ("A", 5),
                45: ("E", 4), 47: ("D", 5), 54: ("C", 5), 75: ("C", 5)}


# --------------------------------------------------------------------------


def midi_a_pitch(midi: int, fifths: int = 0) -> Tuple[str, int, int]:
    pc = midi % 12
    ott = midi // 12 - 1
    if fifths < 0:
        passo, alter = PASSI_BEM[pc], ALTER_BEM[pc]
        if pc in (0, 5) and alter == 0:
            pass
    else:
        passo, alter = PASSI[pc], ALTER_DIESIS[pc]
    return passo, alter, ott


def fifths_scritti(fifths_reali: int, trasposizione: int) -> int:
    """Armatura di chiave della PARTE trasposta (clarinetto in Sib, sax, tromba)."""
    f = fifths_reali + (7 * trasposizione) % 12
    while f > 7:
        f -= 12
    while f < -7:
        f += 12
    return f


VOLUMI = {"pppp": 10, "ppp": 20, "pp": 30, "p": 45, "mp": 60, "mf": 75,
          "f": 90, "ff": 105, "fff": 118, "ffff": 125}


def _volume(segno: str) -> int:
    return VOLUMI.get(segno, 80)


def _unita(q: float) -> int:
    return int(round(q * DIV))


def scomponi(unita: int) -> List[Tuple[str, int, Optional[Tuple[int, int]], int]]:
    """Spezza una durata in valori notabili: [(tipo, punti, timemod, unita)]."""
    out = []
    resto = unita
    guardia = 0
    while resto > 0 and guardia < 64:
        guardia += 1
        for u, tipo, punti, tm in TABELLA:
            if u <= resto:
                out.append((tipo, punti, tm, u))
                resto -= u
                break
        else:
            break
    return out


# --------------------------------------------------------------------------


class EsportatoreMusicXML:
    def __init__(self, part: Partitura):
        self.p = part

    # ------------------------------------------------------------------ API
    def xml(self) -> str:
        righe: List[str] = []
        righe.append('<?xml version="1.0" encoding="UTF-8"?>')
        righe.append('<!DOCTYPE score-partwise PUBLIC '
                     '"-//Recordare//DTD MusicXML 4.0 Partwise//EN" '
                     '"http://www.musicxml.org/dtds/partwise.dtd">')
        righe.append('<score-partwise version="4.0">')
        righe.append("  <work>")
        righe.append(f"    <work-title>{escape(self.p.titolo)}</work-title>")
        righe.append("  </work>")
        righe.append("  <identification>")
        if self.p.compositore:
            righe.append(f'    <creator type="composer">{escape(self.p.compositore)}</creator>')
        righe.append("    <encoding>")
        righe.append("      <software>Arranger SMIM</software>")
        righe.append("    </encoding>")
        righe.append("  </identification>")
        righe.append("  <movement-title>"
                     f"{escape(self.p.sottotitolo or self.p.titolo)}</movement-title>")
        righe.extend(self._part_list())
        for parte in self.p.parti:
            righe.extend(self._parte(parte))
        righe.append("</score-partwise>")
        return "\n".join(righe)

    def scrivi(self, percorso: str) -> str:
        with open(percorso, "w", encoding="utf-8") as f:
            f.write(self.xml())
        return percorso

    # ------------------------------------------------------------ part-list
    def _part_list(self) -> List[str]:
        r = ["  <part-list>"]
        for i, parte in enumerate(self.p.parti):
            st = strumento(parte.strumento)
            pid = f"P{i + 1}"
            parte_id = pid
            setattr(parte, "_xml_id", parte_id)
            r.append(f'    <score-part id="{pid}">')
            r.append(f"      <part-name>{escape(parte.nome)}</part-name>")
            r.append(f"      <part-abbreviation>{escape(parte.abbrev)}</part-abbreviation>")
            r.append(f'      <score-instrument id="{pid}-I1">')
            r.append(f"        <instrument-name>{escape(parte.nome)}</instrument-name>")
            r.append("      </score-instrument>")
            r.append(f'      <midi-instrument id="{pid}-I1">')
            r.append(f"        <midi-channel>{10 if st.percussione else (i % 8) + 1}"
                     "</midi-channel>")
            r.append(f"        <midi-program>{parte.programma_midi + 1}</midi-program>")
            r.append("        <volume>80</volume><pan>0</pan>")
            r.append("      </midi-instrument>")
            r.append("    </score-part>")
        r.append("  </part-list>")
        return r

    # ---------------------------------------------------------------- parte
    def _parte(self, parte: Parte) -> List[str]:
        st = strumento(parte.strumento)
        pid = getattr(parte, "_xml_id", "P1")
        r = [f'  <part id="{pid}">']
        misure = self.p.misure or [Misura(1, 0.0, 4.0)]
        righi = 2 if parte.righi == 2 else 1

        for idx, m in enumerate(misure):
            numero = m.numero if not m.anacrusi else 0
            attrs = 'implicit="yes"' if m.anacrusi else ""
            r.append(f'    <measure number="{numero}" {attrs}>'.replace(" >", ">"))
            if idx == 0:
                r.extend(self._attributi(parte, m, righi))
                r.extend(self._direzioni_iniziali(parte))
            else:
                prec = misure[idx - 1]
                if (m.num, m.den) != (prec.num, prec.den) or m.tonalita != prec.tonalita:
                    r.append("      <attributes>")
                    if m.tonalita != prec.tonalita:
                        r.append("        <key><fifths>"
                                 f"{fifths_scritti(m.tonalita, parte.trasposizione)}"
                                 "</fifths></key>")
                    if (m.num, m.den) != (prec.num, prec.den):
                        r.append(f"        <time><beats>{m.num}</beats>"
                                 f"<beat-type>{m.den}</beat-type></time>")
                    r.append("      </attributes>")

            for rigo in range(1, righi + 1):
                if rigo > 1:
                    dur = _unita(m.durata)
                    r.append(f"      <backup><duration>{dur}</duration></backup>")
                r.extend(self._voce(parte, m, rigo, righi))
            r.append("    </measure>")
        r.append("  </part>")
        return r

    def _attributi(self, parte: Parte, m: Misura, righi: int) -> List[str]:
        st = strumento(parte.strumento)
        armatura = fifths_scritti(m.tonalita, parte.trasposizione)
        r = ["      <attributes>",
             f"        <divisions>{DIV}</divisions>",
             f"        <key><fifths>{armatura}</fifths></key>",
             f"        <time><beats>{m.num}</beats><beat-type>{m.den}</beat-type></time>"]
        if righi == 2:
            r.append("        <staves>2</staves>")
            r.append('        <clef number="1"><sign>G</sign><line>2</line></clef>')
            r.append('        <clef number="2"><sign>F</sign><line>4</line></clef>')
        elif parte.chiave == "percussion":
            r.append("        <clef><sign>percussion</sign><line>2</line></clef>")
        elif parte.chiave == "F":
            r.append("        <clef><sign>F</sign><line>4</line></clef>")
        elif parte.chiave == "C":
            r.append("        <clef><sign>C</sign><line>3</line></clef>")
        else:
            r.append("        <clef><sign>G</sign><line>2</line>" +
                     (f"<clef-octave-change>{parte.ottava_chiave}</clef-octave-change>"
                      if parte.ottava_chiave else "") + "</clef>")
        if parte.trasposizione:
            crom = parte.trasposizione
            diat = round(crom * 7 / 12)
            r.append("        <transpose>")
            r.append(f"          <diatonic>{-diat}</diatonic>")
            r.append(f"          <chromatic>{-crom}</chromatic>")
            if abs(crom) >= 12:
                r.append(f"          <octave-change>{-(crom // 12)}</octave-change>")
            r.append("        </transpose>")
        r.append("      </attributes>")
        return r

    def _direzioni_iniziali(self, parte: Parte) -> List[str]:
        r = []
        if parte is self.p.parti[0]:
            r.append('      <direction placement="above">')
            r.append("        <direction-type><metronome>"
                     "<beat-unit>quarter</beat-unit>"
                     f"<per-minute>{int(self.p.bpm)}</per-minute>"
                     "</metronome></direction-type>")
            r.append(f"        <sound tempo='{int(self.p.bpm)}'/>")
            r.append("      </direction>")
            if self.p.swing:
                r.append('      <direction placement="above">')
                r.append("        <direction-type><words>Swing (crome in terzina)"
                         "</words></direction-type>")
                r.append("      </direction>")
        return r

    # ----------------------------------------------------------------- voce
    def _voce(self, parte: Parte, m: Misura, rigo: int, righi: int) -> List[str]:
        r: List[str] = []
        eventi = [e for e in parte.eventi if e.rigo == rigo] if righi == 2 else parte.eventi
        pezzi = self._taglia(eventi, m)
        sigla_stampata: Optional[str] = None

        for e, legato_prima, legato_dopo in pezzi:
            unita = _unita(e.durata)
            if unita <= 0:
                continue
            if parte.mostra_sigle and e.sigla and e.sigla != sigla_stampata and not e.pausa:
                r.extend(self._armonia(e.sigla, m.tonalita))
                sigla_stampata = e.sigla
            if e.dinamica and not e.pausa:
                r.append('      <direction placement="below"><direction-type>'
                         f"<dynamics><{e.dinamica}/></dynamics>"
                         "</direction-type>"
                         f"<sound dynamics='{_volume(e.dinamica)}'/></direction>")
            if e.gradazione and not e.pausa:
                tipo = "crescendo" if e.gradazione == "crescendo" else "diminuendo"
                r.append('      <direction placement="below"><direction-type>'
                         f'<wedge type="{tipo}"/></direction-type></direction>')
            if e.articolazione in ("pizzicato", "tremolo") and not e.pausa:
                testo = "pizz." if e.articolazione == "pizzicato" else "trem."
                r.append('      <direction placement="above"><direction-type>'
                         f"<words>{testo}</words></direction-type></direction>")

            frammenti = scomponi(unita)
            if not frammenti:
                continue
            if e.fine_gradazione and not e.pausa:
                chiusura = ('      <direction placement="below"><direction-type>'
                            '<wedge type="stop"/></direction-type></direction>')
            else:
                chiusura = None
            for k, (tipo, punti, tm, u) in enumerate(frammenti):
                ultimo = (k == len(frammenti) - 1)
                if e.pausa:
                    r.extend(self._nota_xml(None, u, tipo, punti, tm, rigo, righi,
                                            parte, False, False, None))
                else:
                    for j, altezza in enumerate(sorted(e.altezze)):
                        r.extend(self._nota_xml(
                            altezza, u, tipo, punti, tm, rigo, righi, parte,
                            accordo=(j > 0),
                            legatura_inizio=(legato_dopo and ultimo) or not ultimo,
                            legatura_fine=(legato_prima and k == 0) or k > 0,
                            articolazione=e.articolazione if (k == 0 and j == 0) else None))
            if chiusura:
                r.append(chiusura)
        return r

    def _taglia(self, eventi: List[Evento], m: Misura
                ) -> List[Tuple[Evento, bool, bool]]:
        return taglia_su_misura(eventi, m)


    def _nota_xml(self, altezza: Optional[int], unita: int, tipo: str, punti: int,
                  tm: Optional[Tuple[int, int]], rigo: int, righi: int, parte: Parte,
                  accordo: bool, legatura_inizio: bool, legatura_fine: bool,
                  articolazione: Optional[str] = None) -> List[str]:
        st = strumento(parte.strumento)
        r = ["      <note>"]
        if accordo:
            r.append("        <chord/>")
        if altezza is None:
            r.append("        <rest/>")
        elif st.percussione:
            passo, ott = PERC_DISPLAY.get(altezza, ("C", 5))
            r.append("        <unpitched>")
            r.append(f"          <display-step>{passo}</display-step>")
            r.append(f"          <display-octave>{ott}</display-octave>")
            r.append("        </unpitched>")
        else:
            scritto = altezza + parte.trasposizione
            reali = self.p.misure[0].tonalita if self.p.misure else 0
            passo, alter, ott = midi_a_pitch(
                scritto, fifths_scritti(reali, parte.trasposizione))
            r.append("        <pitch>")
            r.append(f"          <step>{passo}</step>")
            if alter:
                r.append(f"          <alter>{alter}</alter>")
            r.append(f"          <octave>{ott}</octave>")
            r.append("        </pitch>")
        r.append(f"        <duration>{unita}</duration>")
        if altezza is not None:
            if legatura_fine:
                r.append('        <tie type="stop"/>')
            if legatura_inizio:
                r.append('        <tie type="start"/>')
        r.append(f"        <voice>{rigo}</voice>")
        r.append(f"        <type>{tipo}</type>")
        for _ in range(punti):
            r.append("        <dot/>")
        if tm:
            r.append("        <time-modification>")
            r.append(f"          <actual-notes>{tm[0]}</actual-notes>")
            r.append(f"          <normal-notes>{tm[1]}</normal-notes>")
            r.append("        </time-modification>")
        if righi == 2:
            r.append(f"        <staff>{rigo}</staff>")
        notazioni = []
        if altezza is not None and (legatura_inizio or legatura_fine):
            if legatura_fine:
                notazioni.append('          <tied type="stop"/>')
            if legatura_inizio:
                notazioni.append('          <tied type="start"/>')
        if articolazione in ("staccato", "accent", "tenuto"):
            notazioni.append("          <articulations>"
                             f"<{articolazione}/></articulations>")
        if articolazione == "tremolo":
            notazioni.append('          <ornaments><tremolo type="single">3</tremolo>'
                             "</ornaments>")
        if notazioni:
            r.append("        <notations>")
            r.extend(notazioni)
            r.append("        </notations>")
        r.append("      </note>")
        return r

    def _armonia(self, sigla: str, fifths: int) -> List[str]:
        import re
        m = re.match(r"^([A-G])([#b]?)(.*)$", sigla)
        if not m:
            return []
        passo, acc, resto = m.group(1), m.group(2), m.group(3)
        basso = None
        if "/" in resto:
            resto, b = resto.split("/", 1)
            basso = b
        tipi = {"": "major", "m": "minor", "7": "dominant", "m7": "minor-seventh",
                "maj7": "major-seventh", "dim": "diminished", "aug": "augmented",
                "sus4": "suspended-fourth", "6": "major-sixth", "m6": "minor-sixth",
                "dim7": "diminished-seventh", "m7b5": "half-diminished"}
        kind = tipi.get(resto, "major")
        r = ["      <harmony>", "        <root>",
             f"          <root-step>{passo}</root-step>"]
        if acc:
            r.append(f"          <root-alter>{1 if acc == '#' else -1}</root-alter>")
        r.append("        </root>")
        r.append(f'        <kind text="{escape(resto)}">{kind}</kind>')
        if basso:
            bm = __import__("re").match(r"^([A-G])([#b]?)", basso)
            if bm:
                r.append("        <bass>")
                r.append(f"          <bass-step>{bm.group(1)}</bass-step>")
                if bm.group(2):
                    r.append(f"          <bass-alter>"
                             f"{1 if bm.group(2) == '#' else -1}</bass-alter>")
                r.append("        </bass>")
        r.append("      </harmony>")
        return r



def taglia_su_misura(eventi: List[Evento], m: Misura
                     ) -> List[Tuple[Evento, bool, bool]]:
    """
    Ritaglia gli eventi sui confini di misura e segnala le legature di
    valore. Restituisce [(frammento, legato_prima, legato_dopo)] senza
    buchi. Usata sia dall'export MusicXML sia da quello LilyPond.
    """
    out = []
    for e in eventi:
        if e.fine <= m.inizio + 1e-6 or e.inizio >= m.fine - 1e-6:
            continue
        a = max(e.inizio, m.inizio)
        b = min(e.fine, m.fine)
        frammento = Evento(inizio=a, durata=b - a, altezze=list(e.altezze),
                           articolazione=e.articolazione, dinamica=e.dinamica,
                           sigla=e.sigla, rigo=e.rigo,
                           gradazione=e.gradazione if a <= e.inizio + 1e-6 else None,
                           fine_gradazione=e.fine_gradazione
                           and b >= e.fine - 1e-6)
        out.append((frammento, a > e.inizio + 1e-6, b < e.fine - 1e-6))
    out.sort(key=lambda x: x[0].inizio)
    # colma eventuali buchi con pause (robustezza)
    completo: List[Tuple[Evento, bool, bool]] = []
    t = m.inizio
    for fr, lp, ld in out:
        if fr.inizio > t + 1e-6:
            completo.append((Evento(inizio=t, durata=fr.inizio - t, altezze=[]), False, False))
        completo.append((fr, lp, ld))
        t = max(t, fr.fine)
    if m.fine - t > 1e-6:
        completo.append((Evento(inizio=t, durata=m.fine - t, altezze=[]), False, False))
    return completo


def esporta_musicxml(part: Partitura, percorso: str) -> str:
    return EsportatoreMusicXML(part).scrivi(percorso)


# --------------------------------------------------------------------------
# MIDI di anteprima
# --------------------------------------------------------------------------


def _vlq(n: int) -> bytes:
    out = bytearray([n & 0x7F])
    n >>= 7
    while n:
        out.insert(0, (n & 0x7F) | 0x80)
        n >>= 7
    return bytes(out)


def esporta_midi(part: Partitura, percorso: str, tpq: int = 480) -> str:
    tracce = []
    # traccia di tempo
    usec = int(60_000_000 / max(20.0, part.bpm))
    meta = b"\x00\xff\x51\x03" + usec.to_bytes(3, "big") + b"\x00\xff\x2f\x00"
    tracce.append(meta)

    for i, p in enumerate(part.parti):
        st = strumento(p.strumento)
        canale = 9 if st.percussione else (i % 15) + (1 if i % 15 >= 9 else 0)
        canale = min(15, canale)
        eventi: List[Tuple[int, int, int, int]] = []  # (tick, tipo, nota, vel)
        for e in p.eventi:
            if e.pausa:
                continue
            t0 = int(round(e.inizio * tpq))
            t1 = max(t0 + 1, int(round(e.fine * tpq)))
            for a in e.altezze:
                suono = a
                eventi.append((t0, 0x90, suono, 78))
                eventi.append((t1, 0x80, suono, 0))
        eventi.sort(key=lambda x: (x[0], x[1]))
        dati = bytearray()
        dati += b"\x00\xc0" if False else b""
        dati += b"\x00" + bytes([0xC0 | canale, p.programma_midi & 0x7F])
        prec = 0
        for t, tipo, nota, vel in eventi:
            dati += _vlq(max(0, t - prec))
            dati += bytes([tipo | canale, nota & 0x7F, vel])
            prec = t
        dati += b"\x00\xff\x2f\x00"
        tracce.append(bytes(dati))

    with open(percorso, "wb") as f:
        f.write(b"MThd" + struct.pack(">IHHH", 6, 1, len(tracce), tpq))
        for t in tracce:
            f.write(b"MTrk" + struct.pack(">I", len(t)) + t)
    return percorso
