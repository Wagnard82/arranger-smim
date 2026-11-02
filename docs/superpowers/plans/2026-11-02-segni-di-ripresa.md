# Segni di ripresa — piano d'implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Obiettivo:** riconoscere ritornelli, volte, Segno, Coda, D.S., D.C. e
Fine nel MusicXML d'ingresso; riscriverli nelle stesse misure della
partitura arrangiata; suonare la forma srotolata nel MIDI di anteprima.

**Architettura:**
- Un campo nuovo `Misura.ripresa: SegniRipresa`, riempito
  dall'ingestione e trasportato in `Partitura.misure`.
- Un modulo nuovo, `arranger/ripetizioni.py`, calcola l'ordine di
  esecuzione, i confini di ripresa e i controlli, e taglia gli eventi ai
  confini.
- Esportatori MusicXML, MIDI e LilyPond leggono i segni dalle misure.
- L'orchestratore non cambia.

**Tecnologie:** Python 3.12, solo libreria standard. I test sono in
`tests/test_pipeline.py`, con la funzione `verifica(cond, msg)` e senza
framework.

**Specifica:** `docs/superpowers/specs/2026-11-02-segni-di-ripresa-design.md`

## Vincoli globali

- Il nucleo usa solo la libreria standard.
- Commenti e docstring sono in italiano. Ogni testo che arriva
  all'utente va in `arranger/lingua.py`, IT ed EN, con gli stessi
  segnaposto: compresi «D.S. al Coda», «Fine» e «Al Coda».
  - *Deroga alla specifica:* la specifica diceva «non si traducono».
    L'unica differenza è «Al Coda» (IT) contro «To Coda» (EN); il resto
    è identico nelle due lingue.
- `arranger/modello.py`: si aggiunge, senza ristrutturare.
- La melodia non cambia mai in altezza. Ai confini cambia solo la durata
  scritta.
- Il metro non si tocca: le misure parziali (anacrusi, levare di
  sezione) restano come sono.
- Un brano senza segni produce MusicXML e MIDI **identici** a oggi.
- Test: `source .venv312/bin/activate && python tests/test_pipeline.py`.
  L'ultima riga deve essere `N verifiche superate, 0 fallite`.
- **Commit:** solo con i file del task. In `main` ci sono modifiche non
  correlate (`account.py`, `landing/`, `server.py`, `.gitignore`,
  `.streamlit/secrets.toml.esempio`): **non vanno aggiunte.** Non si fa
  push fino al rilascio (Task 9).

## Punti da controllare in revisione

1. **Segni presenti solo nella prima parte, ma usati per tutte.**
   MuseScore scrive i `<words>` solo sul rigo superiore. Ci si aspetta
   che l'ordine sia lo stesso. Test nel Task 1: `ds_al_coda.xml` ha i
   testi solo nella parte 1 di due.
2. **MuseScore scrive sia `<words>` sia `<sound>` sullo stesso salto.**
   Ci si aspetta un salto solo, non due. Test nel Task 1: `volte.xml`
   (variante con entrambi) dà `salto == "ds"` una volta sola.
3. **Volta «1, 2» seguita dalla 3ª con `times="3"`.** Ci si aspetta
   l'ordine giusto. Test nel Task 2.
4. **Nota della melodia `letterale` tenuta nella 1ª volta.** Ci si
   aspetta il taglio senza cambio d'altezza e la riga nel report. Test
   nel Task 4.
5. **Brano con `|:` sull'anacrusi e ultima misura parziale.** Ci si
   aspetta che le durate delle misure siano conservate e che il MIDI duri
   2 × 12 quarti. Test nei Task 1 e 6.

---

### Task 1: modello `SegniRipresa`, esempi e lettura dall'ingestione

**File:**
- Modifica: `arranger/modello.py` (dataclass nuova sopra `Misura`, campo
  in `Misura`)
- Modifica: `arranger/ingestione.py` (nuova `_segni_ripresa`, chiamata in
  `da_musicxml` dopo `_griglia_misure`)
- Modifica: `esempi/genera_esempi.py` (5 generatori nuovi)
- Test: `tests/test_pipeline.py`

**Interfacce:**
- Produce `SegniRipresa`, con i campi esatti della specifica e la
  proprietà `vuoti`.
- Produce `Misura.ripresa: SegniRipresa = field(default_factory=SegniRipresa)`.
- Produce `ingestione._segni_ripresa(parti: List[ET.Element]) -> Dict[int, SegniRipresa]`.
- Produce in `genera_esempi`: `ritornello(p)`, `volte(p)`,
  `ds_al_coda(p)`, `dc_al_fine(p)` e `ritornello_levare(p)`. Ognuno
  restituisce il percorso.

**Esempi da generare.** Melodia semplice in Do, una nota per quarto,
pianoforte con `_intestazione`/`_attributi`. `ds_al_coda` ha una seconda
parte, un Violino, con le stesse stanghette ma **senza** direzioni.

