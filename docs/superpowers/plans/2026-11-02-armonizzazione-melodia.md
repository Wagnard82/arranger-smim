# Armonizzazione della melodia nuda: piano d'implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Obiettivo:** un armonizzatore per la melodia nuda che si avvicini agli
accordi veri del brano, seguendo i principi di Piston.

**Architettura:**
- Un modulo nuovo, `arranger/armonizzazione.py`, lavora in sette fasi:
  tonalità, griglia, candidati, punteggio, frasi, Viterbi, rivolti.
- `analizzatore.armonizza_melodia` delega al modulo nuovo.
- Uno script a mano, `banco_armonia.py`, misura e tara i pesi sui brani
  veri in `XML/`, che restano fuori dal repository.

**Tecnologie:** Python 3.12, solo libreria standard. Test in
`tests/test_pipeline.py`, con `verifica(cond, msg)`.

**Specifica:** `docs/superpowers/specs/2026-11-02-armonizzazione-melodia-design.md`.
I principi P1-P12 sono nella sezione 5 di `docs/principi_arrangiamento.md`.

## Vincoli globali

- **Quando si armonizza:** solo per `sp.tipo == "lead_sheet"` senza sigle.
  Se ci sono sigle o pianoforte, l'armonia del file vince sempre.
- **Libreria e moduli:** il nucleo usa solo la libreria standard.
  `modello.py` si estende soltanto aggiungendo campi.
- **Lingua:**
  - commenti e docstring in italiano;
  - i testi per l'utente stanno nei cataloghi, in IT e in EN, con gli
    stessi segnaposto;
  - la musica deve restare identica fra IT ed EN.
- **Melodia:** non si tocca mai. L'armonizzatore la legge e basta.
- **Brani del banco:** i file di `XML/` sono commerciali. Non entrano nel
  repository né nei test.
- **Test:** `source .venv312/bin/activate && python tests/test_pipeline.py`.
  L'ultima riga attesa è `N verifiche superate, 0 fallite`.
- **Commit:**
  - dopo ogni modifica al motore si rigenera `manifesto.json` con
    `python controllo_file.py --scrivi` e lo si include;
  - si committano solo i file del task;
  - non si fa push.

## Punti da controllare in revisione

1. **Melodia con introduzione strumentale o pause lunghe.** Nei tratti
   senza note si tiene l'accordo precedente (all'inizio, la tonica): non
   deve comparire un accordo a caso. Test nel Task 3.
2. **Melodia in anacrusi.** Il levare è un tratto unico e il primo accordo
   pieno è la tonica, salvo una melodia che la contraddice. Test nel
   Task 3.
3. **Valzer in 3/4.** Al massimo un cambio per misura. Test nel Task 3.
4. **Fa# di passaggio che scende** (Sol-Fa#-Fa in Do). Non deve produrre
   V/V, perché la sensibile deve salire. Test nel Task 2.
5. **Brano brevissimo** (una misura, una nota sola). Nessun errore e
   almeno un accordo in uscita. Test nel Task 3.

---

### Task 1: modulo, griglia e tonalità

**File:**
- Crea: `arranger/armonizzazione.py`
- Modifica: `esempi/genera_esempi.py` (un generatore nuovo)
- Modifica: `.gitignore` (aggiungere `XML/`)
- Test: `tests/test_pipeline.py`

**Interfacce:**
- Produce `Tratto(inizio: float, fine: float, forza: int)`: 2 per il
  battere della misura, 1 per la metà misura, 0 per tutto il resto.
- Produce `griglia(sp: Spartito) -> List[Tratto]`.
- Produce
  `tonalita_della_melodia(sp, melodia: List[Nota], frasi: List[Tuple[float, float]]) -> Tuple[int, str]`,
  che restituisce `(tonica pc, "maggiore" | "minore")`.
- Produce in `genera_esempi`
  `melodia_nuda(percorso, titolo, misure, fifths=0, num=4, den=4, anacrusi=None) -> str`.
  - `misure` è una lista di misure; ogni misura è una lista di
    `(midi, quarti)`, con `midi=None` per la pausa.
  - Scrive un lead sheet su un rigo, senza `<harmony>`.
  - `anacrusi` è una misura parziale opzionale, scritta con
    `implicit="yes"`.

**Griglia (dalla specifica):**

| Metro | Tratti per misura |
|---|---|
| 4/4, 2/2, 12/8 | 2 |
| 2/4, 3/4, 3/8, 6/8 | 1 |
| 9/8 | 3 |
| altri | 1 |

Una misura parziale vale sempre un tratto solo.

