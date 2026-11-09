import os
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

backend_dir = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(backend_dir))

load_dotenv()

from services.identity.app.models import Organization, User, Membership
from services.identity.app.security import hash_password
from services.projects.app.models import Project, ProjectMembership
from services.notebook.app.models import (
    Experiment,
    NotebookEntry,
    StorageLocation,
    Sample,
    InventoryItem,
    StockMovement,
    EquipmentResource,
)
from services.activity.app.models import ActivityEvent

now = datetime.now(timezone.utc)

# 1. Seed Identity Service Database
identity_url = os.getenv("IDENTITY_DATABASE_URL")
print("Connecting to Identity DB...")
engine_ident = create_engine(identity_url)

with Session(engine_ident, expire_on_commit=False) as db:
    # Primary organization: aura-lab
    org = db.scalar(select(Organization).filter_by(slug="aura-lab"))
    if not org:
        org = Organization(
            name="Aura Precision Scientific Lab",
            slug="aura-lab",
            is_active=True,
            created_at=now - timedelta(days=90),
        )
        db.add(org)
        db.flush()
    org_id = org.id

    # Secondary slug alias: auralab
    org_alias = db.scalar(select(Organization).filter_by(slug="auralab"))
    if not org_alias:
        org_alias = Organization(
            name="Aura Lab Global",
            slug="auralab",
            is_active=True,
            created_at=now - timedelta(days=90),
        )
        db.add(org_alias)
        db.flush()
    org_alias_id = org_alias.id

    # 4 Dummy Users
    user_definitions = [
        ("sarah.chen@auralab.com", "Dr. Sarah Chen", "AuraLab2026!", "admin"),
        ("elena.rostova@auralab.com", "Dr. Elena Rostova", "AuraLab2026!", "member"),
        ("marcus.vance@auralab.com", "Marcus Vance", "AuraLab2026!", "member"),
        ("aria.tanaka@auralab.com", "Aria Tanaka", "AuraLab2026!", "member"),
    ]

    seeded_user_ids = {}
    for email, display_name, raw_pwd, role in user_definitions:
        user = db.scalar(select(User).filter_by(email=email))
        if not user:
            user = User(
                email=email,
                password_hash=hash_password(raw_pwd),
                display_name=display_name,
                is_active=True,
                email_verified_at=now - timedelta(days=60),
                created_at=now - timedelta(days=60),
            )
            db.add(user)
            db.flush()
        seeded_user_ids[email] = user.id

        for t_org_id in [org_id, org_alias_id]:
            membership = db.scalar(
                select(Membership).filter_by(organization_id=t_org_id, user_id=user.id)
            )
            if not membership:
                membership = Membership(
                    organization_id=t_org_id,
                    user_id=user.id,
                    role=role,
                    is_active=True,
                    created_at=now - timedelta(days=60),
                )
                db.add(membership)
                db.flush()

    db.commit()
    print(f"[OK] Identity: 4 users configured across organizations 'aura-lab' and 'auralab'.")

user_sarah_id = seeded_user_ids["sarah.chen@auralab.com"]
user_elena_id = seeded_user_ids["elena.rostova@auralab.com"]
user_marcus_id = seeded_user_ids["marcus.vance@auralab.com"]
user_aria_id = seeded_user_ids["aria.tanaka@auralab.com"]

# 2. Seed Projects Service Database
projects_url = os.getenv("PROJECTS_DATABASE_URL")
print("Connecting to Projects DB...")
engine_proj = create_engine(projects_url)

with Session(engine_proj, expire_on_commit=False) as db:
    for target_org_id in [org_id, org_alias_id]:
        p1 = db.scalar(select(Project).filter_by(organization_id=target_org_id, name="Kinase Inhibitor Synthesis & SAR Optimization"))
        if not p1:
            p1 = Project(
                organization_id=target_org_id,
                name="Kinase Inhibitor Synthesis & SAR Optimization",
                description="Discovery of novel selective quinazoline-based kinase inhibitors targeting mutant EGFR.",
                created_at=now - timedelta(days=45),
            )
            db.add(p1)
            db.flush()

        p2 = db.scalar(select(Project).filter_by(organization_id=target_org_id, name="CRISPR-Cas9 Biobank & Cryo Grid"))
        if not p2:
            p2 = Project(
                organization_id=target_org_id,
                name="CRISPR-Cas9 Biobank & Cryo Grid",
                description="Cryogenic biobanking of gene-edited knock-in and knock-out cell lines in 96-well format.",
                created_at=now - timedelta(days=30),
            )
            db.add(p2)
            db.flush()

        p3 = db.scalar(select(Project).filter_by(organization_id=target_org_id, name="Analytical HPLC Method Validation"))
        if not p3:
            p3 = Project(
                organization_id=target_org_id,
                name="Analytical HPLC Method Validation",
                description="Standardized HPLC and LC-MS reverse-phase chromatography gradient validation.",
                created_at=now - timedelta(days=15),
            )
            db.add(p3)
            db.flush()

        # Memberships for all 4 users
        for p in [p1, p2, p3]:
            for u_id, r in [(user_sarah_id, "owner"), (user_elena_id, "editor"), (user_marcus_id, "editor"), (user_aria_id, "viewer")]:
                pm = db.scalar(select(ProjectMembership).filter_by(organization_id=target_org_id, project_id=p.id, user_id=u_id))
                if not pm:
                    db.add(ProjectMembership(
                        organization_id=target_org_id,
                        project_id=p.id,
                        user_id=u_id,
                        role=r,
                    ))
        db.flush()

    db.commit()
    project_1_id = p1.id
    project_2_id = p2.id
    print("[OK] Projects: 3 laboratory projects seeded with permissions for all 4 users.")

