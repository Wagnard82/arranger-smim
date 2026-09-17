"""
Rilevamento dei confini di frase con music21 (opzionale).

Il motore di base lavora senza dipendenze e ricava i confini da respiro,
allungamento, cadenza e metrica. music21 pero' porta in dote informazioni che
un parser MusicXML minimale non estrae: legature di portamento, corone, segni
di respiro, articolazioni, e un'analisi armonica gia' pronta. Dove sono
disponibili, i tagli diventano molto piu' musicali.

Il modulo e' diviso in due parti, e la divisione non e' cosmetica:

  * `estrai_contesto` richiede music21 e traduce lo `Stream` in una struttura
    neutra (`Contesto`);
  * `valuta_confini` e `scegli_tagli` sono **Python puro** e lavorano solo sul
    `Contesto`.

Cosi' la logica - che e' la parte in cui si sbaglia - resta testabile senza
installare nulla, e music21 serve solo a leggere il file.

Uso tipico:

    from music21 import converter
    from arranger.frasi_music21 import punti_di_scambio

    partitura = converter.parse("brano.musicxml")
    tagli = punti_di_scambio(partitura, misure_minime=4, misure_massime=8)

`tagli` e' la lista degli offset (in quarti) dove passare la melodia a un altro
strumento, gia' filtrata: mai dentro una legatura, mai dentro un gruppo di
valore, e con la distanza minima richiesta.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

# --------------------------------------------------------------------------
# Pesi delle euristiche.
#
# Sono tarati perche' un solo indizio forte (una corona, un respiro segnato)
# basti a decidere, mentre gli indizi deboli (la metrica da sola) debbano
# sommarsi. Cambiarli e' il primo posto in cui mettere le mani se i tagli non
# convincono su un certo repertorio.
# --------------------------------------------------------------------------

PESI = {
    "respiro_segnato": 2.20,    # BreathMark: e' una didascalia esplicita
    "corona": 2.00,             # Fermata: la frase finisce qui, senza dubbi
    "pausa": 1.30,              # pausa di durata rilevante
    "allungamento": 1.00,       # nota lunga in chiusura
    "cadenza_perfetta": 1.20,   # V - I
    "semicadenza": 0.60,        # arrivo sulla dominante
    "salto": 0.70,              # intervallo ampio, meglio se cambia direzione
    "cambio_direzione": 0.25,
    "staccato_finale": 0.40,
    "cambio_dinamica": 0.55,
    "ripetizione": 0.90,        # inizio di una ripetizione motivica
    "metrica_8": 0.55,
    "metrica_4": 0.40,
    "metrica_2": 0.15,
}

DURATA_PAUSA_RILEVANTE = 0.5    # in quarti: sotto questa soglia e' articolazione
FATTORE_NOTA_LUNGA = 1.6        # quante volte la durata media per dirla "lunga"
SALTO_RILEVANTE = 7             # semitoni: oltre la quinta giusta


# --------------------------------------------------------------------------
# Struttura neutra
# --------------------------------------------------------------------------


@dataclass
class NotaCtx:
    """Una nota della melodia, con quello che serve alle euristiche."""

    offset: float
    durata: float
    midi: int
    legata_dopo: bool = False        # tie: proibisce il taglio dopo
    dentro_legatura: bool = False    # slur in corso su questa nota
    fine_legatura: bool = False      # ultima nota di una legatura di portamento
    corona: bool = False
    respiro: bool = False            # BreathMark subito dopo
    staccato: bool = False
    dinamica: Optional[str] = None   # dinamica in vigore

    @property
    def fine(self) -> float:
        return self.offset + self.durata


@dataclass
class MisuraCtx:
    numero: int
    offset: float
    durata: float
    grado_armonico: Optional[int] = None
    # grado della scala su cui poggia l'armonia della misura (0 = tonica,
    # 7 = dominante in semitoni dalla tonica)


@dataclass
class Contesto:
    """Tutto cio' che le euristiche hanno bisogno di sapere."""

    note: List[NotaCtx] = field(default_factory=list)
    misure: List[MisuraCtx] = field(default_factory=list)
    pause: List[Tuple[float, float]] = field(default_factory=list)
    # (offset, durata) delle pause della voce melodica
    legature: List[Tuple[float, float]] = field(default_factory=list)
    # (inizio, fine) degli slur: dentro non si taglia mai

    def durata_media(self) -> float:
        if not self.note:
            return 1.0
        return sum(n.durata for n in self.note) / len(self.note)

    def misura_a(self, offset: float) -> Optional[MisuraCtx]:
        for m in self.misure:
            if m.offset - 1e-6 <= offset < m.offset + m.durata - 1e-6:
                return m
        return None