| File | Misure (numero: segni) | Canale |
|---|---|---|
| `ritornello.xml` | 8; m3 `|:`, m6 `:|` | barline |
| `volte.xml` | 7; m1 `|:`; m5 volta 1 start+stop e `:|`; m6 volta 2 start e discontinue; m7 | barline |
| `ds_al_coda.xml` | 9; m3 `<segno/>`; m5 `<coda/>` + words «To Coda»; m7 words «D.S. al Coda»; m8 `<coda/>` | solo `<words>`/simboli |
| `dc_al_fine.xml` | 6; m4 `<sound fine="yes"/>`; m6 `<sound dacapo="yes"/>` | solo `<sound>` |
| `ritornello_levare.xml` | anacrusi m0 di 1 quarto con `|:`; m1, m2; m3 di 3 quarti con `:|` (ultima misura) | barline |

`volte.xml` ha anche una variante con D.S. doppio (words + sound sulla
stessa misura). Generala in coda al file della 2ª parte del test con
`volte(p, doppio=True)`: m3 `<segno/>`, m7 words «D.S.» +
`<sound dalsegno="s1"/>`.

- [ ] **Step 1: scrivi il test che fallisce**

```python
def test_lettura_segni_ripresa(es):
    """es: dizionario nome -> percorso degli esempi di ripresa."""
    sp = ingestione.ingerisci(es["ritornello"])
    r = [m.ripresa for m in sp.misure]
    verifica(r[2].ritornello_inizio and r[5].ritornello_fine == 2, "ritornello m3-m6")
    verifica(sum(not x.vuoti for x in r) == 2, "solo due misure con segni")

    r = [m.ripresa for m in ingestione.ingerisci(es["volte"]).misure]
    verifica(r[4].volte == (1,) and r[4].volta_apre and r[4].volta_chiude == "stop", "1a volta")
    verifica(r[5].volte == (2,) and r[5].volta_chiude == "discontinue", "2a volta")

    r = [m.ripresa for m in ingestione.ingerisci(es["ds_al_coda"]).misure]
    verifica(r[2].segno and r[4].coda and r[4].al_coda and r[7].coda, "segno e code")
    verifica((r[6].salto, r[6].salto_verso, r[6].testo_salto) == ("ds", "coda", "D.S. al Coda"),
             "D.S. al Coda dai words, letto anche se il violino non lo porta")

    r = [m.ripresa for m in ingestione.ingerisci(es["dc_al_fine"]).misure]
    verifica(r[3].fine and (r[5].salto, r[5].salto_verso) == ("dc", "fine"),
             "D.C. al Fine dai soli <sound>")

    r = [m.ripresa for m in ingestione.ingerisci(es["volte_doppio"]).misure]
    verifica(r[6].salto == "ds" and r[6].salto_verso == "", "words + sound = un salto")

    sp = ingestione.ingerisci(es["ritornello_levare"])
    verifica([m.durata for m in sp.misure] == [1.0, 4.0, 4.0, 3.0], "durate col levare")
    verifica(sp.misure[0].ripresa.ritornello_inizio and sp.misure[3].ripresa.ritornello_fine == 2,
             "ritornello sull'anacrusi")

    sp = ingestione.ingerisci(es["inno"])
    verifica(all(m.ripresa.vuoti for m in sp.misure), "inno: nessun segno")
```

`prepara()` genera i 6 file in `esempi/` e restituisce in più il
dizionario `es`, con le chiavi `ritornello`, `volte`, `volte_doppio`,
`ds_al_coda`, `dc_al_fine`, `ritornello_levare` e `inno` (il percorso
`a` dell'Inno alla gioia). In `__main__` chiama
`test_lettura_segni_ripresa(es)`; i test dei task successivi ricevono lo
stesso `es`.

- [ ] **Step 2: esegui i test e controlla che falliscano**

Esegui `python tests/test_pipeline.py`. Risultato atteso:
`AttributeError: 'Misura' object has no attribute 'ripresa'`, oppure
`genera_esempi` senza `ritornello`.

- [ ] **Step 3: implementa modello, esempi e `_segni_ripresa`**

**Regole di lettura** (tabella della specifica):
- `times` assente vale 2.
- Le misure fra un `ending start` e il suo `stop`/`discontinue`
  ereditano `volte`.
- `number="1, 2"` e `"1.2."` danno `(1, 2)`.

**Riconoscimento dei testi.** Normalizza con minuscole, senza punti e
senza spazi:
- `ds`/`dalsegno` all'inizio → `salto = "ds"`;
- `dc`/`dacapo` → `salto = "dc"`;
- `alcoda` in coda → `salto_verso = "coda"`, `alfine` → `"fine"`;
- `tocoda`/`alcoda`/`vaiallacoda` da soli → `al_coda`;
- `fine` → `fine`;
- `coda` da solo → `coda`.

**Origine e destinazione dei segni:**
- Segno, Coda e i salti vanno all'indice della misura in cui compaiono,
  in qualunque parte.
- `<sound tocoda>` imposta `al_coda`, `<sound fine>` imposta `fine`,
  `<sound dalsegno>` dà `salto = "ds"`, `<sound dacapo="yes">` dà `"dc"`.
- Il testo letto va in `testo_salto` solo se è un salto.

In `da_musicxml`, dopo la costruzione di `misure`, assegna
`misure[i].ripresa = segni[i]` per ogni `i` presente.

- [ ] **Step 4: esegui i test e controlla che passino**

Esegui `python tests/test_pipeline.py`. Risultato atteso: `0 fallite`,
compreso il controllo che MusicXML e MIDI dell'Inno non cambino (i test
già esistenti).