# 3. Seed Notebook Service Database
notebook_url = os.getenv("NOTEBOOK_DATABASE_URL")
print("Connecting to Notebook DB...")
engine_note = create_engine(notebook_url)

with Session(engine_note, expire_on_commit=False) as db:
    for target_org_id in [org_id, org_alias_id]:
        # Locations Hierarchy: Room -> Freezer -> Box
        loc_room = db.scalar(select(StorageLocation).filter_by(organization_id=target_org_id, code="LOC-MAIN"))
        if not loc_room:
            loc_room = StorageLocation(
                organization_id=target_org_id,
                code="LOC-MAIN",
                name="Main Research Lab Room 402",
                location_type="room",
                description="Central analytical & synthesis laboratory",
                created_by_user_id=user_sarah_id,
                created_at=now - timedelta(days=60),
            )
            db.add(loc_room)
            db.flush()

        loc_freezer = db.scalar(select(StorageLocation).filter_by(organization_id=target_org_id, code="LOC-CRYO-01"))
        if not loc_freezer:
            loc_freezer = StorageLocation(
                organization_id=target_org_id,
                parent_id=loc_room.id,
                code="LOC-CRYO-01",
                name="CryoVault Ultra-Low Freezer (-80°C)",
                location_type="freezer",
                description="Primary cryogenic cell line biobank",
                created_by_user_id=user_sarah_id,
                created_at=now - timedelta(days=60),
            )
            db.add(loc_freezer)
            db.flush()

        loc_box = db.scalar(select(StorageLocation).filter_by(organization_id=target_org_id, code="BOX-B01"))
        if not loc_box:
            loc_box = StorageLocation(
                organization_id=target_org_id,
                parent_id=loc_freezer.id,
                code="BOX-B01",
                name="Cryogenic Storage Box 1 (96-Well)",
                location_type="box",
                description="96-well cryogenic storage box for clonal cell lines",
                created_by_user_id=user_sarah_id,
                created_at=now - timedelta(days=60),
            )
            db.add(loc_box)
            db.flush()

        # Reagent Inventory
        reagents = [
            ("Sodium Borohydride 98%", "Reducing Agent", "SBH-01", "LOT-9921", Decimal("250.0"), "g", Decimal("25.0")),
            ("Acetonitrile (HPLC Grade)", "Solvent", "ACN-02", "LOT-8410", Decimal("4000.0"), "mL", Decimal("500.0")),
            ("Trifluoroacetic Acid (TFA)", "Acid Additive", "TFA-03", "LOT-7731", Decimal("500.0"), "mL", Decimal("50.0")),
            ("EGFR Kinase Recombinant", "Protein Target", "EGFR-04", "LOT-6612", Decimal("10.0"), "mg", Decimal("2.0")),
        ]
        for name, cat, cat_no, lot, qty, unit, low in reagents:
            item = db.scalar(select(InventoryItem).filter_by(organization_id=target_org_id, catalog_number=cat_no))
            if not item:
                item = InventoryItem(
                    organization_id=target_org_id,
                    name=name,
                    category=cat,
                    catalog_number=cat_no,
                    lot_number=lot,
                    quantity=qty,
                    unit=unit,
                    low_stock_threshold=low,
                    location=loc_room.name,
                    location_id=loc_room.id,
                    status="active",
                    created_at=now - timedelta(days=50),
                    updated_at=now - timedelta(days=50),
                )
                db.add(item)
                db.flush()
                db.add(StockMovement(
                    organization_id=target_org_id,
                    item_id=item.id,
                    changed_by_user_id=user_sarah_id,
                    quantity_delta=qty,
                    resulting_quantity=qty,
                    reason="Initial stock receipt",
                    created_at=now - timedelta(days=50),
                ))
        db.flush()

        # 96-Well Grid Samples
        well_coords = [f"{r}{c}" for r in ["A", "B", "C"] for c in range(1, 13)]
        for coord in well_coords:
            ext_id = f"SMP-{coord}-2026"
            s = db.scalar(select(Sample).filter_by(organization_id=target_org_id, external_id=ext_id))
            if not s:
                db.add(Sample(
                    organization_id=target_org_id,
                    project_id=project_1_id,
                    created_by_user_id=user_marcus_id,
                    current_custodian_user_id=user_marcus_id,
                    name=f"Clone-HEK293-EGFR-L858R-{coord}",
                    sample_type="Cell Line",
                    external_id=ext_id,
                    storage_location_id=loc_box.id,
                    storage_location=f"Box-B01 ({coord})",
                    description=f"Cryopreserved clone at well position {coord}",
                    status="active",
                    created_at=now - timedelta(days=20),
                ))
        db.flush()

        # Equipment
        eq = db.scalar(select(EquipmentResource).filter_by(organization_id=target_org_id, name="Agilent 1290 Infinity II LC-MS"))
        if not eq:
            db.add(EquipmentResource(
                organization_id=target_org_id,
                name="Agilent 1290 Infinity II LC-MS",
                description="Ultra-high performance liquid chromatography with tandem mass spectrometry",
                storage_location_id=loc_room.id,
                location="Main Research Lab Room 402",
                status="operational",
                created_by_user_id=user_sarah_id,
                created_at=now - timedelta(days=50),
            ))
        db.flush()

        # Experiment & Entry
        exp = db.scalar(select(Experiment).filter_by(organization_id=target_org_id, name="EXP-001: Synthesis of 4-anilinoquinazoline EGFR inhibitors"))
        if not exp:
            exp = Experiment(
                organization_id=target_org_id,
                project_id=project_1_id,
                name="EXP-001: Synthesis of 4-anilinoquinazoline EGFR inhibitors",
                description="Multistep catalytic hydrogenation and nucleophilic substitution to yield target EGFR inhibitor analog 4c.",
                status="in_progress",
                created_at=now - timedelta(days=14),
            )
            db.add(exp)
            db.flush()

            entry_content = """# Synthesis of 4-Anilinoquinazoline (Analog 4c)

## Reaction Scheme
The reaction proceeds through a two-step sequence:
$$\\text{C}_8\\text{H}_5\\text{ClN}_2 + \\text{C}_6\\text{H}_7\\text{N} \\xrightarrow{\\text{i-PrOH, } 85^{\\circ}\\text{C}} \\text{C}_{14}\\text{H}_{11}\\text{N}_3 \\cdot \\text{HCl}$$

### Stoichiometry Table
| Compound | MW (g/mol) | Mass (g) | Mmol | Eq |
| :--- | :--- | :--- | :--- | :--- |
| 4-Chloroquinazoline | 164.59 | 1.65 g | 10.0 | 1.00 |
| 3-Ethynylaniline | 117.15 | 1.29 g | 11.0 | 1.10 |
| Isopropanol (solvent) | 60.10 | 25.0 mL | - | - |

## Observations & Yield
- The reaction reached completion within 3.5 hours as monitored by TLC (Hexane:EtOAc 1:1, Rf = 0.38).
- Final recrystallized yield: **2.14 g (87.2%)** as white needles.
- Purity confirmed by HPLC: **99.2% AUC** at $\\lambda = 254\\text{ nm}$.
"""
            db.add(NotebookEntry(
                experiment_id=exp.id,
                organization_id=target_org_id,
                title="Reaction Log & Stoichiometry: Analog 4c Synthesis",
                content=entry_content,
                created_at=now - timedelta(days=12),
            ))
            db.flush()

    db.commit()
    print("[OK] Notebook: Reagents, 96-well cryo grid samples, equipment, experiments & notebook entries seeded.")

