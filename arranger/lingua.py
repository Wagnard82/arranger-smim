"""
Lingua dell'interfaccia e della partitura: italiano ed inglese.

Il motore ragiona sempre sulle stesse chiavi interne (strumenti, ruoli,
stili, livelli "1a Media"/"2a Media"/"3a Media"). Qui sta soltanto COME
quelle chiavi si mostrano: in questo modo la musica prodotta e' identica
nelle due lingue, e una correzione al motore vale per entrambe.

Livelli in inglese: si usa la scala dei GRADE dell'editoria per orchestre e
band scolastiche (Grade 1, 2, 3...), che un docente straniero riconosce
subito. La corrispondenza con i tre livelli SMIM:

    1a Media  ->  Grade 1 - Beginner
    2a Media  ->  Grade 2 - Elementary
    3a Media  ->  Grade 3 - Intermediate

Il richiamo ad ABRSM/Trinity nelle descrizioni e' indicativo, non una
tabella ufficiale di equivalenze.
"""

from __future__ import annotations

import re
from typing import Dict, Optional

LINGUE: Dict[str, str] = {"it": "Italiano", "en": "English"}
PREDEFINITA = "it"


def valida(lingua: Optional[str]) -> str:
    return lingua if lingua in LINGUE else PREDEFINITA


# --------------------------------------------------------------------------
# Livelli
# --------------------------------------------------------------------------

CHIAVI_LIVELLO = ["1a Media", "2a Media", "3a Media"]

_ETICHETTE_LIVELLO = {
    "it": {"1a Media": "1a Media", "2a Media": "2a Media", "3a Media": "3a Media"},
    "en": {"1a Media": "Grade 1 – Beginner",
           "2a Media": "Grade 2 – Elementary",
           "3a Media": "Grade 3 – Intermediate"},
}
_ETICHETTE_LIVELLO_BREVI = {
    "it": {"1a Media": "1a Media", "2a Media": "2a Media", "3a Media": "3a Media"},
    "en": {"1a Media": "Grade 1", "2a Media": "Grade 2", "3a Media": "Grade 3"},
}
_NOTE_LIVELLO_EN = {
    "1a Media": "First position, basic rhythms (half and quarter notes), "
                "two-note chords, leaps within a 5th. Approx. ABRSM/Trinity "
                "Grade 1–2.",
    "2a Media": "Accidentals, simple arpeggios, eighth notes, first octave "
                "stretches. Approx. ABRSM/Trinity Grade 2–3.",
    "3a Media": "Sixteenth notes, position shifts, full chords, wide leaps, "
                "syncopation. Approx. ABRSM/Trinity Grade 3–4.",
}


def normalizza_livello(valore) -> str:
    """
    Riporta a chiave interna qualunque modo di scrivere un livello:
    "1a Media", "Grade 1", "grade1", "Grade 1 – Beginner", "1", 1.
    Un valore non riconosciuto resta com'e' (lo gestisce `strumenti.livello`).
    """
    if valore is None:
        return valore
    if isinstance(valore, int):
        return CHIAVI_LIVELLO[valore - 1] if 1 <= valore <= 3 else str(valore)
    s = str(valore).strip()
    if s in CHIAVI_LIVELLO:
        return s
    m = re.fullmatch(r"(?i)(?:grade|livello|level)?\s*([123])"
                     r"(?:\s*(?:a\s*media|°)?)?(?:\s*[–-].*)?", s)
    if m:
        return CHIAVI_LIVELLO[int(m.group(1)) - 1]
    return s


def etichetta_livello(chiave: str, lingua: str = "it", breve: bool = False) -> str:
    tab = (_ETICHETTE_LIVELLO_BREVI if breve else _ETICHETTE_LIVELLO)[valida(lingua)]
    chiave = normalizza_livello(chiave)
    return tab.get(chiave, chiave)


def note_livello(chiave: str, lingua: str = "it") -> str:
    from .strumenti import livello
    chiave = normalizza_livello(chiave)
    if valida(lingua) == "en":
        return _NOTE_LIVELLO_EN.get(chiave, "")
    return livello(chiave).note


# --------------------------------------------------------------------------
# Strumenti, ruoli, stili, forma
# --------------------------------------------------------------------------

