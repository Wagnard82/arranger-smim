"""
Banco di prova dell'estrazione del basso.

    python strumenti_basso.py brano.mp3
    python strumenti_basso.py brano.mp3 --fmin 41 --fmax 200 --collassa
    python strumenti_basso.py brano.mp3 --confronta

Separa la traccia di basso UNA volta sola, la tiene da parte, e poi permette
di rifare il solo rilevamento d'altezza con parametri diversi: la separazione
con Demucs e' il passaggio lento (minuti), il rilevamento e' veloce (secondi).
Rigenerare tutto l'arrangiamento per vedere l'effetto di una soglia e' tempo
buttato.

COSA GUARDA, e perche'. Su un basso la diagnosi non e' "quante note" ma:

  * DISPERSIONE FRA OTTAVE. Un basso vero sta in un'ottava e mezza scarsa. Se
    le note si dividono fra tre ottave, quasi sempre non e' la linea che salta:
    e' il rilevatore che sbaglia ottava. Il sintomo tipico e' una distribuzione
    a due o tre gobbe con la gobba centrale piu' piccola delle laterali.

  * CLASSI D'ALTEZZA. Se le note piu' frequenti sono i gradi del giro armonico
    del brano, il rilevatore sta riconoscendo le altezze GIUSTE: il problema e'
    solo l'ottava, che e' un errore molto piu' facile da correggere.

  * FRAMMENTAZIONE. Tante note brevissime su un basso sono sospette. Spesso non
    sono note vere ma una nota sola spezzata in quattro dai salti d'ottava.

  * NOTE FUORI SCALA. Una percentuale alta segnala rumore, non musica.

Nessuno di questi numeri e' un verdetto da solo: servono a decidere in fretta
se una modifica migliora o peggiora, invece di riascoltare tutto ogni volta.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import Counter
from typing import Dict, List, Optional, Tuple

from arranger.modello import Nota

NOMI = ["Do", "Do#", "Re", "Re#", "Mi", "Fa", "Fa#", "Sol", "Sol#", "La",
        "La#", "Si"]


def nome_nota(midi: int) -> str:
    return f"{NOMI[midi % 12]}{midi // 12 - 1}"


# --------------------------------------------------------------------------
# Separazione (lenta) con riuso
# --------------------------------------------------------------------------

def ottieni_traccia_basso(percorso_audio: str, cartella: str,
                          riusa: bool = True) -> Optional[str]:
    """
    Restituisce il percorso del wav di solo basso, separandolo con Demucs solo
    se non e' gia' stato fatto.

    Il riuso non e' un dettaglio di comodita': la separazione dura minuti, il
    rilevamento d'altezza secondi. Senza riuso ogni prova costerebbe come una
    generazione completa, e si finirebbe per fare meno prove.
    """
    from arranger.audio_multitraccia import separa_tracce

    atteso = os.path.join(cartella, "bass.wav")
    if riusa and os.path.exists(atteso):
        print(f"  traccia di basso gia' presente, la riuso: {atteso}")
        return atteso

    print("  separazione con Demucs in corso (puo' richiedere qualche "
          "minuto)...")
    try:
        percorsi = separa_tracce(percorso_audio, cartella)
    except Exception as e:
        print(f"  separazione fallita: {e}")
        return None
    if "bass" not in percorsi:
        print("  Demucs non ha prodotto una traccia di basso.")
        return None
    return percorsi["bass"]


# --------------------------------------------------------------------------
# Diagnosi
# --------------------------------------------------------------------------

def distribuzione_ottave(note: List[Nota]) -> Dict[int, int]:
    return Counter(n.midi // 12 - 1 for n in note)


def ottava_dominante(note: List[Nota]) -> Optional[int]:
    if not note:
        return None
    return distribuzione_ottave(note).most_common(1)[0][0]


def collassa_ottave(note: List[Nota], ampiezza: int = 7) -> List[Nota]:
    """
    Riporta dentro un'unica fascia di registro le note finite un'ottava sopra
    o sotto.

    Il ragionamento: su un basso, un salto d'ottava e' quasi sempre un errore
    del rilevatore, non una scelta musicale. Si prende come riferimento la
    MEDIANA delle altezze — piu' robusta della media, che verrebbe trascinata
    dagli errori stessi — e si trasporta di ottave ogni nota che se ne
    allontana piu' di `ampiezza` semitoni, finche' non rientra.

    Non e' una correzione gratuita: se una linea di basso salta davvero
    d'ottava (e capita, nel funk e nel pop), questa funzione la appiattisce.
    Per questo e' un'opzione, non il comportamento predefinito, e il banco di
    prova mostra sempre il PRIMA e il DOPO.
    """
    if not note:
        return []
    altezze = sorted(n.midi for n in note)
    centro = altezze[len(altezze) // 2]
    fuori = []
    for n in note:
        midi = n.midi
        while midi - centro > ampiezza:
            midi -= 12
        while centro - midi > ampiezza:
            midi += 12
        if midi != n.midi:
            fuori.append(n.midi)
        n.midi = midi
    return note


def note_fuori_scala(note: List[Nota], tonica: int, minore: bool = True
                     ) -> int:
    scala = ({0, 2, 3, 5, 7, 8, 10} if minore else {0, 2, 4, 5, 7, 9, 11})
    return sum(1 for n in note if (n.midi - tonica) % 12 not in scala)


def stampa_diagnosi(note: List[Nota], titolo: str,
                    tonica: Optional[int] = None) -> None:
    print(f"\n  --- {titolo} ---")
    if not note:
        print("  nessuna nota: il rilevamento non ha prodotto niente.")
        return

    altezze = [n.midi for n in note]
    durate = [n.durata for n in note]
    ordinate = sorted(altezze)
    mediana = ordinate[len(ordinate) // 2]

    print(f"  note: {len(note)}   ambito: {nome_nota(min(altezze))}-"
          f"{nome_nota(max(altezze))} ({max(altezze) - min(altezze)} semitoni)"
          f"   mediana: {nome_nota(mediana)}")

    dist = distribuzione_ottave(note)
    parti = [f"ott.{o}: {c} ({100 * c / len(note):.0f}%)"
             for o, c in sorted(dist.items())]
    print("  ottave -> " + "   ".join(parti))
    if len(dist) >= 3:
        ordinati = [c for _o, c in sorted(dist.items())]
        centrale = ordinati[len(ordinati) // 2]
        if centrale < max(ordinati) / 2:
            print("  ATTENZIONE: la distribuzione ha le gobbe ai lati e il "
                  "centro scarno. E' il disegno tipico degli errori d'ottava, "
                  "non di una linea che salta davvero.")

    classi = Counter(m % 12 for m in altezze)
    print("  classi d'altezza: " + "  ".join(
        f"{NOMI[pc]} {100 * c / len(note):.0f}%"
        for pc, c in classi.most_common(5)))

    brevi = sum(1 for d in durate if d <= 0.25)
    print(f"  note di durata <= 1/16: {brevi} ({100 * brevi / len(note):.0f}%)")

    salti = [abs(altezze[i + 1] - altezze[i]) for i in range(len(altezze) - 1)]
    if salti:
        ottave = sum(1 for s in salti if s in (12, 24))
        print(f"  salti di ottava esatta: {ottave} "
              f"({100 * ottave / len(salti):.0f}% degli intervalli)")

    if tonica is not None:
        fuori = note_fuori_scala(note, tonica)
        print(f"  note fuori dalla scala di {NOMI[tonica]} minore: {fuori} "
              f"({100 * fuori / len(note):.0f}%)")


# --------------------------------------------------------------------------
# Programma
# --------------------------------------------------------------------------

def prova(percorso_audio: str, fmin: float, fmax: float,
          durata_minima: float, tolleranza: float, conferma: int,
          collassa: bool, ampiezza: int, tonica: Optional[int],
          cartella: str, riusa: bool, sicurezza_minima: float = 0.0,
          restringi: bool = True) -> int:
    from arranger.audio_multitraccia import _note_da_f0

    print(f"Brano: {os.path.basename(percorso_audio)}")
    wav = ottieni_traccia_basso(percorso_audio, cartella, riusa)
    if not wav:
        return 1

    try:
        import librosa
        import numpy as np
    except ImportError:
        print("  `librosa` non installato: senza non si puo' fare questa "
              "prova.")
        return 1

    import math
    m_min = int(round(69 + 12 * math.log2(fmin / 440.0)))
    m_max = int(round(69 + 12 * math.log2(fmax / 440.0)))
    print(f"  registro cercato: {fmin:g}-{fmax:g} Hz "
          f"({nome_nota(m_min)}-{nome_nota(m_max)})")

    y, sr = librosa.load(wav, sr=None, mono=True)
    finestra = 2048
    while finestra < 2.5 * sr / fmin:
        finestra *= 2
    print(f"  finestra d'analisi: {finestra} campioni a {sr} Hz "
          f"(misura fino a {sr / finestra:.1f} Hz), passo 512 "
          f"({512000.0 / sr:.1f} ms)")
    f0, _sonoro, sicurezza = librosa.pyin(y, fmin=fmin, fmax=fmax, sr=sr,
                                          frame_length=finestra,
                                          hop_length=512)
    # Le stesse due cautele della pipeline, con gli stessi valori: un banco
    # di prova che si comporta diversamente da cio' che vuole misurare non
    # serve a niente, anzi inganna.
    valori = np.asarray(f0, dtype=float)
    certezza = (np.asarray(sicurezza, dtype=float)
                if sicurezza is not None else None)
    semitoni = []
    for i, v in enumerate(valori):
        certo = certezza is None or certezza[i] >= sicurezza_minima
        semitoni.append(float(69.0 + 12.0 * np.log2(v / 440.0))
                        if (v == v and v > 0 and certo) else float("nan"))
    prima = sum(1 for v in semitoni if v == v)
    from arranger.audio_multitraccia import _colma_vuoti_brevi
    semitoni = _colma_vuoti_brevi(semitoni)
    print(f"  fotogrammi ricuciti: {sum(1 for v in semitoni if v == v) - prima}")
    prima = sum(1 for v in semitoni if v == v)
    if restringi:
        from arranger.audio_multitraccia import _restringi_al_registro_reale
        semitoni = _restringi_al_registro_reale(semitoni)
        dopo = sum(1 for v in semitoni if v == v)
        print(f"  scartati fuori registro reale: {prima - dopo} "
              f"({100 * (prima - dopo) / max(1, prima):.0f}%)")
    intonati = sum(1 for s in semitoni if s == s)
    print(f"  fotogrammi intonati: {intonati}/{len(semitoni)} "
          f"({100 * intonati / max(1, len(semitoni)):.0f}%)")

    note = _note_da_f0(semitoni, 512.0 / sr, durata_minima=durata_minima,
                       tolleranza=tolleranza, conferma=conferma)
    stampa_diagnosi(note, "cosi' com'e'", tonica)

    if collassa:
        import copy
        collassate = collassa_ottave(copy.deepcopy(note), ampiezza)
        stampa_diagnosi(collassate, f"dopo il collasso d'ottava "
                                    f"(±{ampiezza} semitoni)", tonica)
        note = collassate

    uscita = os.path.join(cartella, "basso_prova.musicxml")
    try:
        from arranger.audio_multitraccia import _parte_da_note
        from arranger.esportatore import esporta_musicxml
        from arranger.modello import Misura, Partitura

        fine = max((n.fine for n in note), default=4.0)
        n_misure = max(1, int(fine / 4.0 + 0.999))
        misure = [Misura(numero=i + 1, inizio=i * 4.0, durata=4.0)
                  for i in range(n_misure)]
        parte = _parte_da_note("basso", "Basso (prova)", "Basso", note,
                               n_misure * 4.0, chiave="F")
        part = Partitura(
            titolo="Prova estrazione basso",
            sottotitolo=(f"fmin={fmin:g} Hz  fmax={fmax:g} Hz  "
                         f"durata minima={durata_minima:g} s  "
                         f"tolleranza={tolleranza:g} st  "
                         f"conferma={conferma}"
                         + ("  collasso d'ottava attivo" if collassa else "")),
            parti=[parte], misure=misure, bpm=120.0)
        esporta_musicxml(part, uscita)
        print(f"\n  scritto: {uscita}")
        print("  (i tempi sono in secondi trattati come quarti a 120 bpm: "
              "serve a leggere le altezze, non a leggere il ritmo)")
    except Exception as e:
        print(f"\n  esportazione non riuscita ({e}); la diagnosi sopra resta "
              "valida.")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(
        description="Banco di prova per l'estrazione del basso.")
    p.add_argument("audio", help="file audio del brano")
    p.add_argument("--fmin", type=float, default=30.87,
                   help="frequenza minima in Hz (predefinita: 30.87, il Si0 "
                        "del basso a cinque corde)")
    p.add_argument("--fmax", type=float, default=261.6,
                   help="frequenza massima in Hz (predefinita: 261.6, Do4)")
    p.add_argument("--durata-minima", type=float, default=0.08,
                   dest="durata_minima",
                   help="sotto questa durata in secondi non e' una nota")
    p.add_argument("--tolleranza", type=float, default=0.6,
                   help="semitoni di scarto tollerati dentro una nota")
    p.add_argument("--conferma", type=int, default=3,
                   help="fotogrammi consecutivi fuori tolleranza necessari a "
                        "chiudere una nota")
    p.add_argument("--collassa", action="store_true",
                   help="riporta le note fuggite d'ottava dentro un'unica "
                        "fascia di registro")
    p.add_argument("--ampiezza", type=int, default=7,
                   help="semitoni di distanza dalla mediana oltre i quali il "
                        "collasso interviene (predefinito 7: una fascia di "
                        "poco piu' di un'ottava, misurata come il miglior "
                        "compromesso fra errori corretti e note vere "
                        "schiacciate)")
    p.add_argument("--tonica", default=None,
                   help="tonica del brano per il conteggio delle note fuori "
                        "scala, es. Do# oppure La")
    p.add_argument("--sicurezza", type=float, default=0.0,
                   help="soglia sulla probabilita' del singolo fotogramma "
                        "(0-1). Predefinito 0, cioe' disattivata: il NaN di "
                        "pyin e' gia' il suo giudizio, preso guardando il "
                        "contesto, e sovrapporgli una soglia lo disfa")
    p.add_argument("--niente-restringi", action="store_true",
                   dest="niente_restringi",
                   help="non scartare il materiale fuori dal registro che la "
                        "traccia usa davvero (serve a vedere quanto ne "
                        "verrebbe tolto)")
    p.add_argument("--cartella", default="tmp_basso",
                   help="dove tenere la traccia separata e l'uscita")
    p.add_argument("--riseparara", action="store_true",
                   help="rifa' la separazione anche se e' gia' presente")
    a = p.parse_args(argv)

    if not os.path.exists(a.audio):
        print(f"file non trovato: {a.audio}")
        return 1
    os.makedirs(a.cartella, exist_ok=True)

    tonica = None
    if a.tonica:
        if a.tonica not in NOMI:
            print(f"tonica non riconosciuta: {a.tonica}. Valori ammessi: "
                  + ", ".join(NOMI))
            return 1
        tonica = NOMI.index(a.tonica)

    return prova(a.audio, a.fmin, a.fmax, a.durata_minima, a.tolleranza,
                 a.conferma, a.collassa, a.ampiezza, tonica, a.cartella,
                 riusa=not a.riseparara, sicurezza_minima=a.sicurezza,
                 restringi=not a.niente_restringi)


if __name__ == "__main__":
    sys.exit(main())
