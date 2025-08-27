
import streamlit as st

# Initialize session state early to prevent KeyError
if 'messages' not in st.session_state:
    st.session_state['messages'] = []
if "history" not in st.session_state:
    st.session_state.history = [
        {"role": "system", "content": "You are a friendly campus events assistant. You remember user preferences during the conversation and use them to recommend events."}
    ]
if "collected_interests" not in st.session_state:
    st.session_state.collected_interests = {"tags": [], "date_constraints": [], "location_constraints": []}
if "recommended_events" not in st.session_state:
    st.session_state["recommended_events"] = []

import json
import requests
import os
from openai import OpenAI
import psycopg2
import datetime
import re
# -------------------- Config --------------------

OPENAI_API_KEY = os.getenv("OPENAI_APIKEY")
# Use Docker service name for Weaviate by default
WEAVIATE_URL = os.getenv("WEAVIATE_URL", "http://weaviate:8080")

client = OpenAI(api_key=OPENAI_API_KEY)


# -------------------- Database Connection --------------------

def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "postgres"),
        dbname=os.getenv("DB_NAME", "event_management"),
        user=os.getenv("DB_USER", "eventuser"),
        password=os.getenv("DB_PASSWORD", "eventpass123"),
        port=os.getenv("DB_PORT", "5432")
    )

# -------------------- Authentication Functions --------------------
def create_user(username, email, password, full_name=None):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO users (username, email, password, full_name) VALUES (%s, %s, %s, %s)",
            (username, email, password, full_name)
        )
        conn.commit()
        return True
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        return False
    finally:
        cur.close()
        conn.close()

def authenticate_user(username, password):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM users WHERE username=%s AND password=%s",
        (username, password)
    )
    user = cur.fetchone()
    cur.close()
    conn.close()
    return user is not None

# -------------------- Extract Interests --------------------
def extract_interests(user_message):
    system_prompt = """
    Extract up to 5 interests, date/time constraints, and optional locations from the text.
    Output valid JSON only with keys: tags, date_constraints, location_constraints.
    """
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        temperature=0.7
    )
    content = resp.choices[0].message.content
    try:
        return json.loads(content)
    except:
        return {"tags": [], "date_constraints": [], "location_constraints": []}
    
def merge_interests(existing, new):
    for key in ["tags", "date_constraints", "location_constraints"]:
        for val in new.get(key, []):
            if val not in existing[key]:
                existing[key].append(val)
    return existing

def user_asked_for_events(user_input, interests):
    # If the extraction found any event-related tags or constraints
    if interests.get("tags") or interests.get("date_constraints") or interests.get("location_constraints"):
        return True
    # Optional: simple keyword check
    event_keywords = ["event", "party", "session", "conference", "seminar", "concert", "meeting", "match", "workshop"]
    return any(word in user_input.lower() for word in event_keywords)

# -------------------- Query Weaviate via GraphQL --------------------
def query_weaviate(query: str, limit: int = 5, weaviate_url: str = WEAVIATE_URL):
    if query.strip():
        gql = {"query": f"""{{ Get {{ Event(nearText: {{concepts: ["{query}"]}}, limit: {limit}) {{ title description category location organizer event_date event_time }} }} }}"""}
    else:
        gql = {"query": f"""{{ Get {{ Event(limit: {limit}) {{ title description category location organizer event_date event_time }} }} }}"""}

    try:
        r = requests.post(f"{weaviate_url}/v1/graphql", json=gql, timeout=10)
        r.raise_for_status()
        return r.json().get("data", {}).get("Get", {}).get("Event", [])
    except Exception as e:
        st.error(f"Weaviate error: {e}")
        return []

