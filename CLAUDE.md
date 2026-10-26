# ScoreCraft Edu (ex Arranger SMIM) — istruzioni per Claude Code

Conversazioni e commenti nel codice **in italiano**.

## Scopo

App Streamlit che trasforma uno spartito MusicXML in una partitura per
l'orchestra di una scuola media a indirizzo musicale (SMIM), rispettando i
limiti didattici di ogni livello. L'output è un MusicXML da rifinire in
Dorico, MuseScore o Sibelius. Il software serve all'autore (docente di
pianoforte) come strumento di lavoro, e in prospettiva sarà venduto ai
singoli docenti.

## Stato attuale: v0.9.6 (26 ottobre 2026)

- **Tolto (0.9.0):** ingresso da audio (Demucs, Basic Pitch, librosa/pyin,
  beat_this, yt-dlp), da PDF/OMR e da MIDI. L'ingresso è **solo MusicXML**.
  La trascrizione voce→MIDI vive in un progetto separato (`~/voicemidi`).
- **Decisione del 22/10/2026:** l'ingresso da PDF tramite OMR **si
  reintroduce**, come passo a monte che produce un MusicXML. Il motore
  dell'arrangiatore continua a leggere solo MusicXML. Prova di
  fattibilità con Audiveris fatta in locale (mini-app in `prova_omr/`,
  esclusa dal repository); l'introduzione è **rimandata** a dopo la 0.9.6:
  vedi «Prossimi passi».
- **Aggiunto:**
  - lead sheet (melodia + sigle) riconosciuto in automatico;
  - livelli per strumento e per singolo leggio;
  - versione inglese (0.9.3);
  - feedback via mail con allegati (0.9.4);
  - controllo dei file all'avvio tramite `manifesto.json` (0.9.5);
  - corno in Fa, mani del pianoforte al loro posto, due pianoforti
    indipendenti, melodia scritta sempre usata, travature per Dorico (0.9.6).
- **Test:** 1158 verifiche, tutte superate sulla 0.9.6.
- La cartella locale `~/arranger_smim` è stata riallineata alla 0.9.5 il
  22/10/2026. I file della vecchia v0.7.2, compresi quelli della pipeline
  audio, sono archiviati in `_vecchio_v0.7.2/`. **Non sono codice attivo:**
  non leggerli né importarli come riferimento. La cartella **non è ancora
  un repository git**.
- Il deploy è su Streamlit Community Cloud, dal repository GitHub
  `arranger-smim`. *Da verificare:* dove sta il clone git locale.

## Ambiente

- Mac (Apple Silicon), VS Code, cartella `~/arranger_smim/`.
- Virtualenv `.venv312`, Python 3.12 (3.12.14).
  - Python 3.14 è stato provato ed è risultato incompatibile con le
    dipendenze ML dell'epoca: non usarlo.
  - Esiste anche una vecchia `.venv`. *Da verificare* se serve ancora.
- Il nucleo usa solo la libreria standard. `requirements.txt` contiene
  `streamlit` e `anthropic` (facoltativo); `music21` è opzionale e commentato.

```bash
source .venv312/bin/activate
streamlit run app.py                 # interfaccia (?lang=en per l'inglese)
python tests/test_pipeline.py        # test, solo stdlib, nessun framework
python cli.py esempi/inno_alla_gioia.xml --organico flauto=2,violino=2,pianoforte=1 \
    --livello "1a Media" -o output   # riga di comando (--lingua en)
python controllo_file.py --scrivi    # rigenera manifesto.json (prima di ogni rilascio)
python controllo_file.py             # verifica che i file corrispondano al manifesto
```

- Segreti: `.streamlit/secrets.toml` (SMTP per il feedback, chiave
  Anthropic). Modello in `.streamlit/secrets.toml.esempio`. **Mai committarli.**
- `.gitignore` esclude `.venv312/` e `_vecchio_v0.7.2/`.

## Architettura

Pipeline: **ingestione → analizzatore → orchestratore → vincoli → esportatore**.

