from app.domain.exceptions.base import DomainException

class ClinicalDomainException(DomainException):
    """Classe base para exceções relacionadas ao domínio clínico."""
    pass

class NoteImmutableError(ClinicalDomainException):
    """Lançada quando tenta-se editar uma nota que já foi finalizada/assinada."""
    def __init__(self, note_id: str):
        super().__init__(f"A nota clínica {note_id} é imutável e não pode ser alterada.")

class NoteNotFoundError(ClinicalDomainException):
    """Lançada quando uma nota clínica não é encontrada."""
    pass
