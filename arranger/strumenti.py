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
    # Note dentro l'estensione ma scomode a quel livello (MIDI a suono reale,
    # enarmonia indifferente). Non si correggono: finiscono solo come avviso
    # nel report, vedi `vincoli.avviso_note_scomode`.
    note_scomode: Dict[str, tuple] = field(default_factory=dict)
    # Peso di sonorita' nel forte di UNA parte (un leggio di ragazzi), per
    # l'equilibrio fra chi canta e chi accompagna. Da Rimskij-Korsakov (1
    # tromba = 2 corni = 4 legni), adattato alla scuola: un leggio d'archi
    # di due o tre ragazzi vale circa un legno. Vedi `equilibra_sonorita`.
    peso: float = 1.0

    def ambito(self, livello: str) -> tuple:
        from .lingua import normalizza_livello
        chiave = normalizza_livello(livello)
        if e_primo_quadrimestre(chiave):
            return self._ambito_primo_quadrimestre(anno_livello(chiave))
        return self.estensione.get(chiave, self.estensione["3a Media"])

    def _ambito_primo_quadrimestre(self, anno: str) -> tuple:
        """
        Estensione nel 1o quadrimestre: a meta' fra la fine dell'anno prima
        e la fine di questo (arrotondando verso l'interno). In 1a Media non
        c'e' un anno prima: l'estensione di fine 1a si accorcia di una 3a
        maggiore in alto, restando larga almeno una 5a.
        STIMA da confermare con i docenti di strumento, come il corno.
        """
        lo2, hi2 = self.estensione[anno]
        if anno == "1a Media":
            return (lo2, max(lo2 + 7, hi2 - 4)) if hi2 - lo2 > 7 else (lo2, hi2)
        precedente = CHIAVI_ANNO[CHIAVI_ANNO.index(anno) - 1]
        lo1, hi1 = self.estensione[precedente]
        return (lo1 + lo2 + 1) // 2, (hi1 + hi2) // 2


# --------------------------------------------------------------------------
# Registro
# --------------------------------------------------------------------------

REGISTRO: Dict[str, Strumento] = {
    "flauto": Strumento(
        chiave="flauto", nome="Flauto", abbrev="Fl.",
        # il flauto scende realmente al Do4: fermarsi al Do5 costringeva a
        # ribaltare d'ottava mezze melodie
        estensione={"1a Media": (62, 84), "2a Media": (60, 88), "3a Media": (60, 93)},
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
        chiave="sax", peso=2.0, nome="Sax Contralto", abbrev="Sax A.",
        estensione={"1a Media": (58, 72), "2a Media": (56, 77), "3a Media": (51, 84)},
        trasposizione=9, programma_midi=65, famiglia="fiati",
        ruoli=["melodia", "controcanto", "armonia"],
    ),
    "corno": Strumento(
        chiave="corno", peso=2.0, nome="Corno in Fa", abbrev="Cr.",
        # Scritto una quinta giusta sopra il suono reale. Estensioni a suono
        # reale, ricavate dagli ambiti scritti tipici dei primi anni (DA
        # VERIFICARE con un docente di corno):
        #   1a Media  scritto Do4-Do5  -> reale Fa3-Fa4
        #   2a Media  scritto Sol3-Mi5 -> reale Do3-La4
        #   3a Media  scritto Fa3-Sol5 -> reale Sib2-Do5
        estensione={"1a Media": (53, 65), "2a Media": (48, 69), "3a Media": (46, 72)},
        trasposizione=7, programma_midi=60, famiglia="ottoni",
        ruoli=["melodia", "controcanto", "armonia"],
    ),
    "tromba": Strumento(
        chiave="tromba", peso=4.0, nome="Tromba in Sib", abbrev="Tr.",
        estensione={"1a Media": (58, 72), "2a Media": (56, 77), "3a Media": (54, 82)},
        trasposizione=2, programma_midi=56, famiglia="ottoni",
        ruoli=["melodia", "controcanto", "armonia"],
    ),
    "violino": Strumento(
        chiave="violino", nome="Violino", abbrev="Vl.",
        # 1a Media: prima posizione intera, fino al Si5 col 4o dito sul Mi
        # (guida Alfred grado 1 e programma di violino di una collega: vedi
        # docs/principi_arrangiamento.md). Prima si fermava al Mi a vuoto.
        # La 2a Media (prima 81) sale almeno quanto la 1a; la terza posizione
        # (fino al Mi6) resta da decidere.
        estensione={"1a Media": (55, 83), "2a Media": (55, 83), "3a Media": (55, 88)},
        programma_midi=40, famiglia="archi", corde=[55, 62, 69, 76],
        # prima e seconda applicazione: mancano il 1o dito basso e il 3o
        # dito alto su ogni corda (Lab3 Do#4 Mib4 Sol#4 Sib4 Re#5 Fa5 La#5)
        note_scomode={"1a Media": (56, 61, 63, 68, 70, 75, 77, 82)},
        ruoli=["melodia", "controcanto", "armonia"],
    ),
    "violoncello": Strumento(
        chiave="violoncello", nome="Violoncello", abbrev="Vc.",
        # 1a Media: prima posizione stretta, fino al Re4 col 4o dito sul La
        # (prima si fermava al La a vuoto). 3a Media: fino al Sol4, il Sol con
        # tre tagli sopra il pentagramma in chiave di basso (prima Do5, troppo
        # alto). Confermato da un docente di violoncello il 30/10/2026: vedi
        # docs/principi_arrangiamento.md
        estensione={"1a Media": (36, 62), "2a Media": (36, 62), "3a Media": (36, 67)},
        chiave_musicale="F", programma_midi=42, famiglia="archi", corde=[36, 43, 50, 57],
        # senza estensioni della mano: mancano +1 e +6 sopra ogni corda vuota
        # (Do#2 Fa#2 Sol#2 Do#3 Mib3 Sol#3 Sib3; il Re#4 e' gia' fuori)
        note_scomode={"1a Media": (37, 42, 44, 49, 51, 56, 58)},
        ruoli=["basso", "armonia", "controcanto", "melodia"],
    ),
    "chitarra": Strumento(
        chiave="chitarra", peso=0.5, nome="Chitarra", abbrev="Chit.",
        estensione={"1a Media": (40, 64), "2a Media": (40, 69), "3a Media": (40, 76)},
        chiave_musicale="G", ottava_chiave=-1, monofonico=False, polifonia_max=6,
        programma_midi=24, famiglia="corde", puo_sigle=True,
        corde=[40, 45, 50, 55, 59, 64],
        ruoli=["armonia", "ritmo", "melodia", "basso"],
    ),
    "pianoforte": Strumento(
        chiave="pianoforte", peso=2.0, nome="Pianoforte", abbrev="Pf.",
        # il pianoforte legge in due chiavi: il registro grave non e' un
        # problema di difficolta', e comprimerlo snatura i bassi
        estensione={"1a Media": (36, 84), "2a Media": (33, 88), "3a Media": (28, 96)},
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
        chiave="percussioni", peso=2.0, nome="Percussioni", abbrev="Perc.",
        estensione={"1a Media": (38, 38), "2a Media": (38, 42), "3a Media": (35, 51)},
        chiave_musicale="percussion", monofonico=False, polifonia_max=3,
        programma_midi=0, famiglia="percussioni", percussione=True,
        ruoli=["ritmo"],
    ),
}

