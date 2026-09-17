"""
Confronto nota per nota fra una nostra trascrizione e una partitura vera.

    python strumenti_confronto.py nostro.musicxml partitura.musicxml
    python strumenti_confronto.py nostro.musicxml partitura.musicxml \\
        --nostra Voce --loro Voice

PERCHE' ESISTE. Per molte versioni le scelte si sono misurate confrontando
la DISTRIBUZIONE DELLE DURATE con quella di uno spartito. E' un indicatore
troppo debole, e ha fatto danni concreti: premia le note lunghe, e le note
lunghe si ottengono anche fondendo note vere. E' cosi' che era passato un
buco d'unione di una croma sul basso, che fondeva i due Mi ribattuti del
riff — il risultato somigliava di piu' allo spartito nelle statistiche ed
era piu' sbagliato nella sostanza.

Qui si confronta invece nota per nota: per ogni nota del riferimento si
cerca, nella nostra trascrizione, una nota della stessa altezza abbastanza
vicina nel tempo. Ne escono due numeri che non si possono imbrogliare
allungando le durate:

  PRECISIONE — quante delle NOSTRE note trovano riscontro. Bassa: stiamo
  scrivendo roba che nell'originale non c'e'.

  RICHIAMO — quante note del RIFERIMENTO abbiamo trovato. Basso: ci stiamo
  perdendo pezzi di musica.

Le due si muovono spesso in direzioni opposte, ed e' proprio quello che le
rende utili insieme: una regola che alza l'una abbassando l'altra non sta
migliorando niente, sta solo spostando il problema.

L'allineamento temporale viene cercato automaticamente (le due partiture
partono quasi sempre da punti diversi), e l'ottava e' ignorata per
impostazione predefinita: un errore d'ottava e' un problema diverso da una
nota sbagliata, e mescolarli nasconde entrambi.
"""

from __future__ import annotations

import argparse
import os
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from typing import Dict, List, Optional, Tuple

PASSI = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
NOMI = ["Do", "Do#", "Re", "Re#", "Mi", "Fa", "Fa#", "Sol", "Sol#", "La",
        "La#", "Si"]

Evento = Tuple[float, int, float]     # (inizio in quarti, midi, durata)


def leggi_parte(percorso: str, filtro: Optional[str]) -> List[Evento]:
    """
    Legge le note di una parte da un MusicXML, in quarti dall'inizio.

    `filtro` e' un pezzo del nome della parte (senza distinzione di
    maiuscole): «Voce» prende sia «Voce» sia «Voce (traccia separata)».
    Senza filtro si prende tutto.

    Gli accordi vengono letti tutti, ma l'elemento <chord> non fa avanzare
    la posizione: e' il modo in cui MusicXML rappresenta le note simultanee,
    e ignorarlo sposterebbe in avanti tutto il resto della misura.
    """
    radice = ET.parse(percorso).getroot()
    div_el = radice.find(".//attributes/divisions")
    divisioni = int(div_el.text) if div_el is not None else 1

    nomi_parti: Dict[str, str] = {}
    for sp in radice.findall(".//part-list/score-part"):
        nome = sp.find("part-name")
        nomi_parti[sp.get("id") or ""] = (nome.text or "") if nome is not None else ""

    eventi: List[Evento] = []
    for parte in radice.findall(".//part"):
        etichetta = nomi_parti.get(parte.get("id") or "", "")
        if filtro and filtro.lower() not in etichetta.lower():
            continue
        inizio_misura = 0.0
        durata_precedente = 0.0
        for misura in parte.findall("measure"):
            posizione = 0.0
            for nota in misura.findall("note"):
                el = nota.find("duration")
                durata = int(el.text) / divisioni if el is not None else 0.0
                if nota.find("chord") is not None:
                    posizione -= durata_precedente
                altezza = nota.find("pitch")
                if altezza is not None:
                    passo = altezza.find("step").text
                    ottava = int(altezza.find("octave").text)
                    alt = altezza.find("alter")
                    scarto = int(alt.text) if alt is not None else 0
                    midi = PASSI[passo] + scarto + (ottava + 1) * 12
                    eventi.append((inizio_misura + posizione, midi, durata))
                posizione += durata
                durata_precedente = durata
            inizio_misura += 4.0
    return sorted(eventi)


