"""Manipuladores de eventos: trilha de auditoria e política de notificações."""
from app.application.interfaces.engagement_repository import AuditRepository, InboxRepository
from app.domain.entities.inbox import Audience, InboxNotification, NotificationCategory as C, Priority, Sector
from app.domain.events import DomainEvent, EventType as E


class AuditTrail:
    """Registra todo evento publicado. Rastreabilidade didática — não é controle de segurança."""

    def __init__(self, repo: AuditRepository):
        self.repo = repo

    async def __call__(self, event: DomainEvent) -> None:
        await self.repo.add(event)


class NotificationPolicy:
    """
    Decide quem é avisado de quê. Cada regra devolve (público, destinatário/setor, categoria,
    título, link, prioridade); a mensagem é o resumo do próprio evento.
    """

    def __init__(self, repo: InboxRepository):
        self.repo = repo

    async def __call__(self, event: DomainEvent) -> None:
        for audience, target, category, title, link, priority in self._targets(event):
            if target is None:
                continue
            await self.repo.save(InboxNotification(
                audience=audience, category=category, title=title, message=event.summary,
                created_at=event.occurred_at, priority=priority, link=link, source_event=event.event_type.value,
                recipient_id=target if audience != Audience.SECTOR else None,
                sector=target if audience == Audience.SECTOR else None,
            ))

    @staticmethod
    def _targets(event: DomainEvent):
        P, PRO, S = Audience.PATIENT, Audience.PROFESSIONAL, Audience.SECTOR
        normal, high = Priority.NORMAL, Priority.HIGH
        data = event.data
        if event.event_type == E.APPOINTMENT_BOOKED:
            return [(P, event.patient_id, C.APPOINTMENT, "Consulta agendada", None, normal),
                    (PRO, event.professional_id, C.APPOINTMENT, "Nova consulta na sua agenda", "/app/consultas", normal)]
        if event.event_type == E.APPOINTMENT_RESCHEDULED:
            return [(P, event.patient_id, C.APPOINTMENT, "Consulta remarcada", None, normal),
                    (PRO, event.professional_id, C.APPOINTMENT, "Consulta remarcada", "/app/consultas", normal)]
        if event.event_type == E.APPOINTMENT_CANCELLED:
            return [(P, event.patient_id, C.APPOINTMENT, "Consulta cancelada", None, normal),
                    (PRO, event.professional_id, C.APPOINTMENT, "Consulta cancelada", "/app/consultas", normal)]
        if event.event_type == E.EXAM_REQUESTED:
            return [(S, Sector.LABORATORY, C.EXAM, "Novo exame solicitado", "/app/laboratorio",
                     high if data.get("urgent") else normal)]
        if event.event_type == E.EXAM_RELEASED:
            priority = high if data.get("abnormal") else normal
            return [(P, event.patient_id, C.EXAM, "Resultado de exame disponível", None, normal),
                    (PRO, event.professional_id, C.EXAM, "Resultado liberado de exame solicitado por você",
                     f"/app/prontuario?patient={event.patient_id}", priority)]
        if event.event_type == E.PRESCRIPTION_ISSUED:
            return [(S, Sector.PHARMACY, C.MEDICATION, "Nova prescrição para dispensar", "/app/farmacia", normal),
                    (S, Sector.NURSING, C.MEDICATION, "Nova prescrição para acompanhamento",
                     f"/app/prontuario?patient={event.patient_id}", normal),
                    (P, event.patient_id, C.MEDICATION, "Nova prescrição emitida", None, normal)]
        if event.event_type == E.MEDICATION_DISPENSED:
            return [(P, event.patient_id, C.MEDICATION, "Medicamentos dispensados", None, normal)]
        if event.event_type == E.INVOICE_ISSUED:
            return [(P, event.patient_id, C.FINANCIAL, "Nova fatura emitida", None, normal)]
        if event.event_type == E.PAYMENT_RECORDED:
            return [(P, event.patient_id, C.FINANCIAL, "Pagamento registrado", None, normal)]
        if event.event_type == E.INVOICE_CANCELLED:
            return [(P, event.patient_id, C.FINANCIAL, "Fatura cancelada", None, normal)]
        if event.event_type == E.ALERT_RAISED:
            sector = Sector(data["sector"]) if data.get("sector") else Sector.ADMINISTRATION
            title = ("Alerta agravado: " if data.get("escalated") else "Novo alerta: ") + data.get("title", "")
            return [(S, sector, C.ALERT, title, "/app/alertas", high if data.get("level") == "CRITICO" else normal)]
        return []
