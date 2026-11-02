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

In coda, `avviso_note_scomode` segnala (senza correggerle) le note scomode
per il livello, es. violino in 1a Media fuori dalle prime due applicazioni,
e `avviso_buchi_armonia` i vuoti nella disposizione dell'orchestra intera.

Ogni intervento e' registrato in `partitura.report` con il numero di misura.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from .modello import Evento, Misura, Parte, Partitura
from .lingua import etichetta_livello, nota, ottave
from .lingua import t as testo
from .strumenti import (Livello, Strumento, livello, livello_parte,
                        nome_livello_parte, strumento)

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


def _armatura_a(misure: List[Misura], t: float) -> int:
    """Armatura (circolo delle quinte) della misura che contiene `t`."""
    for m in misure:
        if m.inizio - 1e-6 <= t < m.fine - 1e-6:
            return m.tonalita
    return misure[-1].tonalita if misure else 0


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
                part.report.append(testo(
                    "polifonia", part.lingua, parte=p.nome,
                    mis=_misura_di(part.misure, e.inizio), n=len(e.altezze)))
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
        lo, hi = st.ambito(nome_livello_parte(p.livello, part.livello))
        for rigo in sorted({e.rigo for e in p.eventi}):
            flusso = [e for e in p.eventi if e.rigo == rigo]
            for tratto in tratti(flusso):
                if any(e.letterale for e in tratto):
                    continue    # copia dell'originale: registri gia' corretti
                monodico = all(len(e.altezze) == 1 for e in tratto)
                if monodico:
                    delta = ottava_migliore([e.altezze[0] for e in tratto], lo, hi)
                    if delta:
                        part.report.append(testo(
                            "estensione_tratto", part.lingua, parte=p.nome,
                            mis=_misura_di(part.misure, tratto[0].inizio),
                            ott=delta // 12))
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
                            part.report.append(testo(
                                "estensione_nota", part.lingua, parte=p.nome,
                                mis=_misura_di(part.misure, e.inizio)))
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
    # Il livello si legge PER PARTE, non una volta per tutta la partitura:
    # in una classe eterogenea il flauto che ha cominciato a ottobre e il
    # violino al terzo anno non possono avere la stessa soglia.
    for p in part.parti:
        L = livello_parte(p.livello, part.livello)
        if L.durata_minima <= 0.25:
            continue
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
                        part.report.append(testo(
                            "ritmo", part.lingua, parte=p.nome,
                            mis=_misura_di(part.misure, e.inizio)))
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
    for p in part.parti:
        L = livello_parte(p.livello, part.livello)
        if p.ruolo == "melodia" or strumento(p.strumento).percussione:
            continue
        st = strumento(p.strumento)
        lo, hi = st.ambito(nome_livello_parte(p.livello, part.livello))
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
                        part.report.append(testo(
                            "salti", part.lingua, parte=p.nome,
                            mis=_misura_di(part.misure, monodici[i].inizio),
                            salto=salto, ott=delta // 12))
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
    scala = _scala(part.misure)
    for p in part.parti:
        L = livello_parte(p.livello, part.livello)
        if L.alterazioni:
            continue
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
                part.report.append(testo(
                    "alterazioni", part.lingua, parte=p.nome,
                    mis=_misura_di(part.misure, e.inizio),
                    livello=etichetta_livello(
                        nome_livello_parte(p.livello, part.livello),
                        part.lingua, breve=True)))
            e.altezze = sorted(set(nuove))


# Una nota dell'originale "conta" per il controllo dei semitoni se non e'
# una nota di passaggio: le crome veloci della melodia sfiorano di semitono
# qualunque accordo, ed e' normale.
SEMITONO_DURATA_MINIMA = 0.5


def filtro_semitoni(part: Partitura, originale: Optional[List] = None) -> None:
    """
    Le note SCRITTE dall'arrangiatore non devono stare a un semitono (o a una
    nona minore) da una nota che nell'originale suona nello stesso momento.
    Succede quando la sigla del file dice una cosa e il pianoforte un'altra:
    Sib/Do scritto, Do-Mi-Sol-Sib suonato; il Fa della sigla, dato a un
    flauto, cade sopra il Mi del pianoforte. Nell'originale quell'attrito non
    c'e'.

    La nota si sposta di un semitono o di un tono verso una nota che non
    stride con nessuna di quelle che suonano, preferendo una nota che
    l'originale suona davvero (Fa -> Mi). Restano intatte la melodia, il
    materiale `letterale` e le note che l'originale stesso suona in quel
    punto: in un Do maj7 scritto e suonato il Si contro il Do e' voluto.
    """
    if not originale:
        return
    lunghe = [n for n in originale if n.durata >= SEMITONO_DURATA_MINIMA - 1e-6]
    for p in part.parti:
        if p.ruolo == "melodia" or strumento(p.strumento).percussione:
            continue
        misure: List[str] = []
        spostate = 0
        for e in p.eventi:
            if e.pausa or e.letterale:
                continue
            fine = e.inizio + e.durata
            sonanti = {n.midi % 12 for n in lunghe
                       if min(n.fine, fine) - max(n.inizio, e.inizio)
                       >= 0.5 * min(n.durata, e.durata) - 1e-6}
            if not sonanti:
                continue

            def stride(m: int) -> bool:
                return m % 12 not in sonanti and any(
                    (m - pc) % 12 in (1, 11) for pc in sonanti)

            nuove = []
            for midi in e.altezze:
                if not stride(midi):
                    nuove.append(midi)
                    continue
                candidate = [c for c in (midi - 1, midi + 1, midi - 2, midi + 2)
                             if not stride(c)]
                candidate.sort(key=lambda c: (c % 12 not in sonanti,
                                              abs(c - midi), c))
                if candidate:
                    nuove.append(candidate[0])
                    spostate += 1
                    mis = _misura_di(part.misure, e.inizio)
                    if mis not in misure:
                        misure.append(mis)
                else:
                    nuove.append(midi)
            e.altezze = sorted(set(nuove))
        if spostate:
            part.report.append(testo("semitoni", part.lingua, parte=p.nome,
                                     mis=", ".join(misure), n=spostate))


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
    for p in part.parti:
        L = livello_parte(p.livello, part.livello)
        st = strumento(p.strumento)

        # ---- chitarra: diteggiature
        if p.strumento == "chitarra":
            for e in p.eventi:
                if len(e.altezze) < 2:
                    continue
                pos = diteggiatura_chitarra(e.altezze, L.capotasto_max)
                if pos is None:
                    e.altezze = e.altezze[:1]
                    part.report.append(testo(
                        "accordo_non_diteggiabile", part.lingua, parte=p.nome,
                        mis=_misura_di(part.misure, e.inizio)))
                else:
                    unici = sorted(set(pos))
                    limite = L.accordi_max
                    e.altezze = unici[:limite] if limite < len(unici) else unici

        # ---- archi: prima posizione e cambi di corda
        if st.famiglia == "archi" and not L.cambi_posizione and p.ruolo != "melodia":
            lo, hi = st.ambito(nome_livello_parte(p.livello, part.livello))
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
                            part.report.append(testo(
                                "cambio_corda", part.lingua, parte=p.nome,
                                mis=_misura_di(part.misure, monodici[i].inizio)))

        # ---- pianoforte: apertura della mano
        if p.strumento == "pianoforte":
            for e in p.eventi:
                if len(e.altezze) < 2:
                    continue
                if max(e.altezze) - min(e.altezze) > L.tastiera_max_semitoni:
                    tenute = [a for a in e.altezze
                              if a - min(e.altezze) <= L.tastiera_max_semitoni]
                    part.report.append(testo(
                        "apertura_mano", part.lingua, parte=p.nome,
                        mis=_misura_di(part.misure, e.inizio)))
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
        lo, hi = st.ambito(nome_livello_parte(p.livello, part.livello))
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
                    part.report.append(testo(
                        "incrocio_destra", part.lingua, parte=p.nome,
                        mis=_misura_di(part.misure, e.inizio),
                        ottave=ottave(salto // 12, part.lingua)))
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
                        part.report.append(testo(
                            "incrocio_sinistra", part.lingua, parte=p.nome,
                            mis=_misura_di(part.misure, e.inizio),
                            ottave=ottave(abs(salto) // 12, part.lingua)))
                        mossa = True
                        break
                if not mossa:
                    # 3) ultimo rimedio: via i raddoppi dalla destra
                    pulite = [a for a in e.altezze if a > tetto]
                    if pulite and pulite != e.altezze:
                        e.altezze = pulite
                        part.report.append(testo(
                            "incrocio_raddoppi", part.lingua, parte=p.nome,
                            mis=_misura_di(part.misure, e.inizio)))


# La destra non scende sotto il SOL sotto il pentagramma in chiave di violino
# (Sol3), la sinistra non sale sopra il MI sopra il pentagramma in chiave di
# basso (Mi4): oltre quei limiti la scrittura si
# riempie di tagli addizionali e le mani si accavallano.
AMBITO_MANI = {1: (55, 96), 2: (28, 64)}


def filtro_mani(part: Partitura) -> None:
    """
    Tiene ogni mano del pianoforte nel proprio registro.

    Il materiale copiato dall'originale (`letterale`) non si tocca: se il
    pianista ha scritto un Fa4 alla sinistra (Cinema Paradiso) o un Re3 alla
    destra (Dune), e' la sua scrittura, e riportarlo d'ottava spezza la
    figura. I limiti valgono per cio' che genera il motore.
    """
    for p in part.parti:
        if p.righi != 2:
            continue
        for e in p.eventi:
            if e.pausa or e.letterale:
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
                part.report.append(testo(
                    "mani_registro", part.lingua, parte=p.nome,
                    mis=_misura_di(part.misure, e.inizio),
                    mano=testo("mano_destra" if e.rigo == 1 else "mano_sinistra",
                               part.lingua)))
            e.altezze = sorted(set(nuove))


def filtro_divisi(part: Partitura) -> None:
    """
    I leggii successivi al primo devono essere PIU' FACILI e non suonare mai
    sopra il primo.

    In una sezione scolastica il secondo e il terzo leggio sono quasi sempre
    gli allievi meno avanti: se scrivi loro una parte piu' acuta e piu' mossa
    della prima, in prova non regge. Quindi: niente note sopra il compagno di
    sezione che li precede, e valori ritmici piu' larghi.
    """
    gruppi: Dict[str, List[Parte]] = {}
    for p in part.parti:
        gruppi.setdefault(p.strumento, []).append(p)

    for chiave, parti in gruppi.items():
        if len(parti) < 2:
            continue
        st = strumento(chiave)
        if st.percussione:
            continue
        parti.sort(key=lambda p: p.variante)

        for indice in range(1, len(parti)):
            sotto = parti[indice]
            sopra = parti[indice - 1]
            # Il livello e' quello della parte SOTTO, cioe' del leggio meno
            # avanti: e' lui che deve poter eseguire. Se il professore gli ha
            # assegnato un livello proprio e' quello che conta, non quello
            # della sezione ne' quello del primo leggio.
            L_sotto = livello_parte(sotto.livello, part.livello)
            lo, hi = st.ambito(nome_livello_parte(sotto.livello,
                                                  part.livello))
            # Pianoforte 1 e 2 sono due strumenti distinti: possono
            # incrociarsi, conta solo che non si incrocino le mani dello
            # stesso pianoforte (filtro_incroci). Confrontati, la destra del
            # secondo finiva schiacciata su una nota ribattuta sotto la cima
            # del primo.
            if st.chiave != "pianoforte":
                _sotto_il_compagno(part, sotto, sopra, lo, hi)
            if sotto.ruolo != "melodia":
                _semplifica_ritmo(part, sotto, L_sotto.durata_minima * 2)


def _sotto_il_compagno(part: Partitura, sotto: Parte, sopra: Parte,
                       lo: int, hi: int) -> None:
    """Abbassa gli eventi di `sotto` che suonano sopra `sopra`."""
    riferimenti = [e for e in sopra.eventi if not e.pausa]
    corretti = 0
    for e in sotto.eventi:
        if e.pausa:
            continue
        simultanei = [r for r in riferimenti
                      if r.inizio < e.fine - 1e-6 and r.fine > e.inizio + 1e-6]
        if not simultanei:
            continue
        tetto = max(max(r.altezze) for r in simultanei)
        if max(e.altezze) <= tetto:
            continue
        nuove = list(e.altezze)
        while max(nuove) > tetto and min(nuove) - 12 >= lo:
            nuove = [a - 12 for a in nuove]
        nuove = [min(a, tetto) for a in nuove]
        if nuove != e.altezze:
            e.altezze = sorted(set(max(lo, a) for a in nuove))
            corretti += 1
    if corretti:
        part.report.append(testo("divisi_sopra", part.lingua, parte=sotto.nome,
                                 n=corretti, sopra=sopra.nome))


def _semplifica_ritmo(part: Partitura, p: Parte, minimo: float) -> None:
    """Allarga i valori troppo brevi per un leggio secondario."""
    if minimo <= 0:
        return
    semplificati = 0
    for rigo in sorted({e.rigo for e in p.eventi}):
        flusso = [e for e in p.eventi if e.rigo == rigo]
        fusi: List[Evento] = []
        for e in flusso:
            if (fusi and e.durata < minimo - 1e-6 and not e.letterale
                    and _stessa_misura(part, fusi[-1], e)):
                prec = fusi[-1]
                if prec.pausa == e.pausa and prec.altezze == e.altezze:
                    prec.durata += e.durata
                    continue
                if not e.pausa and prec.durata >= minimo:
                    prec.durata += e.durata
                    semplificati += 1
                    continue
            fusi.append(e)
        altri = [e for e in p.eventi if e.rigo != rigo]
        p.eventi = sorted(altri + fusi, key=lambda x: (x.rigo, x.inizio))
    if semplificati:
        part.report.append(testo("divisi_ritmo", part.lingua, parte=p.nome,
                                 n=semplificati))


def _stessa_misura(part: Partitura, a: Evento, b: Evento) -> bool:
    return _indice_misura(part.misure, a.inizio) == _indice_misura(part.misure,
                                                                   b.inizio)


def filtro_respiro(part: Partitura) -> None:
    """
    I fiati devono respirare.

    Due limiti, entrambi necessari: nessuna nota tenuta oltre il massimo del
    livello, e nessun tratto suonato di fila oltre quel massimo. Un ragazzo di
    prima media che trova una legatura di otto battute non la esegue: si ferma
    dove capita, e la sezione va fuori insieme.
    """
    respiro = 0.5

    for p in part.parti:
        st = strumento(p.strumento)
        if st.famiglia not in ("fiati", "ottoni"):
            continue
        # Il fiato si misura sul singolo esecutore: e' la piu' personale
        # delle capacita', e in una classe eterogenea due flauti possono
        # averla molto diversa.
        limite = livello_parte(p.livello, part.livello).fiato_max
        if limite <= 0:
            continue
        nuovi: List[Evento] = []
        suonato = 0.0
        accorciate = 0
        for e in sorted(p.eventi, key=lambda x: x.inizio):
            if e.pausa:
                suonato = 0.0
                nuovi.append(e)
                continue

            # 1) nota singola troppo lunga: si accorcia e si apre il respiro
            if e.durata > limite + 1e-6:
                tenuta = max(respiro, limite - respiro)
                nuovi.append(Evento(inizio=e.inizio, durata=tenuta,
                                    altezze=list(e.altezze),
                                    articolazione=e.articolazione,
                                    dinamica=e.dinamica, sigla=e.sigla,
                                    rigo=e.rigo))
                nuovi.append(Evento(inizio=e.inizio + tenuta,
                                    durata=e.durata - tenuta, altezze=[],
                                    rigo=e.rigo))
                accorciate += 1
                suonato = 0.0
                continue

            # 2) troppo tempo di fila senza staccare. Si accorcia solo se
            #    quello che resta e' ancora un valore leggibile al livello:
            #    meglio una frase un filo piu' lunga di una croma isolata in
            #    prima media.
            if suonato + e.durata > limite + 1e-6 and e.durata <= respiro:
                # troppo corta per essere accorciata: diventa lei il respiro.
                # Perdere una nota d'accompagnamento e' meglio di una sezione
                # di fiati che va fuori a meta' frase.
                if p.ruolo != "melodia":
                    nuovi.append(Evento(inizio=e.inizio, durata=e.durata,
                                        altezze=[], rigo=e.rigo))
                    accorciate += 1
                    suonato = 0.0
                    continue
            # per il respiro si accetta un valore piu' breve del minimo del
            # livello: "semiminima + pausa di croma" si legge benissimo, ed e'
            # esattamente cio' che il fiato fa da solo per prendere aria
            if (suonato + e.durata > limite + 1e-6
                    and e.durata - respiro >= 0.25 - 1e-6):
                nuovi.append(Evento(inizio=e.inizio, durata=e.durata - respiro,
                                    altezze=list(e.altezze),
                                    articolazione=e.articolazione,
                                    dinamica=e.dinamica, sigla=e.sigla,
                                    rigo=e.rigo))
                nuovi.append(Evento(inizio=e.fine - respiro, durata=respiro,
                                    altezze=[], rigo=e.rigo))
                accorciate += 1
                suonato = 0.0
                continue

            if suonato + e.durata > limite * 1.5 and p.ruolo != "melodia":
                # ultima risorsa: si sacrifica questa nota per far respirare
                nuovi.append(Evento(inizio=e.inizio, durata=e.durata,
                                    altezze=[], rigo=e.rigo))
                accorciate += 1
                suonato = 0.0
                continue
            suonato += e.durata
            nuovi.append(e)
        p.eventi = sorted(nuovi, key=lambda x: (x.rigo, x.inizio))
        if accorciate:
            part.report.append(testo("respiro", part.lingua, parte=p.nome,
                                     n=accorciate, limite=limite))


def avviso_note_scomode(part: Partitura) -> None:
    """
    Segnala le note che stanno nell'estensione ma sono scomode a quel livello
    (per il violino in 1a Media: 1o dito basso e 3o dito alto, che non fanno
    parte della prima e seconda applicazione). Solo un avviso: le note NON si
    cambiano, nemmeno fuori dalla melodia, finche' la regola non e'
    confermata dai docenti. Vale anche per il materiale letterale, proprio
    perche' e' quello che i filtri non toccano.
    """
    for p in part.parti:
        st = strumento(p.strumento)
        chiave_liv = nome_livello_parte(p.livello, part.livello)
        scomode = set(st.note_scomode.get(chiave_liv, ()))
        if not scomode:
            continue
        trovate = [(e, a) for e in p.eventi if not e.pausa
                   for a in e.altezze if a in scomode]
        if not trovate:
            continue
        misure: List[str] = []
        nomi: Dict[str, int] = {}
        for e, a in trovate:
            m = _misura_di(part.misure, e.inizio)
            if m not in misure:
                misure.append(m)
            # il nome segue l'armatura della misura: Sib4 in Fa maggiore,
            # La#4 in Si maggiore (e nei toni senza alterazioni)
            nomi.setdefault(nota(a, part.lingua,
                                 bemolli=_armatura_a(part.misure, e.inizio) < 0), a)
        elenco = ", ".join(misure[:8]) + (", ..." if len(misure) > 8 else "")
        note = ", ".join(sorted(nomi, key=lambda n: (nomi[n], n)))
        part.report.append(testo(
            "note_scomode", part.lingua, parte=p.nome, n=len(trovate),
            livello=etichetta_livello(chiave_liv, part.lingua, breve=True),
            note=note, misure=elenco))


# Buchi nell'armonia (Rimskij-Korsakov, cap. III: disposizione larga in
# basso e stretta in alto, niente vuoti fra le voci). In semitoni.
BUCO_BASSO = 19     # dal basso alla voce sopra: oltre un'ottava e una quinta
BUCO_CENTRO = 12    # fra due voci superiori vicine: oltre un'ottava
PIANO = ("ppp", "pp", "p")


def _dinamica_a(p: Parte, t: float) -> Optional[str]:
    """Ultimo segno dinamico della parte prima di `t` (None se non ce n'e')."""
    segnati = [e for e in p.eventi if e.dinamica and e.inizio <= t + 1e-6]
    return max(segnati, key=lambda e: e.inizio).dinamica if segnati else None


def _parti_armonia(part: Partitura) -> List[Parte]:
    # glockenspiel e metallofono sono colore, non voci dell'armonia: un loro
    # suono isolato in acuto non e' un buco (e le percussioni non hanno altezza)
    return [p for p in part.parti
            if strumento(p.strumento).famiglia != "percussioni"]


def _battiti(m: Misura) -> List[float]:
    return [m.inizio + k for k in range(int(round(m.durata)) or 1)]


def _buchi_al_battito(parti: List[Parte], t: float) -> Dict[str, Tuple[int, int]]:
    """
    Buchi nella disposizione al battito `t`: {"basso": (grave, acuta)} se il
    basso e' staccato dalla voce sopra, {"centro": (grave, acuta)} se fra due
    voci superiori vicine c'e' un vuoto. Nel piano non si segnala niente.
    """
    suonano = [(p, a) for p in parti for e in p.eventi
               if not e.pausa and e.inizio - 1e-6 <= t < e.fine - 1e-6
               for a in e.altezze]
    altezze = sorted({a for _, a in suonano})
    if len(altezze) < 2:
        return {}
    if all(_dinamica_a(p, t) in PIANO for p in {id(p): p for p, _ in suonano}.values()):
        return {}
    # il basso raddoppiato all'ottava sotto resta UNA voce: si parte dalla
    # nota piu' acuta del gruppo
    k = 0
    while k + 1 < len(altezze) and altezze[k + 1] - altezze[k] == 12:
        k += 1
    if k + 1 >= len(altezze):
        return {}
    buchi: Dict[str, Tuple[int, int]] = {}
    if altezze[k + 1] - altezze[k] > BUCO_BASSO:
        buchi["basso"] = (altezze[k], altezze[k + 1])
    for x, y in zip(altezze[k + 1:], altezze[k + 2:]):
        if y - x > BUCO_CENTRO:
            buchi["centro"] = (x, y)
            break
    return buchi


def _buchi_misura(parti: List[Parte], m: Misura) -> Dict[str, Tuple[int, int]]:
    """Buchi della misura: contano solo se ci sono in almeno meta' dei
    battiti (le note di passaggio non bastano). Ritorna un esempio per tipo."""
    battiti = _battiti(m)
    conti: Dict[str, int] = {}
    esempio: Dict[str, Tuple[int, int]] = {}
    for t in battiti:
        for tipo, coppia in _buchi_al_battito(parti, t).items():
            conti[tipo] = conti.get(tipo, 0) + 1
            esempio.setdefault(tipo, coppia)
    return {tipo: esempio[tipo] for tipo, n in conti.items()
            if n * 2 >= len(battiti)}


def _battiti_con_buchi(parti: List[Parte], misure: List[Misura]) -> int:
    """Quanti (battito, tipo di buco) ci sono in queste misure: la misura
    della qualita' della disposizione usata dalla correzione."""
    return sum(len(_buchi_al_battito(parti, t))
               for m in misure for t in _battiti(m))


def _melodici(eventi: List[Evento], melodia: List) -> bool:
    """True se gli eventi seguono la melodia (raddoppio): la maggior parte
    suona la stessa nota, a meno dell'ottava, della melodia in quel momento."""
    if not eventi or not melodia:
        return False
    uguali = 0
    for e in eventi:
        n = next((n for n in melodia
                  if n.inizio - 1e-6 <= e.inizio < n.inizio + n.durata - 1e-6), None)
        if n is not None and any(a % 12 == n.midi % 12 for a in e.altezze):
            uguali += 1
    return uguali * 5 >= len(eventi) * 3      # almeno il 60%


def _prova_spostamento(part: Partitura, parti: List[Parte], p: Parte,
                       a: float, b: float, melodia: List) -> Optional[List[Evento]]:
    """
    Eventi di `p` fra `a` e `b` se si possono abbassare di un'ottava senza
    violare le regole; altrimenti None. Si sposta solo l'accompagnamento:
    niente melodia (ne' raddoppi), niente materiale letterale, niente
    pianoforte (le mani hanno i loro filtri).
    """
    if p.ruolo == "melodia" or p.righi > 1:
        return None
    st = strumento(p.strumento)
    eventi = [e for e in p.eventi if not e.pausa and a - 1e-6 <= e.inizio < b - 1e-6]
    if not eventi or any(e.letterale for e in eventi) or _melodici(eventi, melodia):
        return None
    chiave_liv = nome_livello_parte(p.livello, part.livello)
    lo, hi = st.ambito(chiave_liv)
    if any(x - 12 < lo for e in eventi for x in e.altezze):
        return None
    for e in eventi:
        nuova_min = min(e.altezze) - 12
        nuova_max = max(e.altezze) - 12
        altri = [x for q in parti if q is not p for f in q.eventi
                 if not f.pausa and f.inizio - 1e-6 <= e.inizio < f.fine - 1e-6
                 for x in f.altezze]
        # non deve diventare il basso
        if not altri or nuova_min <= min(altri):
            return None
        # i leggii successivi dello stesso strumento non salgono sopra
        dopo = False
        for q in parti:
            if q is p:
                dopo = True
                continue
            if not dopo or q.strumento != p.strumento:
                continue
            sopra = [x for f in q.eventi if not f.pausa
                     and f.inizio - 1e-6 <= e.inizio < f.fine - 1e-6 for x in f.altezze]
            if sopra and max(sopra) > nuova_max:
                return None
    # salti d'ingresso e d'uscita entro il limite del livello
    L = livello_parte(p.livello, part.livello)
    prima = [e for e in p.eventi if not e.pausa and e.fine <= a + 1e-6]
    dopo_ev = [e for e in p.eventi if not e.pausa and e.inizio >= b - 1e-6]
    if prima and abs(max(prima[-1].altezze) - (max(eventi[0].altezze) - 12)) > L.salto_massimo:
        return None
    if dopo_ev and abs(max(dopo_ev[0].altezze) - (max(eventi[-1].altezze) - 12)) > L.salto_massimo:
        return None
    return eventi


def _nota_per_la_sinistra(acc, basso: int, apertura: int, tetto: int) -> Optional[int]:
    """
    Nota dell'accordo da aggiungere sopra il basso della sinistra: la piu'
    alta che sta nella mano. Prima la fondamentale o la quinta, poi la terza;
    mai la settima (va risolta) ne' un raddoppio del basso (Rimskij: il basso
    dei rivolti non si raddoppia nelle voci superiori).
    """
    if acc is None:
        return None
    pcs = acc.note_accordo()
    fond, terza = pcs[0], pcs[1]
    quinta = pcs[2] if len(pcs) > 2 else None
    for scelta in ([fond, quinta], [terza]):
        ammesse = {pc for pc in scelta if pc is not None and pc != basso % 12}
        candidate = [x for x in range(basso + 3, min(basso + apertura, tetto) + 1)
                     if x % 12 in ammesse]
        if candidate:
            return max(candidate)
    return None


def _riempi_con_sinistra(part: Partitura, parti: List[Parte],
                         blocco: List[Misura], melodia: List) -> Optional[Parte]:
    """
    Riempie il buco sopra il basso con la sinistra del pianoforte: a ogni
    accordo della sinistra si aggiunge una nota dell'accordo entro
    l'apertura della mano del livello (una quinta, una sesta; la decima non
    entra nella mano ai nostri livelli). Si tiene solo se i buchi calano.
    """
    a, b = blocco[0].inizio, blocco[-1].fine
    prima = _battiti_con_buchi(parti, blocco)
    for p in parti:
        if p.strumento != "pianoforte" or p.righi != 2 or p.ruolo == "melodia":
            continue
        L = livello_parte(p.livello, part.livello)
        sinistra = [e for e in p.eventi if e.rigo == 2 and not e.pausa
                    and a - 1e-6 <= e.inizio < b - 1e-6]
        if not sinistra or any(e.letterale for e in sinistra) \
                or _melodici(sinistra, melodia):
            continue
        aggiunte = []
        for e in sinistra:
            if len(e.altezze) >= L.accordi_max:
                continue
            destra = [x for f in p.eventi if f.rigo == 1 and not f.pausa
                      and f.inizio - 1e-6 <= e.inizio < f.fine - 1e-6 for x in f.altezze]
            tetto = min([AMBITO_MANI[2][1]] + [x - 1 for x in destra])
            nuova = _nota_per_la_sinistra(_accordo_a(part, e.inizio), min(e.altezze),
                                          L.tastiera_max_semitoni, tetto)
            if nuova is not None and nuova not in e.altezze:
                aggiunte.append((e, list(e.altezze)))
                e.altezze = sorted(e.altezze + [nuova])
        if aggiunte and _battiti_con_buchi(parti, blocco) < prima:
            return p
        for e, vecchie in aggiunte:
            e.altezze = vecchie
    return None


def correggi_buchi_armonia(part: Partitura, melodia: Optional[List] = None) -> None:
    """
    Riempie i buchi della disposizione (vedi `_buchi_al_battito`) abbassando
    di un'ottava una voce d'accompagnamento che sta sopra il buco, per un
    blocco intero di misure consecutive: spostarla misura per misura
    creerebbe salti d'ottava a ogni stanghetta.

    Si abbassa e non si alza perche' cosi' i leggii secondari non superano
    mai il primo; il basso non si alza, perche' toglierebbe profondita' (per
    Rimskij-Korsakov il basso si raddoppia sotto, e si riempie il mezzo).
    Fra i candidati si sceglie quello che toglie piu' buchi; al massimo due
    spostamenti per blocco. La melodia e i suoi raddoppi non si toccano.

    Dove il basso resta staccato anche dopo, prova la sinistra del pianoforte
    (vedi `_riempi_con_sinistra`).
    """
    melodia = melodia or []
    parti = _parti_armonia(part)
    for blocco in _blocchi(part, [m for m in part.misure if _buchi_misura(parti, m)]):
        a, b = blocco[0].inizio, blocco[-1].fine
        for _ in range(2):
            prima = _battiti_con_buchi(parti, blocco)
            if not prima:
                break
            migliore = None
            for p in parti:
                eventi = _prova_spostamento(part, parti, p, a, b, melodia)
                if eventi is None:
                    continue
                for e in eventi:
                    e.altezze = [x - 12 for x in e.altezze]
                dopo = _battiti_con_buchi(parti, blocco)
                for e in eventi:
                    e.altezze = [x + 12 for x in e.altezze]
                if dopo < prima and (migliore is None or dopo < migliore[0]):
                    migliore = (dopo, p, eventi)
            if migliore is None:
                break
            _, p, eventi = migliore
            for e in eventi:
                e.altezze = [x - 12 for x in e.altezze]
            part.report.append(testo(
                "buco_riempito", part.lingua, parte=p.nome,
                misure=_intervallo_misure(part, blocco)))

    # poi, dove il basso resta staccato, la sinistra del pianoforte aggiunge
    # una nota dell'accordo sopra il basso
    for blocco in _blocchi(part, [m for m in part.misure
                                  if "basso" in _buchi_misura(parti, m)]):
        p = _riempi_con_sinistra(part, parti, blocco, melodia)
        if p is not None:
            part.report.append(testo(
                "buco_sinistra", part.lingua, parte=p.nome,
                misure=_intervallo_misure(part, blocco)))


def _blocchi(part: Partitura, misure: List[Misura]) -> List[List[Misura]]:
    """Raggruppa misure consecutive."""
    blocchi: List[List[Misura]] = []
    for m in misure:
        if blocchi and abs(blocchi[-1][-1].fine - m.inizio) < 1e-6:
            blocchi[-1].append(m)
        else:
            blocchi.append([m])
    return blocchi


def _intervallo_misure(part: Partitura, blocco: List[Misura]) -> str:
    misure = [_misura_di(part.misure, m.inizio) for m in blocco]
    return misure[0] if len(misure) == 1 else f"{misure[0]}-{misure[-1]}"


def avviso_buchi_armonia(part: Partitura) -> None:
    """
    Segnala le misure in cui l'insieme suona ancora «vuoto» (dopo
    `correggi_buchi_armonia`): il basso troppo lontano dalla voce sopra, o un
    vuoto di oltre un'ottava fra le voci superiori. Si guarda l'orchestra
    intera, battito per battito, perche' ogni parte dispone i suoi accordi per
    conto proprio. Solo un avviso: nessuna nota cambia.

    Una misura e' segnalata quando il buco c'e' in almeno meta' dei battiti.
    Nel piano i vuoti sono tollerati: si salta il battito se tutte le parti
    che suonano sono in p, pp o ppp.
    """
    parti = _parti_armonia(part)
    trovati: Dict[str, List[Tuple[str, int, int]]] = {"basso": [], "centro": []}
    for m in part.misure:
        for tipo, (x, y) in _buchi_misura(parti, m).items():
            trovati[tipo].append((_misura_di(part.misure, m.inizio), x, y))
    for tipo, elenco in trovati.items():
        if not elenco:
            continue
        misure = [x[0] for x in elenco]
        mis_es, a, b = elenco[0]
        t0 = next((m.inizio for m in part.misure
                   if _misura_di(part.misure, m.inizio) == mis_es), 0.0)
        bemolli = _armatura_a(part.misure, t0) < 0
        part.report.append(testo(
            f"buco_{tipo}", part.lingua, n=len(misure),
            misure=", ".join(misure[:8]) + (", ..." if len(misure) > 8 else ""),
            mis=mis_es, grave=nota(a, part.lingua, bemolli=bemolli),
            acuta=nota(b, part.lingua, bemolli=bemolli)))

def valida(part: Partitura, melodia: Optional[List] = None,
           originale: Optional[List] = None) -> List[str]:
    """Esegue tutti i filtri nell'ordine corretto e restituisce il report.
    `melodia` (le note della melodia dall'analisi) serve a riconoscere i
    raddoppi della melodia, che la correzione dei buchi non deve spostare.
    `originale` (le note dello spartito, a suono reale) serve al controllo
    dei semitoni contro cio' che l'originale suona."""
    filtro_polifonia(part)
    filtro_estensione(part)
    filtro_alterazioni(part)
    filtro_semitoni(part, originale)
    filtro_salti(part)
    filtro_idiomatico(part)
    filtro_mani(part)
    filtro_divisi(part)
    filtro_incroci(part)
    filtro_estensione(part)     # secondo passaggio dopo le modifiche idiomatiche
    filtro_ritmico(part)
    filtro_respiro(part)
    correggi_buchi_armonia(part, melodia)
    avviso_note_scomode(part)   # solo report: non cambia nessuna nota
    avviso_buchi_armonia(part)  # solo report: non cambia nessuna nota
    for p in part.parti:
        p.eventi.sort(key=lambda e: (e.rigo, e.inizio))
    return part.report