| File | Ruolo |
|---|---|
| `arranger/modello.py` | Modello dati condiviso. Durate in quarti (float), altezze MIDI a suono reale, anacrusi esplicita (misura 0) |
| `arranger/ingestione.py` | MusicXML/MXL → `Spartito`. Riconosce riduzione pianistica, solista + pianoforte, lead sheet |
| `arranger/analizzatore.py` | Melodia, armonia, basso, groove, frasi, periodi, sezioni |
| `arranger/distribuzione.py` | Casting dei ruoli: ogni parte è valutata sul **proprio** livello |
| `arranger/orchestratore.py` | Costruzione delle parti, stili, staffetta della melodia, riempimenti |
| `arranger/vincoli.py` | Filtri didattici in cascata, ciascuno registrato nel report con il numero di misura |
| `arranger/strumenti.py` | Registro degli strumenti (estensioni per livello) e regole dei livelli |
| `arranger/esportatore.py` / `lilypond.py` | MusicXML 4.0 + MIDI di anteprima / sorgente `.ly` |
| `arranger/pipeline.py` | `esegui()`: dall'inizio alla fine |
| `arranger/ia.py` | Strato IA opzionale. Il motore funziona al 100% senza |
| `arranger/frasi_music21.py` | Rilevatore di frasi avanzato, opzionale |
| `arranger/lingua.py` | Etichette IT/EN e catalogo dei messaggi del report `t()` |
| `arranger/testi_interfaccia.py` | Testi dell'interfaccia IT/EN `ui()` |
| `arranger/feedback.py` | Mail di feedback con allegati, testabile senza Streamlit |
| `arranger/versione.py` | `VERSIONE`, `NOVITA` (IT), `NOVITA_EN`, mostrati nell'app |
| `app.py` | Interfaccia Streamlit. Controlla i file **prima** di importare il motore |
| `controllo_file.py` + `manifesto.json` | Impronte SHA-256 dei file, contro i deploy parziali |
| `esempi/genera_esempi.py` | Genera i MusicXML di prova usati da test e demo |

## Regole musicali da non violare

- **Melodia:**
  - mai alterata in altezze e profilo; ammessa solo la trasposizione d'ottava,
    per blocco intero;
  - niente filtro ritmico né filtro dei salti sulla melodia;
  - la melodia può tacere, può stare al basso o essere divisa fra le due mani;
  - la nota più acuta di un accordo non è automaticamente melodia.
- **Materiale dell'originale:** tutto ciò che è copiato dall'originale è
  marcato `letterale` e resta fuori dai filtri di estensione, salti,
  alterazioni, incroci e levigatura.
- **Sigle:** le sigle scritte nel file prevalgono sull'analisi armonica.
- **Basso:** una nota di basso estranea all'accordo si sostituisce con la
  fondamentale (nei rivolti, con la nota dopo la barra).
- **Metro e anacrusi:** il metro non si tocca mai. Ogni misura ha la durata
  del metro, con la sola eccezione dell'anacrusi. L'accompagnamento si spezza
  sulle stanghette, la melodia no.
- **Livelli:**
  - le chiavi interne sono `1a Media` / `2a Media` / `3a Media`; in inglese si
    mostrano come Grade 1/2/3 e "Grade 2" o "2" vengono normalizzati;
  - precedenza: leggio > strumento > classe;
  - i leggii successivi al primo non suonano mai sopra il primo e hanno
    valori più larghi;
  - eccezione: Pianoforte 1 e 2 sono strumenti distinti e possono
    incrociarsi; conta solo che non si incrocino le mani dello stesso
    pianoforte. Il secondo ha comunque valori più larghi.
- **Organico:** fiati e archi sono monodici, le note in eccesso vanno ai
  divisi. La destra del pianoforte non scende sotto la sinistra.
  Raddoppi e staffetta della melodia sono ammessi.
- **Lingua:** cambia solo i nomi, mai le scelte musicali. Un test verifica
  che la musica sia identica fra IT ed EN.

## Decisioni prese: cosa NON reintrodurre

- Ingresso da audio, YouTube e MIDI nell'arrangiatore. Il modulo di
  feedback invece può ricevere PDF, MIDI e immagini come allegati; un test lo
  controlla.
- Il PDF/OMR **non** rientra in questo elenco dal 22/10/2026. Si reintroduce
  solo come convertitore PDF → MusicXML separato dal nucleo: il nucleo
  resta in sola libreria standard e non sa nulla dell'OMR. Il codice OMR
  della v0.7.2 in `_vecchio_v0.7.2/` resta escluso: si riscrive da capo.