- [ ] **Step 1: scrivi il test che fallisce**

```python
def prepara_armonia():
    d = os.path.join(os.path.dirname(QUI), "esempi")
    g = genera_esempi
    es = {}
    # La minore con la sensibile: si chiude su La lungo
    es["la_minore"] = g.melodia_nuda(os.path.join(d, "nuda_la_minore.xml"), "La minore",
        [[(69, 1), (72, 1), (76, 1), (72, 1)], [(71, 1), (68, 1), (71, 1), (76, 1)],
         [(72, 1), (71, 1), (69, 1), (68, 1)], [(69, 4)]])
    # stesse note senza Sol# e chiusura su Do: Do maggiore
    es["do_maggiore"] = g.melodia_nuda(os.path.join(d, "nuda_do_maggiore.xml"), "Do maggiore",
        [[(69, 1), (72, 1), (76, 1), (72, 1)], [(71, 1), (67, 1), (71, 1), (74, 1)],
         [(72, 1), (71, 1), (69, 1), (67, 1)], [(72, 4)]])
    es["valzer"] = g.melodia_nuda(os.path.join(d, "nuda_valzer.xml"), "Valzer",
        [[(67, 1), (72, 1), (76, 1)], [(74, 2), (71, 1)], [(72, 3)]], num=3, den=4)
    es["sei_ottavi"] = g.melodia_nuda(os.path.join(d, "nuda_sei_ottavi.xml"), "6/8",
        [[(72, 1.5), (74, 1.5)], [(72, 3)]], num=6, den=8)
    es["levare"] = g.melodia_nuda(os.path.join(d, "nuda_levare.xml"), "Levare",
        [[(72, 2), (76, 2)], [(79, 2), (76, 2)], [(74, 2), (71, 2)], [(72, 4)]],
        anacrusi=[(67, 1)])
    return es


def test_griglia_e_tonalita(inno_nudo, es):
    from arranger import armonizzazione as A, analizzatore
    def tratti(nome):
        return A.griglia(ingestione.ingerisci(es[nome]))
    verifica(len(tratti("la_minore")) == 8, "4/4: due tratti per misura")
    verifica(len(tratti("valzer")) == 3, "3/4: uno per misura")
    verifica(len(tratti("sei_ottavi")) == 2, "6/8: uno per misura")
    t = tratti("levare")
    verifica(len(t) == 1 + 4 * 2 and t[0].fine - t[0].inizio == 1.0, "levare: un tratto")
    verifica([x.forza for x in t[1:3]] == [2, 1], "forza: battere 2, meta' misura 1")
    def tono(percorso):
        sp = ingestione.ingerisci(percorso)
        mel = analizzatore.analizza(sp).melodia
        return A.tonalita_della_melodia(sp, mel, analizzatore.rileva_frasi(sp, mel))
    verifica(tono(es["la_minore"]) == (9, "minore"), f"La minore: {tono(es['la_minore'])}")
    verifica(tono(es["do_maggiore"]) == (0, "maggiore"), f"Do maggiore: {tono(es['do_maggiore'])}")
    verifica(tono(inno_nudo) == (0, "maggiore"), "Inno: Do maggiore")
```

`inno_nudo` è il lead sheet dell'Inno senza sigle. Si ottiene dal
generatore `lead_sheet`: si aggiunge il parametro `sigle=True` (default
invariato) e lo si chiama con `sigle=False`, scrivendo il file in
`esempi/inno_nudo.xml`. In `__main__` si chiamano
`es_arm = prepara_armonia()` e `test_griglia_e_tonalita(inno_nudo, es_arm)`.

- [ ] **Step 2: esegui i test e controlla che falliscano**

Risultato atteso: `AttributeError` su `genera_esempi.melodia_nuda` oppure
`ImportError` su `armonizzazione`.

- [ ] **Step 3: implementa `melodia_nuda`, il parametro `sigle` di `lead_sheet`, `Tratto`, `griglia` e `tonalita_della_melodia`; aggiungi `XML/` a `.gitignore`**

**Tonalità:** si confrontano i due candidati, il maggiore dell'armatura
prevalente e la sua relativa minore (tonica = maggiore − 3 semitoni).
Il punteggio del minore somma:

- +2 se l'ultima nota del brano è la tonica minore, +1 se è la sua
  quinta;
- +1 per ogni frase che chiude sulla tonica minore;
- +1.5 se compare la sensibile alzata (tonica minore − 1);
- la differenza fra la durata delle note lunghe o sul battere che stanno
  nella triade minore e quella delle note nella triade maggiore, divisa
  per la durata totale.

