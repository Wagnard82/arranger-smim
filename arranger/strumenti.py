"""
Registro strumenti + regole didattiche per livello (Modulo 2 / Modulo 3.3).

Le estensioni sono espresse in MIDI a SUONO REALE.
`trasposizione` = semitoni da aggiungere al suono reale per ottenere la
scrittura (clarinetto in Sib: scritto = suono + 2).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

# --------------------------------------------------------------------------


@dataclass
class Strumento:
    chiave: str
    nome: str
    abbrev: str
    # estensione a suono reale per livello didattico
    estensione: Dict[str, tuple]
    trasposizione: int = 0
    chiave_musicale: str = "G"
    ottava_chiave: int = 0
    monofonico: bool = True
    polifonia_max: int = 1
    programma_midi: int = 74
    ruoli: List[str] = field(default_factory=lambda: ["melodia", "controcanto", "armonia"])
    famiglia: str = "fiati"
    puo_sigle: bool = False
    righi: int = 1
    percussione: bool = False
    # nota: per gli archi, prima posizione = limite superiore stretto al livello 1
    corde: List[int] = field(default_factory=list)

    def ambito(self, livello: str) -> tuple:
        return self.estensione.get(livello, self.estensione["3a Media"])


# --------------------------------------------------------------------------
# Registro
# --------------------------------------------------------------------------

REGISTRO: Dict[str, Strumento] = {
    "flauto": Strumento(
        chiave="flauto", nome="Flauto", abbrev="Fl.",
        estensione={"1a Media": (72, 84), "2a Media": (72, 88), "3a Media": (72, 93)},
        programma_midi=73, famiglia="fiati",
        ruoli=["melodia", "controcanto", "armonia"],
    ),
    "clarinetto": Strumento(
        chiave="clarinetto", nome="Clarinetto in Sib", abbrev="Cl.",
        estensione={"1a Media": (62, 74), "2a Media": (58, 79), "3a Media": (50, 86)},
        trasposizione=2, programma_midi=71, famiglia="fiati",
        ruoli=["melodia", "controcanto", "armonia"],
    ),
    "sax": Strumento(
        chiave="sax", nome="Sax Contralto", abbrev="Sax A.",
        estensione={"1a Media": (58, 72), "2a Media": (56, 77), "3a Media": (51, 84)},
        trasposizione=9, programma_midi=65, famiglia="fiati",
        ruoli=["melodia", "controcanto", "armonia"],
    ),
    "tromba": Strumento(
        chiave="tromba", nome="Tromba in Sib", abbrev="Tr.",
        estensione={"1a Media": (60, 72), "2a Media": (58, 77), "3a Media": (55, 82)},
        trasposizione=2, programma_midi=56, famiglia="ottoni",
        ruoli=["melodia", "controcanto", "armonia"],
    ),
    "violino": Strumento(
        chiave="violino", nome="Violino", abbrev="Vl.",
        estensione={"1a Media": (55, 76), "2a Media": (55, 81), "3a Media": (55, 88)},
        programma_midi=40, famiglia="archi", corde=[55, 62, 69, 76],
        ruoli=["melodia", "controcanto", "armonia"],
    ),
    "violoncello": Strumento(
        chiave="violoncello", nome="Violoncello", abbrev="Vc.",
        estensione={"1a Media": (36, 57), "2a Media": (36, 62), "3a Media": (36, 72)},
        chiave_musicale="F", programma_midi=42, famiglia="archi", corde=[36, 43, 50, 57],
        ruoli=["basso", "armonia", "controcanto", "melodia"],
    ),
    "chitarra": Strumento(
        chiave="chitarra", nome="Chitarra", abbrev="Chit.",
        estensione={"1a Media": (40, 64), "2a Media": (40, 69), "3a Media": (40, 76)},
        chiave_musicale="G", ottava_chiave=-1, monofonico=False, polifonia_max=6,
        programma_midi=24, famiglia="corde", puo_sigle=True,
        corde=[40, 45, 50, 55, 59, 64],
        ruoli=["armonia", "ritmo", "melodia", "basso"],
    ),
    "pianoforte": Strumento(
        chiave="pianoforte", nome="Pianoforte", abbrev="Pf.",
        # il pianoforte legge in due chiavi: il registro grave non e' un
        # problema di difficolta', e comprimerlo snatura i bassi
        estensione={"1a Media": (40, 84), "2a Media": (36, 88), "3a Media": (28, 96)},
        monofonico=False, polifonia_max=8, programma_midi=0, famiglia="tastiere",
        righi=2, puo_sigle=False,
        ruoli=["armonia", "basso", "ritmo", "melodia"],
    ),
    "glockenspiel": Strumento(
        chiave="glockenspiel", nome="Glockenspiel", abbrev="Glock.",
        estensione={"1a Media": (72, 91), "2a Media": (72, 96), "3a Media": (72, 100)},
        monofonico=False, polifonia_max=2, programma_midi=9, famiglia="percussioni",
        ruoli=["melodia", "controcanto"], percussione=False,
    ),
    "metallofono": Strumento(
        chiave="metallofono", nome="Metallofono", abbrev="Met.",
        estensione={"1a Media": (60, 79), "2a Media": (60, 84), "3a Media": (60, 88)},
        monofonico=False, polifonia_max=2, programma_midi=11, famiglia="percussioni",
        ruoli=["melodia", "armonia", "controcanto"],
    ),
    "percussioni": Strumento(
        chiave="percussioni", nome="Percussioni", abbrev="Perc.",
        estensione={"1a Media": (38, 38), "2a Media": (38, 42), "3a Media": (35, 51)},
        chiave_musicale="percussion", monofonico=False, polifonia_max=3,
        programma_midi=0, famiglia="percussioni", percussione=True,
        ruoli=["ritmo"],
    ),
}

ORDINE_PARTITURA = [
    "flauto", "clarinetto", "sax", "tromba", "percussioni", "glockenspiel",
    "metallofono", "pianoforte", "chitarra", "violino", "violoncello",
]

# Suoni di percussione non intonata (note MIDI canale 10)
PERC_MIDI = {"grancassa": 36, "rullante": 38, "charleston": 42, "charleston_aperto": 46,
             "ride": 51, "piatto": 49, "tom": 45, "claves": 75, "tamburello": 54}


# --------------------------------------------------------------------------
# Livelli didattici
# --------------------------------------------------------------------------


@dataclass
class Livello:
    nome: str
    durata_minima: float          # in quarti: 1.0 = semiminima, 0.5 = croma, 0.25 = semicroma
    salto_massimo: int            # semitoni ammessi fra note consecutive (accompagnamento)
    alterazioni: bool             # ammesse note fuori tonalita'
    accordi_max: int              # note massime per accordo su chitarra/piano
    arpeggi: bool
    sincopi: bool
    cambi_posizione: bool
    tastiera_max_semitoni: int    # apertura massima della mano al pianoforte
    capotasto_max: int            # tasto massimo utilizzabile sulla chitarra
    note: str = ""


LIVELLI: Dict[str, Livello] = {
    "1a Media": Livello(
        nome="1a Media", durata_minima=1.0, salto_massimo=7, alterazioni=False,
        accordi_max=2, arpeggi=False, sincopi=False, cambi_posizione=False,
        tastiera_max_semitoni=9, capotasto_max=3,
        note="Prima posizione, ritmi base (minime/semiminime), bicordi, salti entro la 5a.",
    ),
    "2a Media": Livello(
        nome="2a Media", durata_minima=0.5, salto_massimo=12, alterazioni=True,
        accordi_max=3, arpeggi=True, sincopi=False, cambi_posizione=False,
        tastiera_max_semitoni=12, capotasto_max=5,
        note="Note alterate, arpeggi base, crome, prime estensioni d'ottava.",
    ),
    "3a Media": Livello(
        nome="3a Media", durata_minima=0.25, salto_massimo=19, alterazioni=True,
        accordi_max=6, arpeggi=True, sincopi=True, cambi_posizione=True,
        tastiera_max_semitoni=14, capotasto_max=9,
        note="Semicrome, cambi di posizione, accordi completi, salti ampi, sincopi.",
    ),
}


def livello(nome: str) -> Livello:
    return LIVELLI.get(nome, LIVELLI["3a Media"])


def strumento(chiave: str) -> Strumento:
    return REGISTRO[chiave]


def nomi_parti(chiave: str, quantita: int) -> List[str]:
    """Genera i nomi dei divisi: 'Flauto' se 1, 'Flauto 1'/'Flauto 2' se piu'."""
    s = REGISTRO[chiave]
    if quantita <= 1:
        return [s.nome]
    return [f"{s.nome} {i + 1}" for i in range(quantita)]
