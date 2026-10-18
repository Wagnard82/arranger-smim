"""
Arranger SMIM - interfaccia Streamlit (versione pubblica), italiano/inglese.

    streamlit run app.py

Ingresso: spartiti in MusicXML (.xml/.musicxml/.mxl).
Include un modulo di feedback che invia una mail all'autore.

Lingua: il selettore in cima alla barra laterale cambia interfaccia, report,
nomi delle parti e didascalie della partitura. Si puo' anche aprire l'app
direttamente in inglese con ?lang=en nell'indirizzo. La musica prodotta e'
identica nelle due lingue.
"""

from __future__ import annotations

import os
import smtplib
from datetime import datetime
import tempfile
import traceback
from urllib.parse import quote

import streamlit as st
import streamlit.components.v1 as components

from arranger import Configurazione, esegui
from arranger import ia
from arranger import feedback as FB
from arranger import lingua as L
from arranger.anteprima import html_anteprima
from arranger.esportatore import sigla_scritta
from arranger.orchestratore import costruisci_parti
from arranger.strumenti import ORDINE_PARTITURA, strumento
from arranger.testi_interfaccia import ui
from arranger.versione import (COMPILATO, DATA, DATA_EN, NOVITA, NOVITA_EN,
                               PRECEDENTE, VERSIONE)

DESTINATARIO = "claudiobianchi82@gmail.com"

st.set_page_config(page_title="Arranger SMIM", page_icon="🎼", layout="wide")

# --------------------------------------------------------------------------
# Lingua: prima di tutto, perche' da lei dipende ogni testo della pagina.
# --------------------------------------------------------------------------
if "lingua" not in st.session_state:
    richiesta = st.query_params.get("lang", "it")
    st.session_state["lingua"] = richiesta if richiesta in L.LINGUE else "it"

with st.sidebar:
    # etichetta fissa: se cambiasse con la lingua, Streamlit lo tratterebbe
    # come un widget nuovo proprio nel momento in cui lo si usa
    lng = st.radio("🌐 Lingua · Language", list(L.LINGUE),
                   format_func=lambda k: L.LINGUE[k], horizontal=True,
                   key="lingua")
st.query_params["lang"] = lng


def T(chiave: str, **valori) -> str:
    return ui(chiave, lng, **valori)


# --------------------------------------------------------------------------
# Widget che sopravvivono al cambio di lingua.
#
# Streamlit riconosce un widget anche dalla sua etichetta: tradotta
# l'etichetta, il widget e' «nuovo» e torna al valore iniziale. Passando
# all'inglese si perderebbero organico e livelli appena impostati. Per
# evitarlo ogni valore e' copiato in session_state e restituito al widget
# come valore iniziale alla volta successiva.
# --------------------------------------------------------------------------


def _ombra(nome: str, predefinito=None):
    return st.session_state.get("_v_" + nome, predefinito)


def _salva(nome: str, valore):
    st.session_state["_v_" + nome] = valore
    return valore


def scelta(widget, nome: str, etichetta: str, opzioni, predefinito=None, **kw):
    """radio / selectbox: le opzioni sono chiavi, l'etichetta e' format_func."""
    opzioni = list(opzioni)
    attuale = _ombra(nome, predefinito if predefinito is not None else opzioni[0])
    indice = opzioni.index(attuale) if attuale in opzioni else 0
    return _salva(nome, widget(etichetta, opzioni, index=indice, **kw))


def valore(widget, nome: str, etichetta: str, predefinito, **kw):
    """number_input / slider / checkbox / text_input."""
    return _salva(nome, widget(etichetta, value=_ombra(nome, predefinito), **kw))


# Versione per cui e' scritta QUESTA interfaccia. Se la cartella arranger/
# sul server e' di un'altra versione — succede caricando su GitHub solo una
# parte dei file — l'app non deve partire con un errore incomprensibile a
# meta' esecuzione, ma dire subito che cosa manca.
VERSIONE_INTERFACCIA = "0.9.4"
if VERSIONE != VERSIONE_INTERFACCIA:
    st.error(T("file_non_allineati", ui=VERSIONE_INTERFACCIA, motore=VERSIONE))
    st.stop()

CARTELLA = os.path.join(tempfile.gettempdir(), "arranger_smim")
os.makedirs(CARTELLA, exist_ok=True)

st.title(T("titolo", versione=VERSIONE, compilato=COMPILATO))
st.caption(T("sottotitolo"))

