import os

SEED_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "seed")
os.makedirs(SEED_DIR, exist_ok=True)


def generate_seed_documents():
    print("📄 Generating sample seed documents in backend/seed/...")

    docs = {
        "sample_identity_proof.txt": """GOVERNMENT OF INDIA - UNIQUE IDENTIFICATION AUTHORITY
------------------------------------------------------
Name: Rahul Kumar
Date of Birth: 2004-07-14
Gender: Male
Address: 45 MG Road, Indiranagar, Bengaluru, Karnataka - 560038
Aadhaar Number: AADHAAR-8839-2049-1122
------------------------------------------------------
Verified Government Photo Identity Card
""",
        "sample_income_proof.txt": """DEPARTMENT OF REVENUE - ANNUAL INCOME CERTIFICATE
------------------------------------------------------
Employee Name: Rahul Kumar
Employer: Tech Solutions Pvt Ltd
Designation: Software Engineer
Annual Gross Salary: Rs. 4,50,000.00
Assessment Year: 2025-2026
------------------------------------------------------
Official Revenue Stamp & Signature
""",
        "sample_address_proof.txt": """BANGALORE ELECTRICITY SUPPLY COMPANY (BESCOM)
UTILITY BILL & RESIDENCY PROOF
------------------------------------------------------
Consumer Name: Rahul Kumar
Service Address: 45 MG Road, Indiranagar, Bengaluru, Karnataka - 560038
Account ID: 9812-4019-2210
Status: ACTIVE & PAID
------------------------------------------------------
""",
        "sample_hospital_certificate.txt": """CITY GOVERNANCE HOSPITAL - CERTIFICATE OF BIRTH
------------------------------------------------------
Child Name: Aarav Kumar
Date of Birth: 2024-01-10
Place of Birth: City Governance Hospital, Bengaluru
Father's Name: Rahul Kumar
Mother's Name: Priya Kumar
Registration No: HOSP-BIRTH-2024-09812
------------------------------------------------------
""",
        "sample_medical_declaration.txt": """DEPARTMENT OF TRANSPORT - MEDICAL FITNESS DECLARATION
------------------------------------------------------
Applicant Name: Rahul Kumar
Date of Birth: 2004-07-14
Blood Group: O+
Vision Test: Normal (6/6)
Physical Fitness: CONFIRMED FIT FOR MOTOR VEHICLE DRIVING
Medical Officer: Dr. S. K. Sharma (Reg # MED-88192)
------------------------------------------------------
""",
    }

    for filename, content in docs.items():
        file_path = os.path.join(SEED_DIR, filename)
        with open(file_path, "w") as f:
            f.write(content)
        print(f"  └─ Created: backend/seed/{filename}")

    print("✅ All seed sample documents generated successfully!")


if __name__ == "__main__":
    generate_seed_documents()
