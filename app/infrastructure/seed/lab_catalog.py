"""Catálogo de exames (dado de referência, garantido no startup).

Faixas ILUSTRATIVAS e simplificadas (adulto genérico, sem distinção por sexo,
idade ou método laboratorial) — apenas para demonstração.
"""
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.laboratory import Analyte, ExamCategory, ExamType, Laboratory, SampleType
from app.domain.entities.reference_range import ReferenceRange as R
from app.infrastructure.persistence.repositories.sqlalchemy_clinical_monitoring_repository import (
    SQLAlchemyLaboratoryRepository,
)

BLOOD = SampleType.BLOOD
FASTING = "Jejum de 8 horas (ilustrativo)."


def build_exam_catalog() -> list[ExamType]:
    """Cria objetos novos a cada chamada (salvar atribui ids; não compartilhar instâncias)."""
    return [
        ExamType("HEMO", "Hemograma", ExamCategory.HEMATOLOGY, BLOOD, 24, [
            Analyte("HB", "Hemoglobina", R("g/dL", 2, 25, 12, 16, 7, 20)),
            Analyte("HT", "Hematócrito", R("%", 5, 80, 36, 48, 20, 60)),
            Analyte("LEUCO", "Leucócitos", R("/mm³", 100, 200000, 4000, 11000, 2000, 30000), 0),
            Analyte("PLAQ", "Plaquetas", R("/mm³", 1000, 2000000, 150000, 450000, 50000, 1000000), 0),
        ]),
        ExamType("GLI", "Glicemia de jejum", ExamCategory.BIOCHEMISTRY, BLOOD, 6, [
            Analyte("GLI", "Glicose", R("mg/dL", 10, 1500, 70, 99, 54, 400), 0),
        ], preparation=FASTING),
        ExamType("HBA1C", "Hemoglobina glicada", ExamCategory.BIOCHEMISTRY, BLOOD, 24, [
            Analyte("HBA1C", "Hemoglobina glicada", R("%", 2, 20, 4, 5.6, None, 14)),
        ]),
        ExamType("LIPID", "Perfil lipídico (colesterol)", ExamCategory.BIOCHEMISTRY, BLOOD, 24, [
            Analyte("CT", "Colesterol total", R("mg/dL", 20, 1000, None, 189), 0),
            Analyte("HDL", "Colesterol HDL", R("mg/dL", 5, 200, 40, None), 0),
            Analyte("LDL", "Colesterol LDL", R("mg/dL", 5, 600, None, 129), 0),
        ], preparation=FASTING),
        ExamType("TG", "Triglicerídeos", ExamCategory.BIOCHEMISTRY, BLOOD, 24, [
            Analyte("TG", "Triglicerídeos", R("mg/dL", 10, 5000, None, 149, None, 1000), 0),
        ], preparation=FASTING),
        ExamType("CREA", "Creatinina", ExamCategory.BIOCHEMISTRY, BLOOD, 12, [
            Analyte("CREA", "Creatinina", R("mg/dL", 0.1, 20, 0.6, 1.3, None, 4), 2),
        ]),
        ExamType("UREIA", "Ureia", ExamCategory.BIOCHEMISTRY, BLOOD, 12, [
            Analyte("UREIA", "Ureia", R("mg/dL", 2, 400, 15, 45, None, 150), 0),
        ]),
        ExamType("K", "Potássio", ExamCategory.BIOCHEMISTRY, BLOOD, 6, [
            Analyte("K", "Potássio", R("mmol/L", 1, 10, 3.5, 5.1, 2.5, 6.5)),
        ]),
        ExamType("TSH", "TSH", ExamCategory.HORMONES, BLOOD, 48, [
            Analyte("TSH", "TSH", R("µUI/mL", 0.001, 200, 0.4, 4.0, None, 50), 2),
        ]),
        ExamType("T4L", "T4 livre", ExamCategory.HORMONES, BLOOD, 48, [
            Analyte("T4L", "T4 livre", R("ng/dL", 0.05, 10, 0.8, 1.8), 2),
        ]),
        ExamType("VITD", "Vitamina D (25-OH)", ExamCategory.VITAMINS, BLOOD, 72, [
            Analyte("VITD", "25-hidroxivitamina D", R("ng/mL", 1, 300, 30, 100, 10, 150), 0),
        ]),
    ]


def build_laboratories() -> list[Laboratory]:
    return [
        Laboratory("Laboratório Central Fictício", "Av. Central, 100 - Centro Didático"),
        Laboratory("Laboratório Exemplo Norte", "Rua das Acácias, 250 - Vila Exemplo"),
    ]


async def ensure_lab_catalog(session: AsyncSession) -> int:
    """Cadastra exames e laboratórios ausentes (por código/nome). Retorna quantos foram criados."""
    repo = SQLAlchemyLaboratoryRepository(session)
    created = 0
    for exam_type in build_exam_catalog():
        if not await repo.get_exam_type_by_code(exam_type.code):
            await repo.save_exam_type(exam_type)
            created += 1
    existing_labs = {lab.name for lab in await repo.list_laboratories()}
    for laboratory in build_laboratories():
        if laboratory.name not in existing_labs:
            await repo.save_laboratory(laboratory)
            created += 1
    return created
