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
from arranger.pipeline import esegui_da_audio_multitraccia
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
                    help="spartito pianistico (MusicXML, MIDI o PDF con OMR), "
                         "oppure una registrazione audio con --audio")
    ap.add_argument("--audio", action="store_true",
                    help=("tratta 'sorgente' come registrazione audio: separa "
                          "voce/basso/batteria/resto (richiede demucs e "
                          "basic-pitch) invece di leggere uno spartito"))
    ap.add_argument("--no-tracce-debug", action="store_true",
                    help=("con --audio, non esportare il MusicXML di debug "
                          "con le tracce separate"))
    ap.add_argument("--bpm", type=float, default=None,
                    help=("con --audio, forza il tempo del brano invece di "
                          "rilevarlo in automatico: nessun rilevatore e' "
                          "infallibile, e se conosci il tempo reale "
                          "indicarlo qui e' sempre la scelta piu' sicura"))
    ap.add_argument("--organico", type=organico, required=True,
                    help="es. flauto=2,violino=2,violoncello=1,chitarra=1")
    ap.add_argument("--livello", choices=list(LIVELLI), default="1a Media")
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

    cfg = Configurazione(formazione=a.organico, livello=a.livello, stile=a.stile,
                         trasporto=a.trasporto, staffetta_melodia=not a.no_staffetta,
                         modo=a.modo, cambio_solista=a.cambio,
                         frasi_music21=a.frasi_music21,
                         riempi_silenzi=a.pausa_massima > 0,
                         silenzio_massimo_misure=max(1, a.pausa_massima),
                         misure_minime_solista=a.misure_minime_solista,
                         debug_originale=a.confronto, usa_ia=a.ia,
                         modello_ia=a.modello_ia)
    scelte = {x.strip() for x in a.ia_funzioni.split(",") if x.strip()}
    for funzione in ("melodia", "riferimenti", "stile", "orchestrazione",
                     "armonia", "relazione"):
        setattr(cfg, f"ia_{funzione}", funzione in scelte)
    if a.audio:
        r = esegui_da_audio_multitraccia(
            a.sorgente, cfg, cartella=a.output, esporta_ly=a.lilypond or a.pdf,
            esporta_tracce_debug=not a.no_tracce_debug, bpm_manuale=a.bpm)
    else:
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
    if r.percorso_tracce_debug:
        print(f"Tracce separate, quantizzate (debug): {r.percorso_tracce_debug}")
    if r.percorso_tracce_grezze:
        print(f"Tracce separate, NON quantizzate (debug): "
              f"{r.percorso_tracce_grezze}")
    if r.report:
        print(f"\nInterventi del validatore ({len(r.report)}):")
        for riga in r.report:
            print("  -", riga)
    if r.relazione:
        print("\nRelazione didattica (IA):\n" + r.relazione)
    return 0


if __name__ == "__main__":
    sys.exit(main())