# Diagnostica: quale file sta girando davvero e quando e' stato modificato.
# Con piu' copie del progetto sul disco e' l'unico modo per esserne certi.
_percorso_app = os.path.abspath(__file__)
_modificato = datetime.fromtimestamp(os.path.getmtime(_percorso_app))
st.caption(T("file_in_esecuzione", percorso=_percorso_app,
             data=_modificato.strftime(T("formato_data"))))

PRINCIPALE, REGISTRO_MODIFICHE = st.columns([3, 1], gap="large")

with REGISTRO_MODIFICHE:
    st.markdown(T("novita", versione=VERSIONE))
    st.caption(T("rispetto_a", precedente=PRECEDENTE,
                 data=DATA_EN if lng == "en" else DATA))
    for titolo, voci in (NOVITA_EN if lng == "en" else NOVITA):
        with st.expander(titolo, expanded=False):
            for voce in voci:
                st.markdown(f"- {voce}")
    st.caption(T("segnala"))


# ==========================================================================
# Feedback
# ==========================================================================


def invia_feedback(nome: str, email: str, categoria: str, messaggio: str,
                   allegati=()) -> bool:
    """
    Invia il feedback via SMTP usando le credenziali in st.secrets, con gli
    eventuali allegati (spartito, impostazioni, partitura, file scelti).
    Ritorna False se le credenziali mancano o l'invio fallisce: in quel caso
    l'interfaccia offre il ripiego con un link mailto e lo zip da allegare.
    """
    try:
        cfg = st.secrets["email"]
    except Exception:
        return False
    try:
        msg = FB.componi(cfg["mittente"], cfg.get("destinatario", DESTINATARIO),
                         nome, email, categoria, messaggio, lng,
                         list(allegati), versione=VERSIONE)
        with smtplib.SMTP_SSL(cfg.get("server", "smtp.gmail.com"),
                              int(cfg.get("porta", 465))) as server:
            server.login(cfg["mittente"], cfg["password"])
            server.send_message(msg)
        return True
    except Exception:
        return False


def link_mailto(nome: str, email: str, categoria: str, messaggio: str) -> str:
    corpo = quote(f"Nome: {nome}\nEmail: {email}\n\n{messaggio}")
    oggetto = quote(f"[Arranger SMIM] [{lng.upper()}] {categoria}")
    return f"mailto:{DESTINATARIO}?subject={oggetto}&body={corpo}"


# ==========================================================================
# MODULO 2 - Configurazione
# ==========================================================================

