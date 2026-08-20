# Arranger SMIM

Arrangiatore automatico per orchestra scolastica: trasforma uno spartito per
pianoforte (o un audio / link YouTube) in una partitura completa per la
formazione della scuola media a indirizzo musicale, rispettando i vincoli
didattici della classe.

Implementa i 4 moduli della specifica: **Ingestion → Analyzer → Orchestrator →
Exporter**.

---

## Avvio rapido

```bash
pip install -r requirements.txt        # solo streamlit e' davvero necessario
streamlit run app.py                    # interfaccia grafica
```

Da riga di comando:

```bash
python cli.py esempi/inno_alla_gioia.xml \
    --organico flauto=2,clarinetto=1,violino=2,violoncello=1,chitarra=1,pianoforte=1,percussioni=1 \
    --livello "1a Media" --stile Normale -o output
```

Test (nessun framework richiesto):

```bash
python esempi/genera_esempi.py
python tests/test_pipeline.py
```

**Il nucleo non ha dipendenze esterne**: parser MusicXML, parser MIDI, analisi,
arrangiamento, validazione ed export sono scritti sulla libreria standard. Ne
consegue che gira su Windows 10 senza toolchain di compilazione e resta
testabile in CI. `music21` non e' richiesto (in particolare per l'anacrusi, che
viene gestita nativamente).

---

## Architettura

```
arranger/
  modello.py        modello dati interno (Nota, Misura, Spartito, Accordo,
                    Evento, Parte, Partitura, Configurazione)
  ingestione.py     MODULO 1 - MusicXML/MXL, MIDI, audio, YouTube,
                    quantizzazione, riduzione pianistica
  analizzatore.py   MODULO 3.1 - melodia, armonia, basso, groove, frasi
  orchestratore.py  MODULO 3.2 - template di stile, staffetta, voicing
  vincoli.py        MODULO 3.3 - filtri di validazione didattica
  esportatore.py    MODULO 4 - MusicXML 4.0 partwise + MIDI di anteprima
  strumenti.py      registro strumenti + regole per livello
  lilypond.py       MODULO 4b - sorgente .ly + incisione PDF
  ia.py             strato IA opzionale (API Anthropic)
  pipeline.py       orchestrazione end-to-end
app.py              interfaccia Streamlit (Modulo 2)
cli.py              interfaccia a riga di comando
```

### Modulo 1 — Ingestion

| Ramo | Ingresso | Percorso |
|---|---|---|
| A | `.xml`, `.musicxml`, `.mxl` | parser nativo: `divisions`, `backup`/`forward`, accordi, voci, righi, legature di valore, armatura, metro |
| A′ | `.mid`, `.midi` | parser SMF nativo → quantizzazione → riduzione pianistica |
| B | `.mp3`, `.wav`, link YouTube | `yt-dlp` → **Basic Pitch** → MIDI → riduzione pianistica |

> Il ramo B esiste nel motore (`ingestione.da_audio`, `da_youtube`) ma **non e'
> esposto nell'interfaccia pubblica**: la trascrizione automatica e' la parte
> meno affidabile della catena e produrrebbe segnalazioni fuorviatnti. Richiede
> `yt-dlp`, `ffmpeg` e `basic-pitch` installati a parte.

**L'ingresso atteso e' una riduzione PIANISTICA** su due righi (chiave di
violino e di basso) con melodia, armonia e basso gia' scritti. Partiture gia'
orchestrate, parti staccate o file su un rigo solo danno risultati scadenti:
il Modulo 3 assume di poter distinguere melodia, armonia e basso dentro una
scrittura per pianoforte.

La riduzione pianistica quantizza, sceglie un punto di divisione adattivo fra
le due mani, limita la densita' per rigo mantenendo estremi e note lunghe, e
risolve le sovrapposizioni: il risultato e' un master a due righi leggibile.

**Misure parziali**: il parser fa una prima passata su tutte le parti per
misurare il contenuto reale di ogni battuta. Il metro resta sempre
l'indicazione di tempo; la misura vale meno del metro **solo** in quattro casi:

1. e' la prima del brano → **anacrusi** (`Misura(numero=0, anacrusi=True)`);
2. e' l'ultima → chiusura tronca;
3. il file la dichiara `implicit="yes"`;
4. si completa esattamente con la vicina → battuta spezzata in due (il levare
   di sezione dopo un ritornello: 5 crome + 1 croma in 6/8).

