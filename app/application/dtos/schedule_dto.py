from pydantic import BaseModel
from datetime import datetime
from typing import Optional
import uuid

class ScheduleResponseDTO(BaseModel):
    id: uuid.UUID
    doctor_id: uuid.UUID
    patient_id: Optional[uuid.UUID]
    start_time: datetime
    end_time: datetime
    status: str
    duration_minutes: int