with st.sidebar:
    st.header(T("formazione"))
    formazione = {}
    for chiave in ORDINE_PARTITURA:
        formazione[chiave] = valore(
            st.number_input, f"q_{chiave}", L.nome_strumento(chiave, lng), 0,
            min_value=0, max_value=6, help=T("aiuto_divisi"))

    st.header(T("livello"))
    # Le opzioni sono le chiavi interne; cambia solo l'etichetta mostrata.
    # Cosi' passando da una lingua all'altra la scelta resta quella.
    liv = scelta(st.radio, "liv_classe", T("classe"), L.CHIAVI_LIVELLO,
                 format_func=lambda k: L.etichetta_livello(k, lng),
                 label_visibility="collapsed")
    st.info(L.note_livello(liv, lng))

    # Livelli per singolo strumento. Le classi eterogenee sono la norma piu'
    # che l'eccezione: capita di avere un violino al terzo anno di strumento
    # accanto a un flauto che ha cominciato a ottobre.
    livelli_strumenti = {}
    attivi = [k for k in ORDINE_PARTITURA if formazione.get(k, 0) > 0]
    if attivi:
        with st.expander(T("livelli_strumento")):
            st.caption(T("livelli_strumento_aiuto"))
            for chiave in attivi:
                quanti = formazione[chiave]
                scelto = scelta(
                    st.selectbox, f"liv_{chiave}",
                    L.nome_strumento(chiave, lng)
                    + (T("tutti_i", n=quanti) if quanti > 1 else ""),
                    [""] + L.CHIAVI_LIVELLO,
                    format_func=lambda k: (L.etichetta_livello(k, lng) if k
                                           else T("come_la_classe")))
                if scelto:
                    livelli_strumenti[chiave] = scelto
                # Dentro la stessa sezione i leggii sono spesso di livello
                # diverso: il secondo violino e' quasi sempre l'allievo meno
                # avanti.
                if quanti > 1:
                    for i in range(1, quanti + 1):
                        id_parte = f"{chiave}{i}"
                        s2 = scelta(
                            st.selectbox, f"liv_{id_parte}",
                            f"   └ {L.abbrev_strumento(chiave, lng)} {i}",
                            [""] + L.CHIAVI_LIVELLO,
                            format_func=lambda k: (
                                L.etichetta_livello(k, lng) if k
                                else T("come_lo_strumento")))
                        if s2:
                            livelli_strumenti[id_parte] = s2
            if livelli_strumenti:
                st.success(T("livelli_attivi", n=len(livelli_strumenti)))

    st.header(T("stile"))
    stile = scelta(st.selectbox, "stile", T("stile_arrangiamento"),
                   ["Normale", "Cinematico", "Jazz"],
                   format_func=lambda k: L.stile(k, lng))

    # ----------------------------------------------------------------
    # Impostazioni avanzate: tutto cio' che non serve al primo utilizzo
    # resta chiuso qui dentro, con valori predefiniti sensati.
    # ----------------------------------------------------------------
    with st.expander(T("avanzate")):
        st.markdown(f"**{T('come_trattare')}**")
        modo = scelta(st.radio, "modo", T("come_trattare"),
                      ["auto", "melodico", "tessitura"],
                      horizontal=True, label_visibility="collapsed",
                      format_func=lambda x: T(f"modo_{x}"), help=T("modo_aiuto"))
        stile_automatico = valore(st.checkbox, "stile_auto", T("stile_ia"),
                                  False, help=T("stile_ia_aiuto"))
        if stile_automatico:
            stile = "Automatico"

        st.markdown(T("chi_melodia"))
        attive = {k: v for k, v in formazione.items() if v > 0}
        parti_possibili = [
            p for p in costruisci_parti(Configurazione(formazione=attive,
                                                       lingua=lng))
            if not strumento(p.strumento).percussione]
        etichette = {p.id: p.nome for p in parti_possibili}
        scelte_melodia = _salva("solisti", st.multiselect(
            T("solisti"), options=list(etichette.keys()),
            default=[i for i in _ombra("solisti", []) if i in etichette],
            format_func=lambda i: etichette.get(i, i), help=T("solisti_aiuto")))
        staffetta = valore(st.checkbox, "staffetta", T("staffetta"), True)
        cambio = scelta(st.selectbox, "cambio", T("quando_cambiare"),
                        ["auto", "periodo", "sezione", "frase"],
                        format_func=lambda x: T(f"cambio_{x}"),
                        disabled=not staffetta, help=T("cambio_aiuto"))
        from arranger import frasi_music21 as _fm21
        frasi_avanzate = valore(
            st.checkbox, "frasi_avanzate", T("frasi_avanzate"), False,
            disabled=not _fm21.disponibile(), help=T("frasi_avanzate_aiuto"))
        if not _fm21.disponibile():
            st.caption(T("per_attivarlo"))
        minimo_solista = valore(
            st.slider, "minimo_solista", T("misure_minime"), 8,
            min_value=2, max_value=24,
            disabled=not staffetta, help=T("misure_minime_aiuto"))
        raddoppi = valore(st.checkbox, "raddoppi", T("raddoppi"), True)

        st.markdown(T("altre_opzioni"))
        trasporto = valore(st.slider, "trasporto", T("trasporto"), 0,
                           min_value=-12, max_value=12)
        riempi = valore(st.checkbox, "riempi", T("riempi"), True,
                        help=T("riempi_aiuto"))
        silenzio_max = valore(st.slider, "silenzio_max", T("pausa_max"), 2,
                              min_value=1, max_value=8, disabled=not riempi)
        genera_ly = valore(st.checkbox, "genera_ly", T("genera_ly"), False)
        debug = valore(st.checkbox, "debug", T("confronto"), False,
                       help=T("confronto_aiuto"))

        st.markdown(T("ia"))
        # la chiave puo' arrivare dai segreti dell'istanza o essere
        # incollata qui
        try:
            ia.configura_chiave(st.secrets["anthropic"]["api_key"])
            chiave_da_segreti = True
        except Exception:
            chiave_da_segreti = False

        stato_ia = ia.stato()
        if not stato_ia["libreria"]:
            st.caption(T("ia_libreria"))
            usa_ia = False
            funzioni_ia = set()
            modello_ia = ia.MODELLO_DEFAULT
        else:
            if not chiave_da_segreti:
                chiave = st.text_input(T("ia_chiave"), type="password",
                                       help=T("ia_chiave_aiuto"))
                if chiave:
                    ia.configura_chiave(chiave)
                stato_ia = ia.stato()

            usa_ia = valore(st.checkbox, "usa_ia", T("ia_attiva"), False,
                            disabled=not stato_ia["chiave"])
            if not stato_ia["chiave"]:
                st.caption(T("ia_incolla"))

            nomi_modelli = {v: k for k, v in ia.modelli(lng).items()}
            modello_ia = scelta(st.selectbox, "modello_ia", T("ia_modello"),
                                list(nomi_modelli),
                                format_func=lambda m: nomi_modelli[m],
                                disabled=not usa_ia)

            predefinite = {"melodia", "stile"}
            funzioni_ia = set()
            for chiave_f, (titolo_f, spiega) in ia.funzioni(lng).items():
                if valore(st.checkbox, f"ia_{chiave_f}", titolo_f,
                          chiave_f in predefinite, disabled=not usa_ia,
                          help=spiega):
                    funzioni_ia.add(chiave_f)
            if usa_ia:
                st.caption(T("ia_chiamate", n=len(funzioni_ia)))
                if st.button(T("ia_prova")):
                    ok, messaggio = ia.prova_connessione(modello_ia, lng)
                    (st.success if ok else st.error)(messaggio)


