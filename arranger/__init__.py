"""Arranger SMIM - arrangiatore automatico per orchestra scolastica."""

from .modello import (Accordo, Analisi, Configurazione, Evento, Misura, Nota,
                      Parte, Partitura, Spartito)
from .pipeline import Risultato, esegui
from .strumenti import LIVELLI, ORDINE_PARTITURA, REGISTRO

__version__ = "1.0.0"
__all__ = [
    "Accordo", "Analisi", "Configurazione", "Evento", "Misura", "Nota",
    "Parte", "Partitura", "Spartito", "Risultato", "esegui",
    "LIVELLI", "REGISTRO", "ORDINE_PARTITURA", "__version__",
]
