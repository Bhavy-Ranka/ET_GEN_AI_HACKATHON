import json
import math
import os
import re

try:
    from pymongo import MongoClient
except ModuleNotFoundError:
    MongoClient = None

try:
    from groq import Groq
except ModuleNotFoundError:
    Groq = None

try:
    import google.genai as google_genai
except ModuleNotFoundError:
    google_genai = None

try:
    from model import ensure_collection, ensure_indexes
except ImportError:
    ensure_collection = None
    ensure_indexes = None

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "hack")
MONGO_COLLECTION = os.getenv("MONGO_COLLECTION", "grievances")
MONGO_CANDIDATE_SCAN_LIMIT = int(os.getenv("MONGO_CANDIDATE_SCAN_LIMIT", "500"))
MONGO_VECTOR_INDEX = os.getenv("MONGO_VECTOR_INDEX", "").strip()
MONGO_VECTOR_PATH = os.getenv("MONGO_VECTOR_PATH", "embedding").strip() or "embedding"
MONGO_NUM_CANDIDATES = int(os.getenv("MONGO_NUM_CANDIDATES", "50"))

ALLOWED_CATEGORIES = {
    "waste management": "Waste Management",
    "waste": "Waste Management",
    "garbage": "Waste Management",
    "road": "Road",
    "pothole": "Road",
    "water": "Water",
    "sewage": "Water",
    "electricity": "Electricity",
    "power": "Electricity",
    "others": "Others",
}
ALLOWED_SEVERITIES = {"low": "Low", "medium": "Medium", "high": "High"}
DEFAULT_CATEGORY = "Others"
DEFAULT_SEVERITY = "Medium"
MAX_CANDIDATES = 5
SIMILARITY_THRESHOLD = 0.35



_GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

# text-embedding-004 lives on v1beta; generate_content models live on v1
_embed_client = None
_generate_client = None
_mongo_client = None


def _get_embed_client():
    """Client for embeddings — must use v1beta (text-embedding-004 not on v1)."""
    global _embed_client
    if google_genai is None:
        raise RuntimeError("google-genai is not installed. Run: pip install google-genai")
    if _embed_client is not None:
        return _embed_client
    _embed_client = google_genai.Client(
        api_key=_GEMINI_API_KEY,
        http_options={"api_version": "v1beta"},
    )
    return _embed_client


def _get_generate_client():
    """Client for generate_content — uses stable v1 endpoint."""
    global _generate_client
    if google_genai is None:
        raise RuntimeError("google-genai is not installed. Run: pip install google-genai")
    if _generate_client is not None:
        return _generate_client
    _generate_client = google_genai.Client(
        api_key=_GEMINI_API_KEY,
        http_options={"api_version": "v1beta"},
    )

    return _generate_client


