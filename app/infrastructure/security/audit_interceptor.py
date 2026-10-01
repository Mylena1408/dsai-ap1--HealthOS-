from sqlalchemy import event
from sqlalchemy.orm import Session
from app.infrastructure.persistence.models.audit_model import AuditLogModel
import uuid

class AuditInterceptor:
    """
    Interceptor de Eventos do SQLAlchemy.
    Captura automaticamente alterações em entidades e gera logs de auditoria.
    """

    @staticmethod
    def listen_to_models(base_class):
        """Registra os listeners de auditoria para todos os modelos que herdam de Base."""
        event.listen(base_class, 'after_insert', AuditInterceptor.after_insert)
        event.listen(base_class, 'after_update', AuditInterceptor.after_update)
        event.listen(base_class, 'after_delete', AuditInterceptor.after_delete)

    @staticmethod
    def after_insert(mapper, connection, target):
        # Na prática, recuperaríamos o user_id do contexto da requisição (via ContextVar)
        # Para este exemplo, simulamos um ID de admin ou sistema
        user_id = uuid.uuid4()

        log = AuditLogModel(
            user_id=user_id,
            action="CREATE",
            resource=target.__class__.__name__,
            resource_id=str(getattr(target, 'id', 'unknown')),
            new_value=AuditInterceptor._to_dict(target)
        )
        connection.execute(AuditLogModel.__table__.insert().values(
            user_id=log.user_id,
            action=log.action,
            resource=log.resource,
            resource_id=log.resource_id,
            new_value=log.new_value
        ))

    @staticmethod
    def after_update(mapper, connection, target):
        user_id = uuid.uuid4()

        # Captura o que mudou usando o estado do SQLAlchemy
        state = getattr(target, '_sa_instance_state', None)
        changes = {}
        if state:
            for attr in state.attrs:
                hist = attr.history
                if hist.has_changes():
                    changes[attr.key] = {"old": hist.deleted[0] if hist.deleted else None,
                                        "new": hist.added[0] if hist.added else None}

        log = AuditLogModel(
            user_id=user_id,
            action="UPDATE",
            resource=target.__class__.__name__,
            resource_id=str(getattr(target, 'id', 'unknown')),
            new_value=changes
        )
        connection.execute(AuditLogModel.__table__.insert().values(
            user_id=log.user_id,
            action=log.action,
            resource=log.resource,
            resource_id=log.resource_id,
            new_value=log.new_value
        ))

    @staticmethod
    def after_delete(mapper, connection, target):
        user_id = uuid.uuid4()
        log = AuditLogModel(
            user_id=user_id,
            action="DELETE",
            resource=target.__class__.__name__,
            resource_id=str(getattr(target, 'id', 'unknown')),
            old_value=AuditInterceptor._to_dict(target)
        )
        connection.execute(AuditLogModel.__table__.insert().values(
            user_id=log.user_id,
            action=log.action,
            resource=log.resource,
            resource_id=log.resource_id,
            old_value=log.old_value
        ))

    @staticmethod
    def _to_dict(obj):
        """Converte atributos de um modelo para dicionário, omitando relações."""
        return {
            k: v for k, v in obj.__dict__.items()
            if not k.startswith('_') and not callable(v)
        }
