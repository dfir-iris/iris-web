#!/usr/bin/env python3
"""
Debug script to check what the events API actually returns
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'tests'))
from iris import Iris

def debug_events_api():
    iris = Iris()
    
    print("Creating dummy case...")
    case_identifier = iris.create_dummy_case()
    print(f"Case created with ID: {case_identifier}")
    
    print("\nCreating event...")
    body = {
        'event_title': 'title', 
        'event_category_id': 1,
        'event_date': '2025-03-26T00:00:00.000', 
        'event_tz': '+00:00',
        'event_assets': [], 
        'event_iocs': []
    }
    
    # Get the raw response first
    raw_response = iris.create(f'/api/v2/cases/{case_identifier}/events', body)
    print(f"Raw response status: {raw_response.status_code}")
    print(f"Raw response headers: {dict(raw_response.headers)}")
    
    try:
        json_response = raw_response.json()
        print(f"JSON response: {json_response}")
        print(f"Response keys: {list(json_response.keys()) if isinstance(json_response, dict) else 'Not a dict'}")
        
        # Check for different possible key names
        possible_keys = ['event_id', 'id', 'data', 'event']
        for key in possible_keys:
            if isinstance(json_response, dict) and key in json_response:
                print(f"Found key '{key}': {json_response[key]}")
                
    except Exception as e:
        print(f"Failed to parse JSON: {e}")
        print(f"Raw response text: {raw_response.text}")

if __name__ == "__main__":
    debug_events_api()