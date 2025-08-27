import streamlit as st

if 'messages' not in st.session_state:
    st.session_state['messages'] = []
import json
import requests
import os
from openai import OpenAI
import psycopg2
from psycopg2.pool import SimpleConnectionPool
from psycopg2.extras import RealDictCursor
import datetime
import re
import hashlib
import secrets
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import time
from functools import lru_cache, wraps

# -------------------- Configuration --------------------
class Config:
    """Centralized configuration management"""
    OPENAI_API_KEY = os.getenv("OPENAI_APIKEY")
    # Use Docker service name for Weaviate by default
    WEAVIATE_URL = os.getenv("WEAVIATE_URL", "http://weaviate:8080")
    # Database configuration
    DB_CONFIG = {
        "host": os.getenv("DB_HOST", "postgres"),
        "dbname": os.getenv("DB_NAME", "event_management"),
        "user": os.getenv("DB_USER", "eventuser"),
        "password": os.getenv("DB_PASSWORD", "eventpass123"),
        "port": os.getenv("DB_PORT", "5432")
    }
    
    # Security settings
    SALT_ROUNDS = 12
    SESSION_TIMEOUT_MINUTES = 30
    MAX_LOGIN_ATTEMPTS = 5
    
    # API settings
    OPENAI_MODEL = "gpt-4o-mini"
    OPENAI_TEMPERATURE = 0.7
    MAX_EVENTS_PER_QUERY = 10
    
    # Cache settings
    CACHE_TTL = 300  # 5 minutes

# -------------------- Logging Setup --------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# -------------------- Data Models --------------------
@dataclass
class User:
    """User data model"""
    id: int
    username: str
    email: str
    full_name: Optional[str]
    created_at: datetime.datetime
    last_login: Optional[datetime.datetime]

@dataclass
class Event:
    """Event data model"""
    id: int
    title: str
    description: str
    category: str
    location: str
    organizer: str
    event_date: datetime.date
    event_time: str
    created_at: datetime.datetime
    
class RegistrationStatus(Enum):
    """Event registration status enum"""
    REGISTERED = "registered"
    CANCELLED = "cancelled"
    WAITLISTED = "waitlisted"

# -------------------- Error Handling --------------------
class EventSystemError(Exception):
    """Base exception for event system"""
    pass

class AuthenticationError(EventSystemError):
    """Authentication related errors"""
    pass

class DatabaseError(EventSystemError):
    """Database related errors"""
    pass

class APIError(EventSystemError):
    """External API related errors"""
    pass

# -------------------- Database Connection Pool --------------------
class DatabaseManager:
    """Manage database connections with pooling"""
    
    def __init__(self, config: Dict[str, Any], min_conn: int = 2, max_conn: int = 10):
        self.pool = None
        self.config = config
        self.min_conn = min_conn
        self.max_conn = max_conn
        self.initialize_pool()
    
    def initialize_pool(self):
        """Initialize connection pool"""
        try:
            self.pool = SimpleConnectionPool(
                self.min_conn,
                self.max_conn,
                **self.config
            )
            logger.info("Database connection pool initialized")
        except Exception as e:
            logger.error(f"Failed to initialize database pool: {e}")
            raise DatabaseError(f"Database initialization failed: {e}")
    
    def get_connection(self):
        """Get connection from pool"""
        if not self.pool:
            self.initialize_pool()
        return self.pool.getconn()
    
    def return_connection(self, conn):
        """Return connection to pool"""
        if self.pool and conn:
            self.pool.putconn(conn)
    
    def close_all_connections(self):
        """Close all connections in pool"""
        if self.pool:
            self.pool.closeall()
            logger.info("All database connections closed")
    
    def execute_query(self, query: str, params: tuple = None, fetch: bool = True) -> Any:
        """Execute a database query with proper error handling"""
        conn = None
        cur = None
        try:
            conn = self.get_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(query, params)
            
            if fetch:
                result = cur.fetchall()
            else:
                conn.commit()
                result = cur.rowcount
            
            return result
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Database query error: {e}")
            raise DatabaseError(f"Query execution failed: {e}")
        finally:
            if cur:
                cur.close()
            if conn:
                self.return_connection(conn)

