"""
Interfaccia a riga di comando.

Esempi:
    python cli.py esempi/inno_alla_gioia.xml \
        --organico flauto=2,violino=2,violoncello=1,chitarra=1,pianoforte=1 \
        --livello "1a Media" --stile Normale -o output

    python cli.py "https://youtu.be/XXXX" --organico flauto=1,chitarra=1 --ia
"""

from __future__ import annotations

import argparse
import sys

from arranger import Configurazione, esegui
from arranger.strumenti import LIVELLI, REGISTRO


def organico(testo: str) -> dict:
    fuori = {}
    for pezzo in testo.split(","):
        if not pezzo.strip():
            continue
        chiave, _, quanti = pezzo.partition("=")
        chiave = chiave.strip().lower()
        if chiave not in REGISTRO:
            raise argparse.ArgumentTypeError(
                f"strumento sconosciuto: {chiave} (disponibili: {', '.join(REGISTRO)})")
        fuori[chiave] = int(quanti or 1)
    return fuori


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Arranger SMIM")
    ap.add_argument("sorgente",
                    help="spartito pianistico: MusicXML, MIDI o PDF (con OMR)")
    ap.add_argument("--organico", type=organico, required=True,
                    help="es. flauto=2,violino=2,violoncello=1,chitarra=1")
    ap.add_argument("--livello", choices=list(LIVELLI), default="1a Media")
    ap.add_argument("--stile", default="Normale",
                    choices=["Normale", "Cinematico", "Jazz", "Automatico"])
    ap.add_argument("--trasporto", type=int, default=0)
    ap.add_argument("--no-staffetta", action="store_true")
    ap.add_argument("--confronto", action="store_true",
                    help="accoda lo spartito originale in fondo alla partitura")
    ap.add_argument("--ia", action="store_true", help="usa l'API Anthropic")
    ap.add_argument("--lilypond", action="store_true",
                    help="genera anche il sorgente .ly")
    ap.add_argument("--pdf", action="store_true",
                    help="incide il PDF con LilyPond (richiede l'eseguibile nel PATH)")
    ap.add_argument("-o", "--output", default="output")
    a = ap.parse_args(argv)

    cfg = Configurazione(formazione=a.organico, livello=a.livello, stile=a.stile,
                         trasporto=a.trasporto, staffetta_melodia=not a.no_staffetta,
                         debug_originale=a.confronto, usa_ia=a.ia)
    r = esegui(a.sorgente, cfg, cartella=a.output,
               esporta_ly=a.lilypond or a.pdf, incidi_pdf=a.pdf)

    print(f"Brano: {r.master.titolo}")
    print(f"Anacrusi: {r.master.anacrusi:g} quarti" if r.master.anacrusi
          else "Anacrusi: assente")
    print(f"Melodia: {len(r.analisi.melodia)} note | "
          f"Armonia: {len(r.analisi.armonia)} accordi")
    print(f"Parti: {', '.join(p.nome for p in r.partitura.parti)}")
    print(f"MusicXML: {r.percorso_xml}")
    if r.percorso_midi:
        print(f"MIDI:     {r.percorso_midi}")
    if r.percorso_ly:
        print(f"LilyPond: {r.percorso_ly}")
    if r.percorso_pdf:
        print(f"PDF:      {r.percorso_pdf}")
    if r.report:
        print(f"\nInterventi del validatore ({len(r.report)}):")
        for riga in r.report:
            print("  -", riga)
    if r.relazione:
        print("\nRelazione didattica (IA):\n" + r.relazione)
    return 0


if __name__ == "__main__":
    sys.exit(main())
