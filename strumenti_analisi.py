"""
Banco di prova del rilevatore di melodia.

    python strumenti_analisi.py cartella_con_spartiti/

Per ogni file stampa quanto della durata e' coperto dalla melodia, quanta parte
sta alla mano sinistra, quanti salti oltre l'ottava e l'ambito usato. Serve a
vedere in fretta se una modifica al rilevatore migliora o peggiora le cose su
un repertorio vero, invece che su un solo brano.

Cosa guardare:
  * copertura vicina al 100% su un brano con introduzioni o interludi e'
    sospetta: vuol dire che la melodia non tace mai;
  * una percentuale alta di note alla mano sinistra va verificata a orecchio:
    puo' essere giusta (melodia al basso) o essere un errore;
  * molti salti oltre l'ottava indicano una linea che salta fra i registri.
"""

from __future__ import annotations

import os
import sys

from arranger import analizzatore, ingestione


def analizza_cartella(cartella: str) -> int:
    estensioni = (".xml", ".musicxml", ".mxl", ".mid", ".midi")
    files = sorted(f for f in os.listdir(cartella) if f.lower().endswith(estensioni))
    if not files:
        print(f"Nessuno spartito in {cartella}")
        return 1

    print(f"{'brano':40} {'mis':>4} {'note':>5} {'mel':>5} {'cop%':>5} "
          f"{'sx%':>4} {'salti':>5} {'ambito':>8} {'frasi':>5} {'forma':>8}")
    for nome in files:
        percorso = os.path.join(cartella, nome)
        try:
            sp = ingestione.ingerisci(percorso)
            an = analizzatore.analizza(sp)
        except Exception as e:
            print(f"{nome[:40]:40} errore: {e}")
            continue
        if not an.melodia:
            print(f"{nome[:40]:40} {len(sp.misure):4} {len(sp.note):5} "
                  f"{'0':>5}  nessuna melodia riconosciuta")
            continue
        mel = an.melodia
        copertura = sum(n.durata for n in mel) / (sp.durata_totale or 1) * 100
        sinistra = sum(1 for n in mel if n.rigo == 2) / len(mel) * 100
        salti = [abs(b.midi - a.midi) for a, b in zip(mel, mel[1:])]
        oltre = sum(1 for s in salti if s > 12)
        print(f"{nome[:40]:40} {len(sp.misure):4} {len(sp.note):5} {len(mel):5} "
              f"{copertura:5.0f} {sinistra:4.0f} {oltre:5} "
              f"{min(n.midi for n in mel):3}-{max(n.midi for n in mel):3} "
              f"{len(an.frasi):5} {an.forma:>8}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    sys.exit(analizza_cartella(sys.argv[1]))