# 4. Seed Activity Service Database
activity_url = os.getenv("ACTIVITY_DATABASE_URL")
print("Connecting to Activity DB...")
engine_act = create_engine(activity_url)

with Session(engine_act, expire_on_commit=False) as db:
    for target_org_id in [org_id, org_alias_id]:
        act = db.scalar(select(ActivityEvent).filter_by(organization_id=target_org_id))
        if not act:
            import uuid
            events = [
                ("identity", "user_logged_in", "user", user_sarah_id, {"email": "sarah.chen@auralab.com"}),
                ("projects", "project_created", "project", project_1_id, {"name": "Kinase Inhibitor Synthesis & SAR Optimization"}),
                ("notebook", "experiment_created", "experiment", exp.id, {"title": exp.name}),
                ("inventory", "stock_adjusted", "inventory_item", 1, {"item": "Sodium Borohydride 98%", "qty": "+250 g"}),
            ]
            for src, action, ent_type, ent_id, details in events:
                db.add(ActivityEvent(
                    event_id=f"evt_{uuid.uuid4().hex[:16]}",
                    organization_id=target_org_id,
                    source_service=src,
                    action=action,
                    entity_type=ent_type,
                    entity_id=ent_id,
                    occurred_at=now - timedelta(hours=2),
                    details=details,
                ))
            db.flush()
    db.commit()
    print("[OK] Activity: Audit trail and activity events seeded.")

print("\n" + "="*60)
print("ALL DATABASES SUCCESSFULLY MIGRATED AND POPULATED!")
print("="*60)
