"""
Arranger SMIM - interfaccia Streamlit (versione pubblica).

    streamlit run app.py

Ingresso: SOLO spartiti per PIANOFORTE in MusicXML (.xml/.musicxml/.mxl) o MIDI.
Include un modulo di feedback che invia una mail all'autore.
"""

from __future__ import annotations

import os
import smtplib
from datetime import datetime
import tempfile
import traceback
from email.message import EmailMessage
from urllib.parse import quote

import streamlit as st
import streamlit.components.v1 as components

from arranger import Configurazione, esegui
from arranger import ia
from arranger.anteprima import html_anteprima
from arranger.modello import nome_it
from arranger.orchestratore import costruisci_parti
from arranger.ingestione import stato_dipendenze_omr
from arranger.strumenti import LIVELLI, ORDINE_PARTITURA, REGISTRO, livello, strumento
from arranger.versione import COMPILATO, DATA, NOVITA, PRECEDENTE, VERSIONE

DESTINATARIO = "claudiobianchi82@gmail.com"

st.set_page_config(page_title="Arranger SMIM", page_icon="🎼", layout="wide")

CARTELLA = os.path.join(tempfile.gettempdir(), "arranger_smim")
os.makedirs(CARTELLA, exist_ok=True)

st.title(f"🎼 Arranger SMIM · v{VERSIONE}, {COMPILATO}")
st.caption("Da uno spartito per pianoforte a una partitura per orchestra "
           "scolastica, con controllo automatico dei limiti didattici.")

# Diagnostica: quale file sta girando davvero e quando e' stato modificato.
# Con piu' copie del progetto sul disco e' l'unico modo per esserne certi.
_percorso_app = os.path.abspath(__file__)
_modificato = datetime.fromtimestamp(os.path.getmtime(_percorso_app))
st.caption(f"File in esecuzione: `{_percorso_app}` — modificato il "
           f"{_modificato:%d/%m/%Y alle %H.%M}")

PRINCIPALE, REGISTRO_MODIFICHE = st.columns([3, 1], gap="large")

with REGISTRO_MODIFICHE:
    st.markdown(f"### 🆕 Novita' della {VERSIONE}")
    st.caption(f"rispetto alla {PRECEDENTE} · {DATA}")
    for titolo, voci in NOVITA:
        with st.expander(titolo, expanded=False):
            for voce in voci:
                st.markdown(f"- {voce}")
    st.caption("Hai trovato qualcosa che non torna? Usa il modulo di feedback "
               "in fondo alla pagina: indica il brano e la battuta.")


# ==========================================================================
# Feedback
# ==========================================================================


def invia_feedback(nome: str, email: str, categoria: str, messaggio: str) -> bool:
    """
    Invia il feedback via SMTP usando le credenziali in st.secrets.
    Ritorna False se le credenziali mancano o l'invio fallisce: in quel caso
    l'interfaccia offre il ripiego con un link mailto.
    """
    try:
        cfg = st.secrets["email"]
    except Exception:
        return False
    try:
        msg = EmailMessage()
        msg["Subject"] = f"[Arranger SMIM] {categoria} - da {nome or 'anonimo'}"
        msg["From"] = cfg["mittente"]
        msg["To"] = cfg.get("destinatario", DESTINATARIO)
        if email:
            msg["Reply-To"] = email
        msg.set_content(
            f"Nome: {nome or '-'}\nEmail: {email or '-'}\n"
            f"Categoria: {categoria}\n\n{messaggio}")
        with smtplib.SMTP_SSL(cfg.get("server", "smtp.gmail.com"),
                              int(cfg.get("porta", 465))) as server:
            server.login(cfg["mittente"], cfg["password"])
            server.send_message(msg)
        return True
    except Exception:
        return False


def link_mailto(nome: str, email: str, categoria: str, messaggio: str) -> str:
    corpo = quote(f"Nome: {nome}\nEmail: {email}\n\n{messaggio}")
    oggetto = quote(f"[Arranger SMIM] {categoria}")
    return f"mailto:{DESTINATARIO}?subject={oggetto}&body={corpo}"


