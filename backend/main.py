from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from datetime import date, time, datetime
import psycopg2
from psycopg2.extras import RealDictCursor
import os

app = FastAPI(title="Event Management API", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
class EventCreate(BaseModel):
    title: str
    description: Optional[str] = None
    category: Optional[str] = None
    location: Optional[str] = None
    event_date: date
    event_time: time
    organizer: Optional[str] = None


# Category model
class Category(BaseModel):
    name: str

def get_db():
    config = get_db_config()
    conn = psycopg2.connect(**config, cursor_factory=RealDictCursor)
    return conn

# Endpoint to get all categories from dcategories
@app.get("/events/categories/list", response_model=List[str])
def get_categories():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT name FROM dcategories ORDER BY name ASC;")
    categories = [row["name"] for row in cur.fetchall()]
    cur.close()
    conn.close()
    return categories

# Endpoint to add a new category
@app.post("/events/categories/add", status_code=201)
def add_category(category: Category):
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO dcategories (name) VALUES (%s) RETURNING name;", (category.name,))
        conn.commit()
        new_cat = cur.fetchone()["name"]
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        cur.close()
        conn.close()
        raise HTTPException(status_code=400, detail="Category already exists.")
    cur.close()
    conn.close()
    return {"name": new_cat}

class EventUpdate(BaseModel):
    title: str
    description: Optional[str] = None
    category: Optional[str] = None
    location: Optional[str] = None
    event_date: date
    event_time: time
    organizer: Optional[str] = None

class Event(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    category: Optional[str] = None
    location: Optional[str] = None
    event_date: date
    event_time: time
    organizer: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

# Database connection
def get_db_config():
    return {
        "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", 5432)),
        "database": os.getenv("DB_NAME", "event_management"),
        "user": os.getenv("DB_USER", "eventuser"),
        "password": os.getenv("DB_PASSWORD", "eventpass123")
    }

def get_db_connection():
    try:
        config = get_db_config()
        conn = psycopg2.connect(**config, cursor_factory=RealDictCursor)
        return conn
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database connection failed: {str(e)}")

# API endpoints
@app.get("/")
def read_root():
    return {"message": "Event Management API", "version": "1.0.0"}

@app.get("/health")
def health_check():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        conn.close()
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Health check failed: {str(e)}")

@app.post("/events", response_model=dict)
def create_event(event: EventCreate):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        query = """
            INSERT INTO events (title, description, category, location, event_date, event_time, organizer)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """
        cursor.execute(query, (
            event.title, event.description, event.category, 
            event.location, event.event_date, event.event_time, event.organizer
        ))
        event_id = cursor.fetchone()['id']
        conn.commit()
        cursor.close()
        conn.close()
        return {"message": "Event created successfully", "id": event_id}
    except Exception as e:
        conn.rollback()
        conn.close()
        raise HTTPException(status_code=500, detail=f"Error creating event: {str(e)}")

@app.get("/events", response_model=List[Event])
def get_events(category: Optional[str] = None, search: Optional[str] = None):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Base query
        query = """
            SELECT id, title, description, category, location, event_date, event_time, organizer, created_at, updated_at
            FROM events
        """
        params = []
        conditions = []
        
        # Add filters
        if category and category.lower() != 'all':
            conditions.append("category ILIKE %s")
            params.append(f"%{category}%")
        
        if search:
            conditions.append("(title ILIKE %s OR description ILIKE %s)")
            params.extend([f"%{search}%", f"%{search}%"])
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY event_date, event_time"
        
        cursor.execute(query, params)
        events = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return [dict(event) for event in events]
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=f"Error retrieving events: {str(e)}")

@app.get("/events/{event_id}", response_model=Event)
def get_event(event_id: int):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, title, description, category, location, event_date, event_time, organizer, created_at, updated_at
            FROM events WHERE id = %s
        """, (event_id,))
        event = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")
        
        return dict(event)
    except HTTPException:
        conn.close()
        raise
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=f"Error retrieving event: {str(e)}")

@app.put("/events/{event_id}", response_model=dict)
def update_event(event_id: int, event: EventUpdate):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Check if event exists
        cursor.execute("SELECT id FROM events WHERE id = %s", (event_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Event not found")
        
        # Update event
        query = """
            UPDATE events 
            SET title = %s, description = %s, category = %s, location = %s, 
                event_date = %s, event_time = %s, organizer = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """
        cursor.execute(query, (
            event.title, event.description, event.category,
            event.location, event.event_date, event.event_time, event.organizer, event_id
        ))
        conn.commit()
        cursor.close()
        conn.close()
        
        return {"message": "Event updated successfully", "id": event_id}
    except HTTPException:
        conn.close()
        raise
    except Exception as e:
        conn.rollback()
        conn.close()
        raise HTTPException(status_code=500, detail=f"Error updating event: {str(e)}")

@app.delete("/events/{event_id}", response_model=dict)
def delete_event(event_id: int):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Check if event exists
        cursor.execute("SELECT id FROM events WHERE id = %s", (event_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Event not found")
        
        # Delete event
        cursor.execute("DELETE FROM events WHERE id = %s", (event_id,))
        conn.commit()
        cursor.close()
        conn.close()
        
        return {"message": "Event deleted successfully", "id": event_id}
    except HTTPException:
        conn.close()
        raise
    except Exception as e:
        conn.rollback()
        conn.close()
        raise HTTPException(status_code=500, detail=f"Error deleting event: {str(e)}")

@app.get("/events/categories/list")
def get_categories():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT category FROM events WHERE category IS NOT NULL AND category != '' ORDER BY category")
        categories = [row['category'] for row in cursor.fetchall()]
        cursor.close()
        conn.close()
        return {"categories": categories}
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=f"Error retrieving categories: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)