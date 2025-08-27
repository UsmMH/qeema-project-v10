-- Event Management System Database Schema
-- Fixed creation order to resolve foreign key dependencies

-- 1. Create users table first (referenced by other tables)
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Create dcategories table
CREATE TABLE IF NOT EXISTS dcategories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL
);

-- 3. Create events table (references dcategories)
CREATE TABLE IF NOT EXISTS events (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    category VARCHAR(100),
    location VARCHAR(255),
    event_date DATE NOT NULL,
    event_time TIME NOT NULL,
    organizer VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. Create indexes for events table
CREATE INDEX IF NOT EXISTS idx_events_date ON events(event_date);
CREATE INDEX IF NOT EXISTS idx_events_category ON events(category);

-- 5. Create event_registrations table (references both users and events)
CREATE TABLE IF NOT EXISTS event_registrations (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) DEFAULT 'registered' CHECK (status IN ('registered', 'cancelled', 'waitlist')),
    email_sent BOOLEAN DEFAULT FALSE,
    email_sent_at TIMESTAMP,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, event_id) -- Prevent duplicate registrations
);

-- 6. Create indexes for event_registrations
CREATE INDEX IF NOT EXISTS idx_registrations_user_id ON event_registrations(user_id);
CREATE INDEX IF NOT EXISTS idx_registrations_event_id ON event_registrations(event_id);
CREATE INDEX IF NOT EXISTS idx_registrations_status ON event_registrations(status);
CREATE INDEX IF NOT EXISTS idx_registrations_date ON event_registrations(registration_date);

-- 7. Create user_event_registrations table (references users)
-- Note: This seems to be a duplicate of event_registrations but keeping it as in original
CREATE TABLE IF NOT EXISTS user_event_registrations (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    event_id INTEGER NOT NULL, 
    registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) DEFAULT 'registered', 
    UNIQUE(user_id, event_id)
);

-- 8. Create indexes for user_event_registrations
CREATE INDEX IF NOT EXISTS idx_user_event_registrations_user_id ON user_event_registrations(user_id);
CREATE INDEX IF NOT EXISTS idx_user_event_registrations_event_id ON user_event_registrations(event_id);

-- 9. Create trigger functions
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE OR REPLACE FUNCTION update_registration_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- 10. Create triggers
DROP TRIGGER IF EXISTS update_events_updated_at ON events;
CREATE TRIGGER update_events_updated_at
    BEFORE UPDATE ON events
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_registrations_updated_at ON event_registrations;
CREATE TRIGGER update_registrations_updated_at
    BEFORE UPDATE ON event_registrations
    FOR EACH ROW
    EXECUTE FUNCTION update_registration_updated_at();

-- 11. Set replica identity (for logical replication)
ALTER TABLE events REPLICA IDENTITY FULL;
ALTER TABLE dcategories REPLICA IDENTITY FULL;
ALTER TABLE users REPLICA IDENTITY FULL;
ALTER TABLE event_registrations REPLICA IDENTITY FULL;

-- 12. Insert sample data
INSERT INTO events (title, description, category, location, event_date, event_time, organizer) 
VALUES 
    ('Sample Event', 'This is a sample event for testing', 'Conference', 'New York', '2025-09-01', '10:00:00', 'Admin'),
    ('Workshop', 'Programming workshop', 'Education', 'Online', '2025-09-15', '14:00:00', 'Tech Team')
ON CONFLICT DO NOTHING;