def confronta(nostre: List[Evento], loro: List[Evento],
              tolleranza: float = 0.25,
              ignora_ottava: bool = True
              ) -> Tuple[float, float, float, int]:
    """
    Cerca l'allineamento temporale migliore e conta le corrispondenze.

    Ogni nota del riferimento puo' essere usata una volta sola: senza questo
    vincolo, una raffica di note nostre nello stesso punto verrebbe contata
    tutta come giusta contro un'unica nota vera, e la precisione
    racconterebbe una favola.

    Ritorna (precisione, richiamo, scarto_temporale, corrispondenze).
    """
    if not nostre or not loro:
        return 0.0, 0.0, 0.0, 0

    def conta(scarto: float) -> int:
        usate = set()
        trovate = 0
        for inizio, midi, _d in nostre:
            for j, (r_inizio, r_midi, _rd) in enumerate(loro):
                if j in usate:
                    continue
                if r_inizio > (inizio - scarto) + tolleranza:
                    break
                uguali = ((midi - r_midi) % 12 == 0 if ignora_ottava
                          else midi == r_midi)
                if uguali and abs((inizio - scarto) - r_inizio) <= tolleranza:
                    usate.add(j)
                    trovate += 1
                    break
        return trovate

    migliore, scarto_migliore = -1, 0.0
    passo = 0.25
    for k in range(-80, 81):
        scarto = k * passo
        t = conta(scarto)
        if t > migliore:
            migliore, scarto_migliore = t, scarto

    return (migliore / len(nostre), migliore / len(loro),
            scarto_migliore, migliore)


def profilo(eventi: List[Evento], etichetta: str) -> None:
    if not eventi:
        print(f"  {etichetta}: nessuna nota")
        return
    altezze = [m for _t, m, _d in eventi]
    classi = Counter(m % 12 for m in altezze)
    durate = Counter(round(d, 2) for _t, _m, d in eventi)
    posizioni = Counter(round((t % 4) * 4) / 4 for t, _m, _d in eventi)
    print(f"  {etichetta}: {len(eventi)} note, ambito "
          f"{NOMI[min(altezze) % 12]}{min(altezze) // 12 - 1}-"
          f"{NOMI[max(altezze) % 12]}{max(altezze) // 12 - 1}")
    print("     altezze:  " + "  ".join(
        f"{NOMI[k]} {100 * c / len(eventi):.0f}%"
        for k, c in classi.most_common(5)))
    print("     durate:   " + "  ".join(
        f"{k} {100 * c / len(eventi):.0f}%" for k, c in durate.most_common(5)))
    print("     attacchi: " + "  ".join(
        f"{k} {100 * c / len(eventi):.0f}%"
        for k, c in sorted(posizioni.items())[:8]))


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(
        description="Confronta nota per nota una trascrizione con una "
                    "partitura di riferimento.")
    p.add_argument("nostro", help="MusicXML prodotto da noi")
    p.add_argument("riferimento", help="MusicXML della partitura vera")
    p.add_argument("--nostra", default=None,
                   help="nome (anche parziale) della nostra parte, es. Voce")
    p.add_argument("--loro", default=None,
                   help="nome (anche parziale) della parte di riferimento, "
                        "es. Voice")
    p.add_argument("--tolleranza", type=float, default=0.25,
                   help="scarto massimo in quarti perche' due note siano "
                        "considerate la stessa (predefinito 0.25, una "
                        "semicroma)")
    p.add_argument("--ottava-esatta", action="store_true",
                   dest="ottava_esatta",
                   help="pretendi anche l'ottava giusta, non solo l'altezza")
    a = p.parse_args(argv)

    for percorso in (a.nostro, a.riferimento):
        if not os.path.exists(percorso):
            print(f"file non trovato: {percorso}")
            return 1

    nostre = leggi_parte(a.nostro, a.nostra)
    loro = leggi_parte(a.riferimento, a.loro)
    if not nostre or not loro:
        print("una delle due parti e' vuota: controlla i nomi passati a "
              "--nostra e --loro.")
        return 1

    print("\nProfilo delle due parti")
    profilo(nostre, "nostra    ")
    profilo(loro, "riferimento")

    prec, rich, scarto, trovate = confronta(
        nostre, loro, a.tolleranza, ignora_ottava=not a.ottava_esatta)
    print(f"\nAllineamento trovato: {scarto:+.2f} quarti")
    print(f"Corrispondenze: {trovate}")
    print(f"  PRECISIONE {100 * prec:5.1f}%  "
          f"(quante delle nostre note trovano riscontro)")
    print(f"  RICHIAMO   {100 * rich:5.1f}%  "
          f"(quante note del riferimento abbiamo trovato)")

    if prec < rich - 0.1:
        print("\n  La precisione e' piu' bassa del richiamo: stiamo "
              "scrivendo note che nell'originale non ci sono. Guardare le "
              "regole che AGGIUNGONO o dividono note.")
    elif rich < prec - 0.1:
        print("\n  Il richiamo e' piu' basso della precisione: ci stiamo "
              "perdendo musica. Guardare le regole che UNISCONO o scartano "
              "note.")

    print("\n  Nota: tolleranza allargata per capire se il problema e' di "
          "collocazione o di altezza —")
    for tol in (0.125, 0.25, 0.5, 1.0, 2.0):
        _p, r, _s, _t = confronta(nostre, loro, tol,
                                  ignora_ottava=not a.ottava_esatta)
        print(f"    tolleranza {tol:5.3f} quarti -> richiamo {100 * r:5.1f}%")
    print("  Se il richiamo non sale allargando la tolleranza, le note "
          "mancanti non sono spostate: sono sbagliate d'altezza o assenti.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
