"""
Composizione della mail di feedback, con gli allegati.

Sta fuori da app.py per poterla provare senza Streamlit e senza un server di
posta: qui si costruisce il messaggio, l'invio vero (SMTP) resta
nell'interfaccia.

Cosa si allega, se l'utente lo consente:
  - lo spartito che ha caricato, cosi' il problema si riproduce sul file vero;
  - le impostazioni usate (organico, livelli, stile, opzioni) in JSON: lo
    stesso file con impostazioni diverse da' un arrangiamento diverso, e
    senza di esse la segnalazione non si riproduce;
  - la partitura generata e il report, se l'arrangiamento e' riuscito;
  - l'errore completo, se non e' riuscito: e' proprio il caso piu' utile
    da ricevere;
  - altri file scelti dall'utente (un PDF con la battuta cerchiata, uno
    screenshot...).
"""

from __future__ import annotations

import io
import json
import mimetypes
import os
import zipfile
from dataclasses import asdict, is_dataclass
from email.message import EmailMessage
from typing import Dict, List, Optional, Tuple

# Gmail accetta fino a 25 MB per messaggio, ma l'allegato in base64 cresce
# di un terzo: con 15 MB di file si sta comodi.
LIMITE_FILE = 10 * 1024 * 1024
LIMITE_TOTALE = 15 * 1024 * 1024

Allegato = Tuple[str, bytes]      # (nome del file, contenuto)


def config_json(cfg) -> bytes:
    """Le impostazioni di un arrangiamento, leggibili e ricaricabili."""
    dati = asdict(cfg) if is_dataclass(cfg) else dict(cfg)
    return json.dumps(dati, ensure_ascii=False, indent=2, default=str).encode("utf-8")


def allegati_tentativo(tentativo: Optional[Dict]) -> List[Allegato]:
    """
    I file dell'ultimo arrangiamento tentato, cosi' come l'interfaccia li ha
    registrati in session_state. Un file sparito dal disco (il server di
    Streamlit Cloud ripulisce la cartella temporanea) viene saltato.
    """
    if not tentativo:
        return []
    fuori: List[Allegato] = []

    def da_disco(percorso: Optional[str], nome: Optional[str] = None) -> None:
        if percorso and os.path.exists(percorso):
            with open(percorso, "rb") as f:
                fuori.append((nome or os.path.basename(percorso), f.read()))

    da_disco(tentativo.get("sorgente"), tentativo.get("nome_file"))
    if tentativo.get("config") is not None:
        fuori.append(("impostazioni.json", config_json(tentativo["config"])))
    da_disco(tentativo.get("partitura"))
    if tentativo.get("report"):
        fuori.append(("report.txt",
                      "\n".join(tentativo["report"]).encode("utf-8")))
    if tentativo.get("errore"):
        fuori.append(("errore.txt", tentativo["errore"].encode("utf-8")))
    return fuori


def entro_i_limiti(allegati: List[Allegato]) -> Tuple[List[Allegato], List[str]]:
    """Separa gli allegati che stanno nei limiti da quelli troppo grandi."""
    tenuti: List[Allegato] = []
    scartati: List[str] = []
    totale = 0
    for nome, dati in allegati:
        if len(dati) > LIMITE_FILE or totale + len(dati) > LIMITE_TOTALE:
            scartati.append(f"{nome} ({len(dati) / 1024 / 1024:.1f} MB)")
            continue
        tenuti.append((nome, dati))
        totale += len(dati)
    return tenuti, scartati


def componi(mittente: str, destinatario: str, nome: str, email: str,
            categoria: str, messaggio: str, lingua: str,
            allegati: List[Allegato], versione: str = "") -> EmailMessage:
    """Il messaggio completo, pronto per smtplib."""
    tenuti, scartati = entro_i_limiti(allegati)
    msg = EmailMessage()
    msg["Subject"] = (f"[Arranger SMIM] [{lingua.upper()}] {categoria} - "
                      f"da {nome or 'anonimo'}"
                      + (f" [{len(tenuti)} allegati]" if tenuti else ""))
    msg["From"] = mittente
    msg["To"] = destinatario
    if email:
        msg["Reply-To"] = email
    corpo = (f"Nome: {nome or '-'}\nEmail: {email or '-'}\n"
             f"Lingua: {lingua}\nVersione: {versione or '-'}\n"
             f"Categoria: {categoria}\n\n{messaggio}\n")
    if tenuti:
        corpo += "\nAllegati:\n" + "".join(f"  - {n}\n" for n, _ in tenuti)
    if scartati:
        corpo += ("\nNON allegati perche' troppo grandi:\n"
                  + "".join(f"  - {n}\n" for n in scartati))
    msg.set_content(corpo)
    for nome_file, dati in tenuti:
        tipo, _ = mimetypes.guess_type(nome_file)
        if nome_file.lower().endswith((".musicxml", ".xml")):
            tipo = "application/xml"
        elif nome_file.lower().endswith(".mxl"):
            tipo = "application/vnd.recordare.musicxml"
        principale, _, secondario = (tipo or "application/octet-stream").partition("/")
        msg.add_attachment(dati, maintype=principale, subtype=secondario,
                           filename=nome_file)
    return msg


def zip_allegati(allegati: List[Allegato]) -> bytes:
    """Tutti gli allegati in uno zip: per chi deve allegarli a mano."""
    buffer = io.BytesIO()
    usati: Dict[str, int] = {}
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        for nome, dati in allegati:
            # due file con lo stesso nome non si sovrascrivono
            n = usati.get(nome, 0)
            usati[nome] = n + 1
            if n:
                base, est = os.path.splitext(nome)
                nome = f"{base}_{n + 1}{est}"
            z.writestr(nome, dati)
    return buffer.getvalue()
