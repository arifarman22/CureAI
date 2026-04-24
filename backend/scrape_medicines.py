import os
import re
import sys
import time
import argparse
import requests
from dotenv import load_dotenv

load_dotenv()

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
INDEX_NAME = "test"
BASE_URL = "https://medex.com.bd"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def clean(text):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text)).strip()


def get_brand_links(page=1):
    """Get medicine brand links from listing page."""
    try:
        r = requests.get(f"{BASE_URL}/brands?page={page}", headers=HEADERS, timeout=15)
        return list(set(re.findall(r'href="(https://medex\.com\.bd/brands/\d+/[^"]+)"', r.text)))
    except Exception as e:
        print(f"  Error on page {page}: {e}")
        return []


def scrape_medicine(url):
    """Extract medicine data from page title + meta description."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return None

        html = r.text

        # Title format: "BrandName | Strength | Form | Manufacturer | ..."
        title = re.search(r"<title>(.*?)</title>", html)
        if not title:
            return None
        title_text = clean(title.group(1))
        parts = [p.strip() for p in title_text.split("|")]

        name = parts[0] if parts else "Unknown"
        strength = parts[1] if len(parts) > 1 else ""
        form = parts[2] if len(parts) > 2 else ""

        # Meta description: "BrandName Form Strength is a product of Manufacturer. Its generic name is GenericName."
        desc = re.search(r'<meta name="description" content="(.*?)"', html)
        desc_text = desc.group(1) if desc else ""

        generic = ""
        manufacturer = ""
        if desc_text:
            g = re.search(r"generic name is (.+?)[\.\,]", desc_text, re.I)
            generic = g.group(1).strip() if g else ""
            m = re.search(r"product of (.+?)[\.\,]", desc_text, re.I)
            manufacturer = m.group(1).strip() if m else ""

        # Also try manufacturer from title
        if not manufacturer and len(parts) > 3:
            mfg_part = parts[3].strip()
            if "Indications" not in mfg_part:
                manufacturer = mfg_part

        if not name or name == "Unknown":
            return None

        # Build comprehensive medicine text
        text = f"Medicine: {name}"
        if strength:
            text += f" {strength}"
        if form:
            text += f" ({form})"
        if generic:
            text += f"\nGeneric Name: {generic}"
        if manufacturer:
            text += f"\nManufacturer: {manufacturer}"
        text += f"\nSource: medex.com.bd"
        text += f"\nURL: {url}"

        # Add generic-based medical info
        if generic:
            med_info = get_generic_info(generic.lower())
            if med_info:
                text += f"\n{med_info}"

        return {
            "name": name,
            "strength": strength,
            "form": form,
            "generic": generic,
            "manufacturer": manufacturer,
            "url": url,
            "text": text,
        }

    except Exception as e:
        print(f"  Error: {e}")
        return None


def get_generic_info(generic):
    """Return known medical info for common generics."""
    info = {
        "paracetamol": "Indications: Fever, mild to moderate pain, headache, toothache, backache, muscle pain. Dosage: Adults 500-1000mg every 4-6 hours, max 4g/day. Side Effects: Rare at normal doses. Liver damage with overdose.",
        "amoxicillin": "Indications: Bacterial infections - respiratory tract, urinary tract, skin, ear infections. Dosage: Adults 250-500mg every 8 hours. Side Effects: Diarrhea, nausea, rash. Contraindicated in penicillin allergy.",
        "azithromycin": "Indications: Respiratory infections, skin infections, STIs, otitis media. Dosage: 500mg day 1, then 250mg days 2-5. Side Effects: Nausea, diarrhea, abdominal pain.",
        "omeprazole": "Indications: GERD, peptic ulcer, acid reflux, Zollinger-Ellison syndrome. Dosage: 20-40mg once daily before meals. Side Effects: Headache, nausea, diarrhea.",
        "metformin": "Indications: Type 2 diabetes mellitus. Dosage: Start 500mg twice daily with meals, max 2550mg/day. Side Effects: GI upset, lactic acidosis (rare). Contraindicated in renal impairment.",
        "losartan": "Indications: Hypertension, diabetic nephropathy, heart failure. Dosage: 50-100mg once daily. Side Effects: Dizziness, hyperkalemia, renal impairment.",
        "amlodipine": "Indications: Hypertension, angina pectoris. Dosage: 5-10mg once daily. Side Effects: Edema, headache, flushing, dizziness.",
        "atorvastatin": "Indications: Hypercholesterolemia, prevention of cardiovascular disease. Dosage: 10-80mg once daily. Side Effects: Muscle pain, liver enzyme elevation.",
        "cetirizine": "Indications: Allergic rhinitis, urticaria, hay fever. Dosage: 10mg once daily. Side Effects: Drowsiness, dry mouth, fatigue.",
        "montelukast": "Indications: Asthma prophylaxis, allergic rhinitis. Dosage: Adults 10mg at bedtime. Side Effects: Headache, abdominal pain. Neuropsychiatric effects reported.",
        "ciprofloxacin": "Indications: UTI, respiratory infections, GI infections, bone/joint infections. Dosage: 250-750mg twice daily. Side Effects: Nausea, tendon damage, photosensitivity.",
        "diclofenac": "Indications: Pain, inflammation, arthritis, musculoskeletal disorders. Dosage: 50mg 2-3 times daily. Side Effects: GI bleeding, cardiovascular risk, renal impairment.",
        "ibuprofen": "Indications: Pain, fever, inflammation, arthritis. Dosage: 200-400mg every 4-6 hours, max 1200mg/day OTC. Side Effects: GI upset, bleeding risk.",
        "salbutamol": "Indications: Asthma, bronchospasm, COPD. Dosage: Inhaler 100-200mcg as needed. Side Effects: Tremor, tachycardia, headache.",
        "clopidogrel": "Indications: Prevention of atherosclerotic events, acute coronary syndrome. Dosage: 75mg once daily. Side Effects: Bleeding, bruising, GI upset.",
        "esomeprazole": "Indications: GERD, erosive esophagitis, peptic ulcer. Dosage: 20-40mg once daily. Side Effects: Headache, nausea, flatulence.",
        "pantoprazole": "Indications: GERD, peptic ulcer, Zollinger-Ellison syndrome. Dosage: 40mg once daily. Side Effects: Headache, diarrhea, nausea.",
        "ranitidine": "Indications: Peptic ulcer, GERD, acid hypersecretion. Dosage: 150mg twice daily or 300mg at bedtime. Note: Withdrawn in many countries due to NDMA contamination.",
        "doxycycline": "Indications: Bacterial infections, acne, malaria prophylaxis, Lyme disease. Dosage: 100mg twice daily. Side Effects: Photosensitivity, GI upset, esophageal irritation.",
        "fluconazole": "Indications: Fungal infections - candidiasis, cryptococcal meningitis. Dosage: 150mg single dose for vaginal candidiasis, 200-400mg daily for systemic. Side Effects: Nausea, headache, hepatotoxicity.",
        "prednisolone": "Indications: Inflammatory conditions, autoimmune disorders, allergic reactions, asthma. Dosage: Variable, 5-60mg daily. Side Effects: Weight gain, osteoporosis, hyperglycemia, immunosuppression.",
        "metronidazole": "Indications: Anaerobic bacterial infections, protozoal infections, H. pylori. Dosage: 400mg three times daily. Side Effects: Nausea, metallic taste, disulfiram-like reaction with alcohol.",
        "levofloxacin": "Indications: Respiratory infections, UTI, skin infections. Dosage: 500-750mg once daily. Side Effects: Tendon damage, neuropathy, QT prolongation.",
        "cefixime": "Indications: UTI, respiratory infections, gonorrhea, otitis media. Dosage: 400mg once daily or 200mg twice daily. Side Effects: Diarrhea, nausea, abdominal pain.",
        "cefuroxime": "Indications: Respiratory infections, UTI, skin infections, Lyme disease. Dosage: 250-500mg twice daily. Side Effects: Diarrhea, nausea, headache.",
        "domperidone": "Indications: Nausea, vomiting, gastroparesis, dyspepsia. Dosage: 10mg three times daily before meals. Side Effects: Dry mouth, headache. Cardiac risk at high doses.",
        "fexofenadine": "Indications: Allergic rhinitis, chronic urticaria. Dosage: 120-180mg once daily. Side Effects: Headache, drowsiness (less than older antihistamines).",
        "bromhexine hydrochloride": "Indications: Productive cough, bronchitis, respiratory conditions with thick mucus. Dosage: 8-16mg three times daily. Side Effects: GI upset, headache, dizziness.",
        "calcium": "Indications: Calcium deficiency, osteoporosis prevention, hypoparathyroidism. Dosage: 500-1000mg daily. Side Effects: Constipation, bloating, kidney stones with excess.",
        "iron": "Indications: Iron deficiency anemia. Dosage: 100-200mg elemental iron daily. Side Effects: Constipation, nausea, dark stools.",
        "vitamin d": "Indications: Vitamin D deficiency, osteoporosis, rickets. Dosage: 1000-4000 IU daily. Side Effects: Hypercalcemia with excess.",
    }

    for key, val in info.items():
        if key in generic:
            return val
    return ""


def upload_to_pinecone(medicines):
    """Embed and upload medicine data to Pinecone."""
    if not medicines:
        print("No data to upload.")
        return

    from sentence_transformers import SentenceTransformer
    from pinecone import Pinecone

    print("Loading embedding model...")
    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

    print(f"Connecting to Pinecone '{INDEX_NAME}'...")
    pc = Pinecone(api_key=PINECONE_API_KEY)
    index = pc.Index(INDEX_NAME)

    batch_size = 50
    uploaded = 0

    for i in range(0, len(medicines), batch_size):
        batch = medicines[i:i + batch_size]
        texts = [m["text"] for m in batch]
        embeddings = model.encode(texts).tolist()

        vectors = []
        for j, (med, emb) in enumerate(zip(batch, embeddings)):
            vid = f"medex_{i + j}_{abs(hash(med['name'])) % 100000}"
            vectors.append({
                "id": vid,
                "values": emb,
                "metadata": {
                    "text": med["text"][:1000],
                    "medicine_name": med["name"],
                    "generic": med.get("generic", ""),
                    "source": "medex.com.bd",
                },
            })

        index.upsert(vectors=vectors)
        uploaded += len(batch)
        print(f"  Uploaded {uploaded}/{len(medicines)}")

    stats = index.describe_index_stats()
    print(f"\nDone! Total vectors in index: {stats['total_vector_count']}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pages", type=int, default=5, help="Pages to scrape (30 medicines/page)")
    args = parser.parse_args()

    if not PINECONE_API_KEY:
        print("ERROR: Set PINECONE_API_KEY in .env")
        sys.exit(1)

    print(f"=== MedEx Medicine Scraper ===")
    print(f"Scraping {args.pages} pages...\n")

    all_links = []
    for p in range(1, args.pages + 1):
        print(f"Page {p}...")
        links = get_brand_links(p)
        all_links.extend(links)
        print(f"  Found {len(links)} links")
        time.sleep(0.5)

    all_links = list(set(all_links))
    print(f"\nTotal unique links: {len(all_links)}")

    medicines = []
    for i, link in enumerate(all_links):
        slug = link.split("/")[-1]
        print(f"[{i + 1}/{len(all_links)}] {slug}")
        med = scrape_medicine(link)
        if med:
            medicines.append(med)
            print(f"  -> {med['name']} ({med['generic'] or 'no generic'})")
        time.sleep(0.3)

    print(f"\nScraped {len(medicines)} medicines successfully")

    if medicines:
        upload_to_pinecone(medicines)


if __name__ == "__main__":
    main()
