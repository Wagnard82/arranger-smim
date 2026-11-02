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
from typing import Dict, List, Set, Tuple

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


def ordine_con_esito(misure: List[Misura]) -> Tuple[List[int], str]:
    """
    Indici delle misure nell'ordine in cui si suonano, e l'esito:
    "" se tutto torna, "ciclo" o "destinazione" se i segni non sono
    coerenti; in quei due casi l'ordine e' quello scritto.
    """
    n = len(misure)
    lineare = list(range(n))
    if not ha_segni(misure):
        return lineare, ""
    r_ = [m.ripresa for m in misure]
    ultima = _ultima_volta(misure)
    # senza nessun |: ogni :| torna all'inizio del brano
    nessun_inizio = not any(r.ritornello_inizio for r in r_)

    ordine: List[int] = []
    i, passo, inizio_rit = 0, 1, 0
    eseguiti: Dict[int, int] = {}
    dopo_salto, salti_fatti, indice_salto = False, set(), -1
    while i < n:
        r = r_[i]
        if r.ritornello_inizio and not dopo_salto and inizio_rit != i:
            inizio_rit, passo = i, 1
        if r.volte:
            volta = ultima[i] if dopo_salto else passo
            if volta not in r.volte:
                i += 1            # misura di un'altra volta: si salta
                continue
        ordine.append(i)
        if len(ordine) > 4 * n:
            return lineare, "ciclo"
        if dopo_salto and r.fine:
            break
        if dopo_salto and r.al_coda:
            arrivo = next((k for k in range(indice_salto + 1, n) if r_[k].coda), None)
            if arrivo is None:
                return lineare, "destinazione"
            i = arrivo
            continue
        if not dopo_salto and r.ritornello_fine:
            fatte = eseguiti.get(i, 0)
            if fatte < r.ritornello_fine - 1:
                eseguiti[i] = fatte + 1
                passo += 1
                i = inizio_rit
                continue
            passo = 1             # ritornello finito
            if not nessun_inizio:
                inizio_rit = i + 1
        if r.salto and i not in salti_fatti:
            salti_fatti.add(i)
            indice_salto = i
            if r.salto == "ds":
                segni = [k for k in range(n) if r_[k].segno]
                if not segni:
                    return lineare, "destinazione"
                prima = [k for k in segni if k <= i]
                arrivo = prima[-1] if prima else segni[0]
            else:
                arrivo = 0
            if r.salto_verso == "coda" and not any(r_[k].coda for k in range(i + 1, n)):
                return lineare, "destinazione"
            dopo_salto = True
            i = arrivo
            continue
        i += 1
    return ordine, ""


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

    # volte senza un :| che le chiuda
    i = 0
    while i < n:
        if not r_[i].volte:
            i += 1
            continue
        j = i
        while j < n and r_[j].volte:
            j += 1
        if not any(r_[k].ritornello_fine for k in range(i, j)):
            avvisi.append(t("ripresa_volta_fuori", lingua, mis=num[i]))
        i = j
    # :| dopo un altro :| senza un |: in mezzo
    ultimo_fine = -1
    for i, r in enumerate(r_):
        if r.ritornello_inizio:
            ultimo_fine = -1
        if r.ritornello_fine:
            if ultimo_fine >= 0:
                avvisi.append(t("ripresa_senza_inizio", lingua, mis=num[i]))
            ultimo_fine = i
    # salti senza destinazione
    for i, r in enumerate(r_):
        if r.salto == "ds" and not any(x.segno for x in r_):
            avvisi.append(t("ripresa_ds_senza_segno", lingua, mis=num[i]))
        if (r.salto and r.salto_verso == "coda"
                and not any(x.coda for x in r_[i + 1:])):
            avvisi.append(t("ripresa_coda_mancante", lingua, mis=num[i]))
        if r.salto and r.salto_verso == "fine" and not any(x.fine for x in r_):
            avvisi.append(t("ripresa_fine_mancante", lingua, mis=num[i]))

    ordine, esito = ordine_con_esito(misure)
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
