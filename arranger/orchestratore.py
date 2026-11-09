"""
MODULO 3.2 - Motore di arrangiamento (Orchestrator Core).

Distribuisce i 4 layer analizzati sulle parti reali secondo:
  * la formazione e i divisi scelti dall'utente,
  * il livello didattico,
  * il template di stile (Normale / Cinematico / Jazz),
  * la "staffetta" della melodia fra piu' strumenti (con raddoppi).
"""

from __future__ import annotations

import random
from typing import Dict, List, Optional, Tuple

from .modello import (Accordo, Analisi, Configurazione, Evento, Misura, Nota,
                      Parte, Partitura, Spartito, nome_it)
from .analizzatore import BASSO_SIGLE_MAX
from .distribuzione import assegna as assegna_ruoli_stabili
from .distribuzione import (copertura, migliore_per_frase, solista_per_registro,
                            solisti_ordinati)
from .vincoli import AMBITO_MANI
from .lingua import abbrev_strumento, etichetta_livello, nome_parte_da_id
from .lingua import nota as nome_nota
from .lingua import stile as nome_stile
from .lingua import t as testo
from .strumenti import (ORDINE_PARTITURA, PERC_MIDI, Strumento, grado_livello,
                        livello, nomi_parti, strumento)

# --------------------------------------------------------------------------
# Utilita' armoniche
# --------------------------------------------------------------------------


def voicing(acc: Accordo, minimo: int, massimo: int, n_note: int = 3,
            centro: int = 64, includi_fondamentale: bool = True) -> List[int]:
    """Dispone l'accordo in posizione stretta dentro l'ambito richiesto."""
    pcs = acc.note_accordo()
    if includi_fondamentale:
        ordine = pcs
    else:
        ordine = pcs[1:] + pcs[:1]
    scelte: List[int] = []
    for pc in ordine[:max(1, n_note)]:
        candidate = [o * 12 + pc for o in range(0, 10) if minimo <= o * 12 + pc <= massimo]
        if not candidate:
            continue
        rif = scelte[-1] + 1 if scelte else centro - 4
        scelte.append(min(candidate, key=lambda c: abs(c - rif)))
    scelte = sorted(set(scelte))
    return scelte[:max(1, n_note)]


def nota_in_ambito(midi: int, minimo: int, massimo: int) -> int:
    while midi < minimo:
        midi += 12
    while midi > massimo:
        midi -= 12
    return max(minimo, min(massimo, midi))


def _pausa(inizio: float, durata: float, rigo: int = 1) -> Evento:
    return Evento(inizio=inizio, durata=durata, altezze=[], rigo=rigo)


def _riempi_pause(eventi: List[Evento], inizio: float, fine: float, rigo: int = 1) -> List[Evento]:
    """Completa i buchi con pause: ogni parte deve coprire tutta la durata."""
    eventi = sorted([e for e in eventi if e.durata > 1e-6], key=lambda e: e.inizio)
    risultato: List[Evento] = []
    t = inizio
    for e in eventi:
        if e.inizio > t + 1e-6:
            risultato.append(_pausa(t, e.inizio - t, rigo))
        if e.inizio < t - 1e-6:
            continue  # sovrapposizione: scarta
        risultato.append(e)
        t = e.fine
    if fine > t + 1e-6:
        risultato.append(_pausa(t, fine - t, rigo))
    return risultato


def _accordo_a(armonia: List[Accordo], t: float) -> Optional[Accordo]:
    for a in armonia:
        if a.inizio - 1e-6 <= t < a.fine - 1e-6:
            return a
    return armonia[-1] if armonia else None


# --------------------------------------------------------------------------
# Costruzione dell'organico
# --------------------------------------------------------------------------


def parti_originale(sp: Spartito, lingua: str = "it") -> List[Parte]:
    """
    MODALITA' CONFRONTO: ricostruisce lo spartito di partenza come parte in
    fondo alla partitura, cosi' da poterlo leggere sotto l'arrangiamento e
    verificare a colpo d'occhio melodia, armonia e ritmo.

    Non passa dai filtri di validazione: e' il testo originale, va lasciato
    esattamente com'e'.
    """
    parte = Parte(id="originale", nome=testo("originale_confronto", lingua),
                  abbrev="Orig.",
                  strumento="pianoforte", chiave="G", trasposizione=0,
                  monofonico=False, programma_midi=0, righi=2, ruolo="confronto")
    fine = sp.durata_totale
    inizio = sp.misure[0].inizio if sp.misure else 0.0

    for rigo in (1, 2):
        note = sorted([n for n in sp.note if n.rigo == rigo],
                      key=lambda n: (n.inizio, n.midi))
        if not note:
            parte.eventi.extend(_riempi_pause([], inizio, fine, rigo))
            continue
        attacchi = sorted({round(n.inizio, 6) for n in note})
        eventi: List[Evento] = []
        for i, t in enumerate(attacchi):
            gruppo = [n for n in note if abs(n.inizio - t) < 1e-6]
            prossimo = attacchi[i + 1] if i + 1 < len(attacchi) else fine
            durata = min(min(n.durata for n in gruppo), prossimo - t)
            if durata <= 1e-6:
                continue
            eventi.append(Evento(inizio=t, durata=durata,
                                 altezze=sorted({n.midi for n in gruppo}),
                                 rigo=rigo))
        parte.eventi.extend(_riempi_pause(eventi, inizio, fine, rigo))
    return [parte]


def costruisci_parti(cfg: Configurazione) -> List[Parte]:
    parti: List[Parte] = []
    for chiave in ORDINE_PARTITURA:
        n = cfg.formazione.get(chiave, 0)
        if n <= 0:
            continue
        st = strumento(chiave)
        for i, nome in enumerate(nomi_parti(chiave, n, cfg.lingua)):
            id_parte = f"{chiave}{i + 1}"
            # L'id della parte vince sullo strumento: se il professore ha
            # detto qualcosa del secondo leggio di violino, quella
            # indicazione e' piu' specifica di quella data per i violini in
            # generale, e va rispettata.
            livello_parte_ = (cfg.livelli_strumenti.get(id_parte)
                              or cfg.livelli_strumenti.get(chiave))
            parti.append(Parte(
                id=id_parte, nome=nome,
                abbrev=(abbrev_strumento(chiave, cfg.lingua)
                        + (f" {i + 1}" if n > 1 else "")),
                strumento=chiave, chiave=st.chiave_musicale,
                ottava_chiave=st.ottava_chiave, trasposizione=st.trasposizione,
                monofonico=st.monofonico, programma_midi=st.programma_midi,
                righi=st.righi, mostra_sigle=False, variante=i,
                livello=livello_parte_,
            ))
    return parti


# --------------------------------------------------------------------------
# Staffetta della melodia
# --------------------------------------------------------------------------


def unita_di_scambio(analisi: Analisi, cfg: Configurazione,
                     misure: Optional[List[Misura]] = None
                     ) -> Tuple[List[Tuple[float, float]], str]:
    """
    Dove puo' avvenire lo scambio fra i solisti.

    Non a caso e non ogni quattro battute: alla fine di una frase, meglio se
    alla fine di un periodo. Nei brani con struttura di canzone si cambia fra
    una sezione e l'altra, cosi' la strofa resta di chi l'ha cominciata.
    """
    scelta = cfg.cambio_solista
    if scelta == "auto":
        scelta = "sezione" if analisi.forma == "pop" else "periodo"
    if scelta == "sezione" and analisi.sezioni:
        unita, tipo = [(a, b) for (a, b, _e) in analisi.sezioni], "sezione"
    elif scelta in ("sezione", "periodo") and analisi.periodi:
        unita, tipo = list(analisi.periodi), "periodo"
    else:
        unita, tipo = list(analisi.frasi), "frase"
    return _accorpa_brevi(unita, cfg, misure), tipo


def _accorpa_brevi(unita: List[Tuple[float, float]], cfg: Configurazione,
                   misure: List[Misura]) -> List[Tuple[float, float]]:
    """
    Unisce le unita' troppo corte finche' non durano almeno
    `cfg.misure_minime_solista` misure: cambiare solista ogni due battute fa
    solo confusione, e nessuno fa in tempo a riconoscere il timbro.
    """
    if not unita or cfg.misure_minime_solista <= 0:
        return unita
    durata_misura = misure[0].durata_piena if misure else 4.0
    minimo = cfg.misure_minime_solista * durata_misura
    fuori: List[List[float]] = []
    for (a, b) in unita:
        if fuori and (fuori[-1][1] - fuori[-1][0]) < minimo - 1e-6:
            fuori[-1][1] = b
        else:
            fuori.append([a, b])
    if len(fuori) > 1 and (fuori[-1][1] - fuori[-1][0]) < minimo * 0.5:
        fuori[-2][1] = fuori[-1][1]
        fuori.pop()
    return [(a, b) for a, b in fuori]


def pianifica_staffetta(parti: List[Parte], analisi: Analisi,
                        cfg: Configurazione, tonalita: int = 0,
                        climax: Optional[set] = None,
                        misure_partitura: Optional[List[Misura]] = None
                        ) -> Dict[int, List[str]]:
    """
    Per ogni FRASE decide quali parti portano la melodia, ma i cambi di solista
    avvengono solo sui confini dell'unita' di scambio (periodo o sezione):
    dentro un periodo la melodia non cambia mano.

    Nei ritornelli di un brano pop tutti i solisti suonano all'unisono: e' il
    momento in cui l'unisono ha senso.
    """
    solisti = solisti_ordinati(parti, analisi, cfg, tonalita)
    if not solisti:
        residuo = [p for p in parti if not strumento(p.strumento).percussione]
        solisti = residuo[:1]
    if not solisti:
        return {}

    climax = climax or set()
    frasi = analisi.frasi or [(0.0, 0.0)]
    unita, _tipo = unita_di_scambio(analisi, cfg, misure_partitura)
    unita = unita or frasi

    def indice_unita(inizio: float) -> int:
        for k, (a, b) in enumerate(unita):
            if a - 1e-6 <= inizio < b - 1e-6:
                return k
        return len(unita) - 1

    piano: Dict[int, List[str]] = {}
    for i, (a, b) in enumerate(frasi):
        note = [n for n in analisi.melodia if a - 1e-6 <= n.inizio < b - 1e-6]
        k = indice_unita(a)
        if cfg.staffetta_melodia and len(solisti) > 1:
            turno = solisti[k % len(solisti)]
            capo = turno
            if note:
                dentro, _ = copertura(strumento(turno.strumento), note, cfg.livello)
                if dentro < 0.7:
                    # tratto scomodo per chi tocca: prima si cerca chi lo suona
                    # al registro scritto (tipico dei passaggi alla mano
                    # sinistra), poi si ripiega sul piu' adatto in assoluto -
                    # che lo cantera' trasposto d'ottava
                    capo = (solista_per_registro(solisti, note, cfg.livello,
                                                 tonalita)
                            or migliore_per_frase(solisti, note, cfg.livello,
                                                  tonalita) or turno)
        else:
            capo = migliore_per_frase(solisti, note, cfg.livello, tonalita) \
                or solisti[0]

        in_ritornello = any(x - 1e-6 <= a < y - 1e-6
                            for (x, y) in analisi.ritornelli)
        if in_ritornello and len(solisti) > 1:
            piano[i] = [p.id for p in solisti]      # unisono nel ritornello
            continue

        squadra = [capo.id]
        if cfg.raddoppi_melodia and (not cfg.staffetta_melodia
                                     or len(solisti) < 2 or i in climax):
            compagno = scegli_raddoppio(capo, [p for p in solisti if p is not capo])
            if compagno is not None:
                squadra.append(compagno.id)
        piano[i] = squadra
    return piano


# Affinita' fra famiglie nel raddoppio della melodia (Rimskij-Korsakov,
# cap. I e II): piu' basso = impasto migliore. Legni con legni e archi con
# archi si fondono; i legni addolciscono gli ottoni e ispessiscono gli archi;
# archi e ottoni insieme restano separati.
AFFINITA_FAMIGLIE = {
    frozenset({"fiati"}): 0, frozenset({"archi"}): 0,
    frozenset({"ottoni"}): 1, frozenset({"fiati", "ottoni"}): 1,
    frozenset({"fiati", "archi"}): 2, frozenset({"archi", "ottoni"}): 4,
}


def scegli_raddoppio(capo: Parte, candidati: List[Parte]) -> Optional[Parte]:
    """
    Chi raddoppia la melodia di `capo`: il candidato col miglior impasto di
    famiglia (vedi AFFINITA_FAMIGLIE; tastiere, corde e percussioni valgono
    3). Chi pesa piu' di chi canta e' penalizzato, perche' nell'unisono
    prevarrebbe il suo timbro (il corno su un flauto); chi pesa piu' del
    doppio lo coprirebbe (la tromba su un flauto) ed e' l'ultima scelta. A
    parita', l'ordine dei candidati (idoneita').
    """
    st_capo = strumento(capo.strumento)

    def costo(p: Parte) -> int:
        st = strumento(p.strumento)
        c = AFFINITA_FAMIGLIE.get(frozenset({st_capo.famiglia, st.famiglia}), 3)
        if st.peso > 2 * st_capo.peso:
            c += 5          # lo coprirebbe
        elif st.peso > st_capo.peso:
            c += 2          # nell'unisono prevarrebbe il suo timbro
        return c

    if not candidati:
        return None
    return min(candidati, key=lambda p: (costo(p), candidati.index(p)))