@dataclass
class Candidato:
    """Un punto in cui si potrebbe passare la melodia a un altro strumento."""

    offset: float
    misura: int
    punteggio: float = 0.0
    motivi: Dict[str, float] = field(default_factory=dict)
    vietato: bool = False
    perche_vietato: str = ""

    def aggiungi(self, motivo: str, peso: float) -> None:
        if peso <= 0:
            return
        self.motivi[motivo] = self.motivi.get(motivo, 0.0) + peso
        self.punteggio += peso

    def descrizione(self) -> str:
        if self.vietato:
            return f"mis. {self.misura}: vietato ({self.perche_vietato})"
        motivi = ", ".join(f"{k} {v:+.2f}" for k, v in
                           sorted(self.motivi.items(), key=lambda x: -x[1]))
        return f"mis. {self.misura}: {self.punteggio:.2f} [{motivi or 'nessun indizio'}]"


# ==========================================================================
# Estrazione da music21
# ==========================================================================


def estrai_contesto(flusso, indice_parte: int = 0) -> Contesto:
    """
    Traduce uno `music21.stream.Score` (o `Part`) in un `Contesto`.

    Si lavora sulla parte indicata, appiattita (`flatten`) e con gli offset
    assoluti in quarti. L'analisi armonica usa `chordify` sull'intera partitura:
    e' l'unico modo per sapere che accordo suona sotto la melodia quando la
    melodia sta su un rigo e l'armonia su un altro.
    """
    try:
        from music21 import (articulations, chord, dynamics, expressions, note,
                             spanner, stream)
    except ImportError as e:  # pragma: no cover
        raise RuntimeError(
            "Questo rilevatore richiede music21 (pip install music21). "
            "Il motore di base funziona comunque senza.") from e

    ctx = Contesto()
    partitura = flusso
    if isinstance(flusso, stream.Score):
        parti = list(flusso.parts)
        partitura = parti[min(indice_parte, len(parti) - 1)] if parti else flusso

    # ---------------------------------------------------------------- misure
    for m in partitura.getElementsByClass(stream.Measure):
        ctx.misure.append(MisuraCtx(numero=m.number or 0,
                                    offset=float(m.offset),
                                    durata=float(m.barDuration.quarterLength)))

    # ------------------------------------------------------- legature (slur)
    for sp in partitura.recurse().getElementsByClass(spanner.Slur):
        elementi = sp.getSpannedElements()
        if len(elementi) < 2:
            continue
        try:
            inizio = float(elementi[0].getOffsetInHierarchy(partitura))
            ultimo = elementi[-1]
            fine = (float(ultimo.getOffsetInHierarchy(partitura))
                    + float(ultimo.quarterLength))
        except Exception:
            continue
        ctx.legature.append((inizio, fine))

    fini_legatura = {round(f, 4) for _i, f in ctx.legature}

    # ------------------------------------------------------------ note e pause
    piatto = partitura.flatten()
    dinamica_corrente: Optional[str] = None
    for elemento in piatto.notesAndRests:
        try:
            offset = float(elemento.getOffsetInHierarchy(partitura))
        except Exception:
            offset = float(elemento.offset)
        durata = float(elemento.quarterLength)

        if isinstance(elemento, note.Rest):
            ctx.pause.append((offset, durata))
            continue

        altezza = (elemento.pitch.midi if isinstance(elemento, note.Note)
                   else max(p.midi for p in elemento.pitches))
        legata = bool(getattr(elemento, "tie", None)
                      and elemento.tie.type in ("start", "continue"))
        corona = any(isinstance(e, expressions.Fermata)
                     for e in elemento.expressions)
        respiro = any(isinstance(a, articulations.BreathMark)
                      for a in elemento.articulations)
        staccato = any(isinstance(a, articulations.Staccato)
                       for a in elemento.articulations)
        ctx.note.append(NotaCtx(
            offset=offset, durata=durata, midi=altezza, legata_dopo=legata,
            dentro_legatura=any(a - 1e-6 <= offset < b - 1e-6
                                for a, b in ctx.legature),
            fine_legatura=round(offset + durata, 4) in fini_legatura,
            corona=corona, respiro=respiro, staccato=staccato,
            dinamica=dinamica_corrente))

    for d in piatto.getElementsByClass(dynamics.Dynamic):
        try:
            offset = float(d.getOffsetInHierarchy(partitura))
        except Exception:
            offset = float(d.offset)
        for n in ctx.note:
            if n.offset >= offset - 1e-6:
                n.dinamica = d.value
    _propaga_dinamiche(ctx)

    # -------------------------------------------------------- armonia (gradi)
    try:
        tonalita = flusso.analyze("key")
        tonica = tonalita.tonic.pitchClass
        ridotto = flusso.chordify()
        for m in ctx.misure:
            accordi = [c for c in ridotto.recurse().getElementsByClass(chord.Chord)
                       if m.offset - 1e-6 <= float(c.getOffsetInHierarchy(ridotto))
                       < m.offset + m.durata - 1e-6]
            if accordi:
                fondamentale = accordi[-1].root().pitchClass
                m.grado_armonico = (fondamentale - tonica) % 12
    except Exception:
        pass          # l'analisi armonica e' un di piu': se fallisce si procede

    ctx.note.sort(key=lambda n: n.offset)
    return ctx