Il maggiore riceve gli stessi punti con le sue note. Il minore vince solo
con un margine maggiore di 1.0: nel dubbio vince il maggiore.

- [ ] **Step 4: esegui i test e controlla che passino**

Risultato atteso: `0 fallite`.

- [ ] **Step 5: commit**

```bash
python controllo_file.py --scrivi
git add arranger/armonizzazione.py esempi/genera_esempi.py esempi/nuda_*.xml esempi/inno_nudo.xml tests/test_pipeline.py manifesto.json
git commit -m "Armonizzazione: griglia del ritmo armonico e tonalita' della melodia"
```

`.gitignore` contiene già una modifica non committata dell'utente: la
riga `XML/` si aggiunge al file ma **non si committa** in questo task. La
si porta nel commit di rilascio insieme alla sua modifica, con il suo ok.

---

### Task 2: candidati e punteggio sul tratto

**File:**
- Modifica: `arranger/armonizzazione.py`
- Test: `tests/test_pipeline.py`

**Interfacce:**
- Usa `Tratto` e `tonalita_della_melodia` (Task 1).
- Produce
  `Candidato(fondamentale: int, qualita: str, grado: str, secondaria: bool = False)`,
  frozen. `qualita` è una di `"maj"`, `"min"`, `"dim"`, `"dom7"`.
- Produce
  `candidati(tonica: int, modo: str, note: List[Nota]) -> List[Candidato]`.
  `note` è la melodia di tutto il brano: serve a decidere quali dominanti
  secondarie ammettere.
- Produce
  `emissione(tratto: Tratto, c: Candidato, melodia: List[Nota], pesi: "Pesi") -> float`.
- Produce la dataclass `Pesi` con questi campi e questi default iniziali,
  che il Task 6 ritarerà:

| Campo | Default |
|---|---|
| `estranea` | 0.6 |
| `passaggio` | 0.15 |
| `forte` | 0.3 |
| `cambio` | `(0.25, 0.45, 0.8)` (indice = forza 2, 1, 0) |
| `abituale` | 0.0 |
| `a_volte` | 0.25 |
| `raro` | 0.6 |
| `assente` | 1.2 |
| `salto` | 0.4 |
| `cadenza` | 1.0 |

**Candidati (dalla specifica):**
- **Maggiore:** I, ii, iii, IV, V, vi, V7, vii°; dominanti secondarie V/ii,
  V/iii, V/IV, V/V, V/vi, sia triade maggiore sia `dom7`.
- **Minore:** i, ii°, III, iv, V (maggiore), V7, VI, VII (maggiore), vii°;
  dominanti secondarie V/III, V/iv, V/V, V/VI.

**Regola per le dominanti secondarie (P12):** una secondaria si ammette
solo se nella melodia esiste una nota uguale alla sua sensibile
(fondamentale + 4) seguita entro 2 quarti da una nota mezzo tono sopra.
L'ammissione vale per tutto il brano; poi è il punteggio a decidere dove
usarla.

- [ ] **Step 1: scrivi il test che fallisce**

```python
def test_candidati_e_punteggio():
    from arranger import armonizzazione as A
    N = lambda m, t, d: Nota(midi=m, inizio=t, durata=d)
    sale = [N(67, 0, 1), N(66, 1, 1), N(67, 2, 2)]       # Sol-Fa#-Sol
    scende = [N(67, 0, 1), N(66, 1, 1), N(65, 2, 2)]     # Sol-Fa#-Fa
    gradi = lambda note: {c.grado for c in A.candidati(0, "maggiore", note)}
    verifica("V/V" in gradi(sale), "Fa# che sale: V/V candidato")
    verifica("V/V" not in gradi(scende), "Fa# che scende: niente V/V")
    verifica({"i", "iv", "V", "VI", "VII"} <= {c.grado for c in A.candidati(9, "minore", [])},
             "gradi del minore")
    p, t = A.Pesi(), A.Tratto(0.0, 2.0, 2)
    I, V = A.Candidato(0, "maj", "I"), A.Candidato(7, "maj", "V")
    do_mi = [N(60, 0, 1), N(64, 1, 1)]
    verifica(A.emissione(t, I, do_mi, p) > A.emissione(t, V, do_mi, p), "Do-Mi: I meglio di V")
    passaggio = [N(60, 0, 1), N(62, 1, 0.5), N(64, 1.5, 0.5)]   # Re di passaggio
    appoggio = [N(62, 0, 1), N(64, 1, 1)]                       # Re sul battere
    verifica(A.emissione(t, I, passaggio, p) > A.emissione(t, I, appoggio, p),
             "nota di passaggio meno penalizzata di un'estranea sul battere")
```