def _get_groq_client():
    api_key = (os.getenv("GROK_API_KEY") or os.getenv("GROQ_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError(
            "GROK_API_KEY is not set. Please export it before calling llm_location_check()."
        )
    return Groq(api_key=api_key)


def _get_mongo_collection():
    global _mongo_client
    if MongoClient is None:
        raise RuntimeError("pymongo is not installed. Install it with: pip install pymongo")
    if _mongo_client is None:
        _mongo_client = MongoClient(MONGO_URI)
    db = _mongo_client[MONGO_DB]
    if ensure_collection is not None:
        try:
            collection = ensure_collection(db, MONGO_COLLECTION)
            if ensure_indexes is not None:
                ensure_indexes(collection)
            return collection
        except Exception:
            pass
    return db[MONGO_COLLECTION]


def _normalize_whitespace(text):
    if not text:
        return ""
    return re.sub(r"\s+", " ", str(text)).strip()


def _normalize_category(value):
    if not value:
        return DEFAULT_CATEGORY
    key = _normalize_whitespace(value).lower()
    for hint, canonical in ALLOWED_CATEGORIES.items():
        if hint in key:
            return canonical
    return DEFAULT_CATEGORY


def _normalize_severity(value):
    if not value:
        return DEFAULT_SEVERITY
    key = _normalize_whitespace(value).lower()
    for hint, canonical in ALLOWED_SEVERITIES.items():
        if hint in key:
            return canonical
    return DEFAULT_SEVERITY


def _normalize_tags(value):
    if not value:
        return []
    if isinstance(value, str):
        parts = re.split(r"[;,/|]", value)
        tags = [p.strip() for p in parts if p.strip()]
    elif isinstance(value, list):
        tags = [str(t).strip() for t in value if str(t).strip()]
    else:
        tags = [str(value).strip()]
    seen = set()
    normalized = []
    for tag in tags:
        lower = tag.lower()
        if lower not in seen:
            seen.add(lower)
            normalized.append(lower)
    return normalized[:8]


def _tokenize_location(value):
    text = _normalize_whitespace(value).lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    tokens = [
        t
        for t in text.split()
        if t not in {"near", "at", "in", "the", "and", "of", "on"}
    ]
    return tokens


def _simple_location_match(new_loc, candidates):
    new_tokens = _tokenize_location(new_loc)
    if not new_tokens:
        return None
    new_text = " ".join(new_tokens)
    for candidate in candidates:
        cand_tokens = _tokenize_location(candidate.get("location", ""))
        if not cand_tokens:
            continue
        cand_text = " ".join(cand_tokens)
        if new_text in cand_text or cand_text in new_text:
            return candidate["id"]
        overlap = len(set(new_tokens) & set(cand_tokens))
        union = len(set(new_tokens) | set(cand_tokens))
        if union and (overlap / union) >= 0.6:
            return candidate["id"]
    return None


def _normalize_payload(payload):
    data = dict(payload or {})
    raw_location = data.get("raw_location") or data.get("location")
    user_text = data.get("user_text") or data.get("text")
    data["issue_title"] = (
        _normalize_whitespace(data.get("issue_title")) or "Civic Issue"
    )
    data["detailed_description"] = _normalize_whitespace(
        data.get("detailed_description")
    ) or _normalize_whitespace(user_text)
    if not data["detailed_description"]:
        data["detailed_description"] = data["issue_title"]
    data["category"] = _normalize_category(data.get("category"))
    data["severity"] = _normalize_severity(data.get("severity"))
    data["formatted_location"] = _normalize_whitespace(
        data.get("formatted_location") or raw_location
    )
    data["tags"] = _normalize_tags(data.get("tags"))
    data.setdefault("priority", _severity_to_priority(data["severity"]))
    data.setdefault("report_count", 1)
    data.setdefault("status", "open")
    return data


def _severity_to_priority(severity):
    return {"Low": 1, "Medium": 2, "High": 3}.get(severity, 2)


def _safe_json_loads(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            raise
        return json.loads(match.group(0))


def _cosine_distance(vector_a, vector_b):
    if not vector_a or not vector_b:
        return 1.0
    if len(vector_a) != len(vector_b):
        return 1.0
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for a, b in zip(vector_a, vector_b):
        dot += a * b
        norm_a += a * a
        norm_b += b * b
    if norm_a == 0.0 or norm_b == 0.0:
        return 1.0
    return 1.0 - (dot / (math.sqrt(norm_a) * math.sqrt(norm_b)))


def _fetch_candidates_vector_search(collection, vector, category, include_category=True):
    if not MONGO_VECTOR_INDEX:
        return None
    filters = {"status": "open"}
    if include_category:
        filters["category"] = category
    pipeline = [
        {
            "$vectorSearch": {
                "index": MONGO_VECTOR_INDEX,
                "path": MONGO_VECTOR_PATH,
                "queryVector": vector,
                "numCandidates": MONGO_NUM_CANDIDATES,
                "limit": MAX_CANDIDATES,
                "filter": filters,
            }
        },
        {
            "$project": {
                "formatted_location": 1,
                "embedding": 1,
                "status": 1,
                "category": 1,
                "report_count": 1,
                "priority": 1,
                "severity": 1,
            }
        },
    ]
    try:
        return list(collection.aggregate(pipeline))
    except Exception as exc:
        print(f"[WARNING] MongoDB $vectorSearch failed (index '{MONGO_VECTOR_INDEX}' may not exist): {exc}. Falling back to scan mode.")
        return None


def _fetch_candidates_scan(collection, category, include_category=True):
    query = {"status": "open"}
    if include_category:
        query["category"] = category
    try:
        cursor = (
            collection.find(
                query,
                {
                    "formatted_location": 1,
                    "embedding": 1,
                    "status": 1,
                    "category": 1,
                    "report_count": 1,
                    "priority": 1,
                    "severity": 1,
                },
            )
            .limit(MONGO_CANDIDATE_SCAN_LIMIT)
        )

        return list(cursor)
    except Exception as exc:
        print(f"[WARNING] MongoDB candidate scan failed: {exc}")
        return []


def _fetch_candidates(collection, vector, category, include_category=True):
    if MONGO_VECTOR_INDEX:
        candidates = _fetch_candidates_vector_search(collection, vector, category, include_category=include_category)
        if candidates is not None and len(candidates) > 0:
            return candidates
    return _fetch_candidates_scan(collection, category, include_category=include_category)


def _rank_candidates(vector, candidates):
    scored = []
    for candidate in candidates:
        embedding = candidate.get("embedding")
        if not isinstance(embedding, list):
            continue
        distance = _cosine_distance(vector, embedding)
        scored.append((candidate, distance))
    scored.sort(key=lambda item: item[1])
    return scored[:MAX_CANDIDATES]


_EMBEDDING_MODELS = [
    "models/gemini-embedding-001",
    "models/text-embedding-004",
]

def get_embedding(text):
    if not _GEMINI_API_KEY:
        print("[WARNING] GEMINI_API_KEY is not set. Generating fallback deterministic text hash embedding.")
        import hashlib
        h = hashlib.sha256(text.encode("utf-8")).digest()
        return [((b / 255.0) * 2.0 - 1.0) for b in (h * 24)[:768]]

    client = _get_embed_client()
    last_exc = None
    for model in _EMBEDDING_MODELS:
        try:
            result = client.models.embed_content(
                model=model,
                contents=text,
            )
            return result.embeddings[0].values
        except Exception as exc:
            print(f"Embedding model {model!r} failed: {exc}")
            last_exc = exc

    import hashlib
    h = hashlib.sha256(text.encode("utf-8")).digest()
    return [((b / 255.0) * 2.0 - 1.0) for b in (h * 24)[:768]]



def llm_location_check(new_loc, existing_locs_with_ids):
    """
    Sends the new location and a list of candidate locations to Groq or Gemini LLM.
    Returns a dict: {"match_found": bool, "matching_id": str or None, "reason": str}
    """
    if not _normalize_whitespace(new_loc):
        return {"match_found": False, "matching_id": None, "reason": "No location"}

    if not existing_locs_with_ids:
        return {"match_found": False, "matching_id": None, "reason": "No candidates"}

    prompt = f"""
    You are a location matching expert for a city management system.
    New Report Location: "{new_loc}"
    
    Existing Candidate Locations:
    {json.dumps(existing_locs_with_ids, indent=2)}
    
    Task: Determine if the New Report Location refers to the SAME physical spot as any of the candidates.
    Consider landmarks, sectors, street names, and common variations (e.g., 'Main Gate' and 'Entrance').
    
    Return ONLY a JSON object with:
    {{
        "match_found": true/false,
        "matching_id": "matching candidate id or null",
        "reason": "short explanation"
    }}
    """

    if Groq is not None:
        try:
            groq_client = _get_groq_client()
            chat_completion = groq_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.3-70b-versatile",
                response_format={"type": "json_object"},
            )
            return _safe_json_loads(chat_completion.choices[0].message.content)
        except Exception as exc:
            print(f"[LOCATION CHECK] Groq LLM failed ({exc}); trying Gemini fallback...")

    if google_genai is not None and _GEMINI_API_KEY:
        try:
            gen_client = _get_generate_client()
            resp = gen_client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config={"response_mime_type": "application/json"}
            )
            return _safe_json_loads(resp.text)
        except Exception as exc:
            print(f"[LOCATION CHECK] Gemini LLM failed ({exc}); using fuzzy string matcher fallback.")

    match_id = _simple_location_match(new_loc, existing_locs_with_ids)
    return {
        "match_found": match_id is not None,
        "matching_id": match_id,
        "reason": "Fuzzy token string match fallback",
    }