def nota_di_aggancio(linea: List[Evento], melodia: List[Nota],
                     frasi: List[Tuple[float, float]], ultima_frase: int,
                     staffetta: Dict[int, List[str]], id_parte: str,
                     ambito: Tuple[int, int]) -> Optional[Evento]:
    """
    Passaggio della melodia (Rimskij-Korsakov, cap. IV): l'ultima nota di
    chi finisce coincide con la prima di chi comincia. Chi cede la melodia
    suona anche la prima nota della frase successiva, insieme a chi la
    riceve: un raddoppio di una nota, la melodia non cambia.

    Solo se la frase dopo passa a un'altra parte e le due frasi sono
    attaccate (al massimo un movimento di pausa fra l'una e l'altra): dopo
    un respiro lungo non c'e' niente da agganciare. L'ottava e' quella con
    cui la parte stava cantando, o la piu' vicina dentro l'estensione.
    """
    successiva = ultima_frase + 1
    if not linea or successiva >= len(frasi) or successiva not in staffetta:
        return None
    if id_parte in staffetta[successiva]:
        return None
    a, b = frasi[successiva]
    prima = next((n for n in sorted(melodia, key=lambda n: n.inizio)
                  if a - 1e-6 <= n.inizio < b - 1e-6), None)
    ultima = max(linea, key=lambda e: e.inizio)
    if prima is None or ultima.pausa:
        return None
    if prima.inizio - ultima.fine > 1.0 + 1e-6 or prima.inizio < ultima.fine - 1e-6:
        return None
    sorgente = next((n for n in melodia if abs(n.inizio - ultima.inizio) < 1e-6), None)
    scarto = ultima.altezze[0] - sorgente.midi if sorgente else 0
    lo, hi = ambito
    candidate = [prima.midi + scarto + k for k in (0, -12, 12)
                 if lo <= prima.midi + scarto + k <= hi]
    if not candidate:
        return None
    altezza = min(candidate, key=lambda x: abs(x - ultima.altezze[0]))
    return Evento(inizio=prima.inizio, durata=prima.durata, altezze=[altezza])


