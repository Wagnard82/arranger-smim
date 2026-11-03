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
    "corno": ("Horn in F", "Hn."),
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


BEMOLLI_IT = ["Do", "Reb", "Re", "Mib", "Mi", "Fa", "Solb", "Sol", "Lab", "La", "Sib", "Si"]
BEMOLLI_EN = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]


def nota(midi: int, lingua: str = "it", bemolli: bool = False) -> str:
    """Nome della nota con l'ottava. Con `bemolli` le alterazioni si scrivono
    col bemolle (Sib4 invece di La#4), come nelle tonalita' coi bemolli."""
    from .modello import nome_en, nome_it
    if bemolli:
        nomi = BEMOLLI_EN if valida(lingua) == "en" else BEMOLLI_IT
        return f"{nomi[midi % 12]}{midi // 12 - 1}"
    return nome_en(midi) if valida(lingua) == "en" else nome_it(midi)


_PARAMETRI = {
    "it": {"stile": "stile", "strumenti_melodia": "strumenti della melodia",
           "staffetta_melodia": "staffetta della melodia",
           "cambio_solista": "cambio di solista",
           "misure_minime_solista": "misure minime per solista",
           "raddoppi_melodia": "raddoppi della melodia",
           "riempi_silenzi": "nessuno fermo a lungo",
           "silenzio_massimo_misure": "pausa massima (misure)",
           "trasporto": "trasporto (semitoni)", "modo": "modo"},
    "en": {"stile": "style", "strumenti_melodia": "melody instruments",
           "staffetta_melodia": "melody relay",
           "cambio_solista": "soloist change",
           "misure_minime_solista": "minimum bars per soloist",
           "raddoppi_melodia": "melody doublings",
           "riempi_silenzi": "nobody idle for long",
           "silenzio_massimo_misure": "longest rest (bars)",
           "trasporto": "transposition (semitones)", "modo": "mode"},
}
_VALORI = {
    "it": {True: "si'", False: "no", "auto": "automatico", "frase": "a ogni frase",
           "periodo": "a ogni periodo", "sezione": "a ogni sezione",
           "melodico": "melodia e accompagnamento", "tessitura": "per registri"},
    "en": {True: "yes", False: "no", "auto": "automatic", "frase": "every phrase",
           "periodo": "every period", "sezione": "every section",
           "melodico": "melody and accompaniment", "tessitura": "by register"},
}


def nome_parametro(chiave: str, lingua: str = "it") -> str:
    """Nome leggibile di un parametro della configurazione (report)."""
    return _PARAMETRI[valida(lingua)].get(chiave, chiave)