_STRUMENTI_EN = {
    "flauto": ("Flute", "Fl."),
    "clarinetto": ("Clarinet in Bb", "Cl."),
    "sax": ("Alto Sax", "A. Sax"),
    "tromba": ("Trumpet in Bb", "Tpt."),
    "violino": ("Violin", "Vln."),
    "violoncello": ("Cello", "Vc."),
    "chitarra": ("Guitar", "Gtr."),
    "pianoforte": ("Piano", "Pno."),
    "glockenspiel": ("Glockenspiel", "Glock."),
    "metallofono": ("Metallophone", "Met."),
    "percussioni": ("Percussion", "Perc."),
}


def nome_strumento(chiave: str, lingua: str = "it") -> str:
    if valida(lingua) == "en" and chiave in _STRUMENTI_EN:
        return _STRUMENTI_EN[chiave][0]
    from .strumenti import REGISTRO
    return REGISTRO[chiave].nome if chiave in REGISTRO else chiave


def abbrev_strumento(chiave: str, lingua: str = "it") -> str:
    if valida(lingua) == "en" and chiave in _STRUMENTI_EN:
        return _STRUMENTI_EN[chiave][1]
    from .strumenti import REGISTRO
    return REGISTRO[chiave].abbrev if chiave in REGISTRO else chiave


def nome_parte_da_id(id_parte: str, lingua: str = "it") -> str:
    """'violino2' -> 'Violino 2' / 'Violin 2'; 'violino' -> 'Violino'."""
    m = re.fullmatch(r"([a-z]+?)(\d*)", id_parte)
    if not m:
        return id_parte
    nome = nome_strumento(m.group(1), lingua)
    return f"{nome} {m.group(2)}" if m.group(2) else nome


_RUOLI = {
    "it": {"melodia": "melodia", "controcanto": "controcanto",
           "armonia": "armonia", "basso": "basso", "ritmo": "ritmo",
           "tessitura": "tessitura"},
    "en": {"melodia": "melody", "controcanto": "countermelody",
           "armonia": "harmony", "basso": "bass", "ritmo": "rhythm",
           "tessitura": "texture"},
}

_STILI = {
    "it": {"Normale": "Normale", "Cinematico": "Cinematico", "Jazz": "Jazz",
           "Automatico": "Automatico"},
    "en": {"Normale": "Standard", "Cinematico": "Cinematic", "Jazz": "Jazz",
           "Automatico": "Automatic"},
}

_FORME = {
    "it": {"classica": "Classica", "pop": "Pop"},
    "en": {"classica": "Classical", "pop": "Pop song"},
}

_ACCOMPAGNAMENTI_EN = {
    "blocchi": "block chords", "arpeggio": "arpeggio", "ribattuto": "repeated chords",
    "pad": "pad", "walking": "walking bass",
}


def ruolo(chiave: str, lingua: str = "it") -> str:
    return _RUOLI[valida(lingua)].get(chiave, chiave)


def stile(chiave: str, lingua: str = "it") -> str:
    return _STILI[valida(lingua)].get(chiave, chiave)


def forma(chiave: str, lingua: str = "it") -> str:
    return _FORME[valida(lingua)].get(chiave, chiave.capitalize())


def accompagnamento(chiave: str, lingua: str = "it") -> str:
    if valida(lingua) == "en":
        return _ACCOMPAGNAMENTI_EN.get(chiave, chiave)
    return chiave


def nota(midi: int, lingua: str = "it") -> str:
    from .modello import nome_en, nome_it
    return nome_en(midi) if valida(lingua) == "en" else nome_it(midi)


def ottave(n: int, lingua: str = "it") -> str:
    """'1 ottava' / '2 ottave' — 'octave' / 'octaves'."""
    n = abs(n)
    if valida(lingua) == "en":
        return f"{n} octave" + ("" if n == 1 else "s")
    return f"{n} ottava" if n == 1 else f"{n} ottave"


# --------------------------------------------------------------------------
# Messaggi del report e del motore
# --------------------------------------------------------------------------
#
# Ogni messaggio ha una chiave e un modello per lingua, riempito con
# str.format. Le parti che dipendono dalla lingua (nomi delle note, delle
# parti, dei livelli) arrivano gia' tradotte dal punto di chiamata.

