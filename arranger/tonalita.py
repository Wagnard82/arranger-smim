"""
Tonalita' comoda per l'organico: un SUGGERIMENTO, mai un trasporto
automatico.

Un brano in Mi maggiore e' comodo per la chitarra e scomodo per i
clarinetti in Sib, che leggono sei diesis. Qui si provano tutti i trasporti
da -5 a +6 semitoni (ogni tonalita' una volta) e si dice al docente se uno
di questi rende il brano davvero piu' facile per i ragazzi che ha: lui
decide se usarlo; se no, si arrangia com'e' scritto.

Il punteggio di un trasporto somma tre cose:
  * l'armatura SCRITTA di ogni leggio (contando la trasposizione dello
    strumento), pesata sul livello del leggio: oltre la soglia del livello
    la penalita' cresce col quadrato;
  * la melodia: per ogni leggio che puo' suonarla, se entra intera nella
    sua estensione di livello con uno spostamento d'ottava per blocco
    (l'unico ammesso sulla melodia);
  * la distanza dall'originale: a parita' di comodita' vince il trasporto
    piu' breve, e a pari merito la tonalita' scritta.

Il motore conosce l'armatura, non il modo: la spiegazione parla di
alterazioni in chiave, non di «Fa maggiore».
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .esportatore import fifths_scritti
from .lingua import nome_strumento, t
from .modello import Configurazione, Nota, Spartito
from .strumenti import strumento

# alterazioni in chiave che un leggio regge senza fatica, per livello
TOLLERANZA = {"1a Media": 1, "2a Media": 3, "3a Media": 4}
TRASPORTI = range(-5, 7)
# archi e chitarra leggono meglio i diesis (corde vuote): i bemolli pesano di
# piu'; il pianoforte regge tutto, le percussioni non leggono armature
PESO_BEMOLLI = {"archi": 1.5, "corde": 1.5}
PESO_FAMIGLIA = {"tastiere": 0.3, "percussioni": 0.0}
# guadagno minimo perche' valga la pena disturbare il docente
SOGLIA = 2.0


@dataclass
class Suggerimento:
    semitoni: int
    armatura_da: int                     # fifths reali, prima e dopo
    armatura_a: int
    # (strumento, alterazioni scritte prima, dopo), dal miglioramento piu' grande
    parti: List[Tuple[str, int, int]] = field(default_factory=list)
    melodia_prima: int = 0               # leggii in cui la melodia entra
    melodia_dopo: int = 0
    leggii_melodia: int = 0

    def testo(self, lingua: str = "it") -> str:
        """La spiegazione per il docente, dai cataloghi."""
        verso = "trasporto_su" if self.semitoni > 0 else "trasporto_giu"
        righe = [t("tonalita_suggerita", lingua,
                   spostamento=t(verso, lingua,
                                 intervallo=t(f"intervallo_{abs(self.semitoni)}", lingua)),
                   da=_armatura(self.armatura_da, lingua),
                   a=_armatura(self.armatura_a, lingua))]
        for chiave, prima, dopo in self.parti:
            righe.append(t("tonalita_parte", lingua,
                           strumento=nome_strumento(chiave, lingua),
                           da=_armatura(prima, lingua), a=_armatura(dopo, lingua)))
        if self.melodia_dopo > self.melodia_prima:
            righe.append(t("tonalita_melodia", lingua, dopo=self.melodia_dopo,
                           totale=self.leggii_melodia, prima=self.melodia_prima))
        return " ".join(righe)


def _armatura(fifths: int, lingua: str) -> str:
    if fifths == 0:
        return t("armatura_nessuna", lingua)
    tipo = "diesis" if fifths > 0 else "bemolli"
    if abs(fifths) == 1:
        return t(f"armatura_{tipo}_1", lingua)
    return t(f"armatura_{tipo}", lingua, n=abs(fifths))


def _reali(fifths: int, semitoni: int) -> int:
    """Armatura reale dopo il trasporto, come in `pipeline.trasporta`."""
    return (fifths + 7 * semitoni + 6) % 12 - 6


def _tonalita_prevalente(sp: Spartito) -> int:
    durate: Dict[int, float] = defaultdict(float)
    for m in sp.misure:
        durate[m.tonalita] += m.durata
    return max(durate, key=lambda f: (durate[f], -abs(f))) if durate else 0


def _entra(lo: int, hi: int, ambito: Tuple[int, int]) -> bool:
    """La melodia [lo, hi] entra nell'ambito spostandola d'ottava in blocco."""
    return any(lo + 12 * k >= ambito[0] and hi + 12 * k <= ambito[1]
               for k in range(-3, 4))


def suggerisci_trasporto(sp: Spartito, cfg: Configurazione,
                         melodia: Optional[List[Nota]] = None
                         ) -> Optional[Suggerimento]:
    """
    Il trasporto piu' comodo per l'organico di `cfg`, se migliora davvero
    la tonalita' scritta; None se l'originale va gia' bene. Non modifica
    lo spartito.
    """
    from .orchestratore import costruisci_parti
    parti = [p for p in costruisci_parti(cfg)
             if not strumento(p.strumento).percussione]
    if not parti or not sp.misure:
        return None
    if melodia is None:
        from .analizzatore import analizza
        melodia = analizza(sp).melodia
    altezze = [n.midi for n in melodia] or [n.midi for n in sp.note]
    lo, hi = (min(altezze), max(altezze)) if altezze else (60, 60)
    fifths0 = _tonalita_prevalente(sp)

    def livello(p) -> str:
        from .lingua import normalizza_livello
        return normalizza_livello(p.livello or cfg.livello)

    def valuta(semitoni: int):
        reali = _reali(fifths0, semitoni)
        punti = 0.3 * abs(semitoni)
        scritte = []
        entra = 0
        melodici = 0
        for p in parti:
            st = strumento(p.strumento)
            liv = livello(p)
            f = fifths_scritti(reali, p.trasposizione)
            scritte.append(f)
            n = abs(f) * (PESO_BEMOLLI.get(st.famiglia, 1.0) if f < 0 else 1.0)
            oltre = max(0.0, n - TOLLERANZA.get(liv, 4))
            punti += PESO_FAMIGLIA.get(st.famiglia, 1.0) * (3.0 * oltre * oltre + 0.2 * n)
            if "melodia" in st.ruoli:
                melodici += 1
                if _entra(lo + semitoni, hi + semitoni, st.ambito(liv)):
                    entra += 1
                else:
                    punti += 4.0
        return punti, reali, scritte, entra, melodici

    punti0, reali0, scritte0, entra0, melodici = valuta(0)
    migliore = min(TRASPORTI, key=lambda s: (valuta(s)[0], abs(s), s))
    if migliore == 0:
        return None
    punti, reali, scritte, entra, _ = valuta(migliore)
    if punti0 - punti < SOGLIA:
        return None
    # le parti che cambiano davvero, una riga per strumento
    viste: Dict[str, Tuple[int, int]] = {}
    for p, prima, dopo in zip(parti, scritte0, scritte):
        if abs(prima) - abs(dopo) >= 1 and p.strumento not in viste:
            viste[p.strumento] = (prima, dopo)
    righe = sorted(((k, a, b) for k, (a, b) in viste.items()),
                   key=lambda x: abs(x[2]) - abs(x[1]))[:3]
    if not righe and entra <= entra0:
        return None
    return Suggerimento(semitoni=migliore, armatura_da=reali0, armatura_a=reali,
                        parti=righe, melodia_prima=entra0, melodia_dopo=entra,
                        leggii_melodia=melodici)
