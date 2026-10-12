"""Arranger SMIM - arrangiatore automatico per orchestra scolastica."""

from .modello import (Accordo, Analisi, Configurazione, Evento, Misura, Nota,
                      Parte, Partitura, Spartito)
from .pipeline import Risultato, esegui
from .strumenti import LIVELLI, ORDINE_PARTITURA, REGISTRO

from .versione import NOVITA, VERSIONE

__version__ = VERSIONE
__all__ = [
    "Accordo", "Analisi", "Configurazione", "Evento", "Misura", "Nota",
    "Parte", "Partitura", "Spartito", "Risultato", "esegui",
    "LIVELLI", "REGISTRO", "ORDINE_PARTITURA", "NOVITA", "VERSIONE",
    "__version__",
]