MESSAGGI: Dict[str, Dict[str, str]] = {
    # ---- vincoli
    "polifonia": {
        "it": "[Polifonia] {parte}, mis. {mis}: {n} note su strumento monofonico -> ridotte a 1 (le altre ai divisi).",
        "en": "[Polyphony] {parte}, bar {mis}: {n} notes on a single-line instrument -> reduced to 1 (the others go to the divisi).",
    },
    "estensione_tratto": {
        "it": "[Estensione] {parte}, mis. {mis}: tratto trasposto di {ott:+d} ottave per rientrare nell'ambito.",
        "en": "[Range] {parte}, bar {mis}: passage transposed by {ott:+d} octaves to fit the range.",
    },
    "estensione_nota": {
        "it": "[Estensione] {parte}, mis. {mis}: nota fuori ambito -> trasposta d'ottava.",
        "en": "[Range] {parte}, bar {mis}: note out of range -> moved by an octave.",
    },
    "ritmo": {
        "it": "[Ritmo] {parte}, mis. {mis}: valore inferiore al minimo del livello -> semplificato.",
        "en": "[Rhythm] {parte}, bar {mis}: note value shorter than the level allows -> simplified.",
    },
    "salti": {
        "it": "[Salti] {parte}, mis. {mis}: salto di {salto} semitoni -> seguito della frase trasposto di {ott:+d} ottave.",
        "en": "[Leaps] {parte}, bar {mis}: leap of {salto} semitones -> rest of the phrase transposed by {ott:+d} octaves.",
    },
    "alterazioni": {
        "it": "[Alterazioni] {parte}, mis. {mis}: nota alterata non prevista in {livello} -> ricondotta alla tonalita'.",
        "en": "[Accidentals] {parte}, bar {mis}: accidental not expected at {livello} -> brought back into the key.",
    },
    "accordo_non_diteggiabile": {
        "it": "[Idiomatico] {parte}, mis. {mis}: accordo non diteggiabile -> ridotto alla fondamentale (resta la sigla).",
        "en": "[Idiomatic] {parte}, bar {mis}: chord not playable -> reduced to the root (the chord symbol stays).",
    },
    "cambio_corda": {
        "it": "[Idiomatico] {parte}, mis. {mis}: cambio di corda troppo ampio -> frase riportata in posizione.",
        "en": "[Idiomatic] {parte}, bar {mis}: string crossing too wide -> phrase brought back into position.",
    },
    "apertura_mano": {
        "it": "[Idiomatico] {parte}, mis. {mis}: apertura della mano eccessiva -> accordo ristretto.",
        "en": "[Idiomatic] {parte}, bar {mis}: hand stretch too wide -> chord narrowed.",
    },
    "incrocio_destra": {
        "it": "[Incroci] {parte}, mis. {mis}: mano destra sotto la sinistra -> alzata di {ottave}.",
        "en": "[Crossing] {parte}, bar {mis}: right hand below the left -> raised by {ottave}.",
    },
    "incrocio_sinistra": {
        "it": "[Incroci] {parte}, mis. {mis}: mano sinistra abbassata di {ottave} sotto la melodia.",
        "en": "[Crossing] {parte}, bar {mis}: left hand lowered by {ottave} below the melody.",
    },
    "incrocio_raddoppi": {
        "it": "[Incroci] {parte}, mis. {mis}: note raddoppiate fra le due mani -> tolte dalla destra.",
        "en": "[Crossing] {parte}, bar {mis}: notes doubled between the hands -> removed from the right hand.",
    },
    "mani_registro": {
        "it": "[Mani] {parte}, mis. {mis}: nota fuori dal registro della mano {mano} -> riportata nell'ottava giusta.",
        "en": "[Hands] {parte}, bar {mis}: note outside the {mano} hand's register -> moved to the right octave.",
    },
    "divisi_sopra": {
        "it": "[Divisi] {parte}: {n} note che superavano {sopra} -> riportate sotto.",
        "en": "[Divisi] {parte}: {n} notes above {sopra} -> moved below.",
    },
    "divisi_ritmo": {
        "it": "[Divisi] {parte}: {n} valori allargati (leggio secondario, parte piu' facile).",
        "en": "[Divisi] {parte}: {n} note values lengthened (second desk, easier part).",
    },
    "respiro": {
        "it": "[Respiro] {parte}: {n} punti in cui la parte e' stata accorciata per far respirare (massimo {limite:g} quarti di fila).",
        "en": "[Breathing] {parte}: {n} places shortened to allow a breath (at most {limite:g} beats in a row).",
    },
    # ---- orchestratore
    "ingresso_lead_sheet": {
        "it": "[Ingresso] lead sheet riconosciuto: la melodia e' quella scritta, basso e accompagnamento sono costruiti dalle {n} sigle del file. Il basso suona la fondamentale di ogni accordo (o la nota dopo la barra, nei rivolti come C/E).",
        "en": "[Input] lead sheet detected: the melody is the written one; bass and accompaniment are built from the {n} chord symbols in the file. The bass plays the root of each chord (or the note after the slash, in inversions such as C/E).",
    },
    "ingresso_lead_sheet_senza_sigle": {
        "it": "[Ingresso] lead sheet SENZA SIGLE: l'armonia e' stata proposta dall'arrangiatore, un accordo per misura sui gradi principali della tonalita'. E' un'armonizzazione plausibile della melodia, non necessariamente quella del brano: dalla sola melodia non si puo' ricostruire. Per un arrangiamento fedele aggiungi le sigle nel file (in Dorico, MuseScore o Sibelius) e rigenera.",
        "en": "[Input] lead sheet WITHOUT CHORD SYMBOLS: the harmony was proposed by the arranger, one chord per bar on the main degrees of the key. It is a plausible harmonisation of the melody, not necessarily the song's own: that cannot be reconstructed from the melody alone. For a faithful arrangement, add chord symbols to the file (in Dorico, MuseScore or Sibelius) and generate again.",
    },
    "ingresso_solista": {
        "it": "[Ingresso] parte solista + pianoforte riconosciuta: la melodia e' la parte del solista, l'accompagnamento quello del pianoforte.",
        "en": "[Input] solo part + piano detected: the melody is the solo part, the accompaniment is the piano part.",
    },
    "livelli": {
        "it": "[Livelli] classe impostata su {livello}; indicazioni specifiche: {elenco}. Le parti coinvolte sono state calibrate su quel livello per estensione, valori ritmici, alterazioni e respiro, e sono state valutate su quel livello anche nella scelta di chi porta la melodia.",
        "en": "[Levels] ensemble set to {livello}; specific settings: {elenco}. The parts involved were calibrated to that level for range, note values, accidentals and breathing, and were judged at that level when choosing who carries the melody.",
    },
    "tessitura_brano": {
        "it": "[Tessitura] Brano orchestrato per registri: non e' stata cercata una melodia da affidare a un solista.",
        "en": "[Texture] Piece orchestrated by register: no melody was sought for a soloist.",
    },
    "tessitura_piano": {
        "it": "[Tessitura] {parte}: parte pianistica originale.",
        "en": "[Texture] {parte}: original piano part.",
    },
    "tessitura_fascia": {
        "it": "[Tessitura] {parte}: fascia {da}-{a}.",
        "en": "[Texture] {parte}: register band {da}-{a}.",
    },
    "silenzi": {
        "it": "[Silenzi] {parte}: {n} pause lunghe riempite con l'accompagnamento.",
        "en": "[Rests] {parte}: {n} long rests filled with accompaniment.",
    },
    "solista_alleggerito": {
        "it": "[Solista] {parte}: accompagnamento alleggerito nei tratti in cui porta la melodia ({n} tratti).",
        "en": "[Soloist] {parte}: accompaniment thinned where it carries the melody ({n} passages).",
    },
    "inciso": {
        "it": "[Incisi] {parte}, mis. {mis}: inciso dell'originale ripreso.",
        "en": "[Motifs] {parte}, bar {mis}: motif from the original reused.",
    },
    "inciso_al_posto": {
        "it": "[Incisi] {parte}, mis. {mis}: inciso dell'originale ripreso al posto del riempimento.",
        "en": "[Motifs] {parte}, bar {mis}: motif from the original reused instead of the filler.",
    },
    # ---- distribuzione dei ruoli
    "ruolo_melodia_utente": {
        "it": "[Ruoli] {parte}: melodia (scelta dell'utente).",
        "en": "[Roles] {parte}: melody (user's choice).",
    },
    "ruolo_melodia": {
        "it": "[Ruoli] {parte}: melodia (livello {livello}, idoneita' {idoneita:.2f}, {perc:.0f}% delle note in estensione).",
        "en": "[Roles] {parte}: melody (level {livello}, suitability {idoneita:.2f}, {perc:.0f}% of notes in range).",
    },
    "ruolo_basso": {
        "it": "[Ruoli] {parte}: basso.",
        "en": "[Roles] {parte}: bass.",
    },
    "ruolo_controcanto_voce": {
        "it": "[Ruoli] {parte}: seconda voce / controcanto.",
        "en": "[Roles] {parte}: second voice / countermelody.",
    },
    "ruolo_armonia": {
        "it": "[Ruoli] {parte}: accompagnamento armonico.",
        "en": "[Roles] {parte}: harmonic accompaniment.",
    },
    "ruolo_controcanto": {
        "it": "[Ruoli] {parte}: controcanto.",
        "en": "[Roles] {parte}: countermelody.",
    },
    "ruolo_accompagnamento_forzato": {
        "it": "[Ruoli] {parte}: accompagnamento (nessuno altrimenti accompagnerebbe).",
        "en": "[Roles] {parte}: accompaniment (otherwise nobody would accompany).",
    },
    # ---- pipeline
    "debug_originale": {
        "it": "[Debug] Spartito originale accodato in fondo alla partitura per il confronto.",
        "en": "[Debug] Original score appended at the bottom of the full score for comparison.",
    },
    "pdf_non_generato": {
        "it": "[Incisione] PDF non generato: {errore}",
        "en": "[Engraving] PDF not generated: {errore}",
    },
    "ia_melodia": {
        "it": "IA: melodia rivista in {n} misure.",
        "en": "AI: melody revised in {n} bars.",
    },
    "ia_riferimenti": {
        "it": "IA: raccolte informazioni sul brano originale.",
        "en": "AI: information gathered on the original song.",
    },
    "ia_stile": {
        "it": "IA: stile consigliato {stile}, accompagnamento {acc} ({motivo})",
        "en": "AI: suggested style {stile}, accompaniment {acc} ({motivo})",
    },
    "ia_armonia": {
        "it": "IA: {n} accordi rivisti nella griglia armonica.",
        "en": "AI: {n} chords revised in the chord chart.",
    },
    "music21_periodi": {
        "it": "music21: {n} periodi individuati dal rilevatore avanzato di frasi.",
        "en": "music21: {n} periods found by the advanced phrase detector.",
    },
    "ia_staffetta": {
        "it": "IA: piano di staffetta della melodia generato dal modello.",
        "en": "AI: melody hand-off plan generated by the model.",
    },
    # ---- partitura
    "sottotitolo": {
        "it": "Arrangiamento per orchestra scolastica - {livello} - stile {stile}",
        "en": "Arrangement for school orchestra - {livello} - {stile} style",
    },
    "sottotitolo_differenziati": {
        "it": " (livelli differenziati)",
        "en": " (mixed levels)",
    },
    "swing": {
        "it": "Swing (crome in terzina)",
        "en": "Swing (triplet eighths)",
    },
    "originale_confronto": {
        "it": "Originale (confronto)",
        "en": "Original (comparison)",
    },
    "senza_titolo": {
        "it": "Senza titolo",
        "en": "Untitled",
    },
    "mano_destra": {"it": "destra", "en": "right"},
    "mano_sinistra": {"it": "sinistra", "en": "left"},
}


