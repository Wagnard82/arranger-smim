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

from typing import Dict, List, Set, Tuple

from .modello import Misura


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