- `madmom`: non compatibile con Python 3.12.
- La distribuzione delle durate come metrica di qualità: aveva lasciato
  passare un bug che fondeva le note. Si confronta nota per nota con
  riferimenti reali.
- Testi dell'interfaccia o messaggi del report scritti a mano dentro `app.py`
  o nel motore: vanno nei cataloghi, **in entrambe le lingue**, con gli stessi
  segnaposto (lo controlla `test_cataloghi_completi`).
- Livelli rinominati nelle chiavi interne: si cambia solo l'etichetta.

## Da non riscrivere senza chiedere

*Proposta ricavata dalle decisioni sopra: da confermare.*

- `arranger/modello.py`: modello dati condiviso da tutti i moduli. Per
  aggiungere un campo si aggiunge, senza ristrutturare.
- In `distribuzione.py`, la logica di idoneità per parte e per livello.
- In `ingestione.py`, il riconoscimento delle tre forme di spartito.
- In `vincoli.py`, l'ordine dei filtri e l'esenzione `letterale`.
- `controllo_file.py` e il controllo all'inizio di `app.py`: devono restare
  **prima** degli import di `arranger`.
- `versione.py`: si aggiungono voci, lo storico non si cancella.

## Modo di lavorare

- **Un problema alla volta.** Si verifica su repertorio reale (MusicXML veri)
  e si aspetta conferma prima di passare al successivo.
- **Diagnosi sui file veri** che l'utente carica o riceve dal feedback
  (`impostazioni.json` riproduce l'arrangiamento:
  `Configurazione(**json.load(...))`), non su ipotesi.
- **Distinguere sempre il codice verificato** (eseguito, testato) da quello
  scritto solo dalla documentazione. Il codice non verificato si segnala nella
  docstring e nel resoconto.
- Ogni correzione o funzione nuova ha un test in `tests/test_pipeline.py`.
- Nelle prove sul repertorio, organici realistici: **4 famiglie di
  strumenti** (fiati, ottoni, archi, corde, tastiere, percussioni) e **al
  massimo 2 parti per strumento**.
- **A ogni rilascio:**
  1. aggiornare `VERSIONE`, `PRECEDENTE`, `COMPILATO` e `NOVITA`/`NOVITA_EN`
     in `versione.py`;
  2. aggiornare `VERSIONE_INTERFACCIA` in `app.py` e la versione nel README;
  3. eseguire `python controllo_file.py --scrivi`;
  4. eseguire tutti i test.
- Il deploy si fa caricando **tutti** i file (`git add -A`). Un push parziale
  ha già rotto l'app una volta (ottobre 2026).

## Prossimi passi

1. Collegare `~/arranger_smim` al repository GitHub `arranger-smim`,
   clonandolo o con `git init` + `remote`, senza perdere la storia remota.
2. Verificare su Streamlit Cloud che la 0.9.5 parta e che la mail di feedback
   arrivi con gli allegati.
3. ~~Test dell'arrangiatore su repertorio reale~~: fatto per la 0.9.6
   (Cinema Paradiso, Dune, Can't Help Falling in Love, Let It Be).
4. ~~Avviso «[Mani]» sul lead sheet dell'Inno alla gioia~~: risolto nella
   0.9.6 (pianoforte col ruolo di basso che scriveva il basso anche nella
   destra, più altre tre cause).
5. Ricaricare i testi di riferimento (De La Motte, Piston, Rimskij-Korsakov),
   che risultavano corrotti, e portarne i principi nel motore: condotta delle
   parti, raddoppi, equilibrio timbrico.
6. Limiti noti, dal README:
   - i ritornelli (`<repeat>`) non vengono srotolati;
   - nessuna gestione esplicita delle modulazioni;
   - percussioni a pattern fissi per stile.
7. Ingresso da PDF tramite OMR (decisione del 22/10/2026). **Requisito:**
   deve funzionare nell'app online su Streamlit Cloud, senza che il docente
   scarichi o installi nulla; tutto ciò che serve si installa sul server al
   deploy. Motore scelto: Audiveris 5.11 (AGPL v3), con i dati OCR di
   Tesseract per le sigle. Prova locale: ottimo sui PDF puliti, debole
   sulle scansioni e sulle sigle jazz. Resta da fare la prova sul server
   Streamlit Cloud (memoria e tempi). Rimandato alla settimana dopo il
   26/10/2026.
8. Corno: le estensioni per livello sono una stima; da confermare.
