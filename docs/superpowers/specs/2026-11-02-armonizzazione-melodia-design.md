# Armonizzazione della melodia nuda

*Specifica di design, 2 novembre 2026.*

## Problema

Quando il file contiene solo la melodia, senza sigle e senza pianoforte
(un lead sheet senza sigle), il motore deve inventare l'armonia.
`analizzatore.armonizza_melodia` oggi:

- mette un accordo per misura, scelto fra I, V, IV, V7, VI, II e III;
- ricava la tonica solo dall'armatura e la tratta sempre da maggiore;
- usa un Viterbi con una penalità unica per ogni cambio;
- non conosce cadenze, rivolti né dominanti secondarie.

Sul banco di prova si tolgono le sigle a brani veri, si armonizza la sola
melodia e si confronta la fondamentale proposta con quella vera,
movimento per movimento. Il risultato:

| Brano | Fondamentale giusta | Cambi veri | Cambi proposti |
|---|---|---|---|
| Inno alla gioia (lead sheet di prova) | 84% | 19 | 11 |
| Let It Be | 46% | 69 | 1 |
| All of Me | 32% | 125 | 75 |
| Easy On Me | 34% | 70 | 28 |
| Bridge over Troubled Water | 39% | 132 | 42 |
| Dust in the Wind (La minore) | 45% | 64 | 67 |
| (Everything I Do) I Do It for You | 51% | 78 | 35 |
| Stand by Me | 36% | 13 | 6 |
| Salve Regina (gregoriano, armonizzato) | 24% | 28 | 11 |
| My Future (controllo, jazz) | 22% | 34 | 32 |
| The Girl from Ipanema (controllo, jazz) | 7% | 25 | 14 |

Il difetto principale è il ritmo armonico: nel pop l'accordo cambia circa
ogni due movimenti, mentre il motore ne mette uno per misura.

## Decisioni prese con il docente (2/11/2026)

1. **L'armonia si inventa solo per la melodia nuda.** Se il file ha sigle o
   pianoforte si seguono quelle, come oggi. Il punto d'ingresso non cambia:
   `analizza` chiama l'armonizzatore solo per `lead_sheet` senza sigle.
2. **Obiettivo: avvicinarsi agli accordi veri del brano.** Si misura sul
   banco di prova. Le regole di Piston sono il mezzo per arrivarci.
3. **L'opzione «cambio armonia»** (riarmonizzare anche quando ci sono
   sigle o pianoforte) **viene dopo.** L'armonizzatore lavora sulla sola
   melodia, così l'opzione si aggiunge in seguito con un interruttore.
4. Pop e repertorio scolastico sono l'obiettivo. Il jazz (Ipanema,
   My Future) serve solo come controllo che il risultato non peggiori.

## Fonti

Piston, *Armonia*, capitoli 3, 4, 9, 11, 12 e 16, riassunti nella sezione 5
di `docs/principi_arrangiamento.md`. I numeri di principio citati qui sotto
(P1-P12) sono quelli di quella sezione.

## Fuori dall'ambito

- L'opzione «cambio armonia».
- La scelta del docente fra più armonizzazioni.
- Le modulazioni: una sola tonalità per brano, con la scelta fra maggiore
  e relativa minore.
- Il jazz come obiettivo: settime su ogni grado e catene di ii-V.
- La seconda di sesta e quarta di passaggio e quella di volta: entra solo
  la quarta e sesta di cadenza.
- Le settime diverse da V7 e dalle settime di dominante secondarie.

## Architettura

Si crea un modulo nuovo, `arranger/armonizzazione.py`, in sola libreria
standard. `analizzatore.py` ha già 1761 righe e l'armonizzatore merita un
file suo.

`analizzatore.armonizza_melodia(sp, melodia)` resta come punto
d'ingresso, con la stessa firma: delega al modulo nuovo. Il nome resta per
non toccare chi lo chiama.

Il calcolo procede in sette fasi:

```
melodia ──► 1. tonalita'  ──► 2. griglia ──► 3. candidati ──► 4. punteggi
                                                                  │
            7. rivolti ◄── 6. Viterbi (successioni + cadenze) ◄──┘
                                    ▲
                     5. frasi (rileva_frasi senza armonia)
```

### 1. Tonalità e modo

```python
def tonalita_della_melodia(sp: Spartito, melodia: List[Nota],
                           frasi: List[Tuple[float, float]]) -> Tuple[int, str]:
    """(tonica come classe d'altezza, "maggiore" | "minore")."""
```

- Si parte dall'armatura prevalente, cioè la più lunga. Le due candidate
  sono il maggiore e la sua relativa minore.
- **Minore** quando, sommando gli indizi, prevale la relativa minore
  (Piston P2 e cap. 4):
  - la melodia chiude il brano o la maggioranza delle frasi sulla tonica
    minore o sulla sua quinta;
  - compare la sensibile alzata (Sol# in La minore) o il sesto alzato in
    salita;
  - le note lunghe e sul battere stanno nella triade di tonica minore.
- In caso di dubbio vince il maggiore.

### 2. Griglia del ritmo armonico

```python
@dataclass
class Tratto:
    inizio: float
    fine: float
    forza: int       # 2 = battere della misura, 1 = meta' misura, 0 = altro
```

`griglia(sp) -> List[Tratto]` divide ogni misura in tratti: sono i punti
in cui l'accordo **può** cambiare.

| Metro | Tratti per misura |
|---|---|
| 4/4, 2/2, 12/8 | 2 (metà misura) |
| 2/4, 3/4, 3/8, 6/8 | 1 (misura intera) |
| 9/8 | 3 (un movimento puntato ciascuno) |
| 5/4, 7/8 e altri | 1 |

Le misure parziali (anacrusi, levare di sezione) formano un tratto solo.

### 3. Accordi candidati

```python
@dataclass(frozen=True)
class Candidato:
    fondamentale: int    # classe d'altezza
    qualita: str         # "maj", "min", "dim", "dom7"
    grado: str           # "I", "ii", "V7", "V/V", ... per tavola e spiegazioni
    secondaria: bool = False
```

- **Maggiore:**
  - I, ii, iii, IV, V, vi;
  - V7;
  - vii° solo come sostituto del V, con un peso più basso;
  - dominanti secondarie: V/ii, V/iii, V/IV, V/V e V/vi, triadi maggiori
    o settime di dominante.
- **Minore** (Piston cap. 4):
  - i, ii°, III, iv, V (maggiore, con la sensibile), V7, VI, VII (maggiore,
    settimo grado naturale) e vii°;
  - dominanti secondarie: V/III (= VII), V/iv, V/V e V/VI.
- **Una dominante secondaria è candidata solo nei tratti in cui la melodia
  contiene la sua sensibile**, cioè la nota alterata rispetto alla
  tonalità (Piston P12): per V/V in Do, il Fa#. Senza quella nota non si
  propone. Così le secondarie non escono a caso.

### 4. Punteggio di un candidato su un tratto

`emissione(tratto, candidato, note_del_tratto, pesi) -> float`

- **Ogni nota della melodia nel tratto** pesa per durata, con un
  moltiplicatore per la posizione: ×1.5 se attacca sul battere del tratto,
  ×1.2 se attacca su un movimento forte.
  - Una nota che appartiene all'accordo conta **+peso**.
  - Una nota estranea conta **−peso × `pesi.estranea`**, ridotto a
    **−peso × `pesi.passaggio`** se è una nota di passaggio o di volta
    (arrivo e partenza per grado congiunto, tempo debole, durata non oltre
    il movimento).
- **Priorità del grado** (P7): I, IV e V contano `pesi.forte`; ii conta
  metà; iii, vi e vii° nulla.
- **Una nota tenuta che attraversa il confine del tratto** resta nota
  comune (P3). Se appartiene sia all'accordo prima sia a quello dopo, il
  cambio non viene penalizzato in più.

### 5. Frasi

Le frasi si prendono da `rileva_frasi(sp, melodia, armonia=None)`. La
funzione accetta già l'armonia assente, così le frasi si calcolano prima
dell'armonia. Per ogni frase servono la nota finale della melodia e la
sua durata.

### 6. Viterbi sui tratti

Lo stato è il candidato. Il costo di passare dal tratto *k* al tratto
*k+1* è:

- **lo stesso accordo:** 0;
- **un accordo diverso:**
  - `pesi.cambio[forza]`, tanto più alto quanto più debole è la posizione
    (P4): cambiare sul battere costa poco, a metà misura di più;
  - più il **costo della successione** dalla tavola di Piston (P6, e
    cap. 4 per il minore): `pesi.abituale` per «di solito»,
    `pesi.a_volte` per «a volte», `pesi.raro` per «meno spesso»,
    `pesi.assente` per le successioni fuori tavola;
  - le dominanti secondarie hanno una regola sola: V/X → X costa
    `pesi.abituale`, ogni altra uscita costa `pesi.raro`.
- **Salto melodico** (P3): se il tratto *k+1* comincia nel mezzo di un
  salto che parte da un tempo debole del tratto *k*, il cambio costa in
  più `pesi.salto`. Se il salto arriva sul battere il costo extra è zero,
  come dice Piston.

**Cadenze** (P11), come premio sugli ultimi due tratti di ogni frase:

| La frase chiude su | Si premia |
|---|---|
| Tonica, nota lunga | V → I (o V7 → I); IV → I ammesso con premio minore |
| 2° o 7° grado | V nell'ultimo tratto (cadenza sospesa) |
| 5° grado | V oppure I; V se è la prima di due frasi parallele (P11) |
| Ultima frase del brano | sempre V → I, premio doppio |

Le due frasi «parallele» sono quelle che `raggruppa_in_periodi` mette
insieme. Se il periodo non c'è, la regola si ignora.

### 7. Rivolti: il basso come linea

`scegli_bassi(accordi, melodia, pesi) -> List[Accordo]` è una seconda
passata con una sua programmazione dinamica. Per ogni accordo sceglie fra
lo stato fondamentale e il primo rivolto; il secondo rivolto è ammesso
solo come quarta e sesta di cadenza (I⁶₄ prima del V finale). Il costo
somma:

- il moto del basso, preferendo grado congiunto e piccoli salti;
- il premio per moto contrario rispetto alla melodia;
- la penalità per tonica ripetuta e per più di tre seste parallele con la
  melodia (P8);
- lo stato fondamentale obbligatorio per I e V in cadenza autentica.

Il risultato va in `Accordo.basso` (slash chord), che il resto del motore
(`rileva_basso`, sigle, basso orchestrale) tratta già. Dopo la regola
«il basso estraneo all'accordo si sostituisce con la nota dopo la barra»,
un rivolto proposto qui è sempre coerente.

### Pesi

Tutti i numeri stanno in una dataclass `Pesi`, con valori di default
scritti nel modulo. Sono i valori tarati sul banco e ognuno ha un commento
con la fonte del principio. Non diventano opzioni per l'utente.

## Uscita

`List[Accordo]`, uno per ogni tratto in cui l'accordo cambia: i tratti
consecutivi con lo stesso accordo si fondono. `confidenza` resta 0.5. Le
sigle scritte nel file continuano a vincere su tutto (regola già in
`analizza`).

Il messaggio di report «lead sheet SENZA SIGLE» resta. Si aggiunge una
riga, nel catalogo IT/EN, con la tonalità scelta e il modo:

> «[Ingresso] Armonia proposta in La minore: controlla le sigle nella
> partitura e correggile nel file se il brano ne usa altre.»

## Banco di prova

`banco_armonia.py` nella radice del progetto, accanto a
`strumenti_analisi.py`, che segue lo stesso schema:

```
python banco_armonia.py XML/
```

Per ogni brano con sigle:

1. ingerisce il file;
2. prende la melodia scritta (`analizza(sp).melodia`);
3. armonizza la sola melodia;
4. confronta movimento per movimento con le sigle del file.

Stampa:

- la percentuale di fondamentali giuste;
- la percentuale di funzioni giuste (tonica = I, iii, vi; sottodominante =
  ii, IV; dominante = V, vii°);
- i cambi veri e i cambi proposti;
- la tonalità e il modo scelti.

Con `--taratura` prova una griglia di pesi con il metodo «uno escluso»:
si tara su tutti i brani tranne uno e si misura su quello, a turno. Così
i pesi non si adattano ai brani su cui si misurano.

I brani di `XML/` sono commerciali e restano fuori dal repository (vedi
**Rilascio**). Il banco è uno strumento da lanciare a mano, non un test.

## Test (`tests/test_pipeline.py`)

Solo melodie costruite nei generatori di `esempi/genera_esempi.py` o di
pubblico dominio:

1. **Tonalità:**
   - l'Inno (lead sheet senza sigle) esce in Do maggiore;
   - una melodia in La minore con il Sol# esce in La minore;
   - la stessa melodia senza Sol# e con chiusura su Do esce in Do maggiore.
2. **Griglia:** il numero di tratti per 4/4, 3/4, 6/8 e 9/8, e
   l'anacrusi come tratto unico.
3. **Ritmo armonico:** una melodia di 4 misure in 4/4 costruita su
   I-V | vi-IV | I-V | I (arpeggi dei due accordi per mezza misura) deve
   produrre almeno 6 cambi e le fondamentali giuste in almeno 6 tratti su 8.
4. **Cadenze:**
   - una frase che chiude sulla tonica lunga finisce con V-I;
   - una che chiude sul 2° grado finisce sul V.
5. **Dominante secondaria:**
   - una melodia in Do con Fa# che sale a Sol prima di una cadenza propone
     V/V;
   - la stessa senza Fa# non la propone.
6. **Rivolti:** su una melodia che scende per grado sopra I-V-I il basso
   proposto si muove per grado (per esempio I - V⁶ - I) e non ripete la
   tonica.
7. **Nessuna regressione:**
   - l'Inno di prova resta almeno all'84% di fondamentali giuste;
   - il `lead_sheet` con le sigle produce la stessa armonia di prima,
     perché le sigle vincono;
   - la musica resta identica fra IT ed EN.
8. **Catalogo:** il messaggio nuovo esiste in entrambe le lingue.

## Criterio di successo

- Sul banco, ogni brano pop migliora rispetto alla tabella iniziale.
  Lo si misura anche con il metodo «uno escluso», non solo con i pesi
  tarati su tutto.
- L'Inno di prova non scende sotto l'84%.
- Ipanema e My Future non peggiorano.
- Tutti i test passano, comprese le regole della melodia: la melodia non
  si tocca mai.
- **Il docente ascolta 3 arrangiamenti** (Let It Be, Dust in the Wind,
  Stand by Me, con le sigle tolte) e conferma che l'armonia regge.

## Rilascio

- Si lavora sul ramo `armonizzazione`, che parte da `tonalita-comoda`.
- `XML/` va aggiunta a `.gitignore` nello stesso lavoro, così il
  `git add -A` del deploy non la carica.
- Gli appunti su Piston (`docs/principi_arrangiamento.md`, sezione 5) si
  committano con il primo task.
- La versione (0.9.8 o 0.9.9) si decide al rilascio di lunedì.

## Rischi

| Rischio | Contromisura |
|---|---|
| Pesi adattati ai 10 brani | Metodo «uno escluso»; test su melodie costruite, indipendenti dal banco |
| Troppi cambi d'accordo (armonia agitata) | Il numero di cambi è nel report del banco e va confrontato con quello vero |
| Il minore riconosciuto male | Il maggiore vince sul dubbio; test dedicati; Dust in the Wind nel banco |
| Dominanti secondarie fuori luogo | Candidate solo con la loro sensibile in melodia |
| Tempi più lunghi del calcolo | Tratti × candidati (~15) × candidati: per 200 tratti sono ~45.000 passi, trascurabili |
