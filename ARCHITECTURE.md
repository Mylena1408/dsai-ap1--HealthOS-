# HealthOS - Architecture Documentation

This document provides a deep dive into the architectural decisions and design patterns implemented in HealthOS.

## 1. Layered Architecture (Clean Architecture)

The system is structured into four distinct layers to ensure maintainability and testability.

### Domain Layer (`app/domain`)
Contains the business truth. It is completely agnostic of the database, API, or any framework.
- **Entities**: Rich domain objects (e.g., `Patient`, `Invoice`, `Schedule`) that encapsulate business logic and validations.
- **Exceptions**: Domain-specific errors (e.g., `DomainException`) that are translated to HTTP errors at the presentation layer.
- **Enums**: Standardization of types (e.g., `TriagePriority`, `MedicationUnit`).

### Application Layer (`app/application`)
The bridge between the domain and the outside world.
- **Use Cases**: Command patterns that execute specific business actions (e.g., `PharmacyUseCase.dispense_medication`).
- **Interfaces**: Abstract base classes for repositories, ensuring the application doesn't depend on the database implementation.
- **DTOs**: Data Transfer Objects for strict input/output contracts.

### Infrastructure Layer (`app/infrastructure`)
Handles the "how" of technical implementation.
- **Persistence**: SQLAlchemy models and repository implementations.
- **Security**: JWT handling, password hashing, and the `PermissionChecker` middleware.
- **Cross-cutting Concerns**: The `AuditInterceptor` using SQLAlchemy events to capture all changes automatically.

### Presentation Layer (`app/presentation`)
The entry point of the application.
- **API**: FastAPI routers.
- **Dependencies**: Integration of the repository and use case instances into the request cycle.

---

## 2. Key Technical Implementations

### 2.1. Medical Record Immutability
To comply with medical ethics and law, clinical notes cannot be edited once finalized.
- **Pattern**: State Machine.
- **Logic**: The `ClinicalNote` entity checks its status. If `status == FINALIZED`, the `update_content` method raises a `DomainException`.

### 2.2. Automated Audit Trail
Instead of adding audit logic to every use case, HealthOS uses an Infrastructure-level interceptor.
- **Implementation**: SQLAlchemy `after_insert`, `after_update`, and `after_delete` event listeners.
- **Result**: Every change to any entity in the system is automatically logged into the `audit_logs` table with a timestamp and the acting user's ID.

### 2.3. Temporal Conflict Resolution (Scheduling)
Scheduling a doctor requires preventing double-booking.
- **Logic**: The `SQLAlchemyScheduleRepository` implements overlap detection using the formula: `(StartA < EndB) AND (EndA > StartB)`. This ensures that any overlap, no matter how small, is detected.

### 2.4. Financial Precision
Using `float` for money leads to rounding errors.
- **Implementation**: All financial attributes use Python's `Decimal` type in the domain and `Numeric(12, 2)` in the database.

---

## 3. RBAC Model (Role-Based Access Control)

Permissions are defined as `module:action` strings:
- `patient:read`: View patient data.
- `patient:write`: Create/Edit patient data.
- `billing:admin`: Full control over invoices.
- `pharmacy:dispense`: Ability to remove items from stock.

These are mapped to Roles (e.g., `DOCTOR` has `patient:read`, `patient:write`, `clinical:write`).

---

## 4. Data Flow Example: Dispensing Medication
1. **Request**: `POST /api/v1/pharmacy/dispense` $\rightarrow$ `PharmacyRouter`.
2. **Validation**: `PermissionChecker` verifies if the user has `pharmacy:dispense`.
3. **Orchestration**: `PharmacyRouter` calls `PharmacyUseCase.dispense_medication()`.
4. **Domain Logic**: `InventoryItem` entity validates if `quantity >= requested_amount`.
5. **Persistence**: `SQLAlchemyInventoryRepository` updates the stock in PostgreSQL.
6. **Audit**: `AuditInterceptor` automatically logs the stock reduction.
7. **Response**: `PharmacyRouter` returns a `PatientAlertResponseDTO`.
