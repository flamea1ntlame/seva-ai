import asyncio
import sys
from datetime import date
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models import User, CitizenProfile, Service
from app.auth import get_password_hash


async def seed_data():
    async with AsyncSessionLocal() as db:
        print("🌱 Starting database seed...")

        # 1. Check or Create Demo Citizen User
        result = await db.execute(select(User).where(User.email == "citizen@example.com"))
        user = result.scalar_one_or_none()

        if not user:
            user = User(
                email="citizen@example.com",
                password_hash=get_password_hash("password123"),
                full_name="Ramesh Kumar",
                phone_number="+919876543210",
                role="citizen",
                is_active=True,
            )
            db.add(user)
            await db.flush()

            profile = CitizenProfile(
                user_id=user.id,
                dob=date(1990, 5, 15),
                gender="male",
                address="123 Gandhi Road, Indiranagar",
                state="Karnataka",
                pincode="560038",
                income_annual=350000.00,
                category="General",
            )
            db.add(profile)
            print("✅ Created demo citizen: citizen@example.com / password123")
        else:
            print("ℹ️ Demo citizen already exists.")

        # 2. Seed/Update Exactly 3 Services per Phase 2 spec
        services_to_seed = [
            {
                "code": "income_certificate",
                "title": "Income Certificate",
                "department": "revenue",
                "description": "Official certificate verifying annual family income for welfare schemes and scholarships.",
                "required_documents": ["identity_proof", "address_proof", "income_proof"],
                "required_fields": ["annual_income", "occupation"],
                "processing_time_days": 7,
                "fee_amount": 50.00,
            },
            {
                "code": "birth_certificate",
                "title": "Birth Certificate",
                "department": "municipal",
                "description": "Official record of birth registration issued by local municipal governance authority.",
                "required_documents": ["hospital_certificate", "parent_identity_proof"],
                "required_fields": ["applicant_name", "date_of_birth", "place_of_birth", "father_name", "mother_name"],
                "processing_time_days": 5,
                "fee_amount": 30.00,
            },
            {
                "code": "driving_license",
                "title": "Driving License",
                "department": "transport",
                "description": "Official authorization to drive motor vehicles on public roads.",
                "required_documents": ["identity_proof", "address_proof", "photograph", "medical_declaration"],
                "required_fields": ["date_of_birth", "blood_group", "vehicle_class"],
                "processing_time_days": 14,
                "fee_amount": 200.00,
            },
        ]

        for s_data in services_to_seed:
            res = await db.execute(select(Service).where(Service.code == s_data["code"]))
            service = res.scalar_one_or_none()
            if not service:
                service = Service(
                    code=s_data["code"],
                    title=s_data["title"],
                    department=s_data["department"],
                    description=s_data["description"],
                    required_documents=s_data["required_documents"],
                    required_fields=s_data["required_fields"],
                    processing_time_days=s_data["processing_time_days"],
                    fee_amount=s_data["fee_amount"],
                    is_active=True,
                )
                db.add(service)
                print(f"✅ Created service: {s_data['code']}")
            else:
                service.department = s_data["department"]
                service.required_documents = s_data["required_documents"]
                service.required_fields = s_data["required_fields"]
                print(f"ℹ️ Updated service spec: {s_data['code']}")

        await db.commit()
        print("🚀 Seeding completed successfully!")


if __name__ == "__main__":
    asyncio.run(seed_data())
