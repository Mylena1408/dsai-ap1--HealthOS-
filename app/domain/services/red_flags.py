"""Sinais de alerta em relatos de sintomas: diante deles, a orientação é sempre procurar urgência.

Regra de segurança do domínio, aplicada pelo caso de uso do assistente antes de qualquer provedor
de IA (SPEC/2026-10-06-assistente-ia.md).
"""
import re
import unicodedata

# Comparados sem acentos e em minúsculas (ver normalize).
RED_FLAGS = ["dor no peito", "falta de ar", "desmaio", "desmaiou", "convulsao", "sangramento intenso",
             "fraqueza subita", "boca torta", "confusao mental", "dificuldade para respirar", "labios roxos",
             "vomito com sangue", "pensamentos suicidas"]

URGENT_TEXT = ("Os sintomas descritos incluem sinais de alerta. Procure atendimento de urgência agora "
               "ou ligue para o SAMU (192). Esta orientação é educacional e não substitui avaliação profissional.")


def normalize(text: str) -> str:
    """Minúsculas, sem acentos e com espaços simples."""
    plain = unicodedata.normalize("NFKD", text.lower()).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", plain).strip()


def has_red_flags(text: str) -> bool:
    plain = normalize(text or "")
    return any(flag in plain for flag in RED_FLAGS)
