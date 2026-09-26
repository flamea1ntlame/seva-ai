"""
SEVA AI - Citizen Text Normalizer & Typo / Spelling Correction

Handles real-world citizen inputs:
- Spelling mistakes and typo correction ("birth certifcate" -> "birth certificate", "aadahr" -> "Aadhaar",
  "driving lisence" -> "driving licence", "scholership" -> "scholarship", "incom" -> "income")
- Abbreviations ("cert" -> "certificate", "dl" -> "driving licence", "id" -> "identity proof")
- Multilingual Indic phrase normalization (Devanagari & Kannada support).
- Does NOT mutate verbs/semantics (e.g. 'earning' is NOT mutated to 'income').
- Preserves native Unicode characters and stores original message untouched.
"""

import re
from typing import Dict, List, Tuple
from dataclasses import dataclass, field


# Multi-word phrase replacements (checked first, case-insensitive)
PHRASE_NORMALIZATIONS = [
    # English typos & synonyms
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
    (r"\bbrth\s+crt\b", "birth certificate"),
    (r"\bbirth\s+crt\b", "birth certificate"),
    (r"\bbrth\s+cert\b", "birth certificate"),
    (r"\bbrth\s+certificate\b", "birth certificate"),
    (r"\bincm\s+crt\b", "income certificate"),
    (r"\bincome\s+crt\b", "income certificate"),
    (r"\bjanma\s+praman\s+patra\b", "birth certificate"),
    (r"\baavadhi\s+praman\s+patra\b", "income certificate"),
    (r"\baaye\s+praman\s+patra\b", "income certificate"),
    (r"\baay\s+praman\s+patra\b", "income certificate"),
    
    # Native Devanagari script normalizations (preserve native characters while attaching service marker)
    (r"आय\s*प्रमाण\s*पत्र", "आय प्रमाण पत्र income certificate"),
    (r"आय\s*प्रमाणपत्र", "आय प्रमाण पत्र income certificate"),
    (r"जन्म\s*प्रमाण\s*पत्र", "जन्म प्रमाण पत्र birth certificate"),
    (r"जन्म\s*प्रमाणपत्र", "जन्म प्रमाण पत्र birth certificate"),
    (r"ड्राइविंग\s*लाइसेंस", "ड्राइविंग लाइसेंस driving licence"),
    (r"ड्राइविंग\s*लाइसेन्स", "ड्राइविंग लाइसेंस driving licence"),

    # Native Kannada script normalizations (preserve native characters while attaching service marker)
    (r"ಆದಾಯ\s*ಪ್ರಮಾಣ\s*ಪತ್ರ", "ಆದಾಯ ಪ್ರಮಾಣಪತ್ರ income certificate"),
    (r"ಆದಾಯ\s*ಪ್ರಮಾಣಪತ್ರ", "ಆದಾಯ ಪ್ರಮಾಣಪತ್ರ income certificate"),
    (r"ಜನನ\s*ಪ್ರಮಾಣ\s*ಪತ್ರ", "ಜನನ ಪ್ರಮಾಣಪತ್ರ birth certificate"),
    (r"ಜನನ\s*ಪ್ರಮಾಣಪತ್ರ", "ಜನನ ಪ್ರಮಾಣಪತ್ರ birth certificate"),
    (r"ಚಾಲನಾ\s*ಪರವಾನಗಿ", "ಚಾಲನಾ ಪರವಾನಗಿ driving licence"),
]

# Word-level typo and spelling mappings (strictly genuine typos, NO semantic mutations)
WORD_NORMALIZATIONS: Dict[str, str] = {
    # Income spelling errors (strictly typos, 'earning' removed)
    "incom": "income",
    "incme": "income",
    "incm": "income",
    "salery": "salary",
    
    # Birth variations
    "brth": "birth",

    # Certificate variations
    "certifcate": "certificate",
    "certficate": "certificate",
    "certificte": "certificate",
    "cerficate": "certificate",
    "certificat": "certificate",
    "cert": "certificate",
    "certs": "certificates",
    "crt": "certificate",
    "crts": "certificates",
    
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
    Normalizes citizen input string, correcting genuine typos and expanding abbreviations.
    Supports Unicode Indic scripts without discarding non-Latin characters.
    """
    if not text:
        return NormalizationResult(original_text="", normalized_text="", corrections={}, tokens=[])

    original = text
    working_text = text
    corrections: Dict[str, str] = {}

    # Step 1: Phrase replacements (includes Devanagari & Kannada)
    for pattern, replacement in PHRASE_NORMALIZATIONS:
        matches = re.findall(pattern, working_text, flags=re.IGNORECASE | re.UNICODE)
        if matches:
            for m in matches:
                if m.strip().lower() != replacement.lower():
                    corrections[m.strip()] = replacement
            working_text = re.sub(pattern, replacement, working_text, flags=re.IGNORECASE | re.UNICODE)

    # Step 2: Word-level normalization using Unicode word boundary
    words = re.findall(r"[\w-]+", working_text, flags=re.UNICODE)
    for word in words:
        w_lower = word.lower()
        if w_lower in WORD_NORMALIZATIONS:
            replacement = WORD_NORMALIZATIONS[w_lower]
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

            pattern = rf"\b{re.escape(word)}\b"
            working_text = re.sub(pattern, corrected, working_text, flags=re.UNICODE)

    # Step 3: Clean up whitespace while preserving Unicode script characters
    normalized_clean = re.sub(r"\s+", " ", working_text, flags=re.UNICODE).strip()
    tokens = [t.lower() for t in re.findall(r"[\w-]+", normalized_clean, flags=re.UNICODE)]

    return NormalizationResult(
        original_text=original,
        normalized_text=normalized_clean,
        corrections=corrections,
        tokens=tokens
    )