Il test si aggiunge al `__main__` dopo `test_griglia_e_tonalita`. `Nota`
è già importata nel file di test.

- [ ] **Step 2: esegui i test e controlla che falliscano**

Risultato atteso: `AttributeError: ... 'candidati'`.

- [ ] **Step 3: implementa `Candidato`, `Pesi`, `candidati` ed `emissione`**

Le regole di `emissione` sono quelle della specifica, sezione 4:

- il peso di una nota è la sua durata dentro il tratto;
- il peso si moltiplica per 1.5 se la nota attacca all'inizio del tratto,
  per 1.2 se attacca su un movimento forte;
- una nota dell'accordo vale +peso; una nota estranea vale
  −peso × `estranea`, oppure −peso × `passaggio` se è di passaggio o di
  volta;
- la priorità del grado vale `forte` per I, IV, V e V7, metà per ii,
  zero per gli altri.

Le note dell'accordo si prendono da
`Accordo(..., qualita=c.qualita).note_accordo()`. Per `"dim"` si usa la
qualità `"dim"` già presente nel modello.

- [ ] **Step 4: esegui i test e controlla che passino**

Risultato atteso: `0 fallite`.

- [ ] **Step 5: commit**

```bash
python controllo_file.py --scrivi
git add arranger/armonizzazione.py tests/test_pipeline.py manifesto.json
git commit -m "Armonizzazione: accordi candidati e punteggio sul tratto"
```

---

### Task 3: Viterbi, successioni e cadenze; collegamento ad `analizza`

**File:**
- Modifica: `arranger/armonizzazione.py`
- Modifica: `arranger/analizzatore.py:595-680`: `GRADI_ARMONIZZAZIONE` e il
  corpo di `armonizza_melodia` lasciano il posto alla delega; la
  docstring si aggiorna.
- Test: `tests/test_pipeline.py`

**Interfacce:**
- Usa tutto ciò che producono i Task 1 e 2.
- Produce la tabella `TAVOLA: Dict[str, Dict[str, Tuple[str, ...]]]`, così
  strutturata: `TAVOLA[modo][grado] = (abituali, a_volte, rari)`, con i
  gradi della tavola di Piston (P6). Per il minore valgono le aggiunte
  del capitolo 4:
  - i → VII;
  - III → VII;
  - VII → III, VI, iv;
  - vii° → i.
- Produce
  `armonizza(sp: Spartito, melodia: List[Nota], pesi: Optional[Pesi] = None) -> List[Accordo]`.
- `analizzatore.armonizza_melodia(sp, melodia, penale_cambio=0.35)` ora
  restituisce `armonizzazione.armonizza(sp, melodia)`. Il parametro
  `penale_cambio` resta nella firma per compatibilità, ma è ignorato.

**Costo di passaggio:**
- stesso accordo: 0;
- accordo diverso: `pesi.cambio[...]` della forza del tratto di arrivo,
  più il costo della successione:
  - `abituale`, `a_volte` o `raro` secondo la tavola;
  - `assente` se la successione non è in tavola;
  - per le secondarie, V/X → X costa `abituale` e ogni altra uscita
    `raro`;
- più `pesi.salto` se il tratto d'arrivo comincia dentro un salto
  (intervallo > 2 semitoni) la cui prima nota attacca su un tempo debole
  del tratto precedente;
- il costo di cambio si dimezza se una nota della melodia attraversa il
  confine fra i due tratti ed è nota comune dei due accordi (P3).

**Cadenze**, come premio di `pesi.cadenza` sugli ultimi due tratti di
ogni frase:

| La frase chiude su | Si premia |
|---|---|
| Tonica (nota finale di almeno un movimento) | V o V7 → I (o i); IV → I con metà premio |
| 2° o 7° grado | V nell'ultimo tratto |
| 5° grado | V o I |
| Ultima frase del brano | V → I con premio doppio |

**Tratti senza note** (pause, introduzioni): l'emissione vale 0 per tutti
i candidati. Così il costo di cambio tiene l'accordo precedente; prima
della prima nota l'accordo è la tonica.

**Uscita:** un `Accordo` per ogni tratto in cui l'accordo cambia; i tratti
consecutivi uguali si fondono. `confidenza=0.5`, `basso=None`, che il
Task 4 riempie.

- [ ] **Step 1: scrivi il test che fallisce**

