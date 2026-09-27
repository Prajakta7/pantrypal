"""Word handling shared by pantry, recipe and recall matching."""
import re

# Words that describe packaging or state, not the food itself
GENERIC = {
    "organic", "fresh", "frozen", "baby", "whole", "large", "small", "medium", "raw", "natural",
    "original", "classic", "premium", "canned", "can", "cans", "jar", "bag", "box", "bottle", "pack",
    "cooked", "dried", "roasted", "toasted", "soaked", "chopped", "sliced", "diced", "boneless", "skinless", "plain", "low", "fat",
    "free", "reduced", "style", "brand", "the", "and", "with", "for", "per", "net", "wt", "count",
    "size", "family", "value", "oz", "lb", "lbs", "ct", "pound", "ounce", "ounces", "pint",
    # packaging and labels that follow a product name in recall notices
    "clamshell", "tray", "carton", "pouch", "container", "package", "packaged", "bulk", "case",
    "upc", "lot", "code", "sku", "item", "product", "products", "retail", "each", "unit",
}
# Words describing the form of the same food ("spinach, cut leaf"), not a different product
FORM = {"powder", "seed", "cut", "leaf", "chopped", "shredded", "fillet", "piece", "floret", "halve", "half", "stick", "slice",
        "block", "crumble", "wedge", "loaf", "bunch", "head", "dozen", "grade", "jumbo", "extra"}
KEEP_S = ("ss", "us", "is", "ous")
# Alternative names → one name, so "Haldi" in your pantry covers "turmeric" in a recipe.
# Keys are regular expressions (matched as whole words, optional plural "s"); longer phrases first.
SYNONYMS = {
    # English variants
    "scallion": "green onion", "spring onion": "green onion", "garbanzo": "chickpea", "capsicum": "bell pepper",
    "courgette": "zucchini", "brinjal": "eggplant", "aubergine": "eggplant", "lady ?finger": "okra",
    "chill?(?:i|ie|e)": "chili", "masoor dal": "red lentil", "masoor": "red lentil", "gram flour": "besan", "chickpea flour": "besan",
    "fresh coriander": "cilantro", "coriander lea(?:f|ve)": "cilantro",
    # Hindi and other Indian names
    "hara dhania": "cilantro", "dhania": "coriander", "haldi": "turmeric", "jeera": "cumin", "zeera": "cumin",
    "hing": "asafoetida", "rai": "mustard", "sarson": "mustard", "methi": "fenugreek", "elaichi": "cardamom",
    "dalchini": "cinnamon", "laung": "clove", "lavang": "clove", "saunf": "fennel", "ajwain": "carom",
    "kalonji": "nigella", "tej patta": "bay leaf", "ka?d(?:h)?i patta": "curry leaves", "curry patta": "curry leaves",
    "lal mirch": "red chili", "hari mirch": "green chili", "shimla mirch": "bell pepper",
    "adrak": "ginger", "lehsu?n": "garlic", "lahsun": "garlic", "pyaa?z": "onion", "kanda": "onion",
    "aloo": "potato", "patta gobi": "cabbage", "phool gobi": "cauliflower", "gobi": "cauliflower",
    "palak": "spinach", "bhindi": "okra", "baingan": "eggplant", "matar": "peas", "tamatar": "tomato",
    "nimbu": "lemon", "chawal": "rice", "dahi": "yogurt", "curd": "yogurt", "rava": "semolina",
    "soo?ji": "semolina", "atta": "whole wheat flour", "maida": "flour", "chai patti": "black tea",
    "chole": "chickpea", "kabuli chana": "chickpea", "rajma": "kidney bean",
    "green gram": "green moong", "sabut moong": "green moong", "whole moong": "green moong", "hara moong": "green moong",
    "daal": "dal", "dhal": "dal", "arhar": "toor", "tuvar": "toor", "toovar": "toor", "mung": "moong",
    "yoghurt": "yogurt", "channa": "chana", "black chana": "kala chana", "black chickpea": "kala chana",
    "finger millet": "ragi", "nachni": "ragi", "sorghum": "jowar", "pearl millet": "bajra",
    "fox ?nut": "makhana", "lotus seed": "makhana", "moringa": "drumstick", "sahjan": "drumstick",
    "murungakkai": "drumstick", "tindora": "ivy gourd", "tondli": "ivy gourd", "kundru": "ivy gourd",
    "dondakaya": "ivy gourd", "ivy guard": "ivy gourd", "lauki": "bottle gourd", "dudhi": "bottle gourd",
    "doodhi": "bottle gourd", "bottle guard": "bottle gourd", "meal maker": "soya chunk", "nutrela": "soya chunk",
    "soy chunk": "soya chunk", "daliy?a": "broken wheat", "lobia": "cowpea", "chawli": "cowpea",
    "black eyed pea": "cowpea", "sorrel lea(?:f|ve)": "gongura", "kaddu": "pumpkin", "pudina": "mint",
    "nariyal": "coconut", "imli": "tamarind", "amrood": "guava", "anar": "pomegranate", "badam": "almond",
    "kaju": "cashew", "akhrot": "walnut", "kishmish": "raisin", "anjeer": "fig", "alsi": "flaxseed",
    "flax seed": "flaxseed", "til": "sesame", "gaucamole": "guacamole", "cheela": "chilla",
}
IRREGULAR = {"leaves": "leaf", "halves": "half", "loaves": "loaf"}


def singular(w: str) -> str:
    if w in IRREGULAR:
        return IRREGULAR[w]
    if len(w) <= 3 or w.endswith(KEEP_S):
        return w
    if w.endswith("ies"):
        return w[:-3] + "y"
    if w.endswith(("oes", "ches", "shes", "xes", "sses")):
        return w[:-2]
    if w.endswith("s"):
        return w[:-1]
    return w


_SYN = [(re.compile(rf"\b(?:{a})s?\b"), b) for a, b in SYNONYMS.items()]


def normalize(text: str) -> str:
    """Lowercase and map alternative names ('Haldi' → 'turmeric')."""
    t = (text or "").lower()
    for rx, b in _SYN:
        t = rx.sub(b, t)
    return t


def words(text: str, drop_generic: bool = True) -> set[str]:
    """Significant, singular, lowercase words ('Baby Spinach 5oz' → {'spinach'})."""
    t = normalize(text)
    out = set()
    for w in re.findall(r"[a-z]+", t):
        if len(w) < 3:
            continue
        w = singular(w)
        if drop_generic and w in GENERIC:
            continue
        out.add(w)
    return out


def ordered_words(text: str) -> list[str]:
    """Like words(), but keeps order and duplicates (for looking at what follows a word)."""
    t = normalize(text)
    out = []
    for w in re.findall(r"[a-z]+", t):
        if len(w) < 3:
            continue
        w = singular(w)
        if w not in GENERIC:
            out.append(w)
    return out
