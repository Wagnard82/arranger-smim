"""
Arranger SMIM - interfaccia Streamlit (versione pubblica).

    streamlit run app.py

Ingresso: SOLO spartiti per PIANOFORTE in MusicXML (.xml/.musicxml/.mxl) o MIDI.
Include un modulo di feedback che invia una mail all'autore.
"""

from __future__ import annotations

import os
import smtplib
import tempfile
import traceback
from email.message import EmailMessage
from urllib.parse import quote

import streamlit as st

from arranger import Configurazione, esegui
from arranger import ia
from arranger.modello import nome_it
from arranger.orchestratore import costruisci_parti
from arranger.strumenti import LIVELLI, ORDINE_PARTITURA, REGISTRO, livello, strumento

DESTINATARIO = "claudiobianchi82@gmail.com"

st.set_page_config(page_title="Arranger SMIM", page_icon="🎼", layout="wide")

CARTELLA = os.path.join(tempfile.gettempdir(), "arranger_smim")
os.makedirs(CARTELLA, exist_ok=True)

st.title("🎼 Arranger SMIM")
st.caption("Da uno spartito per pianoforte a una partitura per orchestra "
           "scolastica, con controllo automatico dei limiti didattici.")


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
    stile = st.selectbox("Stile di arrangiamento", ["Normale", "Cinematico", "Jazz"])

    st.header("4 · Chi porta la melodia")
    attive = {k: v for k, v in formazione.items() if v > 0}
    parti_possibili = [p for p in costruisci_parti(Configurazione(formazione=attive))
                       if not strumento(p.strumento).percussione]
    etichette = {p.id: p.nome for p in parti_possibili}
    scelte_melodia = st.multiselect(
        "Strumenti solisti", options=list(etichette.keys()),
        format_func=lambda i: etichette.get(i, i),
        help=("Se non selezioni nulla decide il motore. Selezionando piu' "
              "strumenti la melodia passa dall'uno all'altro, frase per frase."))
    staffetta = st.checkbox("Fai passare la melodia fra i solisti", value=True)
    raddoppi = st.checkbox("Consenti raddoppi della melodia", value=True)

    st.header("5 · Opzioni")
    trasporto = st.slider("Trasporto (semitoni)", -12, 12, 0)
    genera_ly = st.checkbox("Genera anche il sorgente LilyPond (.ly)", value=False)
    usa_ia = st.checkbox("Usa l'IA per le scelte di orchestrazione",
                         value=False, disabled=not ia.disponibile())
    if not ia.disponibile():
        st.caption("IA non configurata: il motore lavora comunque con le sue regole.")

# ==========================================================================
# MODULO 1 - Ingestione (solo spartiti pianistici)
# ==========================================================================

st.subheader("Spartito di partenza")
st.info(
    "**Carica uno spartito per PIANOFORTE**: MusicXML (`.xml`, `.musicxml`, "
    "`.mxl`) oppure MIDI (`.mid`). Il file deve contenere una riduzione "
    "pianistica su due righi, chiave di violino e di basso, con melodia, "
    "armonia e basso gia' scritti per pianoforte. Partiture gia' orchestrate, "
    "parti staccate o file su un rigo solo danno risultati scadenti.")

col1, col2 = st.columns([2, 1])
with col1:
    caricato = st.file_uploader(
        "Spartito pianistico (MusicXML o MIDI)",
        type=["xml", "musicxml", "mxl", "mid", "midi"])
with col2:
    demo = st.checkbox("Prova con il brano dimostrativo",
                       help="Inno alla Gioia, con anacrusi")

avvia = st.button("🎻 Genera arrangiamento", type="primary", use_container_width=True)

# ==========================================================================
# Esecuzione
# ==========================================================================

if avvia:
    if not any(formazione.values()):
        st.error("Seleziona almeno uno strumento nella formazione.")
        st.stop()

    if demo:
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
                         usa_ia=usa_ia)

    with st.spinner("Analisi e arrangiamento in corso..."):
        try:
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

    t1, t2, t3, t4 = st.tabs(["📥 Download", "🔍 Analisi dello spartito",
                              "🎻 Parti generate", "✅ Report dei filtri"])

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
        st.caption("Il MusicXML si apre in MuseScore, Dorico, Sibelius e Finale: "
                   "nomi degli strumenti, graffa del pianoforte, armature "
                   "trasposte, dinamiche e articolazioni sono gia' impostate.")

    with t2:
        c1, c2, c3 = st.columns(3)
        c1.metric("Anacrusi", f"{r.master.anacrusi:g} quarti"
                  if r.master.anacrusi else "assente")
        c2.metric("Note lette", len(r.master.note))
        c3.metric("Accordi dedotti", len(r.analisi.armonia))
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
