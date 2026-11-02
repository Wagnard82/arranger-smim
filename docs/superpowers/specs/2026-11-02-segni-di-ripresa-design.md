# Segni di ripresa: ritornelli, volte, D.S., D.C., Coda, Fine

*Specifica di design, 2 novembre 2026. Uscita prevista con la 0.9.8 (lunedì 9 novembre 2026).*

## Problema

Oggi l'ingestione legge il MusicXML in fila e scarta tutti i segni di
ripresa. Le conseguenze sono tre:

- la 1ª e la 2ª volta si susseguono come misure normali, senza il
  ritornello in mezzo;
- D.S., D.C., Coda e Fine non vengono eseguiti;
- nella partitura arrangiata i segni non compaiono più, e il MIDI di
  anteprima suona una forma sbagliata.

## Obiettivo

1. Riconoscere nel MusicXML d'ingresso i segni di ripresa: ritornelli,
   volte, Segno, Coda, «To Coda», D.S., D.C., «al Coda», «al Fine» e Fine.
2. Riscriverli **nelle stesse misure** della partitura arrangiata, su
   tutte le parti, comprese le parti staccate.
3. Far suonare al MIDI di anteprima la forma vera, cioè srotolata.
4. Segnalare nel report le strutture incoerenti, in IT e in EN.

**Decisione (2/11/2026):** si arrangia la forma scritta, una volta sola.
Le ripetizioni suonano identiche. L'opzione «tutto per esteso» resta per
dopo e riuserà `ordine_esecuzione`.

## Fuori dall'ambito