- [ ] **Step 5: commit**

```bash
git add arranger/modello.py arranger/ingestione.py esempi/genera_esempi.py esempi/ritornello.xml esempi/volte.xml esempi/volte_doppio.xml esempi/ds_al_coda.xml esempi/dc_al_fine.xml esempi/ritornello_levare.xml tests/test_pipeline.py
git commit -m "Segni di ripresa: modello e lettura dal MusicXML"
```

---

### Task 2: ordine di esecuzione e confini (`arranger/ripetizioni.py`)

**File:**
- Crea: `arranger/ripetizioni.py`
- Test: `tests/test_pipeline.py`

**Interfacce:**
- Usa `Misura.ripresa` (Task 1).
- Produce `ha_segni(misure: List[Misura]) -> bool`.
- Produce `ordine_con_esito(misure: List[Misura]) -> Tuple[List[int], str]`.
  Il secondo valore è `""`, `"ciclo"` oppure `"destinazione"`; negli
  ultimi due casi l'ordine è lineare.
- Produce `ordine_esecuzione(misure) -> List[int]`, cioè il primo valore
  di `ordine_con_esito`.
- Produce `confini(misure) -> Set[int]`.

- [ ] **Step 1: scrivi il test che fallisce**

```python
def test_ordine_esecuzione(es):
    from arranger import ripetizioni
    from arranger.modello import SegniRipresa
    def numeri(nome):
        sp = ingestione.ingerisci(es[nome])
        return [sp.misure[i].numero for i in ripetizioni.ordine_esecuzione(sp.misure)]
    verifica(numeri("ritornello") == [1,2,3,4,5,6,3,4,5,6,7,8], "ritornello")
    verifica(numeri("volte") == [1,2,3,4,5,1,2,3,4,6,7], "volte")
    verifica(numeri("ds_al_coda") == [1,2,3,4,5,6,7,3,4,5,8,9], "D.S. al Coda, coda doppia")
    verifica(numeri("dc_al_fine") == [1,2,3,4,5,6,1,2,3,4], "D.C. al Fine")
    verifica(numeri("ritornello_levare") == [0,1,2,3,0,1,2,3], "ritornello col levare")

    def finte(segni):            # misure da 4/4 con i segni dati per indice
        ms = [Misura(i + 1, 4.0 * i, 4.0) for i in range(len(segni))]
        for m, s in zip(ms, segni):
            m.ripresa = s or SegniRipresa()
        return ms
    S = SegniRipresa
    ms = finte([S(ritornello_inizio=True), S(volte=(1, 2), volta_apre=True, volta_chiude="stop",
                ritornello_fine=3), S(volte=(3,), volta_apre=True, volta_chiude="stop"), None])
    verifica(ripetizioni.ordine_esecuzione(ms) == [0,1,0,1,0,2,3], "volta 1,2 e times=3")

    ms = finte([None, S(ritornello_fine=2), None, S(ritornello_fine=2)])
    verifica(ripetizioni.ordine_esecuzione(ms) == [0,1,0,1,2,3,0,1,2,3],
             ":| senza |: torna all'inizio")

    ms = finte([None, S(salto="ds"), None])          # D.S. senza Segno
    verifica(ripetizioni.ordine_con_esito(ms) == ([0,1,2], "destinazione"), "D.S. senza segno")

    sp = ingestione.ingerisci(es["volte"])
    verifica(ripetizioni.confini(sp.misure) == {3, 4}, "confini delle volte")
    sp = ingestione.ingerisci(es["dc_al_fine"])
    verifica(ripetizioni.confini(sp.misure) == {3, 5}, "confini D.C. al Fine")
    verifica(not ripetizioni.ha_segni(ingestione.ingerisci(es["inno"]).misure), "inno")
```

- [ ] **Step 2: esegui i test e controlla che falliscano**

Risultato atteso: `ModuleNotFoundError: arranger.ripetizioni`.

- [ ] **Step 3: implementa `ripetizioni.py`**

**Algoritmo** (la specifica non lo fissa nei dettagli):

