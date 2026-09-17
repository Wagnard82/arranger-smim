"""
MODULO 1c - Importazione da traccia audio multitraccia.

Separa un file audio in voce, basso, batteria e resto (Demucs), trascrive
ogni traccia in note (Basic Pitch per le tracce intonate, un rilevatore
d'attacchi a bande spettrali per la batteria), quantizza e ripulisce, e
costruisce direttamente melodia/basso/armonia/figurazione invece di farli
dedurre al motore da un unico pianoforte.

E' il ramo giusto quando si parte da una registrazione vera: la voce da'
la melodia senza bisogno di indovinarla, il basso da' il movimento per gli
strumenti gravi e la base per l'armonia, la batteria da' il groove per le
percussioni, il resto (chitarre, tastiere, archi) diventa materiale di
riempimento per l'accompagnamento.

Dipendenze pesanti e tutte facoltative — se mancano, il resto del software
funziona comunque:

    pip install demucs basic-pitch librosa

Demucs porta con se' PyTorch: e' un'installazione di alcuni minuti e alcune
centinaia di MB. Su una macchina senza GPU la separazione di un brano di
3-4 minuti richiede qualche minuto di CPU.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Set

from .analizzatore import _pesi_classi, _punteggio_accordo, _tonica_da_fifths
from .modello import (Accordo, Analisi, Evento, Misura, Nota, Parte, Partitura,
                      Spartito)
from .strumenti import PERC_MIDI, REGISTRO

# --------------------------------------------------------------------------
# Dipendenze
# --------------------------------------------------------------------------

TRACCE = ("vocals", "bass", "drums", "other")


def stato_dipendenze() -> Dict[str, bool]:
    """Diagnostica: quali pezzi della catena sono installati."""
    stato = {"demucs": False, "basic_pitch": False, "librosa": False,
             "beat_this": False}
    try:
        import demucs  # noqa: F401
        stato["demucs"] = True
    except ImportError:
        pass
    try:
        import basic_pitch  # noqa: F401
        stato["basic_pitch"] = True
    except ImportError:
        pass
    try:
        import librosa  # noqa: F401
        stato["librosa"] = True
    except ImportError:
        pass
    try:
        import beat_this  # noqa: F401
        stato["beat_this"] = True
    except ImportError:
        pass
    return stato


def disponibile() -> bool:
    """Il minimo per funzionare: separazione + trascrizione delle tracce intonate."""
    s = stato_dipendenze()
    return s["demucs"] and s["basic_pitch"]


def istruzioni_installazione(mancanti: List[str]) -> str:
    comandi = {"demucs": "pip install demucs", "basic_pitch": "pip install basic-pitch",
              "librosa": "pip install librosa",
              "beat_this": ("pip install tqdm einops soxr "
                            "rotary-embedding-torch && pip install "
                            "https://github.com/CPJKU/beat_this/archive/"
                            "main.zip")}
    righe = ["Per l'importazione da audio multitraccia mancano: "
            + ", ".join(mancanti) + "."]
    righe.append("Con l'ambiente virtuale attivo:")
    for m in mancanti:
        if m in comandi:
            righe.append("  " + comandi[m])
    if "demucs" in mancanti:
        righe.append("Demucs installa anche PyTorch: qualche minuto e alcune "
                     "centinaia di MB.")
    if "librosa" in mancanti:
        righe.append("Senza librosa la batteria non viene trascritta: le "
                     "percussioni useranno comunque un pattern automatico.")
    if "beat_this" in mancanti:
        righe.append("`beat_this` non e' obbligatorio: senza, il tempo viene "
                     "stimato con librosa, che sui brani dal ritmo sincopato "
                     "tende ad agganciarsi a una suddivisione sbagliata (e "
                     "sbagliando il tempo si sposta tutta la quantizzazione "
                     "a valle). Si appoggia a PyTorch, che Demucs ha gia' "
                     "installato: in pratica non aggiunge peso.")
    return "\n".join(righe)


# --------------------------------------------------------------------------
# Separazione delle fonti (Demucs)
# --------------------------------------------------------------------------


def separa_tracce(percorso_audio: str, cartella: str = "tmp_smim/stems",
                  modello: str = "htdemucs", timeout: int = 1800
                  ) -> Dict[str, str]:
    """
    Separa il file audio in voce, basso, batteria e resto.

    Si lancia Demucs da riga di comando invece che dalla sua API Python:
    l'API cambia forma fra le versioni, la riga di comando e' stabile ed e'
    quella documentata. Il modello di default (`htdemucs`) e' quello a 4
    tracce; e' il compromesso giusto fra qualita' e tempo di calcolo su CPU.
    """
    mancanti = [k for k, ok in stato_dipendenze().items()
               if not ok and k in ("demucs",)]
    if mancanti:
        raise RuntimeError(istruzioni_installazione(mancanti))

    os.makedirs(cartella, exist_ok=True)
    esito = subprocess.run(
        [sys.executable, "-m", "demucs", "-n", modello, "-o", cartella,
         "--", percorso_audio],
        capture_output=True, text=True, timeout=timeout)
    if esito.returncode != 0:
        raise RuntimeError("Separazione delle tracce fallita:\n"
                           + (esito.stderr or esito.stdout)[-2000:])

    base = os.path.splitext(os.path.basename(percorso_audio))[0]
    cartella_stem = os.path.join(cartella, modello, base)
    tracce: Dict[str, str] = {}
    for nome in TRACCE:
        percorso = os.path.join(cartella_stem, f"{nome}.wav")
        if os.path.exists(percorso):
            tracce[nome] = percorso
    mancano = [t for t in TRACCE if t not in tracce]
    if mancano:
        raise RuntimeError(
            f"Demucs non ha prodotto le tracce {mancano} in {cartella_stem}: "
            "controlla il log qui sopra.")
    return tracce


# --------------------------------------------------------------------------
# Trascrizione delle tracce intonate (voce, basso, resto)
# --------------------------------------------------------------------------


REGISTRI_MONOFONICI = {
    # (frequenza minima, massima) in Hz entro cui cercare la fondamentale.
    # Restringere la ricerca e' la difesa piu' efficace contro gli errori
    # d'ottava: se la traccia vocale non puo' produrre un Mi6, l'armonico non
    # ha proprio modo di essere scambiato per la nota vera.
    # Voce: da Do2 a Do6, abbondante per qualunque voce, dal basso profondo
    # al soprano.
    "voce": (65.4, 1046.5),
    # Basso: da Si0, la corda piu' grave del basso a cinque corde, a Do4.
    # Non si scende oltre: ogni ottava in meno costringe a raddoppiare la
    # finestra d'analisi, e con finestre lunghe le note rapide si impastano.
    # Sotto il Si0 ci sono comunque solo accordature molto ribassate, rare
    # nel repertorio SMIM.
    "basso": (30.87, 261.6),
}


def _colma_vuoti_brevi(semitoni: List[float], massimo: int = 6) -> List[float]:
    """
    Ricuce i buchi brevi nel contorno d'altezza, quando prima e dopo il buco
    l'altezza e' la stessa.

    PERCHE' SERVE. Scartare i fotogrammi poco affidabili sembra innocuo, ma
    non lo e': i fotogrammi scartati sono SPARSI, e ogni buco spezza la nota
    che lo contiene. I frammenti che ne risultano finiscono sotto la durata
    minima e vengono buttati via uno a uno. Non e' una perdita
    proporzionale, e' una valanga: misurato su una nota tenuta di un
    secondo, scartare il 25% dei fotogrammi la spezza in tre, e scartarne il
    50% non ne lascia nessuna.

    E' esattamente quello che era successo alla traccia vocale: da 484 note
    a 31, cioe' praticamente muta, mentre il materiale c'era.

    Si colmano percio' i vuoti fino a `massimo` fotogrammi (con il passo
    abituale, circa 70 ms) quando ai due lati c'e' la stessa altezza entro
    un semitono: in quel caso il buco non e' un silenzio, e' un momento di
    incertezza del rilevatore dentro una nota che sta continuando. I vuoti
    piu' lunghi restano: quelli sono pause vere, respiri, stacchi fra le
    parole.

    Funzione pura: verificabile con dati costruiti a mano.
    """
    def _e_nan(v: float) -> bool:
        return v != v

    fuori = list(semitoni)
    i = 0
    n = len(fuori)
    while i < n:
        if not _e_nan(fuori[i]):
            i += 1
            continue
        inizio = i
        while i < n and _e_nan(fuori[i]):
            i += 1
        fine = i                       # primo indice buono dopo il vuoto
        if inizio == 0 or fine >= n:
            continue                   # vuoto ai bordi: non si inventa nulla
        if fine - inizio > massimo:
            continue                   # pausa vera
        prima, dopo = fuori[inizio - 1], fuori[fine]
        if abs(prima - dopo) > 1.0:
            continue                   # altezze diverse: e' un cambio, non un buco
        for k in range(inizio, fine):
            frazione = (k - inizio + 1) / (fine - inizio + 1)
            fuori[k] = prima + (dopo - prima) * frazione
    return fuori


def _restringi_al_registro_reale(semitoni: List[float],
                                 ampiezza: float = 15.0,
                                 minimo_utile: int = 20) -> List[float]:
    """
    Scarta dal contorno d'altezza i tratti troppo lontani dal registro che
    la traccia usa DAVVERO.

    IL PROBLEMA. Il registro passato a `pyin` e' per forza generoso: deve
    andare bene per un basso profondo come per un soprano, perche' non
    sappiamo in anticipo chi canta. Ma un cantante singolo, dentro un brano
    singolo, ne occupa una porzione stretta — due ottave scarse. Quando la
    separazione lascia filtrare della chitarra nello stem vocale, quel
    materiale cade spesso fuori dalla porzione usata dalla voce, pur restando
    dentro il registro consentito.

    Sul repertorio vero il sintomo era netto: la traccia vocale copriva
    esattamente MIDI 36-84, cioe' PRECISAMENTE gli estremi del campo di
    ricerca. Quando le note occupano tutto lo spazio concesso fino ai bordi,
    non e' una voce con quattro ottave di estensione: e' il vincolo che sta
    facendo tutto il lavoro, e dentro c'e' dell'altro.

    Si prende percio' la mediana del contorno — robusta, non trascinata
    dagli intrusi — e si scartano i fotogrammi oltre `ampiezza` semitoni da
    essa. Quindici semitoni per lato fanno una fascia di due ottave e
    mezza: piu' larga dell'estensione di quasi ogni cantante, quindi
    prudente verso la voce vera, e comunque molto piu' stretta delle quattro
    ottave che il rilevatore stava producendo.

    Non si tocca niente se restano troppi pochi fotogrammi intonati per
    calcolare una mediana attendibile: meglio un contorno sporco che uno
    costruito su una statistica campata in aria.

    Funzione pura: verificabile con dati costruiti a mano.
    """
    def _e_nan(v: float) -> bool:
        return v != v

    validi = sorted(v for v in semitoni if not _e_nan(v))
    if len(validi) < minimo_utile:
        return list(semitoni)

    mediana = validi[len(validi) // 2]
    return [v if (not _e_nan(v) and abs(v - mediana) <= ampiezza)
            else float("nan")
            for v in semitoni]


def _note_da_f0(semitoni: List[float], passo: float,
                durata_minima: float = 0.08,
                tolleranza: float = 0.6,
                finestra_mediana: int = 5,
                conferma: int = 3) -> List[Nota]:
    """
    Trasforma un contorno di frequenza fondamentale in note vere e proprie.

    `semitoni` e' il contorno gia' convertito in numeri MIDI frazionari, un
    valore per fotogramma d'analisi, con `float('nan')` dove il rilevatore
    non ha trovato suono intonato (silenzi, consonanti, respiri). `passo` e'
    la durata di un fotogramma in secondi.

    Il lavoro e' di segmentazione: un contorno e' una linea continua che
    scivola fra le altezze, mentre una partitura vuole note discrete con un
    inizio, una durata e un'altezza sola. Si procede in tre tempi.

    1. FILTRO MEDIANO sul contorno. E' la difesa contro gli errori d'ottava
       isolati: un armonico scambiato per fondamentale dura tipicamente due o
       tre fotogrammi, e la mediana su una finestra piu' ampia lo cancella
       senza spostare le note vere. Sul MusicXML di prova erano 98 i salti
       d'ottava andata-e-ritorno — saliva di dodici semitoni e tornava
       subito indietro — e sono esattamente ci' che questo passaggio elimina.
       Un errore d'ottava PROLUNGATO invece sopravvive, ed e' giusto cosi':
       a quel punto non e' piu' distinguibile da un vero salto melodico, e
       la difesa contro quello e' il registro ristretto, non il filtro.

    2. SEGMENTAZIONE. Si accumulano fotogrammi finche' restano entro
       `tolleranza` semitoni dalla mediana del segmento in corso. Il
       confronto e' con la mediana e non con il fotogramma precedente:
       cosi' un vibrato ampio non spezza la nota in tante notine, mentre un
       cambio di altezza vero — che sposta la mediana — la chiude.

    3. SCARTO DEI FRAMMENTI. Sotto `durata_minima` non e' una nota: e'
       l'attacco di una consonante, un glissando di passaggio, un residuo di
       separazione. Nella notazione per una scuola media queste non vanno
       scritte: producono solo crome puntate illeggibili.

    Funzione pura, senza dipendenze esterne: e' la parte del rilevamento
    d'altezza che si puo' verificare con dati costruiti a mano, e infatti i
    test la coprono direttamente.
    """
    if not semitoni:
        return []

    def _e_nan(v: float) -> bool:
        return v != v      # solo NaN e' diverso da se stesso

    # --- 1. filtro mediano, saltando i tratti non intonati ---
    meta = max(0, finestra_mediana // 2)
    lisciati: List[float] = []
    for i, v in enumerate(semitoni):
        if _e_nan(v):
            lisciati.append(float("nan"))
            continue
        finestra = [u for u in semitoni[max(0, i - meta): i + meta + 1]
                    if not _e_nan(u)]
        finestra.sort()
        lisciati.append(finestra[len(finestra) // 2] if finestra else v)

    # --- 2. segmentazione ---
    note: List[Nota] = []
    inizio_idx: Optional[int] = None
    valori: List[float] = []
    sospesi: List[float] = []

    def _mediana(xs: List[float]) -> float:
        ordinati = sorted(xs)
        return ordinati[len(ordinati) // 2]

    def _chiudi(fine_idx: int) -> None:
        # --- 3. scarto dei frammenti ---
        if inizio_idx is None or not valori:
            return
        durata = (fine_idx - inizio_idx) * passo
        if durata < durata_minima:
            return
        altezza = int(round(_mediana(valori)))
        note.append(Nota(midi=altezza, inizio=inizio_idx * passo,
                         durata=durata, rigo=1))

    for i, v in enumerate(lisciati):
        if _e_nan(v):
            _chiudi(i)
            inizio_idx, valori, sospesi = None, [], []
            continue
        if inizio_idx is None:
            inizio_idx, valori, sospesi = i, [v], []
            continue
        if abs(v - _mediana(valori)) > tolleranza:
            # Un fotogramma fuori tolleranza NON chiude la nota: puo' essere
            # un vibrato ampio, un portamento, un'incertezza momentanea del
            # rilevatore. Serve una serie di `conferma` fotogrammi consecutivi
            # perche' si tratti davvero di un cambio d'altezza. Senza questa
            # cautela un vibrato spezzava la nota in frammenti tutti sotto la
            # durata minima, che venivano scartati uno a uno: il risultato
            # era una traccia VUOTA, il peggiore dei modi di sbagliare.
            sospesi.append(v)
            if len(sospesi) >= conferma:
                _chiudi(i - len(sospesi) + 1)
                inizio_idx = i - len(sospesi) + 1
                valori, sospesi = list(sospesi), []
        else:
            # rientrato: i sospesi erano oscillazione, non cambio d'altezza
            valori.extend(sospesi)
            valori.append(v)
            sospesi = []
    _chiudi(len(lisciati))

    # note contigue con la stessa altezza sono una nota sola tenuta: il
    # contorno puo' averle spezzate per un'incertezza momentanea, ma sulla
    # pagina devono comparire legate
    fuse: List[Nota] = []
    for n in note:
        if (fuse and fuse[-1].midi == n.midi
                and abs(fuse[-1].fine - n.inizio) < passo * 1.5):
            fuse[-1].durata = n.fine - fuse[-1].inizio
        else:
            fuse.append(n)
    return fuse


def trascrivi_monofonica(percorso_wav: str, registro: str = "voce",
                         sicurezza_minima: float = 0.0,
                         restringi: bool = True
                         ) -> Tuple[List[Nota], Optional[str]]:
    """
    Trascrive una traccia monofonica (voce o basso) con `librosa.pyin`,
    invece che con Basic Pitch.

    PERCHE'. Basic Pitch e' un modello POLIFONICO: cerca piu' altezze
    simultanee, ed e' la scelta giusta per la traccia "resto" (accordi,
    tastiere, chitarre). Sulla voce e sul basso, che sono linee singole,
    quella capacita' in piu' diventa un difetto: ogni armonico e' un
    candidato a diventare una nota. Sul MusicXML di prova la traccia vocale
    copriva quasi cinque ottave (da Fa1 a Mi6) — nessuna voce umana lo fa —
    con 98 salti d'ottava andata-e-ritorno, la firma inconfondibile
    dell'armonico scambiato per nota.

    `pyin` cerca UNA fondamentale per volta dentro un registro dichiarato in
    partenza (vedi `REGISTRI_MONOFONICI`). Il vincolo di registro e' la
    difesa piu' efficace: se la ricerca non puo' uscire dall'estensione di
    una voce, l'armonico non ha modo di vincere.

    C'e' anche un difetto che questa strada aggira. `riduci_a_monofonica`
    tiene, a ogni attacco, la nota piu' ACUTA — ma se la nota di troppo e'
    un armonico, cioe' la fondamentale piu' un'ottava, tenere la piu' acuta
    significa scartare la fondamentale e conservare proprio l'errore.

    Ritorna (note_in_secondi, motivo_del_fallimento). In caso di successo il
    motivo e' None; se `librosa` manca o l'analisi fallisce si restituisce
    (lista vuota, motivo), e il chiamante torna a Basic Pitch.

    ATTENDIBILITA': la chiamata a `pyin` e' scritta sulla documentazione di
    librosa e non e' stata eseguita contro la libreria vera (non installabile
    nell'ambiente in cui e' stata scritta). La segmentazione del contorno,
    che e' la parte con la logica musicale, sta in `_note_da_f0` ed e'
    verificata dai test.
    """
    try:
        import librosa
        import numpy as np
    except ImportError:
        return [], ("`librosa` non installato: voce e basso trascritti con "
                    "Basic Pitch, che essendo polifonico tende a scambiare "
                    "gli armonici per note vere.")

    fmin, fmax = REGISTRI_MONOFONICI.get(registro, REGISTRI_MONOFONICI["voce"])
    try:
        y, sr = librosa.load(percorso_wav, sr=None, mono=True)
        if y.size == 0:
            return [], "traccia vuota."
        # La finestra d'analisi va dimensionata sulla nota PIU' GRAVE che si
        # vuole poter riconoscere: per misurare un periodo servono almeno due
        # periodi dentro la finestra, quindi finestra > frequenza di
        # campionamento diviso frequenza minima. Violare questo vincolo non
        # degrada il risultato, lo fa fallire: `pyin` rifiuta la chiamata.
        # Lo si calcola invece di fissarlo, cosi' vale per qualunque
        # frequenza di campionamento e per qualunque registro si aggiunga in
        # futuro — l'alternativa (alzare fmin finche' l'errore sparisce)
        # avrebbe rimesso lo stesso inciampo un passo piu' in la'.
        # Il margine e' 2.5 periodi della nota piu' grave, non 4: con 4 la
        # finestra del basso arrivava a 8192 campioni, cioe' 186 ms, e un
        # attacco viene riconosciuto solo quando la finestra e'
        # prevalentemente dentro la nota — il che lo sposta in avanti fino a
        # meta' finestra. A 121 bpm erano quasi 90 ms, un quinto di
        # movimento: il basso usciva percettibilmente in ritardo. Con 2.5
        # restano comunque due periodi e mezzo dentro la finestra, che e'
        # quanto serve a misurare l'altezza, e il ritardo si dimezza.
        finestra = 2048
        while finestra < 2.5 * sr / fmin:
            finestra *= 2
        # Il passo fra un fotogramma e il successivo si tiene FISSO e corto,
        # indipendente dalla finestra. Sono due cose distinte: la finestra
        # determina quanto in basso si riesce a misurare l'altezza, il passo
        # con quanta precisione si colloca l'attacco nel tempo. Lasciando che
        # il passo seguisse la finestra, il basso sarebbe finito a 46 ms per
        # fotogramma: a 96 bpm una semicroma ne dura tre, troppo pochi per
        # collocarne l'inizio con precisione.
        salto = 512
        f0, _sonoro, sicurezza = librosa.pyin(y, fmin=fmin, fmax=fmax, sr=sr,
                                              frame_length=finestra,
                                              hop_length=salto)
        # SOGLIA DISATTIVATA PER IMPOSTAZIONE PREDEFINITA, e vale la pena
        # spiegare perche', perche' sembra un'informazione utile buttata via.
        #
        # `pyin` lavora in due tempi: prima calcola per ogni fotogramma le
        # altezze candidate con le loro probabilita' (ed e' quella la
        # `sicurezza` restituita qui), poi con una decodifica di Viterbi
        # sceglie la sequenza complessivamente piu' probabile e decide quali
        # fotogrammi siano intonati. I fotogrammi scartati da quella
        # decisione escono gia' come NaN.
        #
        # Il NaN, quindi, E' GIA' il giudizio di `pyin`, preso guardando il
        # contesto temporale. Filtrare in piu' sulla probabilita' del
        # singolo fotogramma significa mettere un giudizio piu' rozzo sopra
        # uno piu' informato, e disfarlo: una nota tenuta puo' benissimo
        # avere probabilita' modeste fotogramma per fotogramma ed essere
        # correttamente riconosciuta da Viterbi grazie a cio' che le sta
        # intorno.
        #
        # Sul repertorio vero il conto era impietoso: la soglia a 0.25
        # buttava via il 79% dei fotogrammi che `pyin` aveva deciso di
        # tenere sulla voce, e il 40% sul basso. La voce usciva muta e gli
        # attacchi del basso ballavano, perche' l'inizio di ogni nota
        # finiva sul primo fotogramma sopravvissuto invece che su quello
        # vero. Il parametro resta disponibile per fare prove, ma a zero.
        valori = np.asarray(f0, dtype=float)
        certezza = (np.asarray(sicurezza, dtype=float)
                    if sicurezza is not None else None)
        # da hertz a numeri MIDI frazionari; i tratti non intonati restano NaN
        semitoni = []
        for i, v in enumerate(valori):
            abbastanza_certo = (certezza is None
                                or certezza[i] >= sicurezza_minima)
            if v == v and v > 0 and abbastanza_certo:
                semitoni.append(float(69.0 + 12.0 * np.log2(v / 440.0)))
            else:
                semitoni.append(float("nan"))
        # Conteggi a OGNI stadio. La prima stesura contava solo dopo il
        # filtro di sicurezza, e quindi misurava soltanto lo stadio
        # innocente: quando la voce si e' svuotata, il report non aveva modo
        # di dirlo. Un conteggio che non copre lo stadio dove il materiale
        # sparisce e' peggio di nessun conteggio, perche' rassicura.
        grezzi = int(np.sum(valori == valori))
        dopo_sicurezza = sum(1 for v in semitoni if v == v)

        # I fotogrammi scartati sono SPARSI, e ogni buco spezza la nota che
        # lo contiene: senza ricucire, una nota tenuta si sbriciola in
        # frammenti che finiscono tutti sotto la durata minima.
        semitoni = _colma_vuoti_brevi(semitoni)
        dopo_ricucitura = sum(1 for v in semitoni if v == v)

        if restringi:
            semitoni = _restringi_al_registro_reale(semitoni)
        dopo_registro = sum(1 for v in semitoni if v == v)
        passo = float(salto) / float(sr)
        note = _note_da_f0(semitoni, passo)
        if not note:
            return [], ("`pyin` non ha trovato materiale intonato in questa "
                        "traccia: uso Basic Pitch.")

        # Diagnostica, non errore: quanto e' stato scartato perche' fuori dal
        # registro effettivamente usato dalla traccia. Una percentuale alta
        # significa che nello stem c'era parecchio materiale estraneo — di
        # solito uno strumento sfuggito dalla separazione. Serve saperlo: e'
        # l'unico modo di accorgersi che il problema sta a monte, nella
        # separazione, e non nel rilevamento d'altezza.
        avviso = None
        if grezzi:
            perso = 1.0 - dopo_registro / grezzi
            if perso > 0.15:
                avviso = (
                    f"traccia «{registro}»: dei {grezzi} fotogrammi intonati "
                    f"trovati, ne restano {dopo_registro} "
                    f"({100 * (1 - perso):.0f}%). Per incertezza del "
                    f"rilevatore: {grezzi - dopo_sicurezza}; ricuciti dopo: "
                    f"{dopo_ricucitura - dopo_sicurezza}; fuori dal registro "
                    f"usato dalla traccia: {dopo_ricucitura - dopo_registro}. "
                    "Se la parte risulta troppo vuota il numero da guardare "
                    "e' il primo; se ci sono note di un altro strumento, "
                    "l'ultimo.")
        return note, avviso
    except Exception as e:
        return [], f"rilevamento d'altezza con `pyin` fallito ({e})."


def trascrivi_intonata(percorso_wav: str, cartella_tmp: str = "tmp_smim"
                       ) -> List[Nota]:
    """
    Nota per nota, cosi' come la trascrive Basic Pitch, senza riduzioni.

    Il MIDI intermedio viene scritto con tempo fisso a 60 bpm
    (`midi_tempo=60.0`): un quarto dura esattamente un secondo, quindi le
    "durate in quarti" restituite qui sono, senza ambiguita', secondi reali.
    Serve a tenere voce/basso/resto sulla STESSA linea del tempo della
    batteria (che viene misurata direttamente in secondi da `librosa`):
    senza questo accorgimento, il tempo interno che Basic Pitch sceglie da
    solo per il suo MIDI non ha alcun rapporto con il tempo reale del brano,
    e le tracce intonate finiscono su un orologio diverso da quello della
    batteria.
    """
    from .ingestione import audio_in_midi, leggi_smf
    midi = audio_in_midi(percorso_wav, cartella_tmp, midi_tempo=60.0)
    grezze, _bpm, _metro = leggi_smf(midi)
    return [Nota(midi=m, inizio=t, durata=d, rigo=1)
            for (t, d, m, canale) in grezze if canale != 9]


def riduci_a_monofonica(note: List[Nota], preferisci: str = "alta") -> List[Nota]:
    """
    Riduce una trascrizione a una linea sola.

    Basic Pitch, su una traccia gia' isolata da Demucs, produce quasi sempre
    una linea pulita; i doppi che restano sono per lo piu' armonici presi per
    note vere. Si tiene, a ogni attacco, la nota piu' acuta (voce, "other") o
    la piu' grave (basso), e si accorciano le sovrapposizioni residue.
    """
    if not note:
        return []
    attacchi = sorted({round(n.inizio, 6) for n in note})
    scelta_fn = max if preferisci == "alta" else min
    linea: List[Nota] = []
    for t in attacchi:
        gruppo = [n for n in note if abs(n.inizio - t) < 1e-6]
        scelta = scelta_fn(gruppo, key=lambda n: n.midi)
        if linea and linea[-1].fine > t + 1e-6:
            linea[-1].durata = max(0.125, t - linea[-1].inizio)
        linea.append(Nota(midi=scelta.midi, inizio=scelta.inizio,
                          durata=scelta.durata, rigo=1))
    return linea


DURATE_PER_TRACCIA = {
    # (buco massimo per unire due note della stessa altezza,
    #  buco massimo per prolungare una nota fino alla successiva,
    #  durata minima di una nota), tutto in quarti.
    #
    # Valori MISURATI, non scelti a occhio: confrontando la nostra
    # trascrizione di «Seven Nation Army» con una riduzione pianistica del
    # brano, si e' cercato per ogni traccia la terna che avvicina di piu' la
    # distribuzione delle durate a quella dello spartito. La distanza fra le
    # due distribuzioni scende da 0.602 a 0.223 sulla voce e da 0.349 a
    # 0.194 sul basso.
    #
    # Le terne sono diverse per traccia, e non e' un caso. La voce si spezza
    # per le consonanti — buchi brevissimi dentro una sillaba tenuta — e va
    # quindi ricucita con un buco d'unione stretto ma legata generosamente
    # fino alla sillaba dopo. Il basso pizzicato ha invece code che si
    # spengono da sole, quindi tollera un buco d'unione ampio, ma non va
    # legato alla nota seguente, o si perdono gli stacchi del riff.
    # ATTENZIONE al primo valore: e' il buco massimo per fondere due note
    # della stessa altezza, e non puo' avvicinarsi a un valore ritmico vero.
    # Il basso aveva 0.5 — una croma — scelto perche' migliorava la
    # distribuzione delle durate. Era un errore di metodo: quella misura
    # premia le note lunghe, e le note lunghe si ottengono anche FONDENDO
    # note vere. Nel riff di «Seven Nation Army» ci sono due Mi separati da
    # esattamente una croma, e venivano fusi in uno: il riff usciva di
    # cinque note invece di sette. Sopra la semicroma si distruggono note
    # ribattute, che nei riff sono la norma.
    "vocals": (0.125, 0.25, 0.5),
    "bass": (0.125, 0.125, 0.5),
}


def ricomponi_note(note: List[Nota], buco_unione: float = 0.125,
                   buco_legatura: float = 0.25,
                   durata_minima: float = 0.5) -> List[Nota]:
    """
    Rimette insieme le note che il rilevatore d'altezza ha spezzato, e
    porta le durate a valori musicalmente plausibili.

    IL PROBLEMA, misurato. Nella nostra trascrizione della voce il 72% delle
    note durava una semicroma; nella riduzione pianistica dello stesso brano
    le semicrome sono il 12%, e il valore dominante e' la croma (55%). Le
    durate non erano sbagliate a caso: erano sistematicamente UN VALORE
    troppo corte.

    La causa e' che il rilevatore d'altezza misura quando c'e' una
    fondamentale riconoscibile, non quando dura la nota. Nel canto le due
    cose divergono di continuo: una consonante interrompe la fonazione
    dentro una sillaba tenuta, e la nota risulta finita quando in realta'
    prosegue. Sul basso pizzicato la coda si spegne prima dell'attacco
    successivo, e la nota sembra piu' corta di come va scritta.

    Tre passaggi, ognuno con la sua ragione musicale:

    1. UNIONE. Due note della stessa altezza separate da un buco piu' breve
       di `buco_unione` sono una nota sola: quel buco e' una consonante o
       un'incertezza, non un attacco nuovo.

    2. LEGATURA. Una nota seguita da un buco piu' breve di `buco_legatura`
       si prolunga fino all'attacco successivo. In una linea cantata una
       nota dura fino alla sillaba dopo, non fino a quando il microfono
       smette di captarla.

    3. DURATA MINIMA. Cio' che resta sotto `durata_minima` viene portato a
       quel valore, senza pero' mai invadere la nota successiva: meglio una
       croma leggibile che una semicroma che non corrisponde a niente.

    Le soglie sono diverse per traccia (vedi `DURATE_PER_TRACCIA`) perche' i
    due difetti sono diversi, e vanno passate da chi chiama.

    Funzione pura, in quarti: verificabile con dati costruiti a mano.
    """
    if not note:
        return []

    ordinate = sorted(note, key=lambda n: (n.inizio, n.midi))
    unite: List[Nota] = []
    for n in ordinate:
        if (unite and unite[-1].midi == n.midi
                and n.inizio - unite[-1].fine <= buco_unione + 1e-9):
            fine = max(unite[-1].fine, n.fine)
            unite[-1].durata = fine - unite[-1].inizio
        else:
            unite.append(Nota(midi=n.midi, inizio=n.inizio, durata=n.durata,
                              rigo=n.rigo))

    for i in range(len(unite) - 1):
        buco = unite[i + 1].inizio - unite[i].fine
        if 0 < buco <= buco_legatura + 1e-9:
            unite[i].durata = unite[i + 1].inizio - unite[i].inizio

    for i, n in enumerate(unite):
        if n.durata >= durata_minima - 1e-9:
            continue
        if i + 1 < len(unite):
            spazio = unite[i + 1].inizio - n.inizio
            if spazio > 0:
                n.durata = min(durata_minima, spazio)
        else:
            n.durata = durata_minima

    # GARANZIA DI MONOFONIA, in due parti. Voce e basso sono linee singole:
    # due note non possono suonare insieme, e il MusicXML non deve contenere
    # accordi in una parte che si legge come una voce sola.
    #
    # Primo: note che condividono lo STESSO attacco. Nascono dalla
    # quantizzazione, quando due note vicine finiscono sulla stessa
    # semicroma. Si tiene la piu' lunga, che e' quella che porta il suono
    # della frase; l'altra e' quasi sempre il residuo di un passaggio.
    per_attacco: List[Nota] = []
    for n in unite:
        if per_attacco and abs(per_attacco[-1].inizio - n.inizio) < 1e-6:
            if n.durata > per_attacco[-1].durata:
                per_attacco[-1] = n
        else:
            per_attacco.append(n)

    # Secondo: code che invadono la nota successiva. Arrivano dalla
    # trascrizione o dall'allungamento fatto qui sopra; si tronca.
    for i in range(len(per_attacco) - 1):
        if per_attacco[i].fine > per_attacco[i + 1].inizio:
            nuova = per_attacco[i + 1].inizio - per_attacco[i].inizio
            per_attacco[i].durata = max(1e-3, nuova)
    return per_attacco


def classi_ammesse(note: List[Nota], frazione_minima: float = 0.12,
                   minimo: int = 5) -> Set[int]:
    """
    Ricava dalle note quali altezze (indipendentemente dall'ottava) il brano
    usa davvero, ordinandole per durata complessiva e prendendone quante ne
    servono a coprire `copertura` del totale.

    PERCHE' NON SI STIMA LA TONALITA'. Sarebbe la strada ovvia, ma non
    funziona qui, per due motivi misurati sul repertorio vero. Primo:
    stimare la tonalita' dalla traccia da correggere e' circolare — sulla
    voce di «Seven Nation Army» i Fa naturali dei portamenti spingevano la
    stima su Do maggiore invece che su Mi minore, cioe' proprio l'errore da
    togliere finiva per giustificarsi da solo. Secondo: tonalita' vicine
    condividono sei note su sette, e il criterio le distingueva per un punto
    percentuale (96% contro 95%), che non e' un margine su cui decidere.

    Prendere le classi piu' usate di una traccia PULITA risolve entrambi i
    problemi e non ha bisogno di dare un nome alla tonalita'. Sul brano di
    prova, applicato al basso, restituisce esattamente le sei note del riff.

    NON E' UN CRITERIO TONALE, ed e' importante che non lo sia: molto
    pop-rock e' modale, e imporre una scala maggiore o minore vi
    introdurrebbe note che il brano non usa mentre ne toglierebbe di
    legittime. Qui non si confronta con nessun modello di scala: si guarda
    soltanto che cosa il brano suona davvero, e va bene per il misolidio,
    il dorico, una scala blues o una pentatonica.

    Le classi vanno ricavate da PIU' tracce insieme, non dal solo basso. Un
    basso costruito su un riff usa cinque o sei note, e la melodia puo'
    legittimamente uscirne: nel riferimento di prova la voce usa un Fa# che
    il basso non tocca mai, e prendere il solo basso come metro lo
    cancellerebbe.
    """
    peso: Dict[int, float] = {}
    for n in note:
        peso[n.midi % 12] = peso.get(n.midi % 12, 0.0) + max(0.0, n.durata)
    totale = sum(peso.values())
    if totale <= 0:
        return set(range(12))

    # IL CRITERIO E' IL PESO RELATIVO alla classe piu' usata, non una quota
    # cumulata: entra chi pesa almeno `frazione_minima` di quella. Misurato
    # sul brano di prova, le classi portanti nostre e del riferimento
    # coincidono (Mi, Do, Si, Sol, Re, La, tutte sopra il 13% della piu'
    # forte) e la differenza sta nella coda — il Re# dei portamenti arriva
    # da noi al 10.3% della piu' forte e nel riferimento all'1.6%. Una
    # soglia relativa separa le due cose; una quota cumulata no, perche'
    # dipende da quante classi ci sono e da come sono distribuite.
    ordinate = sorted(peso.items(), key=lambda kv: -kv[1])
    piu_forte = ordinate[0][1]
    ammesse = {classe for classe, valore in ordinate
               if valore >= frazione_minima * piu_forte}
    # non si scende sotto un numero minimo di classi: con tre o quattro
    # altezze ammesse si riscriverebbe il brano, non lo si ripulirebbe
    for classe, _valore in ordinate:
        if len(ammesse) >= minimo:
            break
        ammesse.add(classe)
    return ammesse


def pesi_classi(note: List[Nota]) -> Dict[int, float]:
    """Quanto pesa ciascuna altezza, in durata complessiva."""
    peso: Dict[int, float] = {}
    for n in note:
        peso[n.midi % 12] = peso.get(n.midi % 12, 0.0) + max(0.0, n.durata)
    return peso


def aggancia_alle_classi(note: List[Nota], ammesse: Set[int],
                         durata_max: float = 0.5,
                         pesi: Optional[Dict[int, float]] = None
                         ) -> List[Nota]:
    """
    Sposta al semitono piu' vicino le note la cui altezza non compare fra
    quelle che il brano usa.

    Sulla voce di prova il 39% delle note stava fuori dalla scala del brano,
    contro il 2% della riduzione pianistica. Le due classi in eccesso erano
    i due semitoni ADIACENTI alla nota tenuta principale: non note, ma il
    cantante che scivola dentro e fuori dall'intonazione. Scritte come note
    rendono la melodia impossibile da suonare, ed e' esattamente il difetto
    da togliere per una parte destinata a ragazzi.

    LA DIREZIONE CONTA, e sceglierla male costa caro. La prima stesura
    provava gli spostamenti in ordine fisso — prima sotto, poi sopra — e
    quell'ordine non aveva nessuna ragione musicale. Su «Seven Nation Army»
    il risultato era che ogni Re# finiva sul Re sotto invece che sul Mi
    sopra: la melodia vera e' per l'84% sul Mi, e la nostra usciva con il
    21% di Re che nell'originale non c'e'. Confrontando nota per nota con
    la partitura, correggere la direzione porta la precisione dal 54% al
    70% e il richiamo dal 43% al 55%.

    Fra i candidati a uno o due semitoni si sceglie percio' quello che PESA
    di piu' nel brano, non il primo di un elenco; a parita' di peso, il piu'
    vicino. Una nota storta tende verso la nota importante che le sta
    accanto, non verso quella che capita.

    SI TOCCANO SOLO LE NOTE BREVI (fino a `durata_max`). Una nota lunga
    fuori dalle classi abituali non e' una stonatura: e' una nota
    caratteristica, e in un brano modale spesso e' PROPRIO quella che
    definisce il modo — la sesta maggiore del dorico, la settima minore del
    misolidio. Cancellarla vorrebbe dire riscrivere il brano in una scala
    che non e' la sua. Un'inflessione, invece, e' breve per definizione.
    """
    if not ammesse or len(ammesse) >= 12:
        return list(note)
    if pesi is None:
        pesi = pesi_classi(note)

    fuori = []
    for n in note:
        midi = n.midi
        if midi % 12 not in ammesse and n.durata <= durata_max + 1e-9:
            candidati = [midi + delta for delta in (-1, 1, -2, 2)
                         if (midi + delta) % 12 in ammesse]
            if candidati:
                midi = max(candidati,
                           key=lambda m: (pesi.get(m % 12, 0.0),
                                          -abs(m - n.midi)))
        fuori.append(Nota(midi=midi, inizio=n.inizio, durata=n.durata,
                          rigo=n.rigo))
    return fuori


def assorbi_portamenti(note: List[Nota], durata_max: float = 0.25,
                       salto_max: int = 2) -> List[Nota]:
    """
    Assorbe le note brevi incastrate fra due note UGUALI e vicine d'altezza:
    sono portamenti, non note.

    La firma e' inconfondibile — Mi, Re#, Mi — e non richiede di sapere in
    che tonalita' si e': quel Re# non e' una scelta melodica, e' il
    passaggio fra due occorrenze della stessa nota. Riportandolo all'altezza
    dei vicini, la regola di unione lo fonde poi in un'unica nota tenuta, che
    e' come lo scriverebbe un arrangiatore.

    Si interviene solo su note brevi: un vicinato uguale attorno a una nota
    LUNGA e' una figurazione vera, non un'inflessione.
    """
    ordinate = sorted(note, key=lambda n: (n.inizio, n.midi))
    fuori = [Nota(midi=n.midi, inizio=n.inizio, durata=n.durata, rigo=n.rigo)
             for n in ordinate]
    for i in range(1, len(fuori) - 1):
        centrale, prima, dopo = fuori[i], fuori[i - 1], fuori[i + 1]
        if (centrale.durata <= durata_max + 1e-9
                and prima.midi == dopo.midi
                and 0 < abs(centrale.midi - prima.midi) <= salto_max):
            centrale.midi = prima.midi
    return fuori


def _firma_finestra(note: List[Nota], inizio: float,
                    risoluzione: float = 0.25) -> Set[Tuple[float, int]]:
    """Gli eventi di una finestra, come coppie (posizione relativa, altezza)."""
    return {(round((n.inizio - inizio) / risoluzione) * risoluzione, n.midi)
            for n in note}


def _somiglianza(a: Set, b: Set) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / max(1, len(a | b))


def consolida_riff(note: List[Nota], ampiezza: float = 8.0,
                   soglia: float = 0.3,
                   minimo_occorrenze: int = 4,
                   tolleranza: float = 0.25
                   ) -> Tuple[List[Nota], int]:
    """
    Riconosce il riff che si ripete e riscrive allo stesso modo tutte le sue
    occorrenze.

    L'OSSERVAZIONE, misurata. Nel pop-rock il basso ripete lo stesso inciso
    per tutto il brano. Nella riduzione pianistica di «Seven Nation Army»
    112 misure di basso si riducono a OTTO schemi distinti, e lo schema piu'
    frequente compare 50 volte. Nella nostra trascrizione le stesse misure
    davano NOVANTUNO schemi diversi: non perche' il bassista suonasse
    diversamente ogni volta, ma perche' ogni occorrenza raccoglieva i suoi
    piccoli errori di rilevamento. Sono varianti nostre, non sue.

    IL RIMEDIO. Si divide la traccia in finestre di `ampiezza` quarti, si
    trova la finestra che assomiglia di piu' a tutte le altre, e si
    costruisce un modello per VOTO: entrano nel modello gli eventi presenti
    nella maggioranza delle occorrenze simili, con la durata mediana. Poi
    ogni finestra abbastanza simile al modello viene riscritta col modello.

    Il voto e' la parte importante: un errore che capita in una occorrenza
    su dieci viene scartato dalla maggioranza, mentre una nota vera, che
    c'e' tutte le volte, resta. E' lo stesso principio per cui si misura una
    cosa piu' volte invece che una sola.

    LE CAUTELE. Si tocca solo cio' che supera `soglia` di somiglianza col
    modello: gli stacchi, gli assoli e i finali non gli assomigliano e
    restano come sono — un brano non e' fatto solo del suo riff. E si agisce
    solo se il modello ricorre almeno `minimo_occorrenze` volte, perche' su
    due o tre occorrenze «la maggioranza» non significa niente.

    I VALORI. Finestra di due misure e soglia 0.3, scelti misurando: sul
    brano di prova portano gli schemi distinti da 91 a 41 e la distanza
    dalla riduzione pianistica da 0.233 a 0.128. La soglia bassa sembra
    ardita, ma un controllo la giustifica: nel riferimento 44 finestre su 57
    sono il riff (il 77%), mentre con 0.3 noi ne riscriviamo 37 su 58 (il
    64%). Restiamo cioe' piu' prudenti di quanto il brano stesso sarebbe.

    Ritorna (note, quante finestre sono state riscritte).
    """
    if not note or ampiezza <= 0:
        return list(note), 0

    ordinate = sorted(note, key=lambda n: (n.inizio, n.midi))
    fine = max(n.fine for n in ordinate)
    n_finestre = int(fine // ampiezza) + 1
    finestre: Dict[int, List[Nota]] = {i: [] for i in range(n_finestre)}
    for n in ordinate:
        finestre[min(n_finestre - 1, int(n.inizio // ampiezza))].append(n)

    firme = {i: _firma_finestra(v, i * ampiezza)
             for i, v in finestre.items() if v}
    if len(firme) < minimo_occorrenze:
        return list(ordinate), 0

    # la finestra piu' "tipica": quella con la somiglianza media piu' alta
    migliore, punteggio_migliore = None, -1.0
    for i, f in firme.items():
        medio = sum(_somiglianza(f, g) for j, g in firme.items()
                    if j != i) / max(1, len(firme) - 1)
        if medio > punteggio_migliore:
            migliore, punteggio_migliore = i, medio

    if migliore is None:
        return list(ordinate), 0

    simili = [i for i, f in firme.items()
              if _somiglianza(f, firme[migliore]) >= soglia]
    if len(simili) < minimo_occorrenze:
        return list(ordinate), 0

    # VOTO: entra nel modello cio' che compare in piu' della meta' delle
    # occorrenze simili
    # I voti si raccolgono con TOLLERANZA di posizione. Senza, una nota
    # rilevata a 1.50 in meta' delle occorrenze e a 1.75 nell'altra meta' si
    # divide fra due caselle e nessuna raggiunge la maggioranza: la nota
    # vera viene scartata proprio perche' e' presente ovunque, ma con un
    # tremolio di collocazione. Misurato sul riff di prova: il Sol aveva 20
    # voti esatti e 31 entro una semicroma, il Si 28 contro 51 — entrambi
    # sotto la maggioranza da esatti, entrambi sopra con la tolleranza.
    voti: Dict[Tuple[float, int], List[Tuple[int, float, float]]] = {}
    for i in simili:
        base = i * ampiezza
        for n in finestre[i]:
            posizione = n.inizio - base
            chiave = None
            for (pos_nota, midi) in voti:
                if midi == n.midi and abs(pos_nota - posizione) <= tolleranza:
                    chiave = (pos_nota, midi)
                    break
            if chiave is None:
                chiave = (round(posizione / 0.25) * 0.25, n.midi)
                voti.setdefault(chiave, [])
            voti[chiave].append((i, posizione, n.durata))

    soglia_voti = len(simili) / 2.0
    conteggio = {k: len({occ for occ, _p, _d in v}) for k, v in voti.items()}
    durate = {k: [d for _o, _p, d in v] for k, v in voti.items()}
    # la posizione definitiva e' la MEDIANA di quelle votate, riportata sulla
    # griglia: piu' fedele del primo valore incontrato per caso
    posizioni_votate = {k: sorted(p for _o, p, _d in v)
                        for k, v in voti.items()}
    modello = sorted(k for k, c in conteggio.items() if c > soglia_voti)
    if not modello:
        return list(ordinate), 0

    def _mediana(xs: List[float]) -> float:
        y = sorted(xs)
        return y[len(y) // 2]

    fuori: List[Nota] = []
    riscritte = 0
    rigo = ordinate[0].rigo
    for i in range(n_finestre):
        if i in simili:
            base = i * ampiezza
            for posizione, midi in modello:
                votate = posizioni_votate[(posizione, midi)]
                collocazione = round(_mediana(votate) / 0.25) * 0.25
                fuori.append(Nota(midi=midi, inizio=base + collocazione,
                                  durata=_mediana(durate[(posizione, midi)]),
                                  rigo=rigo))
            riscritte += 1
        else:
            fuori.extend(finestre.get(i, []))
    fuori.sort(key=lambda n: (n.inizio, n.midi))
    return fuori, riscritte


def quantizza_e_pulisci(note: List[Nota], griglia: float = 0.25,
                        durata_minima: float = 0.125) -> List[Nota]:
    """
    Aggancia gli attacchi alla griglia ed elimina il rumore della
    trascrizione: durate troppo brevi, doppioni, micro-sfasamenti.

    Si riusa `ingestione.quantizza`, che fa esattamente questo lavoro sul
    modello dati dello spartito: costruire un `Spartito` usa e getta evita di
    duplicare la logica.
    """
    from .ingestione import quantizza
    involucro = Spartito(note=[Nota(midi=n.midi, inizio=n.inizio,
                                    durata=n.durata, rigo=n.rigo)
                               for n in note])
    quantizza(involucro, griglia=griglia, durata_minima=durata_minima)
    involucro.ordina()
    return involucro.note


# --------------------------------------------------------------------------
# Trascrizione della batteria (attacchi + bande spettrali)
# --------------------------------------------------------------------------


@dataclass
class ColpoBatteria:
    inizio: float
    strumento: str        # "grancassa" | "rullante" | "charleston"


def trascrivi_batteria(percorso_wav: str, bpm: float,
                       griglia: float = 0.25) -> List[ColpoBatteria]:
    """
    Individua gli attacchi nella traccia di batteria e li classifica per
    banda di frequenza dominante.

    La batteria non ha un'altezza da trascrivere: quello che serve e' il
    RITMO e una classificazione approssimativa in grave/medio/acuto (cassa,
    rullante, charleston). Si usano gli onset di libreria (`librosa`) e, per
    ogni attacco, l'energia in tre bande: sotto i 150 Hz e' quasi sempre
    cassa, fra 150 e 800 Hz con energia ampia e' rullante, sopra i 5 kHz e'
    charleston/piatti. E' un'euristica, non un riconoscitore di timbro: basta
    a dare un pattern ritmico credibile, non a distinguere ogni articolazione.

    Restituisce i colpi GIA' agganciati alla griglia (per l'uso normale,
    dentro l'orchestrazione). Per vedere gli attacchi esatti prima
    dell'aggancio — utile in fase di verifica, per capire se un errore viene
    dalla rilevazione degli onset o dalla quantizzazione — usare
    `trascrivi_batteria_grezza`.

    Richiede `librosa`; se manca si ritorna una lista vuota e il chiamante
    ripiega sul pattern di percussioni generato dal motore.
    """
    grezzi = trascrivi_batteria_grezza(percorso_wav, bpm)
    return _quantizza_colpi(grezzi, griglia)


def trascrivi_batteria_grezza(percorso_wav: str, bpm: float,
                              battiti: Optional[List[float]] = None,
                              indice_origine: int = 0) -> List[ColpoBatteria]:
    """
    Come `trascrivi_batteria`, ma senza agganciare gli attacchi alla griglia:
    il tempo di ogni colpo e' quello rilevato dall'onset, in quarti esatti.

    E' la versione da guardare per capire se un errore nella batteria viene
    dalla separazione/rilevazione (qui) o dalla quantizzazione (che arriva
    dopo, in `trascrivi_batteria`).

    Quando `battiti` c'e', gli istanti si leggono sulla GRIGLIA invece di
    essere divisi per la durata media del quarto: senza, un tempo medio
    anche solo dell'1% sbagliato fa scivolare la batteria di una misura
    ogni paio di minuti, e le percussioni si staccano progressivamente dalle
    altre parti. Con la griglia l'aggancio resta locale.
    """
    try:
        import librosa
        import numpy as np
    except ImportError:
        return []

    y, sr = librosa.load(percorso_wav, sr=None, mono=True)
    if y.size == 0:
        return []

    onset_frames = librosa.onset.onset_detect(y=y, sr=sr, backtrack=True,
                                              units="frames")
    onset_tempi = librosa.frames_to_time(onset_frames, sr=sr)
    passo = 60.0 / max(20.0, bpm)   # durata di un quarto in secondi

    colpi: List[ColpoBatteria] = []
    finestra = int(0.06 * sr)   # 60 ms dopo l'attacco
    for frame, tempo in zip(onset_frames, onset_tempi):
        campione = librosa.frames_to_samples(frame)
        segmento = y[campione:campione + finestra]
        if segmento.size < 32:
            continue
        spettro = np.abs(np.fft.rfft(segmento))
        freq = np.fft.rfftfreq(segmento.size, d=1.0 / sr)

        energia_bassa = spettro[freq < 150].sum()
        energia_media = spettro[(freq >= 150) & (freq < 800)].sum()
        energia_alta = spettro[freq >= 5000].sum()
        totale = energia_bassa + energia_media + energia_alta + 1e-9

        if energia_alta / totale > 0.35:
            strumento = "charleston"
        elif energia_bassa / totale > 0.40:
            strumento = "grancassa"
        else:
            strumento = "rullante"

        if battiti and len(battiti) >= 2:
            posizione = _quarti_su_griglia(float(tempo), battiti,
                                           indice_origine)
        else:
            posizione = float(tempo) / passo
        colpi.append(ColpoBatteria(inizio=posizione, strumento=strumento))

    colpi.sort(key=lambda c: c.inizio)
    return colpi


def _quantizza_colpi(colpi: List[ColpoBatteria], griglia: float
                     ) -> List[ColpoBatteria]:
    """Aggancia gli attacchi alla griglia e fonde quelli troppo vicini."""
    agganciati = [ColpoBatteria(inizio=round(c.inizio / griglia) * griglia,
                                strumento=c.strumento)
                 for c in colpi]
    agganciati.sort(key=lambda c: c.inizio)
    puliti: List[ColpoBatteria] = []
    for c in agganciati:
        if puliti and c.inizio - puliti[-1].inizio < griglia - 1e-6:
            continue
        puliti.append(c)
    return puliti


# --------------------------------------------------------------------------
# Armonia dal basso + resto
# --------------------------------------------------------------------------


def armonia_da_tracce(basso: List[Nota], resto: List[Nota], misure: List[Misura],
                      fifths: int = 0, per_movimento: bool = True
                      ) -> List[Accordo]:
    """
    Deduce la griglia armonica dal basso (che da' quasi sempre la
    fondamentale sul movimento) e da cio' che suona il resto degli strumenti
    (che da' la qualita' dell'accordo).

    Si riusano le stesse funzioni di punteggio del riconoscimento armonico
    principale (`analizzatore._pesi_classi`, `_punteggio_accordo`): qui la
    novita' e' solo la fonte del materiale, non il modo di valutarlo.
    """
    if not misure:
        return []
    tonica = _tonica_da_fifths(fifths)
    tutte = basso + resto
    accordi: List[Accordo] = []
    precedente: Optional[Accordo] = None

    for m in misure:
        passo = m.unita_movimento if per_movimento else m.durata
        t = m.inizio
        while t < m.fine - 1e-6:
            t1 = min(t + passo, m.fine)
            sonanti = [n for n in tutte if n.inizio < t1 - 1e-6 and n.fine > t + 1e-6]
            if not sonanti:
                t = t1
                continue
            pesi = _pesi_classi(sonanti, t, t1, passo)
            basso_qui = [n for n in basso if n.inizio < t1 - 1e-6 and n.fine > t + 1e-6]
            pc_basso = min(basso_qui, key=lambda n: n.midi).midi % 12 \
                if basso_qui else None
            migliore, punteggio_migliore = (0, "maj"), -1e18
            for fondamentale in range(12):
                for qualita in ("maj", "min", "dom7", "min7", "maj7", "dim",
                                "sus4", "6", "m6"):
                    p = _punteggio_accordo(pesi, pc_basso, fondamentale,
                                           qualita, tonica)
                    if precedente is not None and \
                            precedente.fondamentale == fondamentale and \
                            precedente.qualita == qualita:
                        p += 0.06
                    if p > punteggio_migliore:
                        migliore, punteggio_migliore = (fondamentale, qualita), p
            fond, qual = migliore
            acc = Accordo(inizio=t, durata=t1 - t, fondamentale=fond,
                         qualita=qual, basso=pc_basso, confidenza=1.0)
            if accordi and accordi[-1].fondamentale == fond \
                    and accordi[-1].qualita == qual \
                    and abs(accordi[-1].fine - t) < 1e-6:
                accordi[-1].durata += acc.durata
            else:
                accordi.append(acc)
            precedente = accordi[-1]
            t = t1
    return accordi


# --------------------------------------------------------------------------
# Assemblaggio
# --------------------------------------------------------------------------


@dataclass
class RisultatoMultitraccia:
    spartito: Spartito
    analisi: Analisi
    colpi_batteria: List[ColpoBatteria] = field(default_factory=list)
    avvisi: List[str] = field(default_factory=list)
    tracce_grezze: Dict[str, List[Nota]] = field(default_factory=dict)
    # voce/basso/resto DOPO la trascrizione e la riduzione a monofonica, ma
    # PRIMA della quantizzazione: serve a distinguere un errore della
    # separazione/trascrizione da un errore introdotto dall'aggancio alla
    # griglia.
    colpi_batteria_grezzi: List[ColpoBatteria] = field(default_factory=list)


def _misure_da_durata(durata_totale: float, bpm: float,
                      metro: Tuple[int, int] = (4, 4),
                      anacrusi_quarti: float = 0.0) -> List[Misura]:
    num, den = metro
    piena = num * 4.0 / den
    misure: List[Misura] = []
    inizio = 0.0
    if anacrusi_quarti > 1e-6:
        misure.append(Misura(numero=0, inizio=0.0, durata=anacrusi_quarti,
                             num=num, den=den, anacrusi=True))
        inizio = anacrusi_quarti
    n_piene = max(1 if not misure else 0,
                 int((durata_totale - inizio) / piena + 0.999))
    for i in range(n_piene):
        misure.append(Misura(numero=i + 1, inizio=inizio + i * piena,
                             durata=piena, num=num, den=den))
    return misure


def _primo_battere_e_anacrusi(primo_suono: float, battiti: List[float],
                              bpm: float, metro: Tuple[int, int] = (4, 4),
                              tolleranza: float = 0.15,
                              battere_noto: Optional[float] = None
                              ) -> Tuple[float, float]:
    """
    Dati l'istante del primo suono reale del brano (in secondi) e la griglia
    dei battiti rilevata dall'analisi del ritmo, decide dove cade il battere
    della prima misura e se prima di quel battere c'e' un'anacrusi.

    Il ragionamento e' lo stesso, in secondi, che il parser dei file
    simbolici applica in quarti (`ingestione._griglia_misure`): il battere
    di misura 1 e' la prima pulsazione forte e regolare del brano; se prima
    di quella pulsazione c'e' gia' del materiale musicale — non silenzio —
    quello e' un'anacrusi, e dura la differenza fra il battere e il primo
    suono. La tolleranza assorbe i pochi millisecondi di incertezza tipici
    della rilevazione degli attacchi.

    `battere_noto`, quando c'e', e' il battere individuato dal motore
    neurale, e vince su qualunque deduzione fatta qui. La differenza non e'
    accademica: la griglia dei battiti puo' cominciare a META' MISURA,
    perche' il modello la estrapola all'indietro dentro l'introduzione. Su
    Shape of You il primo battito rilevato cade sul TERZO movimento, e
    dedurre il battere come "il primo battito dopo il primo suono" — che e'
    quanto si puo' fare con la sola griglia — significherebbe far cominciare
    la misura 1 a meta' battuta, sfasando l'intera partitura di due
    movimenti. E' un errore silenzioso: il risultato sembra a tempo, ma gli
    accenti cadono nel posto sbagliato.

    Senza `battere_noto` (con il solo librosa, che da' i battiti ma non sa
    dire quali siano dei battere) si resta al ragionamento di prima, che
    resta il meglio ricavabile da quell'informazione.

    Ritorna (istante_del_battere_1_in_secondi, durata_anacrusi_in_quarti).
    Durata 0.0 se il primo suono coincide gia' con un battere (entro la
    tolleranza) o se la distanza e' troppo ampia per essere un'anacrusi
    credibile — segno che la griglia dei battiti e' sfasata rispetto al
    materiale, meglio non inventare una misura di levare che non c'e'.
    """
    passo = 60.0 / max(20.0, bpm)
    durata_misura = metro[0] * (4.0 / metro[1]) * passo   # in secondi

    if battere_noto is not None:
        battere1 = battere_noto
        # Se il primo suono precede il battere di meno di una misura, quel
        # materiale e' un'anacrusi vera e va conservato. Se lo precede di
        # PIU' di una misura, non e' levare: e' introduzione, rumore di
        # sala, sfumatura d'apertura — e va lasciato fuori dalla partitura
        # facendo cominciare il pezzo dal battere.
        differenza = battere1 - primo_suono
        if differenza <= tolleranza:
            return battere1, 0.0
        if differenza >= durata_misura - 1e-6:
            return battere1, 0.0
        return battere1, differenza / passo

    candidati = [b for b in battiti if b >= primo_suono - tolleranza]
    battere1 = min(candidati) if candidati else primo_suono
    differenza = battere1 - primo_suono

    if differenza <= tolleranza:
        return primo_suono, 0.0
    if differenza >= durata_misura - 1e-6:
        return primo_suono, 0.0
    return battere1, differenza / passo


def _a_scalare(x) -> float:
    """
    Estrae un numero semplice da qualunque cosa `librosa`/`numpy` restituisca
    al suo posto: un float gia' pronto, uno scalare numpy, o un array a uno o
    piu' elementi (si prende il primo).

    Serve perche' l'API di `librosa` non e' stabile su questo punto: fino
    alla versione 0.9 `beat_track` restituiva il tempo come un numero
    semplice, dalla 0.10 lo restituisce come un array di un elemento. Un
    `float()` diretto funzionava con le vecchie versioni di numpy ma smette
    di funzionare con le piu' recenti, che sollevano un errore invece di
    convertire in silenzio. Passare sempre da qui evita di doverlo scoprire
    di nuovo la prossima volta che una libreria cambia convenzione.
    """
    try:
        import numpy as np
        arr = np.asarray(x).reshape(-1)
        return float(arr[0]) if arr.size else 0.0
    except Exception:
        return float(x)


def _tempo_e_griglia_neurale(percorso_audio: str
                             ) -> Tuple[Optional[Tuple[float, List[float], float]],
                                        Optional[str]]:
    """
    Stima tempo, griglia dei battiti e primo BATTERE con `beat_this`, come
    alternativa piu' affidabile a `librosa.beat.beat_track`.

    PERCHE' UN SECONDO MOTORE. librosa stima il tempo per autocorrelazione
    dell'inviluppo degli attacchi: cerca cioe' ogni quanto il segnale "si
    ripete". Su un groove sincopato — tipico del pop moderno, dove i colpi
    piu' forti spesso NON cadono sul battito — puo' agganciarsi a una
    suddivisione sbagliata. Su Shape of You (96 bpm reali) l'export
    riportava 129 bpm: non un raddoppio o un dimezzamento, che sarebbero
    facili da riconoscere e correggere, ma un rapporto qualunque. E siccome
    tutta la quantizzazione a valle poggia su quel numero, sbagliare il
    tempo sposta ogni singola nota dell'arrangiamento.

    `beat_this` (Foscarin, Schlueter, Widmer — ISMIR 2024) e' una rete
    neurale addestrata a riconoscere direttamente battiti e battere. Sul
    medesimo brano stima 95.6 bpm contro i ~96 reali, e colloca il primo
    battere dopo l'introduzione rumorosa invece che sul primo rumore utile.

    PERCHE' NON madmom. Era la scelta naturale — stesso gruppo di ricerca —
    ma la versione pubblicata su PyPI regge solo Python < 3.10 e numpy <
    1.20, e su Python 3.12 non si installa senza forzature (Cython assente
    nell'ambiente di build, poi `pkg_resources` rimosso da setuptools). Gli
    autori stessi, con `beat_this`, sono andati oltre l'impianto di madmom:
    il loro nuovo modello e' accurato senza il modello a stati nascosti che
    ne era il cuore.

    DIPENDENZA OPZIONALE, ma leggera in pratica: `beat_this` si appoggia a
    PyTorch, che e' gia' presente per via di Demucs. Chi puo' importare da
    audio ha gia' il grosso di cio' che serve.

    Diversamente dalla prima stesura di questa funzione, i fallimenti non
    vengono piu' inghiottiti in silenzio: si restituisce anche il MOTIVO,
    perche' "non installato" e "installato ma l'analisi non ha concluso"
    richiedono rimedi diversi, e dal report devono potersi distinguere.

    Ritorna ((bpm, battiti_in_secondi, primo_battere_in_secondi), None) in
    caso di successo, oppure (None, motivo_del_fallimento).
    """
    try:
        import numpy as np
        from beat_this.inference import File2Beats
    except ImportError:
        return None, ("`beat_this` non installato: il tempo verra' stimato "
                      "con librosa, meno affidabile sui ritmi sincopati. "
                      "Per installarlo: pip install tqdm einops soxr "
                      "rotary-embedding-torch, poi pip install "
                      "https://github.com/CPJKU/beat_this/archive/main.zip")
    except Exception as e:
        return None, (f"`beat_this` presente ma non importabile ({e}): uso "
                      "librosa per il tempo.")

    try:
        # dbn=False: il modello e' progettato per essere accurato SENZA il
        # post-processing a stati nascosti di madmom, che secondo gli stessi
        # autori puo' introdurre rigidita' metrica. Serve anche a non
        # trascinarsi dietro madmom come dipendenza.
        battiti_sec, battere_sec = File2Beats(dbn=False)(percorso_audio)

        battiti = [float(t) for t in battiti_sec]
        battere = [float(t) for t in battere_sec]
        if len(battiti) < 4:
            return None, ("`beat_this` non ha trovato una pulsazione "
                          "riconoscibile nel brano: uso librosa.")

        # Il tempo si ricava dalla PENDENZA MEDIA di tutta la griglia
        # (ultimo battito meno primo, diviso il numero di intervalli) e non
        # dalla mediana dei singoli intervalli: sui dati reali di Shape of
        # You la mediana dava 96.8 e la pendenza 95.6, piu' vicina al vero,
        # perche' i singoli intervalli sono quantizzati a passi di ~0.02 s
        # mentre l'estremo del brano media via quell'errore.
        intervallo = (battiti[-1] - battiti[0]) / (len(battiti) - 1)
        if intervallo <= 0:
            return None, ("`beat_this` ha prodotto una griglia dei battiti "
                          "non utilizzabile: uso librosa.")
        bpm = 60.0 / intervallo
        if not (20.0 < bpm < 300.0):
            return None, (f"`beat_this` ha stimato un tempo non plausibile "
                          f"({bpm:.0f} bpm): uso librosa.")

        # ATTENZIONE, dettaglio non ovvio: la griglia dei battiti puo'
        # cominciare a META' MISURA, perche' il modello la estrapola
        # all'indietro dentro l'introduzione. Sul nostro caso di prova il
        # primo battito cadeva sul TERZO movimento della misura: prenderlo
        # per inizio della misura 1 avrebbe sfasato tutto di due movimenti.
        # Per questo il battere si legge dall'elenco dedicato, mai dal primo
        # battito.
        primo_battere = battere[0] if battere else battiti[0]

        return (bpm, battiti, float(primo_battere)), None
    except Exception as e:
        return None, (f"analisi con `beat_this` fallita ({e}): uso librosa "
                      "per il tempo.")


def analizza_ritmo(percorso_audio: str, bpm_manuale: Optional[float] = None
                   ) -> Tuple[float, List[float], float, Optional[float],
                              List[str]]:
    """
    Un'unica analisi del brano — tempo, griglia dei battiti, primo suono,
    primo battere — fatta UNA volta sul file audio COMPLETO.

    Prima questa analisi era spezzata in due, con due difetti che si
    sommavano: il tempo veniva stimato dalla sola traccia di BATTERIA gia'
    separata, e la griglia dei battiti veniva ricalcolata a parte, di nuovo,
    sul mix intero — due segnali diversi, con la possibilita' concreta che
    disaccordassero. Su registrazioni datate o con un mix scarno (tipico di
    molte incisioni anteriori agli anni '80) la traccia di batteria isolata
    da Demucs puo' essere debole o incompleta, e la stima del tempo fatta
    solo su di essa ne risente. Il mix intero ha sempre il ritmo portato
    anche da basso, chitarre, voce: un segnale piu' ricco su cui stimare il
    tempo, ed e' anche piu' semplice — un solo caricamento del file, non due.

    Non si nasconde piu' un fallimento dietro un valore plausibile mandato in
    silenzio: se l'analisi fallisce, o il tempo rilevato non e' credibile, lo
    si dice negli avvisi restituiti, invece di far apparire 100 bpm come se
    fosse una misura vera.

    Con `bpm_manuale` impostato, quel valore diventa il tempo definitivo
    (nessun algoritmo automatico e' del tutto affidabile: se conosci il
    tempo del brano, usarlo e' sempre la scelta migliore); la griglia dei
    battiti si cerca comunque, per l'individuazione dell'anacrusi, usando
    quel tempo come riferimento.

    Ritorna (bpm, battiti_in_secondi, primo_suono_in_secondi,
    primo_battere_in_secondi, avvisi). Il primo battere e' None quando il
    motore neurale non e' disponibile: librosa da' i battiti ma non sa dire
    QUALI di essi siano dei battere, e quell'informazione non si puo'
    inventare. Chi la riceve deve trattare None come "non lo so", non come
    "non c'e' anacrusi".
    """
    try:
        import librosa
    except ImportError:
        return (bpm_manuale or 100.0, [], 0.0, None,
               ["`librosa` non installato: impossibile analizzare tempo e "
                "battere. Uso " + (f"il bpm indicato ({bpm_manuale:g})."
                                   if bpm_manuale else
                                   "un tempo di default (100 bpm) — "
                                   "correggilo a mano se conosci quello "
                                   "reale.")])

    try:
        y, sr = librosa.load(percorso_audio, sr=None, mono=True)
        if y.size == 0:
            return (bpm_manuale or 100.0, [], 0.0, None,
                    ["il file audio risulta vuoto: analisi del ritmo "
                     "saltata."])

        # Si prova prima `beat_this`, piu' affidabile sui groove sincopati e
        # sulle introduzioni rumorose; se non c'e' o non conclude, si
        # prosegue con librosa esattamente come prima.
        origine_tempo = "librosa"
        motivo_ricaduta = None
        battere_noto: Optional[float] = None
        esito_neurale, motivo_ricaduta = _tempo_e_griglia_neurale(percorso_audio)
        if esito_neurale is not None:
            origine_tempo = "beat_this"
            # il battere NON si butta via: e' l'unica indicazione affidabile
            # di dove cominci davvero la misura 1 (vedi
            # `_primo_battere_e_anacrusi`)
            tempo, battiti, battere_noto = esito_neurale
        else:
            tempo, beat_frames = librosa.beat.beat_track(
                y=y, sr=sr, start_bpm=bpm_manuale or 120.0)
            # dalla versione 0.10 di librosa, il tempo restituito da
            # beat_track e' un array numpy (forma (1,)), non piu' un numero
            # semplice: con le versioni recenti di numpy, un float() diretto
            # su un array del genere solleva "only 0-dimensional arrays can
            # be converted to Python scalars". _a_scalare estrae il valore in
            # ogni caso, che sia gia' un numero, un array a un elemento o uno
            # scalare numpy, e la conversione resta comunque dentro il blocco
            # protetto: se qualcosa va storto qui, si ricade nell'avviso
            # esplicito piu' sotto, non in un errore che blocca tutta
            # l'importazione.
            tempo = _a_scalare(tempo)
            battiti = [float(t)
                       for t in librosa.frames_to_time(beat_frames, sr=sr)]

        # Il primo attacco resta quello rilevato da librosa: e' il primo
        # suono LETTERALE del file, rumore d'introduzione compreso. Non e' un
        # difetto: `_primo_battere_e_anacrusi` lo confronta con la griglia
        # dei battiti proprio per decidere se sia un'anacrusi vera o materiale
        # da scartare. Migliorando la griglia con `beat_this`, migliora di
        # riflesso anche quella decisione, senza toccarne la logica.
        onset_frames = librosa.onset.onset_detect(y=y, sr=sr, backtrack=True,
                                                  units="frames")
        primo_suono = (_a_scalare(librosa.frames_to_time(onset_frames[0], sr=sr))
                       if len(onset_frames) else 0.0)
    except Exception as e:
        return (bpm_manuale or 100.0, [], 0.0, None,
               [f"analisi del ritmo fallita ({e}): uso "
                + (f"il bpm indicato ({bpm_manuale:g})."
                   if bpm_manuale else
                   "un tempo di default (100 bpm) — probabilmente sbagliato: "
                   "indica il bpm reale a mano se lo conosci.")])

    avvisi = []
    if bpm_manuale:
        bpm_finale = bpm_manuale
    elif tempo and tempo > 20:
        bpm_finale = tempo
        if origine_tempo == "beat_this":
            avvisi.append(
                f"tempo rilevato con `beat_this`: {bpm_finale:.0f} bpm. E' il "
                "piu' affidabile dei due motori, ma nessuno e' infallibile: "
                "se il valore non e' quello giusto, indica il bpm a mano.")
        else:
            # Il MOTIVO della ricaduta va detto, non nascosto: "non
            # installato" e "installato ma l'analisi e' fallita" si
            # correggono in modi diversi, e senza distinguerli si finisce a
            # cercare il problema dalla parte sbagliata.
            avviso = (f"tempo rilevato con librosa: {bpm_finale:.0f} bpm. "
                      "librosa tende ad agganciarsi a una suddivisione "
                      "sbagliata sui brani dal ritmo sincopato: se il valore "
                      "non torna, indica il bpm a mano.")
            if motivo_ricaduta:
                avviso += " Motivo del ripiego su librosa: " + motivo_ricaduta
            avvisi.append(avviso)
    else:
        bpm_finale = 100.0
        avvisi.append(
            "il tempo rilevato automaticamente non sembrava plausibile: uso "
            "un valore di default (100 bpm), quasi certamente sbagliato. "
            "Indica il bpm reale a mano.")

    return bpm_finale, battiti, primo_suono, battere_noto, avvisi


def rileva_inizio(percorso_audio: str, bpm: float, metro: Tuple[int, int] = (4, 4)
                  ) -> Tuple[float, float]:
    """
    Scorciatoia mantenuta per compatibilita': dato il bpm gia' noto, trova
    l'istante in cui comincia davvero il brano e l'eventuale anacrusi.

    Il nuovo codice dovrebbe chiamare `analizza_ritmo` direttamente, che fa
    la stessa analisi ma in un solo passaggio e con gli avvisi sui
    fallimenti; questa funzione la richiama passandole il bpm come
    riferimento per la ricerca dei battiti.
    """
    _bpm, battiti, primo_suono, _battere, _avvisi = analizza_ritmo(percorso_audio,
                                                         bpm_manuale=bpm)
    if not battiti and not primo_suono:
        return 0.0, 0.0
    return _primo_battere_e_anacrusi(primo_suono, battiti, bpm, metro)


def _fase_battere_da_batteria(colpi_quarti: List[ColpoBatteria],
                              bpm: float,
                              metro: Tuple[int, int] = (4, 4)
                              ) -> Tuple[int, Optional[str]]:
    """
    Verifica, e se serve corregge, QUALE battito sia il primo della misura,
    usando la batteria come testimone.

    IL PROBLEMA. Individuare i battiti e individuare il BATTERE sono due
    compiti diversi, e il secondo e' molto piu' difficile: la pulsazione si
    sente, la posizione metrica va dedotta dagli accenti. `beat_this` puo'
    quindi azzeccare il tempo e sbagliare la fase, cioe' far cominciare la
    misura su un movimento debole. Su «Another One Bites the Dust» il tempo
    era esatto (110 bpm) ma la griglia partiva un movimento piu' in la': la
    grancassa cadeva sul secondo e sul quarto movimento invece che sul primo
    e sul terzo, e il rullante sul terzo invece che sul secondo e sul quarto.
    E' un errore silenzioso: non stona, ma sposta tutti gli accenti.

    LA PROVA. Nel pop e nel rock il rullante sta sui movimenti PARI (il
    backbeat) e la grancassa sui DISPARI. E' una convenzione cosi' diffusa
    da poter essere usata come misura: si prova a far cominciare la misura
    su ciascuno dei movimenti possibili e si tiene quello che accorda meglio
    i colpi con questa attesa.

    IL LIMITE, che va detto. Uno schema con grancassa sull'uno-tre e
    rullante sul due-quattro e' SIMMETRICO se lo si ruota di mezza misura.
    La batteria puo' quindi dire che la fase e' sbagliata di un numero
    DISPARI di movimenti, non se di uno o di tre. A parita' di punteggio si
    sceglie lo spostamento piu' piccolo, restando cosi' il piu' vicino
    possibile a quanto aveva concluso `beat_this`: un eventuale residuo di
    mezza misura lascia comunque gli accenti al posto giusto DENTRO la
    misura, mentre un errore di un movimento no.

    Non si corregge nulla se la prova e' debole: senza un backbeat netto —
    musica classica, valzer, brani senza batteria — l'attesa su cui si basa
    il ragionamento non vale, e forzarla peggiorerebbe le cose.

    UNITA'. `colpi_quarti` ha gli istanti gia' in QUARTI e gia' riferiti
    all'origine della partitura, che e' come li restituisce
    `trascrivi_batteria_grezza`. Il nome lo dice per esteso di proposito: la
    prima stesura di questa funzione li trattava come secondi e li divideva
    un'altra volta per la durata del quarto, calcolando posizioni prive di
    senso. Non falliva in modo visibile — trovava semplicemente che nessuna
    fase era migliore dell'altra e lasciava tutto com'era, cioe' sbagliato.

    Ritorna (movimenti_di_spostamento, avviso_o_None).
    """
    battiti_per_misura = max(2, metro[0])
    if not colpi_quarti or bpm <= 20:
        return 0, None

    forti = {i for i in range(battiti_per_misura) if i % 2 == 0}
    deboli = {i for i in range(battiti_per_misura) if i % 2 == 1}

    def punteggio(spostamento: int) -> Tuple[float, int]:
        buoni = totale = 0
        for c in colpi_quarti:
            movimento = int(round(c.inizio - spostamento)) % battiti_per_misura
            if c.strumento == "rullante":
                totale += 1
                buoni += movimento in deboli
            elif c.strumento == "grancassa":
                totale += 1
                buoni += movimento in forti
        return (buoni / totale if totale else 0.0), totale

    base, campioni = punteggio(0)
    if campioni < 20:
        # troppo pochi colpi di grancassa e rullante per fidarsi della prova
        return 0, None

    migliore, punti_migliore = 0, base
    for sp in range(1, battiti_per_misura):
        p, _ = punteggio(sp)
        if p > punti_migliore + 1e-9:
            migliore, punti_migliore = sp, p

    if migliore == 0:
        return 0, None
    # Si corregge solo su prova netta: il nuovo assetto deve accordarsi con
    # l'attesa in modo chiaro E migliorare sensibilmente quello attuale. Con
    # una soglia lasca si finirebbe per spostare la misura anche su brani che
    # semplicemente non hanno un backbeat, peggiorando quel che funzionava.
    if punti_migliore < 0.65 or punti_migliore - base < 0.20:
        return 0, None

    return migliore, (
        f"battere spostato di {migliore} "
        f"{'movimento' if migliore == 1 else 'movimenti'}: con la griglia "
        f"iniziale grancassa e rullante cadevano nel posto sbagliato "
        f"({base * 100:.0f}% di accordo con lo schema abituale), spostandola "
        f"tornano al loro posto ({punti_migliore * 100:.0f}%). Se il brano "
        "non ha un backbeat classico, verifica che la prima misura cominci "
        "dove te l'aspetti.")


def _quarti_su_griglia(istante: float, battiti: List[float],
                       indice_origine: int) -> float:
    """
    Converte un istante in secondi nella sua posizione in quarti, leggendola
    sulla GRIGLIA DEI BATTITI invece che moltiplicando per un tempo medio.

    PERCHE'. Il tempo medio e' un solo numero, e un solo numero non puo'
    descrivere un brano suonato da esseri umani. Ogni scarto fra quel numero
    e il tempo reale si ACCUMULA: convertendo con 121 bpm un brano che ne fa
    123, dopo quattro minuti si e' fuori di quattro secondi, cioe' di due
    misure. Su «Seven Nation Army» era esattamente questo il difetto — le
    prime battute a posto, poi uno scivolamento progressivo.

    La griglia invece dice dove cade OGNI battito. Collocare una nota fra il
    battito che la precede e quello che la segue rende l'errore locale e non
    cumulativo: un battito impreciso sposta le note vicine, non tutte quelle
    successive. E funziona anche quando il tempo cambia davvero — un
    rallentando, un ritornello leggermente piu' mosso — perche' non si
    assume affatto che sia costante.

    `indice_origine` e' il battito che vale quarto 0, cioe' il battere della
    prima misura. Fuori dalla griglia (prima del primo battito o dopo
    l'ultimo) si prolunga l'andamento con l'intervallo di bordo: e' l'unica
    cosa ragionevole da fare, e riguarda comunque solo eventuali code.

    Funzione pura: nessuna dipendenza, verificabile con dati costruiti a
    mano.
    """
    n = len(battiti)
    if n < 2:
        return 0.0

    if istante <= battiti[0]:
        passo = battiti[1] - battiti[0]
        if passo <= 0:
            return -float(indice_origine)
        return (istante - battiti[0]) / passo - indice_origine
    if istante >= battiti[-1]:
        passo = battiti[-1] - battiti[-2]
        if passo <= 0:
            return (n - 1) - indice_origine
        return (n - 1) + (istante - battiti[-1]) / passo - indice_origine

    # ricerca binaria del battito immediatamente precedente
    basso, alto = 0, n - 1
    while alto - basso > 1:
        mezzo = (basso + alto) // 2
        if battiti[mezzo] <= istante:
            basso = mezzo
        else:
            alto = mezzo
    passo = battiti[alto] - battiti[basso]
    frazione = (istante - battiti[basso]) / passo if passo > 0 else 0.0
    return basso + frazione - indice_origine


def _indice_battito(battiti: List[float], istante: float) -> int:
    """
    Indice del battito piu' vicino a `istante`. Serve a stabilire quale
    battito della griglia sia il battere della prima misura, cioe' il
    quarto 0 della partitura.
    """
    if not battiti:
        return 0
    migliore, distanza = 0, abs(battiti[0] - istante)
    for i, b in enumerate(battiti):
        d = abs(b - istante)
        if d < distanza:
            migliore, distanza = i, d
    return migliore


def _secondi_a_quarti(note: List[Nota], bpm: float,
                      ancora_secondi: float = 0.0,
                      battiti: Optional[List[float]] = None,
                      indice_origine: int = 0) -> List[Nota]:
    """
    Converte una lista di note dai secondi (l'unita' in cui esce
    `trascrivi_intonata`, grazie al tempo neutro 60 bpm del MIDI intermedio)
    ai quarti musicali reali del brano, ancorando l'istante `ancora_secondi`
    a t=0. E' il punto in cui voce/basso/resto smettono di essere
    sull'orologio arbitrario di Basic Pitch e passano su quello reale del
    pezzo, lo stesso della batteria.

    Quando `battiti` c'e', la conversione legge la posizione sulla GRIGLIA
    (vedi `_quarti_su_griglia`) invece di moltiplicare per il tempo medio:
    cosi' un tempo medio leggermente sbagliato, o un brano che accelera,
    non producono uno scivolamento che cresce battuta dopo battuta. Il
    percorso con il solo `bpm` resta per quando la griglia non c'e' — con il
    solo librosa, o se il rilevamento dei battiti non ha concluso.
    """
    if battiti and len(battiti) >= 2:
        fuori = []
        for n in note:
            if n.inizio < ancora_secondi - 1e-3:
                continue      # prima dell'inizio rilevato: silenzio o rumore
            inizio = _quarti_su_griglia(n.inizio, battiti, indice_origine)
            fine = _quarti_su_griglia(n.inizio + n.durata, battiti,
                                      indice_origine)
            fuori.append(Nota(midi=n.midi, inizio=inizio,
                              durata=max(1e-3, fine - inizio), rigo=n.rigo))
        return fuori

    fattore = bpm / 60.0
    fuori = []
    for n in note:
        if n.inizio < ancora_secondi - 1e-3:
            continue          # prima dell'inizio rilevato: silenzio o rumore
        fuori.append(Nota(midi=n.midi,
                          inizio=(n.inizio - ancora_secondi) * fattore,
                          durata=n.durata * fattore, rigo=n.rigo))
    return fuori


def _sposta_colpi(colpi: List[ColpoBatteria], quarti: float
                  ) -> List[ColpoBatteria]:
    """Come sopra ma per i colpi di batteria, gia' in quarti reali."""
    return [ColpoBatteria(inizio=c.inizio - quarti, strumento=c.strumento)
           for c in colpi if c.inizio - quarti > -1e-3]


def costruisci_da_tracce(tracce_note: Dict[str, List[Nota]], bpm: float,
                         metro: Tuple[int, int] = (4, 4),
                         colpi_batteria: Optional[List[ColpoBatteria]] = None,
                         titolo: str = "Brano importato da audio",
                         tracce_grezze: Optional[Dict[str, List[Nota]]] = None,
                         colpi_batteria_grezzi: Optional[List[ColpoBatteria]] = None,
                         anacrusi_quarti: float = 0.0
                         ) -> RisultatoMultitraccia:
    """
    Assembla `Spartito` e `Analisi` direttamente dalle tracce separate, senza
    passare dal rilevatore di melodia: qui la melodia non va indovinata,
    e' la traccia voce.

    `anacrusi_quarti`: se il brano comincia con una misura di levare — lo
    decide `rileva_inizio` confrontando il primo suono con la griglia dei
    battiti — la prima misura viene creata parziale (`Misura(numero=0,
    anacrusi=True)`), esattamente come fa il parser dei file simbolici.
    """
    avvisi: List[str] = []
    voce = tracce_note.get("vocals", [])
    basso = tracce_note.get("bass", [])
    resto = tracce_note.get("other", [])

    fine = max([n.fine for lista in tracce_note.values() for n in lista] + [0.0])
    misure = _misure_da_durata(fine, bpm, metro, anacrusi_quarti)

    if not voce:
        avvisi.append(
            "Nessuna voce/melodia rilevata nella traccia separata: il brano "
            "verra' trattato come materiale di sola tessitura (nessun "
            "solista). Se il brano ha una melodia strumentale isolabile, "
            "verifica la traccia 'vocals' separata.")
        melodia: List[Nota] = []
    else:
        melodia = voce

    basso_pulito = basso
    if not basso_pulito:
        avvisi.append("Traccia del basso vuota: il sostegno grave verra' "
                      "dedotto dagli accordi.")

    fifths = 0   # senza un'armatura di riferimento si assume Do maggiore/La minore
    armonia = armonia_da_tracce(basso_pulito, resto, misure, fifths)
    if not armonia and (basso_pulito or resto):
        avvisi.append("Non e' stato possibile dedurre una griglia armonica "
                      "dalle tracce: l'accompagnamento sara' limitato.")

    sp = Spartito(titolo=titolo, note=melodia + basso_pulito + resto,
                 misure=misure, bpm=bpm)
    sp.tipo = "audio_multitraccia"
    sp.anacrusi = anacrusi_quarti
    sp.ordina()
    if anacrusi_quarti > 1e-6:
        avvisi.append(
            f"Rilevata un'anacrusi di circa {anacrusi_quarti:.2f} quarti "
            "prima del primo battere pieno: il primo suono del brano "
            "precede la pulsazione regolare del ritmo.")

    frasi = [(m.inizio, m.fine) for m in misure]     # affinate sotto
    from .analizzatore import raggruppa_in_periodi, rileva_frasi, rileva_sezioni
    frasi = rileva_frasi(sp, melodia, armonia) if melodia else frasi
    sezioni, forma, ritornelli = rileva_sezioni(sp, melodia) if melodia else ([], "classica", [])
    periodi = raggruppa_in_periodi(frasi, sp, melodia, armonia) if melodia else frasi

    analisi = Analisi(melodia=melodia, armonia=armonia, basso=basso_pulito,
                      figurazione=resto, voci_interne=[], frammenti=[],
                      groove=[], suddivisione=0.5, frasi=frasi,
                      periodi=periodi, sezioni=sezioni, forma=forma,
                      ritornelli=ritornelli,
                      melodia_affidabile=bool(melodia))

    return RisultatoMultitraccia(spartito=sp, analisi=analisi,
                                 colpi_batteria=colpi_batteria or [],
                                 avvisi=avvisi,
                                 tracce_grezze=tracce_grezze or {},
                                 colpi_batteria_grezzi=colpi_batteria_grezzi or [])


# --------------------------------------------------------------------------
# Pipeline completa
# --------------------------------------------------------------------------


def importa(percorso_audio: str, cartella_tmp: str = "tmp_smim",
           griglia: float = 0.25, titolo: Optional[str] = None,
           bpm_manuale: Optional[float] = None
           ) -> RisultatoMultitraccia:
    """
    Dal file audio al risultato pronto per l'arrangiatore: separazione,
    trascrizione di ogni traccia, ricerca del vero inizio del brano (e
    dell'eventuale anacrusi), quantizzazione, assemblaggio.

    `bpm_manuale`: nessun rilevatore automatico del tempo e' del tutto
    affidabile — un errore di ottava (meta' o doppio del tempo vero) e' il
    modo piu' comune in cui sbaglia, ed e' difficile da escludere in
    automatico con certezza. Se conosci il tempo del brano, indicarlo qui
    e' sempre la scelta piu' sicura: la ricerca del battere e dell'anacrusi
    continua comunque a girare, usando quel valore come riferimento.
    """
    mancanti = [k for k, ok in stato_dipendenze().items() if not ok]
    essenziali = [k for k in mancanti if k in ("demucs", "basic_pitch")]
    if essenziali:
        raise RuntimeError(istruzioni_installazione(essenziali))

    os.makedirs(cartella_tmp, exist_ok=True)
    percorsi = separa_tracce(percorso_audio, os.path.join(cartella_tmp, "stems"))

    metro = (4, 4)   # la firma di tempo non viene ancora rilevata: si assume
                     # sempre 4/4, l'utente puo' correggerla nell'interfaccia
    bpm, battiti, primo_suono_secondi, battere_secondi, avvisi_ritmo = \
        analizza_ritmo(percorso_audio, bpm_manuale=bpm_manuale)
    anacrusi_quarti = 0.0
    battere1 = primo_suono_secondi
    if battiti or primo_suono_secondi:
        battere1, anacrusi_quarti = _primo_battere_e_anacrusi(
            primo_suono_secondi, battiti, bpm, metro,
            battere_noto=battere_secondi)

    # ORIGINE DEI TEMPI. Tutto quello che segue si misura a partire da questo
    # istante: e' lo zero della partitura. Prima era sempre il primo suono
    # rilevato, cioe' il primo rumore del file — che su un brano con
    # introduzione ambientale non ha niente a che vedere con l'inizio della
    # musica. Ora, quando il battere e' noto, l'origine e' il battere meno
    # l'eventuale anacrusi: il levare resta dentro la partitura, il rumore
    # che lo precede resta fuori.
    origine_secondi = primo_suono_secondi
    if battere_secondi is not None:
        origine_secondi = battere1 - anacrusi_quarti * 60.0 / max(20.0, bpm)
        if anacrusi_quarti > 1e-6:
            avvisi_ritmo.append(
                f"rilevata un'anacrusi di {anacrusi_quarti:.2f} quarti prima "
                "del primo battere: la prima misura e' di levare.")
        elif battere1 - primo_suono_secondi > 0.5:
            avvisi_ritmo.append(
                f"i primi {battere1 - primo_suono_secondi:.1f} secondi del "
                "file precedono il primo battere di piu' di una misura: "
                "trattati come introduzione e lasciati fuori dalla "
                "partitura, che comincia dal battere.")

    # La batteria si trascrive PRIMA delle tracce intonate, anche se poi
    # verra' usata dopo: e' l'unica che puo' dire se il battere individuato
    # cade davvero sul primo movimento della misura, e la sua risposta
    # sposta l'origine di TUTTE le tracce. Trascriverla dopo significherebbe
    # aver gia' convertito le altre con un'origine sbagliata.
    # QUALE BATTITO VALE IL QUARTO 0. Con la griglia disponibile, l'origine
    # della partitura non e' piu' solo un istante in secondi ma un battito
    # preciso: tutte le conversioni successive contano i battiti a partire da
    # quello, invece di moltiplicare i secondi per un tempo medio. E' cio'
    # che rende impossibile lo scivolamento progressivo.
    usa_griglia = bool(battiti) and len(battiti) >= 2
    indice_origine = _indice_battito(battiti, origine_secondi) \
        if usa_griglia else 0

    colpi_grezzi = trascrivi_batteria_grezza(
        percorsi["drums"], bpm,
        battiti=battiti if usa_griglia else None,
        indice_origine=indice_origine) if "drums" in percorsi else []

    if colpi_grezzi:
        # `colpi_grezzi` e' gia' in quarti riferiti all'origine quando si usa
        # la griglia; col solo bpm e' invece riferito all'inizio del file e va
        # spostato
        colpi_riferiti = colpi_grezzi if usa_griglia else _sposta_colpi(
            colpi_grezzi, origine_secondi * bpm / 60.0)
        spostamento_battere, avviso_fase = _fase_battere_da_batteria(
            colpi_riferiti, bpm, metro)
        if spostamento_battere:
            if usa_griglia:
                # spostare il battere significa scegliere un ALTRO battito
                # della griglia come quarto 0
                indice_origine = min(len(battiti) - 1,
                                     indice_origine + spostamento_battere)
                origine_secondi = battiti[indice_origine]
                colpi_grezzi = trascrivi_batteria_grezza(
                    percorsi["drums"], bpm, battiti=battiti,
                    indice_origine=indice_origine)
            else:
                origine_secondi += spostamento_battere * 60.0 / max(20.0, bpm)
            if avviso_fase:
                avvisi_ritmo.append(avviso_fase)

    tracce_note: Dict[str, List[Nota]] = {}
    tracce_grezze: Dict[str, List[Nota]] = {}
    for nome in ("vocals", "bass", "other"):
        if nome not in percorsi:
            continue
        direzione = "alta" if nome == "vocals" else "bassa" if nome == "bass" else "alta"
        if nome == "other":
            # traccia polifonica per natura (accordi, tastiere, chitarre):
            # qui un modello polifonico e' la scelta giusta
            grezze_secondi = trascrivi_intonata(percorsi[nome], cartella_tmp)
        else:
            # voce e basso sono linee singole: si cerca UNA fondamentale per
            # volta dentro il registro dello strumento, invece di chiedere a
            # un modello polifonico tutte le altezze e poi buttarne via
            registro = "voce" if nome == "vocals" else "basso"
            grezze_secondi, motivo = trascrivi_monofonica(percorsi[nome],
                                                          registro)
            if not grezze_secondi:
                # ricaduta sul percorso storico: meglio una trascrizione
                # imperfetta che una traccia vuota
                grezze_secondi = trascrivi_intonata(percorsi[nome],
                                                     cartella_tmp)
                grezze_secondi = riduci_a_monofonica(grezze_secondi,
                                                     preferisci=direzione)
                if motivo:
                    avvisi_ritmo.append(
                        f"traccia «{nome}»: {motivo} Il rilevatore "
                        "polifonico tende a scambiare gli armonici per note "
                        "vere, quindi qui possono comparire salti d'ottava "
                        "che nell'originale non ci sono.")
            elif motivo:
                # `pyin` ha lavorato, ma ha qualcosa da segnalare: non e' un
                # fallimento, e' diagnostica sulla qualita' della separazione
                avvisi_ritmo.append(motivo)
        # dai secondi di Basic Pitch ai quarti musicali reali, ancorati
        # all'origine della partitura (vedi sopra): e' il passaggio che
        # risponde alla domanda "dov'e' il battere iniziale" e che allinea
        # questa traccia alla stessa linea del tempo della batteria
        grezze = _secondi_a_quarti(
            grezze_secondi, bpm, origine_secondi,
            battiti=battiti if usa_griglia else None,
            indice_origine=indice_origine)
        # 'grezze' qui e' gia' dopo la riduzione a monofonica e l'aggancio al
        # battere iniziale, ma prima della quantizzazione: e' il punto giusto
        # per il debug.
        tracce_grezze[nome] = grezze
        quantizzate = quantizza_e_pulisci(grezze, griglia=griglia)
        # Ricomposizione delle note spezzate, con le soglie proprie di questa
        # traccia: il rilevatore d'altezza misura quando c'e' una
        # fondamentale riconoscibile, non quanto dura la nota, e le due cose
        # divergono in modo diverso sul canto e sul basso pizzicato.
        if nome in DURATE_PER_TRACCIA:
            unione, legatura, minima = DURATE_PER_TRACCIA[nome]
            quantizzate = ricomponi_note(quantizzate, buco_unione=unione,
                                         buco_legatura=legatura,
                                         durata_minima=minima)
        tracce_note[nome] = quantizzate

    # --- ripuliture che hanno bisogno di piu' di una traccia ---------------

    # Le altezze che il brano usa si ricavano dal BASSO: e' la traccia
    # monofonica piu' pulita, e ricavarle dalla voce sarebbe circolare —
    # proprio le stonature da togliere finirebbero per giustificarsi da sole.
    if tracce_note.get("bass"):
        # Le classi si ricavano da TUTTE le tracce intonate, non dal solo
        # basso: un basso costruito su un riff ne usa cinque o sei, e la
        # melodia puo' legittimamente uscirne. Il basso pesa comunque molto
        # perche' e' la traccia con le note piu' lunghe, e il conteggio e'
        # per durata.
        insieme: List[Nota] = []
        for chiave in ("bass", "vocals", "other"):
            insieme.extend(tracce_note.get(chiave, []))
        ammesse = classi_ammesse(insieme)
        nomi_classi = ["Do", "Do#", "Re", "Re#", "Mi", "Fa", "Fa#", "Sol",
                       "Sol#", "La", "La#", "Si"]
        avvisi_ritmo.append(
            "altezze riconosciute come portanti nel brano: "
            + ", ".join(nomi_classi[k] for k in sorted(ammesse))
            + ". Le note BREVI fuori da queste vengono riportate alla piu' "
            "vicina, perche' di solito sono intonazioni imprecise; quelle "
            "lunghe restano, perche' in un brano modale sono spesso proprio "
            "loro a definire il modo. Se manca un'altezza che il brano usa "
            "davvero, e' qui che si vede.")
        if tracce_note.get("vocals"):
            # i pesi si calcolano su TUTTE le tracce: una nota storta tende
            # verso la nota importante del brano, che puo' essere portata
            # dal basso o dagli accordi, non solo dalla voce
            voce = aggancia_alle_classi(tracce_note["vocals"], ammesse,
                                        pesi=pesi_classi(insieme))
            voce = assorbi_portamenti(voce)
            # Dopo aver riportato i portamenti all'altezza dei vicini, la
            # stessa unione di prima li fonde nella nota tenuta. Qui pero'
            # la LEGATURA va a zero, e non e' una dimenticanza: le note sono
            # gia' della lunghezza giusta, e prolungarle ancora le farebbe
            # passare oltre il segno. Misurato: con legatura la distanza
            # dalla riduzione pianistica resta 0.259, senza scende a 0.168.
            unione, _legatura, minima = DURATE_PER_TRACCIA["vocals"]
            tracce_note["vocals"] = ricomponi_note(
                voce, buco_unione=unione, buco_legatura=0.0,
                durata_minima=minima)

        # Il riff del basso si ripete: si riscrivono allo stesso modo le
        # occorrenze, per voto fra tutte
        consolidato, riscritte = consolida_riff(tracce_note["bass"])
        if riscritte:
            tracce_note["bass"] = consolidato
            avvisi_ritmo.append(
                f"riconosciuto un riff di basso ricorrente: {riscritte} "
                "occorrenze riscritte in modo uniforme, tenendo per ogni "
                "posizione la lettura data dalla maggioranza. Gli stacchi e "
                "le parti che non seguono il riff sono rimasti come "
                "rilevati.")

    # la batteria si ancora alla stessa origine delle altre tracce: se le due
    # non coincidessero, percussioni e melodia risulterebbero sfasate fra loro.
    # Con la griglia lo spostamento e' gia' stato applicato a monte, leggendo
    # gli istanti a partire dal battito d'origine.
    if not usa_griglia:
        colpi_grezzi = _sposta_colpi(colpi_grezzi,
                                     origine_secondi * bpm / 60.0)
    colpi = _quantizza_colpi(colpi_grezzi, griglia) if colpi_grezzi else []

    base = titolo or os.path.splitext(os.path.basename(percorso_audio))[0]
    risultato = costruisci_da_tracce(tracce_note, bpm, metro, colpi, titolo=base,
                                     tracce_grezze=tracce_grezze,
                                     colpi_batteria_grezzi=colpi_grezzi,
                                     anacrusi_quarti=anacrusi_quarti)
    # L'avviso sul tempo rilevato lo produce ora `analizza_ritmo`, che e'
    # l'unico punto a sapere QUALE motore (beat_this o librosa) ha prodotto
    # stima — informazione utile a chi legge il report, perche' i due hanno
    # affidabilita' diversa. Qui non se ne aggiunge un secondo: sarebbe un
    # doppione, e direbbe meno di quello che sostituisce.
    risultato.avvisi = avvisi_ritmo + risultato.avvisi
    return risultato


# --------------------------------------------------------------------------
# Esportazione di debug: le tracce separate, gia' quantizzate, in MusicXML
# --------------------------------------------------------------------------


def _parte_da_note(id_: str, nome: str, abbrev: str, note: List[Nota],
                   fine: float, chiave: str = "G", trasposizione: int = 0,
                   monofonico: bool = True, percussione: bool = False
                   ) -> Parte:
    """
    Una traccia separata diventa una `Parte` a rigo singolo: un evento per
    ogni attacco distinto, pause a riempire il resto. E' deliberatamente
    un rigo per traccia, senza dividere in strumenti dell'orchestra: qui
    l'obiettivo e' vedere che cosa la separazione e la trascrizione hanno
    prodotto DAVVERO, prima che il motore ci metta mano.

    Gli istanti vengono agganciati al piu' piccolo valore che la notazione
    sa scrivere — un trentaduesimo, un ottavo di quarto — prima di costruire
    gli eventi, non dopo: un arrotondamento fatto nota per nota,
    indipendentemente, puo' far si' che la somma delle durate di una misura
    non torni piu' esatta al totale dichiarato, oppure che l'incisore scarti
    in silenzio la frazione di tick che non sa scomporre in una figura
    ritmica valida (il motore di esportazione lavora su un catalogo chiuso
    di valori — intero, meta', quarto... fino al trentaduesimo e alle
    terzine — e un resto che non e' un loro multiplo va perso). Agganciando
    prima a un multiplo del trentaduesimo, e derivando le durate per
    differenza fra attacchi consecutivi, la somma torna sempre esatta e non
    si perde nessun tick. E' un aggancio finissimo — 1/8 di quarto, circa 60
    millisecondi a 120 bpm — non la quantizzazione a griglia (0,25 di quarto
    di default) che questa vista serve a bypassare: la differenza fra le due
    resta ben visibile.
    """
    from .esportatore import DIV as _DIV_NOTAZIONE
    _GRANA = 3   # tick: il valore piu' piccolo che il catalogo ritmico sa
                # scrivere (un trentaduesimo); qualunque multiplo si
                # scompone sempre in modo esatto, senza resti scartati

    def _tick(t: float) -> float:
        ticks_grezzi = round(t * _DIV_NOTAZIONE / _GRANA) * _GRANA
        return ticks_grezzi / _DIV_NOTAZIONE

    fine = _tick(max(fine, _GRANA / _DIV_NOTAZIONE))
    note = [Nota(midi=n.midi, inizio=_tick(n.inizio),
                 durata=max(_GRANA / _DIV_NOTAZIONE,
                            _tick(n.fine) - _tick(n.inizio)),
                 rigo=n.rigo)
           for n in note]

    parte = Parte(id=id_, nome=nome, abbrev=abbrev, strumento="pianoforte",
                 chiave=chiave, trasposizione=trasposizione,
                 monofonico=monofonico, programma_midi=0, righi=1)
    if percussione:
        parte.chiave = "percussion"

    if not note:
        parte.eventi = [Evento(inizio=0.0, durata=max(fine, 1.0), altezze=[])]
        return parte

    attacchi = sorted({round(n.inizio, 6) for n in note if n.inizio < fine - 1e-6})
    eventi: List[Evento] = []
    t_prec = 0.0
    for i, t in enumerate(attacchi):
        if t - t_prec > 1e-6:
            eventi.append(Evento(inizio=t_prec, durata=t - t_prec, altezze=[]))
        gruppo = [n for n in note if abs(n.inizio - t) < 1e-6]
        prossimo = attacchi[i + 1] if i + 1 < len(attacchi) else fine
        durata = max(_GRANA / _DIV_NOTAZIONE,
                    min(max(n.durata for n in gruppo), prossimo - t))
        eventi.append(Evento(inizio=t, durata=durata,
                             altezze=sorted({n.midi for n in gruppo})))
        t_prec = t + durata
    # la coda va fino alla lunghezza DICHIARATA del brano (multiplo esatto di
    # misure), non solo fino all'ultima nota: altrimenti il totale della
    # parte resta piu' corto di quello che la partitura dichiara nelle
    # misure, e la metrica non torna piu' su nessuna delle parti.
    if fine - t_prec > 1e-6:
        eventi.append(Evento(inizio=t_prec, durata=fine - t_prec, altezze=[]))
    parte.eventi = eventi
    return parte


def esporta_tracce_musicxml(risultato: "RisultatoMultitraccia", percorso: str,
                            titolo: Optional[str] = None,
                            quantizzate: bool = True) -> str:
    """
    Esporta le quattro tracce separate — voce, basso, batteria, resto.

    Con `quantizzate=True` (default) cosi' come sono DOPO l'aggancio alla
    griglia, pronte per l'arrangiatore. Con `quantizzate=False` cosi' come
    sono uscite dalla trascrizione (e, per voce/basso, dalla riduzione a
    monofonica), PRIMA di qualunque aggancio al tempo: gli attacchi cadono
    dove li ha sentiti la trascrizione, non sulle stanghette.

    Confrontare le due versioni e' il modo piu' diretto per capire da dove
    viene un errore: se una nota e' gia' sbagliata nella versione non
    quantizzata, il problema e' nella separazione o nella trascrizione (a
    monte); se compare solo in quella quantizzata, e' l'aggancio alla griglia
    ad aver spostato o fuso qualcosa che andava lasciato com'era.
    """
    sp = risultato.spartito
    fine = sp.durata_totale or 8.0

    if quantizzate:
        voce, basso, resto = (risultato.analisi.melodia,
                              risultato.analisi.basso,
                              risultato.analisi.figurazione)
        colpi = risultato.colpi_batteria
        sottotitolo = ("Debug: voce/basso/batteria/resto, gia' quantizzate, "
                       "prima dell'arrangiamento")
        suffisso = " - tracce separate (quantizzate)"
    else:
        voce = risultato.tracce_grezze.get("vocals", [])
        basso = risultato.tracce_grezze.get("bass", [])
        resto = risultato.tracce_grezze.get("other", [])
        colpi = risultato.colpi_batteria_grezzi
        fine = max([fine] + [n.fine for n in voce + basso + resto]
                  + [c.inizio + 1.0 for c in colpi])
        sottotitolo = ("Debug: voce/basso/batteria/resto COSI' COME SONO "
                       "USCITE dalla trascrizione, PRIMA di ogni aggancio "
                       "alla griglia. Gli attacchi non cadono sulle "
                       "stanghette: e' voluto.")
        suffisso = " - tracce separate (non quantizzate)"

    n_misure = max(1, int(fine / 4.0 + 0.999))
    lunghezza_totale = n_misure * 4.0     # multiplo esatto: e' cio' a cui
                                          # ogni parte deve arrivare, non a
                                          # 'fine' che puo' cadere a meta'
                                          # dell'ultima misura
    # se e' stata rilevata un'anacrusi la si riflette anche qui: la prima
    # misura (di levare) resta parziale, cosi' le stanghette del debug
    # corrispondono a quelle che l'arrangiatore usera' davvero
    misure: List[Misura] = []
    if sp.anacrusi > 1e-6:
        misure.append(Misura(numero=0, inizio=0.0, durata=sp.anacrusi,
                             anacrusi=True))
        resto_durata = max(0.0, lunghezza_totale - sp.anacrusi)
        n_piene = max(1, int(resto_durata / 4.0 + 0.999))
        for i in range(n_piene):
            misure.append(Misura(numero=i + 1,
                                 inizio=sp.anacrusi + i * 4.0, durata=4.0))
        lunghezza_totale = misure[-1].inizio + misure[-1].durata
    else:
        misure = [Misura(numero=i + 1, inizio=i * 4.0, durata=4.0)
                 for i in range(n_misure)]

    parti = [
        _parte_da_note("voce", "Voce (traccia separata)", "Voce", voce,
                      lunghezza_totale),
        _parte_da_note("basso", "Basso (traccia separata)", "Basso", basso,
                      lunghezza_totale, chiave="F"),
        _parte_da_note("resto", "Resto (traccia separata)", "Resto", resto,
                      lunghezza_totale, monofonico=False),
    ]

    if colpi:
        note_batteria = [Nota(midi=PERC_MIDI[c.strumento], inizio=c.inizio,
                              durata=0.2, rigo=1)
                         for c in colpi]
        parti.append(_parte_da_note("batteria", "Batteria (traccia separata)",
                                    "Batt.", note_batteria, lunghezza_totale,
                                    percussione=True))

    part = Partitura(titolo=(titolo or sp.titolo) + suffisso,
                     sottotitolo=sottotitolo, parti=parti, misure=misure,
                     bpm=sp.bpm)

    from .esportatore import esporta_musicxml
    return esporta_musicxml(part, percorso)


def leggi_smf_o_stima(percorso_wav_o_midi: str) -> Tuple[list, float, Tuple[int, int]]:
    """
    Mantenuta per compatibilita' con codice esterno che la chiamasse
    direttamente; internamente non e' piu' usata da `importa`.

    Stimava il bpm dalla sola traccia passata (spesso la batteria isolata),
    con un fallback silenzioso a 100 bpm in caso di errore: proprio quel
    silenzio ha reso difficile capire, in un caso reale, perche' il tempo
    rilevato non fosse quello giusto. `analizza_ritmo` lo sostituisce: lavora
    sul mix intero (un segnale piu' ricco, specie quando la batteria isolata
    e' debole) e restituisce sempre un avviso quando il tempo non e'
    affidabile, invece di restituire un numero plausibile ma falso.
    """
    bpm, _battiti, _primo, _battere, _avvisi = analizza_ritmo(percorso_wav_o_midi)
    return [], bpm, (4, 4)
