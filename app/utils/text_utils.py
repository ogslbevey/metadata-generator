import re
import unicodedata

import logging 



logger= logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)




units=["km","m","cm","mm","kg","g","mg","l","ml","s","ms","h","min"]

def preprocess_text(text: str) -> str:
    # 1. remove accents
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text=text.lower()
    # 2. normalize spaces
    text = re.sub(r"\s+", " ", text)

    # 3. build unit pattern dynamically
    unit_pattern = "|".join(map(re.escape, units))

    # 4. match:
    #    - km [2]
    #    - g/m [2]
    #    - kg/m [2]
    pattern = rf"\b((?:{unit_pattern})(?:/(?:{unit_pattern}))?)\s*\[\s*(\d+)\s*\]"

    # 5. replace → unit2
    text = re.sub(pattern, r"\1\2", text)

    # 6. clean slashes spacing
    text = re.sub(r"\s*/\s*", "/", text)
    # remove punctuation
    text = re.sub(r"[^\w\s]", " ", text)

    # normalize spaces
    text = re.sub(r"\s+", " ", text)
    return text

