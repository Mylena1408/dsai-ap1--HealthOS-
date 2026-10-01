from typing import List, Optional
import uuid
from datetime import datetime
from app.application.interfaces.medication_repository import MedicationRepository, InventoryRepository
from app.domain.entities.medication import Medication, InventoryItem, StockStatus
from app.domain.exceptions.base import DomainException

class PharmacyUseCase:
    """
    Caso de Uso para a gestão de farmácia e suprimentos.
    Orquestra a entrada e saída de medicamentos e monitora níveis de estoque.
    """

    def __init__(self, medication_repo: MedicationRepository, inventory_repo: InventoryRepository):
        self.medication_repo = medication_repo
        self.inventory_repo = inventory_repo

    async def register_medication(self, name: str, generic_name: str, dosage: str,
                                   unit: str, is_controlled: bool = False,
                                   manufacturer: Optional[str] = None,
                                   description: Optional[str] = None) -> Medication:
        """
        Cadastra um novo medicamento no catálogo global do hospital.
        """
        from app.domain.entities.medication import MedicationUnit

        try:
            unit_enum = MedicationUnit(unit)
        except ValueError:
            raise DomainException(message=f"Unidade de medida inválida. Use: {[u.value for u in MedicationUnit]}")

        medication = Medication(
            name=name,
            generic_name=generic_name,
            dosage=dosage,
            unit=unit_enum,
            is_controlled_substance=is_controlled,
            manufacturer=manufacturer,
            description=description
        )
        return await self.medication_repo.save(medication)

    async def add_inventory_stock(self, medication_id: uuid.UUID, location_id: uuid.UUID,
                                  quantity: float, expiration_date: Optional[datetime] = None) -> InventoryItem:
        """
        Adiciona medicamentos ao estoque de uma localização específica.
        """
        # 1. Verifica se o medicamento existe no catálogo
        med = await self.medication_repo.get_by_id(medication_id)
        if not med:
            raise DomainException(message="Medicamento não encontrado no catálogo.")

        # 2. Tenta recuperar item de estoque existente para a localização
        item = await self.inventory_repo.get_by_medication_and_location(medication_id, location_id)

        if item:
            item.add_stock(quantity)
            if expiration_date:
                item.expiration_date = expiration_date
        else:
            # Cria nova entrada de estoque
            item = InventoryItem(
                medication_id=medication_id,
                location_id=location_id,
                quantity=quantity,
                expiration_date=expiration_date
            )

        return await self.inventory_repo.save(item)

    async def dispense_medication(self, medication_id: uuid.UUID, location_id: uuid.UUID,
                                  quantity: float) -> InventoryItem:
        """
        Registra a saída de medicamento para atendimento a paciente.
        """
        item = await self.inventory_repo.get_by_medication_and_location(medication_id, location_id)

        if not item:
            raise DomainException(message="Medicamento não disponível nesta localização.")

        try:
            item.remove_stock(quantity)
        except ValueError as e:
            raise DomainException(message=str(e))

        return await self.inventory_repo.save(item)

    async def get_critical_stock_report(self) -> List[InventoryItem]:
        """
        Gera relatório de itens com estoque baixo (abaixo do limiar mínimo).
        """
        return await self.inventory_repo.get_low_stock_items()

    async def get_stock_status(self, medication_id: uuid.UUID, location_id: uuid.UUID) -> dict:
        """
        Retorna o status detalhado de disponibilidade de um item.
        """
        item = await self.inventory_repo.get_by_medication_and_location(medication_id, location_id)
        if not item:
            return {"status": StockStatus.OUT_OF_STOCK.value, "quantity": 0}

        return {
            "status": item.calculate_status().value,
            "quantity": item.quantity,
            "min_threshold": item.min_threshold,
            "expiration_date": item.expiration_date
        }