def _propaga_dinamiche(ctx: Contesto) -> None:
    """Ogni nota eredita la dinamica in vigore, per rilevarne i cambi."""
    corrente: Optional[str] = None
    for n in ctx.note:
        if n.dinamica:
            corrente = n.dinamica
        else:
            n.dinamica = corrente


# ==========================================================================
# Euristiche (Python puro: testabili senza music21)
# ==========================================================================


def valuta_confini(ctx: Contesto) -> List[Candidato]:
    """
    Assegna a ogni stanghetta un punteggio di "quanto e' naturale finire qui".

    Restituisce un candidato per ogni inizio di misura, dal secondo in poi.
    I candidati vietati (dentro una legatura o una legatura di valore) hanno
    `vietato = True` e non vanno mai scelti, qualunque sia il punteggio.
    """
    candidati: List[Candidato] = []
    if len(ctx.misure) < 2:
        return candidati

    media = ctx.durata_media()
    ripetizioni = _inizi_di_ripetizione(ctx)

    for indice in range(1, len(ctx.misure)):
        m = ctx.misure[indice]
        c = Candidato(offset=m.offset, misura=m.numero)

        vietato, motivo = _e_vietato(ctx, m.offset)
        if vietato:
            c.vietato = True
            c.perche_vietato = motivo
            candidati.append(c)
            continue

        _euristica_respiro(ctx, c, m.offset)
        _euristica_allungamento(ctx, c, m.offset, media)
        _euristica_cadenza(ctx, c, indice)
        _euristica_salto(ctx, c, m.offset)
        _euristica_articolazioni(ctx, c, m.offset)
        _euristica_dinamica(ctx, c, m.offset)
        _euristica_metrica(c, m)
        if round(m.offset, 4) in ripetizioni:
            c.aggiungi("ripetizione", PESI["ripetizione"])

        candidati.append(c)
    return candidati


# ------------------------------------------------------------------ divieti


def _e_vietato(ctx: Contesto, offset: float) -> Tuple[bool, str]:
    """
    Dentro una legatura non si cambia strumento. Mai.

    Vale sia per la legatura di portamento (spezzarla si sente) sia per quella
    di valore, dove la nota fisicamente continua: passarla a un altro strumento
    produrrebbe un attacco che nello spartito non c'e'.
    """
    for a, b in ctx.legature:
        if a + 1e-6 < offset < b - 1e-6:
            return True, "dentro una legatura di portamento"
    for n in ctx.note:
        if n.offset + 1e-6 < offset < n.fine - 1e-6:
            return True, "in mezzo a una nota"
        if n.legata_dopo and abs(n.fine - offset) < 1e-6:
            return True, "legatura di valore attraverso la stanghetta"
    return False, ""


