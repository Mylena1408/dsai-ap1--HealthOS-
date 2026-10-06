"""Popula o banco configurado em DATABASE_URL com dados fictícios.

Uso:
    python -m scripts.seed_demo              # 50 pacientes, 20 profissionais, 100 consultas, 200 exames
    python -m scripts.seed_demo --patients 120 --appointments 300 --seed 7
"""
import argparse
import asyncio

import main  # noqa: F401 - registra todos os modelos no metadata
from app.infrastructure.persistence.database import AsyncSessionLocal, engine
from app.infrastructure.persistence.models.user_model import Base
from app.infrastructure.seed.demo_seed import DEFAULT_SEED, seed_demo_data


async def run(patients: int, appointments: int, exams: int, seed: int) -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as session:
        report = await seed_demo_data(session, patients=patients, appointments=appointments, exams=exams, seed=seed)
    print("Criados:", report.created or "nada")
    print("Já existentes:", report.skipped or "nada")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--patients", type=int, default=50, help="quantidade de pacientes fictícios")
    parser.add_argument("--appointments", type=int, default=100,
                        help="consultas fictícias (geradas apenas se ainda não houver nenhuma)")
    parser.add_argument("--exams", type=int, default=200,
                        help="solicitações de exame fictícias (geradas apenas se ainda não houver nenhuma)")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="semente do gerador (mesma semente = mesmos dados)")
    args = parser.parse_args()
    asyncio.run(run(args.patients, args.appointments, args.exams, args.seed))