# ==========================================================================
# MODULO 2 - Configurazione
# ==========================================================================

with st.sidebar:
    st.header("1 · Formazione")
    formazione = {}
    for chiave in ORDINE_PARTITURA:
        st.session_state.setdefault(f"q_{chiave}", 0)
        formazione[chiave] = st.number_input(
            REGISTRO[chiave].nome, min_value=0, max_value=6,
            value=st.session_state[f"q_{chiave}"], key=f"q_{chiave}",
            help="Quantita' di divisi (es. Flauto 1, 2, 3)")

    st.header("2 · Livello didattico")
    liv = st.radio("Classe", list(LIVELLI.keys()), index=0, label_visibility="collapsed")
    st.info(livello(liv).note)

    st.header("3 · Stile")
    stile = st.selectbox(
        "Stile di arrangiamento", ["Normale", "Cinematico", "Jazz"])

    # ----------------------------------------------------------------
    # Impostazioni avanzate: tutto cio' che non serve al primo utilizzo
    # resta chiuso qui dentro, con valori predefiniti sensati.
    # ----------------------------------------------------------------
    with st.expander("⚙️ Impostazioni avanzate"):
        st.markdown("**Come trattare il brano**")
        modo = st.radio(
            "Come trattare il brano", ["auto", "melodico", "tessitura"],
            horizontal=True, label_visibility="collapsed",
            format_func=lambda x: {"auto": "Automatico",
                                   "melodico": "Melodia + accompagnamento",
                                   "tessitura": "Orchestra i registri"}[x],
            help=("'Melodia + accompagnamento' cerca il tema e lo affida a "
                  "un solista. 'Orchestra i registri' non cerca nessuna "
                  "melodia e divide il tessuto dell'originale fra gli "
                  "strumenti per fasce di altezza: e' la scelta giusta per "
                  "i brani puramente pianistici, dove un tema da cantare "
                  "non c'e'."))
        stile_automatico = st.checkbox(
            "Lascia scegliere lo stile all'IA ('Automatico')", value=False,
            help=("Sovrascrive lo stile scelto sopra: il modello propone "
                  "stile e tipo di accompagnamento tenendo conto anche di "
                  "cio' che si sa del brano originale. Richiede l'IA "
                  "attiva piu' sotto."))
        if stile_automatico:
            stile = "Automatico"

        st.markdown("**Chi porta la melodia**")
        attive = {k: v for k, v in formazione.items() if v > 0}
        parti_possibili = [
            p for p in costruisci_parti(Configurazione(formazione=attive))
            if not strumento(p.strumento).percussione]
        etichette = {p.id: p.nome for p in parti_possibili}
        scelte_melodia = st.multiselect(
            "Strumenti solisti", options=list(etichette.keys()),
            format_func=lambda i: etichette.get(i, i),
            help=("Se non selezioni nulla decide il motore. Selezionando "
                  "piu' strumenti la melodia passa dall'uno all'altro, "
                  "frase per frase."))
        staffetta = st.checkbox("Fai passare la melodia fra i solisti",
                                value=True)
        cambio = st.selectbox(
            "Quando cambiare solista",
            ["auto", "periodo", "sezione", "frase"], disabled=not staffetta,
            help=("Lo scambio avviene sempre a fine frase. 'periodo' "
                  "aspetta la chiusura del periodo (antecedente + "
                  "conseguente), 'sezione' cambia fra strofa e ritornello. "
                  "Con 'auto' decide il software in base alla forma del "
                  "brano, e nei ritornelli manda i solisti all'unisono."))
        from arranger import frasi_music21 as _fm21
        frasi_avanzate = st.checkbox(
            "Rilevatore di frasi avanzato (music21)", value=False,
            disabled=not _fm21.disponibile(),
            help=("Usa music21 per leggere legature di portamento, corone, "
                  "segni di respiro e articolazioni: i cambi di solista "
                  "cadono dove la musica respira davvero, e mai dentro una "
                  "legatura."))
        if not _fm21.disponibile():
            st.caption("Per attivarlo: pip install music21.")
        minimo_solista = st.slider(
            "Misure minime prima di passare la melodia", 2, 24, 8,
            disabled=not staffetta,
            help=("Anche se una frase finisce, il solista non cambia prima "
                  "di tante misure: scambi troppo ravvicinati confondono e "
                  "non danno il tempo di riconoscere il timbro."))
        raddoppi = st.checkbox("Consenti raddoppi della melodia", value=True)

        st.markdown("**Altre opzioni**")
        trasporto = st.slider("Trasporto (semitoni)", -12, 12, 0)
        riempi = st.checkbox(
            "Nessuno strumento resta fermo a lungo", value=True,
            help=("Chi in un tratto non ha la melodia accompagna: una nota "
                  "tenuta, un arpeggio, gli accordi. Restano i silenzi "
                  "brevi, che sono respiro."))
        silenzio_max = st.slider("Pausa massima tollerata (misure)", 1, 8, 2,
                                 disabled=not riempi)
        genera_ly = st.checkbox("Genera anche il sorgente LilyPond (.ly)",
                                value=False)
        debug = st.checkbox(
            "Modalita' confronto", value=False,
            help=("Accoda in fondo alla partitura lo spartito originale, "
                  "non modificato: aprendo il file si legge l'arrangiamento "
                  "sopra e l'originale sotto, battuta per battuta."))

        st.markdown("**Intelligenza artificiale**")
        # la chiave puo' arrivare dai segreti dell'istanza o essere
        # incollata qui
        try:
            ia.configura_chiave(st.secrets["anthropic"]["api_key"])
            chiave_da_segreti = True
        except Exception:
            chiave_da_segreti = False

        stato_ia = ia.stato()
        if not stato_ia["libreria"]:
            st.caption("Per usare l'IA serve il pacchetto `anthropic` "
                       "(`pip install anthropic`). Senza, il motore lavora "
                       "comunque con le sue regole.")
            usa_ia = False
            funzioni_ia = set()
            modello_ia = ia.MODELLO_DEFAULT
        else:
            if not chiave_da_segreti:
                chiave = st.text_input("Chiave API Anthropic",
                                       type="password",
                                       help="Resta solo in questa sessione.")
                if chiave:
                    ia.configura_chiave(chiave)
                stato_ia = ia.stato()

            usa_ia = st.checkbox("Attiva l'IA", value=False,
                                 disabled=not stato_ia["chiave"])
            if not stato_ia["chiave"]:
                st.caption("Incolla una chiave API per attivarla.")

            modello_etichetta = st.selectbox("Modello", list(ia.MODELLI),
                                             disabled=not usa_ia)
            modello_ia = ia.MODELLI[modello_etichetta]

            predefinite = {"melodia", "stile"}
            funzioni_ia = set()
            for chiave_f, (titolo_f, spiega) in ia.FUNZIONI.items():
                if st.checkbox(titolo_f, value=(chiave_f in predefinite),
                               key=f"ia_{chiave_f}", disabled=not usa_ia,
                               help=spiega):
                    funzioni_ia.add(chiave_f)
            if usa_ia:
                st.caption(f"{len(funzioni_ia)} chiamate al modello per "
                           "arrangiamento (la ricerca sul brano ne "
                           "aggiunge qualcuna in piu').")
                if st.button("Prova la connessione"):
                    ok, messaggio = ia.prova_connessione(modello_ia)
                    (st.success if ok else st.error)(messaggio)