```
gruppo_ultima[i] = massimo numero di volta nel gruppo di misure contigue con volte non vuote
i, passo, inizio_rit = 0, 1, 0
eseguiti = {}                 # indice del :| -> ripetizioni gia' fatte
dopo_salto, salti_fatti = False, set()
while i < n:
    r = misure[i].ripresa
    if r.ritornello_inizio and not dopo_salto and inizio_rit != i: inizio_rit, passo = i, 1
    if r.volte and (dopo_salto and gruppo_ultima[i] not in r.volte
                    or not dopo_salto and passo not in r.volte):
        i += 1; continue                     # misura di un'altra volta: si salta
    ordine.append(i)
    if len(ordine) > 4 * n: return lineare, "ciclo"
    if dopo_salto and r.fine: break
    if dopo_salto and r.al_coda: i = prima misura con coda dopo l'indice del salto; continue
    if not dopo_salto and r.ritornello_fine and eseguiti.get(i, 0) < r.ritornello_fine - 1:
        eseguiti[i] += 1; passo += 1; i = inizio_rit; continue
    if r.salto and i not in salti_fatti:
        salti_fatti.add(i); dopo_salto = True
        i = ultimo Segno prima di i (se manca: il primo Segno del brano) se "ds", 0 se "dc"; continue
    i += 1
```

**Casi particolari:**
- Se manca la destinazione (Segno per un D.S., Coda dopo il salto per un
  «al Coda») si restituisce l'ordine lineare con `"destinazione"`.
- Dopo un `:|` completato si azzera `passo` a 1 e `inizio_rit` diventa
  `i + 1`, così un `:|` successivo senza `|:` torna lì. Fa eccezione il
  brano senza alcun `|:`: lì un `:|` torna sempre a 0, come chiede il
  test.

**`confini`:** l'insieme degli `i` per cui esiste `k` con
`ordine[k] == i` e una di queste due condizioni:
- `k + 1 < len(ordine)` e `ordine[k + 1] != i + 1`;
- `k + 1 == len(ordine)` e `i + 1 < n`.

- [ ] **Step 4: esegui i test e controlla che passino**

Risultato atteso: `0 fallite`.

- [ ] **Step 5: commit**

```bash
git add arranger/ripetizioni.py tests/test_pipeline.py
git commit -m "Segni di ripresa: ordine di esecuzione e confini"
```

---

### Task 3: controlli e messaggi del report

**File:**
- Modifica: `arranger/ripetizioni.py`
- Modifica: `arranger/lingua.py` (messaggi nuovi in `MESSAGGI`, dopo
  `pdf_non_generato`)