# --------------------------------------------------------------- euristiche


def _note_prima(ctx: Contesto, offset: float, quante: int = 1) -> List[NotaCtx]:
    prima = [n for n in ctx.note if n.fine <= offset + 1e-6]
    return prima[-quante:] if prima else []


def _note_dopo(ctx: Contesto, offset: float, quante: int = 1) -> List[NotaCtx]:
    dopo = [n for n in ctx.note if n.offset >= offset - 1e-6]
    return dopo[:quante] if dopo else []


def _euristica_respiro(ctx: Contesto, c: Candidato, offset: float) -> None:
    """Pause di durata rilevante a cavallo della stanghetta."""
    for inizio, durata in ctx.pause:
        if durata < DURATA_PAUSA_RILEVANTE:
            continue
        if inizio - 1e-6 <= offset <= inizio + durata + 1e-6:
            # piu' e' lunga la pausa, piu' il respiro e' netto
            c.aggiungi("pausa", PESI["pausa"] * min(1.5, durata / 1.0))
            return
    prima = _note_prima(ctx, offset)
    dopo = _note_dopo(ctx, offset)
    if prima and dopo:
        buco = dopo[0].offset - prima[-1].fine
        if buco >= DURATA_PAUSA_RILEVANTE:
            c.aggiungi("pausa", PESI["pausa"] * min(1.5, buco / 1.0))


def _euristica_allungamento(ctx: Contesto, c: Candidato, offset: float,
                            media: float) -> None:
    """Una nota lunga in fondo alla battuta chiude un'idea."""
    prima = _note_prima(ctx, offset)
    if not prima:
        return
    ultima = prima[-1]
    if ultima.durata >= media * FATTORE_NOTA_LUNGA:
        quanto = min(2.0, ultima.durata / (media * FATTORE_NOTA_LUNGA))
        c.aggiungi("allungamento", PESI["allungamento"] * quanto)


def _euristica_cadenza(ctx: Contesto, c: Candidato, indice: int) -> None:
    """V-I sulla stanghetta, o arrivo sulla dominante (semicadenza)."""
    if indice <= 0 or indice >= len(ctx.misure):
        return
    prima = ctx.misure[indice - 1].grado_armonico
    dopo = ctx.misure[indice].grado_armonico
    if prima is None or dopo is None:
        return
    if prima == 7 and dopo == 0:
        c.aggiungi("cadenza_perfetta", PESI["cadenza_perfetta"])
    elif prima == 7:
        c.aggiungi("semicadenza", PESI["semicadenza"])
    elif dopo == 0:
        c.aggiungi("semicadenza", PESI["semicadenza"] * 0.6)


def _euristica_salto(ctx: Contesto, c: Candidato, offset: float) -> None:
    """
    Un salto ampio sulla stanghetta e' una cesura naturale, e lo e' ancora di
    piu' se la melodia cambia direzione: e' il gesto tipico dell'inizio di una
    frase nuova.
    """
    prima = _note_prima(ctx, offset, 2)
    dopo = _note_dopo(ctx, offset, 2)
    if not prima or not dopo:
        return
    salto = abs(dopo[0].midi - prima[-1].midi)
    if salto < SALTO_RILEVANTE:
        return
    c.aggiungi("salto", PESI["salto"] * min(2.0, salto / SALTO_RILEVANTE))
    if len(prima) >= 2 and len(dopo) >= 2:
        direzione_prima = prima[-1].midi - prima[-2].midi
        direzione_dopo = dopo[1].midi - dopo[0].midi
        if direzione_prima * direzione_dopo < 0:
            c.aggiungi("cambio_direzione", PESI["cambio_direzione"])


