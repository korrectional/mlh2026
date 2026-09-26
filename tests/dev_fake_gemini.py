"""Dev-only: run Study Buddy with canned Gemini responses (no API calls). python tests/dev_fake_gemini.py → localhost:8001"""
import asyncio, json, os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); os.chdir(ROOT)
import routers.study_buddy as sb

QUIZ = {"title": "BIO 181: Chemistry of Life & Membranes", "questions": [
    {"question": "Why are unsaturated fats usually liquid at room temperature?", "options": ["They have more hydrogen atoms", "Cis double bonds kink their tails, preventing tight packing", "They form ionic bonds with water", "They contain cholesterol"], "correct_index": 1, "topic": "Lipid Chemistry"},
    {"question": "What drives phospholipids to form a bilayer in water?", "options": ["Covalent bonds between heads", "Ionic bonds between tails", "The hydrophobic effect", "Hydrogen bonds between tails"], "correct_index": 2, "topic": "Bilayer Formation"},
    {"question": "How does cholesterol act as a fluidity buffer?", "options": ["It restrains movement when warm and prevents packing when cold", "It pumps water out of the cell", "It converts cis bonds to trans", "It only works at high temperature"], "correct_index": 0, "topic": "Cholesterol"},
    {"question": "Which molecule crosses the bilayer most easily without a protein?", "options": ["Glucose", "Na+ ions", "O2", "Large proteins"], "correct_index": 2, "topic": "Selective Permeability"},
    {"question": "Why does ice float on liquid water?", "options": ["Ice is more dense", "Hydrogen bonds lock molecules into a spaced lattice", "Ice contains trapped air", "Covalent bonds lengthen when frozen"], "correct_index": 1, "topic": "Properties of Water"}]}


def q(question, options, correct, why):
    return {"question": question, "options": options, "correct_index": correct, "explanation": why}