In ogni altro caso il contenuto e' corto solo perche' l'esportatore ha omesso
le pause finali, e la misura resta piena: **l'anacrusi si riconosce a inizio
brano, il resto scorre da se'.** Senza il punto 4 le battute spezzate vengono
gonfiate al metro pieno e l'arrangiamento slitta (e si allunga di una battuta);
senza la restrizione, un file esportato in modo pigro fa accorciare il brano.

**Tempi composti**: in 6/8, 9/8 e 12/8 il movimento e' la semiminima puntata.
`Misura.unita_movimento` lo espone, e lo usano il riconoscimento armonico (un
accordo per movimento reale, non per croma), il walking bass, il comping e i
pattern di percussione.

### Modulo 3.1 — Analisi semantica

- **Melodia** — rilevatore *bidirezionale*: tre ipotesi (voce superiore,
  inferiore, neutra) generate con un Viterbi sugli attacchi e confrontate con
  un punteggio di qualita' melodica globale (varieta' di altezze, durata media,
  moto congiunto, penalita' per ribattuti e salti ampi).
  Due accorgimenti fanno la differenza:
  1. gli stati includono la **nota gia' in corso**, cosi' una melodia in valori
     lunghi non viene catturata dagli attacchi dell'accompagnamento;
  2. la salienza "estremo acuto / estremo grave" e' calcolata su tutte le note
     *sonanti*, non solo su quelle che attaccano.

  La scelta fra le ipotesi e' **per misura**, non una sola per tutto il brano:
  un secondo Viterbi valuta la qualita' melodica locale (con una misura di
  contesto per lato) e penalizza i cambi d'ipotesi, cosi' la linea viene
  seguita anche quando migra da una mano all'altra per una sezione e non
  flip-flappa da una battuta all'altra.

  Risultato: la melodia viene trovata quando sta alla mano sinistra per tutto
  il brano (`esempi/melodia_al_basso.xml`) e quando ci passa solo per alcune
  battute (`esempi/melodia_che_migra.xml`).

- **Armonia** — dedotta dal materiale realmente scritto, con tre meccanismi
  che tengono a bada il ritmo armonico (che altrimenti esplode a un accordo per
  nota di passaggio):
  1. le note brevi pesano meno — sono figurazione, non armonia — e il basso
     pesa piu' delle voci interne;
  2. un **priore tonale** favorisce i gradi diatonici e le triadi comuni, e
     una settima viene scelta solo se la settima c'e' davvero; la tonalita' e'
     stimata su finestra scorrevole, quindi le **modulazioni** vengono seguite;
  3. un **Viterbi sui movimenti** penalizza il *cambio* d'accordo: un accordo
     si mantiene finche' le prove contrarie non sono forti.

  Su una sonatina di 89 battute questo porta da 236 accordi (con sigle tipo
  `F#m7b5` nate da note di passaggio) a 96, per il 93% triadi e settime di
  dominante.

- **Basso** — nota piu' grave della mano sinistra; **se non appartiene
  all'accordo viene sostituita dalla fondamentale**, come da specifica.

- **Dinamiche** — i segni presenti nel MusicXML originale (`<dynamics>` o
  `sound dynamics=`) **e le forcelle** `<wedge>` (crescendo / diminuendo)
  vengono letti, conservati nello `Spartito` e riportati su tutte le parti,
  sia nell'export MusicXML sia in LilyPond (`\<`, `\>`, `\!`).

- **Groove e frasi** — pattern d'attacco dominante, suddivisione prevalente,
  segmentazione in frasi (pause, note lunghe, gruppi di 4 misure) usata per la
  staffetta.

### Modulo 3.2 — Motore di arrangiamento

| Stile | Comportamento |
|---|---|
| **Normale** | Flauti/Violini 1 sulla melodia, chitarra e piano sugli accordi a blocchi, violoncello sul basso, clarinetto/sax/violini 2 su controcanti |

