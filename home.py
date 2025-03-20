import streamlit as st
import uuid
import json
from typing import List, Dict, Any
import os
import asyncio
from datetime import datetime

from output_with_guardrails_and_context import travel_agent, TravelPlan, FlightRecommendation, HotelRecommendation
from context import UserContext
from agents import Runner

# Page Configuration
st.set_page_config(
    page_title="Travel Planner Assistant",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .chat-message {
        padding: 1.5rem; 
        border-radius: 0.5rem; 
        margin-bottom: 1rem; 
        display: flex;
        flex-direction: column;
    }
    .chat-message.user {
        background-color: #e6f7ff;
        border-left: 5px solid #2196F3;
    }
    .chat-message.assistant {
        background-color: #f0f0f0;
        border-left: 5px solid #4CAF50;
    }
    .chat-message .content {
        display: flex;
        margin-top: 0.5rem;
    }
    .avatar {
        width: 40px;
        height: 40px;
        border-radius: 50%;
        object-fit: cover;
        margin-right: 1rem;
    }
    .message {
        flex: 1;
        color: #000000;
    }
    .timestamp {
        font-size: 0.8rem;
        color: #888;
        margin-top: 0.2rem;
    }
</style>
""", unsafe_allow_html=True)


# initialize session state for chat history
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

if 'thread_id' not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())

if "user_context" not in st.session_state:
    st.session_state.user_context = UserContext(
        user_id=str(uuid.uuid4())
    )

if "processing_message" not in st.session_state:
    st.session_state.processing_message = None


# Function to format agent response
def format_agent_response(output):
    # Check if output is a Pydantic model and convert to dict
    if hasattr(output, "model_dump"):
        output = output.model_dump()
    
    if isinstance(output, dict):
        # Handle structured outputs
        if "destination" in output:  # TravelPlan
            html = f"""
            <h3>Travel Plan for {output.get('destination', 'Your Trip')}</h3>
            <p><strong>Duration:</strong> {output.get('duration_days', 'N/A')} days</p>
            <p><strong>Budget:</strong> ${output.get('budget', 'N/A')}</p>
            
            <h4>Recommended Activities:</h4>
            <ul>
            """
            for activity in output.get('activities', []):
                html += f"<li>{activity}</li>"
            html += "</ul>"
            
            html += f"<p><strong>Notes:</strong> {output.get('notes', '')}</p>"
            return html
        elif "airline" in output:  # FlightRecommendation
                html = f"""
                <h3>Flight Recommendation</h3>
                <p><strong>Airline:</strong> {output.get('airline', 'N/A')}</p>
                <p><strong>Departure:</strong> {output.get('departure_time', 'N/A')}</p>
                <p><strong>Arrival:</strong> {output.get('arrival_time', 'N/A')}</p>
                <p><strong>Price:</strong> ${output.get('price', 'N/A')}</p>
                <p><strong>Direct Flight:</strong> {'Yes' if output.get('direct_flight', False) else 'No'}</p>
                <p><strong>Why this flight:</strong> {output.get('recommendation_reason', '')}</p>"""
                return html
                
        elif "name" in output and "amenities" in output:  # HotelRecommendation
            html = f"""
            <h3>Hotel Recommendation: {output.get('name', 'N/A')}</h3>
            <p><strong>Location:</strong> {output.get('location', 'N/A')}</p>
            <p><strong>Price per night:</strong> ${output.get('price_per_night', 'N/A')}</p>
            
            <h4>Amenities:</h4>
            <ul>
            """
            for amenity in output.get('amenities', []):
                html += f"<li>{amenity}</li>"
            html += "</ul>"
            
            html += f"<p><strong>Why this hotel:</strong> {output.get('recommendation_reason', '')}</p>"
            return html
    
    # Default: return as string
    return str(output)

# Function to handle user input
def handle_user_messages(user_input: str):
    # Add user message to chat history immediately
    timestamp = datetime.now().strftime("%I:%M %p")
    st.session_state.chat_history.append({
        "role": "user",
        "content": user_input,
        "timestamp": timestamp
    })
    
    # Set the message for processing in the next rerun
    st.session_state.processing_message = user_input
    
# sidebar with user preferences
with st.sidebar:
    st.header("User Preferences")
    
    st.subheader("About you")
    traveler_name = st.text_input("Your Name", value="Traveler")
    
    st.subheader("Travel Preferences")
    preferred_airlines = st.multiselect(
        "Preferred Airlines",
        options=["SkyWays", "OceanAir", "MountainJet", "Delta", "United", "American", "Southwest", "Etihad", "Emirates", "Qatar Airways"],
        default=st.session_state.user_context.preferred_airlines
    )
    
    st.subheader("Hotel Preferences")
    preferred_amenities = st.multiselect(
        "Must Have Amenities",
        options=["WiFi", "Pool", "Gym", "Free Breakfast", "Restaurant", "Spa", "Parking"],
        default=st.session_state.user_context.hotel_amenities
    )
    
    st.subheader("Budget Level")
    budget_level = st.select_slider(
        "Budget Level",
        options=["budget", "mid-range", "luxury"],
        value= st.session_state.user_context.budget_level or "mid-range",
    )
    
    if st.button("Save Preferences"):
        st.session_state.user_context.preferred_airlines = preferred_airlines
        st.session_state.user_context.hotel_amenities = preferred_amenities
        st.session_state.user_context.budget_level = budget_level
        st.success("Preferences saved!")
    
    st.divider()
    
    if st.button("Start New Conversation"):
        st.session_state.chat_history = []
        st.session_state.thread_id = str(uuid.uuid4())
        st.success("New conversation started!")
        
# Main chat interface
st.title("✈️ Travel Planner Assistant")
st.caption("Ask me about travel destinations, flight options, hotel recommendations, and more!")

# Display chat messages
for message in st.session_state.chat_history:
    with st.container():
        if message["role"] == "user":
            st.markdown(f"""
            <div class="chat-message user">
                <div class="content">
                    <img src="https://api.dicebear.com/7.x/avataaars/svg?seed={st.session_state.user_context.user_id}" class="avatar" />
                    <div class="message">
                        {message["content"]}
                        <div class="timestamp">{message["timestamp"]}</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="chat-message assistant">
                <div class="content">
                    <img src="https://api.dicebear.com/7.x/bottts/svg?seed=travel-agent" class="avatar" />
                    <div class="message">
                        {message["content"]}
                        <div class="timestamp">{message["timestamp"]}</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
                        
# User input area
user_input = st.chat_input("Ask about travel plans, flights, hotels, or anything else!")

if user_input:
    handle_user_messages(user_input)
    st.rerun()


if st.session_state.processing_message:
    user_input = st.session_state.processing_message
    st.session_state.processing_message = None
    
    # Process the message asynchronously
    with st.spinner("Processing..."):
        try:
            # Prepare the input for the agent using chat history
            if len(st.session_state.chat_history) > 1:
                input_list = []
                for msg in st.session_state.chat_history:
                    input_list.append({"role": msg["role"], "content": msg["content"]})
            else: 
                input_list = user_input

            # Run the agent with the user input
            result = asyncio.run(Runner.run(
                travel_agent,
                context= st.session_state.user_context,
                input= input_list,  
            ))
            
            # handle the agentresponse with the function created before.
            response = format_agent_response(result.final_output)
            
            # add the assistant response to the chat history
            st.session_state.chat_history.append({
                "role": "assistant",
                "content": response,
                "timestamp": datetime.now().strftime("%I:%M %p")
            })
            
        except Exception as e:
            st.error(f"An error occurred: {e}")
            st.session_state.chat_history.append({
                "role": "assistant",
                "content": f"An error occurred: {e}",
                "timestamp": datetime.now().strftime("%I:%M %p")
            })

        # force a rerun to update the chat history
        st.rerun()
        
# Footer
st.divider()
st.caption("Powered by OpenAI Agents SDK | Built with Streamlit")
st.text("Made by Hetav \"GodSpeed\" Patel")
            
            