- Modifica: `arranger/pipeline.py` (`esegui`, dopo l'ingestione)
- Test: `tests/test_pipeline.py`

**Interfacce:**
- Usa `ordine_con_esito` e `ha_segni` (Task 2).
- Produce `controlla(misure: List[Misura], lingua: str) -> List[str]`.
  Se `not ha_segni(misure)` restituisce `[]`.
- Produce in `MESSAGGI` le chiavi seguenti, con i segnaposto indicati:

| Chiave | Segnaposto |
|---|---|
| `ripresa_forma` | `{misure}` |
| `ripresa_convenzione` | nessuno |
| `ripresa_volta_fuori` | `{mis}` |
| `ripresa_senza_inizio` | `{mis}` |
| `ripresa_ds_senza_segno` | `{mis}` |
| `ripresa_coda_mancante` | `{mis}` |
| `ripresa_fine_mancante` | `{mis}` |
| `ripresa_lineare` | nessuno |
| `ripresa_legature_tolte` | `{n}` |

- Produce in `MESSAGGI` anche i testi dei segni:

| Chiave | IT | EN |
|---|---|---|
| `segno_ds` | «D.S.» | «D.S.» |
| `segno_ds_coda` | «D.S. al Coda» | «D.S. al Coda» |
| `segno_ds_fine` | «D.S. al Fine» | «D.S. al Fine» |
| `segno_dc` | «D.C.» | «D.C.» |
| `segno_dc_coda` | «D.C. al Coda» | «D.C. al Coda» |
| `segno_dc_fine` | «D.C. al Fine» | «D.C. al Fine» |
| `segno_al_coda` | «Al Coda» | «To Coda» |
| `segno_fine` | «Fine» | «Fine» |

**Testi dei messaggi IT:**

| Chiave | Testo |
|---|---|
| `ripresa_forma` | `[Forma] Ritornelli e salti riconosciuti: si suonano le misure {misure}.` |
| `ripresa_convenzione` | `[Forma] Dopo il D.S./D.C. i ritornelli non si ripetono e delle volte si suona l'ultima.` |
| `ripresa_volta_fuori` | `[Forma] mis. {mis}: volta fuori da un ritornello.` |
| `ripresa_senza_inizio` | `[Forma] mis. {mis}: ritornello senza segno d'inizio dopo un altro ritornello, si torna all'inizio del brano.` |
| `ripresa_ds_senza_segno` | `[Forma] mis. {mis}: D.S. senza Segno.` |
| `ripresa_coda_mancante` | `[Forma] mis. {mis}: «al Coda» senza Coda.` |
| `ripresa_fine_mancante` | `[Forma] mis. {mis}: «al Fine» senza Fine.` |
| `ripresa_lineare` | `[Forma] I segni di ripresa non sono coerenti: l'anteprima suona il brano di seguito, così com'è scritto. I segni restano in partitura.` |
| `ripresa_legature_tolte` | `[Forma] {n} legature di valore dell'originale interrotte a un ritornello o a una volta: le altezze non cambiano.` |

In EN si traduce con lo stesso prefisso tradotto (`[Form]`) e «bar»
al posto di «mis.».

- [ ] **Step 1: scrivi il test che fallisce**

```python
def test_controlli_ripresa(es):
    from arranger import ripetizioni
    from arranger.modello import SegniRipresa as S
    sp = ingestione.ingerisci(es["volte"])
    msg = ripetizioni.controlla(sp.misure, "it")
    verifica(any("1-5, 1-4, 6-7" in m for m in msg), f"forma compressa: {msg}")
    sp = ingestione.ingerisci(es["ds_al_coda"])
    verifica(any("Dopo il D.S./D.C." in m for m in ripetizioni.controlla(sp.misure, "it")),
             "convenzione dichiarata dopo un salto")
    ms = [Misura(i + 1, 4.0 * i, 4.0) for i in range(3)]
    ms[1].ripresa = S(salto="ds")
    msg = ripetizioni.controlla(ms, "en")
    verifica(any("bar 2" in m for m in msg) and any("[Form]" in m for m in msg), f"D.S. senza segno EN: {msg}")
    verifica(ripetizioni.controlla(ingestione.ingerisci(es["inno"]).misure, "it") == [], "inno muto")
    r = esegui(es["volte"], Configurazione(formazione={"flauto": 1, "violino": 1, "pianoforte": 1}),
               cartella=os.path.join(QUI, "_out_ripresa"))
    verifica(any(m.startswith("[Forma]") for m in r.report), "report della pipeline")
```

- [ ] **Step 2: esegui i test e controlla che falliscano**

Risultato atteso: `AttributeError: ... 'controlla'`.

- [ ] **Step 3: implementa `controlla`, i messaggi e la chiamata in `esegui`**

- Le misure si scrivono come intervalli di `Misura.numero` consecutivi,
  separati da «, ». Per esempio `1-5, 1-4, 6-7`; un intervallo di una
  sola misura si scrive `7`.
- In `esegui`, subito dopo `master = ...`, calcola
  `forma = ripetizioni.controlla(master.misure, cfg.lingua)`. Dopo
  `report = vincoli.valida(...)` usa `report = forma + report`.

- [ ] **Step 4: esegui i test e controlla che passino**

Risultato atteso: `0 fallite`, compreso `test_cataloghi_completi`.

- [ ] **Step 5: commit**

```bash
git add arranger/ripetizioni.py arranger/lingua.py arranger/pipeline.py tests/test_pipeline.py
git commit -m "Segni di ripresa: controlli e report IT/EN"
```

---

### Task 4: taglio degli eventi ai confini

**File:**
- Modifica: `arranger/ripetizioni.py`
- Modifica: `arranger/pipeline.py` (dopo il blocco `debug_originale`,
  prima dell'export)
- Test: `tests/test_pipeline.py`

**Interfacce:**
- Usa `confini` (Task 2) e la chiave `ripresa_legature_tolte` (Task 3).
- Produce `taglia_ai_confini(partitura: Partitura) -> int`. Restituisce
  quante legature di eventi `letterale` ha interrotto.

- [ ] **Step 1: scrivi il test che fallisce**

```python
def test_taglio_ai_confini(es):
    from arranger import ripetizioni
    from arranger.modello import Evento, Parte, Partitura
    sp = ingestione.ingerisci(es["volte"])
    T = sp.misure[3].fine                         # fine di m4, prima della 1a volta
    tenuta = Evento(inizio=T - 1, durata=2, altezze=[72], letterale=True)
    legata = Evento(inizio=T - 1, durata=1, altezze=[67], legata_dopo=True, letterale=True)
    p = Parte(id="x", nome="X", abbrev="X", strumento="flauto", eventi=[tenuta, legata,
              Evento(inizio=T, durata=1, altezze=[67])])
    part = Partitura(misure=sp.misure, parti=[p])
    n = ripetizioni.taglia_ai_confini(part)
    ev = sorted(p.eventi, key=lambda e: (e.inizio, e.altezze))
    verifica(not any(e.inizio < T - 1e-6 < e.fine - 1e-6 for e in ev), "nessun evento attraversa")
    verifica(not any(e.legata_dopo and abs(e.fine - T) < 1e-6 for e in ev), "nessuna legatura al confine")
    verifica(sorted(a for e in ev for a in e.altezze) == [67, 67, 72, 72], "altezze invariate")
    verifica(n == 2, f"due legature letterali interrotte: {n}")

    r = esegui(es["volte"], Configurazione(formazione={"flauto": 1, "violino": 1, "pianoforte": 1}),
               cartella=os.path.join(QUI, "_out_ripresa"))
    tagli = {r.partitura.misure[i].fine for i in ripetizioni.confini(r.partitura.misure)}
    for parte in r.partitura.parti:
        for e in parte.eventi:
            verifica(not any(e.inizio < T - 1e-6 < e.fine - 1e-6 for T in tagli),
                     f"{parte.nome}: evento oltre un confine a {e.inizio}")
```

- [ ] **Step 2: esegui i test e controlla che falliscano**

Risultato atteso: `AttributeError: ... 'taglia_ai_confini'`.

- [ ] **Step 3: implementa `taglia_ai_confini` e chiamala in `esegui`**

- Per ogni tempo di confine `T = misure[i].fine`, un evento con
  `inizio < T < fine` diventa due eventi, `[inizio, T)` e `[T, fine)`,
  copiati con `dataclasses.replace`. Il primo ha `legata_dopo=False`;
  la gradazione resta solo sul primo, `fine_gradazione` solo sul secondo.
- Un evento con `legata_dopo` e `fine == T` perde `legata_dopo`.
- Il conteggio aumenta solo per gli eventi `letterale`.
- In `esegui`: se il conteggio è maggiore di zero, aggiungi
  `testo("ripresa_legature_tolte", cfg.lingua, n=...)` al report.

- [ ] **Step 4: esegui i test e controlla che passino**

Risultato atteso: `0 fallite`.

- [ ] **Step 5: commit**

```bash
git add arranger/ripetizioni.py arranger/pipeline.py tests/test_pipeline.py
git commit -m "Segni di ripresa: niente note ne' legature oltre i confini"
```

---

### Task 5: scrittura nel MusicXML

**File:**
- Modifica: `arranger/esportatore.py` (`EsportatoreMusicXML._parte` e
  due metodi nuovi)
- Test: `tests/test_pipeline.py`

**Interfacce:**
- Usa `Misura.ripresa` e le chiavi `segno_*` (Task 3).
- Produce `EsportatoreMusicXML._ripresa_inizio(m: Misura, prima: bool) -> List[str]`.
  Scrive la stanghetta sinistra e le direzioni di Segno e Coda.
- Produce `EsportatoreMusicXML._ripresa_fine(m: Misura, prima: bool, coda_arrivo: bool) -> List[str]`.
  Scrive i testi dei salti e la stanghetta destra.

**Ordine dentro la misura:**
1. `<measure>` e gli attributi;
2. `_ripresa_inizio`;
3. le voci;
4. `_ripresa_fine`;
5. `</measure>`.

**Elementi MusicXML esatti** (l'ordine degli elementi nel `<barline>` è
quello del DTD 4.0):
- **Stanghetta sinistra:** `<barline location="left">`, con
  `<bar-style>heavy-light</bar-style>` se c'è `|:`, poi
  `<ending number="N" type="start"/>` se `volta_apre`, poi
  `<repeat direction="forward"/>`.
- **Stanghetta destra:** `<barline location="right">`, con
  `<bar-style>light-heavy</bar-style>` se c'è `:|`, poi
  `<ending number="N" type="stop|discontinue"/>` se `volta_chiude`, poi
  `<repeat direction="backward"/>`. Si aggiunge ` times="n"` solo se
  `n != 2`.
- **Numero della volta:** `N` sono i numeri separati da «, », cioè
  `"1, 2"`.
- **Segno:** `<direction placement="above"><direction-type><segno/></direction-type>`;
  solo nella prima parte va anche `<sound segno="s1"/>`.
- **Coda:** come il Segno, con `<coda/>`. Il `<sound coda="c1"/>` va solo
  nella prima parte, e solo sulla misura d'arrivo, cioè la prima con
  `coda` dopo un salto (`coda_arrivo`).
- **Testi dei salti:** `<words>` dal catalogo, nella lingua di
  `self.p.lingua`. Si usa `testo_salto` se non è vuoto. Solo nella prima
  parte si aggiunge `<sound dalsegno="s1"/>`, `<sound dacapo="yes"/>`,
  `<sound tocoda="c1"/>` oppure `<sound fine="yes"/>`.

- [ ] **Step 1: scrivi il test che fallisce**

```python
def test_segni_nel_musicxml(es):
    cfg = Configurazione(formazione={"flauto": 1, "violino": 1, "pianoforte": 1})
    for nome in ("volte", "ds_al_coda", "dc_al_fine"):
        r = esegui(es[nome], cfg, cartella=os.path.join(QUI, "_out_ripresa"))
        radice = ET.parse(r.percorso_xml).getroot()
        parti = radice.findall("part")
        for k, parte in enumerate(parti):
            mis = parte.findall("measure")
            if nome == "volte":
                verifica(mis[0].find("barline/repeat[@direction='forward']") is not None, f"|: {k}")
                verifica(mis[4].find("barline/ending[@number='1'][@type='stop']") is not None, f"volta1 {k}")
                verifica(mis[4].find("barline/repeat[@direction='backward']") is not None, f":| {k}")
                verifica(mis[5].find("barline/ending[@type='discontinue']") is not None, f"volta2 {k}")
            if nome == "ds_al_coda":
                verifica(mis[2].find(".//segno") is not None and mis[7].find(".//coda") is not None, f"segni {k}")
                verifica(any(w.text == "D.S. al Coda" for w in mis[6].iter("words")), f"testo D.S. {k}")
            suoni = [s for m in mis for s in m.iter("sound") if set(s.attrib) - {"tempo"}]
            verifica(bool(suoni) == (k == 0 and nome != "volte"), f"<sound> solo nella prima parte ({nome} {k})")
    a = esegui(es["inno"], cfg, cartella=os.path.join(QUI, "_out_ripresa"))
    verifica("<barline" not in open(a.percorso_xml, encoding="utf-8").read(), "inno senza stanghette")
```

- [ ] **Step 2: esegui i test e controlla che falliscano**

Risultato atteso: i test su `|:` falliscono.

- [ ] **Step 3: implementa i due metodi e la chiamata in `_parte`**

`prima` è `parte is self.p.parti[0]`. `coda_arrivo` si calcola una volta
in `xml()`: è l'indice della prima misura con `coda` dopo la prima misura
con `salto`.

- [ ] **Step 4: esegui i test e controlla che passino**

Risultato atteso: `0 fallite`. Controlla anche che
`test_versione_inglese` dia ancora la stessa musica fra IT ed EN.

- [ ] **Step 5: commit**

```bash
git add arranger/esportatore.py tests/test_pipeline.py
git commit -m "Segni di ripresa: scrittura nel MusicXML"
```

---

### Task 6: MIDI di anteprima srotolato

**File:**
- Modifica: `arranger/ripetizioni.py`
- Modifica: `arranger/esportatore.py` (`esporta_midi`)
- Test: `tests/test_pipeline.py`

**Interfacce:**
- Usa `ordine_esecuzione` e `ha_segni` (Task 2), più
  `esportatore.taglia_su_misura`. Per evitare un import circolare, si
  importa dentro la funzione.
- Produce `srotola_eventi(eventi: List[Evento], misure: List[Misura]) -> List[Evento]`.
  Restituisce gli eventi al tempo di esecuzione, senza pause.

- [ ] **Step 1: scrivi il test che fallisce**

```python
def test_midi_srotolato(es):
    from arranger import ripetizioni
    from arranger.modello import Evento
    sp = ingestione.ingerisci(es["ritornello_levare"])
    ev = [Evento(inizio=m.inizio, durata=m.durata, altezze=[60 + i]) for i, m in enumerate(sp.misure)]
    fuori = ripetizioni.srotola_eventi(ev, sp.misure)
    verifica(abs(max(e.fine for e in fuori) - 24.0) < 1e-6, "2 x 12 quarti")
    verifica([e.altezze[0] for e in fuori] == [60, 61, 62, 63] * 2, "ordine delle note")
    tenuta = [Evento(inizio=4.0, durata=8.0, altezze=[70])]      # m1-m2, nessun confine in mezzo
    verifica(len(ripetizioni.srotola_eventi(tenuta, sp.misure)) == 2, "una nota per passaggio, non per misura")
    a = esegui(es["inno"], Configurazione(formazione={"flauto": 1, "pianoforte": 1}),
               cartella=os.path.join(QUI, "_out_ripresa"), nome_base="prima")
    b = esegui(es["inno"], Configurazione(formazione={"flauto": 1, "pianoforte": 1}),
               cartella=os.path.join(QUI, "_out_ripresa"), nome_base="dopo")
    verifica(open(a.percorso_midi, "rb").read() == open(b.percorso_midi, "rb").read(), "inno: MIDI stabile")
```

- [ ] **Step 2: esegui i test e controlla che falliscano**

Risultato atteso: `AttributeError: ... 'srotola_eventi'`.

- [ ] **Step 3: implementa `srotola_eventi` e usalo in `esporta_midi`**

- Per ogni indice `i` di `ordine_esecuzione`, si prendono i frammenti
  non di pausa di `taglia_su_misura(eventi, misure[i])` e si spostano di
  `t_corrente - misure[i].inizio`.
- Un frammento con `legato_dopo` si fonde con il frammento della stessa
  altezza che apre la misura successiva, se quella misura è suonata
  subito dopo (`ordine[k+1] == i+1`) e porta `legato_prima`.
- In `esporta_midi`, `eventi = p.eventi` diventa
  `srotola_eventi(p.eventi, part.misure)` solo se
  `ha_segni(part.misure)`. Senza segni il percorso resta quello di oggi.

- [ ] **Step 4: esegui i test e controlla che passino**

Risultato atteso: `0 fallite`.

- [ ] **Step 5: commit**

```bash
git add arranger/ripetizioni.py arranger/esportatore.py tests/test_pipeline.py
git commit -m "Segni di ripresa: MIDI di anteprima srotolato"
```

---

### Task 7: LilyPond

**File:**
- Modifica: `arranger/lilypond.py` (`_corpo`, nel ciclo sulle misure)
- Test: `tests/test_pipeline.py`

**Interfacce:**
- Usa `Misura.ripresa` e le chiavi `segno_*` (Task 3).

**Cosa scrivere** prima di `self._misura(...)` di ogni misura:
- `\bar ".|:"` se c'è `|:`;
- `\set Score.repeatCommands = #'((volta "1, 2."))` se `volta_apre`;
- `\mark \markup { \musicglyph "scripts.segno" }` se c'è il Segno;
- `\mark \markup { \musicglyph "scripts.coda" }` se c'è la Coda.

**Cosa scrivere** dopo la misura:
- `\bar ":|."` se c'è `:|`;
- `\set Score.repeatCommands = #'((volta #f))` se `volta_chiude`;
- per i testi, `\once \override Score.RehearsalMark.break-visibility =
  #begin-of-line-invisible` seguito da `\mark \markup { \italic "…" }`,
  con l'allineamento a destra.

I segni vanno solo nel rigo della prima parte, perché `\mark` vale per
tutta la partitura. `\bar` va in tutti i righi.

- [ ] **Step 1: scrivi il test che fallisce**

```python
def test_segni_lilypond(es):
    r = esegui(es["volte"], Configurazione(formazione={"flauto": 1, "pianoforte": 1}),
               cartella=os.path.join(QUI, "_out_ripresa"), esporta_ly=True)
    ly = open(r.percorso_ly, encoding="utf-8").read()
    verifica('\\bar ".|:"' in ly and '\\bar ":|."' in ly, "stanghette di ritornello")
    verifica("(volta \"1.\")" in ly and "(volta #f)" in ly, "volte")
```

- [ ] **Step 2: esegui i test e controlla che falliscano**

- [ ] **Step 3: implementa**

- [ ] **Step 4: esegui i test e controlla che passino.** Se LilyPond è
  installato (`which lilypond`), incidi `volte.xml` con `cli.py --pdf` e
  guarda il PDF. Se non è installato, scrivi nella docstring di
  `_corpo`: *«segni di ripresa: sorgente verificata dai test, incisione
  non verificata»*.

- [ ] **Step 5: commit**

```bash
git add arranger/lilypond.py tests/test_pipeline.py
git commit -m "Segni di ripresa: sorgente LilyPond"
```

---

### Task 8: prova su repertorio reale (con l'utente)

**File:** nessuno, salvo correzioni. Ogni correzione ha il suo test nel
task che ne possiede il codice.

- [ ] **Step 1:** l'utente mette 2 o 3 MusicXML veri nella cartella del
  progetto, esportati da programmi diversi, con ritornelli, volte e un
  D.S. al Coda.
- [ ] **Step 2:** per ogni file, `python cli.py <file> --organico
  flauto=2,clarinetto=1,violino=2,violoncello=1,chitarra=1,pianoforte=1 --livello
  "2a Media" -o output`. Controlla la riga `[Forma]` del report contro la
  partitura originale, misura per misura.
- [ ] **Step 3:** l'utente apre l'uscita in Dorico e in MuseScore e
  controlla che Segno e Coda non compaiano doppi. Se compaiono doppi, si
  applica il ripiego della specifica: direzioni solo nella prima parte di
  ogni gruppo. È una modifica al Task 5, con un test.
- [ ] **Step 4:** ascolta il MIDI di anteprima nell'app: deve seguire la
  forma.

---

### Task 9: rilascio 0.9.8

**File:**
- Modifica: `arranger/versione.py`
- Modifica: `app.py` (`VERSIONE_INTERFACCIA`)
- Modifica: `README.md`
- Modifica: `manifesto.json`

- [ ] **Step 1:** in `versione.py`: `VERSIONE = "0.9.8"`,
  `PRECEDENTE = "0.9.7"`, `COMPILATO` alla data del rilascio, voci
  `NOVITA` e `NOVITA_EN` sui segni di ripresa. Lo storico non si
  cancella.
- [ ] **Step 2:** `VERSIONE_INTERFACCIA` in `app.py` e versione nel
  README. Nel README togli il limite «i ritornelli non vengono
  srotolati» e aggiungi: «l'analisi (frasi, levigatura) lavora sulla
  forma scritta: fra la 1ª e la 2ª volta può valutare salti che in
  esecuzione non ci sono».
- [ ] **Step 3:** `python controllo_file.py --scrivi`, poi
  `python tests/test_pipeline.py`. Risultato atteso: `0 fallite`.
- [ ] **Step 4:** aggiorna in `CLAUDE.md` lo stato (0.9.8) e i prossimi
  passi.
- [ ] **Step 5:** commit e push solo con l'ok dell'utente. Il deploy si
  fa con `git add -A`, come da `CLAUDE.md`: prima chiedi all'utente che
  cosa fare delle modifiche non correlate in `main` (`account.py`,
  `landing/`, `server.py`).