Gli accordi a blocchi non vengono stesi sulla durata dell'armonia ma disposti
sul **groove** rilevato: se l'originale ha basso sul primo movimento e accordo
sul secondo (il pattern della *Gymnopedie*), l'accompagnamento lo riproduce, e
sugli strumenti a due righi la destra non raddoppia l'attacco del basso.
| **Cinematico** | Archi in tremolo e pizzicato, pianoforte ad arpeggi ampi, fiati su pad lunghi, glockenspiel che raddoppia la melodia **nei climax** (individuati per densita' e registro) |
| **Jazz** | Crome in terzina (notate come terzine reali, con `time-modification`), walking bass su violoncello o mano sinistra, chitarra in comping sul levare, percussioni su pattern ride/charleston |

**Divisi differenziati**: due pianoforti (o due chitarre) non suonano la stessa
parte. Il primo accompagna, il secondo prende melodia o controcanto e cambia
scrittura (arpeggi invece di blocchi, basso sostenuto invece di basso
articolato). Il campo `Parte.variante` porta l'indice del diviso ed e' il punto
in cui aggiungere altre scritture alternative.

**Staffetta della melodia**: le frasi vengono distribuite a rotazione fra gli
strumenti in grado di portarla, con raddoppi facoltativi — la melodia passa
davvero di mano durante il brano. L'utente puo' indicare esplicitamente i
solisti con `Configurazione.strumenti_melodia` (nell'interfaccia: "Chi porta la
melodia"); se la lista e' vuota decide il motore.

### Modulo 3.3 — Constraint Checker

Filtri applicati in cascata, ciascuno con registrazione nel report per numero
di misura:

1. **Polifonia** — fiati e archi restano monodici; le note in esubero vengono
   assegnate ai divisi (Violino 2, Flauto 3…).
2. **Estensione** — trasposizione d'ottava finche' la nota rientra
   nell'ambito dello strumento *per quel livello*.
3. **Alterazioni** — in 1ª media le note fuori tonalita' vengono ricondotte
   alla scala **nell'accompagnamento**; la melodia non viene mai toccata, e
   nemmeno le note che appartengono all'armonia corrente (sensibili, accordi
   delle modulazioni): una nota difficile e' molto meglio di una nota
   sbagliata.
4. **Salti** — limite per livello (5ª in 1ª media), applicato per rigo e solo
   alle linee monodiche, mai agli accordi.
5. **Idiomatico** — diteggiature di chitarra verificate su un modello reale di
   tastiera (6 corde, apertura massima, fondamentale al basso, capotasto
   limitato per livello); prima posizione e cambi di corda per gli archi;
   apertura della mano al pianoforte.
6. **Incroci** — sugli strumenti a due righi la mano destra non scende mai
   sotto la sinistra e non ne raddoppia le note: si alza la destra, o si
   abbassa la sinistra quando e' la destra a portare una melodia grave.
7. **Ritmico** — valori inferiori al minimo del livello vengono fusi
   (niente crome in 1ª media, niente semicrome fino alla 3ª), **mai oltre la
   stanghetta**.

> **Il metro non si tocca mai.** Nessun filtro e nessun livello puo' alterare
> l'indicazione di tempo o produrre misure irregolari: in ingestione la durata
> di ogni misura e' quella dettata dal metro (unica eccezione l'anacrusi), e
> l'accompagnamento generato viene spezzato sulle stanghette in modo che il
> tempo forte sia sempre riattaccato. La melodia invece non viene mai spezzata:
> le sue sincopi restano quelle dell'originale.

> La melodia resta **sempre** intatta nelle altezze e nel profilo: subisce solo
> trasposizioni d'ottava, e per frase intera, mai nota per nota. Non le si
> applicano nemmeno il filtro ritmico ne' quello dei salti.

### Linee non frammentate

Tutte le correzioni d'ottava lavorano sul **tratto di frase** (delimitato dai
respiri), mai sulla singola nota: spostare una nota sola crea un salto
all'andata e uno al ritorno, ed e' cosi' che una scala si riempie di balzi
d'ottava. In concreto:

* il filtro estensione traspone il tratto intero;
* il filtro dei salti traspone **tutto il seguito** del tratto;
* frasi consecutive affidate allo stesso strumento formano un blocco unico, con
  una sola scelta d'ottava;
* le linee costruite accordo per accordo (basso, controcanto, pad) passano per
  una levigatura che porta ogni nota all'ottava piu' vicina alla precedente;
