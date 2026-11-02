"""
Banco di prova dell'armonizzazione della melodia nuda.

    python banco_armonia.py XML/               # misura
    python banco_armonia.py XML/ --taratura    # prova i pesi, metodo "uno escluso"
    python banco_armonia.py XML/ --arrangia    # arrangia la sola melodia, per l'ascolto

Per ogni brano con le sigle: si tiene la sola melodia (le sigle e il
pianoforte si tolgono), la si armonizza e si confronta movimento per
movimento con le sigle vere. Stampa la percentuale di fondamentali giuste,
quella di funzioni giuste (tonica, sottodominante, dominante), i cambi
d'accordo veri e proposti, la tonalita' scelta.

I brani di prova sono commerciali: stanno in XML/, fuori dal repository.
Questo e' uno strumento da lanciare a mano, non un test.

Cosa guardare:
  * la media dei brani pop (Ipanema e My Future sono jazz: solo controllo);
  * i cambi proposti contro quelli veri: troppi = armonia agitata,
    pochi = armonia statica;
  * con --taratura, il valore "uno escluso" e' quello onesto: i pesi sono
    scelti sugli altri brani, non su quello misurato.
"""

from __future__ import annotations

import copy
import itertools
import os
import sys
from typing import Dict, List, Tuple

from arranger import analizzatore, armonizzazione, ingestione
from arranger.modello import Accordo, Nota, Spartito

CONTROLLI = ("girl-from-ipanema", "my-future")   # jazz: non sono l'obiettivo

# funzione armonica per grado della fondamentale rispetto alla tonica
# (approssimata sulla sola fondamentale: V/ii e vi hanno la stessa)
_FUNZIONE = {0: "T", 3: "T", 4: "T", 8: "T", 9: "T",
             2: "S", 5: "S",
             7: "D", 10: "D", 11: "D"}


def solo_melodia(sp: Spartito) -> Tuple[Spartito, List[Nota]]:
    """Una copia dello spartito con la sola melodia scritta, senza sigle:
    il caso in cui l'arrangiatore deve proporre l'armonia."""
    melodia = analizzatore.melodia_dello_spartito(sp)
    nudo = copy.deepcopy(sp)
    nudo.note = [Nota(midi=n.midi, inizio=n.inizio, durata=n.durata, origine=0)
                 for n in melodia]
    nudo.tipo = "lead_sheet"
    nudo.parte_solista = 0
    nudo.sigle = []
    return nudo, analizzatore.linea_del_solista(nudo)


def _sigla_a(sigle, t: float):
    att = None
    for s in sigle:
        if s[0] <= t + 1e-6:
            att = s
        else:
            break
    return att


def confronta(sp: Spartito, accordi: List[Accordo], tonica: int) -> Dict[str, float]:
    """Accordi proposti contro le sigle vere di `sp`, movimento per movimento."""
    sigle = sorted(sp.sigle, key=lambda s: s[0])
    tot = fond = funz = 0
    cambi_v = cambi_p = 0
    prec_v = prec_p = None
    for m in sp.misure:
        t = m.inizio
        while t < m.fine - 1e-6:
            v = _sigla_a(sigle, t)
            p = next((a for a in accordi if a.inizio - 1e-6 <= t < a.fine - 1e-6), None)
            if v is not None and p is not None:
                tot += 1
                fond += v[1] == p.fondamentale
                fv = _FUNZIONE.get((v[1] - tonica) % 12, "-")
                fp = _FUNZIONE.get((p.fondamentale - tonica) % 12, "-")
                funz += fv == fp
                cambi_v += v[1] != prec_v
                cambi_p += p.fondamentale != prec_p
                prec_v, prec_p = v[1], p.fondamentale
            t += m.unita_movimento
    tot = tot or 1
    return {"fondamentali": fond / tot, "funzioni": funz / tot,
            "cambi_veri": cambi_v, "cambi_proposti": cambi_p, "movimenti": tot}


def _carica(cartella: str) -> List[Tuple[str, Spartito, Spartito, List[Nota]]]:
    brani = []
    for nome in sorted(os.listdir(cartella)):
        if not nome.lower().endswith((".xml", ".musicxml", ".mxl")):
            continue
        sp = ingestione.ingerisci(os.path.join(cartella, nome))
        if not sp.sigle:
            continue
        nudo, mel = solo_melodia(sp)
        brani.append((nome, sp, nudo, mel))
    return brani