def _climax(analisi: Analisi) -> List[int]:
    """Indici delle frasi con maggiore intensita' (densita' x registro)."""
    punteggi = []
    for i, (a, b) in enumerate(analisi.frasi):
        note = [n for n in analisi.melodia if a <= n.inizio < b]
        if not note:
            punteggi.append((i, 0.0))
            continue
        dens = len(note) / max(1.0, b - a)
        alt = sum(n.midi for n in note) / len(note)
        punteggi.append((i, dens * 0.6 + (alt - 60) * 0.4))
    punteggi.sort(key=lambda x: -x[1])
    return [i for i, _ in punteggi[:max(1, len(punteggi) // 3)]]


# --------------------------------------------------------------------------
# Generatori di linee
# --------------------------------------------------------------------------


def linea_melodia(melodia: List[Nota], st: Strumento, liv: str,
                  intervallo: Optional[Tuple[float, float]] = None,
                  minimo: Optional[int] = None) -> List[Evento]:
    """
    La melodia NON viene alterata: solo trasposizione d'ottava se necessario.

    `minimo` alza il limite grave (la destra del pianoforte): l'ottava si
    sceglie per l'intero blocco gia' qui, altrimenti il filtro delle mani
    riporterebbe su le note gravi una per una, spezzando il profilo
    (esempi/melodia_al_basso.xml).
    """
    lo, hi = st.ambito(liv)
    if minimo is not None:
        lo = max(lo, minimo)
    ev: List[Evento] = []
    note = melodia
    if intervallo:
        a, b = intervallo
        note = [n for n in melodia if a - 1e-6 <= n.inizio < b - 1e-6]
    if not note:
        return ev
    # Un'unica ottava per l'intera frase, cosi' il profilo resta quello
    # dell'originale. Se la frase non ci sta tutta, si spezza sui respiri
    # (pause) e si sceglie un'ottava per ogni tratto: mai nota per nota,
    # altrimenti nascono salti d'ottava dentro una scala.
    globale = _ottava_migliore([n.midi for n in note], lo, hi)
    if all(lo <= n.midi + globale <= hi for n in note):
        # tutta la frase in una sola ottava: profilo identico all'originale
        for n in note:
            ev.append(Evento(inizio=n.inizio, durata=n.durata,
                             altezze=[n.midi + globale]))
        return ev

    # non ci sta tutta: si spezza sui respiri, preferendo pero' l'ottava piu'
    # vicina a quella del tratto precedente per non strappare la linea
    precedente = globale
    for tratto in _tratti(note):
        scarto = _ottava_migliore([n.midi for n in tratto], lo, hi,
                                  preferito=precedente)
        precedente = scarto
        for n in tratto:
            ev.append(Evento(inizio=n.inizio, durata=n.durata,
                             altezze=[nota_in_ambito(n.midi + scarto, lo, hi)]))
    return ev


def _leviga_selettiva(eventi: List[Evento], lo: int, hi: int,
                      immutabili: set,
                      ambito_rigo: Optional[Dict[int, Tuple[int, int]]] = None
                      ) -> None:
    """
    Come `leviga_ottave`, ma non tocca gli eventi indicati (la melodia) e
    guarda ENTRAMBI i vicini: cosi' l'accompagnamento si avvicina anche
    all'ingresso della melodia, che non puo' essere spostato.

    `ambito_rigo` restringe l'ambito rigo per rigo (le due mani del
    pianoforte): senza, la destra veniva portata sotto il Sol3 per
    avvicinarsi alla melodia, e il filtro delle mani la riportava su.
    """
    for i, e in enumerate(eventi):
        if e.pausa or len(e.altezze) != 1 or id(e) in immutabili or e.letterale:
            continue
        lo_e, hi_e = lo, hi
        if ambito_rigo and e.rigo in ambito_rigo:
            lo_e = max(lo, ambito_rigo[e.rigo][0])
            hi_e = min(hi, ambito_rigo[e.rigo][1])
        vicini: List[Tuple[int, float]] = []
        for j, contiguo in ((i - 1, lambda a, b: abs(a.fine - b.inizio) < 1e-6),
                            (i + 1, lambda a, b: abs(b.fine - a.inizio) < 1e-6)):
            if not (0 <= j < len(eventi)):
                continue
            v = eventi[j]
            if v.pausa or len(v.altezze) != 1 or v.rigo != e.rigo:
                continue
            if not contiguo(v, e):
                continue
            vicini.append((v.altezze[0], 2.5 if id(v) in immutabili else 1.0))
        if not vicini:
            continue
        migliore = e.altezze[0]

        def costo(x: int) -> float:
            # il vicino immutabile (la melodia) pesa di piu': e' lui che
            # l'accompagnamento deve raggiungere, non viceversa
            return sum(abs(x - v) * peso for v, peso in vicini)

        costo_migliore = costo(migliore)
        for cand in (migliore + 12, migliore - 12, migliore + 24, migliore - 24):
            if not (lo_e <= cand <= hi_e):
                continue
            if costo(cand) < costo_migliore:
                migliore, costo_migliore = cand, costo(cand)
        e.altezze = [migliore]


def _respiro_prima_della_melodia(eventi: List[Evento], immutabili: set,
                                 salto_minimo: int = 12) -> None:
    """
    Quando una parte passa dall'accompagnamento alla melodia con un balzo
    ampio, accorcia l'ultima nota dell'accompagnamento: un respiro prima
    dell'entrata e' cio' che scriverebbe un arrangiatore, ed evita la
    sensazione di linea strappata.
    """
    for a, b in zip(eventi, eventi[1:]):
        if a.pausa or b.pausa or id(a) in immutabili or id(b) not in immutabili:
            continue
        if a.rigo != b.rigo or abs(a.fine - b.inizio) > 1e-6:
            continue
        if len(a.altezze) != 1 or len(b.altezze) != 1:
            continue
        if abs(b.altezze[0] - a.altezze[0]) < salto_minimo:
            continue
        respiro = min(1.0, a.durata / 2.0)
        if respiro > 1e-6:
            a.durata -= respiro


def _blocchi_contigui(indici: List[int]) -> List[List[int]]:
    fuori: List[List[int]] = []
    for i in indici:
        if fuori and i == fuori[-1][-1] + 1:
            fuori[-1].append(i)
        else:
            fuori.append([i])
    return fuori


def _tratti(note: List[Nota], respiro: float = 1.0) -> List[List[Nota]]:
    """Spezza una linea nei suoi tratti legati, separati dalle pause."""
    fuori: List[List[Nota]] = []
    for n in note:
        if fuori and n.inizio - fuori[-1][-1].fine < respiro - 1e-6:
            fuori[-1].append(n)
        else:
            fuori.append([n])
    return fuori


def _ottava_migliore(midis: List[int], lo: int, hi: int,
                     preferito: int = 0) -> int:
    """
    Trasposizione d'ottava unica che fa stare piu' note possibile nell'ambito
    (a parita', quella che centra meglio il registro).
    """
    if not midis:
        return 0
    migliore, punteggio_migliore = 0, None
    centro = (lo + hi) / 2
    for delta in (0, 12, -12, 24, -24, 36, -36):
        fuori = sum(1 for m in midis if not (lo <= m + delta <= hi))
        medio = sum(m + delta for m in midis) / len(midis)
        # a parita' di note fuori ambito si preferisce NON spostare nulla:
        # centrare il registro alzerebbe di un'ottava anche i bassi che
        # stanno benissimo dove sono
        punteggio = (fuori, abs(delta - preferito), abs(delta), abs(medio - centro))
        if punteggio_migliore is None or punteggio < punteggio_migliore:
            migliore, punteggio_migliore = delta, punteggio
    return migliore


def linea_controcanto(analisi: Analisi, st: Strumento, liv: str,
                      stile: str, voce: int = 0) -> List[Evento]:
    """
    Controcanto: note tenute dell'accordo in moto contrario alla melodia.

    `voce` distingue le parti di controcanto: la prima (0) tiene la linea,
    le altre scendono di `voce` note dell'accordo sotto di lei (una terza,
    una quarta: la seconda voce, poi la terza). Prima tutte le parti di
    controcanto suonavano la stessa linea, nota per nota, e il registro
    medio restava vuoto (Cinema Paradiso in 1a Media).
    """
    base = _linea_controcanto(analisi, st, liv, stile)
    if voce <= 0:
        return base
    lo, hi = st.ambito(liv)
    ev: List[Evento] = []
    for e in base:
        if e.pausa or len(e.altezze) != 1:
            ev.append(e)
            continue
        v = e.altezze[0]
        acc = _accordo_a(analisi.armonia, e.inizio)
        pcs = acc.note_accordo() if acc else [v % 12]
        mel = [n.midi for n in analisi.melodia
               if n.inizio - 1e-6 <= e.inizio < n.inizio + n.durata - 1e-6]
        # la nota della melodia no: una voce interna che la raddoppia non
        # aggiunge armonia (e la correzione dei buchi non la puo' spostare)
        if mel and len(pcs) > 1:
            pcs = [pc for pc in pcs if pc != mel[0] % 12] or pcs
        tutte = [x for x in range(lo, hi + 1) if x % 12 in pcs]
        sotto = sorted((x for x in tutte if x < v), reverse=True)
        if len(sotto) >= voce:
            nuova = sotto[voce - 1]
        elif sotto:
            nuova = sotto[-1]
        else:
            # niente sotto nell'estensione: una nota dell'accordo sopra la
            # prima voce ma sotto la melodia, altrimenti l'unisono
            sopra = [x for x in tutte if v < x < (mel[0] if mel else v)]
            nuova = min(sopra) if sopra else v
        ev.append(Evento(inizio=e.inizio, durata=e.durata, altezze=[nuova],
                         articolazione=e.articolazione))
    return _fondi_uguali(ev)


def _linea_controcanto(analisi: Analisi, st: Strumento, liv: str,
                       stile: str) -> List[Evento]:
    lo, hi = st.ambito(liv)
    L = livello(liv)
    ev: List[Evento] = []
    for acc in analisi.armonia:
        mel = [n for n in analisi.melodia if acc.inizio <= n.inizio < acc.fine]
        rif = mel[0].midi if mel else 67
        pcs = acc.note_accordo()
        # sceglie la terza o la quinta sotto la melodia
        candidate = []
        for pc in pcs[1:3] or pcs:
            for o in range(0, 10):
                m = o * 12 + pc
                if lo <= m <= hi and m < rif:
                    candidate.append(m)
        if not candidate:
            candidate = [nota_in_ambito(pcs[0] + 60, lo, hi)]
        scelta = max(candidate)
        durata = acc.durata
        if not L.sincopi and durata < 1.0:
            durata = max(durata, L.durata_minima)
        ev.append(Evento(inizio=acc.inizio, durata=acc.durata, altezze=[scelta],
                         articolazione="tenuto" if stile == "Cinematico" else None))
    return _fondi_uguali(leviga_ottave(ev, lo, hi))


def leviga_ottave(eventi: List[Evento], lo: int, hi: int) -> List[Evento]:
    """
    Riporta ogni nota all'ottava piu' vicina alla precedente (restando
    nell'ambito). Le linee costruite accordo per accordo saltano di ottava a
    ogni cambio di armonia: questo le rende cantabili senza toccarne le note.
    """
    prec: Optional[int] = None
    for e in eventi:
        if e.pausa or len(e.altezze) != 1 or e.letterale:
            prec = None
            continue
        if prec is None:
            prec = e.altezze[0]
            continue
        migliore = e.altezze[0]
        for cand in (migliore, migliore + 12, migliore - 12, migliore + 24, migliore - 24):
            if lo <= cand <= hi and abs(cand - prec) < abs(migliore - prec):
                migliore = cand
        e.altezze = [migliore]
        prec = migliore
    return eventi


def _fondi_uguali(ev: List[Evento]) -> List[Evento]:
    out: List[Evento] = []
    for e in sorted(ev, key=lambda x: x.inizio):
        if out and out[-1].altezze == e.altezze and abs(out[-1].fine - e.inizio) < 1e-6:
            out[-1].durata += e.durata
        else:
            out.append(e)
    return out


def accordi_a_blocchi(analisi: Analisi, st: Strumento, liv: str,
                      groove: List[float], misure: List[Misura],
                      senza_primo_movimento: bool = False,
                      minimo: Optional[int] = None) -> List[Evento]:
    """
    Accordi a blocchi disposti sul GROOVE del brano, non semplicemente sulla
    durata dell'armonia: se l'originale ha basso sul primo movimento e accordo
    sul secondo (il pattern della Gymnopedie, per dirne uno), l'accompagnamento
    lo riproduce invece di stendere un unico accordo per battuta.
    """
    L = livello(liv)
    lo, hi = st.ambito(liv)
    n_note = min(L.accordi_max, st.polifonia_max, 4)
    posizioni = _posizioni_groove(groove, misure)
    ev: List[Evento] = []

    if not posizioni:
        for acc in analisi.armonia:
            note = voicing(acc, max(lo, minimo or 48), min(hi, 79),
                           n_note=n_note)
            if note:
                ev.append(Evento(inizio=acc.inizio, durata=acc.durata,
                                 altezze=note, sigla=acc.sigla()))
        return _fondi_uguali(ev)

    if senza_primo_movimento and len(posizioni) > 1:
        # la mano sinistra ha gia' il basso sul primo movimento: la destra
        # entra dopo, com'e' scritto nell'originale
        posizioni = posizioni[1:]
    for m in misure:
        attacchi = [m.inizio + p for p in posizioni if p < m.durata - 1e-6]
        if not attacchi:
            continue
        for i, t in enumerate(attacchi):
            fine = attacchi[i + 1] if i + 1 < len(attacchi) else m.fine
            acc = _accordo_a(analisi.armonia, t)
            if acc is None:
                continue
            note = voicing(acc, max(lo, minimo or 48), min(hi, 79),
                           n_note=n_note)
            if note:
                ev.append(Evento(inizio=t, durata=fine - t, altezze=note,
                                 sigla=acc.sigla()))
    return ev


def _posizioni_groove(groove: List[float], misure: List[Misura],
                      massimo: int = 4) -> List[float]:
    """
    Posizioni d'attacco tipiche entro la misura, filtrate: si tengono solo
    quelle sui movimenti (o loro meta') e al massimo quattro, altrimenti
    l'accompagnamento diventa un tremolio.
    """
    if not misure or not groove:
        return []
    m = misure[0]
    passo = m.unita_movimento
    valide = sorted({p for p in groove
                     if 0 <= p < m.durata - 1e-6
                     and abs((p / passo) - round(p / passo)) < 1e-6})
    if 0.0 not in valide:
        valide = [0.0] + valide
    if len(valide) <= 1 or len(valide) > massimo:
        return []
    return valide


def arpeggio(analisi: Analisi, st: Strumento, liv: str,
             passo: float = 0.5, ampio: bool = False,
             minimo: Optional[int] = None,
             sopra_a: Optional[List[Nota]] = None) -> List[Evento]:
    """
    Arpeggio sull'armonia. `sopra_a` sono note che suonano sotto l'arpeggio
    (la sinistra dell'originale, copiata cosi' com'e'): accordo per accordo
    l'arpeggio parte sopra la piu' acuta, altrimenti le due mani dello
    stesso pianoforte si incrociano (stile Cinematico, Cinema Paradiso).
    """
    L = livello(liv)
    if not L.arpeggi:
        passo = max(passo, 1.0)
    lo, hi = st.ambito(liv)
    ev: List[Evento] = []
    for acc in analisi.armonia:
        pavimento = max(lo, minimo or 48)
        if sopra_a:
            sotto = [n.midi for n in sopra_a
                     if n.inizio < acc.fine - 1e-6 and n.fine > acc.inizio + 1e-6]
            if sotto:
                pavimento = max(pavimento, max(sotto) + 1)
        note = voicing(acc, pavimento, min(hi, 84),
                       n_note=4 if ampio else 3)
        if not note:
            continue
        if ampio:
            note = note + [n + 12 for n in note[:2] if n + 12 <= hi]
        t = acc.inizio
        i = 0
        while t < acc.fine - 1e-6:
            d = min(passo, acc.fine - t)
            ev.append(Evento(inizio=t, durata=d, altezze=[note[i % len(note)]]))
            t += d
            i += 1
    return ev


def riproduci_figurazione(note: List[Nota], st: Strumento, liv: str,
                          misure: List[Misura], max_note: int = 3,
                          rigo: int = 1, mantieni_ottave: bool = False
                          ) -> List[Evento]:
    """
    Riproduce l'accompagnamento COSI' COM'E' SCRITTO nell'originale: stessi
    attacchi, stesse durate, stessa figurazione (arpeggi, bassi ribattuti,
    pattern ritmici). Le altezze vengono solo ridotte di numero e riportate
    nell'ambito dello strumento.

    E' la differenza fra un pianoforte che accompagna e uno che tiene una
    semibreve per battuta.
    """
    if not note:
        return []
    L = livello(liv)
    lo, hi = st.ambito(liv)
    massimo = min(max_note, st.polifonia_max, L.accordi_max)

    attacchi = sorted({round(n.inizio, 6) for n in note})
    ev: List[Evento] = []
    for i, t in enumerate(attacchi):
        gruppo = sorted({n.midi for n in note if abs(n.inizio - t) < 1e-6})
        if not gruppo:
            continue
        if len(gruppo) > massimo:
            # si tengono gli estremi (basso e voce superiore) e si riempie
            scelte = [gruppo[0], gruppo[-1]] + gruppo[1:-1][:max(0, massimo - 2)]
            gruppo = sorted(set(scelte))[:massimo]
        durata = min(n.durata for n in note if abs(n.inizio - t) < 1e-6)
        if i + 1 < len(attacchi):
            durata = min(durata, attacchi[i + 1] - t)
        m = next((x for x in misure if x.inizio - 1e-6 <= t < x.fine - 1e-6), None)
        if m is not None:
            durata = min(durata, m.fine - t)
        if durata <= 1e-6:
            continue
        ev.append(Evento(inizio=t, durata=durata, altezze=gruppo, rigo=rigo,
                         letterale=True))

    if mantieni_ottave:
        # copia per il pianoforte: le ottave dell'originale sono gia' quelle
        # giuste, spostarle e' il modo piu' rapido per ottenere collisioni fra
        # le mani e registri assurdi
        for e in ev:
            e.altezze = sorted({max(lo, min(hi, a)) for a in e.altezze})
        return ev

    # una sola ottava per tratto, per non spezzare la figurazione
    for tratto in _tratti_eventi(ev):
        altezze = [a for e in tratto for a in e.altezze]
        scarto = _ottava_migliore(altezze, lo, hi)
        if scarto:
            for e in tratto:
                e.altezze = [a + scarto for a in e.altezze]
    for e in ev:
        e.altezze = sorted({nota_in_ambito(a, lo, hi) for a in e.altezze})
    return ev


def _tratti_eventi(eventi: List[Evento], respiro: float = 1.0) -> List[List[Evento]]:
    fuori: List[List[Evento]] = []
    for e in eventi:
        if fuori and e.inizio - fuori[-1][-1].fine < respiro - 1e-6:
            fuori[-1].append(e)
        else:
            fuori.append([e])
    return fuori


def ritmo_figurazione(figurazione: List[Nota], a: float, b: float
                      ) -> List[Tuple[float, float]]:
    """Solo gli attacchi e le durate dell'accompagnamento originale."""
    dentro = [n for n in figurazione if a - 1e-6 <= n.inizio < b - 1e-6]
    attacchi = sorted({round(n.inizio, 6) for n in dentro})
    fuori: List[Tuple[float, float]] = []
    for i, t in enumerate(attacchi):
        fine = attacchi[i + 1] if i + 1 < len(attacchi) else b
        fuori.append((t, fine - t))
    return fuori


def dirada_ritmo(ritmo: List[Tuple[float, float]], misure: List[Misura],
                 per_movimento: int = 1) -> List[Tuple[float, float]]:
    """
    Riduce il ritmo dell'accompagnamento a pochi attacchi per movimento.
    Una chitarra che pesta l'accordo su ogni croma della figurazione non
    accompagna: fa rumore.
    """
    if not ritmo or not misure:
        return ritmo
    passo = misure[0].unita_movimento / max(1, per_movimento)
    inizio_brano = misure[0].inizio
    tenuti: List[Tuple[float, float]] = []
    ultimo = None
    for (t, durata) in ritmo:
        cella = round((t - inizio_brano) / passo)
        if cella == ultimo:
            continue
        ultimo = cella
        # l'attacco si aggancia al BATTERE della cella: se la melodia entra in
        # ritardo (sincope, appoggiatura) l'accordo non deve seguirla, o
        # l'accompagnamento suona sistematicamente in ritardo
        tenuti.append((inizio_brano + cella * passo, durata))
    fuori: List[Tuple[float, float]] = []
    for i, (t, _d) in enumerate(tenuti):
        fine = tenuti[i + 1][0] if i + 1 < len(tenuti) else t + passo
        fuori.append((t, fine - t))
    return fuori


def accordi_su_ritmo(analisi: Analisi, st: Strumento, liv: str,
                     ritmo: List[Tuple[float, float]],
                     arpeggia: bool = False,
                     minimo: Optional[int] = None) -> List[Evento]:
    """
    Note dell'armonia disposte sul ritmo dell'accompagnamento originale.
    Serve agli strumenti che non possono copiare la figurazione alla lettera
    (chitarra, secondo pianoforte) ma devono comunque respirare con il brano.
    """
    L = livello(liv)
    lo, hi = st.ambito(liv)
    n_note = min(L.accordi_max, st.polifonia_max, 4)
    ev: List[Evento] = []
    passo = 0
    ultima_sigla: Optional[str] = None
    for (t, durata) in ritmo:
        acc = _accordo_a(analisi.armonia, t)
        if acc is None or durata <= 1e-6:
            continue
        note = sorted(set(voicing(acc, max(lo, minimo or 45), min(hi, 79),
                                  n_note=n_note)))
        if not note:
            continue
        if arpeggia:
            # la sigla si stampa al cambio d'accordo: sopra il rigo resta la
            # griglia, sul rigo la linea
            cambio = (ultima_sigla != acc.sigla())
            ev.append(Evento(inizio=t, durata=durata,
                             altezze=[note[passo % len(note)]],
                             sigla=acc.sigla() if cambio else None))
            ultima_sigla = acc.sigla()
            passo += 1
        else:
            ev.append(Evento(inizio=t, durata=durata, altezze=note,
                             sigla=acc.sigla()))
    return ev


def linea_basso(analisi: Analisi, st: Strumento, liv: str,
                massimo: Optional[int] = None) -> List[Evento]:
    """
    Riproduce la linea di basso dell'originale, ritmo compreso.

    `massimo` tiene la linea nel registro di basso (la sinistra del
    pianoforte, fino al Mi3): con l'estensione intera la levigatura la
    portava fino al Sol3, dove cominciano gli accordi della destra.
    """
    lo, hi = st.ambito(liv)
    if massimo is not None:
        hi = min(hi, massimo)
    ev = [Evento(inizio=n.inizio, durata=n.durata,
                 altezze=[nota_in_ambito(n.midi, lo, hi)])
          for n in analisi.basso]
    return leviga_ottave(ev, lo, hi)


def basso_sostenuto(analisi: Analisi, st: Strumento, liv: str,
                   misure: List[Misura]) -> List[Evento]:
    """Una sola nota grave per misura (o per meta' misura): scrittura di
    sostegno, diversa dal basso articolato del primo pianoforte.

    La nota resta nel registro di basso (fino al Mi3): con l'estensione
    intera del pianoforte la levigatura d'ottava la faceva salire di misura
    in misura fino a Sol3-La#3, dentro il registro della destra, e le due
    mani si scontravano (Cinema Paradiso con due pianoforti, 3a Media).
    """
    lo, hi = st.ambito(liv)
    hi = min(hi, BASSO_SIGLE_MAX)
    ev: List[Evento] = []
    for m in misure:
        acc_a = _accordo_a(analisi.armonia, m.inizio)
        acc_b = _accordo_a(analisi.armonia, m.inizio + m.durata / 2)
        if acc_a is None:
            continue
        if acc_b is not None and acc_b.fondamentale != acc_a.fondamentale:
            meta = m.durata / 2
            ev.append(Evento(inizio=m.inizio, durata=meta,
                             altezze=[nota_in_ambito(acc_a.fondamentale + 36, lo, hi)]))
            ev.append(Evento(inizio=m.inizio + meta, durata=m.durata - meta,
                             altezze=[nota_in_ambito(acc_b.fondamentale + 36, lo, hi)]))
        else:
            ev.append(Evento(inizio=m.inizio, durata=m.durata,
                             altezze=[nota_in_ambito(acc_a.fondamentale + 36, lo, hi)]))
    return _fondi_uguali(leviga_ottave(ev, lo, hi))


def _note_sopra_il_basso(acc: Accordo, basso_pc: int, quante: int) -> List[int]:
    """
    Le classi d'altezza da mettere sopra il basso, in ordine d'importanza:
    terza e settima prima (dicono che accordo e'), poi quinta e fondamentale.
    Con due sole note un accordo di settima resta riconoscibile: terza e
    settima, come insegna qualsiasi manuale d'accompagnamento.
    """
    pcs = acc.note_accordo()
    radice = acc.fondamentale
    ordine = []
    for intervallo in (3, 4, 10, 11, 9, 7, 6, 8, 5, 0):
        pc = (radice + intervallo) % 12
        if pc in pcs and pc not in ordine:
            ordine.append(pc)
    for pc in pcs:
        if pc not in ordine:
            ordine.append(pc)
    scelte = [pc for pc in ordine if pc != basso_pc] or ordine
    return scelte[:quante]


def sinistra_basso_accordo(analisi: Analisi, st: Strumento, liv: str,
                           misure: List[Misura]) -> List[Evento]:
    """
    Mano sinistra di un lead sheet quando la destra canta la melodia:
    basso e accordo. Senza, la sinistra ha solo il basso, una nota per
    accordo, e l'armonia scritta nelle sigle al pianoforte non si sente.

    1a media: basso piu' una nota dell'accordo, tenuti (bicordo, mano
    ferma). 2a e 3a: basso sul primo movimento e accordo sugli altri, il
    classico «um-pa»: um-pa-pa in 3/4, basso-accordo-basso-accordo in 4/4,
    basso e accordo nei tempi composti. Ogni cambio di sigla riparte dal
    basso. L'accordo sta sotto il si3 e sotto la melodia: dove la melodia
    scende troppo, la sinistra tiene il solo basso.
    """
    L = livello(liv)
    semplice = L.accordi_max <= 2
    # note sopra il basso: una in 1a (bicordo), due in 2a, tre in 3a
    quante = 1 if semplice else (2 if L.accordi_max <= 3 else 3)
    ev: List[Evento] = []
    for acc in analisi.armonia:
        if acc.durata <= 1e-6:
            continue
        # il basso e' quello gia' calcolato dalle sigle (rivolti compresi)
        dal_basso = [n for n in analisi.basso
                     if acc.inizio - 1e-6 <= n.inizio < acc.fine - 1e-6]
        basso_pc = acc.basso if acc.basso is not None else acc.fondamentale
        basso = (dal_basso[0].midi if dal_basso
                 else nota_in_ambito(basso_pc + 36, 40, 52))
        # tetto dell'accordo: sotto il si3 e sotto la nota piu' grave della
        # melodia in quel tratto
        canto = [n.midi for n in analisi.melodia
                 if n.inizio < acc.fine - 1e-6 and n.fine > acc.inizio + 1e-6]
        tetto = min([59] + [x - 1 for x in canto])
        sopra: List[int] = []
        for pc in _note_sopra_il_basso(acc, basso_pc, quante):
            candidati = [o * 12 + pc for o in range(3, 6)
                         if basso < o * 12 + pc <= tetto
                         and o * 12 + pc - basso <= L.tastiera_max_semitoni + (
                             0 if semplice else 12)]
            if candidati:
                rif = sopra[-1] if sopra else tetto
                sopra.append(min(candidati, key=lambda c: abs(c - rif)))
        sopra = sorted(set(sopra))
        if not semplice and sopra and max(sopra) - min(sopra) > L.tastiera_max_semitoni:
            sopra = sopra[1:]
        if semplice:
            ev.append(Evento(inizio=acc.inizio, durata=acc.durata,
                             altezze=sorted({basso, *sopra}), sigla=acc.sigla()))
            continue
        m = next((x for x in misure
                  if x.inizio - 1e-6 <= acc.inizio < x.fine - 1e-6), None)
        passo = m.unita_movimento if m is not None else 1.0
        t, k = acc.inizio, 0
        while t < acc.fine - 1e-6:
            d = min(passo, acc.fine - t)
            # in 4/4 il basso torna sul terzo movimento; in 3/4 e nei
            # composti solo sul primo
            movimenti = round(m.durata / passo) if m is not None else 4
            sul_basso = k == 0 or (movimenti == 4 and k % 2 == 0)
            if sul_basso or not sopra:
                ev.append(Evento(inizio=t, durata=d, altezze=[basso],
                                 sigla=acc.sigla()))
            else:
                ev.append(Evento(inizio=t, durata=d, altezze=list(sopra),
                                 sigla=acc.sigla()))
            t += d
            k += 1
    return ev


def walking_bass(analisi: Analisi, st: Strumento, liv: str,
                 misure: List[Misura]) -> List[Evento]:
    """Walking bass semplificato: fondamentale - quinta - fondamentale - grado di passaggio."""
    lo, hi = st.ambito(liv)
    L = livello(liv)
    ev: List[Evento] = []
    for m in misure:
        passo = m.unita_movimento
        t = m.inizio
        grado = 0
        while t < m.fine - 1e-6:
            acc = _accordo_a(analisi.armonia, t)
            if acc is None:
                t += passo
                grado += 1
                continue
            pcs = acc.note_accordo()
            pc = pcs[[0, 2, 0, 1][grado % 4] % len(pcs)]
            midi = nota_in_ambito(pc + 36, lo, hi)
            ev.append(Evento(inizio=t, durata=min(passo, m.fine - t), altezze=[midi]))
            t += passo
            grado += 1
    leviga_ottave(ev, lo, hi)
    if L.durata_minima > 1.0:
        return _fondi_uguali(ev)
    return ev


def comping_chitarra(analisi: Analisi, st: Strumento, liv: str,
                     misure: List[Misura], swing: bool = True) -> List[Evento]:
    """Accordi in levare (2 e 4 / contrattempo swing)."""
    L = livello(liv)
    lo, hi = st.ambito(liv)
    n_note = min(L.accordi_max, 4)
    ev: List[Evento] = []
    for m in misure:
        passo = m.unita_movimento
        t = m.inizio
        while t < m.fine - 1e-6:
            acc = _accordo_a(analisi.armonia, t)
            if acc is None:
                t += passo
                continue
            note = voicing(acc, max(lo, 45), min(hi, 69), n_note=n_note)
            if L.durata_minima >= 1.0 or m.composto:
                ev.append(Evento(inizio=t, durata=min(passo, m.fine - t), altezze=note,
                                 sigla=acc.sigla(), articolazione="staccato"))
            else:
                off = t + (2.0 / 3.0 if swing else 0.5)
                if off < m.fine - 1e-6:
                    d = min(1.0 / 3.0 if swing else 0.5, m.fine - off)
                    ev.append(Evento(inizio=off, durata=d, altezze=note,
                                     sigla=acc.sigla(), articolazione="staccato"))
            t += passo
    return ev


def linea_dalla_figurazione(analisi: Analisi, st: Strumento, liv: str,
                            a: float, b: float, misure: List[Misura],
                            riferimento: Optional[int] = None) -> List[Evento]:
    """
    Ricava una parte monodica da cio' che l'originale scrive DAVVERO in quel
    tratto, nel registro dello strumento.

    E' il primo posto in cui guardare quando serve un accompagnamento: prima
    di inventare un pad o un accordo a blocchi, si prende quello che c'e'
    scritto. Se in quel registro non c'e' materiale sufficiente si restituisce
    una lista vuota e il chiamante ripiega sull'invenzione.
    """
    lo, hi = st.ambito(liv)
    dentro = [n for n in analisi.figurazione
              if a - 1e-6 <= n.inizio < b - 1e-6]
    if len(dentro) < 4:
        return []
    # si sceglie la fascia piu' vicina all'ambito dello strumento
    centro = (lo + hi) / 2
    vicine = sorted(dentro, key=lambda n: abs(n.midi - centro))
    soglia = vicine[max(3, len(vicine) // 2)].midi
    banda = [n for n in dentro if abs(n.midi - centro) <= abs(soglia - centro) + 12]
    if len(banda) < 4:
        return []
    # gli attacchi troppo ravvicinati per il livello vengono uniti: questa
    # linea e' accompagnamento, non deve essere piu' difficile della melodia
    minimo = livello(liv).durata_minima
    grezzi = sorted({round(n.inizio, 6) for n in banda})
    attacchi: List[float] = []
    for t in grezzi:
        if not attacchi or t - attacchi[-1] >= minimo - 1e-6:
            attacchi.append(t)
    if len(attacchi) < 3:
        return []
    eventi: List[Evento] = []
    for i, t in enumerate(attacchi):
        gruppo = [n for n in banda if abs(n.inizio - t) < 1e-6]
        scelta = min(gruppo, key=lambda n: abs(n.midi - centro))
        fine = attacchi[i + 1] if i + 1 < len(attacchi) else b
        m = next((x for x in misure if x.inizio - 1e-6 <= t < x.fine - 1e-6), None)
        if m is not None:
            fine = min(fine, m.fine)
        durata = min(max(scelta.durata, minimo), fine - t)
        if durata < minimo - 1e-6:
            # il tratto disponibile e' piu' corto del valore minimo: si
            # allunga l'evento precedente invece di scrivere un valore
            # che a questo livello non si sa leggere
            if eventi:
                eventi[-1].durata = max(eventi[-1].durata, fine - eventi[-1].inizio)
            continue
        eventi.append(Evento(inizio=t, durata=durata, altezze=[scelta.midi]))
    # una sola ottava per l'intero tratto: spostare nota per nota
    # riempirebbe la linea di salti che nell'originale non ci sono
    scarto = _ottava_migliore([e.altezze[0] for e in eventi], lo, hi,
                              preferito=_scarto_di_raccordo(eventi, riferimento,
                                                            lo, hi))
    for e in eventi:
        e.altezze = [nota_in_ambito(e.altezze[0] + scarto, lo, hi)]
    return _riduci_sovrapposizioni(eventi)


def _scarto_di_raccordo(eventi: List[Evento], riferimento: Optional[int],
                        lo: int, hi: int) -> int:
    """
    Ottava che avvicina l'inizio della linea alla nota che la precede: senza,
    l'accompagnamento entra con un salto che nell'originale non c'e'.
    """
    if riferimento is None or not eventi:
        return 0
    primo = eventi[0].altezze[0]
    migliore, distanza = 0, None
    for delta in (0, 12, -12, 24, -24):
        if not (lo <= primo + delta <= hi):
            continue
        d = abs(primo + delta - riferimento)
        if distanza is None or d < distanza:
            migliore, distanza = delta, d
    return migliore


def _riduci_sovrapposizioni(eventi: List[Evento]) -> List[Evento]:
    for a, b in zip(eventi, eventi[1:]):
        if a.fine > b.inizio + 1e-6:
            a.durata = max(0.125, b.inizio - a.inizio)
    return eventi


def pad_fiati(analisi: Analisi, st: Strumento, liv: str, misure: List[Misura],
              grado: int = 1) -> List[Evento]:
    """Note lunghe tenute (una per misura) sul grado indicato dell'accordo."""
    lo, hi = st.ambito(liv)
    ev: List[Evento] = []
    for m in misure:
        acc = _accordo_a(analisi.armonia, m.inizio)
        if acc is None:
            continue
        pcs = acc.note_accordo()
        pc = pcs[grado % len(pcs)]
        ev.append(Evento(inizio=m.inizio, durata=m.durata,
                         altezze=[nota_in_ambito(pc + 60, lo, hi)],
                         articolazione="tenuto", dinamica="p" if m.numero == 1 else None))
    return _fondi_uguali(leviga_ottave(ev, lo, hi))


def archi_cinematici(analisi: Analisi, st: Strumento, liv: str, misure: List[Misura],
                     pizzicato: bool = False) -> List[Evento]:
    lo, hi = st.ambito(liv)
    ev: List[Evento] = []
    for m in misure:
        acc = _accordo_a(analisi.armonia, m.inizio)
        if acc is None:
            continue
        pcs = acc.note_accordo()
        if pizzicato:
            t = m.inizio
            i = 0
            while t < m.fine - 1e-6:
                pc = pcs[i % len(pcs)]
                ev.append(Evento(inizio=t, durata=1.0, altezze=[nota_in_ambito(pc + 48, lo, hi)],
                                 articolazione="pizzicato" if i == 0 else None))
                t += 1.0
                i += 1
        else:
            ev.append(Evento(inizio=m.inizio, durata=m.durata,
                             altezze=[nota_in_ambito(pcs[0] + 60, lo, hi)],
                             articolazione="tremolo"))
    return ev


def pattern_percussioni(stile: str, liv: str, misure: List[Misura],
                        groove: List[float]) -> List[Evento]:
    L = livello(liv)
    ev: List[Evento] = []
    for m in misure:
        passo = m.unita_movimento
        battute = max(1, int(round(m.durata / passo)))
        for b in range(battute):
            t = m.inizio + b * passo
            if t >= m.fine - 1e-6:
                break
            if stile == "Jazz" and L.durata_minima <= 0.5:
                d = min(passo, m.fine - t)
                ev.append(Evento(inizio=t, durata=d * 2 / 3, altezze=[PERC_MIDI["ride"]]))
                ev.append(Evento(inizio=t + d * 2 / 3, durata=d / 3,
                                 altezze=[PERC_MIDI["ride"]]))
            elif stile == "Cinematico":
                d = min(passo, m.fine - t)
                if b == 0:
                    ev.append(Evento(inizio=t, durata=d, altezze=[PERC_MIDI["grancassa"]],
                                     articolazione="accent"))
                else:
                    ev.append(_pausa(t, d))
            else:
                colpo = PERC_MIDI["grancassa"] if b % 2 == 0 else PERC_MIDI["rullante"]
                ev.append(Evento(inizio=t, durata=min(passo, m.fine - t), altezze=[colpo]))
    return ev


def orchestra_tessitura(sp: Spartito, analisi: Analisi, parti: List[Parte],
                        cfg: Configurazione, misure: List[Misura]) -> List[str]:
    """
    Orchestrazione per REGISTRI, senza separare melodia e accompagnamento.

    In molta musica pianistica - Debussy, la musica d'atmosfera, certi studi -
    non c'e' un tema da affidare a un solista: c'e' una tessitura. Cercare a
    tutti i costi una melodia produce un solista che canta l'arpeggio e un
    accompagnamento inventato. Qui invece il tessuto originale viene diviso in
    fasce di registro e ogni fascia va allo strumento che ci sta dentro, con la
    scrittura dell'originale.
    """
    resoconto: List[str] = []
    candidati = [p for p in parti if not strumento(p.strumento).percussione]
    if not candidati or not sp.note:
        return resoconto

    altezze = sorted(n.midi for n in sp.note)
    # gli strumenti si dispongono dal grave all'acuto secondo il loro ambito
    candidati.sort(key=lambda p: sum(strumento(p.strumento).ambito(cfg.livello)))
    fasce: List[Tuple[Parte, int, int]] = []
    n = len(candidati)
    for i, p in enumerate(candidati):
        basso = altezze[int(len(altezze) * i / n)]
        alto = altezze[min(len(altezze) - 1, int(len(altezze) * (i + 1) / n))]
        lo, hi = strumento(p.strumento).ambito(cfg.livello)
        fasce.append((p, max(basso - 2, lo - 12), min(alto + 2, hi + 12)))

    inizio = misure[0].inizio if misure else 0.0
    fine = sp.durata_totale
    for (p, basso, alto) in fasce:
        st = strumento(p.strumento)
        if p.righi == 2:
            # il pianoforte tiene la parte originale, com'e' scritta
            for rigo in (1, 2):
                note = [x for x in sp.note if x.rigo == rigo]
                p.eventi.extend(_riempi_pause(
                    riproduci_figurazione(note, st, cfg.livello, misure,
                                          max_note=3, rigo=rigo,
                                          mantieni_ottave=True),
                    inizio, fine, rigo))
            p.ruolo = "tessitura"
            resoconto.append(testo("tessitura_piano", cfg.lingua, parte=p.nome))
            continue

        note = [x for x in sp.note if basso <= x.midi <= alto]
        if not note:
            p.eventi = _riempi_pause([], inizio, fine)
            continue
        eventi = riproduci_figurazione(note, st, cfg.livello, misure,
                                       max_note=st.polifonia_max, rigo=1)
        if st.monofonico:
            for e in eventi:
                if e.altezze:
                    e.altezze = [max(e.altezze)]
        p.eventi = _riempi_pause(eventi, inizio, fine)
        p.ruolo = "tessitura"
        if p.strumento == "chitarra":
            p.mostra_sigle = True
        resoconto.append(testo("tessitura_fascia", cfg.lingua, parte=p.nome,
                               da=nome_nota(basso, cfg.lingua),
                               a=nome_nota(alto, cfg.lingua)))

    for p in parti:
        if strumento(p.strumento).percussione:
            p.eventi = _riempi_pause(
                pattern_percussioni(cfg.stile, cfg.livello, misure, analisi.groove),
                inizio, fine)
            p.ruolo = "ritmo"
    return resoconto


def raddoppia_melodia(voce: List[Nota], melodia: List[Nota]) -> bool:
    """True se almeno il 60% delle note della voce suona, a meno
    dell'ottava, la nota che la melodia ha in quel momento."""
    if not voce or not melodia:
        return False
    uguali = 0
    for n in voce:
        m = next((x for x in melodia
                  if x.inizio - 1e-6 <= n.inizio < x.inizio + x.durata - 1e-6), None)
        if m is not None and m.midi % 12 == n.midi % 12:
            uguali += 1
    return uguali * 5 >= len(voce) * 3


# Importanza dei ruoli per l'ordine dei leggii: la parte piu' esposta va al
# primo leggio, che nelle orchestre scolastiche e' il piu' sicuro
IMPORTANZA_RUOLO = {"melodia": 3, "controcanto": 2, "armonia": 1, "basso": 1,
                    "ritmo": 0}


def _leggii(parti: List[Parte], strumento_: str) -> List[Parte]:
    return sorted((p for p in parti if p.strumento == strumento_),
                  key=lambda p: p.variante)


def _puo_cedere(primo: Parte, secondo: Parte, cfg: Configurazione) -> bool:
    """Il primo leggio puo' prendere il posto del secondo: non e' di un
    livello piu' basso (se il docente ha messo al secondo leggio un allievo
    piu' avanti, la scelta e' sua) e il secondo non e' stato scelto a mano
    come solista."""
    if secondo.id in (cfg.strumenti_melodia or []):
        return False
    return (grado_livello(primo.livello or cfg.livello)
            >= grado_livello(secondo.livello or cfg.livello))


def melodia_ai_primi_leggii(parti: List[Parte], cfg: Configurazione) -> List[str]:
    """
    Fra i leggii dello stesso strumento il ruolo piu' esposto va sempre al
    primo: nelle orchestre scolastiche le seconde parti sono le piu' deboli.
    Se la distribuzione ha dato la melodia al Flauto 2 e il controcanto al
    Flauto 1, i due ruoli si scambiano (Akatsuki no Requiem, 3a Media).
    """
    note: List[str] = []
    for chiave in sorted({p.strumento for p in parti}):
        leggii = _leggii(parti, chiave)
        for k in range(1, len(leggii)):
            for j in range(k):
                primo, secondo = leggii[j], leggii[k]
                if (IMPORTANZA_RUOLO.get(secondo.ruolo, 1)
                        > IMPORTANZA_RUOLO.get(primo.ruolo, 1)
                        and _puo_cedere(primo, secondo, cfg)):
                    primo.ruolo, secondo.ruolo = secondo.ruolo, primo.ruolo
                    note.append(testo("ruoli_leggii", cfg.lingua,
                                      primo=primo.nome, secondo=secondo.nome))
    return note


def staffetta_ai_primi_leggii(staffetta: Dict[int, List[str]], parti: List[Parte],
                              cfg: Configurazione) -> int:
    """
    Nella staffetta un secondo leggio non canta mai da solo: se in una frase
    la melodia tocca al Violino 2 e il Violino 1 non c'e', la prende il
    Violino 1 (il secondo puo' solo raddoppiarlo). Ritorna le frasi corrette.
    """
    per_id = {p.id: p for p in parti}
    corrette = 0
    for i, squadra in staffetta.items():
        nuova: List[str] = []
        for pid in squadra:
            p = per_id.get(pid)
            if p is not None and p.variante > 0:
                primo = _leggii(parti, p.strumento)[0]
                if (primo is not p and primo.id not in squadra
                        and primo.ruolo == "melodia" and _puo_cedere(primo, p, cfg)):
                    pid = primo.id
            if pid not in nuova:
                nuova.append(pid)
        if nuova != squadra:
            staffetta[i] = nuova
            corrette += 1
    return corrette


def arrangia(sp: Spartito, analisi: Analisi, cfg: Configurazione,
             piano_melodia: Optional[Dict[int, List[str]]] = None,
             cfg_ruoli: Optional[Configurazione] = None) -> Partitura:
    """
    `cfg_ruoli`: se c'e', i ruoli e la staffetta si decidono sui SUOI
    livelli (il 1o quadrimestre), la scrittura sui livelli di `cfg`. Cosi'
    la versione di maggio da' a ognuno la stessa parte di quella di ottobre.
    """
    parti = costruisci_parti(cfg)
    cr = cfg_ruoli or cfg
    if cfg_ruoli is not None:
        for p, q in zip(parti, costruisci_parti(cfg_ruoli)):
            p.livello = q.livello
    tonalita = misure[0].tonalita if (misure := sp.misure) else 0
    resoconto_ruoli = assegna_ruoli_stabili(parti, analisi, cr, tonalita)
    L = livello(cfg.livello)
    misure = sp.misure
    inizio = misure[0].inizio if misure else 0.0
    fine = sp.durata_totale
    if cfg.strumenti_melodia:
        # le parti scelte dall'utente diventano solisti; le altre lasciano
        # il ruolo di melodia per non raddoppiarla senza motivo
        for p in parti:
            if p.id in cfg.strumenti_melodia:
                p.ruolo = "melodia"
            elif p.ruolo == "melodia":
                p.ruolo = "controcanto"
    resoconto_ruoli.extend(melodia_ai_primi_leggii(parti, cr))
    # la figurazione originale si conserva dalla 2a media in su: in 1a i
    # valori brevi e i salti degli arpeggi non sono ancora alla portata
    usa_figurazione = (livello(cfg.livello).durata_minima <= 0.5
                       and len(analisi.figurazione) > 0)
    # le voci interne dell'originale vengono distribuite ai controcanti PRIMA
    # della staffetta: chi ha una seconda voce da suonare non deve anche
    # contendersi la melodia
    contrappunti = [p for p in parti if p.ruolo == "controcanto"]
    # una «voce interna» che raddoppia la melodia (la destra del pianoforte
    # che suona il canto del solista, Akatsuki no Requiem) non e' una seconda
    # voce: la melodia la porta gia' la staffetta, e data al controcanto
    # finiva al Flauto 2 piu' che al Flauto 1
    voci_interne = [v for v in analisi.voci_interne
                    if not raddoppia_melodia(v, analisi.melodia)]
    voci_assegnate: Dict[str, List[Nota]] = {}
    if usa_figurazione:          # dalla 2a media in su
        for i, p_c in enumerate(contrappunti):
            if i < len(voci_interne):
                voci_assegnate[p_c.id] = voci_interne[i]

    staffetta = piano_melodia or pianifica_staffetta(
        parti, analisi, cr, tonalita, set(_climax(analisi)), misure)
    frasi_ai_primi = staffetta_ai_primi_leggii(staffetta, parti, cr)
    if cfg_ruoli is not None:
        # ruoli decisi: da qui si scrive sui livelli del quadrimestre scelto
        for p, q in zip(parti, costruisci_parti(cfg)):
            p.livello = q.livello
    if piano_melodia:
        for ids in piano_melodia.values():
            for i in ids:
                p = next((x for x in parti if x.id == i), None)
                if p is not None and p.ruolo == "armonia":
                    p.ruolo = "controcanto"
    climax = set(_climax(analisi))
    frasi = analisi.frasi or [(inizio, fine)]

    part = Partitura(titolo=sp.titolo, compositore=sp.compositore, misure=misure,
                     bpm=sp.bpm, stile=cfg.stile, livello=cfg.livello,
                     swing=(cfg.stile == "Jazz"), parti=parti,
                     armonia=list(analisi.armonia), lingua=cfg.lingua)
    lingua = cfg.lingua
    etichetta = etichetta_livello(cfg.livello, lingua, breve=True)
    if cfg.quadrimestre == 2:
        etichetta = testo("quadrimestre_secondo_etichetta", lingua, anno=etichetta)
    part.sottotitolo = testo("sottotitolo", lingua, livello=etichetta,
                             stile=nome_stile(cfg.stile, lingua))
    if sp.sigle:
        # Le sigle SCRITTE nel file sono un dato certo: chi suona il
        # pianoforte le deve trovare in partitura, come in ogni lead sheet.
        # Quelle dedotte dall'analisi restano solo sulla chitarra, che le ha
        # sempre avute: sul pianoforte, scritte accanto a una parte che
        # potrebbe dire altro, confonderebbero.
        for p in parti:
            if p.strumento == "pianoforte":
                p.mostra_sigle = True
    if sp.tipo == "lead_sheet":
        if sp.sigle:
            chiave = {"editor": "ingresso_lead_sheet_editor",
                      "proposta": "ingresso_lead_sheet_proposta_accettata"
                      }.get(sp.origine_sigle, "ingresso_lead_sheet")
            part.report.append(testo(chiave, lingua, n=len(sp.sigle)))
        else:
            from .lingua import nota as nome_nota
            tonica, modo = analisi.tonalita_proposta or (0, "maggiore")
            bemolli = bool(sp.misure) and sp.misure[0].tonalita < 0
            part.report.append(testo(
                "ingresso_lead_sheet_senza_sigle", lingua,
                tonalita=nome_nota(60 + tonica, lingua, bemolli=bemolli)[:-1],
                modo=testo(f"modo_{modo}", lingua)))
    elif sp.tipo == "solista_e_piano":
        part.report.append(testo("ingresso_solista", lingua))
    if cfg.livelli_strumenti:
        # Va scritto sulla partitura, non solo nel report: chi la prende in
        # mano fra sei mesi deve sapere che alcune parti sono state calibrate
        # su un livello diverso, o le leggera' come errori di scrittura.
        part.sottotitolo += testo("sottotitolo_differenziati", lingua)
        elenco = ", ".join(
            f"{nome_parte_da_id(chiave, lingua)} = "
            f"{etichetta_livello(valore, lingua, breve=True)}"
            for chiave, valore in sorted(cfg.livelli_strumenti.items()))
        part.report.append(testo(
            "livelli", lingua,
            livello=etichetta_livello(cfg.livello, lingua, breve=True),
            elenco=elenco))

    tessitura = (cfg.modo == "tessitura"
                 or (cfg.modo == "auto" and not analisi.melodia_affidabile))
    if tessitura:
        part.report.extend(orchestra_tessitura(sp, analisi, parti, cfg, misure))
        for p in parti:
            applica_dinamiche(p, sp.dinamiche, sp.gradazioni)
        part.report.append(testo("tessitura_brano", lingua))
        return part

    agganci = 0     # passaggi della melodia agganciati con una nota in comune
    # le parti di controcanto senza una voce dell'originale: la prima tiene la
    # linea, le altre prendono le voci sotto (vedi `linea_controcanto`).
    # Glockenspiel e metallofono sono colore: raddoppiano la prima voce e non
    # contano nella numerazione
    voci_controcanto = [p.id for p in parti
                        if p.ruolo == "controcanto" and p.id not in voci_assegnate
                        and strumento(p.strumento).famiglia != "percussioni"]
    for p in parti:
        # Il livello di QUESTA parte: in una classe eterogenea ogni
        # strumento puo' avere il suo, e tutto il materiale che segue —
        # melodia, basso, accompagnamento, figurazioni — va scritto sul
        # livello di chi lo suonera', non su una media della classe.
        liv_p = p.livello or cfg.livello
        st = strumento(p.strumento)
        ev: List[Evento] = []

        # ---------------------------------------------------- percussioni
        if st.percussione:
            ev = pattern_percussioni(cfg.stile, liv_p, misure, analisi.groove)
            p.eventi = _riempi_pause(ev, inizio, fine)
            applica_dinamiche(p, sp.dinamiche, sp.gradazioni)
            continue

        # ---------------------------------------------------- melodia (staffetta)
        ev_melodia: List[Evento] = []
        ev_originali: List[Evento] = []     # voci interne copiate dall'originale
        porta_melodia = sorted(i for i, squadra in staffetta.items() if p.id in squadra)
        # frasi consecutive dello stesso strumento vengono trattate come un
        # blocco unico: scegliere l'ottava frase per frase creerebbe un salto
        # artificiale a ogni giunzione
        for blocco in _blocchi_contigui(porta_melodia):
            a = frasi[blocco[0]][0] if blocco[0] < len(frasi) else inizio
            b = frasi[blocco[-1]][1] if blocco[-1] < len(frasi) else fine
            linea = linea_melodia(
                analisi.melodia, st, liv_p, (a, b),
                minimo=AMBITO_MANI[1][0] if p.righi == 2 else None)
            ev_melodia.extend(linea)
            if cfg.staffetta_melodia:
                aggancio = nota_di_aggancio(linea, analisi.melodia, frasi,
                                            blocco[-1], staffetta, p.id,
                                            st.ambito(liv_p))
                if aggancio is not None:
                    ev_melodia.append(aggancio)
                    agganci += 1

        # glockenspiel raddoppia la melodia nei climax (cinematico)
        if cfg.stile == "Cinematico" and p.strumento in ("glockenspiel", "metallofono"):
            for i in climax:
                if i < len(frasi) and i not in porta_melodia:
                    ev_melodia.extend(
                        linea_melodia(analisi.melodia, st, liv_p, frasi[i]))

        ev.extend(ev_melodia)
        coperto = _copertura(ev)

        # ---------------------------------------------------- ruolo di base
        # Un solista NON riempie i vuoti con l'accompagnamento: quando la
        # melodia tace, tace anche lui. Solo con la staffetta attiva, nelle
        # frasi cantate da altri, passa a seconda voce o accompagnamento.
        solista_puro = p.ruolo == "melodia" and (
            not cfg.staffetta_melodia
            or p.id in (cfg.strumenti_melodia or []))
        if solista_puro:
            vuoti = []
        else:
            vuoti = _intervalli_liberi(coperto, inizio, fine, minimo=1.0)
        for (a, b) in vuoti:
            sotto = _sotto_analisi(analisi, a, b)
            mis_sub = [m for m in misure if m.inizio >= a - 1e-6 and m.fine <= b + 1e-6]
            if not mis_sub:
                mis_sub = [m for m in misure if m.inizio < b and m.fine > a]

            # Il pianoforte col ruolo di basso NON passa di qui: il basso lo
            # suona la sinistra (blocco piu' sotto), la destra accompagna. Qui
            # la linea finiva sul rigo 1 e il filtro delle mani la alzava di
            # due o tre ottave: un basso doppio, con la copia nel registro del
            # canto (Dune, lead sheet dell'Inno alla gioia).
            if (p.ruolo == "basso" and p.strumento != "pianoforte") \
                    or (p.strumento == "violoncello" and p.ruolo != "melodia"):
                if cfg.stile == "Jazz":
                    ev.extend(walking_bass(sotto, st, liv_p, mis_sub))
                elif cfg.stile == "Cinematico":
                    ev.extend(archi_cinematici(sotto, st, liv_p, mis_sub,
                                               pizzicato=True))
                else:
                    ev.extend(linea_basso(sotto, st, liv_p))

            elif p.strumento == "chitarra":
                # La chitarra si tratta come strumento MELODICO: sopra il rigo
                # vanno le sigle, sul rigo una parte vera (melodia, seconda
                # voce o accompagnamento arpeggiato). Gli accordi a blocchi li
                # legge dalle sigle chi accompagna, non servono in partitura.
                p.mostra_sigle = True
                # nei tempi composti l'accompagnamento arpeggiato va in crome
                # (tre per movimento): diradare a meta' movimento produce un
                # ritmo che con il 6/8 non c'entra nulla
                composto = bool(mis_sub) and mis_sub[0].composto
                ritmo_ch = dirada_ritmo(
                    ritmo_figurazione(analisi.figurazione, a, b), mis_sub,
                    per_movimento=3 if composto else 2)
                if usa_figurazione and ritmo_ch:
                    ev.extend(accordi_su_ritmo(sotto, st, liv_p, ritmo_ch,
                                               arpeggia=True))
                else:
                    passo_arp = 1.0 if grado_livello(liv_p) <= 1 else 0.5
                    if mis_sub and mis_sub[0].composto:
                        passo_arp = 1.5 if grado_livello(liv_p) <= 1 else 0.5
                    ev.extend(arpeggio(sotto, st, liv_p, passo=passo_arp))

            elif p.strumento == "pianoforte":
                ritmo = ritmo_figurazione(analisi.figurazione, a, b)
                copia_fedele = (usa_figurazione and p.variante % 2 == 0
                                and cfg.stile == "Normale")
                if copia_fedele:
                    # il pianoforte accompagna con la figurazione scritta
                    # nell'originale: arpeggi e pattern ritmici si conservano
                    destra = riproduci_figurazione(
                        [n for n in analisi.figurazione
                         if n.rigo == 1 and a - 1e-6 <= n.inizio < b - 1e-6],
                        st, liv_p, mis_sub, max_note=3, rigo=1,
                        mantieni_ottave=True)
                    # se nell'originale la destra fa solo melodia, qui tace:
                    # inventarle accordi produce solo collisioni con la sinistra
                # gli accordi inventati nascono gia' nel registro della destra:
                # sotto il Sol3 il filtro delle mani li riporterebbe su una
                # nota alla volta, rovesciando l'accordo (Elvis, 1a Media)
                elif cfg.stile == "Cinematico":
                    # la sinistra del primo pianoforte sara' quella
                    # dell'originale (vedi sotto): l'arpeggio le sta sopra
                    copia_sinistra = usa_figurazione and p.variante % 2 == 0
                    destra = arpeggio(sotto, st, liv_p, passo=0.5,
                                      ampio=(p.variante % 2 == 0),
                                      minimo=AMBITO_MANI[1][0],
                                      sopra_a=[n for n in sp.note if n.rigo == 2]
                                      if copia_sinistra else None)
                elif usa_figurazione and ritmo:
                    destra = accordi_su_ritmo(
                        sotto, st, liv_p,
                        dirada_ritmo(ritmo, mis_sub, per_movimento=2),
                        arpeggia=(p.variante % 2 == 1),
                        minimo=AMBITO_MANI[1][0])
                elif p.variante % 2 == 1:
                    destra = arpeggio(sotto, st, liv_p, passo=0.5, ampio=False,
                                      minimo=AMBITO_MANI[1][0])
                else:
                    destra = accordi_a_blocchi(sotto, st, liv_p,
                                               analisi.groove, mis_sub,
                                               senza_primo_movimento=True,
                                               minimo=AMBITO_MANI[1][0])
                for e in destra:
                    e.rigo = 1
                ev.extend(destra)

            elif p.ruolo == "controcanto" and p.id in voci_assegnate:
                # seconda voce / contrappunto gia' scritti nell'originale:
                # si riprendono tali e quali, solo trasposti d'ottava
                voce = linea_melodia(voci_assegnate[p.id], st, liv_p, (a, b))
                ev_originali.extend(voce)
                ev.extend(voce)

            elif p.ruolo == "controcanto":
                if cfg.stile == "Cinematico" and st.famiglia in ("fiati", "ottoni"):
                    ev.extend(pad_fiati(sotto, st, liv_p, mis_sub, grado=1))
                elif cfg.stile == "Cinematico" and st.famiglia == "archi":
                    ev.extend(archi_cinematici(sotto, st, liv_p, mis_sub))
                else:
                    ev.extend(linea_controcanto(sotto, st, liv_p, cfg.stile,
                                                voce=voci_controcanto.index(p.id)
                                                if p.id in voci_controcanto else 0))

            else:  # armonia
                if st.monofonico:
                    # prima si guarda che cosa scrive l'originale in quel
                    # registro; solo se non basta si inventa un pad
                    precedenti = [e for e in ev
                                  if not e.pausa and e.fine <= a + 1e-6]
                    riferimento = (max(precedenti, key=lambda e: e.fine).altezze[0]
                                   if precedenti else None)
                    dalla_musica = linea_dalla_figurazione(analisi, st,
                                                           liv_p, a, b,
                                                           mis_sub, riferimento)
                    ev.extend(dalla_musica or
                              pad_fiati(sotto, st, liv_p, mis_sub, grado=2))
                else:
                    ev.extend(accordi_a_blocchi(sotto, st, liv_p, analisi.groove, mis_sub))

        if p.strumento == "pianoforte":
            # la sinistra copre sempre tutto il brano, anche dove la destra
            # porta la melodia (altrimenti resterebbe muta nelle frasi cantate)
            tutto = _sotto_analisi(analisi, inizio, fine)
            # la mano sinistra si riprende PER INTERO dall'originale, bassi
            # compresi: se la melodia sta al basso, escluderla lascerebbe il
            # pianoforte con i soli accordi interni
            sinistra_originale = [n for n in sp.note if n.rigo == 2]
            if cfg.stile == "Jazz":
                sinistra = walking_bass(tutto, st, liv_p, misure)
            elif sp.tipo == "lead_sheet" and p.ruolo == "melodia":
                # la destra canta: l'armonia delle sigle la deve dare la
                # sinistra, non basta il basso
                sinistra = sinistra_basso_accordo(tutto, st, liv_p, misure)
            elif usa_figurazione and p.variante % 2 == 0 and sinistra_originale:
                # la mano sinistra dell'originale e' gia' la parte giusta:
                # arpeggi e figure ritmiche vanno conservati, non appiattiti
                sinistra = riproduci_figurazione(sinistra_originale, st,
                                                 liv_p, misure,
                                                 max_note=3, rigo=2,
                                                 mantieni_ottave=True)
            elif p.variante % 2 == 1:
                sinistra = basso_sostenuto(tutto, st, liv_p, misure)
            else:
                sinistra = linea_basso(tutto, st, liv_p,
                                       massimo=BASSO_SIGLE_MAX)
            for e in sinistra:
                e.rigo = 2
                if not e.letterale:
                    e.altezze = [nota_in_ambito(x, 36, 59) for x in e.altezze]
            ev = [e for e in ev if e.rigo != 2] + sinistra

        # melodia e voci interne sono testo originale: non si levigano, non si
        # spezzano, non si trasportano se non per intere frasi
        id_melodia = {id(e) for e in ev_melodia + ev_originali}
        intatti = [e for e in ev if id(e) in id_melodia]
        ev = intatti + spezza_su_misure(
            [e for e in ev if id(e) not in id_melodia], misure)
        # raccorda le giunzioni fra melodia e accompagnamento dentro la stessa
        # parte: si muove solo l'accompagnamento, la melodia resta intatta
        lo_p, hi_p = st.ambito(liv_p)
        ordinati = sorted(ev, key=lambda e: (e.rigo, e.inizio))
        for _ in range(3):        # poche passate: la correzione si propaga
            _leviga_selettiva(ordinati, lo_p, hi_p, id_melodia,
                              AMBITO_MANI if p.righi == 2 else None)
        # il respiro prima dell'entrata della melodia si puo' prendere anche
        # accorciando una voce interna: si cambia una durata, non un'altezza
        _respiro_prima_della_melodia(ordinati, {id(e) for e in ev_melodia})

        if p.righi == 2:
            p.eventi = (_riempi_pause([e for e in ev if e.rigo == 1], inizio, fine, 1) +
                        _riempi_pause([e for e in ev if e.rigo == 2], inizio, fine, 2))
        else:
            p.eventi = _riempi_pause(ev, inizio, fine)

        applica_dinamiche(p, sp.dinamiche, sp.gradazioni)

    if usa_figurazione:
        # tutto il materiale dell'originale va sfruttato: voci interne rimaste
        # fuori e incisi vengono affidati a chi tace, o a chi sta solo
        # riempiendo l'armonia
        residuo = [seg for seg in voci_interne
                   if not any(seg is v for v in voci_assegnate.values())]
        materiale = sorted(residuo + analisi.frammenti,
                           key=lambda seg: seg[0].inizio)
        part.report.extend(distribuisci_frammenti(parti, materiale,
                                                  cfg.livello, misure,
                                                  lingua=cfg.lingua))

    if frasi_ai_primi:
        part.report.append(testo("staffetta_primi_leggii", lingua, n=frasi_ai_primi))
    if agganci:
        part.report.append(testo("staffetta_aggancio", lingua, n=agganci))
    part.report.extend(alleggerisci_per_solista(part, analisi))
    part.report.extend(equilibra_sonorita(part, analisi))
    part.report.extend(riempi_silenzi_lunghi(part, analisi, cfg, misure))
    part.report.extend(resoconto_ruoli)

    return part


# --------------------------------------------------------------------------


def spezza_su_misure(eventi: List[Evento], misure: List[Misura]) -> List[Evento]:
    """
    Taglia gli eventi di accompagnamento sui confini di misura, riattaccando
    il tempo forte. La melodia non viene mai spezzata: le sue sincopi restano
    quelle dell'originale.
    """
    fuori: List[Evento] = []
    for e in eventi:
        resto = e
        for m in misure:
            if resto.inizio < m.fine - 1e-6 < resto.fine - 1e-6:
                primo = Evento(inizio=resto.inizio, durata=m.fine - resto.inizio,
                               altezze=list(resto.altezze),
                               articolazione=resto.articolazione,
                               dinamica=resto.dinamica, sigla=resto.sigla,
                               rigo=resto.rigo, gradazione=resto.gradazione)
                fuori.append(primo)
                resto = Evento(inizio=m.fine, durata=resto.fine - m.fine,
                               altezze=list(resto.altezze), sigla=resto.sigla,
                               rigo=resto.rigo)
        fuori.append(resto)
    return fuori


def applica_dinamiche(parte: Parte, dinamiche: List[Tuple[float, str]],
                      gradazioni: Optional[List[Tuple[float, float, str]]] = None
                      ) -> None:
    """
    Riporta sulle parti i segni dinamici e le forcelle (crescendo /
    diminuendo) presenti nello spartito originale.
    """
    for rigo in sorted({e.rigo for e in parte.eventi}):
        flusso = [e for e in parte.eventi if e.rigo == rigo and not e.pausa]
        if not flusso:
            continue
        for inizio, fine, tipo in (gradazioni or []):
            partenza = next((e for e in flusso if e.inizio >= inizio - 1e-6), None)
            arrivo = next((e for e in reversed(flusso) if e.inizio < fine - 1e-6), None)
            if partenza is None or arrivo is None or partenza is arrivo:
                continue
            partenza.gradazione = tipo
            arrivo.fine_gradazione = True
    if not dinamiche:
        return
    for rigo in sorted({e.rigo for e in parte.eventi}):
        flusso = [e for e in parte.eventi if e.rigo == rigo and not e.pausa]
        if not flusso:
            continue
        ultimo = None
        for offset, segno in sorted(dinamiche):
            if segno == ultimo:
                continue
            candidato = next((e for e in flusso if e.inizio >= offset - 1e-6), None)
            if candidato is None:
                candidato = flusso[-1]
            candidato.dinamica = segno
            ultimo = segno


# strumenti che, se portano la melodia, vanno protetti: hanno poca proiezione
# e qualunque accompagnamento denso li copre
SOLISTI_DEBOLI = {"chitarra", "glockenspiel", "metallofono", "violoncello"}


def riempi_silenzi_lunghi(part: Partitura, analisi: Analisi,
                          cfg: Configurazione, misure: List[Misura]
                          ) -> List[str]:
    """
    Nessuno strumento resta fermo a lungo.

    Un ragazzo che conta ottanta battute di pausa si distrae, e in un
    arrangiamento scolastico una parte silenziosa e' una parte sprecata. Chi
    non ha la melodia in quel tratto fa accompagnamento: una nota tenuta, un
    arpeggio, gli accordi - quello che il brano offre in quel punto.

    Restano i silenzi brevi, che sono respiro e servono.
    """
    note_report: List[str] = []
    if not cfg.riempi_silenzi or not misure:
        return note_report
    durata_misura = misure[0].durata_piena
    soglia = max(1, cfg.silenzio_massimo_misure) * durata_misura

    for p in part.parti:
        st = strumento(p.strumento)
        if st.percussione or p.righi == 2:
            continue          # le percussioni hanno il loro pattern, il piano suona
        riempiti = 0
        for rigo in sorted({e.rigo for e in p.eventi}):
            for (a, b) in _pause_lunghe(p, rigo, soglia):
                sotto = _sotto_analisi(analisi, a, b)
                if not sotto.armonia:
                    continue
                mis_sub = [m for m in misure if m.inizio < b and m.fine > a]
                eventi = _accompagnamento_di_riserva(sotto, st, cfg, mis_sub, p)
                eventi = [e for e in eventi if a - 1e-6 <= e.inizio < b - 1e-6]
                for e in eventi:
                    e.rigo = rigo
                    e.durata = min(e.durata, b - e.inizio)
                if eventi and _sostituisci_span(p, eventi):
                    riempiti += 1
        if riempiti:
            note_report.append(testo("silenzi", cfg.lingua, parte=p.nome,
                                     n=riempiti))
    return note_report


def _pause_lunghe(parte: Parte, rigo: int, soglia: float
                  ) -> List[Tuple[float, float]]:
    """Tratti in cui la parte tace per piu' della soglia."""
    flusso = [e for e in parte.eventi if e.rigo == rigo]
    tratti: List[List[float]] = []
    for e in flusso:
        if not e.pausa:
            tratti.append(None) if False else None
            continue
        if tratti and abs(tratti[-1][1] - e.inizio) < 1e-6:
            tratti[-1][1] = e.fine
        else:
            tratti.append([e.inizio, e.fine])
    return [(a, b) for a, b in tratti if b - a >= soglia - 1e-6]


def _accompagnamento_di_riserva(sotto: Analisi, st: Strumento,
                                cfg: Configurazione, misure: List[Misura],
                                p: Parte) -> List[Evento]:
    """Che cosa far suonare a chi in quel tratto non ha nulla da fare."""
    if p.strumento == "chitarra":
        ritmo = ritmo_figurazione(sotto.figurazione, misure[0].inizio,
                                  misure[-1].fine) if misure else []
        composto = bool(misure) and misure[0].composto
        if ritmo:
            return accordi_su_ritmo(sotto, st, cfg.livello,
                                    dirada_ritmo(ritmo, misure,
                                                 per_movimento=3 if composto else 2),
                                    arpeggia=True)
        return arpeggio(sotto, st, cfg.livello, passo=0.5)
    if st.monofonico:
        if misure:
            dalla_musica = linea_dalla_figurazione(sotto, st, cfg.livello,
                                                   misure[0].inizio,
                                                   misure[-1].fine, misure)
            if dalla_musica:
                return dalla_musica
        # niente di utile scritto qui: nota tenuta dell'armonia, che sostiene
        # senza coprire chi ha il tema
        return pad_fiati(sotto, st, cfg.livello, misure,
                         grado=1 + (p.variante % 2))
    return accordi_a_blocchi(sotto, st, cfg.livello, sotto.groove, misure,
                             senza_primo_movimento=False)


def alleggerisci_per_solista(part: Partitura, analisi: Analisi) -> List[str]:
    """
    Quando la melodia e' affidata a uno strumento debole (tipicamente la
    chitarra) l'accompagnamento va DIRADATO, altrimenti il solista sparisce.

    Nei tratti interessati: si tolgono i raddoppi della melodia, gli accordi
    scendono a due note, le percussioni battono solo sul primo movimento e
    tutti scendono di dinamica. Il solista sale a mezzoforte.
    """
    note_report: List[str] = []
    attacchi_melodia = {round(n.inizio, 6): n.midi for n in analisi.melodia}

    for solista in part.parti:
        if solista.strumento not in SOLISTI_DEBOLI or solista.ruolo != "melodia":
            continue
        tratti = _tratti_solista(solista, attacchi_melodia)
        if not tratti:
            continue
        for (a, b) in tratti:
            primo = next((e for e in solista.eventi
                          if not e.pausa and a - 1e-6 <= e.inizio < b - 1e-6), None)
            if primo is not None and not primo.dinamica:
                primo.dinamica = "mf"
            for p in part.parti:
                if p is solista or p.ruolo == "melodia":
                    continue      # gli altri solisti raddoppiano: e' voluto
                _dirada_parte(p, a, b, attacchi_melodia, ripristina=True)
        note_report.append(testo("solista_alleggerito", part.lingua,
                                 parte=solista.nome, n=len(tratti)))
    return note_report


# Equilibrio (Rimskij-Korsakov, cap. I): una parte d'accompagnamento copre
# chi canta se pesa piu' del doppio, o l'accompagnamento intero se pesa piu'
# di tanto quanto la melodia
COPRE_SINGOLA = 2.0
COPRE_INSIEME = 5.0


def _canta_nel_tratto(p: Parte, a: float, b: float,
                      attacchi_melodia: Dict[float, int]) -> bool:
    """True se nel tratto la parte suona soprattutto la melodia (anche
    all'ottava, come nota piu' acuta, per piu' di meta' delle note): e' chi
    canta o un suo raddoppio, non accompagnamento."""
    dentro = [e for e in p.eventi if not e.pausa and a - 1e-6 <= e.inizio < b - 1e-6]
    if not dentro:
        return False
    # conta la nota piu' acuta: un accordo che contiene per caso la nota
    # della melodia e' accompagnamento, non un raddoppio
    uguali = sum(1 for e in dentro
                 if round(e.inizio, 6) in attacchi_melodia
                 and max(e.altezze) % 12 == attacchi_melodia[round(e.inizio, 6)] % 12)
    return uguali * 2 > len(dentro)


def equilibra_sonorita(part: Partitura, analisi: Analisi) -> List[str]:
    """
    Generalizza `alleggerisci_per_solista` con i pesi di sonorita' degli
    strumenti (`Strumento.peso`). In ogni tratto in cui qualcuno canta, si
    sommano i pesi di chi porta la melodia (con i raddoppi) e si guardano le
    parti che accompagnano:
      - una parte che pesa piu' di COPRE_SINGOLA volte la melodia la copre
        (una tromba sotto un flauto);
      - se l'accompagnamento intero supera COPRE_INSIEME volte la melodia,
        si diradano le parti piu' pesanti finche' non rientra.
    Le parti che coprono si diradano come per i solisti deboli (piano,
    accordi a due note, niente raddoppi della melodia) e alla fine del tratto
    ritrovano la dinamica di prima. I solisti deboli restano a
    `alleggerisci_per_solista`, che li protegge sempre.
    """
    note_report: List[str] = []
    attacchi_melodia = {round(n.inizio, 6): n.midi for n in analisi.melodia}
    fatti: set = set()
    diradati: Dict[str, List[str]] = {}
    for solista in part.parti:
        if solista.ruolo != "melodia" or solista.strumento in SOLISTI_DEBOLI:
            continue
        for (a, b) in _tratti_solista(solista, attacchi_melodia):
            cantano = [p for p in part.parti
                       if _canta_nel_tratto(p, a, b, attacchi_melodia)]
            if solista not in cantano:
                continue
            peso_melodia = sum(strumento(p.strumento).peso for p in cantano)
            accompagnano = [p for p in part.parti if p not in cantano and any(
                not e.pausa and e.inizio < b - 1e-6 and e.fine > a + 1e-6
                for e in p.eventi)]
            accompagnano.sort(key=lambda p: -strumento(p.strumento).peso)
            pesanti = [p for p in accompagnano
                       if strumento(p.strumento).peso > COPRE_SINGOLA * peso_melodia]
            totale = sum(strumento(p.strumento).peso for p in accompagnano)
            for p in accompagnano:
                if totale - sum(strumento(q.strumento).peso for q in pesanti) \
                        <= COPRE_INSIEME * peso_melodia:
                    break
                if p not in pesanti:
                    pesanti.append(p)
            for p in pesanti:
                chiave = (p.id, round(a, 6), round(b, 6))
                if chiave in fatti:
                    continue
                fatti.add(chiave)
                _dirada_parte(p, a, b, attacchi_melodia, ripristina=True)
                inizio, fine = (_numero_misura(part.misure, a),
                                _numero_misura(part.misure, b - 1e-3))
                mis = inizio if inizio == fine else f"{inizio}-{fine}"
                diradati.setdefault(p.nome, [])
                if mis not in diradati[p.nome]:
                    diradati[p.nome].append(mis)
    for nome, misure in diradati.items():
        misure.sort(key=lambda m: int(m.split("-")[0]) if m.split("-")[0].isdigit() else 0)
        note_report.append(testo(
            "equilibrio", part.lingua, parte=nome,
            misure=", ".join(misure[:8]) + (", ..." if len(misure) > 8 else "")))
    return note_report


def _tratti_solista(parte: Parte, attacchi_melodia: Dict[float, int],
                    respiro: float = 2.0) -> List[Tuple[float, float]]:
    """Intervalli in cui la parte sta effettivamente suonando la melodia."""
    suonate = [e for e in parte.eventi
               if not e.pausa and round(e.inizio, 6) in attacchi_melodia]
    tratti: List[List[float]] = []
    for e in suonate:
        if tratti and e.inizio - tratti[-1][1] < respiro - 1e-6:
            tratti[-1][1] = e.fine
        else:
            tratti.append([e.inizio, e.fine])
    return [(a, b) for a, b in tratti]


def _dirada_parte(p: Parte, a: float, b: float,
                  attacchi_melodia: Dict[float, int],
                  ripristina: bool = False) -> None:
    st = strumento(p.strumento)
    # dinamica in vigore prima del tratto, da rimettere dopo (`ripristina`)
    segnate = [e for e in p.eventi if e.dinamica and e.inizio <= a + 1e-6]
    prima = max(segnate, key=lambda e: e.inizio).dinamica if segnate else "mf"
    nuovi: List[Evento] = []
    for e in p.eventi:
        if e.pausa or not (e.inizio < b - 1e-6 and e.fine > a + 1e-6):
            nuovi.append(e)
            continue
        # via i raddoppi della melodia: sotto un solista debole sono deleteri
        altezza_melodia = attacchi_melodia.get(round(e.inizio, 6))
        if (altezza_melodia is not None and len(e.altezze) == 1
                and e.altezze[0] % 12 == altezza_melodia % 12
                and p.ruolo in ("melodia", "controcanto")):
            nuovi.append(Evento(inizio=e.inizio, durata=e.durata, altezze=[],
                                rigo=e.rigo))
            continue
        if st.percussione:
            # solo il primo movimento della misura
            if abs(e.inizio - a) > 1e-6 and abs(e.inizio % 4.0) > 1e-6:
                nuovi.append(Evento(inizio=e.inizio, durata=e.durata,
                                    altezze=[], rigo=e.rigo))
                continue
        if len(e.altezze) > 2:
            e.altezze = [e.altezze[0], e.altezze[-1]]
        nuovi.append(e)
    p.eventi = nuovi
    # un solo segno all'inizio del tratto: una dinamica su ogni nota rende la
    # partitura illeggibile
    primo = next((e for e in nuovi
                  if not e.pausa and a - 1e-6 <= e.inizio < b - 1e-6), None)
    if primo is not None:
        primo.dinamica = "p"
        if ripristina:
            dopo = next((e for e in sorted(nuovi, key=lambda e: e.inizio)
                         if not e.pausa and e.inizio >= b - 1e-6), None)
            if dopo is not None and not dopo.dinamica and prima != "p":
                dopo.dinamica = prima


def distribuisci_frammenti(parti: List[Parte], frammenti: List[List[Nota]],
                           liv: str, misure: List[Misura],
                           lingua: str = "it") -> List[str]:
    """
    Affida gli incisi rimasti (scale, volatine, riempimenti) agli strumenti
    che in quel punto tacciono. A rotazione, cosi' che il materiale si
    distribuisca invece di ammucchiarsi su una parte sola.
    """
    note_report: List[str] = []
    candidati = [p for p in parti
                 if not strumento(p.strumento).percussione and p.righi == 1]
    # prima i monodici (fiati, archi): una scala su una chitarra strimpellata
    # non si sente, su un flauto si'
    candidati.sort(key=lambda p: (not strumento(p.strumento).monofonico,
                                  p.ruolo == "basso"))
    if not candidati:
        return note_report
    turno = 0
    for frammento in frammenti:
        a = frammento[0].inizio
        b = frammento[-1].fine
        # 1) chi tace; 2) chi sta facendo solo riempimento armonico: un inciso
        #    dell'originale vale piu' di un pad inventato
        scelto = None
        for priorita in ("tace", "armonia", "controcanto"):
            for k in range(len(candidati)):
                p = candidati[(turno + k) % len(candidati)]
                if priorita == "tace" and not _tace_in(p, a, b):
                    continue
                if priorita != "tace" and p.ruolo != priorita:
                    continue
                st = strumento(p.strumento)
                lo, hi = st.ambito(liv)
                scarto = _ottava_migliore([n.midi for n in frammento], lo, hi)
                if any(not (lo <= n.midi + scarto <= hi) for n in frammento):
                    continue
                scelto = (p, scarto, priorita)
                turno = (turno + k + 1) % len(candidati)
                break
            if scelto:
                break
        if scelto is None:
            continue
        p, scarto, priorita = scelto
        eventi = [Evento(inizio=n.inizio, durata=n.durata,
                         altezze=[n.midi + scarto], letterale=True)
                  for n in frammento]
        if _sostituisci_span(p, eventi):
            note_report.append(testo(
                "inciso" if priorita == "tace" else "inciso_al_posto", lingua,
                parte=p.nome, mis=_numero_misura(misure, a)))
    return note_report


def _numero_misura(misure: List[Misura], t: float) -> str:
    for m in misure:
        if m.inizio - 1e-6 <= t < m.fine - 1e-6:
            return "levare" if m.anacrusi else str(m.numero)
    return "?"


def _sostituisci_span(parte: Parte, eventi: List[Evento]) -> bool:
    """Rimpiazza il contenuto della parte nell'intervallo coperto dagli eventi."""
    if not eventi:
        return False
    a, b = eventi[0].inizio, eventi[-1].fine
    rigo = next((e.rigo for e in parte.eventi
                 if e.inizio < b - 1e-6 and e.fine > a + 1e-6), 1)
    for nuovo in eventi:
        nuovo.rigo = rigo
    tenuti: List[Evento] = []
    for e in parte.eventi:
        if e.rigo != rigo or e.fine <= a + 1e-6 or e.inizio >= b - 1e-6:
            tenuti.append(e)
            continue
        if e.inizio < a - 1e-6:
            tenuti.append(Evento(inizio=e.inizio, durata=a - e.inizio,
                                 altezze=list(e.altezze), rigo=rigo,
                                 letterale=e.letterale))
        if e.fine > b + 1e-6:
            tenuti.append(Evento(inizio=b, durata=e.fine - b,
                                 altezze=list(e.altezze), rigo=rigo,
                                 letterale=e.letterale))
    parte.eventi = sorted(tenuti + eventi, key=lambda e: (e.rigo, e.inizio))
    return True


def _tace_in(parte: Parte, a: float, b: float) -> bool:
    return all(e.pausa for e in parte.eventi
               if e.inizio < b - 1e-6 and e.fine > a + 1e-6)


def _inserisci_blocco(parte: Parte, eventi: List[Evento]) -> bool:
    """Sostituisce le pause di una parte con gli eventi indicati."""
    if not eventi:
        return False
    a, b = eventi[0].inizio, eventi[-1].fine
    risultato: List[Evento] = []
    inserito = False
    for e in parte.eventi:
        if e.pausa and e.inizio < b - 1e-6 and e.fine > a + 1e-6:
            if a - e.inizio > 1e-6:
                risultato.append(Evento(inizio=e.inizio, durata=a - e.inizio,
                                        altezze=[], rigo=e.rigo))
            if not inserito:
                for nuovo in eventi:
                    nuovo.rigo = e.rigo
                    risultato.append(nuovo)
                inserito = True
            if e.fine - b > 1e-6:
                risultato.append(Evento(inizio=b, durata=e.fine - b,
                                        altezze=[], rigo=e.rigo))
        else:
            risultato.append(e)
    if inserito:
        parte.eventi = sorted(risultato, key=lambda e: (e.rigo, e.inizio))
    return inserito


def _copertura(ev: List[Evento]) -> List[Tuple[float, float]]:
    if not ev:
        return []
    intervalli = sorted((e.inizio, e.fine) for e in ev)
    unione = [list(intervalli[0])]
    for a, b in intervalli[1:]:
        if a <= unione[-1][1] + 1e-6:
            unione[-1][1] = max(unione[-1][1], b)
        else:
            unione.append([a, b])
    return [(a, b) for a, b in unione]


def _intervalli_liberi(coperto: List[Tuple[float, float]], inizio: float, fine: float,
                       minimo: float = 0.5) -> List[Tuple[float, float]]:
    liberi = []
    t = inizio
    for a, b in coperto:
        if a - t > minimo:
            liberi.append((t, a))
        t = max(t, b)
    if fine - t > minimo:
        liberi.append((t, fine))
    return liberi


def _sotto_analisi(analisi: Analisi, a: float, b: float) -> Analisi:
    return Analisi(
        melodia=[n for n in analisi.melodia if a - 1e-6 <= n.inizio < b - 1e-6],
        armonia=[Accordo(inizio=max(x.inizio, a), durata=min(x.fine, b) - max(x.inizio, a),
                         fondamentale=x.fondamentale, qualita=x.qualita, basso=x.basso,
                         confidenza=x.confidenza)
                 for x in analisi.armonia if x.inizio < b - 1e-6 and x.fine > a + 1e-6],
        basso=[n for n in analisi.basso if a - 1e-6 <= n.inizio < b - 1e-6],
        groove=analisi.groove, suddivisione=analisi.suddivisione, frasi=analisi.frasi,
    )