def _euristica_articolazioni(ctx: Contesto, c: Candidato, offset: float) -> None:
    """Corone, segni di respiro e staccati a fine battuta."""
    prima = _note_prima(ctx, offset)
    if not prima:
        return
    ultima = prima[-1]
    if ultima.corona:
        c.aggiungi("corona", PESI["corona"])
    if ultima.respiro:
        c.aggiungi("respiro_segnato", PESI["respiro_segnato"])
    if ultima.staccato:
        c.aggiungi("staccato_finale", PESI["staccato_finale"])
    if ultima.fine_legatura:
        # la legatura finisce proprio qui: e' un confine dichiarato
        c.aggiungi("respiro_segnato", PESI["respiro_segnato"] * 0.5)


def _euristica_dinamica(ctx: Contesto, c: Candidato, offset: float) -> None:
    """Un cambio netto di dinamica segna quasi sempre una nuova idea."""
    prima = _note_prima(ctx, offset)
    dopo = _note_dopo(ctx, offset)
    if not prima or not dopo:
        return
    if prima[-1].dinamica and dopo[0].dinamica and \
            prima[-1].dinamica != dopo[0].dinamica:
        c.aggiungi("cambio_dinamica", PESI["cambio_dinamica"])


def _euristica_metrica(c: Candidato, m: MisuraCtx) -> None:
    """I blocchi regolari di 8, 4 o 2 misure sono la norma statistica."""
    if m.numero <= 0:
        return
    posizione = m.numero - 1
    if posizione % 8 == 0:
        c.aggiungi("metrica_8", PESI["metrica_8"])
    elif posizione % 4 == 0:
        c.aggiungi("metrica_4", PESI["metrica_4"])
    elif posizione % 2 == 0:
        c.aggiungi("metrica_2", PESI["metrica_2"])


# ------------------------------------------------- ripetizione motivica


def _inizi_di_ripetizione(ctx: Contesto, finestre: Sequence[int] = (1, 2),
                          soglia: float = 0.8) -> Dict[float, bool]:
    """
    Trova dove un motivo di una o due misure ricomincia.

    Il confronto e' sugli INTERVALLI, non sulle altezze: una progressione
    ripete la stessa figura piu' in alto o piu' in basso, e va riconosciuta
    lo stesso. Tagliare all'inizio della ripetizione fa nascere l'effetto
    domanda-risposta fra due strumenti, che e' esattamente cio' che si vuole.
    """
    inizi: Dict[float, bool] = {}
    if len(ctx.misure) < 4:
        return inizi

    def profilo(a: float, b: float) -> Tuple[int, ...]:
        dentro = [n for n in ctx.note if a - 1e-6 <= n.offset < b - 1e-6]
        return tuple(y.midi - x.midi for x, y in zip(dentro, dentro[1:]))

    for larghezza in finestre:
        for i in range(len(ctx.misure) - 2 * larghezza + 1):
            a = ctx.misure[i].offset
            b = ctx.misure[i + larghezza].offset
            c = (ctx.misure[i + 2 * larghezza].offset
                 if i + 2 * larghezza < len(ctx.misure)
                 else ctx.misure[-1].offset + ctx.misure[-1].durata)
            uno, due = profilo(a, b), profilo(b, c)
            if len(uno) < 2 or len(due) < 2:
                continue
            if abs(len(uno) - len(due)) > 1:
                continue
            comuni = sum(1 for x, y in zip(uno, due) if x == y)
            if comuni / max(len(uno), len(due)) >= soglia:
                inizi[round(b, 4)] = True
    return inizi


# ==========================================================================
# Scelta dei tagli
# ==========================================================================


