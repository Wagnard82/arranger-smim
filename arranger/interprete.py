"""
Interprete a regole della personalizzazione a parole: funziona SENZA IA.

Legge la richiesta del docente («melodia sempre ai violini, atmosfera da film,
un tono sotto») e la traduce negli stessi parametri che proporrebbe il
modello (vedi `richiesta.PARAMETRI`), con la stessa forma di risposta:
{"modifiche": {...}, "non_applicabili": [...], "spiegazione": ""}. La
validazione resta quella di `richiesta.applica`.

Come lavora: il testo si divide in frasi (virgole, punti, punti e virgola,
a capo) e ogni frase si confronta con un insieme chiuso di parole chiave e
costrutti, in italiano e in inglese. Una frase che non corrisponde a nessuna
regola non si indovina: finisce fra i non applicabili, con le parole del
docente. Capisce meno dell'IA, ma sempre allo stesso modo, gratis e offline.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Dict, List, Optional, Tuple

from .lingua import nome_strumento
from .lingua import t as testo

# radice della parola -> strumento del registro. L'ordine conta: il
# violoncello prima del violino, il pianoforte prima del «piano» dinamico
STRUMENTI: List[Tuple[str, str]] = [
    ("violoncell", "violoncello"), ("cell", "violoncello"),
    ("violin", "violino"),
    ("flaut", "flauto"), ("flute", "flauto"),
    ("clarinet", "clarinetto"),
    ("trombe", "tromba"), ("tromba", "tromba"), ("trumpet", "tromba"),
    ("corn", "corno"), ("horn", "corno"),
    ("sax", "sax"), ("sassofon", "sax"),
    ("chitarr", "chitarra"), ("guitar", "chitarra"),
    ("pianofort", "pianoforte"), ("pianist", "pianoforte"),
    ("glock", "glockenspiel"),
    ("metallofon", "metallofono"),
    ("percuss", "percussioni"), ("batteri", "percussioni"), ("drum", "percussioni"),
]

NEGAZIONE = r"\b(niente|senza|non|no|nessun\w*|evita\w*|without|avoid\w*|never|mai)\b"

# ampiezza in semitoni: i casi piu' lunghi prima (mezzo tono prima di tono)
AMPIEZZE: List[Tuple[str, int]] = [
    (r"mezzo\s+tono|semitono|half[\s-]?step|semitone|half[\s-]?tone", 1),
    (r"terza\s+minore|minor\s+third", 3),
    (r"terza(\s+maggiore)?|major\s+third|\bthird\b", 4),
    (r"quarta|fourth", 5),
    (r"quinta|fifth", 7),
    (r"ottava|octave", 12),
    (r"\btono\b|whole[\s-]?(step|tone)|\btone\b", 2),
]
GIU = r"\b(sotto|giu|piu\s+bass[oa]|abbass\w*|lower\w*|down|below)\b"
SU = r"\b(sopra|su|piu\s+alt[oa]|alz\w*|higher|up|above|raise\w*)\b"


def _normalizza(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.replace("’", "'").replace("'", " ")


def _strumenti_citati(frase: str) -> List[str]:
    trovati: List[str] = []
    for parola in re.findall(r"[a-z]+", frase):
        if parola in ("piano", "pianissimo"):
            # «piano» da solo e' quasi sempre la dinamica; «al piano» lo
            # strumento: si accetta solo con un articolo davanti
            if re.search(r"\b(al|il|del|dal|sul|the|on)\s+piano\b", frase):
                if "pianoforte" not in trovati:
                    trovati.append("pianoforte")
            continue
        for radice, chiave in STRUMENTI:
            if parola.startswith(radice):
                if chiave not in trovati:
                    trovati.append(chiave)
                break
    return trovati


def _parti_di(strumenti: List[str], id_parti: Dict[str, str], tutti: bool) -> List[str]:
    """Id delle parti di quegli strumenti: il primo leggio, o tutti."""
    scelte: List[str] = []
    for chiave in strumenti:
        leggii = sorted((pid for pid in id_parti if re.fullmatch(rf"{chiave}\d+", pid)),
                        key=lambda pid: int(re.sub(r"\D", "", pid)))
        scelte.extend(leggii if tutti else leggii[:1])
    return scelte


def _trasporto(frase: str) -> Optional[int]:
    if re.search(r"tonalita\s+originale|original\s+key|non\s+trasport", frase):
        return 0
    ampiezza = None
    m = re.search(r"(\d+)\s*(semiton\w*|semitones?)", frase)
    if m:
        ampiezza = int(m.group(1))
    else:
        for modello, semitoni in AMPIEZZE:
            if re.search(modello, frase):
                ampiezza = semitoni
                break
    if ampiezza is None:
        return None
    if re.search(GIU, frase):
        return -ampiezza
    if re.search(SU, frase):
        return ampiezza
    return None


def interpreta(richiesta_testo: str, id_parti: Dict[str, str],
               lingua: str = "it") -> dict:
    """La richiesta tradotta in parametri, frase per frase."""
    modifiche: Dict[str, object] = {}
    non_applicabili: List[str] = []
    riconosciute = 0
    frasi = [f.strip() for f in re.split(r"[,;.\n]+", richiesta_testo) if f.strip()]
    presenti = {re.sub(r"\d+$", "", pid) for pid in id_parti}

    for originale in frasi:
        f = _normalizza(originale)
        neg = re.search(NEGAZIONE, f) is not None
        capita = False      # almeno un'impostazione ricavata dalla frase
        spiegata = False    # gia' fra i non applicabili, con il motivo

        # livello e organico si scelgono nel pannello
        if re.search(r"\b(prima|seconda|terza|1a|2a|3a|1\^|2\^|3\^)\s+media\b|\bgrade\s*\d", f):
            non_applicabili.append(f"«{originale}» ({testo('regola_livello', lingua)})")
            continue
        if re.search(r"\b(aggiung\w*|togli\w*|rimuov\w*|add|remove)\b", f) and _strumenti_citati(f):
            non_applicabili.append(f"«{originale}» ({testo('regola_organico', lingua)})")
            continue

        # stile
        if re.search(r"film|cinema|colonna\s+sonora|soundtrack|cinemat|epic", f):
            modifiche["stile"] = "Cinematico"
            capita = True
        elif re.search(r"jazz|swing", f):
            if not neg:
                modifiche["stile"] = "Jazz"
            capita = True
        elif re.search(r"classic|normale|standard|tradizional", f):
            modifiche["stile"] = "Normale"
            capita = True

        # chi porta la melodia (e se deve restargli)
        if re.search(r"melod|tema\b|\btune\b|\btheme\b", f):
            strumenti = _strumenti_citati(f)
            if strumenti:
                mancanti = [s for s in strumenti if s not in presenti]
                if mancanti:
                    non_applicabili.append(
                        f"«{originale}» ({testo('regola_manca', lingua, strumenti=', '.join(nome_strumento(x, lingua) for x in mancanti))})")
                    spiegata = True
                parti = _parti_di([s for s in strumenti if s in presenti], id_parti,
                                  tutti=re.search(r"\b(tutti|tutte|all|both|entramb\w*)\b", f) is not None)
                if parti:
                    modifiche["strumenti_melodia"] = parti
                    capita = True
                if parti and re.search(r"\b(sempre|solo|soltanto|only|always)\b|senza\s+passar|non\s+passar", f):
                    modifiche["staffetta_melodia"] = False

        # staffetta
        if re.search(r"staffett|relay|a\s+turno|take\s+turns|altern|passa\w*\s+la\s+melod|passing\s+the\s+melod", f):
            modifiche["staffetta_melodia"] = not neg
            capita = True

        # ogni quanto cambia chi canta
        if re.search(r"ogni\s+frase|every\s+phrase", f):
            modifiche["cambio_solista"] = "frase"
            capita = True
        elif re.search(r"ogni\s+periodo|every\s+period", f):
            modifiche["cambio_solista"] = "periodo"
            capita = True
        elif re.search(r"ogni\s+sezione|every\s+section|ogni\s+strofa", f):
            modifiche["cambio_solista"] = "sezione"
            capita = True
        m = re.search(r"(?:ogni|every|almeno|at\s+least)\s+(\d+)\s*(misur\w*|bars?)", f)
        if m and re.search(r"cambi|melod|solist|switch|change|passa|staffett|relay", f):
            modifiche["misure_minime_solista"] = int(m.group(1))
            capita = True

        # raddoppi
        if re.search(r"raddopp|doubl", f):
            modifiche["raddoppi_melodia"] = not neg
            capita = True

        # pause
        m = re.search(r"(\d+)\s*(misur\w*|bars?)", f)
        if re.search(r"paus|\brests?\b|\bferm|\bidle|\btac\w*|riposa", f):
            if re.search(r"nessuno\s+(sia\s+)?ferm|tutti\s+suon\w*\s+sempre|keep\s+everyone|"
                         r"nobody\s+idle|no\s+long\s+rests|senza\s+pause\s+lunghe", f):
                modifiche["riempi_silenzi"] = True
                capita = True
            elif m and re.search(r"massim|al\s+massimo|at\s+most|non\s+piu\s+di|longest|max", f):
                modifiche["riempi_silenzi"] = True
                modifiche["silenzio_massimo_misure"] = int(m.group(1))
                capita = True
            elif re.search(r"pause\s+lunghe|long\s+rests|riposa|\btac\w*|lascia\w*\s+ferm|economi", f):
                modifiche["riempi_silenzi"] = False
                capita = True

        # trasporto
        trasporto = _trasporto(f)
        if trasporto is not None:
            modifiche["trasporto"] = trasporto
            capita = True

        # modo
        if re.search(r"per\s+registri|tessitura|by\s+register|texture", f):
            modifiche["modo"] = "tessitura"
            capita = True

        if capita:
            riconosciute += 1
        elif not spiegata:
            non_applicabili.append(f"«{originale}» ({testo('regola_non_capita', lingua)})")

    return {"modifiche": modifiche, "non_applicabili": non_applicabili,
            "spiegazione": testo("regola_sintesi", lingua, n=riconosciute, totale=len(frasi))}
