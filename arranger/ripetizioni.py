"""
Segni di ripresa: ritornelli, volte, D.S., D.C., Coda, Fine.

Si arrangia la forma SCRITTA, una volta sola: le ripetizioni suonano
identiche e i segni tornano in partitura nelle stesse misure
dell'originale. Questo modulo sa in che ordine le misure si suonano
davvero, e serve a tre cose:

  * il MIDI di anteprima, che deve seguire la forma vera;
  * i confini di ripresa, oltre i quali nessuna nota puo' essere tenuta
    (dopo la fine di un ritornello non si suona la misura scritta dopo);
  * i controlli di coerenza che finiscono nel report.

Convenzione dopo un D.S. o un D.C.: i ritornelli non si ripetono e delle
volte si suona l'ultima. «To Coda» e «Fine» valgono solo dopo il salto.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Dict, List, Optional, Set, Tuple

from .lingua import t
from .modello import Evento, Misura, Partitura


def ha_segni(misure: List[Misura]) -> bool:
    """True se almeno una misura porta un segno di ripresa."""
    return any(not m.ripresa.vuoti for m in misure)


def _ultima_volta(misure: List[Misura]) -> List[int]:
    """Per ogni misura dentro le volte, il numero piu' alto del suo gruppo
    di volte (misure contigue con volte); 0 fuori dalle volte."""
    n = len(misure)
    ultima = [0] * n
    i = 0
    while i < n:
        if not misure[i].ripresa.volte:
            i += 1
            continue
        j = i
        while j < n and misure[j].ripresa.volte:
            j += 1
        massimo = max(max(misure[k].ripresa.volte) for k in range(i, j))
        for k in range(i, j):
            ultima[k] = massimo
        i = j
    return ultima


def _gruppi_volte(misure: List[Misura]) -> List[Optional[Tuple[int, int]]]:
    """Per ogni misura dentro le volte, il suo gruppo di volte come
    (prima misura, misura dopo l'ultima); None fuori dalle volte."""
    n = len(misure)
    gruppi: List[Optional[Tuple[int, int]]] = [None] * n
    i = 0
    while i < n:
        if not misure[i].ripresa.volte:
            i += 1
            continue
        j = i
        while j < n and misure[j].ripresa.volte:
            j += 1
        for k in range(i, j):
            gruppi[k] = (i, j)
        i = j
    return gruppi


def _strutture(misure: List[Misura]) -> List[Tuple[int, int]]:
    """
    Le strutture di ripresa: da un |: (o dall'inizio) fino al |: dopo
    (escluso). Per ogni misura, i limiti della sua struttura.
    """
    n = len(misure)
    inizi = [0] + [i for i, m in enumerate(misure) if m.ripresa.ritornello_inizio and i > 0]
    limiti: List[Tuple[int, int]] = [(0, n)] * n
    for k, a in enumerate(inizi):
        b = inizi[k + 1] if k + 1 < len(inizi) else n
        for i in range(a, b):
            limiti[i] = (a, b)
    return limiti


def _ordina(misure: List[Misura]) -> Tuple[List[int], str, List[Tuple[str, int, int]]]:
    """
    L'ordine di esecuzione, l'esito ("", "ciclo", "destinazione") e le note
    per il report: ("senza_inizio", misura del :|, misura d'arrivo) quando
    un :| non torna a un |:, ("volta_mancante", misura, passaggio) quando
    per un passaggio non c'e' la sua volta.

    Regole, ricavate dai MusicXML veri (Let It Be, Never Gonna Give You
    Up, Für Elise esportati da MuseScore):
      * un :| torna al |: piu' vicino; se il ritornello prima e' gia'
        finito, alla misura dopo; senza nessun |: nel brano, all'inizio;
      * i passaggi si contano per struttura (dal |: al |: dopo): un
        ritornello con le volte e' finito solo quando si esce dalle volte
        all'ultimo passaggio previsto, cioe' al numero di volta piu' alto
        della struttura (Let It Be: 1a e 2a volta, poi un :| e la 3a);
      * se in un gruppo di volte manca quella del passaggio in corso, si
        va avanti fino alla volta giusta, anche lontana; se non c'e', si
        prosegue dopo il gruppo.
    """
    n = len(misure)
    lineare = list(range(n))
    note: List[Tuple[str, int, int]] = []
    if not ha_segni(misure):
        return lineare, "", note
    r_ = [m.ripresa for m in misure]
    ultima = _ultima_volta(misure)
    gruppi = _gruppi_volte(misure)
    strutture = _strutture(misure)
    massima = {}
    for a, b in set(strutture):
        massima[a] = max((max(r_[k].volte) for k in range(a, b) if r_[k].volte), default=0)
    nessun_inizio = not any(r.ritornello_inizio for r in r_)

    ordine: List[int] = []
    i, passo, inizio_rit = 0, 1, 0
    eseguiti: Dict[int, int] = {}
    dopo_salto, salti_fatti, indice_salto = False, set(), -1
    visitata = -1                 # ultima misura guardata, suonata o saltata
    while i < n:
        r = r_[i]
        # uscendo in avanti dalle volte all'ultimo passaggio della
        # struttura, il ritornello e' finito
        if (not dopo_salto and not r.volte and visitata >= 0 and i == visitata + 1
                and r_[visitata].volte
                and passo >= massima[strutture[visitata][0]]):
            passo = 1
            if not nessun_inizio:
                inizio_rit = i
        visitata = i
        if r.ritornello_inizio and not dopo_salto and inizio_rit != i:
            inizio_rit, passo = i, 1
        if r.volte:
            volta = ultima[i] if dopo_salto else passo
            if volta not in r.volte:
                a, b = gruppi[i]
                nel_gruppo = any(volta in r_[k].volte for k in range(a, b))
                if not nel_gruppo and not dopo_salto:
                    fine_struttura = strutture[i][1]
                    arrivo = next((k for k in range(b, fine_struttura)
                                   if r_[k].volta_apre and volta in r_[k].volte), None)
                    if arrivo is not None:
                        i = arrivo
                        continue
                    if i == a:
                        note.append(("volta_mancante", i, volta))
                i += 1            # misura di un'altra volta: si salta
                continue
        ordine.append(i)
        if len(ordine) > 4 * n:
            return lineare, "ciclo", note
        if dopo_salto and r.fine:
            break
        if dopo_salto and r.al_coda:
            arrivo = next((k for k in range(indice_salto + 1, n) if r_[k].coda), None)
            if arrivo is None:
                return lineare, "destinazione", note
            i = arrivo
            continue
        if not dopo_salto and r.ritornello_fine:
            fatte = eseguiti.get(i, 0)
            if fatte < r.ritornello_fine - 1:
                eseguiti[i] = fatte + 1
                passo += 1
                if not r_[inizio_rit].ritornello_inizio and any(
                        x.ritornello_fine for x in r_[:i]):
                    note.append(("senza_inizio", i, inizio_rit))
                i = inizio_rit
                continue
            if not r.volte:       # ritornello senza volte finito
                passo = 1
                if not nessun_inizio:
                    inizio_rit = i + 1
        if r.salto and i not in salti_fatti:
            salti_fatti.add(i)
            indice_salto = i
            if r.salto == "ds":
                segni = [k for k in range(n) if r_[k].segno]
                if not segni:
                    return lineare, "destinazione", note
                prima = [k for k in segni if k <= i]
                arrivo = prima[-1] if prima else segni[0]
            else:
                arrivo = 0
            if r.salto_verso == "coda" and not any(r_[k].coda for k in range(i + 1, n)):
                return lineare, "destinazione", note
            dopo_salto = True
            i = arrivo
            continue
        i += 1
    return ordine, "", note


def ordine_con_esito(misure: List[Misura]) -> Tuple[List[int], str]:
    """
    Indici delle misure nell'ordine in cui si suonano, e l'esito:
    "" se tutto torna, "ciclo" o "destinazione" se i segni non sono
    coerenti; in quei due casi l'ordine e' quello scritto.
    """
    ordine, esito, _note = _ordina(misure)
    return ordine, esito


def ordine_esecuzione(misure: List[Misura]) -> List[int]:
    """Indici delle misure nell'ordine in cui si suonano."""
    return ordine_con_esito(misure)[0]


def confini(misure: List[Misura]) -> Set[int]:
    """
    Misure dopo le quali, almeno in un passaggio, non si suona la misura
    scritta successiva: fine di un ritornello, ultima misura prima di una
    volta, fine di una volta, salti, «To Coda», Fine.
    """
    ordine = ordine_esecuzione(misure)
    n = len(misure)
    fuori: Set[int] = set()
    for k, i in enumerate(ordine):
        if k + 1 < len(ordine):
            if ordine[k + 1] != i + 1:
                fuori.add(i)
        elif i + 1 < n:
            fuori.add(i)
    return fuori


def _intervalli(numeri: List[int]) -> str:
    """[1, 2, 3, 1, 2, 6] -> "1-3, 1-2, 6"."""
    gruppi: List[List[int]] = []
    for x in numeri:
        if gruppi and x == gruppi[-1][-1] + 1:
            gruppi[-1].append(x)
        else:
            gruppi.append([x])
    return ", ".join(str(g[0]) if len(g) == 1 else f"{g[0]}-{g[-1]}" for g in gruppi)


def controlla(misure: List[Misura], lingua: str) -> List[str]:
    """
    Messaggi di report sui segni di ripresa: la forma riconosciuta, la
    convenzione seguita dopo i salti e le strutture incoerenti. Un brano
    senza segni non produce nessun messaggio.
    """
    if not ha_segni(misure):
        return []
    r_ = [m.ripresa for m in misure]
    n = len(misure)
    num = [m.numero for m in misure]
    avvisi: List[str] = []

    # volte senza nessun :| in tutta la loro struttura (dal |: al |: dopo):
    # l'ultima volta non ha il :|, e nemmeno una volta che ne precede
    # un'altra con il :| piu' avanti (Never Gonna Give You Up, m9)
    strutture = _strutture(misure)
    gruppi = _gruppi_volte(misure)
    for i in range(n):
        if r_[i].volte and gruppi[i][0] == i:
            a, b = strutture[i]
            if not any(r_[k].ritornello_fine for k in range(a, b)):
                avvisi.append(t("ripresa_volta_fuori", lingua, mis=num[i]))
    # salti senza destinazione
    for i, r in enumerate(r_):
        if r.salto == "ds" and not any(x.segno for x in r_):
            avvisi.append(t("ripresa_ds_senza_segno", lingua, mis=num[i]))
        if (r.salto and r.salto_verso == "coda"
                and not any(x.coda for x in r_[i + 1:])):
            avvisi.append(t("ripresa_coda_mancante", lingua, mis=num[i]))
        if r.salto and r.salto_verso == "fine" and not any(x.fine for x in r_):
            avvisi.append(t("ripresa_fine_mancante", lingua, mis=num[i]))

    ordine, esito, note = _ordina(misure)
    for tipo, i, x in note:
        if tipo == "senza_inizio":
            avvisi.append(t("ripresa_senza_inizio", lingua, mis=num[i], da=num[x]))
        elif tipo == "volta_mancante":
            avvisi.append(t("ripresa_volta_mancante", lingua, mis=num[i], n=x))
    if esito:
        return avvisi + [t("ripresa_lineare", lingua)]
    righe = [t("ripresa_forma", lingua, misure=_intervalli([num[i] for i in ordine]))]
    if any(r.salto for r in r_):
        righe.append(t("ripresa_convenzione", lingua))
    return righe + avvisi


def taglia_ai_confini(partitura: Partitura) -> int:
    """
    Spezza ogni evento che attraversa un confine di ripresa e toglie le
    legature di valore che lo superano: oltre il confine, in almeno un
    passaggio, non si suona la misura scritta dopo. Le altezze non
    cambiano, cambia solo la durata scritta.

    Restituisce quante legature di materiale `letterale` (copiato
    dall'originale) sono state interrotte, per il report.
    """
    tempi = sorted(partitura.misure[i].fine for i in confini(partitura.misure))
    if not tempi:
        return 0
    interrotte = 0
    for parte in partitura.parti:
        nuovi: List[Evento] = []
        for e in parte.eventi:
            pezzi = [e]
            for x in tempi:
                ultimo = pezzi[-1]
                if ultimo.inizio < x - 1e-6 and ultimo.fine > x + 1e-6:
                    if not ultimo.pausa and ultimo.letterale:
                        interrotte += 1
                    prima = replace(ultimo, durata=x - ultimo.inizio,
                                    altezze=list(ultimo.altezze),
                                    legata_dopo=False, fine_gradazione=False)
                    dopo = replace(ultimo, inizio=x, durata=ultimo.fine - x,
                                   altezze=list(ultimo.altezze), gradazione=None)
                    pezzi[-1:] = [prima, dopo]
            for pz in pezzi:
                if pz.legata_dopo and any(abs(pz.fine - x) < 1e-6 for x in tempi):
                    pz.legata_dopo = False
                    if pz.letterale:
                        interrotte += 1
            nuovi.extend(pezzi)
        parte.eventi = nuovi
    return interrotte


def srotola_eventi(eventi: List[Evento], misure: List[Misura]) -> List[Evento]:
    """
    Gli eventi di una parte al tempo di ESECUZIONE, misura per misura
    nell'ordine in cui si suonano; le pause si lasciano fuori. Una nota
    legata alla misura dopo resta una nota sola se quella misura si suona
    davvero subito dopo. Serve al MIDI di anteprima.
    """
    from .esportatore import taglia_su_misura   # qui: import circolare
    fuori: List[Evento] = []
    aperti: Dict[Tuple[Tuple[int, ...], int], Evento] = {}
    t = 0.0
    precedente = -2
    for i in ordine_esecuzione(misure):
        m = misure[i]
        if i != precedente + 1:
            aperti = {}
        ancora: Dict[Tuple[Tuple[int, ...], int], Evento] = {}
        for frammento, legato_prima, legato_dopo in taglia_su_misura(eventi, m):
            if frammento.pausa:
                continue
            chiave = (tuple(frammento.altezze), frammento.rigo)
            if legato_prima and chiave in aperti \
                    and abs(frammento.inizio - m.inizio) < 1e-6:
                ev = aperti.pop(chiave)
                ev.durata += frammento.durata
            else:
                ev = replace(frammento, inizio=frammento.inizio - m.inizio + t,
                             altezze=list(frammento.altezze))
                fuori.append(ev)
            if legato_dopo:
                ancora[chiave] = ev
        aperti = ancora
        precedente = i
        t += m.durata
    return fuori
