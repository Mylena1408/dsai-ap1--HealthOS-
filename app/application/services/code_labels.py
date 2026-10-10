"""Rótulos legíveis para os códigos gravados pelo sistema (situações, tipos, locais)."""

# Rótulos de códigos cuja forma legível não sai só trocando "_" por espaço (acentos, termos).
CODE_LABELS = {
    "NAO_COMPARECEU": "Não compareceu", "URGENCIA": "Urgência", "ATRASADO": "Em atraso",
    "PARCIALMENTE_PAGO": "Parcialmente paga", "PAGO": "Paga", "CANCELADO": "Cancelado",
    "PRESCRICAO_EMITIDA": "Prescrição emitida", "PRESCRICAO_CANCELADA": "Prescrição cancelada",
    "DIAGNOSTICO_REGISTRADO": "Diagnóstico registrado", "RELATORIO_EXPORTADO": "Relatório exportado",
    "EVOLUCAO_ASSINADA": "Evolução assinada",
    "FARMACIA_CENTRAL": "Farmácia central", "ALA_A": "Ala A",
    "MEDICO": "Médico(a)", "ENFERMEIRO": "Enfermeiro(a)", "FARMACEUTICO": "Farmacêutico(a)",
    "PSICOLOGO": "Psicólogo(a)",
}


def code_label(code: str) -> str:
    """EM_PROCESSAMENTO -> "Em processamento" (ou o rótulo de CODE_LABELS)."""
    return CODE_LABELS.get(code) or code.replace("_", " ").capitalize()
