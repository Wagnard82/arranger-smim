"""
Modello dati interno di Arranger SMIM.

Tutto il sistema lavora su questa rappresentazione neutra (nessuna dipendenza
esterna). MusicXML / MIDI / audio entrano da `ingestion`, escono da `esportatore`.

Convenzioni:
  - le durate e gli offset sono espressi in QUARTI (float), non in tick;
  - le altezze sono MIDI *reali* (suono reale, non scrittura trasposta);
  - l'anacrusi e' gestita esplicitamente: la misura 0 puo' essere piu' corta.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# --------------------------------------------------------------------------
# Nomi delle note (italiano + anglosassone)
# --------------------------------------------------------------------------

NOMI_IT = ["Do", "Do#", "Re", "Re#", "Mi", "Fa", "Fa#", "Sol", "Sol#", "La", "La#", "Si"]
NOMI_EN = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def nome_it(midi: int) -> str:
    return f"{NOMI_IT[midi % 12]}{midi // 12 - 1}"


def nome_en(midi: int) -> str:
    return f"{NOMI_EN[midi % 12]}{midi // 12 - 1}"


# --------------------------------------------------------------------------
# Eventi
# --------------------------------------------------------------------------


@dataclass
class Nota:
    """Una singola nota del master pianistico."""

    midi: int
    inizio: float          # offset globale in quarti
    durata: float          # in quarti
    rigo: int = 1          # 1 = chiave di violino (mano dx), 2 = basso (mano sx)
    voce: int = 1
    legata_dopo: bool = False
    legata_prima: bool = False

    @property
    def fine(self) -> float:
        return self.inizio + self.durata

    def suona_a(self, t: float) -> bool:
        return self.inizio <= t < self.fine - 1e-6


@dataclass
class Misura:
    """Contenitore metrico. `durata` puo' essere ridotta in caso di anacrusi."""

    numero: int            # 1-based; 0 se anacrusi
    inizio: float
    durata: float
    num: int = 4           # numeratore
    den: int = 4           # denominatore
    tonalita: int = 0      # circolo delle quinte (fifths), -7..+7
    anacrusi: bool = False

    @property
    def fine(self) -> float:
        return self.inizio + self.durata

    @property
    def durata_piena(self) -> float:
        return self.num * 4.0 / self.den

    @property
    def composto(self) -> bool:
        """6/8, 9/8, 12/8...: il movimento e' la semiminima puntata."""
        return self.den == 8 and self.num % 3 == 0 and self.num > 3

    @property
    def unita_movimento(self) -> float:
        """Durata di un movimento in quarti (1.5 nei tempi composti)."""
        return 1.5 if self.composto else 4.0 / self.den

    @property
    def parziale(self) -> bool:
        """Misura piu' corta del metro: anacrusi o levare di sezione."""
        return self.durata < self.durata_piena - 1e-6


@dataclass
class Spartito:
    """Il 'master' pianistico prodotto dal Modulo 1."""

    titolo: str = "Senza titolo"
    compositore: str = ""
    note: List[Nota] = field(default_factory=list)
    misure: List[Misura] = field(default_factory=list)
    bpm: float = 90.0
    anacrusi: float = 0.0  # durata in quarti della battuta di levare (0 = nessuna)
    dinamiche: List[Tuple[float, str]] = field(default_factory=list)
    # [(offset in quarti, "p"/"mf"/"ff"/...)] lette dallo spartito originale
    gradazioni: List[Tuple[float, float, str]] = field(default_factory=list)
    # [(inizio, fine, "crescendo"/"diminuendo")] dalle forcelle <wedge>

    # ---------------------------------------------------------------- utilita'
    @property
    def durata_totale(self) -> float:
        return max((m.fine for m in self.misure), default=0.0)

    def misura_a(self, t: float) -> Optional[Misura]:
        for m in self.misure:
            if m.inizio - 1e-6 <= t < m.fine - 1e-6:
                return m
        return self.misure[-1] if self.misure else None

    def note_in(self, inizio: float, fine: float) -> List[Nota]:
        """Note che *suonano* (anche solo parzialmente) nell'intervallo."""
        return [n for n in self.note if n.inizio < fine - 1e-6 and n.fine > inizio + 1e-6]

    def attacchi(self) -> List[float]:
        """Istanti distinti in cui parte almeno una nota, ordinati."""
        return sorted({round(n.inizio, 6) for n in self.note})

    def ordina(self) -> None:
        self.note.sort(key=lambda n: (n.inizio, -n.midi))


# --------------------------------------------------------------------------
# Analisi (Modulo 3.1)
# --------------------------------------------------------------------------


