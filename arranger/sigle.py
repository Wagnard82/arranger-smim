"""
Sigle per l'editor del sito: lettura del testo scritto dal docente,
scrittura in forma standard, tavolozza della tonalita', proposta di
partenza e MusicXML della melodia con le sigle da disegnare.

Il docente puo' scrivere la sigla come in Dorico o MuseScore (C, Am7, F/A,
Bb7) o all'italiana (Do, La-7, Fa/La, Sib): la forma standard usa sempre le
lettere inglesi, come le sigle che il motore scrive in partitura.

Forma di una sigla nel motore: (istante in quarti, fondamentale pc,
qualita', basso pc o None), la stessa di Spartito.sigle.
"""

from __future__ import annotations

from typing import Optional, Tuple

from .esportatore import sigla_scritta
from .modello import Accordo

# nomi italiani prima delle lettere: "Do" e' Do, non Re diminuito
_NOMI_IT = (("sol", 7), ("do", 0), ("re", 2), ("mi", 4), ("fa", 5), ("la", 9), ("si", 11))
_LETTERE = {"c": 0, "d": 2, "e": 4, "f": 5, "g": 7, "a": 9, "b": 11}
_ALTERAZIONI = {"#": 1, "♯": 1, "b": -1, "♭": -1}

# suffisso -> qualita' del modello (maiuscole e minuscole contano: M7 e m7)
_SUFFISSI = {
    "": "maj", "maj": "maj", "M": "maj",
    "m": "min", "-": "min", "min": "min", "mi": "min",
    "7": "dom7",
    "m7": "min7", "-7": "min7", "min7": "min7",
    "maj7": "maj7", "M7": "maj7", "Δ": "maj7", "Δ7": "maj7", "7M": "maj7",
    "dim": "dim", "°": "dim", "o": "dim",
    "dim7": "dim7", "°7": "dim7", "o7": "dim7",
    "m7b5": "m7b5", "ø": "m7b5", "ø7": "m7b5", "-7b5": "m7b5",
    "aug": "aug", "+": "aug", "#5": "aug",
    "sus4": "sus4", "sus": "sus4", "7sus4": "sus4",
    "6": "6",
    "m6": "m6", "-6": "m6",
    # forme fuori vocabolario, ricondotte alla piu' vicina
    "add9": "maj", "sus2": "maj", "5": "maj",
    "9": "dom7", "13": "dom7", "m9": "min7", "maj9": "maj7",
}


def _fondamentale(testo: str) -> Tuple[Optional[int], str]:
    """(classe d'altezza, resto del testo); None se non comincia con una nota."""
    basso = testo.lower()
    radice, resto = None, ""
    for nome, pc in _NOMI_IT:
        if basso.startswith(nome):
            radice, resto = pc, testo[len(nome):]
            break
    if radice is None and basso[:1] in _LETTERE:
        radice, resto = _LETTERE[basso[0]], testo[1:]
    if radice is None:
        return None, testo
    if resto[:1] in _ALTERAZIONI:
        radice = (radice + _ALTERAZIONI[resto[0]]) % 12
        resto = resto[1:]
    return radice, resto


def leggi_sigla(testo: str) -> Optional[Tuple[int, str, Optional[int]]]:
    """
    «Am7», «F/A», «Bb», «C#m7b5», «G7sus4», «La-7», «Lam», «Fa/La», «Sib»
    -> (fondamentale, qualita', basso); None se non e' una sigla.
    """
    testo = (testo or "").strip().replace(" ", "")
    if not testo:
        return None
    corpo, _, dopo = testo.partition("/")
    radice, suffisso = _fondamentale(corpo)
    if radice is None or suffisso not in _SUFFISSI:
        return None
    basso = None
    if dopo:
        basso, avanzo = _fondamentale(dopo)
        if basso is None or avanzo:
            return None
        if basso == radice:
            basso = None
    return radice, _SUFFISSI[suffisso], basso


def scrivi_sigla(fondamentale: int, qualita: str, basso: Optional[int],
                 fifths: int) -> str:
    """La forma standard, come in partitura: 'Bb', 'F#m7', 'C/E'."""
    return sigla_scritta(Accordo(inizio=0, durata=1, fondamentale=fondamentale,
                                 qualita=qualita, basso=basso), fifths)
