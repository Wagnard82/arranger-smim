"""
Testi dell'interfaccia Streamlit, in italiano e in inglese.

Stanno qui e non dentro app.py perche' cosi' app.py resta leggibile come
codice, e chi vuole ritoccare una frase la trova in un posto solo, con la
traduzione accanto.

Uso:  ui("chiave", lingua, valore=...)
"""

from __future__ import annotations

from typing import Dict

TESTI: Dict[str, Dict[str, str]] = {
    # ------------------------------------------------------------ intestazione
    "lingua": {"it": "🌐 Lingua / Language", "en": "🌐 Language / Lingua"},
    "titolo": {"it": "🎼 Arranger SMIM · v{versione}, {compilato}",
               "en": "🎼 Arranger SMIM · v{versione}, {compilato}"},
    "sottotitolo": {
        "it": "Da uno spartito per pianoforte a una partitura per orchestra "
              "scolastica, con controllo automatico dei limiti didattici.",
        "en": "From a piano score to a full score for school orchestra, with "
              "automatic checks on what students at each level can play.",
    },
    "file_in_esecuzione": {
        "it": "File in esecuzione: `{percorso}` — modificato il {data}",
        "en": "Running file: `{percorso}` — modified on {data}",
    },
    "formato_data": {"it": "%d/%m/%Y alle %H.%M", "en": "%Y-%m-%d at %H:%M"},
    "file_non_allineati": {
        "it": "**File non allineati.** Questa interfaccia (app.py) e' della "
              "versione {ui}, ma il motore (cartella `arranger/`) e' della "
              "{motore}. Succede quando si aggiorna solo una parte dei file. "
              "Carica sul repository **tutto** il contenuto dello zip — in "
              "particolare le cartelle `arranger/` ed `esempi/` e il file "
              "`requirements.txt` — e riavvia l'app.",
        "en": "**Files out of sync.** This interface (app.py) is version {ui}, "
              "but the engine (`arranger/` folder) is version {motore}. This "
              "happens when only some of the files are updated. Upload "
              "**the whole** content of the zip to the repository — in "
              "particular the `arranger/` and `esempi/` folders and the "
              "`requirements.txt` file — and restart the app.",
    },
    # ---------------------------------------------------------------- novita'
    "novita": {"it": "### 🆕 Novita' della {versione}",
               "en": "### 🆕 What's new in {versione}"},
    "rispetto_a": {"it": "rispetto alla {precedente} · {data}",
                   "en": "compared with {precedente} · {data}"},
    "segnala": {
        "it": "Hai trovato qualcosa che non torna? Usa il modulo di feedback "
              "in fondo alla pagina: indica il brano e la battuta.",
        "en": "Found something that doesn't look right? Use the feedback form "
              "at the bottom of the page: tell us the piece and the bar.",
    },
    # ---------------------------------------------------------- 1 formazione
    "formazione": {"it": "1 · Formazione", "en": "1 · Ensemble"},
    "aiuto_divisi": {"it": "Quantita' di divisi (es. Flauto 1, 2, 3)",
                     "en": "Number of parts (e.g. Flute 1, 2, 3)"},
    # -------------------------------------------------------------- 2 livello
    "livello": {"it": "2 · Livello didattico", "en": "2 · Level"},
    "classe": {"it": "Classe", "en": "Ensemble level"},
    "livelli_strumento": {"it": "Livelli diversi per strumento (classi eterogenee)",
                          "en": "Different levels per instrument (mixed-ability groups)"},
    "livelli_strumento_aiuto": {
        "it": "Lascia «come la classe» dove non serve distinguere. Le "
              "indicazioni date qui valgono per tutto: estensione, valori "
              "ritmici, alterazioni, respiro, e anche la scelta di chi porta "
              "la melodia — che va a chi puo' davvero eseguirla.",
        "en": "Leave “same as ensemble” where no distinction is needed. "
              "Settings made here apply to everything: range, note values, "
              "accidentals, breathing, and also the choice of who carries "
              "the melody — which goes to whoever can actually play it.",
    },
    "tutti_i": {"it": " (tutti i {n})", "en": " (all {n})"},
    "come_la_classe": {"it": "come la classe", "en": "same as ensemble"},
    "come_lo_strumento": {"it": "come lo strumento", "en": "same as instrument"},
    "livelli_attivi": {"it": "{n} indicazioni di livello specifiche attive.",
                       "en": "{n} specific level settings active."},
    # ---------------------------------------------------------------- 3 stile
    "stile": {"it": "3 · Stile", "en": "3 · Style"},
    "stile_arrangiamento": {"it": "Stile di arrangiamento", "en": "Arrangement style"},
    # ------------------------------------------------------------- avanzate
    "avanzate": {"it": "⚙️ Impostazioni avanzate", "en": "⚙️ Advanced settings"},
    "come_trattare": {"it": "Come trattare il brano", "en": "How to treat the piece"},
    "modo_auto": {"it": "Automatico", "en": "Automatic"},
    "modo_melodico": {"it": "Melodia + accompagnamento", "en": "Melody + accompaniment"},
    "modo_tessitura": {"it": "Orchestra i registri", "en": "Orchestrate by register"},
    "modo_aiuto": {
        "it": "'Melodia + accompagnamento' cerca il tema e lo affida a un "
              "solista. 'Orchestra i registri' non cerca nessuna melodia e "
              "divide il tessuto dell'originale fra gli strumenti per fasce "
              "di altezza: e' la scelta giusta per i brani puramente "
              "pianistici, dove un tema da cantare non c'e'.",
        "en": "'Melody + accompaniment' looks for the tune and gives it to a "
              "soloist. 'Orchestrate by register' looks for no melody and "
              "splits the original texture among the instruments by pitch "
              "band: the right choice for purely pianistic pieces, where "
              "there is no tune to sing.",
    },
    "stile_ia": {"it": "Lascia scegliere lo stile all'IA ('Automatico')",
                 "en": "Let the AI choose the style ('Automatic')"},
    "stile_ia_aiuto": {
        "it": "Sovrascrive lo stile scelto sopra: il modello propone stile e "
              "tipo di accompagnamento tenendo conto anche di cio' che si sa "
              "del brano originale. Richiede l'IA attiva piu' sotto.",
        "en": "Overrides the style chosen above: the model suggests style and "
              "accompaniment type, also taking into account what is known "
              "about the original song. Requires the AI to be enabled below.",
    },
    "chi_melodia": {"it": "**Chi porta la melodia**", "en": "**Who carries the melody**"},
    "solisti": {"it": "Strumenti solisti", "en": "Solo instruments"},
    "solisti_aiuto": {
        "it": "Se non selezioni nulla decide il motore. Selezionando piu' "
              "strumenti la melodia passa dall'uno all'altro, frase per frase.",
        "en": "If you select nothing, the engine decides. Selecting several "
              "instruments passes the melody from one to the next, phrase "
              "by phrase.",
    },
    "staffetta": {"it": "Fai passare la melodia fra i solisti",
                  "en": "Pass the melody between soloists"},
    "quando_cambiare": {"it": "Quando cambiare solista", "en": "When to change soloist"},
    "cambio_auto": {"it": "auto", "en": "auto"},
    "cambio_periodo": {"it": "periodo", "en": "period"},
    "cambio_sezione": {"it": "sezione", "en": "section"},
    "cambio_frase": {"it": "frase", "en": "phrase"},
    "cambio_aiuto": {
        "it": "Lo scambio avviene sempre a fine frase. 'periodo' aspetta la "
              "chiusura del periodo (antecedente + conseguente), 'sezione' "
              "cambia fra strofa e ritornello. Con 'auto' decide il software "
              "in base alla forma del brano, e nei ritornelli manda i solisti "
              "all'unisono.",
        "en": "The hand-off always happens at the end of a phrase. 'period' "
              "waits for the period to close (antecedent + consequent), "
              "'section' changes between verse and chorus. With 'auto' the "
              "software decides from the form of the piece, and sends the "
              "soloists in unison in the choruses.",
    },
    "frasi_avanzate": {"it": "Rilevatore di frasi avanzato (music21)",
                       "en": "Advanced phrase detector (music21)"},
    "frasi_avanzate_aiuto": {
        "it": "Usa music21 per leggere legature di portamento, corone, segni "
              "di respiro e articolazioni: i cambi di solista cadono dove la "
              "musica respira davvero, e mai dentro una legatura.",
        "en": "Uses music21 to read slurs, fermatas, breath marks and "
              "articulations: soloist changes fall where the music really "
              "breathes, and never inside a slur.",
    },
    "per_attivarlo": {"it": "Per attivarlo: pip install music21.",
                      "en": "To enable it: pip install music21."},
    "misure_minime": {"it": "Misure minime prima di passare la melodia",
                      "en": "Minimum bars before passing the melody"},
    "misure_minime_aiuto": {
        "it": "Anche se una frase finisce, il solista non cambia prima di "
              "tante misure: scambi troppo ravvicinati confondono e non danno "
              "il tempo di riconoscere il timbro.",
        "en": "Even if a phrase ends, the soloist does not change before this "
              "many bars: hand-offs that are too close confuse players and "
              "leave no time to recognise the timbre.",
    },
    "raddoppi": {"it": "Consenti raddoppi della melodia", "en": "Allow melody doublings"},
    "altre_opzioni": {"it": "**Altre opzioni**", "en": "**Other options**"},
    "trasporto": {"it": "Trasporto (semitoni)", "en": "Transposition (semitones)"},
    "riempi": {"it": "Nessuno strumento resta fermo a lungo",
               "en": "No instrument stays silent for long"},
    "riempi_aiuto": {
        "it": "Chi in un tratto non ha la melodia accompagna: una nota "
              "tenuta, un arpeggio, gli accordi. Restano i silenzi brevi, che "
              "sono respiro.",
        "en": "Whoever doesn't have the melody in a passage accompanies: a "
              "held note, an arpeggio, the chords. Short rests stay: they are "
              "breathing space.",
    },
    "pausa_max": {"it": "Pausa massima tollerata (misure)",
                  "en": "Longest rest allowed (bars)"},
    "genera_ly": {"it": "Genera anche il sorgente LilyPond (.ly)",
                  "en": "Also generate the LilyPond source (.ly)"},
    "confronto": {"it": "Modalita' confronto", "en": "Comparison mode"},
    "confronto_aiuto": {
        "it": "Accoda in fondo alla partitura lo spartito originale, non "
              "modificato: aprendo il file si legge l'arrangiamento sopra e "
              "l'originale sotto, battuta per battuta.",
        "en": "Appends the original, unmodified score at the bottom of the "
              "full score: opening the file you read the arrangement above "
              "and the original below, bar by bar.",
    },
    # ---------------------------------------------------------------- IA
    "ia": {"it": "**Intelligenza artificiale**", "en": "**Artificial intelligence**"},
    "ia_libreria": {
        "it": "Per usare l'IA serve il pacchetto `anthropic` (`pip install "
              "anthropic`). Senza, il motore lavora comunque con le sue regole.",
        "en": "The AI needs the `anthropic` package (`pip install anthropic`). "
              "Without it, the engine still works with its own rules.",
    },
    "ia_chiave": {"it": "Chiave API Anthropic", "en": "Anthropic API key"},
    "ia_chiave_aiuto": {"it": "Resta solo in questa sessione.",
                        "en": "Kept only for this session."},
    "ia_attiva": {"it": "Attiva l'IA", "en": "Enable AI"},
    "ia_incolla": {"it": "Incolla una chiave API per attivarla.",
                   "en": "Paste an API key to enable it."},
    "ia_modello": {"it": "Modello", "en": "Model"},
    "ia_chiamate": {
        "it": "{n} chiamate al modello per arrangiamento (la ricerca sul "
              "brano ne aggiunge qualcuna in piu').",
        "en": "{n} model calls per arrangement (the song research adds a few "
              "more).",
    },
    "ia_prova": {"it": "Prova la connessione", "en": "Test the connection"},
    # ----------------------------------------------------------- ingresso
    "spartito_partenza": {"it": "Spartito di partenza", "en": "Source score"},
    "spiega_ingresso": {
        "it": "**Carica un MusicXML** (`.xml`, `.musicxml`, `.mxl`), in una di "
              "queste tre forme — l'arrangiatore le riconosce da solo:\n\n"
              "- **riduzione per pianoforte** su due righi, con melodia, "
              "armonia e basso;\n"
              "- **parte solista + pianoforte** (voce, flauto, violino... con "
              "l'accompagnamento sotto);\n"
              "- **lead sheet**: la sola melodia su un rigo, con le **sigle** "
              "degli accordi sopra (come nei canzonieri). Basso e "
              "accompagnamento vengono costruiti dalle sigle.\n\n"
              "Partiture gia' orchestrate o parti staccate danno risultati "
              "scadenti.",
        "en": "**Upload a MusicXML file** (`.xml`, `.musicxml`, `.mxl`) in one "
              "of these three forms — the arranger recognises them on its "
              "own:\n\n"
              "- **piano reduction** on two staves, with melody, harmony and "
              "bass;\n"
              "- **solo part + piano** (voice, flute, violin... with the "
              "accompaniment below);\n"
              "- **lead sheet**: just the melody on one staff, with **chord "
              "symbols** above (as in fake books). Bass and accompaniment are "
              "built from the chord symbols.\n\n"
              "Scores that are already orchestrated, or separate parts, give "
              "poor results.",
    },
    "carica": {"it": "Spartito in MusicXML", "en": "Score in MusicXML"},
    "altri_formati": {"it": "Ho un MIDI, un PDF o un audio: come faccio?",
                      "en": "I have a MIDI, a PDF or an audio file: what do I do?"},
    "altri_formati_testo": {
        "it": "L'arrangiatore legge solo MusicXML: e' l'unico formato che "
              "porta con se' metro, tonalita', sigle, dinamiche e voci senza "
              "doverle indovinare. Gli altri formati vanno prima portati in "
              "notazione — e li' conviene controllarli, perche' ogni errore "
              "si propaga all'arrangiamento:\n\n"
              "- **MIDI**: aprilo in **MuseScore 4** o **Dorico**, sistema "
              "metro e valori, poi *Esporta > MusicXML*;\n"
              "- **PDF**: *File > Importa PDF* in **MuseScore 4**, oppure "
              "**Audiveris** (gratuito, il piu' accurato sulla musica "
              "stampata); ricontrolla alterazioni e legature;\n"
              "- **audio**: trascrivi la melodia e scrivi le sigle — il "
              "**lead sheet** e' il modo piu' rapido per arrangiare un brano "
              "che hai solo in registrazione.",
        "en": "The arranger reads only MusicXML: it is the only format that "
              "carries metre, key, chord symbols, dynamics and voices without "
              "having to guess them. Other formats must first be turned into "
              "notation — and that is the moment to check them, because every "
              "error carries over into the arrangement:\n\n"
              "- **MIDI**: open it in **MuseScore 4** or **Dorico**, fix metre "
              "and note values, then *Export > MusicXML*;\n"
              "- **PDF**: *File > Import PDF* in **MuseScore 4**, or "
              "**Audiveris** (free, the most accurate on printed music); "
              "double-check accidentals and ties;\n"
              "- **audio**: transcribe the melody and write the chord symbols "
              "— a **lead sheet** is the quickest way to arrange a song you "
              "only have as a recording.",
    },
    "esempio": {"it": "Oppure prova un esempio", "en": "Or try an example"},
    "esempio_nessuno": {"it": "nessuno", "en": "none"},
    "esempio_pf": {"it": "Inno alla gioia (pianoforte)", "en": "Ode to Joy (piano)"},
    "esempio_ls": {"it": "Inno alla gioia (lead sheet)", "en": "Ode to Joy (lead sheet)"},
    "esempio_aiuto": {
        "it": "Lo stesso brano in due forme: utile per vedere come cambia "
              "l'arrangiamento quando il basso e l'accompagnamento nascono "
              "dalle sigle invece che dalla parte di pianoforte.",
        "en": "The same piece in two forms: useful to see how the arrangement "
              "changes when bass and accompaniment come from the chord "
              "symbols instead of the piano part.",
    },
    "genera": {"it": "🎻 Genera arrangiamento", "en": "🎻 Generate arrangement"},
    "err_formazione": {"it": "Seleziona almeno uno strumento nella formazione.",
                       "en": "Select at least one instrument in the ensemble."},
    "err_sorgente": {"it": "Carica un MusicXML oppure scegli uno degli esempi.",
                     "en": "Upload a MusicXML file or choose one of the examples."},
    "in_corso": {"it": "Analisi e arrangiamento in corso...",
                 "en": "Analysing and arranging..."},
    "err_elabora": {"it": "Non sono riuscito a elaborare il file: {errore}",
                    "en": "Could not process the file: {errore}"},
    "dettagli": {"it": "Dettagli tecnici", "en": "Technical details"},
    "errore_segnala": {
        "it": "Puoi inviarmi il file con il modulo di feedback in fondo alla "
              "pagina: è già pronto da allegare, insieme alle impostazioni e "
              "all'errore.",
        "en": "You can send me the file with the feedback form at the bottom "
              "of the page: it is already set to be attached, together with "
              "the settings and the error.",
    },
    # ------------------------------------------------------------ risultati
    "completato": {
        "it": "Arrangiamento di **{titolo}** completato: {parti} parti, {misure} misure.",
        "en": "Arrangement of **{titolo}** done: {parti} parts, {misure} bars.",
    },
    "tab_anteprima": {"it": "👀 Anteprima", "en": "👀 Preview"},
    "tab_download": {"it": "📥 Download", "en": "📥 Download"},
    "tab_analisi": {"it": "🔍 Analisi dello spartito", "en": "🔍 Score analysis"},
    "tab_parti": {"it": "🎻 Parti generate", "en": "🎻 Generated parts"},
    "tab_report": {"it": "✅ Report dei filtri", "en": "✅ Validation report"},
    "misure_mostrare": {"it": "Misure da mostrare", "en": "Bars to show"},
    "misure_mostrare_aiuto": {
        "it": "Disegnare tutto il brano nel browser e' lento: per farsi "
              "un'idea bastano le prime pagine.",
        "en": "Drawing the whole piece in the browser is slow: the first "
              "pages are enough to get an idea.",
    },
    "zoom": {"it": "Ingrandimento", "en": "Zoom"},
    "lettore_midi": {"it": "Includi il lettore MIDI", "en": "Include the MIDI player"},
    "lettore_midi_aiuto": {"it": "Ascolto approssimativo, utile per l'insieme.",
                           "en": "Rough playback, useful for the overall picture."},
    "anteprima_indicativa": {
        "it": "L'anteprima e' indicativa: per l'impaginazione definitiva apri "
              "il MusicXML in MuseScore, Dorico o Sibelius.",
        "en": "The preview is approximate: for final layout open the MusicXML "
              "in MuseScore, Dorico or Sibelius.",
    },
    "anteprima_non_disp": {
        "it": "Anteprima non disponibile: {errore}. Il file resta scaricabile "
              "dalla scheda Download.",
        "en": "Preview not available: {errore}. The file can still be "
              "downloaded from the Download tab.",
    },
    "non_vedi": {"it": "Non vedi niente qui sopra?", "en": "Can't see anything above?"},
    "non_vedi_testo": {
        "it": "L'anteprima e' disegnata nel browser da due librerie caricate "
              "da internet: **non serve installare nulla**, ma serve la "
              "connessione.\n\n"
              "- Se lavori offline, o la rete blocca `cdn.jsdelivr.net` e "
              "`unpkg.com`, il riquadro resta vuoto. Il MusicXML nella scheda "
              "**Download** e' comunque completo.\n"
              "- Se hai un blocco pubblicita' attivo, provalo a disattivare su "
              "questa pagina.\n"
              "- Su partiture lunghe abbassa il numero di misure.",
        "en": "The preview is drawn in the browser by two libraries loaded "
              "from the internet: **nothing needs installing**, but a "
              "connection is needed.\n\n"
              "- If you are offline, or the network blocks `cdn.jsdelivr.net` "
              "and `unpkg.com`, the box stays empty. The MusicXML in the "
              "**Download** tab is complete anyway.\n"
              "- If you have an ad blocker on, try disabling it for this page.\n"
              "- On long scores, lower the number of bars.",
    },
    "scarica_xml": {"it": "Scarica la partitura MusicXML", "en": "Download the MusicXML score"},
    "scarica_midi": {"it": "Scarica il MIDI di anteprima", "en": "Download the preview MIDI"},
    "scarica_ly": {"it": "Scarica il sorgente LilyPond (.ly)",
                   "en": "Download the LilyPond source (.ly)"},
    "download_nota": {
        "it": "Il MusicXML si apre in MuseScore, Dorico, Sibelius e Finale: "
              "nomi degli strumenti, graffa del pianoforte, armature "
              "trasposte, dinamiche e articolazioni sono gia' impostate.",
        "en": "The MusicXML opens in MuseScore, Dorico, Sibelius and Finale: "
              "instrument names, piano brace, transposed key signatures, "
              "dynamics and articulations are already set.",
    },
    "anacrusi": {"it": "Anacrusi", "en": "Pickup"},
    "quarti": {"it": "{n:g} quarti", "en": "{n:g} beats"},
    "assente": {"it": "assente", "en": "none"},
    "note_lette": {"it": "Note lette", "en": "Notes read"},
    "accordi_dedotti": {"it": "Accordi dedotti", "en": "Chords found"},
    "forma": {"it": "Forma", "en": "Form"},
    "frasi_periodi": {"it": "Frasi / periodi", "en": "Phrases / periods"},
    "ritornelli": {"it": "Ritornelli", "en": "Choruses"},
    "sezioni": {"it": "**Sezioni riconosciute**", "en": "**Sections found**"},
    "melodia_rilevata": {"it": "**Melodia rilevata**", "en": "**Melody found**"},
    "griglia": {"it": "**Griglia armonica**", "en": "**Chord chart**"},
    "parte_riga": {"it": "{nome} — ruolo: {ruolo} — {n} eventi",
                   "en": "{nome} — role: {ruolo} — {n} events"},
    "parte_in_pausa": {"it": "Parte in pausa.", "en": "Part is silent."},
    "ambito": {"it": "Ambito impiegato: {da} – {a}", "en": "Range used: {da} – {a}"},
    "trasposizione": {"it": " · trasposizione: {n:+d} semitoni",
                      "en": " · transposition: {n:+d} semitones"},
    "info_brano": {"it": "Informazioni sul brano originale (ricerca IA)",
                   "en": "Information on the original song (AI research)"},
    "relazione": {"it": "**Relazione per il docente**", "en": "**Report for the teacher**"},
    "interventi": {"it": "{n} interventi automatici del validatore:",
                   "en": "{n} automatic changes by the validator:"},
    "e_altri": {"it": "...e altri {n}.", "en": "...and {n} more."},
    "nessun_intervento": {
        "it": "Nessun intervento necessario: tutte le parti rispettano i "
              "vincoli del livello selezionato.",
        "en": "No changes needed: every part fits the limits of the selected "
              "level.",
    },
    # -------------------------------------------------------------- feedback
    "feedback_titolo": {"it": "💬 Dimmi come è andata", "en": "💬 Tell me how it went"},
    "feedback_spiega": {
        "it": "Il progetto è in prova: ogni segnalazione aiuta a migliorarlo. "
              "Se hai trovato un errore, indica il brano e la battuta.",
        "en": "The project is in testing: every report helps improve it. If "
              "you found an error, tell us the piece and the bar.",
    },
    "nome_facoltativo": {"it": "Nome (facoltativo)", "en": "Name (optional)"},
    "tua_email": {"it": "La tua email (se vuoi una risposta)",
                  "en": "Your email (if you'd like a reply)"},
    "tipo_segnalazione": {"it": "Tipo di segnalazione", "en": "Type of report"},
    "cat_musicale": {"it": "Errore musicale", "en": "Musical error"},
    "cat_tecnico": {"it": "Errore tecnico", "en": "Technical error"},
    "cat_suggerimento": {"it": "Suggerimento", "en": "Suggestion"},
    "cat_altro": {"it": "Altro", "en": "Other"},
    "messaggio": {"it": "Messaggio", "en": "Message"},
    "messaggio_es": {"it": "Es.: nella battuta 12 il clarinetto...",
                     "en": "E.g.: in bar 12 the clarinet..."},
    "invia": {"it": "Invia", "en": "Send"},
    "allega_ultimo": {
        "it": "Allega il brano dell'ultimo arrangiamento ({file}) e le impostazioni usate",
        "en": "Attach the piece from the last arrangement ({file}) and the settings used",
    },
    "allega_ultimo_aiuto": {
        "it": "Insieme al file arrivano organico, livelli, stile e opzioni, "
              "la partitura generata e il report: servono per rifare "
              "esattamente lo stesso arrangiamento e vedere il problema.",
        "en": "Along with the file come the ensemble, levels, style and "
              "options, the generated score and the report: they are needed "
              "to reproduce exactly the same arrangement and see the problem.",
    },
    "allega_con_errore": {
        "it": "L'ultimo arrangiamento non e' riuscito: verra' allegato anche "
              "il dettaglio dell'errore.",
        "en": "The last arrangement failed: the error details will be "
              "attached too.",
    },
    "allega_altri": {"it": "Altri file da allegare (facoltativo)",
                     "en": "Other files to attach (optional)"},
    "allega_altri_aiuto": {
        "it": "Uno spartito diverso, un PDF con la battuta cerchiata, uno "
              "screenshot. MusicXML, MIDI, PDF, immagini o zip.",
        "en": "A different score, a PDF with the bar circled, a screenshot. "
              "MusicXML, MIDI, PDF, images or zip.",
    },
    "allega_privacy": {
        "it": "I file allegati arrivano solo all'autore e servono "
              "esclusivamente per le prove sull'arrangiatore.",
        "en": "Attached files go only to the author and are used solely to "
              "test the arranger.",
    },
    "grazie_allegati": {"it": "Grazie! Il messaggio è stato inviato con {n} allegati.",
                        "en": "Thank you! Your message has been sent with {n} attachments."},
    "allegati_troppo_grandi": {
        "it": "Questi file erano troppo grandi per la mail e non sono stati "
              "allegati: {elenco}.",
        "en": "These files were too large for email and were not attached: "
              "{elenco}.",
    },
    "allega_a_mano": {
        "it": "Il programma di posta non riceve gli allegati dal link: scarica "
              "lo zip qui sotto e aggiungilo a mano alla mail.",
        "en": "Your email program can't receive attachments from the link: "
              "download the zip below and attach it to the email yourself.",
    },
    "scarica_allegati": {"it": "Scarica gli allegati (.zip)",
                         "en": "Download the attachments (.zip)"},
    "scrivi_qualcosa": {"it": "Scrivi qualcosa nel messaggio prima di inviare.",
                        "en": "Write something in the message before sending."},
    "grazie": {"it": "Grazie! Il messaggio è stato inviato.",
               "en": "Thank you! Your message has been sent."},
    "invio_non_disp": {"it": "L'invio automatico non è disponibile in questo momento.",
                       "en": "Automatic sending is not available right now."},
    "apri_posta": {"it": "Apri il messaggio nel tuo programma di posta",
                   "en": "Open the message in your email program"},
    "anonimo": {"it": "anonimo", "en": "anonymous"},
}


def ui(chiave: str, lingua: str = "it", **valori) -> str:
    voce = TESTI[chiave]
    testo = voce.get(lingua) or voce["it"]
    return testo.format(**valori) if valori else testo
