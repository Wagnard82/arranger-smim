"""
Interfaccia a riga di comando.

Esempi:
    python cli.py esempi/inno_alla_gioia.xml \
        --organico flauto=2,violino=2,violoncello=1,chitarra=1,pianoforte=1 \
        --livello "1a Media" --stile Normale -o output

    # versione inglese: livelli come Grade 1/2/3, parti e report in inglese
    python cli.py esempi/lead_sheet.xml --organico flauto=1,violino=2 \
        --livello "Grade 2" --livello-strumento violino2=1 --lingua en

    python cli.py "https://youtu.be/XXXX" --organico flauto=1,chitarra=1 --ia
"""

from __future__ import annotations

import argparse
import sys

from arranger import Configurazione, esegui
from arranger.lingua import LINGUE, normalizza_livello
from arranger.strumenti import LIVELLI, REGISTRO


def livello_cli(testo: str) -> str:
    """Accetta "1a Media", "Grade 1", "1"... e restituisce la chiave interna."""
    chiave = normalizza_livello(testo)
    if chiave not in LIVELLI:
        raise argparse.ArgumentTypeError(
            f"livello non riconosciuto: {testo}. Ammessi: "
            f"{', '.join(LIVELLI)} oppure Grade 1, Grade 2, Grade 3")
    return chiave


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
                    help="spartito in MusicXML (.xml, .musicxml, .mxl): "
                         "riduzione per pianoforte, parte solista con "
                         "pianoforte, oppure lead sheet (melodia con le "
                         "sigle degli accordi)")
    ap.add_argument("--organico", type=organico, required=True,
                    help="es. flauto=2,violino=2,violoncello=1,chitarra=1")
    ap.add_argument("--livello", type=livello_cli, default="1a Media",
                    help="1a Media / 2a Media / 3a Media, oppure "
                         "Grade 1 / Grade 2 / Grade 3, oppure 1 / 2 / 3")
    ap.add_argument("--lingua", choices=list(LINGUE), default="it",
                    help="lingua di report, nomi delle parti e didascalie "
                         "(it, en); la musica non cambia")
    ap.add_argument("--livello-strumento", action="append", default=[],
                    metavar="CHIAVE=LIVELLO", dest="livello_strumento",
                    help="livello di un singolo strumento o leggio, "
                         "ripetibile: --livello-strumento violino=\"3a Media\" "
                         "--livello-strumento flauto2=\"1a Media\". La chiave "
                         "puo' essere lo strumento (vale per tutti i suoi "
                         "leggii) oppure l'id della parte come violino2 "
                         "(vale solo per quel leggio). Serve alle classi "
                         "eterogenee: senza, si e' costretti a scegliere fra "
                         "annoiare chi suona da tre anni e travolgere chi ha "
                         "cominciato a ottobre.")
    ap.add_argument("--stile", default="Normale",
                    choices=["Normale", "Cinematico", "Jazz", "Automatico"])
    ap.add_argument("--trasporto", type=int, default=0)
    ap.add_argument("--no-staffetta", action="store_true")
    ap.add_argument("--frasi-music21", action="store_true",
                    help="rilevatore di frasi avanzato (richiede music21)")
    ap.add_argument("--pausa-massima", type=int, default=2,
                    help="misure di pausa oltre le quali uno strumento viene "
                         "messo ad accompagnare (0 = lascia i silenzi)")
    ap.add_argument("--modo", default="auto",
                    choices=["auto", "melodico", "tessitura"],
                    help="melodico = melodia + accompagnamento; "
                         "tessitura = orchestra i registri dell'originale")
    ap.add_argument("--cambio", default="auto",
                    choices=["auto", "frase", "periodo", "sezione"],
                    help="dove avviene lo scambio fra i solisti")
    ap.add_argument("--misure-minime-solista", type=int, default=8,
                    help="misure minime prima di passare la melodia")
    ap.add_argument("--confronto", action="store_true",
                    help="accoda lo spartito originale in fondo alla partitura")
    ap.add_argument("--ia", action="store_true", help="attiva lo strato IA")
    ap.add_argument("--ia-funzioni", default="melodia,stile",
                    help=("funzioni IA da attivare, separate da virgola: "
                          "melodia, riferimenti, stile, orchestrazione, "
                          "armonia, relazione (default: melodia,stile)"))
    ap.add_argument("--modello-ia", default="claude-sonnet-4-6")
    ap.add_argument("--lilypond", action="store_true",
                    help="genera anche il sorgente .ly")
    ap.add_argument("--pdf", action="store_true",
                    help="incide il PDF con LilyPond (richiede l'eseguibile nel PATH)")
    ap.add_argument("-o", "--output", default="output")
    a = ap.parse_args(argv)

    livelli_strumenti = {}
    for voce in a.livello_strumento:
        if "=" not in voce:
            ap.error(f"--livello-strumento vuole CHIAVE=LIVELLO, ricevuto: {voce}")
        chiave, _, valore = voce.partition("=")
        chiave, valore = chiave.strip(), valore.strip()
        try:
            livelli_strumenti[chiave] = livello_cli(valore)
        except argparse.ArgumentTypeError as e:
            ap.error(str(e))

    cfg = Configurazione(formazione=a.organico, livello=a.livello, stile=a.stile,
                         livelli_strumenti=livelli_strumenti,
                         trasporto=a.trasporto, staffetta_melodia=not a.no_staffetta,
                         modo=a.modo, cambio_solista=a.cambio,
                         frasi_music21=a.frasi_music21,
                         riempi_silenzi=a.pausa_massima > 0,
                         silenzio_massimo_misure=max(1, a.pausa_massima),
                         misure_minime_solista=a.misure_minime_solista,
                         debug_originale=a.confronto, usa_ia=a.ia,
                         modello_ia=a.modello_ia, lingua=a.lingua)
    scelte = {x.strip() for x in a.ia_funzioni.split(",") if x.strip()}
    for funzione in ("melodia", "riferimenti", "stile", "orchestrazione",
                     "armonia", "relazione"):
        setattr(cfg, f"ia_{funzione}", funzione in scelte)
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