-- Insert Cairo-based events
INSERT INTO events (title, description, category, location, event_date, event_time, organizer) VALUES
('Welcome Week Orientation', 'Introduction to campus life and academic programs for new students', 'Academic', 'Cairo University Main Campus, Giza', '2025-08-27', '09:00', 'Student Affairs Office'),
('Tech Innovation Summit', 'Latest trends in technology and innovation showcase', 'Technology', 'American University in Cairo, New Cairo', '2025-09-05', '10:00', 'Computer Science Department'),
('Cultural Heritage Festival', 'Celebrating Egyptian culture and traditions', 'Cultural', 'Al-Azhar Park, Islamic Cairo', '2025-09-12', '16:00', 'Cultural Committee'),
('Career Fair 2025', 'Meet top employers and explore career opportunities', 'Career', 'Cairo International Convention Center, Nasr City', '2025-09-18', '09:00', 'Career Services'),
('Sports Day Championship', 'Inter-university sports competition', 'Sports', 'Cairo Stadium, Heliopolis', '2025-09-25', '08:00', 'Sports Club'),
('Art Exhibition Opening', 'Contemporary Egyptian art showcase', 'Cultural', 'Opera House, Zamalek', '2025-10-02', '18:00', 'Fine Arts Department'),
('Entrepreneurship Workshop', 'Building your startup from idea to execution', 'Workshop', 'Tahrir Lounge, Downtown Cairo', '2025-10-10', '14:00', 'Business School'),
('Science Fair', 'Student research presentations and experiments', 'Academic', 'Egyptian Museum, Tahrir Square', '2025-10-17', '10:00', 'Science Faculty'),
('Music Concert: Cairo Beats', 'Local and international music performances', 'Entertainment', 'Cairo Opera House, Zamalek', '2025-10-24', '20:00', 'Music Society'),
('Halloween Party', 'Costume party with games and prizes', 'Social', 'Maadi Community Center, Maadi', '2025-10-31', '19:00', 'Student Union'),
('Photography Workshop', 'Learn professional photography techniques', 'Workshop', 'Khan El Khalili, Old Cairo', '2025-11-07', '09:00', 'Photography Club'),
('Book Fair', 'Literature showcase and book sales', 'Academic', 'Cairo International Book Fair Grounds, Nasr City', '2025-11-14', '10:00', 'Library Committee'),
('Coding Bootcamp', 'Intensive programming workshop', 'Technology', 'Greek Campus, Downtown Cairo', '2025-11-21', '09:00', 'IT Department'),
('Food Festival', 'International cuisine tasting event', 'Social', 'Nile Corniche, Garden City', '2025-11-28', '17:00', 'International Students Office'),
('Debate Championship', 'Inter-university debate competition', 'Academic', 'Faculty of Law, Cairo University, Giza', '2025-12-05', '14:00', 'Debate Society'),
('Winter Concert', 'Classical and modern music performances', 'Entertainment', 'Al-Azhar Mosque Complex, Islamic Cairo', '2025-12-12', '19:00', 'Music Department'),
('Gaming Tournament', 'Esports and board game competitions', 'Entertainment', 'City Center Mall, New Cairo', '2025-12-19', '12:00', 'Gaming Club'),
('New Year Celebration', 'Welcome 2026 campus party', 'Social', 'Nile Boat, Maadi Corniche', '2025-12-31', '21:00', 'Event Committee'),
('Research Symposium', 'Academic research presentations', 'Academic', 'National Research Center, Dokki', '2026-01-09', '09:00', 'Research Office'),
('Fashion Show', 'Student designer fashion showcase', 'Cultural', 'Four Seasons Hotel, Garden City', '2026-01-16', '18:00', 'Design Department'),
('Volunteer Fair', 'Community service opportunities showcase', 'Social', 'Abdeen Palace Museum, Downtown Cairo', '2026-01-23', '10:00', 'Community Service Office'),
('Language Exchange', 'Practice languages with international students', 'Academic', 'British Council, Agouza', '2026-01-30', '16:00', 'Language Center'),
('Film Festival', 'Student short films and documentaries', 'Entertainment', 'Zawya Cinema, Downtown Cairo', '2026-02-06', '18:00', 'Film Club'),
('Health & Wellness Fair', 'Health screenings and wellness workshops', 'Health', 'Medical City, Ain Shams', '2026-02-13', '09:00', 'Health Services'),
('Environmental Summit', 'Sustainability and climate change awareness', 'Academic', 'Botanical Garden, Giza', '2026-02-20', '10:00', 'Environmental Club'),
('Cultural Night', 'International students cultural presentations', 'Cultural', 'Citadel of Saladin, Old Cairo', '2026-02-27', '18:00', 'International Office'),
('Spring Sports Festival', 'Outdoor sports and activities', 'Sports', 'Al-Azhar Park, Islamic Cairo', '2026-03-06', '08:00', 'Athletic Department'),
('Technology Expo', 'Latest gadgets and tech innovations', 'Technology', 'Cairo ICT Conference Center, Smart Village', '2026-03-13', '10:00', 'Tech Society'),
('Graduation Ceremony Prep', 'Rehearsal and preparation for graduation', 'Academic', 'Cairo University Great Hall, Giza', '2026-03-20', '14:00', 'Academic Affairs'),
('Spring Break Kickoff', 'Pre-vacation celebration and activities', 'Social', 'Felucca Ride, Nile River, Maadi', '2026-03-27', '16:00', 'Student Activities')
ON CONFLICT DO NOTHING;

-- 13. Create view for registration details
CREATE OR REPLACE VIEW registration_details AS
SELECT 
    er.id as registration_id,
    er.registration_date,
    er.status,
    er.email_sent,
    er.email_sent_at,
    u.id as user_id,
    u.username,
    u.email,
    u.full_name,
    e.id as event_id,
    e.title as event_title,
    e.description as event_description,
    e.category as event_category,
    e.location as event_location,
    e.event_date,
    e.event_time,
    e.organizer
FROM event_registrations er
JOIN users u ON er.user_id = u.id
JOIN events e ON er.event_id = e.id;

-- 14. Grant privileges (assuming eventuser exists)
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO eventuser;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO eventuser;