import os
import sys
import shutil
from typing import Annotated
from pydantic import BaseModel
from fastapi import FastAPI, File, UploadFile, HTTPException, Depends
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from database import ComplaintDB, get_db
from authentication import router as auth_router, get_current_user

try:
    from gen_ai.ai_main import run_pipeline
    _PIPELINE_AVAILABLE = True
except Exception as _err:
    _PIPELINE_AVAILABLE = False
    print(f"[WARNING] gen_ai pipeline could not be imported: {_err}")

app = FastAPI()

origins_env = os.getenv("ALLOWED_ORIGINS", "").strip()
if origins_env:
    allowed_origins = [o.strip() for o in origins_env.split(",") if o.strip()]
else:
    allowed_origins = [
        "http://localhost:8501",
        "http://127.0.0.1:8501",
        "http://localhost:3000",
        "http://127.0.0.1:8000",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


class DescriptionRequest(BaseModel):
    text: str
    address: str
    filename: str



def _get_safe_upload_path(filename: str) -> str:
    safe_name = os.path.basename(filename)
    if not safe_name:
        raise HTTPException(status_code=400, detail="Invalid filename.")
    abs_upload_dir = os.path.abspath(UPLOAD_DIR)
    target_path = os.path.abspath(os.path.join(abs_upload_dir, safe_name))
    if not target_path.startswith(abs_upload_dir):
        raise HTTPException(status_code=400, detail="Invalid file path.")
    return target_path


@app.post("/uploadfile/")
async def create_upload_file(file: UploadFile, current_user: str = Depends(get_current_user)):
    safe_filename = os.path.basename(file.filename)
    file_path = _get_safe_upload_path(safe_filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return {"filename": safe_filename, "status": "Saved successfully"}


@app.post("/imageDescription")
async def give_description(
    req: DescriptionRequest,
    current_user: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    safe_filename = os.path.basename(req.filename)
    # 1. Save complaint to SQLite DB using dependency
    new_complaint = ComplaintDB(
        username=current_user,
        text=req.text,
        address=req.address,
        filename=safe_filename,
    )
    db.add(new_complaint)
    db.commit()

    # 2. Run AI pipeline
    pipeline_result = {}
    pipeline_warning = None

    if not _PIPELINE_AVAILABLE:
        pipeline_warning = "Pipeline unavailable at startup; skipping."
    else:
        try:
            image_path = _get_safe_upload_path(safe_filename)
            if not os.path.isfile(image_path):
                pipeline_warning = f"Image '{safe_filename}' not found in uploads/; pipeline skipped."
            else:
                try:
                    pipeline_result = run_pipeline(image_path, req.address, req.text, user_name=current_user)
                except Exception as exc:
                    pipeline_warning = f"Pipeline error: {exc}"
                    print(f"[ERROR] Pipeline failed: {exc}")
        except HTTPException as e:
            pipeline_warning = f"Invalid filename: {e.detail}"

    response = {
        "status": "Complaint Saved",
        "description": req.text,
        "address": req.address,
        "pipeline": pipeline_result,
    }
    if pipeline_warning:
        response["pipeline_warning"] = pipeline_warning

    return response


@app.get("/view/{filename}")
async def view_image(filename: str, current_user: str = Depends(get_current_user)):
    try:
        file_path = _get_safe_upload_path(filename)
    except HTTPException:
        raise HTTPException(status_code=404, detail=f"File {filename} not found on server.")
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail=f"File {filename} not found on server.")
    return FileResponse(file_path)

@app.get("/admin/complaints")
async def get_all_complaints(current_user: str = Depends(get_current_user)):
    if current_user != "bhavyranka@gmail.com":
        raise HTTPException(status_code=403, detail="Not authorized as admin")
    
    try:
        from pymongo import MongoClient
        import os
        client = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017"))
        db = client[os.getenv("MONGO_DB", "hack")]
        collection = db[os.getenv("MONGO_COLLECTION", "grievances")]
        
        complaints = list(collection.find({}, {"embedding": 0}))  # exclude embedding field
        for c in complaints:
            c["_id"] = str(c["_id"])  # convert ObjectId to string
        
        return complaints
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"MongoDB error: {e}")
    
@app.delete("/admin/complaints/{complaint_id}")
async def delete_complaint(complaint_id: str, current_user: str = Depends(get_current_user)):
    if current_user != "bhavyranka@gmail.com":
        raise HTTPException(status_code=403, detail="Not authorized as admin")
    try:
        from pymongo import MongoClient
        from bson import ObjectId
        client = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017"))
        db = client[os.getenv("MONGO_DB", "hack")]
        collection = db[os.getenv("MONGO_COLLECTION", "grievances")]
        result = collection.delete_one({"_id": ObjectId(complaint_id)})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Complaint not found")
        return {"status": "deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))    