* alle giunzioni fra accompagnamento e melodia dentro la stessa parte si muove
  solo l'accompagnamento, e se il balzo resta ampio si apre un **respiro**
  prima dell'entrata.

Sulla stessa sonatina gli interventi automatici scendono da 883 a 168, e dei
31 salti d'ottava rimasti 26 sono gia' nell'originale.

### Modulo 4 — Export

MusicXML 4.0 partwise con: nomi e abbreviazioni degli strumenti, graffa del
pianoforte (`<staves>2</staves>` con chiavi di violino e basso),
**armature di chiave trasposte** e `<transpose>` per clarinetto/sax/tromba,
chiave di percussione con `<unpitched>`, sigle accordali (`<harmony>`) sulla
chitarra, articolazioni (staccato, accento, tenuto, tremolo, pizz.), legature
di valore ai cambi di misura, terzine, metronomo e indicazione di swing.

La metrica di ogni misura e' verificata dai test: ogni voce somma esattamente
la durata metrica, condizione necessaria perche' Dorico, Sibelius e MuseScore
aprano il file senza correzioni.

In piu' viene generato un **MIDI di anteprima** per l'ascolto rapido.

### Modulo 4b — Export LilyPond

`arranger/lilypond.py` produce il sorgente `.ly` e, se l'eseguibile e' nel PATH,
incide direttamente il PDF:

```bash
python cli.py esempi/inno_alla_gioia.xml --organico flauto=2,chitarra=1,pianoforte=1 \
    --stile Jazz --livello "3a Media" --pdf
```

```python
from arranger.lilypond import esporta_lilypond, incidi_pdf
esporta_lilypond(risultato.partitura, "partitura.ly")
incidi_pdf("partitura.ly")            # -> partitura.pdf
```

Copre: `\partial` per l'anacrusi, `PianoStaff` con graffa e due righi,
`DrumStaff` per le percussioni, `StaffGroup` per famiglia, armature trasposte
coerenti con il MusicXML, terzine raggruppate **un movimento per volta**
(piu' leggibili di un'unica parentesi per misura), legature di valore,
`ChordNames` per le sigle della chitarra, articolazioni e nomi/abbreviazioni
degli strumenti a inizio accollatura. Nomenclatura italiana
(`\language "italiano"`).

Se hai gia' un engraver LilyPond, il punto di aggancio e' l'oggetto
`Partitura`: `EsportatoreLilyPond` legge solo quello, quindi puoi sostituire
la generazione del sorgente mantenendo intatti i moduli 1–3.

---

## Strato IA (facoltativo)

Attivo solo con `ANTHROPIC_API_KEY` impostata e il pacchetto `anthropic`
installato; se manca, tutto continua a funzionare con le regole interne.
L'IA interviene dove le regole deterministiche sono deboli, cioe' nelle scelte
di gusto:

1. `piano_orchestrazione` — chi porta la melodia frase per frase e dove
   collocare i climax;
2. `revisiona_armonia` — revisione delle sigle con bassa confidenza secondo la
   logica tonale;
3. `relazione_didattica` — sintesi in italiano degli interventi del validatore,
   scritta per il docente.

---

## Pubblicazione su Streamlit Community Cloud

Il repository e' gia' pronto: `requirements.txt` con la sola dipendenza
`streamlit`, `.streamlit/config.toml` con tema e limite di upload,
`.gitignore` che esclude `secrets.toml`. Il modulo di feedback invia una mail
via SMTP leggendo le credenziali da `st.secrets["email"]`; se mancano, l'app
non va in errore ma offre un link `mailto`. Vedi
`.streamlit/secrets.toml.esempio` per le chiavi attese.

## Limiti noti / possibili estensioni

- I ritornelli non vengono ancora "srotolati": un brano con `<repeat>` viene
  letto in forma lineare.
- Il riconoscimento accordale non modula esplicitamente: usa l'armatura
  iniziale per l'ortografia delle note (diesis o bemolle).
- Le percussioni non intonate usano pattern fissi per stile; un `groove
  library` per stile e' l'estensione naturale.
- L'incisione PDF non e' inclusa: l'output MusicXML e' pensato per essere
  rifinito dal docente nel proprio software di notazione (o inciso con
  LilyPond a valle).
