#!/usr/bin/env python3

"""
Web interface for validating single LLM transition model predictions.

This Flask app presents individual transition predictions and allows users
to judge plausibility and categorize errors.
"""

import json
import random
import datetime
import os
from pathlib import Path
from typing import Dict, List, Any, Optional

from flask import Flask, render_template, request, jsonify, redirect, url_for
import argparse

app = Flask(__name__)

class ValidationManager:
    """Manages the validation data and error categorization process."""
    
    def __init__(self, data_file: str, results_dir: str = "validation_results", session_name: str = None, random_seed: int = None):
        self.data_file = data_file
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(exist_ok=True)
        
        # Create session-based filename
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_name = session_name
        self.random_seed = random_seed
        if session_name:
            self.session_id = f"{session_name}_{timestamp}"
            self.session_file = self.results_dir / f"validation_session_{session_name}_{timestamp}.json"
        else:
            self.session_id = timestamp
            self.session_file = self.results_dir / f"validation_session_{timestamp}.json"
        
        self.transitions = []
        self.current_transitions = []
        self.completed_transitions = set()
        self.session_validations = []
        
        self.error_categories = [
            {
                "id": "materials_missing",
                "label": "Missing Expected Materials",
                "description": "Expected materials were not predicted"
            },
            {
                "id": "materials_incorrect",
                "label": "Incorrect Material Properties",
                "description": "Material properties don't match expected values"
            },
            {
                "id": "materials_extra",
                "label": "Unexpected Materials",
                "description": "Materials predicted that shouldn't exist"
            },
            {
                "id": "observations_missing",
                "label": "Missing Expected Observations",
                "description": "Expected observations were not predicted"
            },
            {
                "id": "observations_incorrect",
                "label": "Incorrect Observation Values",
                "description": "Observation values don't match expected results"
            },
            {
                "id": "observations_extra",
                "label": "Unexpected Observations",
                "description": "Observations predicted that shouldn't occur"
            },
            {
                "id": "timing_wrong",
                "label": "Incorrect Timing",
                "description": "Events predicted at wrong time points"
            },
            {
                "id": "physical_impossible",
                "label": "Physically Impossible",
                "description": "Predictions violate physical laws or constraints"
            },
            {
                "id": "reasoning_flawed",
                "label": "Flawed Reasoning",
                "description": "Logical errors in the model's reasoning"
            },
            {
                "id": "context_ignored",
                "label": "Context Ignored",
                "description": "Model ignored important contextual information"
            }
        ]
        
        self._load_data()
        self._build_material_lookup()
        self._randomize_transitions()
        self._initialize_session_file()
    
    def _load_data(self):
        """Load the transition validation data."""
        with open(self.data_file, 'r') as f:
            data = json.load(f)
        
        # Extract individual predictions from comparison data
        if 'comparisons' in data:
            for comparison in data['comparisons']:
                for i, prediction in enumerate(comparison['predictions']):
                    if not prediction.get('error'):
                        transition = {
                            'transition_id': f"{comparison['transition_id']}_{i}",
                            'original_transition_id': comparison['transition_id'],
                            'prediction_index': i,
                            'action': comparison['action'],
                            'input_materials': comparison['input_materials'],
                            'input_observations': comparison['input_observations'],
                            'prediction': prediction
                        }
                        self.transitions.append(transition)
        else:
            # Handle direct transition data format
            self.transitions = data.get('transitions', [])
        
        self.metadata = data.get('metadata', {})
        print(f"Loaded {len(self.transitions)} transitions for validation")
    
    def _build_material_lookup(self):
        """Build a lookup table from barcode to material name."""
        self.material_lookup = {}
        
        for transition in self.transitions:
            # Build lookup from input materials
            if transition.get('input_materials'):
                for material in transition['input_materials']:
                    if 'barcode' in material and 'name' in material:
                        self.material_lookup[material['barcode']] = material['name']
            
            # Also check predicted materials for any additional mappings
            pred_materials = transition.get('prediction', {}).get('prediction', {}).get('new_materials', [])
            for material in pred_materials:
                if 'barcode' in material and 'name' in material:
                    self.material_lookup[material['barcode']] = material['name']
        
        print(f"Built material lookup table with {len(self.material_lookup)} entries")
    
    def _randomize_transitions(self):
        """Randomize the order of transitions for validation."""
        # Set random seed for reproducible results across reviewers
        if self.random_seed is not None:
            random.seed(self.random_seed)
            print(f"Using random seed: {self.random_seed} for reproducible order")
        
        self.current_transitions = self.transitions.copy()
        random.shuffle(self.current_transitions)
        print(f"Randomized order of {len(self.current_transitions)} transitions")
    
    def _initialize_session_file(self):
        """Initialize the session validation file."""
        session_data = {
            'session_id': self.session_id,
            'session_name': self.session_name,
            'random_seed': self.random_seed,
            'start_time': datetime.datetime.now().isoformat(),
            'source_data_file': self.data_file,
            'total_transitions': len(self.current_transitions),
            'metadata': self.metadata,
            'error_categories': self.error_categories,
            'validations': []
        }
        
        with open(self.session_file, 'w') as f:
            json.dump(session_data, f, indent=2)
        
        print(f"Initialized validation session file: {self.session_file}")
    
    @classmethod
    def resume_from_session(cls, session_file_path: str, data_file: str = None):
        """Resume validation from an existing session file."""
        session_path = Path(session_file_path)
        if not session_path.exists():
            raise FileNotFoundError(f"Session file not found: {session_file_path}")
        
        # Load existing session data
        with open(session_path, 'r') as f:
            session_data = json.load(f)
        
        # Use data file from session if not provided
        if data_file is None:
            data_file = session_data.get('source_data_file')
            if not data_file or not os.path.exists(data_file):
                raise FileNotFoundError("Original data file not found, please specify with --data-file")
        
        # Create new instance
        session_name = session_data.get('session_name')
        random_seed = session_data.get('random_seed', 42)
        results_dir = session_path.parent
        
        instance = cls.__new__(cls)
        instance.data_file = data_file
        instance.results_dir = results_dir
        instance.session_name = session_name
        instance.random_seed = random_seed
        instance.session_id = session_data['session_id']
        instance.session_file = session_path
        
        # Initialize required attributes
        instance.transitions = []
        instance.current_transitions = []
        instance.completed_transitions = set()
        instance.session_validations = []
        
        # Load error categories
        instance.error_categories = session_data.get('error_categories', [])
        
        # Load and setup transitions
        instance._load_data()
        instance._build_material_lookup()
        instance._randomize_transitions()
        
        # Restore completed transitions and validations
        instance.session_validations = session_data.get('validations', [])
        instance.completed_transitions = set()
        for validation in instance.session_validations:
            instance.completed_transitions.add(validation['transition_id'])
        
        print(f"Resumed session from: {session_path}")
        print(f"Progress: {len(instance.completed_transitions)}/{len(instance.current_transitions)} completed")
        
        return instance
    
    def get_next_transition(self) -> Optional[Dict[str, Any]]:
        """Get the next transition to validate."""
        for transition in self.current_transitions:
            if transition['transition_id'] not in self.completed_transitions:
                # Add material lookup information to the transition
                enhanced_transition = self._enhance_transition_with_names(transition)
                return enhanced_transition
        return None
    
    def _enhance_transition_with_names(self, transition: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance transition data by replacing barcodes with names in action parameters."""
        enhanced = transition.copy()
        
        # Create a copy of action parameters with resolved names
        if 'action' in enhanced and 'parameters' in enhanced['action']:
            enhanced_params = {}
            for key, value in enhanced['action']['parameters'].items():
                enhanced_params[key] = self._resolve_barcode_to_name(value)
            
            enhanced['action'] = enhanced['action'].copy()
            enhanced['action']['parameters'] = enhanced_params
            enhanced['action']['parameters_display'] = enhanced_params  # Keep original for display
        
        return enhanced
    
    def _resolve_barcode_to_name(self, value):
        """Recursively resolve barcodes to names in nested data structures."""
        if isinstance(value, str):
            # Check if this looks like a barcode and we have a mapping for it
            return self.material_lookup.get(value, value)
        elif isinstance(value, list):
            return [self._resolve_barcode_to_name(item) for item in value]
        elif isinstance(value, dict):
            return {k: self._resolve_barcode_to_name(v) for k, v in value.items()}
        else:
            return value
    
    def save_validation(self, transition_id: str, is_plausible: bool, 
                       error_categories: List[str], custom_error: str = "",
                       comments: str = "", confidence: int = None, transition_data: Dict = None) -> None:
        """Save a validation result to the session file."""
        validation_result = {
            'transition_id': transition_id,
            'timestamp': datetime.datetime.now().isoformat(),
            'is_plausible': is_plausible,
            'error_categories': error_categories,
            'custom_error': custom_error,
            'comments': comments,
            'confidence': confidence,
            'transition_data': transition_data,
            'prediction_config': transition_data.get('prediction', {}).get('config', {}) if transition_data else {}
        }
        
        self.session_validations.append(validation_result)
        self._update_session_file()
        self.completed_transitions.add(transition_id)
        
        status = "plausible" if is_plausible else f"implausible ({len(error_categories)} errors)"
        print(f"Saved validation for {transition_id}: {status}")
    
    def _update_session_file(self):
        """Update the session file with current validations."""
        with open(self.session_file, 'r') as f:
            session_data = json.load(f)
        
        session_data['validations'] = self.session_validations
        session_data['last_updated'] = datetime.datetime.now().isoformat()
        session_data['completed_transitions'] = len(self.completed_transitions)
        session_data['progress_percentage'] = (len(self.completed_transitions) / len(self.current_transitions)) * 100 if self.current_transitions else 0
        
        with open(self.session_file, 'w') as f:
            json.dump(session_data, f, indent=2)
    
    def get_progress(self) -> Dict[str, int]:
        """Get current progress statistics."""
        return {
            'completed': len(self.completed_transitions),
            'total': len(self.current_transitions),
            'remaining': len(self.current_transitions) - len(self.completed_transitions)
        }

# Global manager instance
manager = None

@app.route('/')
def index():
    """Main page showing current transition validation."""
    transition = manager.get_next_transition()
    
    if not transition:
        return render_template('validation_completed.html', 
                             progress=manager.get_progress())
    
    return render_template('validate.html', 
                         transition=transition,
                         error_categories=manager.error_categories,
                         progress=manager.get_progress())

@app.route('/validate', methods=['POST'])
def validate():
    """Handle validation submission."""
    data = request.json
    
    transition_id = data['transition_id']
    is_plausible = data['is_plausible']
    error_categories = data.get('error_categories', [])
    custom_error = data.get('custom_error', '')
    comments = data.get('comments', '')
    confidence = data.get('confidence')
    transition_data = data.get('transition_data')
    
    manager.save_validation(transition_id, is_plausible, error_categories, 
                          custom_error, comments, confidence, transition_data)
    
    return jsonify({'status': 'success'})

@app.route('/skip', methods=['POST'])
def skip():
    """Skip current transition."""
    data = request.json
    transition_id = data['transition_id']
    manager.completed_transitions.add(transition_id)
    return jsonify({'status': 'success'})

@app.route('/progress')
def progress():
    """Get current progress."""
    return jsonify(manager.get_progress())

def main():
    parser = argparse.ArgumentParser(description='Web interface for validating LLM transitions')
    parser.add_argument('--data-file', '-d', default='./transition_comparisons.json',
                      help='JSON file containing transition data')
    parser.add_argument('--results-dir', '-r', default='./validation_results',
                      help='Directory to save validation results')
    parser.add_argument('--port', '-p', type=int, default=5001,
                      help='Port to run web server on')
    parser.add_argument('--host', default='127.0.0.1',
                      help='Host to run web server on')
    parser.add_argument('--session-name', '-s',
                      help='Session name for organizing results (will be included in filename)')
    parser.add_argument('--resume-session', '-R',
                      help='Resume from existing validation session file (e.g., validation_session_20241201_143022.json)')
    parser.add_argument('--random-seed', default=42, type=int,
                      help='Random seed for reproducible ordering across reviewers (e.g., 42)')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.data_file):
        print(f"Error: Data file {args.data_file} not found")
        print("Please prepare transition data first")
        return
    
    # Initialize manager
    global manager
    if args.resume_session:
        manager = ValidationManager.resume_from_session(args.resume_session, args.data_file)
    else:
        manager = ValidationManager(args.data_file, args.results_dir, args.session_name, args.random_seed)
    
    # Add custom filter to truncate reasoning at SECRET:
    @app.template_filter('truncate_at_secret')
    def truncate_at_secret(text):
        if not text:
            return text
        secret_pos = text.find("SECRET:")
        if secret_pos != -1:
            return text[:secret_pos].strip()
        return text
    
    print(f"Starting validation interface on http://{args.host}:{args.port}")
    print(f"Press Ctrl+C to stop")
    
    app.run(host=args.host, port=args.port, debug=True)

if __name__ == "__main__":
    main()