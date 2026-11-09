import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from alembic import command
from alembic.config import Config

load_dotenv()

backend_dir = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(backend_dir))
migrations_dir = backend_dir / "migrations"

services = ["identity", "projects", "notebook", "activity"]

for service in services:
    ini_path = migrations_dir / service / "alembic.ini"
    print(f"Running migration for {service}...")
    cfg = Config(str(ini_path))
    command.upgrade(cfg, "head")
    print(f"  [OK] {service} migrated to head.")

print("All database migrations verified and up to date!")
