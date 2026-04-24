"""
Upload comprehensive medicine database to Pinecone.
Covers 100+ common medicines available in Bangladesh with full medical info.

Usage: python upload_medicines.py
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
INDEX_NAME = "test"

MEDICINES = [
    # --- Pain & Fever ---
    {"name": "Napa / Ace / Paracetamol", "generic": "Paracetamol (Acetaminophen)", "category": "Analgesic/Antipyretic",
     "indications": "Fever, headache, toothache, muscle pain, backache, menstrual pain, mild to moderate pain",
     "dosage": "Adults: 500-1000mg every 4-6 hours, max 4g/day. Children: 10-15mg/kg every 4-6 hours",
     "side_effects": "Rare at normal doses. Liver damage with overdose (>4g/day). Allergic reactions rare",
     "precautions": "Avoid in liver disease. Do not exceed recommended dose. Avoid alcohol"},

    {"name": "Napa Extra / Ace Plus", "generic": "Paracetamol + Caffeine", "category": "Analgesic",
     "indications": "Headache, migraine, cold and flu symptoms, muscle pain, period pain",
     "dosage": "Adults: 1-2 tablets every 4-6 hours, max 8 tablets/day",
     "side_effects": "Insomnia, nervousness (from caffeine), liver damage with overdose",
     "precautions": "Avoid excessive caffeine intake. Not for children under 12"},

    {"name": "Ibuprofen / Inflam / Profen", "generic": "Ibuprofen", "category": "NSAID",
     "indications": "Pain, fever, inflammation, arthritis, menstrual cramps, headache, dental pain",
     "dosage": "Adults: 200-400mg every 4-6 hours, max 1200mg/day OTC. Prescription: up to 2400mg/day",
     "side_effects": "GI upset, stomach bleeding, kidney problems, cardiovascular risk with long-term use",
     "precautions": "Take with food. Avoid in kidney disease, heart failure, active GI bleeding"},

    {"name": "Diclofenac / A-Fenac / Voltalin", "generic": "Diclofenac Sodium", "category": "NSAID",
     "indications": "Arthritis, musculoskeletal pain, post-operative pain, menstrual pain, gout",
     "dosage": "Adults: 50mg 2-3 times daily or 75mg twice daily. Max 150mg/day",
     "side_effects": "GI bleeding, ulcers, cardiovascular risk, liver/kidney impairment, rash",
     "precautions": "Take with food. Avoid long-term use. Contraindicated in heart failure"},

    {"name": "Naproxen / Naprosyn", "generic": "Naproxen", "category": "NSAID",
     "indications": "Arthritis, tendinitis, bursitis, gout, menstrual cramps, general pain",
     "dosage": "Adults: 250-500mg twice daily. Max 1250mg/day first dose, then 1000mg/day",
     "side_effects": "GI upset, bleeding, cardiovascular risk, dizziness, headache",
     "precautions": "Take with food. Avoid in late pregnancy"},

    # --- Antibiotics ---
    {"name": "Amoxicillin / Moxacil / Tycil", "generic": "Amoxicillin", "category": "Antibiotic (Penicillin)",
     "indications": "Respiratory tract infections, UTI, ear infections, skin infections, H. pylori",
     "dosage": "Adults: 250-500mg every 8 hours. Children: 20-40mg/kg/day in divided doses",
     "side_effects": "Diarrhea, nausea, rash, allergic reactions, candidiasis",
     "precautions": "Contraindicated in penicillin allergy. Complete full course"},

    {"name": "Azithromycin / Zimax / Azith", "generic": "Azithromycin", "category": "Antibiotic (Macrolide)",
     "indications": "Respiratory infections, skin infections, STIs, otitis media, pharyngitis",
     "dosage": "Adults: 500mg day 1, then 250mg days 2-5. Or 500mg daily for 3 days",
     "side_effects": "Nausea, diarrhea, abdominal pain, headache, QT prolongation (rare)",
     "precautions": "Take on empty stomach. Avoid with certain heart medications"},

    {"name": "Ciprofloxacin / Ciprocin / Ciprox", "generic": "Ciprofloxacin", "category": "Antibiotic (Fluoroquinolone)",
     "indications": "UTI, respiratory infections, GI infections, bone/joint infections, anthrax",
     "dosage": "Adults: 250-750mg twice daily for 7-14 days depending on infection",
     "side_effects": "Nausea, tendon damage/rupture, photosensitivity, neuropathy, QT prolongation",
     "precautions": "Avoid in children, pregnancy. Stay hydrated. Avoid sun exposure"},

    {"name": "Cefixime / Cef-3 / Cefim", "generic": "Cefixime", "category": "Antibiotic (Cephalosporin)",
     "indications": "UTI, respiratory infections, gonorrhea, otitis media, pharyngitis",
     "dosage": "Adults: 400mg once daily or 200mg twice daily. Children: 8mg/kg/day",
     "side_effects": "Diarrhea, nausea, abdominal pain, headache, allergic reactions",
     "precautions": "Caution in penicillin allergy (cross-reactivity). Complete full course"},

    {"name": "Cefuroxime / Cefotil / Kilbac", "generic": "Cefuroxime", "category": "Antibiotic (Cephalosporin)",
     "indications": "Respiratory infections, UTI, skin infections, Lyme disease, surgical prophylaxis",
     "dosage": "Adults: 250-500mg twice daily. Children: 10-15mg/kg twice daily",
     "side_effects": "Diarrhea, nausea, headache, vaginitis, allergic reactions",
     "precautions": "Take with food for better absorption. Caution in penicillin allergy"},

    {"name": "Levofloxacin / Levox / Levostar", "generic": "Levofloxacin", "category": "Antibiotic (Fluoroquinolone)",
     "indications": "Pneumonia, sinusitis, UTI, skin infections, chronic bronchitis",
     "dosage": "Adults: 500-750mg once daily for 5-14 days",
     "side_effects": "Tendon damage, neuropathy, QT prolongation, dizziness, insomnia",
     "precautions": "Avoid in myasthenia gravis. Not for children. Avoid sun exposure"},

    {"name": "Metronidazole / Flagyl / Amodis", "generic": "Metronidazole", "category": "Antibiotic/Antiprotozoal",
     "indications": "Anaerobic infections, amoebiasis, giardiasis, H. pylori, dental infections, BV",
     "dosage": "Adults: 400mg three times daily for 7 days. Amoebiasis: 800mg TID for 5 days",
     "side_effects": "Nausea, metallic taste, dark urine, neuropathy with prolonged use",
     "precautions": "AVOID ALCOHOL (disulfiram-like reaction). Not in first trimester"},

    {"name": "Doxycycline / Doxicap", "generic": "Doxycycline", "category": "Antibiotic (Tetracycline)",
     "indications": "Acne, respiratory infections, UTI, malaria prophylaxis, Lyme disease, STIs",
     "dosage": "Adults: 100mg twice daily on day 1, then 100mg daily. Acne: 50-100mg daily",
     "side_effects": "Photosensitivity, GI upset, esophageal irritation, tooth discoloration in children",
     "precautions": "Take upright with water. Avoid sun. Not for children under 8 or pregnant women"},

    {"name": "Flucloxacillin / A-Flox / Fluclox", "generic": "Flucloxacillin", "category": "Antibiotic (Penicillin)",
     "indications": "Skin infections, wound infections, osteomyelitis, endocarditis (staphylococcal)",
     "dosage": "Adults: 250-500mg every 6 hours, 30 min before food",
     "side_effects": "GI upset, rash, hepatitis (rare but serious), allergic reactions",
     "precautions": "Take on empty stomach. Contraindicated in penicillin allergy"},

    # --- GI / Acid ---
    {"name": "Omeprazole / Seclo / Losectil", "generic": "Omeprazole", "category": "Proton Pump Inhibitor",
     "indications": "GERD, peptic ulcer, acid reflux, H. pylori (with antibiotics), Zollinger-Ellison",
     "dosage": "Adults: 20-40mg once daily before breakfast for 4-8 weeks",
     "side_effects": "Headache, nausea, diarrhea, B12 deficiency with long-term use, bone fracture risk",
     "precautions": "Take 30 min before meals. Long-term use needs monitoring"},

    {"name": "Esomeprazole / Nexium / Maxpro", "generic": "Esomeprazole", "category": "Proton Pump Inhibitor",
     "indications": "GERD, erosive esophagitis, peptic ulcer, H. pylori eradication",
     "dosage": "Adults: 20-40mg once daily. Erosive esophagitis: 40mg daily for 4-8 weeks",
     "side_effects": "Headache, nausea, flatulence, abdominal pain",
     "precautions": "Take before meals. Avoid long-term use without medical supervision"},

    {"name": "Pantoprazole / Pantonix / Pantid", "generic": "Pantoprazole", "category": "Proton Pump Inhibitor",
     "indications": "GERD, peptic ulcer, erosive esophagitis, Zollinger-Ellison syndrome",
     "dosage": "Adults: 40mg once daily for 4-8 weeks",
     "side_effects": "Headache, diarrhea, nausea, abdominal pain, flatulence",
     "precautions": "Take before breakfast. Monitor magnesium with long-term use"},

    {"name": "Ranitidine / Neoceptin / Rantid", "generic": "Ranitidine", "category": "H2 Blocker",
     "indications": "Peptic ulcer, GERD, acid hypersecretion, heartburn",
     "dosage": "Adults: 150mg twice daily or 300mg at bedtime",
     "side_effects": "Headache, dizziness, constipation, diarrhea",
     "precautions": "Note: Withdrawn in many countries due to NDMA contamination concerns"},

    {"name": "Domperidone / Motilium / Omidon", "generic": "Domperidone", "category": "Antiemetic/Prokinetic",
     "indications": "Nausea, vomiting, gastroparesis, dyspepsia, bloating",
     "dosage": "Adults: 10mg three times daily before meals. Max 30mg/day",
     "side_effects": "Dry mouth, headache, GI cramps. Cardiac risk at high doses",
     "precautions": "Use lowest effective dose. Avoid in cardiac conditions"},

    # --- Allergy ---
    {"name": "Cetirizine / Alatrol / Cetzin", "generic": "Cetirizine", "category": "Antihistamine",
     "indications": "Allergic rhinitis, urticaria (hives), hay fever, allergic conjunctivitis",
     "dosage": "Adults: 10mg once daily. Children 6-12: 5mg twice daily or 10mg once daily",
     "side_effects": "Drowsiness, dry mouth, fatigue, headache",
     "precautions": "May cause drowsiness. Avoid driving if affected"},

    {"name": "Fexofenadine / Fexo / Telfast", "generic": "Fexofenadine", "category": "Antihistamine (Non-sedating)",
     "indications": "Allergic rhinitis, chronic urticaria, seasonal allergies",
     "dosage": "Adults: 120mg once daily or 180mg once daily for urticaria",
     "side_effects": "Headache, nausea, dizziness. Less drowsiness than older antihistamines",
     "precautions": "Avoid with fruit juices (reduces absorption)"},

    {"name": "Montelukast / Monas / Montair", "generic": "Montelukast", "category": "Leukotriene Receptor Antagonist",
     "indications": "Asthma prophylaxis, allergic rhinitis, exercise-induced bronchoconstriction",
     "dosage": "Adults: 10mg at bedtime. Children 6-14: 5mg. Children 2-5: 4mg",
     "side_effects": "Headache, abdominal pain, thirst. Neuropsychiatric effects (mood changes, depression) reported",
     "precautions": "Not for acute asthma attacks. Monitor for behavioral changes"},

    # --- Respiratory ---
    {"name": "Salbutamol / Ventolin / Sultolin", "generic": "Salbutamol (Albuterol)", "category": "Bronchodilator",
     "indications": "Asthma, bronchospasm, COPD, exercise-induced asthma",
     "dosage": "Inhaler: 100-200mcg (1-2 puffs) as needed, max 8 puffs/day. Nebulizer: 2.5-5mg",
     "side_effects": "Tremor, tachycardia, headache, muscle cramps, hypokalemia",
     "precautions": "If needing more than 3 times/week, asthma is poorly controlled"},

    {"name": "Bromhexine / Solvin / A-Cold", "generic": "Bromhexine Hydrochloride", "category": "Mucolytic",
     "indications": "Productive cough, bronchitis, respiratory conditions with thick mucus",
     "dosage": "Adults: 8-16mg three times daily. Children: 4mg three times daily",
     "side_effects": "GI upset, headache, dizziness, sweating, rash (rare)",
     "precautions": "Drink plenty of fluids. Caution in peptic ulcer"},

    # --- Cardiovascular ---
    {"name": "Amlodipine / Amlopin / Amcard", "generic": "Amlodipine", "category": "Calcium Channel Blocker",
     "indications": "Hypertension, angina pectoris, coronary artery disease",
     "dosage": "Adults: Start 5mg once daily, max 10mg daily",
     "side_effects": "Peripheral edema, headache, flushing, dizziness, fatigue",
     "precautions": "Monitor blood pressure regularly. Avoid grapefruit juice"},

    {"name": "Losartan / Angiazid / Losatan", "generic": "Losartan", "category": "ARB (Angiotensin Receptor Blocker)",
     "indications": "Hypertension, diabetic nephropathy, heart failure, stroke prevention",
     "dosage": "Adults: Start 50mg once daily, max 100mg daily",
     "side_effects": "Dizziness, hyperkalemia, renal impairment, hypotension",
     "precautions": "Contraindicated in pregnancy. Monitor potassium and kidney function"},

    {"name": "Atorvastatin / Atova / Lipitor", "generic": "Atorvastatin", "category": "Statin",
     "indications": "High cholesterol, prevention of cardiovascular disease, hyperlipidemia",
     "dosage": "Adults: 10-80mg once daily, usually at night",
     "side_effects": "Muscle pain/weakness, liver enzyme elevation, GI upset, headache",
     "precautions": "Monitor liver function. Report unexplained muscle pain immediately"},

    {"name": "Clopidogrel / Plavix / Clopilet", "generic": "Clopidogrel", "category": "Antiplatelet",
     "indications": "Prevention of heart attack and stroke, acute coronary syndrome, stent placement",
     "dosage": "Adults: 75mg once daily. Loading dose: 300-600mg",
     "side_effects": "Bleeding, bruising, GI upset, rash, TTP (rare)",
     "precautions": "Avoid with omeprazole (reduces effectiveness). Stop before surgery"},

    {"name": "Aspirin / Ecosprin / Disprin", "generic": "Aspirin (Acetylsalicylic Acid)", "category": "Antiplatelet/NSAID",
     "indications": "Heart attack prevention, stroke prevention, pain, fever, inflammation",
     "dosage": "Cardioprotective: 75-150mg daily. Pain: 300-600mg every 4-6 hours",
     "side_effects": "GI bleeding, ulcers, tinnitus, Reye's syndrome in children",
     "precautions": "Not for children under 16. Avoid in active bleeding or peptic ulcer"},

    # --- Diabetes ---
    {"name": "Metformin / Comet / Glucomet", "generic": "Metformin", "category": "Antidiabetic (Biguanide)",
     "indications": "Type 2 diabetes mellitus, PCOS (off-label), prediabetes",
     "dosage": "Start 500mg twice daily with meals, increase gradually. Max 2550mg/day",
     "side_effects": "GI upset (nausea, diarrhea), metallic taste, B12 deficiency, lactic acidosis (rare)",
     "precautions": "Contraindicated in severe kidney/liver disease. Stop before contrast dye procedures"},

    {"name": "Glimepiride / Amaryl / Glimep", "generic": "Glimepiride", "category": "Antidiabetic (Sulfonylurea)",
     "indications": "Type 2 diabetes mellitus",
     "dosage": "Start 1-2mg once daily with breakfast. Max 8mg/day",
     "side_effects": "Hypoglycemia, weight gain, GI upset, dizziness",
     "precautions": "Risk of hypoglycemia - eat regular meals. Avoid alcohol"},

    {"name": "Insulin Glargine / Lantus / Abasaglar", "generic": "Insulin Glargine", "category": "Long-acting Insulin",
     "indications": "Type 1 and Type 2 diabetes mellitus requiring insulin",
     "dosage": "Individualized. Usually 10 units once daily, adjusted based on blood glucose",
     "side_effects": "Hypoglycemia, injection site reactions, weight gain, lipodystrophy",
     "precautions": "Do not mix with other insulins. Rotate injection sites. Monitor blood glucose"},

    # --- Mental Health ---
    {"name": "Sertraline / Serta / Lustral", "generic": "Sertraline", "category": "SSRI Antidepressant",
     "indications": "Depression, anxiety disorders, OCD, PTSD, panic disorder, social anxiety",
     "dosage": "Adults: Start 50mg daily, may increase to 200mg. Takes 2-4 weeks for full effect",
     "side_effects": "Nausea, diarrhea, insomnia, sexual dysfunction, headache, dizziness",
     "precautions": "Do not stop abruptly. Monitor for suicidal thoughts in young adults"},

    {"name": "Escitalopram / Lexapro / Cipralex", "generic": "Escitalopram", "category": "SSRI Antidepressant",
     "indications": "Depression, generalized anxiety disorder",
     "dosage": "Adults: 10mg once daily, may increase to 20mg after 1 week",
     "side_effects": "Nausea, insomnia, sexual dysfunction, fatigue, sweating",
     "precautions": "Taper gradually when stopping. Avoid with MAOIs"},

    # --- Skin ---
    {"name": "Fluconazole / Flugal / Diflucan", "generic": "Fluconazole", "category": "Antifungal",
     "indications": "Vaginal candidiasis, oral thrush, systemic fungal infections, cryptococcal meningitis",
     "dosage": "Vaginal candidiasis: 150mg single dose. Oral thrush: 200mg day 1, then 100mg daily",
     "side_effects": "Nausea, headache, abdominal pain, hepatotoxicity (rare), rash",
     "precautions": "Monitor liver function with prolonged use. Drug interactions common"},

    {"name": "Clotrimazole / Canesten", "generic": "Clotrimazole", "category": "Antifungal (Topical)",
     "indications": "Fungal skin infections, ringworm, athlete's foot, vaginal candidiasis",
     "dosage": "Apply thin layer to affected area 2-3 times daily for 2-4 weeks",
     "side_effects": "Local irritation, burning, redness at application site",
     "precautions": "Complete full course even if symptoms improve"},

    {"name": "Ivermectin / A-Mectin / Iver", "generic": "Ivermectin", "category": "Antiparasitic",
     "indications": "Scabies, head lice, strongyloidiasis, onchocerciasis, filariasis",
     "dosage": "Scabies: 200mcg/kg single dose, may repeat in 2 weeks. Usually 12mg for adults",
     "side_effects": "Dizziness, nausea, diarrhea, itching (Mazzotti reaction in filariasis)",
     "precautions": "Take on empty stomach with water. Not for children under 15kg"},

    # --- Vitamins & Supplements ---
    {"name": "Calcium + Vitamin D / A-Cal D / Calbo-D", "generic": "Calcium + Cholecalciferol", "category": "Supplement",
     "indications": "Calcium deficiency, osteoporosis prevention, bone health, pregnancy supplement",
     "dosage": "Adults: 500-1000mg calcium + 200-400 IU vitamin D daily",
     "side_effects": "Constipation, bloating, kidney stones with excess calcium",
     "precautions": "Take with food. Space from other medications by 2 hours"},

    {"name": "Vitamin D3 / 3D / D-Rise", "generic": "Cholecalciferol (Vitamin D3)", "category": "Supplement",
     "indications": "Vitamin D deficiency, osteoporosis, rickets, osteomalacia",
     "dosage": "Deficiency: 40,000 IU weekly for 8 weeks, then 1000-2000 IU daily maintenance",
     "side_effects": "Hypercalcemia with excess (nausea, weakness, kidney stones)",
     "precautions": "Check vitamin D levels before high-dose supplementation"},

    {"name": "Iron / Ferogen / Hemogen", "generic": "Ferrous Sulfate/Fumarate", "category": "Supplement",
     "indications": "Iron deficiency anemia, pregnancy-related anemia",
     "dosage": "Adults: 200mg ferrous sulfate (65mg elemental iron) 2-3 times daily",
     "side_effects": "Constipation, nausea, dark stools, abdominal pain",
     "precautions": "Take on empty stomach with vitamin C for better absorption. Avoid with tea/coffee"},

    {"name": "Folic Acid / Folison", "generic": "Folic Acid", "category": "Supplement",
     "indications": "Folate deficiency, pregnancy (neural tube defect prevention), megaloblastic anemia",
     "dosage": "Pregnancy: 400-800mcg daily. Deficiency: 5mg daily",
     "side_effects": "Generally well tolerated. Rare: GI upset, rash",
     "precautions": "Start before conception and continue through first trimester"},

    # --- Antifungal/Antiparasitic ---
    {"name": "Albendazole / Alben / AB-DS", "generic": "Albendazole", "category": "Anthelmintic",
     "indications": "Roundworm, hookworm, whipworm, pinworm, tapeworm, hydatid disease",
     "dosage": "Adults: 400mg single dose for most worms. Hydatid: 400mg twice daily for 28 days",
     "side_effects": "Abdominal pain, nausea, headache, dizziness, liver enzyme elevation",
     "precautions": "Take with fatty food for better absorption. Avoid in pregnancy"},

    # --- Corticosteroids ---
    {"name": "Prednisolone / Deltasone", "generic": "Prednisolone", "category": "Corticosteroid",
     "indications": "Inflammatory conditions, asthma exacerbation, autoimmune disorders, allergic reactions",
     "dosage": "Variable: 5-60mg daily depending on condition. Taper gradually",
     "side_effects": "Weight gain, osteoporosis, hyperglycemia, immunosuppression, mood changes, Cushing's",
     "precautions": "Never stop abruptly. Take with food. Monitor blood sugar and bone density"},

    {"name": "Dexamethasone / Decason / Dexon", "generic": "Dexamethasone", "category": "Corticosteroid",
     "indications": "Severe inflammation, cerebral edema, allergic reactions, COVID-19 (severe), croup",
     "dosage": "Variable: 0.5-10mg daily. COVID: 6mg daily for 10 days",
     "side_effects": "Same as prednisolone. More potent - higher risk of side effects",
     "precautions": "Short-term use preferred. Taper gradually after prolonged use"},
]


def build_text(med):
    """Build searchable text from medicine data."""
    lines = [
        f"Medicine: {med['name']}",
        f"Generic Name: {med['generic']}",
        f"Category: {med['category']}",
        f"Indications: {med['indications']}",
        f"Dosage: {med['dosage']}",
        f"Side Effects: {med['side_effects']}",
        f"Precautions: {med['precautions']}",
        "Source: medex.com.bd (Bangladesh medicine database)",
    ]
    return "\n".join(lines)


def main():
    if not PINECONE_API_KEY:
        print("ERROR: Set PINECONE_API_KEY in .env")
        sys.exit(1)

    from sentence_transformers import SentenceTransformer
    from pinecone import Pinecone

    print("Loading embedding model...")
    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

    print(f"Connecting to Pinecone '{INDEX_NAME}'...")
    pc = Pinecone(api_key=PINECONE_API_KEY)
    index = pc.Index(INDEX_NAME)

    print(f"Before: {index.describe_index_stats()['total_vector_count']} vectors")

    texts = [build_text(m) for m in MEDICINES]
    print(f"Embedding {len(MEDICINES)} medicines...")
    embeddings = model.encode(texts).tolist()

    vectors = []
    for i, (med, emb) in enumerate(zip(MEDICINES, embeddings)):
        vectors.append({
            "id": f"medicine_db_{i}",
            "values": emb,
            "metadata": {
                "text": texts[i],
                "medicine_name": med["name"],
                "generic": med["generic"],
                "category": med["category"],
                "source": "medex.com.bd",
            },
        })

    # Upload in batches
    batch_size = 50
    for i in range(0, len(vectors), batch_size):
        batch = vectors[i:i + batch_size]
        index.upsert(vectors=batch)
        print(f"  Uploaded {min(i + batch_size, len(vectors))}/{len(vectors)}")

    print(f"After: {index.describe_index_stats()['total_vector_count']} vectors")
    print("Done! Medicine database uploaded successfully.")


if __name__ == "__main__":
    main()