# -------------------- Generate Reply --------------------
def generate_reply(user_input, events, interests, history):
    today = datetime.date.today().isoformat()
    # Filter out already recommended events
    recommended_keys = set(st.session_state.get("recommended_events", []))
    filtered_events = [e for e in events if e and f"{e['title']}|{e['event_date']}" not in recommended_keys]
    # Stronger system prompt for strict event recommendation
    system_prompt = f"""
    Today is {today}.
    You are a helpful campus events chatbot.
    DO NOT recommend any events unless the user's CURRENT message is a direct request for events, an event, or something clearly related (like 'show me events', 'any tech events?', 'what's happening this week?').
    If the user's message is about help, interests, or changing topics, DO NOT recommend events under ANY circumstances.
    If the user says they are not interested, or asks for help with interests, or wants to change topics, DO NOT recommend events. Instead, offer to help with something else, or ask what they are interested in.
    If you are unsure, err on the side of NOT recommending events.
    Never recommend events just because you remember previous interests—only if the CURRENT message is a request for events.
    """
    if user_asked_for_events(user_input, interests):
        # Event recommendation mode
        if filtered_events:
            event = filtered_events[0]
            prompt = f"""
            {system_prompt}
            - Recommend only one event at a time.
            - After recommending, ask: 'Would you like to register for this event?'
            - Format the event details in a visually appealing way using emojis, clear labels, and line breaks. Example:

            🏅 **Event:** Tech Innovation Summit
            📅 **Date:** 2025-09-05
            ⏰ **Time:** 10:00 AM
            📍 **Location:** American University in Cairo, New Cairo
            📝 **Description:** Showcase of the latest trends in technology and innovation.
            🏷️ **Category:** Technology
            👤 **Organizer:** AUC

            - Keep replies under 80 words.
            - If the event is in the past, do not recommend it. Only recommend upcoming events.

            Event to recommend:
            Title: {event['title']}
            Description: {event['description']}
            Category: {event['category']}
            Location: {event['location']}
            Organizer: {event['organizer']}
            Date: {event['event_date']}
            Time: {event['event_time']}
            """
        else:
            prompt = f"""
            {system_prompt}
            No more new events found matching the user's interests. Suggest they try different keywords or dates.
            """
    else:
        # Chat mode (no events mentioned)
        prompt = f"""
        {system_prompt}
        The user said: "{user_input}".
        Respond naturally in a friendly chatbot style.
        Do NOT recommend or mention any events unless the user's CURRENT message is a direct request for events.
        Keep the reply short (1–2 sentences).
        """

    history_plus_prompt = history + [{"role": "user", "content": prompt}]
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=history_plus_prompt,
        temperature=0.7
    )
    # Store the recommended event key if one was recommended
    if user_asked_for_events(user_input, interests) and filtered_events:
        event = filtered_events[0]
        event_key = f"{event['title']}|{event['event_date']}"
        if event_key not in st.session_state["recommended_events"]:
            st.session_state["recommended_events"].append(event_key)
    return resp.choices[0].message.content



# -------------------- Streamlit UI --------------------
st.set_page_config(page_title="Campus Events Recommender", page_icon="🤖", layout="wide")

# -------------------- Auth UI --------------------
def show_auth_page():
    st.title("🔑 Sign Up / Log In")
    mode = st.radio("Select mode:", ["Log In", "Sign Up"])

    if mode == "Sign Up":
        st.subheader("Create a new account")
        with st.form("signup_form"):
            new_user = st.text_input("Username")
            new_email = st.text_input("Email")
            new_full_name = st.text_input("Full Name (optional)")
            new_pass = st.text_input("Password", type="password")
            confirm_pass = st.text_input("Confirm Password", type="password")
            signup_btn = st.form_submit_button("Sign Up")

            if signup_btn:
                if new_pass != confirm_pass:
                    st.error("⚠️ Passwords do not match")
                elif new_user.strip() == "" or new_pass.strip() == "" or new_email.strip() == "":
                    st.error("⚠️ Please fill all required fields")
                else:
                    success = create_user(new_user, new_email, new_pass, new_full_name)
                    if success:
                        st.success("✅ Account created successfully! Please log in.")
                    else:
                        st.error("⚠️ Username or email already exists")

    elif mode == "Log In":
        st.subheader("Log in to your account")
        with st.form("login_form"):
            user = st.text_input("Username")
            passwd = st.text_input("Password", type="password")
            login_btn = st.form_submit_button("Log In")

            if login_btn:
                if authenticate_user(user, passwd):
                    st.session_state["authenticated"] = True
                    st.session_state["username"] = user
                    st.success(f"✅ Welcome back, {user}!")
                    st.rerun()
                else:
                    st.error("❌ Invalid username or password")