def valore_parametro(chiave: str, valore, lingua: str = "it",
                     id_parti: Optional[Dict[str, str]] = None) -> str:
    """Valore leggibile di un parametro: stili e scelte tradotti, le parti
    per nome."""
    lingua = valida(lingua)
    if chiave == "stile":
        return stile(valore, lingua)
    if chiave == "strumenti_melodia":
        if not valore:
            return _VALORI[lingua]["auto"]
        return ", ".join(nome_parte_da_id(x, lingua) for x in valore)
    # attenzione: 1 == True per Python, un trasporto di 1 non e' un «si'»
    if isinstance(valore, bool) or (isinstance(valore, str) and valore in _VALORI[lingua]):
        return _VALORI[lingua][valore]
    return f"{valore:+d}" if chiave == "trasporto" and isinstance(valore, int) else str(valore)


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
    "semitoni": {
        "it": "[Semitoni] {parte}, mis. {mis}: {n} note a un semitono da una nota dell'originale -> spostate su una nota che non stride.",
        "en": "[Semitones] {parte}, bar {mis}: {n} notes a semitone away from a note of the original -> moved to a note that does not clash.",
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
    "buco_riempito": {
        "it": "[Armonia] {parte}, mis. {misure}: accompagnamento abbassato di un'ottava per riempire il vuoto nel registro medio.",
        "en": "[Harmony] {parte}, bars {misure}: accompaniment moved down an octave to fill the gap in the middle register.",
    },
    "buco_sinistra": {
        "it": "[Armonia] {parte}, mis. {misure}: la sinistra aggiunge una nota dell'accordo sopra il basso per riempire il registro medio.",
        "en": "[Harmony] {parte}, bars {misure}: the left hand adds a chord tone above the bass to fill the middle register.",
    },
    "buco_basso": {
        "it": "[Armonia] Basso staccato dalle altre voci (oltre un'ottava e una quinta). Misure segnalate: {n} ({misure}). Es. mis. {mis}: {grave} e sopra subito {acuta}. Si puo' avvicinare il basso o riempire il registro medio.",
        "en": "[Harmony] Bass far from the other voices (more than an octave and a fifth). Bars flagged: {n} ({misure}). E.g. bar {mis}: {grave} with {acuta} directly above. Move the bass closer or fill the middle register.",
    },
    "buco_centro": {
        "it": "[Armonia] Vuoto di oltre un'ottava fra le voci superiori. Misure segnalate: {n} ({misure}). Es. mis. {mis}: niente fra {grave} e {acuta}. Si puo' riempire con una voce interna.",
        "en": "[Harmony] Gap of more than an octave between the upper voices. Bars flagged: {n} ({misure}). E.g. bar {mis}: nothing between {grave} and {acuta}. Fill it with an inner voice.",
    },
    "note_scomode": {
        "it": "[Diteggiatura] {parte}: note scomode in {livello} ({note}), {n} in tutto. Lasciate come sono, da controllare a mano: mis. {misure}",
        "en": "[Fingering] {parte}: awkward notes at {livello} ({note}), {n} in total. Left unchanged, check by hand: bars {misure}",
    },
    # ---- orchestratore
    "ingresso_lead_sheet": {
        "it": "[Ingresso] lead sheet riconosciuto: la melodia e' quella scritta, basso e accompagnamento sono costruiti dalle {n} sigle del file. Il basso suona la fondamentale di ogni accordo (o la nota dopo la barra, nei rivolti come C/E).",
        "en": "[Input] lead sheet detected: the melody is the written one; bass and accompaniment are built from the {n} chord symbols in the file. The bass plays the root of each chord (or the note after the slash, in inversions such as C/E).",
    },
    "ingresso_lead_sheet_senza_sigle": {
        "it": "[Ingresso] lead sheet SENZA SIGLE: l'armonia e' stata proposta dall'arrangiatore in {tonalita} {modo}, seguendo la melodia (cadenze, ritmo armonico, dominanti secondarie dove la melodia le chiede). E' un'armonizzazione plausibile, non necessariamente quella del brano: per un arrangiamento fedele aggiungi le sigle nel file (in Dorico, MuseScore o Sibelius) e rigenera.",
        "en": "[Input] lead sheet WITHOUT CHORD SYMBOLS: the harmony was proposed by the arranger in {tonalita} {modo}, following the melody (cadences, harmonic rhythm, secondary dominants where the melody asks for them). It is a plausible harmonization, not necessarily the song's own: for a faithful arrangement add the chord symbols to the file (in Dorico, MuseScore or Sibelius) and generate again.",
    },
    "modo_maggiore": {"it": "maggiore", "en": "major"},
    "modo_minore": {"it": "minore", "en": "minor"},
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
    "ruoli_leggii": {
        "it": "[Ruoli] {primo} e {secondo}: ruoli scambiati, la parte piu' esposta va al primo leggio.",
        "en": "[Roles] {primo} and {secondo}: roles swapped, the more exposed part goes to the first desk.",
    },
    "staffetta_primi_leggii": {
        "it": "[Staffetta] Frasi in cui la melodia passa dal secondo al primo leggio: {n}. Le seconde parti la raddoppiano, non la portano da sole.",
        "en": "[Relay] Phrases where the melody moves from the second to the first desk: {n}. Second parts double it, never carry it alone.",
    },
    "regola_sintesi": {
        "it": "Richiesta letta senza IA: {n} indicazioni su {totale} riconosciute.",
        "en": "Request read without AI: {n} of {totale} instructions recognised.",
    },
    "regola_non_capita": {
        "it": "frase non riconosciuta: con l'IA attiva si capisce di piu'",
        "en": "not recognised: with the AI switched on more is understood",
    },
    "regola_livello": {
        "it": "il livello si sceglie nel pannello a sinistra",
        "en": "the grade is chosen in the left panel",
    },
    "regola_organico": {
        "it": "l'organico si sceglie nel pannello a sinistra",
        "en": "the ensemble is chosen in the left panel",
    },
    "regola_manca": {
        "it": "non c'e' nell'organico: {strumenti}",
        "en": "not in the ensemble: {strumenti}",
    },
    "richiesta_sintesi": {
        "it": "[Richiesta] {testo}",
        "en": "[Request] {testo}",
    },
    "richiesta_applicata": {
        "it": "[Richiesta] {cosa}: {valore}.",
        "en": "[Request] {cosa}: {valore}.",
    },
    "richiesta_valore": {
        "it": "[Richiesta] {cosa}: valore «{valore}» non ammesso, lasciato com'era.",
        "en": "[Request] {cosa}: value «{valore}» not allowed, left unchanged.",
    },
    "richiesta_scartata": {
        "it": "[Richiesta] «{cosa}» non e' un'impostazione del motore: ignorata.",
        "en": "[Request] «{cosa}» is not an engine setting: ignored.",
    },
    "richiesta_non_applicabile": {
        "it": "[Richiesta] Non applicato: {cosa}",
        "en": "[Request] Not applied: {cosa}",
    },
    "richiesta_nulla": {
        "it": "[Richiesta] Nessuna impostazione da cambiare: l'arrangiamento resta quello di base.",
        "en": "[Request] No setting to change: the arrangement stays the default one.",
    },
    "richiesta_fallita": {
        "it": "[Richiesta] Il modello non ha risposto in modo utilizzabile (errore: {errore}): la richiesta e' stata letta senza IA.",
        "en": "[Request] The model did not give a usable answer (error: {errore}): the request was read without AI.",
    },
    "staffetta_aggancio": {
        "it": "[Staffetta] Passaggi della melodia agganciati con una nota in comune: {n}. Chi cede la melodia suona anche la prima nota di chi la riceve.",
        "en": "[Relay] Melody hand-overs linked by a shared note: {n}. The outgoing instrument also plays the first note of the incoming one.",
    },
    "equilibrio": {
        "it": "[Equilibrio] {parte}: copriva la melodia, diradato e in piano nelle misure {misure}.",
        "en": "[Balance] {parte}: was covering the melody, thinned out and played piano in bars {misure}.",
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
    # ---- segni di ripresa
    "ripresa_forma": {
        "it": "[Forma] Ritornelli e salti riconosciuti: si suonano le misure {misure}.",
        "en": "[Form] Repeats and jumps recognised: the bars are played as {misure}.",
    },
    "ripresa_convenzione": {
        "it": "[Forma] Dopo il D.S./D.C. i ritornelli non si ripetono e delle volte si suona l'ultima.",
        "en": "[Form] After the D.S./D.C. repeats are not taken and only the last ending is played.",
    },
    "ripresa_volta_fuori": {
        "it": "[Forma] mis. {mis}: volta fuori da un ritornello.",
        "en": "[Form] bar {mis}: ending outside a repeat.",
    },
    "ripresa_senza_inizio": {
        "it": "[Forma] mis. {mis}: ritornello senza segno d'inizio dopo un altro ritornello: si riprende da mis. {da}.",
        "en": "[Form] bar {mis}: repeat with no start sign after another repeat: it goes back to bar {da}.",
    },
    "ripresa_volta_mancante": {
        "it": "[Forma] mis. {mis}: nessuna volta per il passaggio {n}, si prosegue dopo le volte.",
        "en": "[Form] bar {mis}: no ending for pass {n}, playback continues after the endings.",
    },
    "ripresa_ds_senza_segno": {
        "it": "[Forma] mis. {mis}: D.S. senza Segno.",
        "en": "[Form] bar {mis}: D.S. without a Segno.",
    },
    "ripresa_coda_mancante": {
        "it": "[Forma] mis. {mis}: «al Coda» senza Coda.",
        "en": "[Form] bar {mis}: \"to Coda\" without a Coda.",
    },
    "ripresa_fine_mancante": {
        "it": "[Forma] mis. {mis}: «al Fine» senza Fine.",
        "en": "[Form] bar {mis}: \"al Fine\" without a Fine.",
    },
    "ripresa_lineare": {
        "it": "[Forma] I segni di ripresa non sono coerenti: l'anteprima suona il brano di seguito, così com'è scritto. I segni restano in partitura.",
        "en": "[Form] The repeat signs are inconsistent: the preview plays the piece straight through, as written. The signs stay in the score.",
    },
    "ripresa_legature_tolte": {
        "it": "[Forma] {n} legature di valore dell'originale interrotte a un ritornello o a una volta: le altezze non cambiano.",
        "en": "[Form] {n} ties from the original broken at a repeat or an ending: the pitches do not change.",
    },
    # ---- tonalita' comoda per l'organico
    "tonalita_suggerita": {
        "it": "[Tonalità] Più comoda per questo organico: {spostamento} (armatura da {da} a {a}). Per usarla imposta il trasporto; se no, il brano resta com'è scritto.",
        "en": "[Key] More comfortable for this ensemble: {spostamento} (key signature from {da} to {a}). To use it, set the transposition; otherwise the piece stays as written.",
    },
    "tonalita_suggerita_ui": {
        "it": "Più comoda per questo organico: {spostamento} (armatura da {da} a {a}).",
        "en": "More comfortable for this ensemble: {spostamento} (key signature from {da} to {a}).",
    },
    "tonalita_parte": {
        "it": "{strumento}: da {da} a {a}.",
        "en": "{strumento}: from {da} to {a}.",
    },
    "tonalita_melodia": {
        "it": "La melodia entra nell'estensione di {dopo} leggii su {totale} (prima {prima}).",
        "en": "The melody fits the range of {dopo} parts out of {totale} (before: {prima}).",
    },
    "trasporto_su": {"it": "{intervallo} sopra", "en": "{intervallo} up"},
    "trasporto_giu": {"it": "{intervallo} sotto", "en": "{intervallo} down"},
    "intervallo_1": {"it": "un semitono", "en": "a semitone"},
    "intervallo_2": {"it": "un tono", "en": "a whole tone"},
    "intervallo_3": {"it": "una terza minore", "en": "a minor third"},
    "intervallo_4": {"it": "una terza maggiore", "en": "a major third"},
    "intervallo_5": {"it": "una quarta", "en": "a fourth"},
    "intervallo_6": {"it": "un tritono", "en": "a tritone"},
    "armatura_nessuna": {"it": "nessuna alterazione", "en": "no sharps or flats"},
    "armatura_diesis_1": {"it": "1 diesis", "en": "1 sharp"},
    "armatura_diesis": {"it": "{n} diesis", "en": "{n} sharps"},
    "armatura_bemolli_1": {"it": "1 bemolle", "en": "1 flat"},
    "armatura_bemolli": {"it": "{n} bemolli", "en": "{n} flats"},
    # ---- editor delle sigle (sito)
    "sigle_editor_ignorate": {
        "it": "[Ingresso] Le sigle dell'editor valgono solo per la sola melodia: questo spartito ha il pianoforte, e si seguono le sue note.",
        "en": "[Input] The editor's chords only apply to a melody on its own: this score has a piano part, and its notes are followed.",
    },
    "sigla_illeggibile": {
        "it": "La sigla «{testo}» non si legge: scrivila come C, Am7, F/A oppure Do, La-7, Fa/La.",
        "en": "Can't read the chord «{testo}»: write it like C, Am7, F/A.",
    },
    # testi dei segni scritti in partitura
    "segno_ds": {"it": "D.S.", "en": "D.S."},
    "segno_ds_coda": {"it": "D.S. al Coda", "en": "D.S. al Coda"},
    "segno_ds_fine": {"it": "D.S. al Fine", "en": "D.S. al Fine"},
    "segno_dc": {"it": "D.C.", "en": "D.C."},
    "segno_dc_coda": {"it": "D.C. al Coda", "en": "D.C. al Coda"},
    "segno_dc_fine": {"it": "D.C. al Fine", "en": "D.C. al Fine"},
    "segno_al_coda": {"it": "Al Coda", "en": "To Coda"},
    "segno_fine": {"it": "Fine", "en": "Fine"},
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