ORDINE_PARTITURA = [
    "flauto", "clarinetto", "sax", "corno", "tromba", "percussioni", "glockenspiel",
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
    fiato_max: float = 6.0        # quarti di suono continuo prima del respiro
    note: str = ""


LIVELLI: Dict[str, Livello] = {
    "1a Media": Livello(
        nome="1a Media", durata_minima=1.0, salto_massimo=7, alterazioni=False,
        accordi_max=2, arpeggi=False, sincopi=False, cambi_posizione=False,
        tastiera_max_semitoni=9, capotasto_max=3, fiato_max=4.0,
        note="Prima posizione, ritmi base (minime/semiminime), bicordi, salti entro la 5a.",
    ),
    "2a Media": Livello(
        nome="2a Media", durata_minima=0.5, salto_massimo=12, alterazioni=True,
        accordi_max=3, arpeggi=True, sincopi=False, cambi_posizione=False,
        tastiera_max_semitoni=12, capotasto_max=5, fiato_max=6.0,
        note="Note alterate, arpeggi base, crome, prime estensioni d'ottava.",
    ),
    "3a Media": Livello(
        nome="3a Media", durata_minima=0.25, salto_massimo=19, alterazioni=True,
        accordi_max=6, arpeggi=True, sincopi=True, cambi_posizione=True,
        tastiera_max_semitoni=14, capotasto_max=9, fiato_max=8.0,
        note="Semicrome, cambi di posizione, accordi completi, salti ampi, sincopi.",
    ),
}


# --------------------------------------------------------------------------
# Quadrimestri
# --------------------------------------------------------------------------
#
# I limiti di LIVELLI sono quelli di FINE anno (2o quadrimestre). Il 1o
# quadrimestre e' una via di mezzo fra la fine dell'anno prima e la fine di
# questo, cosi' lo stesso brano si suona a ottobre e, piu' ricco, a maggio.
# Le chiavi del 1o quadrimestre sono quelle dell'anno con SUFFISSO_Q1
# ("2a Media Q1"): le chiavi dell'anno non cambiano. Solo in italiano:
# l'interfaccia inglese resta sui Grade 1/2/3.

CHIAVI_ANNO = ["1a Media", "2a Media", "3a Media"]
SUFFISSO_Q1 = " Q1"

LIVELLI_PRIMO_QUADRIMESTRE: Dict[str, Livello] = {
    # STIMA del 3/11/2026 approvata dall'autore; da confermare in classe
    "1a Media" + SUFFISSO_Q1: Livello(
        nome="1a Media" + SUFFISSO_Q1, durata_minima=1.0, salto_massimo=5,
        alterazioni=False, accordi_max=1, arpeggi=False, sincopi=False,
        cambi_posizione=False, tastiera_max_semitoni=7, capotasto_max=2,
        fiato_max=3.0,
        note="Note singole, minime e semiminime, salti entro la 4a, posizione fissa.",
    ),
    "2a Media" + SUFFISSO_Q1: Livello(
        nome="2a Media" + SUFFISSO_Q1, durata_minima=0.5, salto_massimo=9,
        alterazioni=True, accordi_max=2, arpeggi=True, sincopi=False,
        cambi_posizione=False, tastiera_max_semitoni=10, capotasto_max=4,
        fiato_max=5.0,
        note="Prime crome e alterazioni, arpeggi semplici, salti entro la 6a.",
    ),
    "3a Media" + SUFFISSO_Q1: Livello(
        nome="3a Media" + SUFFISSO_Q1, durata_minima=0.5, salto_massimo=15,
        alterazioni=True, accordi_max=4, arpeggi=True, sincopi=True,
        cambi_posizione=False, tastiera_max_semitoni=13, capotasto_max=7,
        fiato_max=7.0,
        note="Crome, sincopi, accordi di quattro note, salti entro la 10a.",
    ),
}


def e_primo_quadrimestre(chiave: Optional[str]) -> bool:
    return bool(chiave) and str(chiave).endswith(SUFFISSO_Q1)


def anno_livello(chiave: Optional[str]) -> Optional[str]:
    """La classe senza il quadrimestre: "2a Media Q1" -> "2a Media"."""
    from .lingua import normalizza_livello
    if e_primo_quadrimestre(chiave):
        chiave = chiave[:-len(SUFFISSO_Q1)]
    return normalizza_livello(chiave)


def chiave_quadrimestre(chiave: Optional[str], quadrimestre: int) -> Optional[str]:
    """La chiave del livello nel quadrimestre dato (1 o 2; 0 = nessuno = 2)."""
    if chiave is None:
        return None
    anno = anno_livello(chiave)
    if quadrimestre == 1 and anno in CHIAVI_ANNO:
        return anno + SUFFISSO_Q1
    return anno


def grado_livello(chiave: Optional[str]) -> float:
    """Per confrontare due livelli: 1a Q1 = 0.5, 1a = 1, 2a Q1 = 1.5, ..."""
    anno = anno_livello(chiave)
    g = CHIAVI_ANNO.index(anno) + 1.0 if anno in CHIAVI_ANNO else 3.0
    return g - 0.5 if e_primo_quadrimestre(chiave) else g


def livello(nome: str) -> Livello:
    from .lingua import normalizza_livello
    chiave = normalizza_livello(nome)
    if chiave in LIVELLI_PRIMO_QUADRIMESTRE:
        return LIVELLI_PRIMO_QUADRIMESTRE[chiave]
    return LIVELLI.get(chiave, LIVELLI["3a Media"])


def livello_parte(livello_parte_: Optional[str],
                  livello_partitura: str) -> Livello:
    """
    Il livello da applicare a una parte: il suo, se ce l'ha, altrimenti
    quello della partitura.

    Esiste perche' le classi eterogenee sono la norma nella scuola media.
    Un livello unico per tutta l'orchestra obbliga a scegliere fra annoiare
    chi suona da tre anni e travolgere chi ha cominciato a ottobre; potendo
    indicarlo strumento per strumento, la stessa partitura sta insieme
    davvero.

    Il valore None della parte significa «come la partitura», e non e' la
    stessa cosa di «1a Media»: serve a distinguere una parte per cui il
    professore non ha detto niente da una che ha messo espressamente al
    livello piu' basso.
    """
    return livello(livello_parte_ or livello_partitura)


def nome_livello_parte(livello_parte_: Optional[str],
                       livello_partitura: str) -> str:
    """Come sopra ma restituisce il nome, per `Strumento.ambito`."""
    return livello_parte_ or livello_partitura


def strumento(chiave: str) -> Strumento:
    return REGISTRO[chiave]


def nomi_parti(chiave: str, quantita: int, lingua: str = "it") -> List[str]:
    """Genera i nomi dei divisi: 'Flauto' se 1, 'Flauto 1'/'Flauto 2' se piu'."""
    from .lingua import nome_strumento
    nome = nome_strumento(chiave, lingua)
    if quantita <= 1:
        return [nome]
    return [f"{nome} {i + 1}" for i in range(quantita)]