# ==========================================================================
# MODULO 1 - Ingestione (solo MusicXML)
# ==========================================================================

with PRINCIPALE:
    st.subheader(T("spartito_partenza"))
    st.info(T("spiega_ingresso"))

    col1, col2 = st.columns([2, 1])
    with col1:
        caricato = st.file_uploader(T("carica"), type=["xml", "musicxml", "mxl"])
        with st.expander(T("altri_formati")):
            st.markdown(T("altri_formati_testo"))
    with col2:
        demo = scelta(
            st.radio, "demo", T("esempio"), ["nessuno", "pf", "ls"],
            format_func=lambda k: T({"nessuno": "esempio_nessuno",
                                     "pf": "esempio_pf",
                                     "ls": "esempio_ls"}[k]),
            help=T("esempio_aiuto"))

    avvia = st.button(T("genera"), type="primary", use_container_width=True)

    # ==========================================================================
    # Esecuzione
    # ==========================================================================

    if avvia:
        if not any(formazione.values()):
            st.error(T("err_formazione"))
            st.stop()

        if demo == "pf":
            from esempi import genera_esempi
            sorgente = genera_esempi.inno_alla_gioia(
                os.path.join(CARTELLA, "inno_alla_gioia.xml"))
        elif demo == "ls":
            from esempi import genera_esempi
            sorgente = genera_esempi.lead_sheet(
                os.path.join(CARTELLA, "lead_sheet.xml"))
        elif caricato is not None:
            sorgente = os.path.join(CARTELLA, caricato.name)
            with open(sorgente, "wb") as f:
                f.write(caricato.getbuffer())
        else:
            st.error(T("err_sorgente"))
            st.stop()

        cfg = Configurazione(formazione={k: v for k, v in formazione.items() if v > 0},
                             livelli_strumenti=livelli_strumenti,
                             livello=liv, stile=stile, trasporto=trasporto,
                             strumenti_melodia=scelte_melodia,
                             staffetta_melodia=staffetta, raddoppi_melodia=raddoppi,
                             modo=modo, cambio_solista=cambio,
                             frasi_music21=frasi_avanzate,
                             riempi_silenzi=riempi,
                             silenzio_massimo_misure=silenzio_max,
                             misure_minime_solista=minimo_solista,
                             debug_originale=debug, usa_ia=usa_ia,
                             modello_ia=modello_ia, lingua=lng)
        for funzione in ia.FUNZIONI:
            setattr(cfg, f"ia_{funzione}", funzione in funzioni_ia)

        # Registrato PRIMA di generare: se l'arrangiamento fallisce, il file
        # e le impostazioni restano disponibili per il modulo di feedback,
        # ed e' proprio il caso che piu' serve ricevere.
        st.session_state["ultimo_tentativo"] = {
            "sorgente": sorgente,
            "nome_file": caricato.name if (demo == "nessuno" and caricato)
            else os.path.basename(sorgente),
            "config": cfg, "esempio": demo != "nessuno"}
        with st.spinner(T("in_corso")):
            try:
                st.session_state["risultato"] = esegui(
                    sorgente, cfg, cartella=CARTELLA, esporta_ly=genera_ly)
                st.session_state["ultimo_tentativo"].update(
                    partitura=st.session_state["risultato"].percorso_xml,
                    report=st.session_state["risultato"].report)
            except Exception as e:
                st.session_state.pop("risultato", None)
                st.session_state["ultimo_tentativo"]["errore"] = traceback.format_exc()
                st.error(T("err_elabora", errore=L.traduci_errore(str(e), lng)))
                with st.expander(T("dettagli")):
                    st.code(traceback.format_exc())
                # niente st.stop(): la pagina prosegue fino al modulo di
                # feedback, che ha gia' pronto il file da inviare
                st.info(T("errore_segnala"))

    # ==========================================================================
    # Risultati
    # ==========================================================================

    r = st.session_state.get("risultato")
    if r:
        # Il risultato porta con se' la lingua in cui e' stato generato
        # (report, nomi delle parti, file): cambiando lingua dopo, i testi
        # dell'interfaccia cambiano subito, il contenuto alla prossima
        # generazione.
        st.success(T("completato", titolo=r.master.titolo,
                     parti=len(r.partitura.parti),
                     misure=len(r.partitura.misure)))

        t0, t1, t2, t3, t4 = st.tabs(
            [T("tab_anteprima"), T("tab_download"), T("tab_analisi"),
             T("tab_parti"), T("tab_report")])

        with t0:
            c1, c2 = st.columns([1, 1])
            quante = c1.slider(
                T("misure_mostrare"), 4, max(8, len(r.partitura.misure)),
                min(16, len(r.partitura.misure)), help=T("misure_mostrare_aiuto"))
            zoom = c2.slider(T("zoom"), 0.4, 1.2, 0.7, 0.05)
            con_audio = st.checkbox(T("lettore_midi"), value=True,
                                    help=T("lettore_midi_aiuto"))
            try:
                with open(r.percorso_xml, encoding="utf-8") as f:
                    xml_partitura = f.read()
                dati_midi = None
                if con_audio and r.percorso_midi and os.path.exists(r.percorso_midi):
                    with open(r.percorso_midi, "rb") as f:
                        dati_midi = f.read()
                components.html(
                    html_anteprima(xml_partitura, midi=dati_midi, zoom=zoom,
                                   misure=int(quante), lingua=lng),
                    height=820, scrolling=True)
                st.caption(T("anteprima_indicativa"))
            except Exception as errore:
                st.warning(T("anteprima_non_disp", errore=errore))
            with st.expander(T("non_vedi")):
                st.markdown(T("non_vedi_testo"))

        with t1:
            with open(r.percorso_xml, "rb") as f:
                st.download_button(T("scarica_xml"), f.read(),
                                   file_name=os.path.basename(r.percorso_xml),
                                   mime="application/vnd.recordare.musicxml+xml",
                                   use_container_width=True)
            if r.percorso_midi and os.path.exists(r.percorso_midi):
                with open(r.percorso_midi, "rb") as f:
                    st.download_button(T("scarica_midi"), f.read(),
                                       file_name=os.path.basename(r.percorso_midi),
                                       mime="audio/midi", use_container_width=True)
            if r.percorso_ly and os.path.exists(r.percorso_ly):
                with open(r.percorso_ly, "rb") as f:
                    st.download_button(T("scarica_ly"), f.read(),
                                       file_name=os.path.basename(r.percorso_ly),
                                       mime="text/plain", use_container_width=True)
            st.caption(T("download_nota"))

        with t2:
            c1, c2, c3 = st.columns(3)
            c1.metric(T("anacrusi"), T("quarti", n=r.master.anacrusi)
                      if r.master.anacrusi else T("assente"))
            c2.metric(T("note_lette"), len(r.master.note))
            c3.metric(T("accordi_dedotti"), len(r.analisi.armonia))
            c4, c5, c6 = st.columns(3)
            c4.metric(T("forma"), L.forma(r.analisi.forma, lng))
            c5.metric(T("frasi_periodi"),
                      f"{len(r.analisi.frasi)} / {len(r.analisi.periodi)}")
            c6.metric(T("ritornelli"), len(r.analisi.ritornelli))
            if r.analisi.sezioni:
                st.markdown(T("sezioni"))
                st.code(" ".join(e for _a, _b, e in r.analisi.sezioni))
            st.markdown(T("melodia_rilevata"))
            st.code(" ".join(L.nota(n.midi, lng)
                             for n in r.analisi.melodia[:80]) or "-")
            st.markdown(T("griglia"))
            armatura = r.partitura.misure[0].tonalita if r.partitura.misure else 0
            st.code(" | ".join(sigla_scritta(a, armatura)
                               for a in r.analisi.armonia[:80]) or "-")

        with t3:
            for p in r.partitura.parti:
                suonate = [e for e in p.eventi if not e.pausa]
                with st.expander(T("parte_riga", nome=p.nome,
                                   ruolo=L.ruolo(p.ruolo, lng), n=len(suonate))):
                    if not suonate:
                        st.write(T("parte_in_pausa"))
                        continue
                    estremi = (min(min(e.altezze) for e in suonate),
                               max(max(e.altezze) for e in suonate))
                    st.write(T("ambito", da=L.nota(estremi[0], lng),
                               a=L.nota(estremi[1], lng))
                             + (T("trasposizione", n=p.trasposizione)
                                if p.trasposizione else ""))
                    st.code(" ".join(
                        ("/".join(L.nota(a, lng) for a in e.altezze)
                         if e.altezze else "·")
                        for e in p.eventi[:64]))

        with t4:
            for n in r.note_ia:
                st.info(n)
            if r.riferimenti:
                with st.expander(T("info_brano")):
                    st.write(r.riferimenti)
            if r.relazione:
                st.markdown(T("relazione"))
                st.write(r.relazione)
            if r.report:
                st.warning(T("interventi", n=len(r.report)))
                for riga in r.report[:200]:
                    st.write("- " + riga)
                if len(r.report) > 200:
                    st.caption(T("e_altri", n=len(r.report) - 200))
            else:
                st.success(T("nessun_intervento"))

    # ==========================================================================
    # Feedback
    # ==========================================================================

    st.divider()
    st.subheader(T("feedback_titolo"))
    st.caption(T("feedback_spiega"))

    with st.form("feedback", clear_on_submit=True):
        c1, c2 = st.columns(2)
        nome_utente = c1.text_input(T("nome_facoltativo"))
        email_utente = c2.text_input(T("tua_email"))
        categoria = st.selectbox(
            T("tipo_segnalazione"),
            [T("cat_musicale"), T("cat_tecnico"), T("cat_suggerimento"),
             T("cat_altro")])
        messaggio = st.text_area(T("messaggio"), height=140,
                                 placeholder=T("messaggio_es"))

        # Allegati: il brano dell'ultimo arrangiamento con le impostazioni
        # usate, piu' qualunque altro file. Senza il file vero una
        # segnalazione musicale quasi mai si riproduce.
        tentativo = st.session_state.get("ultimo_tentativo")
        allega_ultimo = False
        if tentativo:
            allega_ultimo = st.checkbox(
                T("allega_ultimo", file=tentativo["nome_file"]), value=True,
                help=T("allega_ultimo_aiuto"))
            if tentativo.get("errore"):
                st.caption(T("allega_con_errore"))
        altri_file = st.file_uploader(
            T("allega_altri"), accept_multiple_files=True,
            type=["xml", "musicxml", "mxl", "mid", "midi", "pdf", "png",
                  "jpg", "jpeg", "zip"],
            help=T("allega_altri_aiuto"))
        st.caption(T("allega_privacy"))
        inviato = st.form_submit_button(T("invia"), type="primary")

    if inviato:
        allegati = FB.allegati_tentativo(tentativo) if allega_ultimo else []
        allegati += [(f.name, f.getvalue()) for f in (altri_file or [])]
        _, troppo_grandi = FB.entro_i_limiti(allegati)
        if not messaggio.strip():
            st.warning(T("scrivi_qualcosa"))
        elif invia_feedback(nome_utente, email_utente, categoria, messaggio,
                            allegati):
            st.success(T("grazie_allegati", n=len(allegati) - len(troppo_grandi))
                       if allegati else T("grazie"))
            if troppo_grandi:
                st.warning(T("allegati_troppo_grandi",
                             elenco=", ".join(troppo_grandi)))
        else:
            st.warning(T("invio_non_disp"))
            st.markdown(
                f"[{T('apri_posta')}]"
                f"({link_mailto(nome_utente, email_utente, categoria, messaggio)})")
            if allegati:
                # il link mailto non puo' portare allegati: li si offre in
                # uno zip da aggiungere a mano alla mail
                st.info(T("allega_a_mano"))
                st.download_button(T("scarica_allegati"),
                                   FB.zip_allegati(allegati),
                                   file_name="arranger_smim_feedback.zip",
                                   mime="application/zip")