def t(chiave: str, lingua: str = "it", **valori) -> str:
    """Il messaggio `chiave` nella lingua richiesta, riempito con `valori`."""
    modelli = MESSAGGI[chiave]
    modello = modelli.get(valida(lingua)) or modelli[PREDEFINITA]
    return modello.format(**valori) if valori else modello


# --------------------------------------------------------------------------
# Errori del motore che arrivano all'utente come eccezioni
# --------------------------------------------------------------------------
#
# L'ingestione solleva eccezioni con testo italiano; nell'interfaccia
# inglese si traducono qui, per prefisso, senza toccare il motore.

_ERRORI_EN = [
    ("Archivio .mxl senza partitura", "The .mxl archive contains no score"),
    ("MusicXML timewise non supportato: converti in partwise.",
     "Timewise MusicXML is not supported: convert it to partwise."),
    ("Nessuna <part> trovata nel MusicXML", "No <part> found in the MusicXML"),
    ("LilyPond non trovato nel PATH.", "LilyPond not found in PATH."),
    ("Incisione fallita:", "Engraving failed:"),
    ("Formato non supportato", "Unsupported format"),
]


def traduci_errore(testo: str, lingua: str = "it") -> str:
    if valida(lingua) != "en":
        return testo
    for it, en in _ERRORI_EN:
        if testo.startswith(it):
            return en + testo[len(it):]
    return testo