def process_grievance_with_llm_filter(new_json):
    """
    Returns a tuple: (result_data, message)
    Handles candidate ranking, location matching, embedding similarity,
    and report_count + dynamic severity escalation upon deduplication.
    """
    normalized = _normalize_payload(new_json)
    user_name = new_json.get("user_name", "Anonymous")

    if MongoClient is None:
        return normalized, "Error: pymongo not installed"

    new_vector = get_embedding(normalized["detailed_description"])
    collection = _get_mongo_collection()

    # 1. Fetch Candidates (Stage 1)
    candidates = _fetch_candidates(collection, new_vector, normalized["category"], include_category=True)
    ranked_candidates = _rank_candidates(new_vector, candidates)

    # 2. Location Check (Stage 2)
    loc_candidates = [
        {"id": str(candidate["_id"]), "location": candidate.get("formatted_location", "")}
        for candidate, _ in ranked_candidates
    ]
    loc_result = llm_location_check(normalized["formatted_location"], loc_candidates)

    if loc_result.get("match_found"):
        match_id = str(loc_result.get("matching_id"))
        match_entry = next(
            (
                (candidate, distance)
                for candidate, distance in ranked_candidates
                if str(candidate.get("_id")) == match_id
            ),
            None,
        )

        if match_entry is not None:
            candidate, match_distance = match_entry
            if match_distance < SIMILARITY_THRESHOLD:
                current_status = candidate.get("status", "open")

                if current_status == "resolved":
                    save_as_new_issue(collection, normalized, new_vector, user_name, new_json)
                    return normalized, "Grievance registered as a new report."

                new_report_count = candidate.get("report_count", 1) + 1
                orig_severity = candidate.get("severity") or normalized["severity"]
                base_priority = _severity_to_priority(orig_severity)
                
                new_priority = base_priority + (new_report_count - 1)
                
                if new_report_count >= 4 or new_priority >= 5:
                    new_severity = "High"
                elif new_priority >= 3 or new_report_count >= 2:
                    new_severity = "Medium" if orig_severity == "Low" else orig_severity
                else:
                    new_severity = orig_severity

                update_fields = {
                    "report_count": new_report_count,
                    "priority": new_priority,
                    "severity": new_severity,
                }
                collection.update_one({"_id": candidate["_id"]}, {"$set": update_fields})

                normalized["report_count"] = new_report_count
                normalized["priority"] = new_priority
                normalized["severity"] = new_severity

                return (
                    normalized,
                    f"This issue is already registered. Report count updated to {new_report_count} (Severity: {new_severity}). (ID: {candidate['_id']})",
                )

    save_as_new_issue(collection, normalized, new_vector, user_name, new_json)
    return normalized, "Grievance registered successfully."



def save_as_new_issue(collection, data, vector, user_name, new_json=None):
    raw_location = ""
    image_path = ""
    user_text = ""
    image_value = None
    if isinstance(new_json, dict):
        raw_location = new_json.get("raw_location") or new_json.get("location") or ""
        image_value = new_json.get("image")
        image_path = new_json.get("image_path") or image_value or ""
        user_text = new_json.get("user_text") or new_json.get("text") or ""

    doc = {
        "issue_title": data["issue_title"],
        "detailed_description": data["detailed_description"],
        "category": data["category"],
        "severity": data["severity"],
        "formatted_location": data["formatted_location"],
        "tags": data.get("tags", []),
        "priority": data.get("priority", _severity_to_priority(data["severity"])),
        "report_count": data.get("report_count", 1),
        "status": data.get("status", "open"),
        "raw_location": raw_location,
        "image_path": image_path,
        "user_text": user_text,
        "user_name": user_name,
        "embedding": vector,
    }
    if image_value is not None:
        doc["image"] = image_value
    collection.insert_one(doc)
