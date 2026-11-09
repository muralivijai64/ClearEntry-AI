from app.database import Base, engine, SessionLocal
from app.models import User, Shipment
from app.security import hash_password

Base.metadata.create_all(bind=engine)

db = SessionLocal()

try:
    # Create demo users only if they do not already exist
    executive = db.query(User).filter(
        User.email == "executive@clearentry.ai"
    ).first()

    if not executive:
        executive = User(
            name="Demo Executive",
            email="executive@clearentry.ai",
            password_hash=hash_password("Executive@123"),
            role="executive"
        )
        db.add(executive)

    manager = db.query(User).filter(
        User.email == "manager@clearentry.ai"
    ).first()

    if not manager:
        manager = User(
            name="Demo Manager",
            email="manager@clearentry.ai",
            password_hash=hash_password("Manager@123"),
            role="manager"
        )
        db.add(manager)

    # Create sample shipments
    shipment_one = db.query(Shipment).filter(
        Shipment.shipment_number == "SHP-24811"
    ).first()

    if not shipment_one:
        shipment_one = Shipment(
            shipment_number="SHP-24811",
            importer="Company A",
            supplier="Company B",
            origin_country="China",
            status="Awaiting Documents"
        )
        db.add(shipment_one)

    shipment_two = db.query(Shipment).filter(
        Shipment.shipment_number == "SHP-24812"
    ).first()

    if not shipment_two:
        shipment_two = Shipment(
            shipment_number="SHP-24812",
            importer="Company A",
            supplier="Company C",
            origin_country="Sweden",
            status="Awaiting Documents"
        )
        db.add(shipment_two)

    db.commit()

    print("Database setup completed!")
    print("Demo users and sample shipments created.")

finally:
    db.close()