@dataclass
class Accordo:
    """Accordo dedotto su un movimento (o frazione di esso)."""

    inizio: float
    durata: float
    fondamentale: int          # pitch class 0..11
    qualita: str = "maj"       # maj, min, dom7, min7, maj7, dim, aug, sus4, 6, m6, dim7, m7b5
    basso: Optional[int] = None  # pitch class del basso, se rivolto
    confidenza: float = 0.0

    @property
    def fine(self) -> float:
        return self.inizio + self.durata

    def sigla(self) -> str:
        suff = {
            "maj": "", "min": "m", "dom7": "7", "min7": "m7", "maj7": "maj7",
            "dim": "dim", "aug": "aug", "sus4": "sus4", "6": "6", "m6": "m6",
            "dim7": "dim7", "m7b5": "m7b5",
        }[self.qualita]
        s = NOMI_EN[self.fondamentale] + suff
        if self.basso is not None and self.basso != self.fondamentale:
            s += "/" + NOMI_EN[self.basso]
        return s

    def note_accordo(self) -> List[int]:
        """Pitch class dell'accordo."""
        intervalli = {
            "maj": [0, 4, 7], "min": [0, 3, 7], "dom7": [0, 4, 7, 10],
            "min7": [0, 3, 7, 10], "maj7": [0, 4, 7, 11], "dim": [0, 3, 6],
            "aug": [0, 4, 8], "sus4": [0, 5, 7], "6": [0, 4, 7, 9],
            "m6": [0, 3, 7, 9], "dim7": [0, 3, 6, 9], "m7b5": [0, 3, 6, 10],
        }[self.qualita]
        return [(self.fondamentale + i) % 12 for i in intervalli]


@dataclass
class Analisi:
    """I 4 layer astratti estratti dal master."""

    melodia: List[Nota] = field(default_factory=list)
    armonia: List[Accordo] = field(default_factory=list)
    basso: List[Nota] = field(default_factory=list)
    groove: List[float] = field(default_factory=list)   # posizioni d'attacco tipiche (in quarti dalla stanghetta)
    suddivisione: float = 0.5                            # 1.0=semiminime, 0.5=crome, 0.25=semicrome
    frasi: List[Tuple[float, float]] = field(default_factory=list)  # (inizio, fine) in quarti


# --------------------------------------------------------------------------
# Parti strumentali (Modulo 3.2 / 3.3)
# --------------------------------------------------------------------------


@dataclass
class Evento:
    """Evento di una parte strumentale: accordo, nota singola o pausa."""

    inizio: float
    durata: float
    altezze: List[int] = field(default_factory=list)   # vuoto = pausa
    articolazione: Optional[str] = None                # staccato, accent, tenuto, pizzicato, tremolo, arco
    dinamica: Optional[str] = None                     # p, mf, f ...
    gradazione: Optional[str] = None                   # crescendo / diminuendo
    fine_gradazione: bool = False                      # chiude la forcella
    sigla: Optional[str] = None                        # sigla accordale da stampare
    legata_dopo: bool = False
    testo: Optional[str] = None
    rigo: int = 1                 # per strumenti a due righi (pianoforte)

    @property
    def fine(self) -> float:
        return self.inizio + self.durata

    @property
    def pausa(self) -> bool:
        return not self.altezze


@dataclass
class Parte:
    """Una parte (= un rigo) della partitura finale."""

    id: str
    nome: str                    # "Flauto 1"
    abbrev: str                   # "Fl. 1"
    strumento: str                # chiave del registro strumenti
    eventi: List[Evento] = field(default_factory=list)
    ruolo: str = "armonia"        # melodia, controcanto, armonia, basso, ritmo
    chiave: str = "G"             # G, F, C, percussion
    ottava_chiave: int = 0
    trasposizione: int = 0        # semitoni: scritto = suono + trasposizione
    monofonico: bool = True
    programma_midi: int = 74
    mostra_sigle: bool = False
    righi: int = 1                # 2 per il pianoforte
    variante: int = 0             # indice del diviso: differenzia le scritture
                                  # fra Pianoforte 1 e 2, Chitarra 1 e 2, ecc.

    def ordina(self) -> None:
        self.eventi.sort(key=lambda e: (e.inizio, -max(e.altezze) if e.altezze else 0))


@dataclass
class Partitura:
    """Output del Modulo 3, input del Modulo 4."""

    titolo: str = "Arrangiamento"
    compositore: str = ""
    sottotitolo: str = ""
    parti: List[Parte] = field(default_factory=list)
    misure: List[Misura] = field(default_factory=list)
    bpm: float = 90.0
    stile: str = "Normale"
    livello: str = "1a Media"
    swing: bool = False
    armonia: List["Accordo"] = field(default_factory=list)
    report: List[str] = field(default_factory=list)   # log dei filtri di validazione

    def parte(self, id_: str) -> Optional[Parte]:
        for p in self.parti:
            if p.id == id_:
                return p
        return None


# --------------------------------------------------------------------------
# Configurazione utente (Modulo 2)
# --------------------------------------------------------------------------


@dataclass
class Configurazione:
    formazione: Dict[str, int] = field(default_factory=dict)  # {"flauto": 2, "violino": 2, ...}
    livello: str = "1a Media"
    stile: str = "Normale"
    tonalita_originale: bool = True
    trasporto: int = 0                 # semitoni di trasporto globale
    strumenti_melodia: List[str] = field(default_factory=list)
    # id delle parti abilitate a portare la melodia (vuoto = decide il motore)
    staffetta_melodia: bool = True     # la melodia passa fra piu' strumenti
    raddoppi_melodia: bool = True
    usa_ia: bool = False
    modello_ia: str = "claude-sonnet-4-6"

    def strumenti_attivi(self) -> List[str]:
        return [k for k, v in self.formazione.items() if v > 0]