```python
def test_armonizzazione_viterbi(inno_nudo, es):
    from arranger import armonizzazione as A, analizzatore
    d = os.path.join(os.path.dirname(QUI), "esempi")
    def armonia(percorso):
        sp = ingestione.ingerisci(percorso)
        return sp, A.armonizza(sp, analizzatore.analizza(sp).melodia)
    def fondamentale_a(acc, t):
        return next(a.fondamentale for a in acc if a.inizio - 1e-6 <= t < a.fine - 1e-6)
    # I-V | vi-IV | I-V | I, arpeggi per mezza misura
    ritmo = genera_esempi.melodia_nuda(os.path.join(d, "nuda_ritmo.xml"), "Ritmo", [
        [(60, 0.5), (64, 0.5), (67, 1), (67, 0.5), (71, 0.5), (74, 1)],
        [(69, 0.5), (72, 0.5), (76, 1), (65, 0.5), (69, 0.5), (72, 1)],
        [(60, 0.5), (64, 0.5), (67, 1), (67, 0.5), (71, 0.5), (74, 1)],
        [(72, 4)]])
    sp, acc = armonia(ritmo)
    attese = [0, 7, 9, 5, 0, 7, 0, 0]
    giusti = sum(fondamentale_a(acc, 2.0 * k) == f for k, f in enumerate(attese))
    verifica(giusti >= 6, f"ritmo armonico a mezza misura: {giusti}/8")
    verifica(len(acc) >= 6, f"almeno 6 accordi: {len(acc)}")
    # cadenze
    _sp, acc = armonia(es["do_maggiore"])
    verifica([a.fondamentale for a in acc[-2:]] == [7, 0], f"chiusura sulla tonica: V-I {acc[-2:]}")
    sospesa = genera_esempi.melodia_nuda(os.path.join(d, "nuda_sospesa.xml"), "Sospesa",
        [[(64, 1), (65, 1), (67, 2)], [(69, 1), (67, 1), (65, 1), (64, 1)],
         [(65, 1), (64, 1), (62, 2)], [(62, 4)]])
    _sp, acc = armonia(sospesa)
    verifica(acc[-1].fondamentale == 7, "chiusura sul 2o grado: V")
    # dominante secondaria
    vv = genera_esempi.melodia_nuda(os.path.join(d, "nuda_vv.xml"), "V del V",
        [[(64, 2), (60, 2)], [(69, 2), (66, 2)], [(67, 4)], [(71, 2), (74, 2)], [(72, 4)]])
    _sp, acc = armonia(vv)
    verifica(any(a.fondamentale == 2 and a.qualita in ("maj", "dom7") for a in acc),
             f"Fa# che sale a Sol: V/V proposto ({[(a.fondamentale, a.qualita) for a in acc]})")
    # minore
    _sp, acc = armonia(es["la_minore"])
    verifica(acc[-1].fondamentale == 9 and acc[-1].qualita == "min", "La minore chiude su La-")
    verifica(any(a.fondamentale == 4 and a.qualita in ("maj", "dom7") for a in acc),
             "La minore: dominante maggiore (Mi)")
    # Inno senza sigle contro le sigle vere del lead sheet di prova
    vero = ingestione.ingerisci(genera_esempi.lead_sheet(os.path.join(d, "lead_sheet.xml")))
    _sp, acc = armonia(inno_nudo)
    vere = sorted(vero.sigle)
    def vera_a(t):
        return [s for s in vere if s[0] <= t + 1e-6][-1][1]
    mov = [x * 1.0 for x in range(int(vero.durata_totale))]
    pct = sum(fondamentale_a(acc, t) == vera_a(t) for t in mov) / len(mov)
    verifica(pct >= 0.84, f"Inno senza sigle: {pct:.0%} (minimo 84%)")
    # punti di revisione
    _sp, acc = armonia(es["valzer"])
    verifica(len(acc) <= 3, "valzer: al massimo un accordo per misura")
    sp, acc = armonia(es["levare"])
    verifica(fondamentale_a(acc, 1.0) == 0, "levare: primo accordo pieno sulla tonica")
    pausa = genera_esempi.melodia_nuda(os.path.join(d, "nuda_pausa.xml"), "Pausa",
        [[(None, 4)], [(None, 4)], [(64, 2), (67, 2)], [(72, 4)]])
    _sp, acc = armonia(pausa)
    verifica(acc[0].fondamentale == 0 and acc[0].fine >= 8.0 - 1e-6,
             "introduzione senza melodia: tonica tenuta")
    corta = genera_esempi.melodia_nuda(os.path.join(d, "nuda_corta.xml"), "Corta", [[(60, 4)]])
    _sp, acc = armonia(corta)
    verifica(len(acc) >= 1, "una nota sola: almeno un accordo")
    # le sigle scritte vincono ancora
    a = analizzatore.analizza(vero).armonia
    verifica(a[0].fondamentale == 0 and len(a) >= 16, "lead sheet con sigle: armonia del file")
```

