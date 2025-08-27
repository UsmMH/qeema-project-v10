import streamlit as st
import requests
import pandas as pd
import os
from datetime import datetime, date, time
from typing import Optional, List, Dict, Any

# API configuration
API_URL = os.getenv("API_URL", "http://localhost:8000")

class EventAPIClient:
    def __init__(self, base_url: str):
        self.base_url = base_url
        
    def _handle_response(self, response: requests.Response) -> Any:
        """Handle API response and errors"""
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 201:
            return response.json()
        elif response.status_code == 404:
            st.error("Event not found")
            return None
        else:
            st.error(f"API Error: {response.status_code} - {response.text}")
            return None
    
    def health_check(self) -> bool:
        """Check if API is healthy"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False
    
    def create_event(self, event_data: Dict) -> bool:
        """Create a new event"""
        try:
            response = requests.post(f"{self.base_url}/events", json=event_data)
            result = self._handle_response(response)
            return result is not None
        except requests.exceptions.RequestException as e:
            st.error(f"Connection error: {str(e)}")
            return False
    
    def get_events(self, category: Optional[str] = None, search: Optional[str] = None) -> List[Dict]:
        """Get all events with optional filters"""
        try:
            params = {}
            if category and category != 'All':
                params['category'] = category
            if search:
                params['search'] = search
                
            response = requests.get(f"{self.base_url}/events", params=params)
            result = self._handle_response(response)
            return result if result is not None else []
        except requests.exceptions.RequestException as e:
            st.error(f"Connection error: {str(e)}")
            return []
    
    def get_event(self, event_id: int) -> Optional[Dict]:
        """Get a specific event by ID"""
        try:
            response = requests.get(f"{self.base_url}/events/{event_id}")
            return self._handle_response(response)
        except requests.exceptions.RequestException as e:
            st.error(f"Connection error: {str(e)}")
            return None
    
    def update_event(self, event_id: int, event_data: Dict) -> bool:
        """Update an existing event"""
        try:
            response = requests.put(f"{self.base_url}/events/{event_id}", json=event_data)
            result = self._handle_response(response)
            return result is not None
        except requests.exceptions.RequestException as e:
            st.error(f"Connection error: {str(e)}")
            return False
    
    def delete_event(self, event_id: int) -> bool:
        """Delete an event"""
        try:
            response = requests.delete(f"{self.base_url}/events/{event_id}")
            result = self._handle_response(response)
            return result is not None
        except requests.exceptions.RequestException as e:
            st.error(f"Connection error: {str(e)}")
            return False
    
    def get_categories(self) -> List[str]:
        """Get all unique categories"""
        try:
            response = requests.get(f"{self.base_url}/events/categories/list")
            result = self._handle_response(response)
            return result if result else []
        except requests.exceptions.RequestException as e:
            st.error(f"Connection error: {str(e)}")
            return []

# Initialize API client
api_client = EventAPIClient(API_URL)

def main():
    st.set_page_config(page_title="Event Management System", page_icon="📅", layout="wide")
    
    # Check API health
    if not api_client.health_check():
        st.error("🔴 Backend API is not available. Please check if the backend service is running.")
        st.stop()
    else:
        st.success("🟢 Connected to backend API")
    
    st.title("📅 Event Management System")
    st.markdown("---")
    
    # Sidebar menu
    st.sidebar.title("Menu")
    menu_option = st.sidebar.radio(
        "Select an option:",
        ["Add Event", "View Events", "Update Event", "Delete Event"]
    )
    
    if menu_option == "Add Event":
        st.header("Add New Event")
        # Fetch categories from backend
        categories = api_client.get_categories()
        if not categories:
            categories = []
        st.markdown("#### Add a new category if not listed")
        with st.form("add_category_form"):
            new_category = st.text_input("New Category Name", placeholder="e.g., Conference, Workshop")
            add_cat_btn = st.form_submit_button("Add Category", type="secondary")
            if add_cat_btn and new_category:
                resp = requests.post(f"{API_URL}/events/categories/add", json={"name": new_category})
                if resp.status_code == 201:
                    st.success(f"Category '{new_category}' added!")
                    st.rerun()
                else:
                    st.error(f"Failed to add category: {resp.json().get('detail', 'Unknown error')}")
        st.markdown("---")
        with st.form("add_event_form"):
            col1, col2 = st.columns(2)
            with col1:
                title = st.text_input("Title*", placeholder="Enter event title")
                category = st.selectbox("Category*", categories)
                event_date = st.date_input("Date*", value=datetime.now().date())
                organizer = st.text_input("Organizer", placeholder="Event organizer name")
            with col2:
                location = st.text_input("Location", placeholder="Event location")
                event_time = st.time_input("Time*", value=time(9, 0))
            description = st.text_area("Description", placeholder="Event description (optional)")
            submitted = st.form_submit_button("Add Event", type="primary")
            if submitted:
                if title and event_date and event_time and category:
                    event_data = {
                        "title": title,
                        "description": description if description else None,
                        "category": category,
                        "location": location if location else None,
                        "event_date": event_date.isoformat(),
                        "event_time": event_time.strftime("%H:%M:%S"),
                        "organizer": organizer if organizer else None
                    }
                    if api_client.create_event(event_data):
                        st.success("✅ Event added successfully!")
                        st.rerun()
                    else:
                        st.error("❌ Failed to add event. Please try again.")
                else:
                    st.error("❌ Please fill in all required fields (marked with *)")
    
    elif menu_option == "View Events":
        st.header("All Events")
        
        # Get available categories
        categories = ['All'] + api_client.get_categories()
        
        # Filters
        col1, col2, col3 = st.columns(3)
        
        with col1:
            selected_category = st.selectbox("Filter by Category", categories)
        
        with col2:
            # Note: Date filtering would need to be implemented in the backend
            st.info("Date filtering available in backend API")
        
        with col3:
            search_term = st.text_input("Search in Title/Description")
        
        # Get events with filters
        events = api_client.get_events(
            category=selected_category if selected_category != 'All' else None,
            search=search_term if search_term else None
        )
        
        if events:
            st.markdown(f"**Total Events:** {len(events)}")
            
            # Display events
            for event in events:
                with st.expander(f"📅 {event['title']} - {event['event_date']} at {event['event_time']}"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write(f"**Category:** {event['category'] or 'N/A'}")
                        st.write(f"**Location:** {event['location'] or 'N/A'}")
                        st.write(f"**Organizer:** {event['organizer'] or 'N/A'}")
                    
                    with col2:
                        st.write(f"**Date:** {event['event_date']}")
                        st.write(f"**Time:** {event['event_time']}")
                        st.write(f"**Created:** {event['created_at'][:16]}")
                    
                    if event['description']:
                        st.write(f"**Description:** {event['description']}")
        else:
            st.info("No events found. Add some events to get started!")
    
    elif menu_option == "Update Event":
        st.header("Update Event")
        
        events = api_client.get_events()
        if events:
            # Select event to update
            event_options = {f"{event['title']} - {event['event_date']}": event for event in events}
            selected_event_key = st.selectbox("Select Event to Update", list(event_options.keys()))
            
            if selected_event_key:
                event = event_options[selected_event_key]
                
                with st.form("update_event_form"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        title = st.text_input("Title*", value=event['title'])
                        category = st.text_input("Category", value=event['category'] or '')
                        event_date = st.date_input("Date*", 
                                                 value=datetime.fromisoformat(event['event_date']).date())
                        organizer = st.text_input("Organizer", value=event['organizer'] or '')
                    
                    with col2:
                        location = st.text_input("Location", value=event['location'] or '')
                        # Parse time string (format: HH:MM:SS)
                        time_parts = event['event_time'].split(':')
                        event_time_obj = time(int(time_parts[0]), int(time_parts[1]))
                        event_time = st.time_input("Time*", value=event_time_obj)
                    
                    description = st.text_area("Description", value=event['description'] or '')
                    
                    updated = st.form_submit_button("Update Event", type="primary")
                    
                    if updated:
                        if title and event_date and event_time:
                            event_data = {
                                "title": title,
                                "description": description if description else None,
                                "category": category if category else None,
                                "location": location if location else None,
                                "event_date": event_date.isoformat(),
                                "event_time": event_time.strftime("%H:%M:%S"),
                                "organizer": organizer if organizer else None
                            }
                            
                            if api_client.update_event(event['id'], event_data):
                                st.success("✅ Event updated successfully!")
                                st.rerun()
                            else:
                                st.error("❌ Failed to update event. Please try again.")
                        else:
                            st.error("❌ Please fill in all required fields (marked with *)")
        else:
            st.info("No events available to update.")
    
    elif menu_option == "Delete Event":
        st.header("Delete Event")
        
        events = api_client.get_events()
        if events:
            # Select event to delete
            event_options = {f"{event['title']} - {event['event_date']}": event for event in events}
            selected_event_key = st.selectbox("Select Event to Delete", list(event_options.keys()))
            
            if selected_event_key:
                event = event_options[selected_event_key]
                
                st.warning(f"Are you sure you want to delete: **{event['title']}**?")
                st.write(f"Date: {event['event_date']}")
                st.write(f"Time: {event['event_time']}")
                
                if st.button("🗑️ Delete Event", type="secondary"):
                    if api_client.delete_event(event['id']):
                        st.success("✅ Event deleted successfully!")
                        st.rerun()
                    else:
                        st.error("❌ Failed to delete event. Please try again.")
        else:
            st.info("No events available to delete.")

    # API Information in sidebar
    st.sidebar.markdown("---")
    st.sidebar.markdown("### API Information")
    st.sidebar.text(f"Backend: {API_URL}")
    if api_client.health_check():
        st.sidebar.success("✅ API Connected")
    else:
        st.sidebar.error("❌ API Disconnected")

if __name__ == "__main__":
    main()