# Initialize database manager
@st.cache_resource
def get_db_manager():
    """Get cached database manager instance"""
    return DatabaseManager(Config.DB_CONFIG)

# -------------------- Security Functions --------------------
class SecurityManager:
    """Handle security-related operations"""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Return password as-is (no hashing)"""
        return password
    
    @staticmethod
    def verify_password(password: str, stored_password: str) -> bool:
        """Verify password by direct comparison"""
        return password == stored_password
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """Validate email format"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    @staticmethod
    def validate_password(password: str) -> Tuple[bool, str]:
        """Validate password strength"""
        if len(password) < 8:
            return False, "Password must be at least 8 characters long"
        if not re.search(r'[A-Z]', password):
            return False, "Password must contain at least one uppercase letter"
        if not re.search(r'[a-z]', password):
            return False, "Password must contain at least one lowercase letter"
        if not re.search(r'\d', password):
            return False, "Password must contain at least one number"
        return True, "Password is valid"

# -------------------- Authentication Functions --------------------
class AuthManager:
    """Handle authentication operations"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self.security = SecurityManager()
    
    def create_user(self, username: str, email: str, password: str, full_name: Optional[str] = None) -> Tuple[bool, str]:
        """Create new user account"""
        try:
            # Validate inputs
            if not username or not email or not password:
                return False, "All fields are required"
            
            if not self.security.validate_email(email):
                return False, "Invalid email format"
            
            valid, msg = self.security.validate_password(password)
            if not valid:
                return False, msg
            
            # Store password as plain text (no hashing)
            plain_password = password
            
            # Insert user - use actual database schema
            query = """
                INSERT INTO users (username, email, password, full_name)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            """
            result = self.db.execute_query(
                query,
                (username, email, plain_password, full_name),
                fetch=True
            )
            
            if result:
                logger.info(f"User created successfully: {username}")
                return True, "Account created successfully"
            return False, "Failed to create account"
            
        except DatabaseError as e:
            if "unique" in str(e).lower():
                return False, "Username or email already exists"
            return False, f"Database error: {e}"
        except Exception as e:
            logger.error(f"User creation error: {e}")
            return False, f"An error occurred: {e}"
    
    def authenticate_user(self, username: str, password: str) -> Tuple[bool, Optional[User]]:
        """Authenticate user login"""
        try:
            # Query using actual database schema
            query = """
                SELECT id, username, email, password, full_name
                FROM users WHERE username = %s
            """
            result = self.db.execute_query(query, (username,), fetch=True)
            
            if result and len(result) > 0:
                user_data = result[0]
                if password == user_data['password']:  # Plain text password comparison
                    
                    user = User(
                        id=user_data['id'],
                        username=user_data['username'],
                        email=user_data['email'],
                        full_name=user_data.get('full_name'),
                        created_at=datetime.datetime.now(),  # Default since column doesn't exist
                        last_login=datetime.datetime.now()   # Set to current time
                    )
                    logger.info(f"User authenticated: {username}")
                    return True, user
            
            return False, None
            
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return False, None

# -------------------- AI Integration --------------------
class AIManager:
    """Handle AI-related operations"""
    
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)
        self.model = Config.OPENAI_MODEL
    
    @lru_cache(maxsize=128)
    def extract_interests(self, user_message: str) -> Dict[str, List[str]]:
        """Extract interests from user message with caching"""
        try:
            system_prompt = """
            DO NOT recommend any events unless the user's CURRENT message is a direct request for events, an event, or something clearly related (like 'show me events', 'any tech events?', 'what's happening this week?').
            If the user's message is about help, interests, or changing topics, DO NOT recommend events under ANY circumstances.
            If the user says they are not interested, or asks for help with interests, or wants to change topics, DO NOT recommend events. Instead, offer to help with something else, or ask what they are interested in.
            If you are unsure, err on the side of NOT recommending events.
            Never recommend events just because you remember previous interests—only if the CURRENT message is a request for events.
            Extract interests, date/time constraints, and locations from the text.
            never get any events that not exists in our database.

            Output valid JSON with keys: tags, date_constraints, location_constraints.
            Be specific and extract only relevant information.
            Example output:
            {
                "tags": ["technology", "sports"],
                "date_constraints": ["this weekend", "next month"],
                "location_constraints": ["campus", "downtown"]
            }
            """
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=0,
                max_tokens=200
            )
            
            content = response.choices[0].message.content
            return json.loads(content)
            
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse AI response as JSON")
            return {"tags": [], "date_constraints": [], "location_constraints": []}
        except Exception as e:
            logger.error(f"AI extraction error: {e}")
            return {"tags": [], "date_constraints": [], "location_constraints": []}
    
    def generate_reply(self, user_input: str, events: List[Dict], interests: Dict, history: List[Dict]) -> str:
        """Generate AI reply for user"""
        try:
            today = datetime.date.today().isoformat()
            
            if events and len(events) > 0:
                event = events[0]
                system_prompt = f"""
                You are a helpful campus events chatbot. Today is {today}.
                The user has specifically requested event recommendations.
                never recommend an event unless the user's CURRENT message is a direct request for events.
                If the user says they are not interested, or asks for help with interests, or wants to change topics, DO NOT recommend events. Instead, offer to help with something else, or ask what they are interested in.
                If you are unsure, err on the side of NOT recommending events.
                Never recommend events just because you remember previous interests—only if the CURRENT message is a request for events.
                never get any events that not exists in our database.
                Recommend ONE event at a time in a clear, engaging format.
                Keep responses concise (under 100 words).
                Format events with emojis and clear sections.
                Always ask if the user would like to register after recommending.
                """
                
                event_info = f"""
                Event to recommend:
                Title: {event.get('title', 'Unknown')}
                Description: {event.get('description', 'No description')}
                Category: {event.get('category', 'General')}
                Location: {event.get('location', 'TBA')}
                Date: {event.get('event_date', 'TBA')}
                Time: {event.get('event_time', 'TBA')}
                """
                
                messages = history + [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"{user_input}\n\n{event_info}"}
                ]
            else:
                system_prompt = f"""
                You are a helpful campus events chatbot. Today is {today}.
                The user has NOT requested event recommendations in their current message.
                Be helpful and conversational. Answer their questions or respond to their message naturally.
                You can offer to help them find events if they're interested, but don't push event recommendations.
                never get any events that not exists in our database.

                Keep responses brief and friendly.
                If they seem interested in events later, encourage them to ask about specific types of events.
                """
                
                messages = history + [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_input}
                ]
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=Config.OPENAI_TEMPERATURE,
                max_tokens=200
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Reply generation error: {e}")
            return "I'm having trouble generating a response right now. Please try again."

# -------------------- Event Management --------------------
class EventManager:
    """Handle event-related operations"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
    
    def query_weaviate(self, query: str, limit: int = 5) -> List[Dict]:
        """Query Weaviate for events"""
        try:
            if query.strip():
                gql = {
                    "query": f"""
                    {{
                        Get {{
                            Event(
                                nearText: {{concepts: ["{query}"]}},
                                limit: {limit}
                            ) {{
                                title
                                description
                                category
                                location
                                organizer
                                event_date
                                event_time
                            }}
                        }}
                    }}
                    """
                }
            else:
                gql = {
                    "query": f"""
                    {{
                        Get {{
                            Event(limit: {limit}) {{
                                title
                                description
                                category
                                location
                                organizer
                                event_date
                                event_time
                            }}
                        }}
                    }}
                    """
                }
            
            response = requests.post(
                f"{Config.WEAVIATE_URL}/v1/graphql",
                json=gql,
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            events = data.get("data", {}).get("Get", {}).get("Event", [])
            return events
            
        except requests.RequestException as e:
            logger.error(f"Weaviate query error: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error querying Weaviate: {e}")
            return []
    
    def get_all_events(self, filters: Dict[str, Any] = None) -> List[Dict]:
        """Get all events with optional filters"""
        try:
            query = """
                SELECT id, title, description, category, location, organizer,
                       event_date, event_time, created_at
                FROM events
                WHERE event_date >= %s
            """
            params = [datetime.date.today()]
            
            if filters:
                if filters.get('category') and filters['category'] != 'All':
                    query += " AND category = %s"
                    params.append(filters['category'])
                
                if filters.get('date_range'):
                    start, end = filters['date_range']
                    query += " AND event_date BETWEEN %s AND %s"
                    params.extend([start, end])
                
                if filters.get('keyword'):
                    keyword = f"%{filters['keyword'].lower()}%"
                    query += """ 
                        AND (LOWER(title) LIKE %s 
                        OR LOWER(location) LIKE %s 
                        OR LOWER(organizer) LIKE %s
                        OR LOWER(description) LIKE %s)
                    """
                    params.extend([keyword, keyword, keyword, keyword])
            
            query += " ORDER BY event_date ASC, event_time ASC"
            
            return self.db.execute_query(query, tuple(params), fetch=True)
            
        except Exception as e:
            logger.error(f"Error fetching events: {e}")
            return []
    
    def get_event_by_id(self, event_id: int) -> Optional[Dict]:
        """Get event by ID"""
        try:
            query = """
                SELECT id, title, description, category, location, organizer,
                       event_date, event_time, created_at
                FROM events
                WHERE id = %s
            """
            result = self.db.execute_query(query, (event_id,), fetch=True)
            return result[0] if result else None
            
        except Exception as e:
            logger.error(f"Error fetching event {event_id}: {e}")
            return None
    
    def get_categories(self) -> List[str]:
        """Get all event categories"""
        try:
            query = "SELECT DISTINCT category FROM events ORDER BY category ASC"
            result = self.db.execute_query(query, fetch=True)
            return [r['category'] for r in result if r['category']]
            
        except Exception as e:
            logger.error(f"Error fetching categories: {e}")
            return []

# -------------------- Registration Management --------------------
class RegistrationManager:
    """Handle event registration operations"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
    
    def register_for_event(self, user_id: int, event_id: int, notes: Optional[str] = None) -> Tuple[bool, str]:
        """Register user for an event"""
        try:
            # Check if already registered
            check_query = """
                SELECT id, status FROM event_registrations
                WHERE user_id = %s AND event_id = %s
            """
            existing = self.db.execute_query(check_query, (user_id, event_id), fetch=True)
            
            if existing:
                status = existing[0]['status']
                if status == RegistrationStatus.REGISTERED.value:
                    return False, "You are already registered for this event"
                elif status == RegistrationStatus.CANCELLED.value:
                    # Reactivate registration
                    update_query = """
                        UPDATE event_registrations 
                        SET status = %s, registration_date = %s
                        WHERE user_id = %s AND event_id = %s
                    """
                    self.db.execute_query(
                        update_query,
                        (RegistrationStatus.REGISTERED.value, datetime.datetime.now(), user_id, event_id),
                        fetch=False
                    )
                    return True, "Registration reactivated successfully"
            
            # New registration
            insert_query = """
                INSERT INTO event_registrations (user_id, event_id, status, notes, registration_date)
                VALUES (%s, %s, %s, %s, %s)
            """
            self.db.execute_query(
                insert_query,
                (user_id, event_id, RegistrationStatus.REGISTERED.value, notes, datetime.datetime.now()),
                fetch=False
            )
            
            logger.info(f"User {user_id} registered for event {event_id}")
            return True, "Successfully registered for the event"
            
        except Exception as e:
            logger.error(f"Registration error: {e}")
            return False, f"Registration failed: {e}"
    
    def cancel_registration(self, user_id: int, event_id: int) -> Tuple[bool, str]:
        """Cancel event registration"""
        try:
            query = """
                UPDATE event_registrations
                SET status = %s
                WHERE user_id = %s AND event_id = %s AND status = %s
            """
            result = self.db.execute_query(
                query,
                (RegistrationStatus.CANCELLED.value, user_id, event_id, RegistrationStatus.REGISTERED.value),
                fetch=False
            )
            
            if result > 0:
                logger.info(f"User {user_id} cancelled registration for event {event_id}")
                return True, "Registration cancelled successfully"
            return False, "No active registration found"
            
        except Exception as e:
            logger.error(f"Cancellation error: {e}")
            return False, f"Cancellation failed: {e}"
    
    def is_user_registered(self, user_id: int, event_id: int) -> bool:
        """Check if user is registered for an event"""
        try:
            query = """
                SELECT id FROM event_registrations
                WHERE user_id = %s AND event_id = %s AND status = %s
            """
            result = self.db.execute_query(
                query,
                (user_id, event_id, RegistrationStatus.REGISTERED.value),
                fetch=True
            )
            return len(result) > 0
            
        except Exception as e:
            logger.error(f"Registration check error: {e}")
            return False
    
    def get_user_registrations(self, user_id: int) -> List[Dict]:
        """Get all events a user is registered for"""
        try:
            query = """
                SELECT e.*, r.registration_date, r.notes
                FROM event_registrations r
                JOIN events e ON r.event_id = e.id
                WHERE r.user_id = %s AND r.status = %s
                ORDER BY e.event_date ASC
            """
            return self.db.execute_query(
                query,
                (user_id, RegistrationStatus.REGISTERED.value),
                fetch=True
            )
            
        except Exception as e:
            logger.error(f"Error fetching user registrations: {e}")
            return []

# -------------------- Session Management --------------------
class SessionManager:
    """Handle session state management"""
    
    @staticmethod
    def initialize_session():
        """Initialize session state variables"""
        defaults = {
            "authenticated": False,
            "user": None,
            "username": None,
            "history": [
                {"role": "system", "content": "You are a friendly campus events assistant."}
            ],
            "collected_interests": {"tags": [], "date_constraints": [], "location_constraints": []},
            "messages": [],
            "recommended_events": [],
            "last_recommended_event": None,
            "login_attempts": 0,
            "last_activity": datetime.datetime.now()
        }
        
        for key, value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = value
    
    @staticmethod
    def check_session_timeout():
        """Check if session has timed out"""
        if st.session_state.get("authenticated"):
            last_activity = st.session_state.get("last_activity")
            if last_activity:
                timeout = datetime.timedelta(minutes=Config.SESSION_TIMEOUT_MINUTES)
                if datetime.datetime.now() - last_activity > timeout:
                    SessionManager.logout()
                    st.warning("Session timed out. Please login again.")
                    return True
            st.session_state["last_activity"] = datetime.datetime.now()
        return False
    
    @staticmethod
    def login(user: User):
        """Set session for logged in user"""
        st.session_state["authenticated"] = True
        st.session_state["user"] = user
        st.session_state["username"] = user.username
        st.session_state["last_activity"] = datetime.datetime.now()
        st.session_state["login_attempts"] = 0
        logger.info(f"User logged in: {user.username}")
    
    @staticmethod
    def logout():
        """Clear session for logout"""
        st.session_state["authenticated"] = False
        st.session_state["user"] = None
        st.session_state["username"] = None
        st.session_state["messages"] = []
        st.session_state["history"] = [
            {"role": "system", "content": "You are a friendly campus events assistant."}
        ]
        st.session_state["collected_interests"] = {"tags": [], "date_constraints": [], "location_constraints": []}
        st.session_state["recommended_events"] = []
        logger.info("User logged out")

# -------------------- UI Components --------------------
class UIComponents:
    """Reusable UI components"""
    
    @staticmethod
    def show_event_card(event: Dict, registration_manager: RegistrationManager, user_id: Optional[int] = None):
        """Display event card with registration option"""
        with st.container():
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.markdown(f"### 🏅 {event['title']}")
                st.markdown(f"📅 **Date:** {event['event_date']} | ⏰ **Time:** {event['event_time']}")
                st.markdown(f"📍 **Location:** {event['location']}")
                
                with st.expander("View Details"):
                    st.markdown(f"**Description:** {event['description']}")
                    st.markdown(f"**Category:** {event['category']}")
                    st.markdown(f"**Organizer:** {event['organizer']}")
            
            with col2:
                if user_id:
                    is_registered = registration_manager.is_user_registered(user_id, event['id'])
                    
                    if is_registered:
                        st.success("✅ Registered")
                        if st.button(f"Cancel", key=f"cancel_{event['id']}"):
                            success, msg = registration_manager.cancel_registration(user_id, event['id'])
                            if success:
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)
                    else:
                        if st.button(f"Register", key=f"register_{event['id']}"):
                            success, msg = registration_manager.register_for_event(user_id, event['id'])
                            if success:
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)
                else:
                    st.info("Login to register")
            
            st.markdown("---")
    
    @staticmethod
    def show_auth_page(auth_manager: AuthManager):
        """Display authentication page"""
        st.title("🔑 Campus Events - Sign In")
        
        tab1, tab2 = st.tabs(["Login", "Sign Up"])
        
        with tab1:
            st.subheader("Welcome Back!")
            with st.form("login_form"):
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                col1, col2 = st.columns(2)
                with col1:
                    login_btn = st.form_submit_button("Login", use_container_width=True)
                with col2:
                    forgot_pwd = st.form_submit_button("Forgot Password?", use_container_width=True)
                
                if login_btn:
                    if st.session_state.get("login_attempts", 0) >= Config.MAX_LOGIN_ATTEMPTS:
                        st.error("Too many failed attempts. Please try again later.")
                    elif username and password:
                        success, user = auth_manager.authenticate_user(username, password)
                        if success and user:
                            SessionManager.login(user)
                            st.success(f"Welcome back, {user.full_name or user.username}!")
                            st.rerun()
                        else:
                            st.session_state["login_attempts"] = st.session_state.get("login_attempts", 0) + 1
                            st.error("Invalid credentials. Please try again.")
                    else:
                        st.error("Please enter both username and password")
                
                if forgot_pwd:
                    st.info("Password reset functionality coming soon!")
        
        with tab2:
            st.subheader("Create Your Account")
            with st.form("signup_form"):
                new_username = st.text_input("Username*")
                new_email = st.text_input("Email*")
                new_fullname = st.text_input("Full Name")
                new_password = st.text_input("Password*", type="password")
                confirm_password = st.text_input("Confirm Password*", type="password")
                
                st.caption("Password must be at least 8 characters with uppercase, lowercase, and numbers")
                
                agree = st.checkbox("I agree to the Terms of Service and Privacy Policy")
                signup_btn = st.form_submit_button("Create Account", use_container_width=True)
                
                if signup_btn:
                    if not agree:
                        st.error("Please agree to the terms to continue")
                    elif new_password != confirm_password:
                        st.error("Passwords do not match")
                    else:
                        success, msg = auth_manager.create_user(
                            new_username, new_email, new_password, new_fullname
                        )
                        if success:
                            st.success(msg)
                            st.info("Please login with your new credentials")
                        else:
                            st.error(msg)

# -------------------- Main Application --------------------
def main():
    """Main application entry point"""
    
    # Page configuration
    st.set_page_config(
        page_title="Campus Events Hub",
        page_icon="🎓",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Custom CSS
    st.markdown("""
        <style>
        .stButton > button {
            background-color: #4CAF50;
            color: white;
            border-radius: 5px;
        }
        .stButton > button:hover {
            background-color: #45a049;
        }
        .event-card {
            border: 1px solid #ddd;
            border-radius: 10px;
            padding: 15px;
            margin: 10px 0;
        }
        </style>
    """, unsafe_allow_html=True)
    
    # Initialize managers
    try:
        db_manager = get_db_manager()
        auth_manager = AuthManager(db_manager)
        ai_manager = AIManager(Config.OPENAI_API_KEY)
        event_manager = EventManager(db_manager)
        registration_manager = RegistrationManager(db_manager)
    except Exception as e:
        st.error(f"Failed to initialize application: {e}")
        st.stop()
    
    # Initialize session
    SessionManager.initialize_session()
    
    # Check session timeout
    if SessionManager.check_session_timeout():
        st.rerun()
    
    # Authentication check
    if not st.session_state.get("authenticated"):
        UIComponents.show_auth_page(auth_manager)
        return
    
    # Main application
    current_user = st.session_state.get("user")
    
    # Sidebar navigation
    with st.sidebar:
        st.title("🎓 Campus Events Hub")
        st.markdown(f"Welcome, **{current_user.full_name or current_user.username}**!")
        
        page = st.radio(
            "Navigation",
            ["🤖 AI Assistant", "📅 All Events", "✅ My Registrations", "👤 Profile"],
            key="navigation"
        )
        
        if st.button("Logout", use_container_width=True):
            SessionManager.logout()
            st.rerun()
    
    # Page routing
    if page == "🤖 AI Assistant":
        show_chatbot_page(ai_manager, event_manager, registration_manager, current_user)
    elif page == "📅 All Events":
        show_all_events_page(event_manager, registration_manager, current_user)
    elif page == "✅ My Registrations":
        show_my_registrations_page(registration_manager, event_manager, current_user)
    elif page == "👤 Profile":
        show_profile_page(current_user, auth_manager)

def show_chatbot_page(ai_manager: AIManager, event_manager: EventManager, 
                     registration_manager: RegistrationManager, user: User):
    """Display the AI chatbot page"""
    st.title("🤖 AI Event Assistant")
    st.markdown("Ask me about events, and I'll help you find the perfect ones!")
    
    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Chat input
    if user_input := st.chat_input("Ask about events..."):
        # Handle registration intents
        registration_intents = ["yes", "y", "register", "sign me up", "sure", "ok", "okay", "yes please"]
        
        # Check for specific event registration
        reg_match = re.search(r"register.*?for.*?(['\"]?)([^'\"]+)\1", user_input, re.IGNORECASE)
        if reg_match:
            event_title = reg_match.group(2).strip()
            handle_event_registration_by_title(event_title, registration_manager, user.id)
            return
        
        # Check for general registration confirmation
        if (st.session_state.get("last_recommended_event") and 
            user_input.strip().lower() in registration_intents):
            handle_last_event_registration(registration_manager, user.id)
            return
        
        # Add user message to chat
        st.session_state.messages.append({"role": "user", "content": user_input})
        st.session_state.history.append({"role": "user", "content": user_input})
        
        with st.chat_message("user"):
            st.markdown(user_input)
        
        # Check if user is actually asking for events
        event_request_keywords = [
            "event", "events", "happening", "show me", "recommend", "find", "what's on",
            "activities", "program", "schedule", "calendar", "tonight", "today", "tomorrow",
            "this week", "weekend", "party", "conference", "workshop", "seminar", "meeting",
            "concert", "festival", "exhibition", "performance", "class", "course"
        ]
        
        user_wants_events = any(keyword in user_input.lower() for keyword in event_request_keywords)
        
        if user_wants_events:
            # Extract interests and query events
            interests = ai_manager.extract_interests(user_input)
            merge_interests(interests)

            query_text = ", ".join(st.session_state.collected_interests.get("tags", []))
            events = event_manager.query_weaviate(query_text)

            # Fetch all valid events from the database (title + date)
            valid_events = event_manager.get_all_events()
            def normalize(s):
                return str(s).strip().lower() if s is not None else ""
            valid_event_keys = set(
                (normalize(e['title']), str(e['event_date'])) for e in valid_events
            )

            # Filter Weaviate results to only those that exist in the database (strict match)
            events = [
                e for e in events
                if (normalize(e.get('title')), str(e.get('event_date'))) in valid_event_keys
            ]

            # Filter out already recommended events
            recommended_keys = set(st.session_state.get("recommended_events", []))
            filtered_events = [e for e in events if f"{e['title']}|{e['event_date']}" not in recommended_keys]
        else:
            # User is not asking for events, so don't recommend any
            filtered_events = []
            interests = {"tags": [], "date_constraints": [], "location_constraints": []}
        
        # Generate AI reply
        reply = ai_manager.generate_reply(user_input, filtered_events, interests, st.session_state.history)
        
        # Add assistant message to chat
        st.session_state.messages.append({"role": "assistant", "content": reply})
        st.session_state.history.append({"role": "assistant", "content": reply})
        
        with st.chat_message("assistant"):
            st.markdown(reply)
        
        # Store recommended event only if we actually recommended one
        if filtered_events and user_wants_events:
            event = filtered_events[0]
            st.session_state["last_recommended_event"] = event
            event_key = f"{event['title']}|{event['event_date']}"
            if event_key not in st.session_state["recommended_events"]:
                st.session_state["recommended_events"].append(event_key)

def show_all_events_page(event_manager: EventManager, registration_manager: RegistrationManager, user: User):
    """Display all events page with filters"""
    st.title("📅 All Events")
    
    # Filters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        categories = event_manager.get_categories()
        category_filter = st.selectbox("Category", ["All"] + categories)
    
    with col2:
        today = datetime.date.today()
        max_date = today + datetime.timedelta(days=365)
        date_range = st.date_input("Date Range", value=(today, max_date))
    
    with col3:
        keyword = st.text_input("Search Keywords")
    
    # Build filters
    filters = {}
    if category_filter != "All":
        filters["category"] = category_filter
    if date_range:
        filters["date_range"] = date_range
    if keyword:
        filters["keyword"] = keyword
    
    # Get and display events
    events = event_manager.get_all_events(filters)
    
    if not events:
        st.info("No events found matching your criteria.")
    else:
        st.markdown(f"Found **{len(events)}** events")
        for event in events:
            UIComponents.show_event_card(event, registration_manager, user.id)

def show_my_registrations_page(registration_manager: RegistrationManager, 
                              event_manager: EventManager, user: User):
    """Display user's registered events"""
    st.title("✅ My Registrations")
    
    registrations = registration_manager.get_user_registrations(user.id)
    
    if not registrations:
        st.info("You haven't registered for any events yet.")
        if st.button("Browse Events"):
            st.session_state["navigation"] = "📅 All Events"
            st.rerun()
    else:
        st.markdown(f"You are registered for **{len(registrations)}** events")
        for reg in registrations:
            UIComponents.show_event_card(reg, registration_manager, user.id)

def show_profile_page(user: User, auth_manager: AuthManager):
    """Display user profile page"""
    st.title("👤 Profile")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.image("https://via.placeholder.com/150x150.png?text=Profile", width=150)
    
    with col2:
        st.markdown(f"**Username:** {user.username}")
        st.markdown(f"**Email:** {user.email}")
        st.markdown(f"**Full Name:** {user.full_name or 'Not provided'}")
        st.markdown("**Member Since:** Welcome to Campus Events!")
        st.markdown("**Last Login:** This session")

def handle_event_registration_by_title(event_title: str, registration_manager: RegistrationManager, user_id: int):
    """Handle registration for a specific event by title"""
    db_manager = get_db_manager()
    
    try:
        query = "SELECT id FROM events WHERE LOWER(title) = %s ORDER BY event_date ASC LIMIT 1"
        result = db_manager.execute_query(query, (event_title.lower(),), fetch=True)
        
        if result:
            event_id = result[0]['id']
            success, msg = registration_manager.register_for_event(user_id, event_id)
            
            with st.chat_message("assistant"):
                if success:
                    st.success(f"✅ {msg}")
                else:
                    st.error(f"❌ {msg}")
        else:
            with st.chat_message("assistant"):
                st.warning(f"❓ No event found with title '{event_title}'")
    except Exception as e:
        logger.error(f"Registration by title error: {e}")
        with st.chat_message("assistant"):
            st.error("Sorry, something went wrong with the registration.")

def handle_last_event_registration(registration_manager: RegistrationManager, user_id: int):
    """Handle registration for the last recommended event"""
    event = st.session_state.get("last_recommended_event")
    if not event:
        return
    
    db_manager = get_db_manager()
    
    try:
        query = "SELECT id FROM events WHERE title = %s AND event_date = %s"
        result = db_manager.execute_query(query, (event['title'], event['event_date']), fetch=True)
        
        if result:
            event_id = result[0]['id']
            success, msg = registration_manager.register_for_event(user_id, event_id)
            
            with st.chat_message("assistant"):
                if success:
                    st.success(f"✅ {msg}")
                else:
                    st.error(f"❌ {msg}")
        else:
            with st.chat_message("assistant"):
                st.warning("❓ Event not found in database")
    except Exception as e:
        logger.error(f"Last event registration error: {e}")
        with st.chat_message("assistant"):
            st.error("Sorry, something went wrong with the registration.")
    
    # Clear the last recommended event
    st.session_state["last_recommended_event"] = None

def merge_interests(new_interests: Dict[str, List[str]]):
    """Merge new interests with existing ones"""
    existing = st.session_state.collected_interests
    for key in ["tags", "date_constraints", "location_constraints"]:
        for val in new_interests.get(key, []):
            if val not in existing[key]:
                existing[key].append(val)

if __name__ == "__main__":
    main()
