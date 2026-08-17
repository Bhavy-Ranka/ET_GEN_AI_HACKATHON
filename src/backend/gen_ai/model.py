"""
MongoDB schema/validator and helpers for the grievances collection.
"""

from typing import Dict, Any


CATEGORY_ENUM = ["Waste Management", "Road", "Water", "Electricity", "Others"]
SEVERITY_ENUM = ["Low", "Medium", "High"]
STATUS_ENUM = ["open", "resolved"]


GRIEVANCE_VALIDATOR: Dict[str, Any] = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": [
            "issue_title",
            "detailed_description",
            "category",
            "severity",
            "formatted_location",
            "tags",
            "priority",
            "report_count",
            "status",
            "raw_location",
            "image_path",
            "user_text",
            "user_name",
            "embedding",
        ],
        "properties": {
            "issue_title": {"bsonType": "string"},
            "detailed_description": {"bsonType": "string"},
            "category": {"bsonType": "string", "enum": CATEGORY_ENUM},
            "severity": {"bsonType": "string", "enum": SEVERITY_ENUM},
            "formatted_location": {"bsonType": "string"},
            "tags": {"bsonType": "array", "items": {"bsonType": "string"}},
            "priority": {"bsonType": "int", "minimum": 1},
            "report_count": {"bsonType": "int", "minimum": 1},
            "status": {"bsonType": "string", "enum": STATUS_ENUM},
            "raw_location": {"bsonType": "string"},
            "image_path": {"bsonType": "string"},
            "user_text": {"bsonType": "string"},
            "user_name": {"bsonType": "string"},
            "embedding": {"bsonType": "array", "items": {"bsonType": "double"}},
            # optional or flexible types
            "image": {},
        },
        "additionalProperties": True,
    }
}


def ensure_collection(db, collection_name: str = "grievances", validation_level: str = "moderate"):
    """
    Create the collection with validator if it doesn't exist.
    If it exists, update validator via collMod.
    """
    existing = collection_name in db.list_collection_names()
    if not existing:
        db.create_collection(
            collection_name,
            validator=GRIEVANCE_VALIDATOR,
            validationLevel=validation_level,
        )
        return db[collection_name]
    try:
        db.command(
            {
                "collMod": collection_name,
                "validator": GRIEVANCE_VALIDATOR,
                "validationLevel": validation_level,
            }
        )
    except Exception:
        pass
    return db[collection_name]


def ensure_indexes(collection):
    collection.create_index([("status", 1), ("category", 1)])

def vector_index_spec(num_dimensions: int, path: str = "embedding") -> Dict[str, Any]:
    return {
        "fields": [
            {"type": "vector", "path": path, "numDimensions": num_dimensions, "similarity": "cosine"},
            {"type": "filter", "path": "status"},
            {"type": "filter", "path": "category"},
        ]
    }