# --- Main App Routing ---
if "authenticated" not in st.session_state or not st.session_state["authenticated"]:
    show_auth_page()
    st.stop()

# --- Sidebar navigation: Chatbot or All Events ---
page = st.sidebar.radio("Navigation", ["🤖 Chatbot", "📅 All Events"])

def is_user_registered(user_id, event_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id FROM event_registrations 
        WHERE user_id = %s AND event_id = %s AND status = 'registered'
    """, (user_id, event_id))
    result = cur.fetchone()
    cur.close()
    conn.close()
    return result is not None

def register_for_event(user_id, event_id, notes=None):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO event_registrations (user_id, event_id, notes) 
            VALUES (%s, %s, %s)
        """, (user_id, event_id, notes))
        conn.commit()
        return True
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        return False  # Already registered
    except Exception as e:
        conn.rollback()
        st.error(f"Registration failed: {e}")
        return False
    finally:
        cur.close()
        conn.close()

if page == "📅 All Events":
    st.header("All Upcoming Events")
    # --- Filters ---
    conn = get_connection()
    cur = conn.cursor()
    # Get all categories for filter dropdown
    cur.execute("SELECT DISTINCT category FROM events ORDER BY category ASC")
    categories = [row[0] for row in cur.fetchall() if row[0]]
    category_filter = st.selectbox("Category", ["All"] + categories)
    # Date range filter
    today = datetime.date.today()
    min_date = today
    cur.execute("SELECT MIN(event_date), MAX(event_date) FROM events WHERE event_date >= %s", (today,))
    min_event_date, max_event_date = cur.fetchone()
    if not min_event_date:
        min_event_date = today
    if not max_event_date:
        max_event_date = today
    date_range = st.date_input("Date range", (min_event_date, max_event_date))
    # Keyword filter
    keyword = st.text_input("Search by keyword (title, location, organizer)")
    # --- Query with filters ---
    query = "SELECT id, title, description, category, location, organizer, event_date, event_time FROM events WHERE event_date >= %s"
    params = [today]
    if category_filter != "All":
        query += " AND category = %s"
        params.append(category_filter)
    if date_range:
        start_date, end_date = date_range if isinstance(date_range, tuple) else (date_range, date_range)
        query += " AND event_date BETWEEN %s AND %s"
        params.extend([start_date, end_date])
    if keyword.strip():
        query += " AND (LOWER(title) LIKE %s OR LOWER(location) LIKE %s OR LOWER(organizer) LIKE %s)"
        kw = f"%{keyword.lower()}%"
        params.extend([kw, kw, kw])
    query += " ORDER BY event_date ASC"
    cur.execute(query, params)
    all_events = cur.fetchall()
    cur.close()
    conn.close()
    if not all_events:
        st.info("No upcoming events found.")
    else:
        for event in all_events:
            event_id, title, description, category, location, organizer, event_date, event_time = event
            with st.container():
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"**🏅 {title}**")
                    st.markdown(f"📅 **Date:** {event_date} | ⏰ **Time:** {event_time}")
                    st.markdown(f"📍 **Location:** {location}")
                    st.markdown(f"📝 **Description:** {description}")
                    st.markdown(f"🏷️ **Category:** {category}")
                    st.markdown(f"👤 **Organizer:** {organizer}")
                with col2:
                    user_id = None
                    if st.session_state.get("username"):
                        conn2 = get_connection()
                        cur2 = conn2.cursor()
                        cur2.execute("SELECT id FROM users WHERE username=%s", (st.session_state["username"],))
                        user = cur2.fetchone()
                        cur2.close()
                        conn2.close()
                        user_id = user[0] if user else None
                    if user_id:
                        if is_user_registered(user_id, event_id):
                            st.success("Registered")
                        else:
                            if st.button(f"Register for {title} on {event_date}", key=f"register_all_{event_id}"):
                                register_for_event(user_id, event_id)
                                st.success("Registered!")
                    else:
                        st.info("Login to register")
                st.markdown("---")

