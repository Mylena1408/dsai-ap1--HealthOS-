
# HealthOS - Integrated Hospital Management System

HealthOS is a large-scale, professional-grade Integrated Hospital Management System (IHMS) developed as a demonstration of software engineering excellence, focusing on Clean Architecture, Domain-Driven Design (DDD), and rigorous business rule enforcement.

## 🚀 Project Overview

The system is designed to manage the entire patient lifecycle within a hospital environment, from initial triage and appointment scheduling to clinical evolution, pharmacy management, and financial billing.

### Key Engineering Goals
- **Scalability**: Modular architecture allowing independent scaling of services.
- **Auditability**: Every single data change is captured via an automated audit interceptor.
- **Data Integrity**: Strict temporal validations for scheduling and physiological boundary checks for clinical data.
- **Immutability**: Implementation of state machines for clinical notes to ensure medical records cannot be altered after finalization.

---

## 🏗️ Architectural Design

HealthOS follows **Clean Architecture** principles, ensuring that business logic is decoupled from external frameworks (FastAPI, SQLAlchemy, PostgreSQL).

### Layers
1. **Domain Layer**: The heart of the system. Contains entities, value objects, and domain exceptions. Pure Python code with no external dependencies.
2. **Application Layer**: Orchestrates the flow of data. Contains Use Cases (Interactors) and Repository Interfaces.
3. **Infrastructure Layer**: Concrete implementations of repositories, security handlers (JWT), and database models (SQLAlchemy).
4. **Presentation Layer**: API endpoints (FastAPI), DTOs, and request/response validation.

### Core Design Patterns
- **Repository Pattern**: Abstracts the data source, allowing easy migration between databases.
- **Dependency Injection**: Used throughout the application to maintain loose coupling.
- **RBAC (Role-Based Access Control)**: Granular permission system (`modulo:action`) mapped to roles (Admin, Doctor, Nurse, Receptionist).
- **State Pattern**: Used in `ClinicalNote` and `Invoice` to manage lifecycle transitions.

---

## 🛠️ Technical Stack

- **Language**: Python 3.11+
- **API Framework**: FastAPI
- **ORM**: SQLAlchemy 2.0 (Async)
- **Database**: PostgreSQL (Production) / SQLite (Testing)
- **Security**: JWT (Stateless Auth) & bcrypt
- **Validation**: Pydantic v2
- **Testing**: Pytest + Pytest-asyncio

---

## 📦 Module Breakdown

| Module | Key Features | Complexity |
| :--- | :--- | :--- |
| **User & Auth** | RBAC, JWT, Audit Logs, User Management | Medium |
| **Patient Core** | Demographic Management, Clinical Evolution, Immutability | High |
| **Scheduling** | Overlap detection, Doctor Availability, Booking | Medium |
| **Triage** | Manchester Protocol, Vital Signs Validation, Waiting List | Medium |
| **Pharmacy** | Inventory Thresholds, Unit Standardization, Dispensing | High |
| **Billing** | Insurance Copayments, Invoice Lifecycle, Financial Summary | High |
| **Notifications** | Multi-channel alerts (SMS, Email, In-App), Priority Queue | Medium |

---

## 🚦 Getting Started

### Prerequisites
- Python 3.11+
- PostgreSQL (optional, defaults to SQLite for dev)

### Installation
```bash
pip install -r requirements.txt
```

### Running the Application
```bash
uvicorn app.main:app --reload
```

### Testing
```bash
pytest tests/
```

---

## 📈 Development Flow
The project follows a specification-driven development flow:
`Problem Analysis` $\rightarrow$ `Architectural Proposal` $\rightarrow$ `Component Identification` $\rightarrow$ `Specification` $\rightarrow$ `Implementation` $\rightarrow$ `Verification`.
>>>>>>> 49a6f09 (commit: initial version of HealthOS)