def _misura(brani, pesi) -> Dict[str, Dict[str, float]]:
    fuori = {}
    for nome, sp, nudo, mel in brani:
        tonica, modo = armonizzazione.ultima_tonalita(nudo, mel)
        r = confronta(sp, armonizzazione.armonizza(nudo, mel, pesi), tonica)
        r["tonalita"] = f"{tonica} {modo}"
        fuori[nome] = r
    return fuori


def _pop(nome: str) -> bool:
    return not nome.startswith(CONTROLLI)


def stampa(risultati: Dict[str, Dict[str, float]]) -> None:
    for nome, r in risultati.items():
        print(f"{nome[:44]:44s} fond {r['fondamentali']:4.0%}  funz {r['funzioni']:4.0%}  "
              f"cambi {r['cambi_proposti']:3d}/{r['cambi_veri']:3d}  ({r['tonalita']})"
              + ("" if _pop(nome) else "  [controllo]"))
    pop = [r["fondamentali"] for n, r in risultati.items() if _pop(n)]
    if pop:
        print(f"media pop: fondamentali {sum(pop) / len(pop):.0%}")


GRIGLIA = {
    "cambio_battere": (-0.4, -0.1, 0.25),   # negativo = premio (Piston P4)
    "cambio_meta": (0.4, 0.9, 1.4),
    "estranea": (0.6, 1.0),
    "a_volte": (0.15, 0.4),
    "raro": (0.4, 0.9),
    "cadenza": (0.5, 1.5),
    "forte": (0.0, 0.3),
}


def _pesi(cambio_battere, cambio_meta, estranea, a_volte, raro, cadenza,
          forte) -> armonizzazione.Pesi:
    return armonizzazione.Pesi(cambio=(cambio_battere, cambio_meta, max(1.6, cambio_meta)),
                               estranea=estranea, a_volte=a_volte, raro=raro,
                               cadenza=cadenza, forte=forte)


def taratura(brani) -> None:
    """Griglia di pesi; per ogni brano pop il valore "uno escluso": i pesi
    migliori sugli ALTRI brani pop, misurati su questo."""
    combinazioni = list(itertools.product(*GRIGLIA.values()))
    pop = [b for b in brani if _pop(b[0])]
    tabella = []
    for i, valori in enumerate(combinazioni):
        r = _misura(pop, _pesi(*valori))
        tabella.append((valori, {n: x["fondamentali"] for n, x in r.items()}))
        print(f"\r{i + 1}/{len(combinazioni)}", end="", file=sys.stderr)
    print(file=sys.stderr)
    nomi = [b[0] for b in pop]
    escluso = []
    for nome in nomi:
        altri = [n for n in nomi if n != nome]
        migliore = max(tabella, key=lambda r: sum(r[1][n] for n in altri))
        escluso.append(migliore[1][nome])
        print(f"{nome[:44]:44s} uno escluso {migliore[1][nome]:4.0%}  pesi {migliore[0]}")
    print(f"media pop uno escluso: {sum(escluso) / len(escluso):.0%}")
    globale = max(tabella, key=lambda r: sum(r[1].values()))
    print(f"pesi migliori su tutti: {dict(zip(GRIGLIA, globale[0]))} "
          f"media {sum(globale[1].values()) / len(nomi):.0%}")


def arrangia(brani, cartella_uscita: str = os.path.join("output", "armonia")) -> None:
    from arranger import Configurazione, esegui
    cfg = Configurazione(formazione={"flauto": 2, "clarinetto": 1, "violino": 2,
                                     "violoncello": 1, "chitarra": 1, "pianoforte": 1},
                         livello="2a Media")
    for nome, _sp, nudo, _mel in brani:
        r = esegui(nome, cfg, cartella=cartella_uscita,
                   nome_base=os.path.splitext(nome)[0] + "_sola_melodia", spartito=nudo)
        print(r.percorso_xml)


def main(argv: List[str]) -> int:
    if not argv:
        print(__doc__)
        return 1
    brani = _carica(argv[0])
    if "--taratura" in argv:
        taratura(brani)
    elif "--arrangia" in argv:
        arrangia(brani)
    else:
        stampa(_misura(brani, armonizzazione.Pesi()))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