elif page == "🤖 Chatbot":
    st.title("🎓 Campus Events Chatbot ")


    # Session state already initialized at top of file
    
    # Show previous messages
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])


    def get_postgres_event_id(title, event_date):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM events WHERE title=%s AND event_date=%s", (title, event_date))
        row = cur.fetchone()
        cur.close()
        conn.close()
        return row[0] if row else None

    # New user input
    if user_input := st.chat_input("Ask about events..."):
        # Registration intent detection (before generating reply)
        registration_intents = ["yes", "y", "register", "sign me up", "sure", "ok", "okay", "yes please", "yeah"]
        # 1. Check for registration by event title
        reg_title_match = re.search(r"register (me )?(for|to)? ([\w\s\-']+)", user_input, re.IGNORECASE)
        if reg_title_match:
            event_title = reg_title_match.group(3).strip()
            # Try to find the event by title (latest upcoming event with that title)
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("SELECT id, event_date FROM events WHERE LOWER(title) = %s ORDER BY event_date ASC", (event_title.lower(),))
            event_row = cur.fetchone()
            cur.close()
            conn.close()
            if event_row:
                event_id, event_date = event_row
                user_id = None
                if st.session_state.get("username"):
                    conn = get_connection()
                    cur = conn.cursor()
                    cur.execute("SELECT id FROM users WHERE username=%s", (st.session_state["username"],))
                    user = cur.fetchone()
                    cur.close()
                    conn.close()
                    user_id = user[0] if user else None
                with st.chat_message("assistant"):
                    if user_id:
                        if is_user_registered(user_id, event_id):
                            st.success(f"You are already registered for '{event_title}'.")
                        else:
                            register_for_event(user_id, event_id)
                            st.success(f"You have been registered for '{event_title}'!")
                    else:
                        st.info("Login to register.")
            else:
                with st.chat_message("assistant"):
                    st.warning(f"No event found with the title '{event_title}'. Please check the event name.")
            # Do not process further (skip AI reply)
        # 2. Normal registration intent for last recommended event
        elif (
            st.session_state.get("last_recommended_event")
            and user_input.strip().lower() in registration_intents
        ):
            user_id = None
            if st.session_state.get("username"):
                conn = get_connection()
                cur = conn.cursor()
                cur.execute("SELECT id FROM users WHERE username=%s", (st.session_state["username"],))
                user = cur.fetchone()
                cur.close()
                conn.close()
                user_id = user[0] if user else None
            event = st.session_state["last_recommended_event"]
            event_id = get_postgres_event_id(event["title"], event["event_date"])
            with st.chat_message("assistant"):
                if user_id and event_id:
                    if is_user_registered(user_id, event_id):
                        st.success("You are already registered for this event.")
                    else:
                        register_for_event(user_id, event_id)
                        st.success("You have been registered for the event!")
                elif user_id and not event_id:
                    st.warning("Registration not available: Event not found in database.")
                else:
                    st.info("Login to register.")
            del st.session_state["last_recommended_event"]
            # Do not process further (skip AI reply)
        else:
            st.session_state.messages.append({"role": "user", "content": user_input})
            st.session_state.history.append({"role": "user", "content": user_input})
            with st.chat_message("user"):
                st.markdown(user_input)
            new_interests = extract_interests(user_input)
            st.session_state.collected_interests = merge_interests(st.session_state.collected_interests, new_interests)
            query_text = ", ".join(st.session_state.collected_interests.get("tags", []))
            events = query_weaviate(query_text)
            # Filter out already recommended events
            recommended_keys = set(st.session_state.get("recommended_events", []))
            filtered_events = [e for e in events if f"{e['title']}|{e['event_date']}" not in recommended_keys]
            # Store the event to be recommended (or None)
            event_to_recommend = filtered_events[0] if filtered_events else None
            if event_to_recommend:
                st.session_state["last_recommended_event"] = event_to_recommend
            else:
                st.session_state.pop("last_recommended_event", None)
            # Generate reply using only the event_to_recommend
            reply = generate_reply(user_input, [event_to_recommend] if event_to_recommend else [], st.session_state.collected_interests, st.session_state.history)
            st.session_state.messages.append({"role": "assistant", "content": reply})
            st.session_state.history.append({"role": "assistant", "content": reply})
            with st.chat_message("assistant"):
                st.markdown(reply)



