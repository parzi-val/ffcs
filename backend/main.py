import json
import shutil
import uuid

from fastapi import BackgroundTasks, FastAPI, File, Form, UploadFile, HTTPException, Cookie,Response
from fastapi.middleware.cors import CORSMiddleware
from itsdangerous import URLSafeSerializer
from tqdm import tqdm

from config import ROOT_DIR, UPLOADS
from core.utils.extraction import TextExtraction
from core.utils.pipeline import Pipeline
from core.utils.restructure import Restructure

app = FastAPI()

SECRET_KEY = "your-secret-key"
serializer = URLSafeSerializer(SECRET_KEY)

# Configure CORS to allow all origins
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=".*",  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allow all headers
)

def clean_up():
    for file in UPLOADS.iterdir():
        file.unlink()

def extract(image_paths):
    """Extract text from images"""
    reformat_data = []
    base_text = []
    for image_path in tqdm(image_paths):
        base = TextExtraction(image_path)
        reformat_data.append(base.reformat)
        base_text.append(base.text)
    
    return {"base_reformat":reformat_data, "base_text":base_text}

def cache_it(data):
    id = str(uuid.uuid4())
    with open(ROOT_DIR / "cache" / f"{id}.json", "w") as file: 
        json.dump(data, file)
    return id

def retrieve_it(id):
    with open(ROOT_DIR / "cache" / f"{id}.json", "r") as file:
        data = json.load(file)
    return data

def delete_it(id):
    (ROOT_DIR / "cache" / f"{id}.json").unlink()

@app.post("/process2/")
def process_images(
    background_tasks: BackgroundTasks,
    image: list[UploadFile] = File(...),
):
    """API for generating timetables from uploaded images."""
    file_paths = []

    for file in image:
        file_location = UPLOADS / file.filename
        file_paths.append(str(file_location))

        with open(str(file_location), "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    
    image_data = extract(file_paths)
    id = cache_it(image_data["base_text"])
    background_tasks.add_task(clean_up)

    return {"courses" : image_data["base_reformat"],"id":id}

@app.post("/process3/")
def process(
    session_token :str = Cookie(None),
    credits: str = Form(...),
    timing: str = Form(...),
    courses: str = Form(...),
    id: str = Form(...),
):
    courses = json.loads(courses)
    print(id)
    print(type(courses))

    base_text = retrieve_it(id)
    delete_it(id)
    restructured = Restructure({"courses": base_text})
    restructured.mandate(courses)
    restructured_data = restructured.data
    pipeline = Pipeline(restructured_data, credits=credits, morning= True if timing == "morning" else False)
    response = pipeline.response

    return response


import uvicorn

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
