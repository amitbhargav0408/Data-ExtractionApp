import re
import PyPDF2
import sqlite3
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
import uvicorn
import os
from dotenv import load_dotenv

app = FastAPI()

load_dotenv()
DATABASE = os.getenv('DATABASE_FILEPATH')

def get_db_connection():
    try:
        conn = sqlite3.connect(DATABASE)
        return conn
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database connection failed: {e}")

@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Invalid file type")

    # Create the directory if it doesn't exist
    upload_dir = os.getenv("UPLOAD_FILEPATH")
    os.makedirs(upload_dir, exist_ok=True)

    file_path = os.path.join(upload_dir, file.filename)

    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())

    text = extract_detail_pdf(file_path)
    details = extract_details_from_text(text)
    store_details_in_db(details)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''SELECT id FROM cv_details WHERE email = ?''', (details['email'],))
    user_id = cursor.fetchone()[0]
    conn.close()

    return JSONResponse(content={"message": "File processed successfully", "id": user_id, "details": details})

@app.get("/details/")
async def get_details():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''SELECT * FROM cv_details''')
    details = cursor.fetchall()

    conn.close()
    return JSONResponse(content={"message": "Data retrieved successfully", "details": details})

@app.get("/details/{id}")
async def get_user_details(id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''SELECT * FROM cv_details WHERE id = ?''', (id,))
    details = cursor.fetchone()

    conn.close()
    return JSONResponse(content={"message": "Data retrieved successfully", "details": details})

@app.get("/update/{id}/")
async def update_details(id: int, name: str=None, email: str=None, phone: str=None, linkedin: str=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    query = "UPDATE cv_details SET"
    params = []
    if name:
        query += " name = ?,"
        params.append(name)
    if email:
        query += " email = ?,"
        params.append(email)
    if phone:
        query += " phone = ?,"
        params.append(phone)
    if linkedin:
        query += " linkedin = ?,"
        params.append(linkedin)

    query = query.rstrip(',') + " WHERE id = ?;"
    params.append(id)
    
    cursor.execute(query, params)
    conn.commit()

    cursor.execute('''SELECT * FROM cv_details WHERE id = ?''', (id,))
    details = cursor.fetchone()

    conn.close()
    return JSONResponse(content={"message": "Data updated successfully", "details": details})

def extract_detail_pdf(pdf_file):
    with open(pdf_file, "rb") as file:
        reader = PyPDF2.PdfReader(file)
        text = "".join([page.extract_text() for page in reader.pages])

    return text


def extract_details_from_text(text):
    cv_details = {}
    cv_details['name'] = re.search(r'\b[A-Z][a-z]+\s[A-Z][a-z]+\b', text).group(0)  
    cv_details['email'] = re.search(r'[\w\.-]+@[\w\.-]+', text).group(0) 
    cv_details['phone'] = re.search(r'\+?\d[\d\s()-]{7,}', text).group(0)

    linkedin_match = re.search(r'linkedin.com/[^\s|]+', text)
    cv_details['linkedin'] = linkedin_match.group(0) if linkedin_match else None

    education_match = re.search(r'EDUCATION(.*?)(?=EXPERIENCE|SKILLS|$)', text, re.S)
    cv_details['education'] = education_match.group(1).strip() if education_match else None
    
    work_experience_match = re.search(r'EXPERIENCE(.*?)(?=SKILLS|EDUCATION|$)', text, re.S)
    cv_details['work_experience'] = work_experience_match.group(1).strip() if work_experience_match else None

    project_match = re.search(r'PROJECTS(.*?)(?=EXPERIENCE|SKILLS|EDUCATION|$)', text, re.S)
    cv_details['projects'] = project_match.group(1).strip() if project_match else None
    
    skills_match = re.search(r'SKILLS(.*)', text, re.S)
    cv_details['skills'] = skills_match.group(1).strip() if skills_match else None
    
    return cv_details


def store_details_in_db(details):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS {os.getenv("DATABASE_NAME")} (
                id INTEGER PRIMARY KEY,
                name VARCHAR(255),
                email VARCHAR(255),
                phone VARCHAR(255),
                linkedin VARCHAR(255),
                education TEXT,
                work_experience TEXT,
                projects TEXT,
                skills TEXT
            )
        ''')

        cursor.execute('''
            INSERT INTO cv_details (name, email, phone, linkedin, education, work_experience, projects, skills)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            details['name'], 
            details['email'], 
            details['phone'], 
            details['linkedin'], 
            details['education'], 
            details['work_experience'], 
            details['projects'], 
            details['skills']
        ))

        conn.commit()
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Failed to insert data: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)


