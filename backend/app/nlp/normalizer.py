"""
SEVA AI - Citizen Text Normalizer & Typo / Spelling Correction

Handles real-world citizen inputs:
- Spelling mistakes and typo correction ("birth certifcate" -> "birth certificate", "aadahr" -> "Aadhaar",
  "driving lisence" -> "driving licence", "scholership" -> "scholarship", "incom" -> "income")
- Abbreviations ("cert" -> "certificate", "dl" -> "driving licence", "id" -> "identity proof")
- Informal language and phonetic misspellings.
- Keeps original user message stored for audit/debugging.
"""

import re
from typing import Dict, List, Tuple
from dataclasses import dataclass, field


# Multi-word phrase replacements (checked first, case-insensitive)
PHRASE_NORMALIZATIONS = [
    (r"\bbirth\s+certifcate\b", "birth certificate"),
    (r"\bbirth\s+cert\b", "birth certificate"),
    (r"\bbirth\s+cerficate\b", "birth certificate"),
    (r"\bincom\s+certificate\b", "income certificate"),
    (r"\bincom\s+certficate\b", "income certificate"),
    (r"\bincom\s+cert\b", "income certificate"),
    (r"\bincome\s+cert\b", "income certificate"),
    (r"\bdriving\s+lisence\b", "driving licence"),
    (r"\bdriving\s+license\b", "driving licence"),
    (r"\bdriver\s+license\b", "driving licence"),
    (r"\bdriver\'?s\s+license\b", "driving licence"),
    (r"\bdriver\'?s\s+licence\b", "driving licence"),
    (r"\blearning\s+licence\b", "learner licence"),
    (r"\blearning\s+license\b", "learner licence"),
    (r"\bnew\s+born\b", "newborn"),
    (r"\bjanma\s+praman\s+patra\b", "birth certificate"),
    (r"\baavadhi\s+praman\s+patra\b", "income certificate"),
    (r"\baaye\s+praman\s+patra\b", "income certificate"),
    (r"\baay\s+praman\s+patra\b", "income certificate"),
]

# Word-level typo and synonym mappings (regex matched on word boundaries)
WORD_NORMALIZATIONS: Dict[str, str] = {
    # Income & Money
    "incom": "income",
    "incme": "income",
    "incm": "income",
    "salery": "salary",
    "earning": "income",
    "earnings": "income",
    
    # Certificate variations
    "certifcate": "certificate",
    "certficate": "certificate",
    "certificte": "certificate",
    "cerficate": "certificate",
    "certificat": "certificate",
    "cert": "certificate",
    "certs": "certificates",
    
    # Scholarship variations
    "scholership": "scholarship",
    "scholarshipp": "scholarship",
    "scholorship": "scholarship",
    "skolarship": "scholarship",
    "scholorships": "scholarships",
    "scholerships": "scholarships",

    # Identity Documents
    "aadahr": "Aadhaar",
    "adharr": "Aadhaar",
    "aadhar": "Aadhaar",
    "adhaar": "Aadhaar",
    "adar": "Aadhaar",
    "adhar": "Aadhaar",
    "aaddhar": "Aadhaar",
    "pancard": "PAN card",
    "pan": "PAN",
    "voterid": "Voter ID",
    "rationcard": "ration card",

    # Licence variations
    "lisence": "licence",
    "license": "licence",
    "licens": "licence",
    "licnse": "licence",
    "lisenc": "licence",
    "dl": "driving licence",

    # Birth & Family
    "newborns": "newborn",
    "famly": "family",
    "familly": "family",
    "childs": "child",

    # General government words
    "documnts": "documents",
    "documnt": "document",
    "doc": "document",
    "docs": "documents",
    "pappers": "papers",
    "paprs": "papers",
    "proov": "proof",
    "proff": "proof",
    "prooff": "proof",
    "aply": "apply",
    "aplying": "applying",
    "aplication": "application",
    "applicaton": "application",
    "aplications": "applications",
    "submitt": "submit",
    "submision": "submission",
    "submited": "submitted",
    "goverment": "government",
    "gov": "government",
    "govt": "government",
    "requirments": "requirements",
    "requirment": "requirement",
    "requird": "required",
    "requred": "required",
    "req": "requirement",
    "reqs": "requirements",
    "verifaction": "verification",
    "verfy": "verify",
}


@dataclass
class NormalizationResult:
    original_text: str
    normalized_text: str
    corrections: Dict[str, str] = field(default_factory=dict)
    tokens: List[str] = field(default_factory=list)


def normalize_text(text: str) -> NormalizationResult:
    """
    Normalizes a citizen input string, correcting typos, expanding abbreviations,
    and tracking every applied transformation for auditing.
    """
    if not text:
        return NormalizationResult(original_text="", normalized_text="", corrections={}, tokens=[])

    original = text
    working_text = text
    corrections: Dict[str, str] = {}

    # Step 1: Phrase replacements
    for pattern, replacement in PHRASE_NORMALIZATIONS:
        matches = re.findall(pattern, working_text, flags=re.IGNORECASE)
        if matches:
            for m in matches:
                if m.lower() != replacement.lower():
                    corrections[m.strip()] = replacement
            working_text = re.sub(pattern, replacement, working_text, flags=re.IGNORECASE)

    # Step 2: Word-level normalization
    # Tokenize while preserving word structures and SEVA references
    words = re.findall(r"\b[A-Za-z0-9_-]+\b", working_text)
    for word in words:
        w_lower = word.lower()
        if w_lower in WORD_NORMALIZATIONS:
            replacement = WORD_NORMALIZATIONS[w_lower]
            # Preserve capitalization style if proper noun like Aadhaar / PAN
            if replacement in ["Aadhaar", "PAN", "Voter ID"]:
                corrected = replacement
            elif word.isupper():
                corrected = replacement.upper()
            elif word[0].isupper():
                corrected = replacement.capitalize()
            else:
                corrected = replacement.lower()

            if word != corrected and w_lower != corrected.lower():
                corrections[word] = corrected

            # Replace using regex boundary
            pattern = rf"\b{re.escape(word)}\b"
            working_text = re.sub(pattern, corrected, working_text)

    # Step 3: Clean up excess whitespace
    normalized_clean = re.sub(r"\s+", " ", working_text).strip()
    tokens = [t.lower() for t in re.findall(r"\b[A-Za-z0-9_-]+\b", normalized_clean)]

    return NormalizationResult(
        original_text=original,
        normalized_text=normalized_clean,
        corrections=corrections,
        tokens=tokens
    )
