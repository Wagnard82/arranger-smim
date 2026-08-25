"""
MODULO 3.3 - Controllo dei limiti (Constraint Checker).

Filtri di validazione applicati alle bozze generate dall'Orchestrator:

  1. Filtro Polifonia    - fiati/archi non divisi monofonici; le note in
                           esubero passano ai divisi (Violino 2, Flauto 3...)
  2. Filtro Estensione   - ottava alzata/abbassata finche' la nota e' suonabile
  3. Filtro Ritmico      - durate compatibili col livello (no crome in 1a media)
  4. Filtro Salti        - salti massimi consentiti (non tocca la melodia)
  5. Filtro Alterazioni  - in 1a media niente note fuori tonalita'
  6. Filtro Idiomatico   - diteggiature chitarra, prima posizione archi,
                           apertura della mano al pianoforte

Ogni intervento e' registrato in `partitura.report` con il numero di misura.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from .modello import Evento, Misura, Parte, Partitura
from .strumenti import Livello, Strumento, livello, strumento

MAGGIORE = [0, 2, 4, 5, 7, 9, 11]
RESPIRO = 1.0     # una pausa di almeno un quarto separa due tratti di frase


def tratti(eventi: List[Evento]) -> List[List[Evento]]:
    """
    Spezza il flusso di una parte nei suoi tratti legati (separati da pause
    significative). Tutte le correzioni d'ottava lavorano sul TRATTO, non
    sulla singola nota: e' cio' che evita i salti dentro una scala.
    """
    fuori: List[List[Evento]] = []
    corrente: List[Evento] = []
    pausa_accumulata = 0.0
    for e in eventi:
        if e.pausa:
            pausa_accumulata += e.durata
            if pausa_accumulata >= RESPIRO - 1e-6 and corrente:
                fuori.append(corrente)
                corrente = []
            continue
        pausa_accumulata = 0.0
        corrente.append(e)
    if corrente:
        fuori.append(corrente)
    return fuori


def ottava_migliore(midis: List[int], lo: int, hi: int) -> int:
    if not midis:
        return 0
    centro = (lo + hi) / 2
    migliore, punteggio = 0, None
    for delta in (0, 12, -12, 24, -24, 36, -36):
        fuori = sum(1 for m in midis if not (lo <= m + delta <= hi))
        medio = sum(m + delta for m in midis) / len(midis)
        # a parita' di note fuori ambito si preferisce non spostare nulla
        p = (fuori, abs(delta), abs(medio - centro))
        if punteggio is None or p < punteggio:
            migliore, punteggio = delta, p
    return migliore


# --------------------------------------------------------------------------


def _misura_di(misure: List[Misura], t: float) -> str:
    for m in misure:
        if m.inizio - 1e-6 <= t < m.fine - 1e-6:
            return "levare" if m.anacrusi else str(m.numero)
    return "?"


def _tonica(misure: List[Misura]) -> int:
    fifths = misure[0].tonalita if misure else 0
    return (fifths * 7) % 12


def _scala(misure: List[Misura]) -> List[int]:
    t = _tonica(misure)
    return [(t + g) % 12 for g in MAGGIORE]


# --------------------------------------------------------------------------
# 1. Polifonia / divisi
# --------------------------------------------------------------------------


def filtro_polifonia(part: Partitura) -> None:
    gruppi: Dict[str, List[Parte]] = {}
    for p in part.parti:
        gruppi.setdefault(p.strumento, []).append(p)

    for chiave, parti in gruppi.items():
        st = strumento(chiave)
        if not st.monofonico:
            continue
        for idx, p in enumerate(parti):
            for e in p.eventi:
                if len(e.altezze) <= 1:
                    continue
                ordinate = sorted(e.altezze, reverse=True)
                # distribuisce le note in esubero sui divisi disponibili
                for j, altezza in enumerate(ordinate[1:], start=1):
                    dest = parti[idx + j] if idx + j < len(parti) else None
                    if dest is not None:
                        _inserisci(dest, Evento(inizio=e.inizio, durata=e.durata,
                                                altezze=[altezza],
                                                articolazione=e.articolazione))
                part.report.append(
                    f"[Polifonia] {p.nome}, mis. {_misura_di(part.misure, e.inizio)}: "
                    f"{len(e.altezze)} note su strumento monofonico -> ridotte a 1 "
                    f"(le altre ai divisi).")
                e.altezze = [ordinate[0]]


def _inserisci(p: Parte, nuovo: Evento) -> None:
    """Inserisce un evento sostituendo le pause corrispondenti."""
    risultato: List[Evento] = []
    inserito = False
    for e in p.eventi:
        if e.pausa and e.inizio <= nuovo.inizio + 1e-6 and e.fine >= nuovo.fine - 1e-6:
            if nuovo.inizio - e.inizio > 1e-6:
                risultato.append(Evento(inizio=e.inizio, durata=nuovo.inizio - e.inizio,
                                        altezze=[], rigo=e.rigo))
            risultato.append(nuovo)
            if e.fine - nuovo.fine > 1e-6:
                risultato.append(Evento(inizio=nuovo.fine, durata=e.fine - nuovo.fine,
                                        altezze=[], rigo=e.rigo))
            inserito = True
        else:
            risultato.append(e)
    if inserito:
        p.eventi = risultato


# --------------------------------------------------------------------------
# 2. Estensione
# --------------------------------------------------------------------------


def filtro_estensione(part: Partitura) -> None:
    """
    Porta le note nell'ambito dello strumento trasponendo d'ottava un TRATTO
    intero di frase alla volta. Correggere nota per nota fa nascere salti
    d'ottava in mezzo alle scale: e' il difetto che questa versione evita.
    """
    for p in part.parti:
        st = strumento(p.strumento)
        if st.percussione:
            continue
        lo, hi = st.ambito(part.livello)
        for rigo in sorted({e.rigo for e in p.eventi}):
            flusso = [e for e in p.eventi if e.rigo == rigo]
            for tratto in tratti(flusso):
                if any(e.letterale for e in tratto):
                    continue    # copia dell'originale: registri gia' corretti
                monodico = all(len(e.altezze) == 1 for e in tratto)
                if monodico:
                    delta = ottava_migliore([e.altezze[0] for e in tratto], lo, hi)
                    if delta:
                        part.report.append(
                            f"[Estensione] {p.nome}, mis. "
                            f"{_misura_di(part.misure, tratto[0].inizio)}: tratto "
                            f"trasposto di {delta // 12:+d} ottave per rientrare "
                            f"nell'ambito.")
                        for e in tratto:
                            e.altezze = [e.altezze[0] + delta]
                # residui (e accordi): correzione puntuale, ormai rara
                for e in tratto:
                    nuove = []
                    for midi in e.altezze:
                        orig = midi
                        while midi < lo:
                            midi += 12
                        while midi > hi:
                            midi -= 12
                        midi = max(lo, min(hi, midi))
                        if midi != orig and not monodico:
                            part.report.append(
                                f"[Estensione] {p.nome}, mis. "
                                f"{_misura_di(part.misure, e.inizio)}: nota fuori "
                                f"ambito -> trasposta d'ottava.")
                        nuove.append(midi)
                    e.altezze = sorted(set(nuove))


# --------------------------------------------------------------------------
# 3. Ritmo
# --------------------------------------------------------------------------


def _indice_misura(misure: List[Misura], t: float) -> int:
    for i, m in enumerate(misure):
        if m.inizio - 1e-6 <= t < m.fine - 1e-6:
            return i
    return -1


def filtro_ritmico(part: Partitura) -> None:
    """
    Semplifica i valori troppo brevi per il livello.
    Non fonde MAI oltre la stanghetta: il metro del brano resta intatto a
    qualunque livello didattico.
    """
    L = livello(part.livello)
    if L.durata_minima <= 0.25:
        return
    for p in part.parti:
        if p.ruolo == "melodia":
            continue          # la melodia conserva il ritmo dell'originale
        if strumento(p.strumento).percussione and part.stile == "Jazz":
            continue
        for rigo in sorted({e.rigo for e in p.eventi}):
            flusso = [e for e in p.eventi if e.rigo == rigo]
            fusi: List[Evento] = []
            for e in flusso:
                stessa_misura = (
                    fusi and _indice_misura(part.misure, fusi[-1].inizio)
                    == _indice_misura(part.misure, e.inizio))
                if fusi and stessa_misura and e.durata < L.durata_minima - 1e-6:
                    prec = fusi[-1]
                    if prec.pausa == e.pausa and prec.altezze == e.altezze:
                        prec.durata += e.durata
                        continue
                    if not e.pausa and prec.durata >= L.durata_minima:
                        # nota troppo breve: assorbita dalla precedente
                        prec.durata += e.durata
                        part.report.append(
                            f"[Ritmo] {p.nome}, mis. {_misura_di(part.misure, e.inizio)}: "
                            f"valore inferiore al minimo del livello -> semplificato.")
                        continue
                fusi.append(e)
            altri = [e for e in p.eventi if e.rigo != rigo]
            p.eventi = sorted(altri + fusi, key=lambda x: (x.rigo, x.inizio))


# --------------------------------------------------------------------------
# 4. Salti (non tocca la melodia)
# --------------------------------------------------------------------------


def filtro_salti(part: Partitura) -> None:
    """
    Riduce i salti oltre il limite del livello trasponendo d'ottava TUTTO IL
    SEGUITO del tratto, non la singola nota: spostare una nota sola crea un
    salto all'andata e uno al ritorno, cioe' proprio la frammentazione che si
    vuole evitare. La melodia non viene mai toccata.
    """
    L = livello(part.livello)
    for p in part.parti:
        if p.ruolo == "melodia" or strumento(p.strumento).percussione:
            continue
        st = strumento(p.strumento)
        lo, hi = st.ambito(part.livello)
        for rigo in sorted({e.rigo for e in p.eventi}):
            flusso = [e for e in p.eventi if e.rigo == rigo]
            for tratto in tratti(flusso):
                if any(e.letterale for e in tratto):
                    continue
                monodici = [e for e in tratto if len(e.altezze) == 1]
                i = 1
                while i < len(monodici):
                    prec = monodici[i - 1].altezze[0]
                    corrente = monodici[i].altezze[0]
                    salto = abs(corrente - prec)
                    if salto <= L.salto_massimo:
                        i += 1
                        continue
                    direzione = -12 if corrente > prec else 12
                    coda = monodici[i:]
                    delta = 0
                    while abs(corrente + delta + direzione - prec) < abs(
                            corrente + delta - prec):
                        prova = delta + direzione
                        if all(lo <= e.altezze[0] + prova <= hi for e in coda):
                            delta = prova
                        else:
                            break
                    if delta:
                        for e in coda:
                            e.altezze = [e.altezze[0] + delta]
                        part.report.append(
                            f"[Salti] {p.nome}, mis. "
                            f"{_misura_di(part.misure, monodici[i].inizio)}: salto di "
                            f"{salto} semitoni -> seguito della frase trasposto "
                            f"di {delta // 12:+d} ottave.")
                    i += 1


# --------------------------------------------------------------------------
# 5. Alterazioni
# --------------------------------------------------------------------------


def _accordo_a(part: Partitura, t: float):
    for a in part.armonia:
        if a.inizio - 1e-6 <= t < a.fine - 1e-6:
            return a
    return None


def filtro_alterazioni(part: Partitura) -> None:
    """
    In 1a media si evitano le note alterate... ma solo quelle ESTRANEE
    all'armonia. Una sensibile o una nota di un accordo alterato (tipico nelle
    modulazioni) va lasciata: ricondurla alla scala produrrebbe una nota
    sbagliata, che e' molto peggio di una nota difficile.
    """
    L = livello(part.livello)
    if L.alterazioni:
        return
    scala = _scala(part.misure)
    for p in part.parti:
        if strumento(p.strumento).percussione:
            continue
        for e in p.eventi:
            if e.pausa or e.letterale:
                continue
            nuove = []
            cambiato = False
            for midi in e.altezze:
                if midi % 12 in scala:
                    nuove.append(midi)
                    continue
                if p.ruolo == "melodia":
                    nuove.append(midi)      # la melodia resta intatta
                    continue
                acc = _accordo_a(part, e.inizio)
                if acc is not None and midi % 12 in acc.note_accordo():
                    nuove.append(midi)      # nota dell'armonia: si tiene
                    continue
                candidate = [midi - 1, midi + 1, midi - 2, midi + 2]
                scelta = next((c for c in candidate if c % 12 in scala), midi)
                nuove.append(scelta)
                cambiato = True
            if cambiato:
                part.report.append(
                    f"[Alterazioni] {p.nome}, mis. {_misura_di(part.misure, e.inizio)}: "
                    f"nota alterata non prevista in {part.livello} -> ricondotta alla tonalita'.")
            e.altezze = sorted(set(nuove))


# --------------------------------------------------------------------------
# 6. Idiomatico
# --------------------------------------------------------------------------


def diteggiatura_chitarra(altezze: List[int], capotasto_max: int = 5,
                          apertura: int = 3) -> Optional[List[int]]:
    """
    Cerca una posizione realizzabile sulle 6 corde (Mi-La-Re-Sol-Si-Mi).
    Ritorna le altezze effettivamente suonabili, o None se impossibile.
    """
    corde = [40, 45, 50, 55, 59, 64]
    pcs = {a % 12 for a in altezze}
    if not pcs:
        return None
    fondamentale = min(altezze) % 12
    migliore = None
    for base in range(0, capotasto_max + 1):
        suonate: List[int] = []
        for corda in corde:
            opzioni = [corda + f for f in range(base, base + apertura + 1)
                       if (corda + f) % 12 in pcs]
            if base > 0 and (corda % 12) in pcs:
                opzioni.append(corda)          # corda a vuoto
            if opzioni:
                suonate.append(min(opzioni))
        if len(suonate) >= 3 and {s % 12 for s in suonate} & pcs:
            radici = [x for x in suonate if x % 12 == fondamentale]
            if radici and suonate[0] % 12 != fondamentale:
                # la fondamentale deve essere la nota piu' grave dell'accordo
                suonate = [s for s in suonate if s >= min(radici)] or suonate
            elif not radici:
                continue
            if migliore is None or len(suonate) > len(migliore):
                migliore = suonate
    return migliore


def filtro_idiomatico(part: Partitura) -> None:
    L = livello(part.livello)
    for p in part.parti:
        st = strumento(p.strumento)

        # ---- chitarra: diteggiature
        if p.strumento == "chitarra":
            for e in p.eventi:
                if len(e.altezze) < 2:
                    continue
                pos = diteggiatura_chitarra(e.altezze, L.capotasto_max)
                if pos is None:
                    e.altezze = e.altezze[:1]
                    part.report.append(
                        f"[Idiomatico] {p.nome}, mis. {_misura_di(part.misure, e.inizio)}: "
                        f"accordo non diteggiabile -> ridotto alla fondamentale "
                        f"(resta la sigla).")
                else:
                    unici = sorted(set(pos))
                    limite = L.accordi_max
                    e.altezze = unici[:limite] if limite < len(unici) else unici

        # ---- archi: prima posizione e cambi di corda
        if st.famiglia == "archi" and not L.cambi_posizione and p.ruolo != "melodia":
            lo, hi = st.ambito(part.livello)
            for rigo in sorted({e.rigo for e in p.eventi}):
                flusso = [e for e in p.eventi if e.rigo == rigo]
                for tratto in tratti(flusso):
                    monodici = [e for e in tratto if len(e.altezze) == 1]
                    for i in range(1, len(monodici)):
                        prec = monodici[i - 1].altezze[0]
                        a = monodici[i].altezze[0]
                        if abs(a - prec) <= 12:
                            continue
                        direzione = -12 if a > prec else 12
                        coda = monodici[i:]
                        if all(lo <= e.altezze[0] + direzione <= hi for e in coda):
                            for e in coda:
                                e.altezze = [e.altezze[0] + direzione]
                            part.report.append(
                                f"[Idiomatico] {p.nome}, mis. "
                                f"{_misura_di(part.misure, monodici[i].inizio)}: cambio "
                                f"di corda troppo ampio -> frase riportata in "
                                f"posizione.")

        # ---- pianoforte: apertura della mano
        if p.strumento == "pianoforte":
            for e in p.eventi:
                if len(e.altezze) < 2:
                    continue
                if max(e.altezze) - min(e.altezze) > L.tastiera_max_semitoni:
                    tenute = [a for a in e.altezze
                              if a - min(e.altezze) <= L.tastiera_max_semitoni]
                    part.report.append(
                        f"[Idiomatico] {p.nome}, mis. {_misura_di(part.misure, e.inizio)}: "
                        f"apertura della mano eccessiva -> accordo ristretto.")
                    e.altezze = tenute or [min(e.altezze)]
                if len(e.altezze) > L.accordi_max and e.rigo == 1:
                    e.altezze = sorted(e.altezze)[-L.accordi_max:]


# --------------------------------------------------------------------------


def filtro_incroci(part: Partitura) -> None:
    """
    Evita le collisioni fra le due mani degli strumenti a due righi: stesse
    note suonate da entrambe (raddoppio inutile) o mano destra che scende sotto
    la sinistra. Si sposta sempre la destra, mai il basso.
    """
    for p in part.parti:
        if p.righi != 2:
            continue
        st = strumento(p.strumento)
        lo, hi = st.ambito(part.livello)
        sinistra = [e for e in p.eventi if e.rigo == 2 and not e.pausa]
        for e in (x for x in p.eventi if x.rigo == 1 and not x.pausa):
            if e.letterale:
                continue        # e' la scrittura dell'originale: si rispetta
            sotto = [s for s in sinistra
                     if s.inizio < e.fine - 1e-6 and s.fine > e.inizio + 1e-6]
            if not sotto:
                continue
            tetto = max(max(s.altezze) for s in sotto)
            if min(e.altezze) > tetto:
                continue

            # 1) si prova ad alzare la destra
            for salto in (12, 24):
                spostate = [a + salto for a in e.altezze]
                if all(lo <= a <= hi for a in spostate) and min(spostate) > tetto:
                    e.altezze = spostate
                    part.report.append(
                        f"[Incroci] {p.nome}, mis. "
                        f"{_misura_di(part.misure, e.inizio)}: mano destra sotto "
                        f"la sinistra -> alzata di {salto // 12} ottava/e.")
                    break
            else:
                # 2) altrimenti si abbassa la sinistra (tipico quando e' la
                #    destra a portare una melodia grave)
                mossa = False
                for salto in (-12, -24):
                    prova = {id(s): [a + salto for a in s.altezze] for s in sotto}
                    if all(lo <= a <= hi for v in prova.values() for a in v) and \
                            max(max(v) for v in prova.values()) < min(e.altezze):
                        for s in sotto:
                            s.altezze = prova[id(s)]
                        part.report.append(
                            f"[Incroci] {p.nome}, mis. "
                            f"{_misura_di(part.misure, e.inizio)}: mano sinistra "
                            f"abbassata di {abs(salto) // 12} ottava/e sotto la "
                            f"melodia.")
                        mossa = True
                        break
                if not mossa:
                    # 3) ultimo rimedio: via i raddoppi dalla destra
                    pulite = [a for a in e.altezze if a > tetto]
                    if pulite and pulite != e.altezze:
                        e.altezze = pulite
                        part.report.append(
                            f"[Incroci] {p.nome}, mis. "
                            f"{_misura_di(part.misure, e.inizio)}: note raddoppiate "
                            f"fra le due mani -> tolte dalla destra.")


# La destra non scende sotto il SOL sotto il pentagramma in chiave di violino
# (Sol3), la sinistra non sale sopra il Do5: oltre quei limiti la scrittura si
# riempie di tagli addizionali e le mani si accavallano.
AMBITO_MANI = {1: (55, 96), 2: (28, 72)}


def filtro_mani(part: Partitura) -> None:
    """Tiene ogni mano del pianoforte nel proprio registro."""
    for p in part.parti:
        if p.righi != 2:
            continue
        for e in p.eventi:
            if e.pausa:
                continue
            lo, hi = AMBITO_MANI.get(e.rigo, (21, 108))
            nuove = []
            fuori = False
            for midi in e.altezze:
                originale = midi
                while midi < lo:
                    midi += 12
                while midi > hi:
                    midi -= 12
                if midi != originale:
                    fuori = True
                nuove.append(max(lo, min(hi, midi)))
            if fuori:
                part.report.append(
                    f"[Mani] {p.nome}, mis. {_misura_di(part.misure, e.inizio)}: "
                    f"nota fuori dal registro della mano "
                    f"{'destra' if e.rigo == 1 else 'sinistra'} -> riportata "
                    f"nell'ottava giusta.")
            e.altezze = sorted(set(nuove))


def valida(part: Partitura) -> List[str]:
    """Esegue tutti i filtri nell'ordine corretto e restituisce il report."""
    filtro_polifonia(part)
    filtro_estensione(part)
    filtro_alterazioni(part)
    filtro_salti(part)
    filtro_idiomatico(part)
    filtro_mani(part)
    filtro_incroci(part)
    filtro_estensione(part)     # secondo passaggio dopo le modifiche idiomatiche
    filtro_ritmico(part)
    for p in part.parti:
        p.eventi.sort(key=lambda e: (e.rigo, e.inizio))
    return part.report