- Arrangiamento diverso alla ripetizione (entrate a gradini, staffetta
  della melodia fra un passaggio e l'altro).
- La partitura «per esteso», scritta tutta di seguito.
- Segni senza riscontro nel MusicXML (per esempio «bis» scritto a mano
  sopra una misura). Si riconoscono solo i testi dell'elenco qui sotto.
- Le analisi (frasi, sezioni, levigatura, salti) restano sulla forma
  scritta. Un salto fra la fine della 1ª volta e l'inizio della 2ª può
  quindi essere valutato come se le due misure fossero contigue. È un
  limite noto: va scritto nel README.

## Modello dati (`arranger/modello.py`)

Si aggiunge un campo, senza ristrutturare:

```python
@dataclass
class SegniRipresa:
    """Segni di ripresa di una misura, come scritti nell'originale."""

    ritornello_inizio: bool = False    # |: sulla stanghetta sinistra
    ritornello_fine: int = 0           # :| sulla destra; esecuzioni totali (times, 2 di default)
    volte: Tuple[int, ...] = ()        # volte a cui appartiene la misura: (1,), (2,), (1, 2)
    volta_apre: bool = False           # la parentesi della volta comincia qui
    volta_chiude: str = ""             # "stop" (con gancio), "discontinue" (aperta), "" se continua
    segno: bool = False                # Segno all'inizio della misura
    coda: bool = False                 # simbolo di Coda all'inizio della misura
    al_coda: bool = False              # «To Coda» alla fine della misura
    fine: bool = False                 # «Fine» alla fine della misura
    salto: str = ""                    # "ds" o "dc" alla fine della misura
    salto_verso: str = ""              # "coda", "fine" o "" (D.S./D.C. semplice)
    testo_salto: str = ""              # il testo come scritto, per riscriverlo uguale

    @property
    def vuoti(self) -> bool:
        """True se la misura non porta nessun segno di ripresa."""
```

In `Misura`: `ripresa: SegniRipresa = field(default_factory=SegniRipresa)`.

`Partitura.misure` viene già dalle misure del master, quindi i segni
arrivano all'esportatore senza toccare l'orchestratore.

## Lettura (`arranger/ingestione.py`)

Una nuova funzione `_segni_ripresa(parti) -> Dict[int, SegniRipresa]`,
chiamata in `da_musicxml` subito dopo `_griglia_misure`. Legge tutte le
parti e unisce i segni per indice di misura: basta che un segno compaia in
una parte. I canali sono quattro.

| Fonte nel MusicXML | Segno |
|---|---|
| `<barline location="left"><repeat direction="forward"/>` | `ritornello_inizio` |
| `<barline location="right"><repeat direction="backward" times="n"/>` | `ritornello_fine = n` (2 se manca) |
| `<ending number="1, 2" type="start\|stop\|discontinue">` | `volte`, `volta_apre`, `volta_chiude`; le misure in mezzo ereditano le volte |
| `<direction-type><segno/>` / `<coda/>` | `segno` / `coda` |
| `<sound dalsegno=… dacapo="yes" tocoda=… fine=…>` | `salto`, `al_coda`, `fine` |
| `<words>` riconosciuti (vedi sotto) | come sopra |

**Testi riconosciuti.** Il confronto ignora maiuscole, punti e spazi.

- «D.S.», «Dal Segno», «D.S. al Coda», «D.S. al Fine»
- «D.C.», «Da Capo», «D.C. al Coda», «D.C. al Fine»
- «To Coda», «Al Coda», «Vai alla Coda», «Fine»
- «Coda» da solo, cioè l'etichetta della sezione, vale come `coda`.

Il testo originale si conserva in `testo_salto`.

**Coda doppia.** Dorico e MuseScore mettono spesso il simbolo di Coda
anche nella misura del «To Coda». La destinazione del salto è la prima
misura con `coda` che viene **dopo** la misura del D.S./D.C.

## Ordine di esecuzione (`arranger/ripetizioni.py`, nuovo, solo stdlib)

```python
def ordine_esecuzione(misure: List[Misura]) -> List[int]:
    """Indici delle misure nell'ordine in cui si suonano."""

def controlla(misure: List[Misura], lingua: str) -> List[str]:
    """Messaggi di report per le strutture incoerenti (catalogo t())."""

def confini(misure: List[Misura]) -> Set[int]:
    """Misure dopo le quali la successiva scritta non e' sempre quella suonata."""
```

**Regole di `ordine_esecuzione`:**

- **Ritornello.** Un `:|` rimanda al `|:` precedente più vicino, oppure
  all'inizio del brano se non ce n'è uno. Si ripete `ritornello_fine - 1`
  volte.
- **Volte.** Al passaggio *p* di un ritornello si saltano le misure la
  cui tupla `volte` non contiene *p*. L'ultima volta, di solito senza
  `:|`, prosegue in avanti.
- **D.S. / D.C.**
  - Il salto si esegue una volta sola, alla fine della misura che lo
    porta: verso il Segno per il D.S., verso l'inizio per il D.C.
  - Dopo il salto non si ripetono i ritornelli e, dentro le volte, si
    prende l'ultima. È la convenzione corrente; la scelta va indicata nel
    report.
  - «To Coda» e «Fine» valgono **solo dopo** il salto. «To Coda» porta
    alla Coda di destinazione (vedi sopra); «Fine» chiude il brano alla
    fine della misura.
- **Protezione.** Se l'ordine supera 4 volte il numero di misure, o se
  un salto non ha destinazione, si torna all'ordine lineare e il report
  lo segnala.

**Messaggi di `controlla`.** Vanno in `lingua.py`, IT ed EN, con gli
stessi segnaposto:

- una riga informativa con la forma riconosciuta, per esempio
  `[Forma] Ritornelli e volte riconosciuti: si suonano le misure 1-8, 1-6, 9-12`;
- un avviso per:
  - una volta fuori da un ritornello;
  - un `:|` senza `|:` dopo un altro `:|` (rimanda all'inizio: va detto);
  - un D.S. senza Segno;
  - un «To Coda» senza Coda;
  - un «al Fine» senza Fine;
  - il ritorno all'ordine lineare.

## Confini di ripresa

Un confine è la fine di una misura dopo la quale, almeno in un
passaggio, non si suona la misura scritta successiva. I casi sono:

- la fine di un `:|`;
- l'ultima misura prima di una volta;
- la fine di una volta;
- la misura con D.S. o D.C.;
- la misura con «To Coda»;
- la misura con «Fine».

Un passo nuovo, `ripetizioni.taglia_ai_confini(partitura)`, viene
chiamato in `pipeline.esegui` dopo `vincoli.valida` e prima
dell'esportazione. Spezza ogni evento che attraversa un confine e toglie
`legata_dopo` sul frammento che lo precede.

Le altezze non cambiano, quindi la regola «melodia mai alterata» resta
rispettata. Cambia solo la durata scritta oltre il confine, che in quel
punto non ha un seguito nell'esecuzione. Se nell'originale una legatura
di valore entrava nella 1ª volta, nella partitura sparisce: va segnalato
nel report quando il frammento è `letterale`.

## Scrittura

### MusicXML (`arranger/esportatore.py`, in `_parte`)

**Su tutte le parti:**

- `<barline location="left">` con `<repeat direction="forward"/>`;
- `<barline location="right">` con `<bar-style>light-heavy</bar-style>`
  e `<repeat direction="backward" times="n"/>`; `times` si scrive solo se
  è diverso da 2;
- `<ending number="…" type="start|stop|discontinue">` sulle stanghette
  di apertura e di chiusura;
- le direzioni `<segno/>` e `<coda/>` all'inizio della misura, sopra il
  rigo;
- i `<words>` di «To Coda», «Fine» e D.S./D.C. alla fine della misura,
  con il testo originale o, se manca, la forma standard presa dal
  catalogo di `lingua.py`. Le due lingue coincidono, tranne «Al Coda»
  (IT) e «To Coda» (EN).

**Solo sulla prima parte:** il `<sound>` corrispondente (`segno`, `coda`,
`dalsegno`, `dacapo`, `tocoda`, `fine`), così che i programmi di
notazione eseguano i salti una volta sola.

*Da verificare in Dorico 5 e in MuseScore 4:* i Segni e le Code ripetuti
in tutte le parti potrebbero essere importati come doppi. Se succede, si
scrivono le direzioni solo nella prima parte di ogni gruppo
(`<part-group>`) e si lascia che le parti staccate le ereditino. La
decisione si prende sulla prova reale.

### MIDI di anteprima (`esporta_midi`)

Si srotola secondo `ordine_esecuzione`. Per ogni misura suonata si
prendono i frammenti di `taglia_su_misura(eventi, m)` e si spostano al
tempo di esecuzione. Senza segni di ripresa il MIDI resta identico a
oggi: un test lo verifica byte per byte.

### LilyPond (`arranger/lilypond.py`)

Si scrivono stanghette `\bar ".|:"`, `\bar ":|."` e `\bar ":|.|:"`, le
volte con `\set Score.repeatCommands`, `\mark \markup { \musicglyph
"scripts.segno" }` e i testi. Va **segnalato come non verificato** se
non si incide almeno un PDF di prova con LilyPond installato.

## Anteprima nel browser

OSMD disegna dal MusicXML ritornelli e volte. Il lettore MIDI suona la
versione srotolata. Non serve altro.

## Test (`tests/test_pipeline.py`)

**Esempi nuovi** in `esempi/genera_esempi.py`:

- `ritornello.xml`: 8 misure con `|: :|`;
- `volte.xml`: ritornello con 1ª e 2ª volta;
- `ds_al_coda.xml`: Segno, To Coda, D.S. al Coda e Coda, con la Coda
  doppia;
- `dc_al_fine.xml`: Fine e D.C. al Fine;
- `ritornello_levare.xml`: ritornello che comincia in levare, con le
  misure parziali.

**Verifiche:**

1. L'ingestione legge i segni giusti nelle misure giuste, anche quando
   arrivano solo dai `<words>` o solo dai `<sound>`.
2. `ordine_esecuzione` dà la sequenza attesa per ogni esempio, oltre
   alla `times="3"`, alle volte «1, 2» e alla protezione da cicli.
3. `controlla` produce gli avvisi attesi su file rotti costruiti nel
   test.
4. Il MusicXML esportato contiene `<repeat>`, `<ending>`, `<segno>`,
   `<coda>` e i `<words>` nelle misure attese, in tutte le parti; il
   `<sound>` è solo nella prima.
5. Nessun evento attraversa un confine di ripresa e nessuna legatura di
   valore lo supera.
6. La durata del MIDI srotolato è uguale alla somma delle misure
   suonate; senza segni il MIDI è identico a prima.
7. La musica è identica fra IT ed EN anche con i segni.
8. `test_cataloghi_completi` copre i messaggi nuovi.

**Repertorio reale.** Servono 2 o 3 MusicXML veri, esportati da
programmi diversi, con ritornelli, volte e un D.S. al Coda. Su questi
file:

- si confronta l'ordine di esecuzione con la partitura;
- si apre l'uscita in Dorico e in MuseScore e si controllano i segni
  doppi.

Organici realistici: 4 famiglie, al massimo 2 parti per strumento.

## Rilascio 0.9.8

Si segue la lista di `CLAUDE.md`:

- `VERSIONE`, `PRECEDENTE`, `COMPILATO`, `NOVITA` e `NOVITA_EN`;
- `VERSIONE_INTERFACCIA` e il README; dal README si toglie il limite noto
  «i ritornelli non vengono srotolati» e si aggiunge il limite
  sull'analisi della forma scritta;
- `python controllo_file.py --scrivi`;
- tutti i test.

## Rischi

| Rischio | Contromisura |
|---|---|
| Ogni programma di notazione scrive i salti a modo suo | Quattro canali di lettura; prova su file di tre programmi diversi |
| Segni doppi all'importazione | Prova in Dorico e MuseScore prima del rilascio; ripiego su una sola parte per gruppo |
| Convenzione dopo il D.S. (ritornelli non ripetuti) diversa da quella voluta | La scelta è dichiarata nel report; se serve diventa un'opzione dopo la 0.9.8 |
| Tempi stretti | LilyPond è l'ultima voce; se manca il tempo esce segnalato come non verificato |