Nel `__main__` si chiama `test_armonizzazione_viterbi(inno_nudo, es_arm)`.

- [ ] **Step 2: esegui i test e controlla che falliscano**

Risultato atteso: `AttributeError: ... 'armonizza'`.

- [ ] **Step 3: implementa `TAVOLA` e `armonizza`, e fai delegare `armonizza_melodia`**

Il Viterbi è quello di oggi in `armonizza_melodia`: si porta nel modulo
nuovo, con le emissioni del Task 2, i costi di passaggio e i premi di
cadenza sopra. Le frasi si prendono da `analizzatore.rileva_frasi(sp,
melodia)` senza armonia; per evitare un import circolare, l'import va
dentro la funzione.

- [ ] **Step 4: esegui i test e controlla che passino**

Risultato atteso: `0 fallite`. Se l'Inno scende sotto l'84%, si
correggono i pesi di default e si registra un `Ruling`: è un caso della
taratura del Task 6, anticipato.

- [ ] **Step 5: commit**

```bash
python controllo_file.py --scrivi
git add arranger/armonizzazione.py arranger/analizzatore.py esempi/nuda_*.xml tests/test_pipeline.py manifesto.json
git commit -m "Armonizzazione: ritmo armonico, tavola di Piston e cadenze"
```

---

### Task 4: rivolti, cioè il basso come linea

**File:**
- Modifica: `arranger/armonizzazione.py`
- Test: `tests/test_pipeline.py`

**Interfacce:**
- Usa `armonizza` (Task 3).
- Produce
  `scegli_bassi(accordi: List[Accordo], melodia: List[Nota], pesi: Pesi) -> List[Accordo]`,
  che restituisce nuovi `Accordo` con `basso` impostato quando il rivolto
  non è lo stato fondamentale.
- `armonizza` chiama `scegli_bassi` come ultimo passo.

**Programmazione dinamica sui bassi**, con regole e costi della
specifica, sezione 7:
- **Bassi possibili:** fondamentale o terza dell'accordo. La quinta è
  ammessa solo per I in cadenza, come quarta e sesta di cadenza, cioè
  I⁶₄ subito prima del V finale.
- **Costo del moto del basso:**
  - 0 per un grado congiunto (1-2 semitoni);
  - 0.3 per una terza;
  - 0.6 per una quarta o una quinta;
  - 1.0 per salti più ampi.
- **Moto contrario** rispetto alla melodia: −0.2.
- **Tonica ripetuta nel basso:** +0.4 per ogni ripetizione oltre la
  seconda.
- **Più di tre seste parallele** con la melodia: +0.8.
- **Fondamentale imposta:** V e I nelle ultime due posizioni del brano
  stanno sempre in stato fondamentale.
- **Peso del primo rivolto:** a parità di costo vince lo stato
  fondamentale; il primo rivolto costa +0.15.

- [ ] **Step 1: scrivi il test che fallisce**

```python
def test_rivolti():
    from arranger import armonizzazione as A
    from arranger.modello import Accordo
    N = lambda m, t, d: Nota(midi=m, inizio=t, durata=d)
    # melodia Mi-Re-Do sopra I-V-I: il V con il Si nel basso (V6) e' piu' liscio
    acc = [Accordo(0, 2, 0, "maj"), Accordo(2, 2, 7, "maj"), Accordo(4, 4, 0, "maj")]
    mel = [N(76, 0, 2), N(74, 2, 2), N(72, 4, 4)]
    fuori = A.scegli_bassi(acc, mel, A.Pesi())
    verifica(fuori[1].basso == 11, f"V6 fra due I: {[a.basso for a in fuori]}")
    verifica(fuori[-1].basso in (None, 0), "accordo finale in stato fondamentale")
    acc = [Accordo(0, 2, 0, "maj"), Accordo(2, 2, 7, "maj"), Accordo(4, 4, 0, "maj")]
    mel = [N(64, 0, 2), N(67, 2, 2), N(72, 4, 4)]
    fuori = A.scegli_bassi(acc, mel, A.Pesi())
    verifica(fuori[-2].basso in (None, 7), "V di cadenza in stato fondamentale")
```

- [ ] **Step 2: esegui i test e controlla che falliscano**