def scegli_tagli(candidati: List[Candidato], misure_minime: int = 4,
                 misure_massime: int = 8, ideale: Optional[int] = None
                 ) -> List[Candidato]:
    """
    Sceglie i tagli massimizzando gli indizi, con una programmazione dinamica.

    Prendere semplicemente i punteggi migliori non funziona: si otterrebbero
    tagli ammassati dove la musica respira spesso e nessun taglio per pagine
    intere. Il vincolo di distanza (`misure_minime`, `misure_massime`) e la
    preferenza per la lunghezza `ideale` producono invece una spartizione
    regolare, che e' quello che serve a far girare il tema fra gli strumenti.
    """
    if not candidati:
        return []
    ideale = ideale or (misure_minime + misure_massime) // 2
    ammessi = [c for c in candidati if not c.vietato]
    if not ammessi:
        return []

    # indicizzati per numero di misura, per ragionare in misure e non in quarti
    per_misura = {c.misura: c for c in ammessi}
    numeri = sorted(per_misura)
    primo = min(c.misura for c in candidati) - 1
    ultimo = max(c.misura for c in candidati)

    migliore: Dict[int, float] = {primo: 0.0}
    provenienza: Dict[int, int] = {}
    for numero in numeri + [ultimo]:
        opzioni = []
        for precedente, punteggio in migliore.items():
            distanza = numero - precedente
            if distanza < misure_minime or distanza > misure_massime:
                continue
            valore = punteggio - 0.18 * abs(distanza - ideale)
            if numero in per_misura:
                valore += per_misura[numero].punteggio
            opzioni.append((valore, precedente))
        if opzioni:
            valore, precedente = max(opzioni)
            if valore > migliore.get(numero, -1e18):
                migliore[numero] = valore
                provenienza[numero] = precedente

    if ultimo not in provenienza:
        # nessun percorso valido: si ripiega sui candidati migliori distanziati
        return _ripiego(ammessi, misure_minime)

    catena: List[int] = []
    corrente = ultimo
    while corrente in provenienza:
        corrente = provenienza[corrente]
        if corrente != primo:
            catena.append(corrente)
    catena.reverse()
    return [per_misura[n] for n in catena if n in per_misura]


def _ripiego(ammessi: List[Candidato], misure_minime: int) -> List[Candidato]:
    scelti: List[Candidato] = []
    for c in sorted(ammessi, key=lambda x: -x.punteggio):
        if all(abs(c.misura - s.misura) >= misure_minime for s in scelti):
            scelti.append(c)
    return sorted(scelti, key=lambda c: c.misura)


def punti_di_scambio(flusso, misure_minime: int = 4, misure_massime: int = 8,
                     indice_parte: int = 0) -> List[float]:
    """
    Scorciatoia: dallo `Stream` agli offset (in quarti) dove cambiare strumento.
    """
    ctx = estrai_contesto(flusso, indice_parte)
    return [c.offset for c in scegli_tagli(valuta_confini(ctx),
                                           misure_minime, misure_massime)]


def disponibile() -> bool:
    try:
        import music21  # noqa: F401
        return True
    except ImportError:
        return False


def periodi_da_file(percorso: str, misure_minime: int = 4,
                    misure_massime: int = 8
                    ) -> Optional[List[Tuple[float, float]]]:
    """
    Dai tagli agli intervalli (inizio, fine) usabili come periodi dal motore.
    Ritorna None se music21 non c'e' o il file non e' leggibile: in quel caso
    si usa il rilevatore interno.
    """
    if not disponibile():
        return None
    try:
        from music21 import converter
        flusso = converter.parse(percorso)
        ctx = estrai_contesto(flusso)
        tagli = scegli_tagli(valuta_confini(ctx), misure_minime, misure_massime)
    except Exception:
        return None
    if not ctx.misure:
        return None
    confini = ([ctx.misure[0].offset] + [c.offset for c in tagli]
               + [ctx.misure[-1].offset + ctx.misure[-1].durata])
    return [(a, b) for a, b in zip(confini, confini[1:]) if b > a + 1e-6]


def relazione(flusso, misure_minime: int = 4, misure_massime: int = 8,
              indice_parte: int = 0) -> str:
    """
    Spiega, candidato per candidato, perche' il taglio e' stato scelto o no.
    Serve a tarare i pesi su un repertorio: senza, si procede alla cieca.
    """
    ctx = estrai_contesto(flusso, indice_parte)
    candidati = valuta_confini(ctx)
    scelti = {c.misura for c in scegli_tagli(candidati, misure_minime,
                                             misure_massime)}
    righe = ["Confini di frase (* = taglio scelto)", ""]
    for c in candidati:
        righe.append(("* " if c.misura in scelti else "  ") + c.descrizione())
    return "\n".join(righe)
