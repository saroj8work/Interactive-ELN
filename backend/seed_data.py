"""
Seed script to populate a rich, realistic, domain-specific scientific dataset
for the Interactive Electronic Laboratory Notebook (ELN).
Compatible with both PostgreSQL and in-memory/file-based SQLite test databases.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib

from sqlalchemy import select
from sqlalchemy.orm import Session

from eln_common.database import Base, Database
from services.identity.app.models import (
    Organization,
    User,
    Membership,
)
from services.identity.app.security import hash_password
from services.projects.app.models import (
    Project,
    ProjectMembership,
)
from services.notebook.app.models import (
    Experiment,
    NotebookEntry,
    AuditEvent,
    RecordSignature,
    InventoryItem,
    InventoryCustomFieldDefinition,
    StockMovement,
    Sample,
    SampleCustodyTransfer,
    NotebookTemplate,
    EquipmentResource,
    EquipmentBooking,
    LabTask,
    StorageLocation,
)
from services.activity.app.models import (
    ActivityEvent,
    Notification,
    WebhookEndpoint,
)


def seed_database(db: Session) -> dict[str, int]:
    """
    Seeds the complete laboratory dataset into the active session.
    Returns a dictionary of created entity record counts.
    """
    now = datetime.now(timezone.utc)

    # 1. Organization
    org = db.scalar(select(Organization).filter_by(slug="biosynth"))
    if not org:
        org = Organization(
            name="BioSynth Discovery Institute",
            slug="biosynth",
            is_active=True,
            created_at=now - timedelta(days=120),
        )
        db.add(org)
        db.flush()

    org_id = org.id

    # 2. Users & Memberships
    users_data = [
        ("dr.elena.rostova@biosynth.org", "Dr. Elena Rostova", "ElenaLab#2026!", "admin"),
        ("marcus.vance@biosynth.org", "Marcus Vance", "MarcusLab#2026!", "member"),
        ("sarah.chen@biosynth.org", "Sarah Chen", "SarahQA#2026!", "member"),
    ]

    users = {}
    for email, display_name, password, role in users_data:
        user = db.scalar(select(User).filter_by(email=email))
        if not user:
            user = User(
                email=email,
                display_name=display_name,
                password_hash=hash_password(password),
                is_active=True,
                email_verified_at=now - timedelta(days=100),
                created_at=now - timedelta(days=100),
            )
            db.add(user)
            db.flush()
            # Membership
            membership = Membership(
                organization_id=org_id,
                user_id=user.id,
                role=role,
                is_active=True,
                created_at=now - timedelta(days=100),
            )
            db.add(membership)
            db.flush()
        users[email] = user

    elena = users["dr.elena.rostova@biosynth.org"]
    marcus = users["marcus.vance@biosynth.org"]
    sarah = users["sarah.chen@biosynth.org"]

    # 3. Projects & Project Memberships
    projects_info = [
        ("Kinase Inhibitor Optimization & Synthesis", "Development of potent, selective small-molecule ATP-competitive tyrosine kinase inhibitors."),
        ("CRISPR-Cas9 Gene Editing Screening in Hepatocytes", "Targeted knockout of lipogenic regulator genes in primary human hepatocytes."),
        ("Preclinical Pharmacokinetics & ADMET Profiling", "Assessing metabolic stability, CYP450 inhibition, and pharmacokinetic parameters."),
    ]

    projects = {}
    for p_name, p_desc in projects_info:
        proj = db.scalar(select(Project).filter_by(organization_id=org_id, name=p_name))
        if not proj:
            proj = Project(
                organization_id=org_id,
                name=p_name,
                description=p_desc,
                created_at=now - timedelta(days=90),
            )
            db.add(proj)
            db.flush()
            # Roles: Elena owner, Marcus editor, Sarah viewer
            db.add(ProjectMembership(organization_id=org_id, project_id=proj.id, user_id=elena.id, role="owner"))
            db.add(ProjectMembership(organization_id=org_id, project_id=proj.id, user_id=marcus.id, role="editor"))
            db.add(ProjectMembership(organization_id=org_id, project_id=proj.id, user_id=sarah.id, role="viewer"))
            db.flush()
        projects[p_name] = proj

    p_kinase = projects["Kinase Inhibitor Optimization & Synthesis"]
    p_crispr = projects["CRISPR-Cas9 Gene Editing Screening in Hepatocytes"]

    # 4. Storage Locations (Hierarchy)
    loc_room = db.scalar(select(StorageLocation).filter_by(organization_id=org_id, code="ROOM-402"))
    if not loc_room:
        loc_room = StorageLocation(
            organization_id=org_id,
            created_by_user_id=elena.id,
            code="ROOM-402",
            name="Main Wet Chemistry Lab (Room 402)",
            location_type="room",
            parent_id=None,
            description="Central analytical and synthetic chemistry lab suite",
        )
        db.add(loc_room)
        db.flush()

    loc_freezer = db.scalar(select(StorageLocation).filter_by(organization_id=org_id, code="FRZ-CRYO-03"))
    if not loc_freezer:
        loc_freezer = StorageLocation(
            organization_id=org_id,
            created_by_user_id=elena.id,
            code="FRZ-CRYO-03",
            name="-80°C Ultra-Low CryoVault 3",
            location_type="freezer",
            parent_id=loc_room.id,
            description="Ultra-low temperature cryogenic sample repository",
        )
        db.add(loc_freezer)
        db.flush()

    loc_rack = db.scalar(select(StorageLocation).filter_by(organization_id=org_id, code="RCK-A"))
    if not loc_rack:
        loc_rack = StorageLocation(
            organization_id=org_id,
            created_by_user_id=elena.id,
            code="RCK-A",
            name="Freezer Rack A (Upper Tier)",
            location_type="shelf",
            parent_id=loc_freezer.id,
            description="Primary storage rack for cellular isolates",
        )
        db.add(loc_rack)
        db.flush()

    loc_box = db.scalar(select(StorageLocation).filter_by(organization_id=org_id, code="BOX-B01"))
    if not loc_box:
        loc_box = StorageLocation(
            organization_id=org_id,
            created_by_user_id=elena.id,
            code="BOX-B01",
            name="9x9 Cryo Box B-01 (Plate/Box Grid)",
            location_type="box",
            parent_id=loc_rack.id,
            description="81-well cryovial box for hepatocyte clones and small molecule leads",
        )
        db.add(loc_box)
        db.flush()

    loc_cabinet = db.scalar(select(StorageLocation).filter_by(organization_id=org_id, code="CAB-FLAM-1"))
    if not loc_cabinet:
        loc_cabinet = StorageLocation(
            organization_id=org_id,
            created_by_user_id=elena.id,
            code="CAB-FLAM-1",
            name="Flammable Solvents Cabinet 1",
            location_type="cabinet",
            parent_id=loc_room.id,
            description="Certified fire-rated chemical storage cabinet",
        )
        db.add(loc_cabinet)
        db.flush()

    # 5. Inventory Custom Field Definitions
    fields_data = [
        ("CAS Number", "text", False, []),
        ("Purity %", "number", False, []),
        ("Supplier", "text", False, []),
        ("SMILES Structure", "text", False, []),
    ]
    for f_name, f_type, f_req, f_opts in fields_data:
        cf = db.scalar(select(InventoryCustomFieldDefinition).filter_by(organization_id=org_id, name=f_name))
        if not cf:
            cf = InventoryCustomFieldDefinition(
                organization_id=org_id,
                created_by_user_id=elena.id,
                name=f_name,
                field_type=f_type,
                required=f_req,
                options=f_opts,
                status="active",
                created_at=now - timedelta(days=60),
            )
            db.add(cf)
            db.flush()

    # 6. Inventory Items
    inv_items_data = [
        ("Sodium Borohydride", "Reducing Agent", "SBH-01", "LOT-9921", Decimal("250.0"), "g", Decimal("25.0"), "Flammable Solvents Cabinet 1", loc_cabinet.id,
         {"CAS Number": "16940-66-2", "Purity %": "98.5", "Supplier": "Sigma-Aldrich", "SMILES Structure": "[BH4-].[Na+]"}),
        ("4-Bromobenzaldehyde", "Building Block", "BBA-02", "LOT-8410", Decimal("100.0"), "g", Decimal("15.0"), "Shelf 2", loc_room.id,
         {"CAS Number": "1122-91-4", "Purity %": "99.0", "Supplier": "Enamine", "SMILES Structure": "O=Cc1ccc(Br)cc1"}),
        ("Phenylboronic Acid", "Organoboron", "PBA-03", "LOT-7731", Decimal("50.0"), "g", Decimal("10.0"), "Shelf 2", loc_room.id,
         {"CAS Number": "98-80-6", "Purity %": "98.0", "Supplier": "Combi-Blocks", "SMILES Structure": "OB(O)c1ccccc1"}),
        ("Tetrakis(triphenylphosphine)palladium(0)", "Catalyst", "PD-TET-04", "LOT-6612", Decimal("15.0"), "g", Decimal("2.0"), "CryoVault-3", loc_freezer.id,
         {"CAS Number": "14221-01-3", "Purity %": "99.5", "Supplier": "Strem Chemicals", "SMILES Structure": "c1ccccc1P(c2ccccc2)(c3ccccc3)[Pd]"}),
        ("Potassium Carbonate", "Base", "PC-05", "LOT-5541", Decimal("500.0"), "g", Decimal("50.0"), "Main Bench", loc_room.id,
         {"CAS Number": "584-08-7", "Purity %": "99.0", "Supplier": "Fisher Scientific"}),
        ("1,4-Dioxane (Anhydrous)", "Solvent", "DIOX-06", "LOT-4419", Decimal("1000.0"), "mL", Decimal("200.0"), "Flammable Solvents Cabinet 1", loc_cabinet.id,
         {"CAS Number": "123-91-1", "Purity %": "99.8", "Supplier": "Acros Organics", "SMILES Structure": "C1COCCO1"}),
    ]

    inventory = {}
    for name, cat, cat_no, lot, qty, unit, low, loc_name, loc_id, cfields in inv_items_data:
        item = db.scalar(select(InventoryItem).filter_by(organization_id=org_id, catalog_number=cat_no))
        if not item:
            item = InventoryItem(
                organization_id=org_id,
                name=name,
                category=cat,
                catalog_number=cat_no,
                lot_number=lot,
                quantity=qty,
                unit=unit,
                low_stock_threshold=low,
                location=loc_name,
                location_id=loc_id,
                notes=f"Analytical standard grade {name}",
                custom_fields=cfields,
                status="active",
                created_at=now - timedelta(days=50),
                updated_at=now - timedelta(days=50),
            )
            db.add(item)
            db.flush()
            # Initial stock movement
            db.add(StockMovement(
                organization_id=org_id,
                item_id=item.id,
                changed_by_user_id=elena.id,
                quantity_delta=qty,
                resulting_quantity=qty,
                reason="Initial inventory receipt and qualification",
                created_at=now - timedelta(days=50),
            ))
            db.flush()
        inventory[name] = item

    # 7. Samples & Aliquots
    samples_data = [
        ("Primary Human Hepatocyte Cell Line Alpha", "Cell Culture", "SMP-1001", p_crispr.id, None, "Box-B01 (A1)", loc_box.id, elena.id, marcus.id, "Passage 4 primary hepatocytes with validated viability > 95%."),
        ("CRISPR Knockout Clone B4", "Cell Line", "SMP-1002", p_crispr.id, None, "Box-B01 (B2)", loc_box.id, elena.id, marcus.id, "Validated biallelic indel target confirmed by Sanger sequencing."),
        ("Kinase Inhibitor Lead Compound BS-8042", "Chemical Compound", "SMP-1003", p_kinase.id, None, "Box-B01 (C3)", loc_box.id, elena.id, elena.id, "Purified Suzuki coupling product (MW: 236.27 g/mol, white solid)."),
        ("Plasma PK Sample Day 7 Post-Dose", "Biological Specimen", "SMP-1004", p_kinase.id, None, "Box-B01 (D4)", loc_box.id, elena.id, sarah.id, "Mouse plasma collected at t = 168h post oral administration."),
    ]

    samples = {}
    for s_name, s_type, ext_id, proj_id, parent_id, loc_s, loc_id, creator, custodian, desc in samples_data:
        smp = db.scalar(select(Sample).filter_by(organization_id=org_id, external_id=ext_id))
        if not smp:
            smp = Sample(
                organization_id=org_id,
                created_by_user_id=creator,
                current_custodian_user_id=custodian,
                name=s_name,
                sample_type=s_type,
                external_id=ext_id,
                project_id=proj_id,
                parent_sample_id=parent_id,
                storage_location=loc_s,
                storage_location_id=loc_id,
                description=desc,
                status="active",
                created_at=now - timedelta(days=40),
            )
            db.add(smp)
            db.flush()
        samples[ext_id] = smp

    # Set parent on SMP-1002
    if "SMP-1001" in samples and "SMP-1002" in samples:
        samples["SMP-1002"].parent_sample_id = samples["SMP-1001"].id
        db.flush()

    # 8. Experiments & Notebook Entries
    exp1 = db.scalar(select(Experiment).filter_by(organization_id=org_id, name="Palladium-Catalyzed Suzuki-Miyaura Cross-Coupling for Lead BS-8042"))
    if not exp1:
        exp1 = Experiment(
            organization_id=org_id,
            project_id=p_kinase.id,
            name="Palladium-Catalyzed Suzuki-Miyaura Cross-Coupling for Lead BS-8042",
            description="Synthesis of biaryl kinase inhibitor core via Suzuki cross-coupling reaction.",
            status="completed",
            created_at=now - timedelta(days=30),
            updated_at=now - timedelta(days=2),
        )
        db.add(exp1)
        db.flush()

        # Entry 1
        e1 = NotebookEntry(
            organization_id=org_id,
            experiment_id=exp1.id,
            title="Reaction Setup & In-Situ Monitoring",
            content=(
                "Coupling executed under inert argon atmosphere using [@4-Bromobenzaldehyde](#inv:2) "
                "(5.0 mmol, 925 mg) and [@Phenylboronic Acid](#inv:3) (6.0 mmol, 731 mg) catalyzed by "
                "[@Tetrakis(triphenylphosphine)palladium(0)](#inv:4) (0.1 mmol, 115 mg) and base [@Potassium Carbonate](#inv:5) "
                "(12.5 mmol, 1.73 g) in 30 mL anhydrous [@1,4-Dioxane (Anhydrous)](#inv:6) / water (4:1).\n\n"
                "Kinetics observed follow pseudo-first order rate expression:\n"
                "$$r = -\\frac{d[ArBr]}{dt} = k_{obs} [ArBr]$$\n"
                "$$k_{obs} = A e^{-\\frac{E_a}{RT}}$$\n\n"
                "Reaction progress sampled every 30 minutes via analytical HPLC. Complete conversion achieved at t = 3.5 h.\n\n"
                "Isolated material assigned to registered sample record [#Kinase Inhibitor Lead Compound BS-8042](#smp:3)."
            ),
            created_at=now - timedelta(days=28),
            updated_at=now - timedelta(days=28),
        )
        db.add(e1)
        db.flush()

        # 21 CFR Part 11 Electronic Signature by Author (Elena)
        e1_digest = hashlib.sha256(e1.content.encode("utf-8")).hexdigest()
        sig1 = RecordSignature(
            organization_id=org_id,
            entity_type="notebook_entry",
            entity_id=e1.id,
            signed_by_user_id=elena.id,
            meaning="authored",
            comment="I confirm the data accuracy and methodology as lead investigator.",
            record_sha256=e1_digest,
            previous_hash="0" * 64,
            event_hash=hashlib.sha256(f"{elena.id}:authored:{e1_digest}".encode("utf-8")).hexdigest(),
            created_at=now - timedelta(days=27),
        )
        db.add(sig1)

        # 21 CFR Part 11 Electronic Signature by QA Reviewer (Sarah)
        sig2 = RecordSignature(
            organization_id=org_id,
            entity_type="notebook_entry",
            entity_id=e1.id,
            signed_by_user_id=sarah.id,
            meaning="reviewed",
            comment="QA review complete. Conforms to Good Laboratory Practice standard SOP-CH-04.",
            record_sha256=e1_digest,
            previous_hash=sig1.event_hash,
            event_hash=hashlib.sha256(f"{sarah.id}:reviewed:{e1_digest}".encode("utf-8")).hexdigest(),
            created_at=now - timedelta(days=26),
        )
        db.add(sig2)

        # Entry 2
        e2 = NotebookEntry(
            organization_id=org_id,
            experiment_id=exp1.id,
            title="Chromatographic Purification & Isolated Yield Analysis",
            content=(
                "The reaction mixture was filtered through celite, extracted with ethyl acetate (3 x 40 mL), "
                "dried over anhydrous Na2SO4, and concentrated under reduced pressure.\n\n"
                "Purified by automated silica flash column chromatography (gradient 0-25% EtOAc/Hexanes).\n"
                "Isolated mass: 802.4 mg (Theoretical yield: 917.9 mg -> Isolated yield = 87.4%).\n\n"
                "1H-NMR (400 MHz, CDCl3): 10.06 (s, 1H, CHO), 7.97 (d, J = 8.4 Hz, 2H), 7.76 (d, J = 8.4 Hz, 2H), "
                "7.65 (d, J = 7.2 Hz, 2H), 7.49 (t, J = 7.4 Hz, 2H), 7.42 (t, J = 7.2 Hz, 1H).\n"
                "Conforms with pure 4-phenylbenzaldehyde core."
            ),
            created_at=now - timedelta(days=25),
            updated_at=now - timedelta(days=25),
        )
        db.add(e2)
        db.flush()

        # Audit events for exp1
        import json
        audit1 = AuditEvent(
            organization_id=org_id,
            entity_type="experiment",
            entity_id=exp1.id,
            actor_user_id=elena.id,
            action="experiment_created",
            payload_json=json.dumps({"name": exp1.name, "project_id": str(p_kinase.id)}),
            previous_hash="0" * 64,
            event_hash=hashlib.sha256(f"{exp1.id}:created".encode("utf-8")).hexdigest(),
            created_at=now - timedelta(days=30),
        )
        db.add(audit1)
        db.flush()

        audit2 = AuditEvent(
            organization_id=org_id,
            entity_type="notebook_entry",
            entity_id=e1.id,
            actor_user_id=elena.id,
            action="entry_signed",
            payload_json=json.dumps({"meaning": "authored", "signer": elena.email}),
            previous_hash=audit1.event_hash,
            event_hash=hashlib.sha256(f"{e1.id}:sig1".encode("utf-8")).hexdigest(),
            created_at=now - timedelta(days=27),
        )
        db.add(audit2)
        db.flush()

    exp2 = db.scalar(select(Experiment).filter_by(organization_id=org_id, name="In Vitro Kinase Assay & IC50 Profiling"))
    if not exp2:
        exp2 = Experiment(
            organization_id=org_id,
            project_id=p_kinase.id,
            name="In Vitro Kinase Assay & IC50 Profiling",
            description="Fluorescent enzymatic kinase inhibition curve determination.",
            status="in_progress",
            created_at=now - timedelta(days=14),
            updated_at=now - timedelta(days=1),
        )
        db.add(exp2)
        db.flush()

        e3 = NotebookEntry(
            organization_id=org_id,
            experiment_id=exp2.id,
            title="Dose-Response IC50 Protocol & Assay Execution",
            content=(
                "Enzymatic inhibition of recombinant tyrosine kinase evaluated in 384-well black microplate format.\n"
                "Compound BS-8042 tested at 10-point concentrations (0.1 nM to 10 uM) in triplicate.\n\n"
                "Enzyme kinetics modeled under standard steady-state formulation:\n"
                "$$V = \\frac{V_{max}[S]}{K_m + [S]}$$\n"
                "$$Y = \\text{Bottom} + \\frac{\\text{Top} - \\text{Bottom}}{1 + 10^{(\\log IC_{50} - X) \\cdot \\text{HillSlope}}}$$\n\n"
                "Fitted IC50: 4.8 nM (R^2 = 0.994). Excellent selectivity over counter-screen panel."
            ),
            created_at=now - timedelta(days=10),
            updated_at=now - timedelta(days=10),
        )
        db.add(e3)
        db.flush()

        # Lab Tasks
        db.add(LabTask(
            organization_id=org_id,
            project_id=p_kinase.id,
            experiment_id=exp2.id,
            created_by_user_id=elena.id,
            assigned_to_user_id=marcus.id,
            title="Perform duplicate IC50 assay with batch #2",
            description="Verify reproducibility across fresh kinase aliquot.",
            due_at=now + timedelta(days=3),
            priority="high",
            status="in_progress",
        ))
        db.flush()

    # 9. Equipment Resources & Bookings
    equip_data = [
        ("Agilent 1290 Infinity II UHPLC System", "Chromatography", "EQ-UHPLC-01", "Room 402, Bench 3", "active"),
        ("Thermo Scientific Orbitrap Exploris 240 MS", "Mass Spectrometry", "EQ-MS-02", "Room 402, MS Bay 1", "active"),
        ("Beckman Coulter Allegra X-30R Refrigerated Centrifuge", "Centrifuge", "EQ-CENT-03", "Room 402, Prep Bay", "active"),
    ]

    for eq_name, eq_cat, eq_code, eq_loc, eq_stat in equip_data:
        eq = db.scalar(select(EquipmentResource).filter_by(organization_id=org_id, name=eq_name))
        if not eq:
            eq = EquipmentResource(
                organization_id=org_id,
                created_by_user_id=elena.id,
                name=eq_name,
                description=f"Standard laboratory resource: {eq_name}",
                storage_location_id=loc_room.id,
                location=eq_loc,
                category=eq_cat,
                status=eq_stat,
                created_at=now - timedelta(days=60),
            )
            db.add(eq)
            db.flush()
            # Scheduled calibration booking
            db.add(EquipmentBooking(
                organization_id=org_id,
                equipment_id=eq.id,
                booked_by_user_id=elena.id,
                project_id=p_kinase.id,
                starts_at=now + timedelta(days=1, hours=9),
                ends_at=now + timedelta(days=1, hours=11),
                purpose="Weekly Instrument Performance Qualification & QC",
                status="reserved",
                created_at=now - timedelta(days=2),
            ))
            db.flush()

    # 10. Notebook Templates
    template = db.scalar(select(NotebookTemplate).filter_by(organization_id=org_id, name="Synthetic Organic Reaction Protocol"))
    if not template:
        template = NotebookTemplate(
            organization_id=org_id,
            created_by_user_id=elena.id,
            name="Synthetic Organic Reaction Protocol",
            description="Standard GLP template for multistep organic synthesis reactions",
            template_kind="entry",
            sections=[
                "1. Reaction Objective & Hypothesis",
                "2. Chemical Reaction Scheme & SMILES",
                "3. Reagents & Stoichiometry Table",
                "4. Safety & Hazards (GHS)",
                "5. Experimental Procedure & Observation Log",
                "6. Workup, Isolation & Purification",
                "7. Analytical Characterization (NMR, LC-MS, HPLC)",
            ],
            created_at=now - timedelta(days=50),
        )
        db.add(template)
        db.flush()

    # 11. Activity Events
    activity_events = [
        ("identity", "user_logged_in", "user", elena.id, {"email": elena.email, "ip": "127.0.0.1"}),
        ("projects", "project_created", "project", p_kinase.id, {"name": p_kinase.name}),
        ("notebook", "entry_signed", "notebook_entry", 1, {"signer": elena.email, "meaning": "authored"}),
        ("inventory", "stock_adjusted", "inventory_item", 1, {"item": "Sodium Borohydride", "qty": "+250.0 g"}),
    ]
    import uuid
    for src, action, ent_type, ent_id, details in activity_events:
        db.add(ActivityEvent(
            event_id=f"evt_{uuid.uuid4().hex[:16]}",
            organization_id=org_id,
            source_service=src,
            action=action,
            entity_type=ent_type,
            entity_id=ent_id,
            occurred_at=now - timedelta(hours=5),
            details=details,
        ))
    db.flush()

    db.commit()

    return {
        "organizations": db.query(Organization).count(),
        "users": db.query(User).count(),
        "projects": db.query(Project).count(),
        "storage_locations": db.query(StorageLocation).count(),
        "inventory_items": db.query(InventoryItem).count(),
        "samples": db.query(Sample).count(),
        "experiments": db.query(Experiment).count(),
        "notebook_entries": db.query(NotebookEntry).count(),
        "equipment": db.query(EquipmentResource).count(),
    }


if __name__ == "__main__":
    import os
    from eln_common.config import required_postgresql_url
    
    pg_url = os.getenv("NOTEBOOK_DATABASE_URL")
    if pg_url:
        db_inst = Database(pg_url)
        with db_inst.session() as session:
            counts = seed_database(session)
            print("Successfully seeded PostgreSQL database:")
            for k, v in counts.items():
                print(f"  {k}: {v}")
    else:
        # SQLite test demonstration
        db_inst = Database("sqlite://", allow_sqlite_for_tests=True)
        Base.metadata.create_all(bind=db_inst.engine)
        with db_inst.session() as session:
            counts = seed_database(session)
            print("Successfully seeded test database:")
            for k, v in counts.items():
                print(f"  {k}: {v}")