- [ ] **Step 3: implementa `scegli_bassi` e chiamalo in `armonizza`**

- [ ] **Step 4: esegui i test e controlla che passino.** Controlla anche
  che `test_armonizzazione_viterbi` passi ancora: i rivolti non cambiano
  le fondamentali.

- [ ] **Step 5: commit**

```bash
python controllo_file.py --scrivi
git add arranger/armonizzazione.py tests/test_pipeline.py manifesto.json
git commit -m "Armonizzazione: rivolti e basso come linea"
```

---

### Task 5: report con tonalità e modo

**File:**
- Modifica: `arranger/modello.py`: un campo nuovo in `Analisi`
- Modifica: `arranger/analizzatore.py`, in `analizza_con_melodia`, dove si
  chiama `armonizza_melodia`
- Modifica: `arranger/lingua.py`, il messaggio `ingresso_lead_sheet_senza_sigle`
- Modifica: `arranger/orchestratore.py:1474`
- Test: `tests/test_pipeline.py`

**Interfacce:**
- Produce
  `Analisi.tonalita_proposta: Optional[Tuple[int, str]] = None`,
  cioè (tonica, modo). Si riempie solo quando l'armonia è stata proposta.
- Produce `armonizzazione.ultima_tonalita(sp, melodia) -> Tuple[int, str]`,
  che chiama `tonalita_della_melodia` con le frasi.
- Cambia il messaggio `ingresso_lead_sheet_senza_sigle`, che ora ha i
  segnaposto `{tonalita}` e `{modo}`.

**Nuovi testi** (sostituiscono quelli attuali, che parlano di «un accordo
per misura»):
- IT: `[Ingresso] lead sheet SENZA SIGLE: l'armonia e' stata proposta
  dall'arrangiatore in {tonalita} {modo}, seguendo la melodia (cadenze,
  ritmo armonico, dominanti secondarie dove la melodia le chiede). E'
  un'armonizzazione plausibile, non necessariamente quella del brano: per
  un arrangiamento fedele aggiungi le sigle nel file (in Dorico, MuseScore
  o Sibelius) e rigenera.`
- EN: `[Input] lead sheet WITHOUT CHORD SYMBOLS: the harmony was proposed
  by the arranger in {tonalita} {modo}, following the melody (cadences,
  harmonic rhythm, secondary dominants where the melody asks for them).
  It is a plausible harmonization, not necessarily the song's own: for a
  faithful arrangement add the chord symbols to the file (in Dorico,
  MuseScore or Sibelius) and generate again.`

Per riempire i segnaposto:
- `{tonalita}` è `lingua.nota(tonica + 60, lingua)` senza il numero
  d'ottava. Si usano i bemolli se l'armatura ha bemolli.
- `{modo}` viene da due voci nuove del catalogo, `modo_maggiore` e
  `modo_minore`: IT «maggiore» / «minore», EN «major» / «minor».

- [ ] **Step 1: scrivi il test che fallisce**

```python
def test_report_tonalita_proposta(es):
    cfg = Configurazione(formazione={"flauto": 1, "pianoforte": 1})
    r = esegui(es["la_minore"], cfg, cartella=os.path.join(QUI, "_out"), nome_base="nuda_it")
    verifica(any("in La minore" in m for m in r.report), f"report IT: {r.report[:3]}")
    r_en = esegui(es["la_minore"], Configurazione(formazione={"flauto": 1, "pianoforte": 1},
                  lingua="en"), cartella=os.path.join(QUI, "_out"), nome_base="nuda_en")
    verifica(any("in A minor" in m for m in r_en.report), "report EN")
    verifica(r.analisi.tonalita_proposta == (9, "minore"), "tonalita' proposta in Analisi")
```

- [ ] **Step 2: esegui i test e controlla che falliscano**

- [ ] **Step 3: implementa**

- [ ] **Step 4: esegui i test e controlla che passino**, compresi
  `test_cataloghi_completi` e `test_versione_inglese`.

- [ ] **Step 5: commit**

```bash
python controllo_file.py --scrivi
git add arranger/modello.py arranger/analizzatore.py arranger/lingua.py arranger/orchestratore.py arranger/armonizzazione.py tests/test_pipeline.py manifesto.json
git commit -m "Armonizzazione: tonalita' e modo proposti nel report"
```

---

### Task 6: banco di prova e taratura dei pesi

**File:**
- Crea: `banco_armonia.py` nella radice, sullo schema di
  `strumenti_analisi.py`
- Modifica: `arranger/armonizzazione.py`: i default di `Pesi`, con un
  commento sulla taratura