# ==========================================================================
# MODULO 1 - Ingestione (solo spartiti pianistici)
# ==========================================================================

with PRINCIPALE:
    st.subheader("Spartito di partenza")
    st.info(
        "**Carica uno spartito per PIANOFORTE**: MusicXML (`.xml`, `.musicxml`, "
        "`.mxl`) oppure MIDI (`.mid`). Il file deve contenere una riduzione "
        "pianistica su due righi, chiave di violino e di basso, con melodia, "
        "armonia e basso gia' scritti per pianoforte. Partiture gia' orchestrate, "
        "parti staccate o file su un rigo solo danno risultati scadenti.")

    _omr = stato_dipendenze_omr()
    _tipi = ["xml", "musicxml", "mxl", "mid", "midi"]
    if any(_omr.values()):
        _tipi.append("pdf")

    col1, col2 = st.columns([2, 1])
    with col1:
        caricato = st.file_uploader(
            "Spartito pianistico (MusicXML o MIDI)"
            + (" o PDF" if any(_omr.values()) else ""), type=_tipi)
        if not any(_omr.values()):
            with st.expander("Ho solo un PDF: come faccio?"):
                st.markdown(
                    "Il riconoscimento ottico non e' attivo su questa istanza "
                    "(richiede troppa memoria). Converti il PDF in MusicXML con "
                    "uno di questi, poi carica il file ottenuto:\n\n"
                    "- **MuseScore 4** (gratuito): *File > Importa PDF*;\n"
                    "- **Audiveris** (gratuito, open source): il piu' accurato "
                    "sulla musica stampata;\n"
                    "- **PlayScore 2** o **Soundslice**: servizi online.\n\n"
                    "Ricontrolla sempre il MusicXML prodotto: il riconoscimento "
                    "ottico sbaglia spesso alterazioni, voci e legature, e gli "
                    "errori si propagano all'arrangiamento.")
    with col2:
        demo = st.checkbox("Prova con il brano dimostrativo",
                           help="Inno alla Gioia, con anacrusi")

    # ---------------------------------------------------------- audio multitraccia
    # Visibile solo se le dipendenze pesanti (demucs, basic-pitch) sono
    # installate: sull'istanza pubblica restano assenti e questa sezione non
    # compare, coerentemente con la scelta di non esporre l'ingresso audio
    # li' (la trascrizione resta la parte meno affidabile della catena).
    from arranger import audio_multitraccia as am
    _stato_audio = am.stato_dipendenze()
    caricato_audio = None
    usa_audio = False
    bpm_manuale = None
    if _stato_audio["demucs"] and _stato_audio["basic_pitch"]:
        with st.expander("🎤 Oppure importa da una registrazione audio"):
            st.caption(
                "Separa voce, basso, batteria e resto (Demucs), trascrive "
                "ogni traccia e usa la voce come melodia, il basso come "
                "sostegno grave e base per l'armonia, la batteria come "
                "pattern ritmico reale. Ci vogliono alcuni minuti su CPU.")
            caricato_audio = st.file_uploader(
                "Registrazione audio (mp3, wav, m4a...)",
                type=["mp3", "wav", "m4a", "flac", "ogg"])
            usa_audio = caricato_audio is not None
            if not _stato_audio["librosa"]:
                st.caption("`librosa` non installato: la batteria non verra' "
                           "trascritta, le percussioni useranno comunque un "
                           "pattern automatico. Anche il tempo del brano "
                           "non potra' essere rilevato: indicalo qui sotto.")
            if _stato_audio["librosa"] and not _stato_audio.get("beat_this"):
                st.caption(
                    "Il tempo verra' stimato con `librosa`. Installando "
                    "`beat_this` la stima diventa piu' affidabile sui brani "
                    "dal ritmo sincopato, dove librosa tende ad agganciarsi "
                    "a una suddivisione sbagliata — e un tempo sbagliato "
                    "sposta tutta la quantizzazione. Si appoggia a PyTorch, "
                    "che Demucs ha gia' installato.")
            bpm_auto = st.checkbox(
                "Rileva il tempo (bpm) automaticamente", value=True,
                disabled=not _stato_audio["librosa"],
                help=("Nessun rilevatore automatico e' infallibile. Con "
                      "`beat_this` installato la stima e' piu' solida; con "
                      "il solo librosa l'errore piu' comune e' agganciarsi a "
                      "una suddivisione sbagliata del battito, specie sui "
                      "ritmi sincopati o sulle registrazioni datate. Se "
                      "conosci il tempo del brano, disattiva e indicalo: "
                      "resta sempre la scelta piu' sicura."))
            bpm_manuale = None
            if not bpm_auto or not _stato_audio["librosa"]:
                bpm_manuale = st.number_input(
                    "Tempo del brano (bpm)", min_value=20.0, max_value=300.0,
                    value=100.0, step=1.0,
                    help="Se non lo conosci con precisione, un valore "
                         "approssimativo va gia' meglio di un rilevamento "
                         "automatico sbagliato di un'ottava.")

    avvia = st.button("🎻 Genera arrangiamento", type="primary", use_container_width=True)

    # ==========================================================================
    # Esecuzione
    # ==========================================================================

    if avvia:
        if not any(formazione.values()):
            st.error("Seleziona almeno uno strumento nella formazione.")
            st.stop()

        if usa_audio:
            sorgente = os.path.join(CARTELLA, caricato_audio.name)
            with open(sorgente, "wb") as f:
                f.write(caricato_audio.getbuffer())
        elif demo:
            from esempi import genera_esempi
            sorgente = genera_esempi.inno_alla_gioia(
                os.path.join(CARTELLA, "inno_alla_gioia.xml"))
        elif caricato is not None:
            sorgente = os.path.join(CARTELLA, caricato.name)
            with open(sorgente, "wb") as f:
                f.write(caricato.getbuffer())
        else:
            st.error("Carica un file oppure spunta il brano dimostrativo.")
            st.stop()

        cfg = Configurazione(formazione={k: v for k, v in formazione.items() if v > 0},
                             livello=liv, stile=stile, trasporto=trasporto,
                             strumenti_melodia=scelte_melodia,
                             staffetta_melodia=staffetta, raddoppi_melodia=raddoppi,
                             modo=modo, cambio_solista=cambio,
                             frasi_music21=frasi_avanzate,
                             riempi_silenzi=riempi,
                             silenzio_massimo_misure=silenzio_max,
                             misure_minime_solista=minimo_solista,
                             debug_originale=debug, usa_ia=usa_ia,
                             modello_ia=modello_ia)
        for funzione in ia.FUNZIONI:
            setattr(cfg, f"ia_{funzione}", funzione in funzioni_ia)

        with st.spinner("Separazione delle tracce e arrangiamento in corso "
                        "(qualche minuto)..." if usa_audio else
                        "Analisi e arrangiamento in corso..."):
            try:
                from arranger.pipeline import esegui_da_audio_multitraccia
                if usa_audio:
                    st.session_state["risultato"] = esegui_da_audio_multitraccia(
                        sorgente, cfg, cartella=CARTELLA, esporta_ly=genera_ly,
                        bpm_manuale=bpm_manuale)
                else:
                    st.session_state["risultato"] = esegui(
                        sorgente, cfg, cartella=CARTELLA, esporta_ly=genera_ly)
            except Exception as e:
                st.error(f"Non sono riuscito a elaborare il file: {e}")
                with st.expander("Dettagli tecnici"):
                    st.code(traceback.format_exc())
                st.stop()

    # ==========================================================================
    # Risultati
    # ==========================================================================

    r = st.session_state.get("risultato")
    if r:
        st.success(f"Arrangiamento di **{r.master.titolo}** completato: "
                   f"{len(r.partitura.parti)} parti, {len(r.partitura.misure)} misure.")

        t0, t1, t2, t3, t4 = st.tabs(
            ["👀 Anteprima", "📥 Download", "🔍 Analisi dello spartito",
             "🎻 Parti generate", "✅ Report dei filtri"])

        with t0:
            c1, c2 = st.columns([1, 1])
            quante = c1.slider(
                "Misure da mostrare", 4, max(8, len(r.partitura.misure)),
                min(16, len(r.partitura.misure)),
                help=("Disegnare tutto il brano nel browser e' lento: per "
                      "farsi un'idea bastano le prime pagine."))
            zoom = c2.slider("Ingrandimento", 0.4, 1.2, 0.7, 0.05)
            con_audio = st.checkbox(
                "Includi il lettore MIDI", value=True,
                help="Ascolto approssimativo, utile per l'insieme.")
            try:
                with open(r.percorso_xml, encoding="utf-8") as f:
                    xml_partitura = f.read()
                dati_midi = None
                if con_audio and r.percorso_midi and os.path.exists(r.percorso_midi):
                    with open(r.percorso_midi, "rb") as f:
                        dati_midi = f.read()
                components.html(
                    html_anteprima(xml_partitura, midi=dati_midi, zoom=zoom,
                                   misure=int(quante)),
                    height=820, scrolling=True)
                st.caption("L'anteprima e' indicativa: per l'impaginazione "
                           "definitiva apri il MusicXML in MuseScore, Dorico "
                           "o Sibelius.")
            except Exception as errore:
                st.warning(f"Anteprima non disponibile: {errore}. "
                           "Il file resta scaricabile dalla scheda Download.")
            with st.expander("Non vedi niente qui sopra?"):
                st.markdown(
                    "L'anteprima e' disegnata nel browser da due librerie "
                    "caricate da internet: **non serve installare nulla**, "
                    "ma serve la connessione.\n\n"
                    "- Se lavori offline, o la rete blocca "
                    "`cdn.jsdelivr.net` e `unpkg.com`, il riquadro resta "
                    "vuoto. Il MusicXML nella scheda **Download** e' "
                    "comunque completo.\n"
                    "- Se hai un blocco pubblicita' attivo, provalo a "
                    "disattivare su questa pagina.\n"
                    "- Su partiture lunghe abbassa il numero di misure.")

        with t1:
            with open(r.percorso_xml, "rb") as f:
                st.download_button("Scarica la partitura MusicXML", f.read(),
                                   file_name=os.path.basename(r.percorso_xml),
                                   mime="application/vnd.recordare.musicxml+xml",
                                   use_container_width=True)
            if r.percorso_midi and os.path.exists(r.percorso_midi):
                with open(r.percorso_midi, "rb") as f:
                    st.download_button("Scarica il MIDI di anteprima", f.read(),
                                       file_name=os.path.basename(r.percorso_midi),
                                       mime="audio/midi", use_container_width=True)
            if r.percorso_ly and os.path.exists(r.percorso_ly):
                with open(r.percorso_ly, "rb") as f:
                    st.download_button("Scarica il sorgente LilyPond (.ly)", f.read(),
                                       file_name=os.path.basename(r.percorso_ly),
                                       mime="text/plain", use_container_width=True)
            if r.percorso_tracce_debug and os.path.exists(r.percorso_tracce_debug):
                st.divider()
                st.markdown("**Tracce separate (debug)**")
                st.caption(
                    "Voce, basso, batteria e resto separate dall'audio, "
                    "prima che l'arrangiatore le tocchi: apri questi file "
                    "per valutare la qualita' della separazione e della "
                    "trascrizione indipendentemente dall'arrangiamento "
                    "finale.")
                c1, c2 = st.columns(2)
                with open(r.percorso_tracce_debug, "rb") as f:
                    c1.download_button(
                        "Quantizzate", f.read(),
                        file_name=os.path.basename(r.percorso_tracce_debug),
                        mime="application/vnd.recordare.musicxml+xml",
                        use_container_width=True,
                        help="Attacchi agganciati alla griglia: quello che "
                             "usa l'arrangiatore.")
                if r.percorso_tracce_grezze and os.path.exists(r.percorso_tracce_grezze):
                    with open(r.percorso_tracce_grezze, "rb") as f:
                        c2.download_button(
                            "Non quantizzate", f.read(),
                            file_name=os.path.basename(r.percorso_tracce_grezze),
                            mime="application/vnd.recordare.musicxml+xml",
                            use_container_width=True,
                            help="Attacchi esattamente dove li ha sentiti la "
                                 "trascrizione, senza aggancio alla griglia: "
                                 "se un errore c'e' gia' qui, non e' colpa "
                                 "della quantizzazione.")
                st.caption(
                    "Confrontale: una nota sbagliata gia' nella versione "
                    "non quantizzata viene dalla separazione o dalla "
                    "trascrizione; se compare solo in quella quantizzata, "
                    "e' l'aggancio alla griglia ad averla spostata o fusa.")
            st.caption("Il MusicXML si apre in MuseScore, Dorico, Sibelius e Finale: "
                       "nomi degli strumenti, graffa del pianoforte, armature "
                       "trasposte, dinamiche e articolazioni sono gia' impostate.")

        with t2:
            c1, c2, c3 = st.columns(3)
            c1.metric("Anacrusi", f"{r.master.anacrusi:g} quarti"
                      if r.master.anacrusi else "assente")
            c2.metric("Note lette", len(r.master.note))
            c3.metric("Accordi dedotti", len(r.analisi.armonia))
        c4, c5, c6 = st.columns(3)
        c4.metric("Forma", r.analisi.forma.capitalize())
        c5.metric("Frasi / periodi",
                  f"{len(r.analisi.frasi)} / {len(r.analisi.periodi)}")
        c6.metric("Ritornelli", len(r.analisi.ritornelli))
        if r.analisi.sezioni:
            st.markdown("**Sezioni riconosciute**")
            st.code(" ".join(e for _a, _b, e in r.analisi.sezioni))
            st.markdown("**Melodia rilevata**")
            st.code(" ".join(nome_it(n.midi) for n in r.analisi.melodia[:80]) or "-")
            st.markdown("**Griglia armonica**")
            st.code(" | ".join(a.sigla() for a in r.analisi.armonia[:80]) or "-")

        with t3:
            for p in r.partitura.parti:
                suonate = [e for e in p.eventi if not e.pausa]
                with st.expander(f"{p.nome} — ruolo: {p.ruolo} — {len(suonate)} eventi"):
                    if not suonate:
                        st.write("Parte in pausa.")
                        continue
                    estremi = (min(min(e.altezze) for e in suonate),
                               max(max(e.altezze) for e in suonate))
                    st.write(f"Ambito impiegato: {nome_it(estremi[0])} – "
                             f"{nome_it(estremi[1])}"
                             + (f" · trasposizione: {p.trasposizione:+d} semitoni"
                                if p.trasposizione else ""))
                    st.code(" ".join(
                        ("/".join(nome_it(a) for a in e.altezze) if e.altezze else "·")
                        for e in p.eventi[:64]))

        with t4:
            for n in r.note_ia:
                st.info(n)
            if r.riferimenti:
                with st.expander("Informazioni sul brano originale (ricerca IA)"):
                    st.write(r.riferimenti)
            if r.relazione:
                st.markdown("**Relazione per il docente**")
                st.write(r.relazione)
            if r.report:
                st.warning(f"{len(r.report)} interventi automatici del validatore:")
                for riga in r.report[:200]:
                    st.write("- " + riga)
                if len(r.report) > 200:
                    st.caption(f"...e altri {len(r.report) - 200}.")
            else:
                st.success("Nessun intervento necessario: tutte le parti rispettano "
                           "i vincoli del livello selezionato.")

    # ==========================================================================
    # Feedback
    # ==========================================================================

    st.divider()
    st.subheader("💬 Dimmi come è andata")
    st.caption("Il progetto è in prova: ogni segnalazione aiuta a migliorarlo. "
               "Se hai trovato un errore, indica il brano e la battuta.")

    with st.form("feedback", clear_on_submit=True):
        c1, c2 = st.columns(2)
        nome_utente = c1.text_input("Nome (facoltativo)")
        email_utente = c2.text_input("La tua email (se vuoi una risposta)")
        categoria = st.selectbox(
            "Tipo di segnalazione",
            ["Errore musicale", "Errore tecnico", "Suggerimento", "Altro"])
        messaggio = st.text_area("Messaggio", height=140,
                                 placeholder="Es.: nella battuta 12 il clarinetto...")
        inviato = st.form_submit_button("Invia", type="primary")

    if inviato:
        if not messaggio.strip():
            st.warning("Scrivi qualcosa nel messaggio prima di inviare.")
        elif invia_feedback(nome_utente, email_utente, categoria, messaggio):
            st.success("Grazie! Il messaggio è stato inviato.")
        else:
            st.warning("L'invio automatico non è disponibile in questo momento.")
            st.markdown(
                f"[Apri il messaggio nel tuo programma di posta]"
                f"({link_mailto(nome_utente, email_utente, categoria, messaggio)})")
