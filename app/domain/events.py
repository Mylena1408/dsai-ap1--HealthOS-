"""Eventos de domínio: fatos relevantes que já aconteceram.

Os casos de uso publicam eventos sem saber quem reage a eles. Manipuladores
registrados no publicador (auditoria, notificações) tratam cada evento dentro da
mesma transação, o que mantém os módulos desacoplados.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
import uuid


class EventType(Enum):
    PATIENT_CREATED = "PACIENTE_CRIADO"
    APPOINTMENT_BOOKED = "CONSULTA_AGENDADA"
    APPOINTMENT_CONFIRMED = "CONSULTA_CONFIRMADA"
    APPOINTMENT_RESCHEDULED = "CONSULTA_REMARCADA"
    APPOINTMENT_CANCELLED = "CONSULTA_CANCELADA"
    APPOINTMENT_COMPLETED = "CONSULTA_FINALIZADA"
    APPOINTMENT_NO_SHOW = "CONSULTA_NAO_COMPARECEU"
    ALLERGY_RECORDED = "ALERGIA_REGISTRADA"
    DIAGNOSIS_RECORDED = "DIAGNOSTICO_REGISTRADO"
    EVOLUTION_SIGNED = "EVOLUCAO_ASSINADA"
    VITAL_SIGNS_RECORDED = "SINAIS_VITAIS_REGISTRADOS"
    EXAM_REQUESTED = "EXAME_SOLICITADO"
    EXAM_COLLECTED = "AMOSTRA_COLETADA"
    EXAM_RESULTED = "RESULTADO_REGISTRADO"
    EXAM_RELEASED = "RESULTADO_LIBERADO"
    EXAM_CANCELLED = "EXAME_CANCELADO"
    PRESCRIPTION_ISSUED = "PRESCRICAO_EMITIDA"
    PRESCRIPTION_CANCELLED = "PRESCRICAO_CANCELADA"
    MEDICATION_DISPENSED = "MEDICAMENTO_DISPENSADO"
    STOCK_RECEIVED = "ESTOQUE_ENTRADA"
    STOCK_DISCARDED = "ESTOQUE_DESCARTE"
    ALERT_RAISED = "ALERTA_GERADO"
    ALERT_RESOLVED = "ALERTA_RESOLVIDO"
    AI_CONSULTED = "ASSISTENTE_CONSULTADO"
    INVOICE_ISSUED = "FATURA_EMITIDA"
    PAYMENT_RECORDED = "PAGAMENTO_REGISTRADO"
    INVOICE_CANCELLED = "FATURA_CANCELADA"
    REPORT_EXPORTED = "RELATORIO_EXPORTADO"


@dataclass(frozen=True)
class DomainEvent:
    event_type: EventType
    occurred_at: datetime
    entity_type: str            # ex.: "Consulta", "Exame", "Lote"
    entity_id: uuid.UUID
    summary: str                # frase legível para auditoria e notificações
    patient_id: Optional[uuid.UUID] = None
    professional_id: Optional[uuid.UUID] = None  # quem executou ou a quem se refere
    data: dict[str, Any] = field(default_factory=dict)