- Modifica: `docs/principi_arrangiamento.md`, sezione 5.2: la tabella con
  i risultati nuovi
- Test: `tests/test_pipeline.py`

**Interfacce:**
- Produce
  `confronta(sp: Spartito, accordi: List[Accordo], tonica: int) -> Dict[str, float]`,
  con le chiavi `fondamentali`, `funzioni`, `cambi_veri`,
  `cambi_proposti` e `movimenti`.
- Produce `solo_melodia(sp: Spartito) -> Tuple[Spartito, List[Nota]]`:
  - una copia con le sole note della melodia scritta (`linea_del_solista`
    per `solista_e_piano`, `analizza(sp).melodia` negli altri casi);
  - `tipo="lead_sheet"`, `sigle=[]`.
- Produce la riga di comando
  `python banco_armonia.py CARTELLA [--taratura] [--arrangia]`:
  - senza opzioni, stampa una riga per brano e la media dei brani pop;
  - `--taratura` prova una griglia di valori per `cambio`, `estranea`,
    `a_volte`, `raro` e `cadenza`, con il metodo «uno escluso»;
  - `--arrangia` scrive in `output/armonia/` l'arrangiamento della sola
    melodia di ogni brano, con `esegui(..., spartito=solo_melodia(sp)[0])`.
- **Funzioni:** tonica = I, iii, vi; sottodominante = ii, IV;
  dominante = V, vii° e tutte le dominanti secondarie. In minore si usano
  gli stessi gradi relativi alla tonica minore.
- **Brani pop:** tutti tranne `girl-from-ipanema*` e `my-future*`, che
  sono i controlli.

- [ ] **Step 1: scrivi il test che fallisce**

```python
def test_banco_armonia():
    import banco_armonia as B
    d = os.path.join(os.path.dirname(QUI), "esempi")
    vero = ingestione.ingerisci(genera_esempi.lead_sheet(os.path.join(d, "lead_sheet.xml")))
    nudo, mel = B.solo_melodia(vero)
    verifica(nudo.sigle == [] and nudo.tipo == "lead_sheet" and mel, "solo melodia")
    from arranger import armonizzazione as A
    r = B.confronta(vero, A.armonizza(nudo, mel), 0)
    verifica(r["fondamentali"] >= 0.84 and r["cambi_veri"] > 0, f"confronto: {r}")
    perfetto = B.confronta(vero, analizzatore.armonia_dalle_sigle(vero), 0)
    verifica(perfetto["fondamentali"] == 1.0, "le sigle contro se stesse: 100%")
```

- [ ] **Step 2: esegui i test e controlla che falliscano**

- [ ] **Step 3: implementa `banco_armonia.py`**

- [ ] **Step 4: esegui il banco e tara i pesi.**
  1. Lancia `python banco_armonia.py XML/` e salva l'uscita.
  2. Lancia `python banco_armonia.py XML/ --taratura`.
  3. Scegli i pesi con la media migliore sui brani pop nel metodo «uno
     escluso», a condizione che ogni brano pop migliori rispetto alla
     tabella iniziale della specifica e che Ipanema e My Future non
     peggiorino.
  4. Scrivi quei pesi come default di `Pesi`.
  5. Rilancia la suite: deve dare `0 fallite`, compreso l'Inno ≥ 84%.
  6. Aggiorna la tabella della sezione 5.2 degli appunti con prima, dopo
     e il valore «uno escluso».
  
  Se un brano pop non migliora, non si forza: si scrive nel ledger con
  la causa, per esempio una modulazione o un accordo fuori vocabolario.

- [ ] **Step 5: commit**

```bash
python controllo_file.py --scrivi
git add banco_armonia.py arranger/armonizzazione.py docs/principi_arrangiamento.md tests/test_pipeline.py manifesto.json
git commit -m "Armonizzazione: banco di prova e taratura dei pesi"
```

---

### Task 7: ascolto del docente (con l'utente)

**File:** nessuno, salvo correzioni. Ogni correzione ha il suo test nel
task che possiede il codice.

- [ ] **Step 1:** `python banco_armonia.py XML/ --arrangia` con un
  organico realistico: `flauto=2, clarinetto=1, violino=2, violoncello=1,
  chitarra=1, pianoforte=1`, livello 2a Media.
- [ ] **Step 2:** l'utente apre e ascolta Let It Be, Dust in the Wind e
  Stand by Me in `output/armonia/`, e conferma che l'armonia regge.
- [ ] **Step 3:** le osservazioni dell'utente diventano test e correzioni
  nei task 1-4, oppure voci rimandate nel ledger.