CONCEPTS = {"title": "BIO 181: Chemistry of Life", "concepts": [
    {"id": "c3", "name": "Hydrophobic Effect", "summary": "Why nonpolar molecules cluster in water.", "difficulty": 2, "key_terms": ["hydrophobic", "hydrophilic", "nonpolar"], "prerequisites": ["c2"],
     "lesson": "Water molecules hydrogen-bond with each other. Nonpolar molecules can't join that network, so water pushes them together to minimize disruption. No bond forms between the nonpolar molecules; it's water's own attraction doing the work. Example: oil droplets merging in salad dressing.",
     "check": q("What drives nonpolar tails together in water?", ["Covalent bonds between tails", "Water's hydrogen-bond network excluding them", "Ionic attraction", "Gravity"], 1, "Water maximizes its hydrogen bonds by excluding nonpolar molecules."),
     "review": q("Oil and water separate mainly because...", ["Oil is denser", "Water molecules prefer bonding with each other", "Oil is ionic", "They react chemically"], 1, "Water's cohesion excludes nonpolar oil.")},
    {"id": "c1", "name": "Chemical Bonds", "summary": "How atoms share or transfer electrons.", "difficulty": 1, "key_terms": ["covalent", "ionic", "electronegativity", "hydrogen bond"], "prerequisites": [],
     "lesson": "Atoms bond through valence electrons. Covalent bonds share electrons, ionic bonds transfer them, and hydrogen bonds are weak attractions between a slightly positive hydrogen and a slightly negative oxygen or nitrogen. Example: table salt is ionic; the O-H in water is polar covalent.",
     "check": q("Which bond transfers electrons completely?", ["Covalent", "Ionic", "Hydrogen", "Van der Waals"], 1, "Ionic bonds form when one atom gives electrons to another."),
     "review": q("A hydrogen bond is...", ["A strong covalent bond", "A weak attraction between partial charges", "An ionic bond", "A metallic bond"], 1, "It's an attraction, not shared electrons.")},
    {"id": "c2", "name": "Polarity of Water", "summary": "Water's uneven charge and its effects.", "difficulty": 1, "key_terms": ["polar", "partial charge"], "prerequisites": ["c1"],
     "lesson": "Oxygen pulls shared electrons harder than hydrogen, so water has a slightly negative oxygen end and slightly positive hydrogen ends. That polarity lets water dissolve salts and form hydrogen bonds. Example: salt crystals falling apart in water.",
     "check": q("Why is water polar?", ["Oxygen pulls electrons more strongly than hydrogen", "It is ionic", "It has no electrons", "It is nonpolar"], 0, "Unequal sharing creates partial charges."),
     "review": q("Water dissolves salt because...", ["It is nonpolar", "Its partial charges surround the ions", "It forms covalent bonds with salt", "Salt is hydrophobic"], 1, "Partial charges attract and separate the ions.")},
    {"id": "c4", "name": "Phospholipid Bilayer", "summary": "How membranes assemble.", "difficulty": 2, "key_terms": ["phospholipid", "amphipathic", "bilayer", "head", "tail"], "prerequisites": ["c3"],
     "lesson": "Phospholipids have a hydrophilic head and two hydrophobic tails. In water, tails hide inside and heads face out on both sides, forming a bilayer. Example: every cell membrane in your body.",
     "check": q("In a bilayer, where do the tails point?", ["Toward the water", "Toward each other inside", "Outside the cell only", "Randomly"], 1, "Tails avoid water by facing each other."),
     "review": q("Phospholipids are amphipathic, meaning...", ["Fully polar", "Fully nonpolar", "Part hydrophilic, part hydrophobic", "Charged"], 2, "Head loves water, tails avoid it.")},
    {"id": "c5", "name": "Membrane Fluidity", "summary": "Temperature, saturation, and cholesterol.", "difficulty": 3, "key_terms": ["saturated", "unsaturated", "cholesterol", "fluidity buffer", "cis double bond", "packing"], "prerequisites": ["c4"],
     "lesson": "Membranes must stay fluid. Kinked unsaturated tails pack loosely and keep membranes fluid in the cold; cholesterol restrains movement when warm and prevents tight packing when cold. Example: fish in icy water have more unsaturated fats in their membranes.",
     "check": q("A fish moves to colder water. Its membranes adapt by...", ["More saturated fats", "More unsaturated fats", "Removing all cholesterol", "Removing proteins"], 1, "Kinks prevent tight packing in the cold."),
     "review": q("Cholesterol's role in membranes is to...", ["Only increase fluidity", "Buffer fluidity in both directions", "Pump water", "Form covalent bonds"], 1, "It resists change both ways.")},
    {"id": "c6", "name": "Selective Permeability", "summary": "What crosses the membrane on its own.", "difficulty": 2, "key_terms": ["permeability", "aquaporin", "nonpolar"], "prerequisites": ["c4"],
     "lesson": "The hydrophobic core lets small nonpolar molecules like O2 through but blocks ions and large polar molecules, which need transport proteins. Water mostly crosses through aquaporins. Example: glucose needs a transporter to enter a cell.",
     "check": q("Which crosses the bilayer without help?", ["Glucose", "Na+", "O2", "Proteins"], 2, "Small nonpolar molecules slip through the core."),
     "review": q("Water mostly crosses membranes through...", ["The lipid core", "Aquaporins", "Ion pumps only", "Endocytosis"], 1, "Aquaporins are water channels.")}]}

async def fake_json(**kw):
    await asyncio.sleep(3)
    return json.dumps(CONCEPTS if 'core concepts' in kw.get('prompt', '') else QUIZ)

async def fake_explain(**kw):
    await asyncio.sleep(1)
    return ("It makes sense to think bonds hold the bilayer together, since the structure is so stable. "
            "But no bonds form between the lipids at all. Water molecules hydrogen-bond with each other, and the "
            "nonpolar tails get pushed together because they can't join that network. That's the hydrophobic effect.")

def install():
    sb.ask_gemini_json = fake_json
    sb.ask_gemini = fake_explain


if __name__ == "__main__":
    install()
    from main import app
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001, log_level="warning")
