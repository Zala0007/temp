"""
Flask API Server - All data derived exclusively from uploaded Excel
No defaults, no assumptions, no fallback values
"""

import os
import json
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename
from data_parser import ExcelDataParser
from optimizer import ClinkerOptimizer, optimizer

app = Flask(__name__)
CORS(app)

# Configuration
UPLOAD_FOLDER = Path(__file__).parent / 'uploads'
UPLOAD_FOLDER.mkdir(exist_ok=True)
ALLOWED_EXTENSIONS = {'xlsx', 'xls', 'csv'}
DATA_FOLDER = Path(__file__).parent.parent  # Parent folder with CSV files

app.config['UPLOAD_FOLDER'] = str(UPLOAD_FOLDER)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max

# Global parser instance
parser = ExcelDataParser()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ============================================================================
# HEALTH CHECK
# ============================================================================

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy',
        'data_loaded': parser.is_loaded,
        'message': 'All insights derived exclusively from uploaded dataset'
    })


# ============================================================================
# DATA UPLOAD & LOADING
# ============================================================================

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Upload Excel or CSV file - system rebuilds itself from this data"""
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No file selected'}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Detect file type and parse accordingly
        file_ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
        
        if file_ext == 'csv':
            # Single CSV file - parse it as a specific data sheet
            result = parser.load_single_csv(filepath, filename)
        else:
            # Excel file with multiple sheets
            result = parser.load_from_excel(filepath)
        
        # Load data into optimizer
        if result['success']:
            optimizer.load_data(parser.data)
        
        return jsonify({
            'success': result['success'],
            'filename': filename,
            'file_type': 'csv' if file_ext == 'csv' else 'excel',
            'errors': result['errors'],
            'metadata': result['metadata'],
            'message': 'System reconfigured from uploaded dataset' if result['success'] else 'Failed to parse file'
        })
    
    return jsonify({'success': False, 'error': 'Invalid file type. Supported: .xlsx, .xls, .csv'}), 400


@app.route('/api/upload-multiple', methods=['POST'])
def upload_multiple_files():
    """Upload multiple CSV files - each file maps to a data sheet"""
    if 'files' not in request.files:
        return jsonify({'success': False, 'error': 'No files provided'}), 400
    
    files = request.files.getlist('files')
    if not files or all(f.filename == '' for f in files):
        return jsonify({'success': False, 'error': 'No files selected'}), 400
    
    # Save all files to upload folder
    saved_files = []
    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            saved_files.append(filepath)
    
    if not saved_files:
        return jsonify({'success': False, 'error': 'No valid files uploaded'}), 400
    
    # Parse all CSV files from the upload folder
    result = parser.load_from_folder(str(UPLOAD_FOLDER))
    
    # Load data into optimizer
    if result['success']:
        optimizer.load_data(parser.data)
    
    return jsonify({
        'success': result['success'],
        'files_count': len(saved_files),
        'errors': result['errors'],
        'metadata': result['metadata'],
        'message': f'System reconfigured from {len(saved_files)} uploaded files' if result['success'] else 'Failed to parse files'
    })


@app.route('/api/load-folder', methods=['POST'])
def load_from_folder():
    """Load data from CSV files in a folder"""
    data = request.get_json() or {}
    folder_path = data.get('folder_path', str(DATA_FOLDER))
    
    result = parser.load_from_folder(folder_path)
    
    # Load data into optimizer
    if result['success']:
        optimizer.load_data(parser.data)
    
    return jsonify({
        'success': result['success'],
        'errors': result['errors'],
        'metadata': result['metadata'],
        'message': 'System reconfigured from dataset folder' if result['success'] else 'Failed to load data'
    })


@app.route('/api/load-default', methods=['POST'])
def load_default_data():
    """Load data from the default CSV files in the project folder"""
    result = parser.load_from_folder(str(DATA_FOLDER))
    
    # Load data into optimizer
    if result['success']:
        optimizer.load_data(parser.data)
    
    return jsonify({
        'success': result['success'],
        'errors': result['errors'],
        'metadata': result['metadata'],
        'message': 'System configured from default dataset' if result['success'] else 'Failed to load data'
    })


# ============================================================================
# METADATA & DROPDOWNS (STRICTLY FROM EXCEL)
# ============================================================================

@app.route('/api/metadata', methods=['GET'])
def get_metadata():
    """Get all metadata derived from Excel"""
    if not parser.is_loaded:
        return jsonify({
            'success': False,
            'error': 'No dataset loaded. Please upload an Excel file first.',
            'data_loaded': False
        }), 400
    
    return jsonify({
        'success': True,
        'data_loaded': True,
        'metadata': parser.metadata,
        'note': 'All values derived exclusively from uploaded dataset'
    })


@app.route('/api/sources', methods=['GET'])
def get_sources():
    """Get valid source IUs - ONLY from Excel"""
    if not parser.is_loaded:
        return jsonify({
            'success': False,
            'error': 'No dataset loaded',
            'sources': []
        }), 400
    
    return jsonify({
        'success': True,
        'sources': parser.metadata.get('source_ius', []),
        'note': 'Source plants discovered dynamically from uploaded dataset'
    })


@app.route('/api/destinations/<source>', methods=['GET'])
def get_destinations(source):
    """Get valid destinations for a source - FILTERED by Excel"""
    if not parser.is_loaded:
        return jsonify({
            'success': False,
            'error': 'No dataset loaded',
            'destinations': []
        }), 400
    
    # Validate source exists
    if source not in parser.metadata.get('source_ius', []):
        return jsonify({
            'success': False,
            'error': f'Source "{source}" not found in uploaded dataset',
            'destinations': []
        }), 400
    
    destinations = parser.get_destinations_for_source(source)
    
    return jsonify({
        'success': True,
        'source': source,
        'destinations': destinations,
        'count': len(destinations),
        'note': 'Destinations filtered by source from uploaded dataset'
    })


@app.route('/api/modes/<source>/<destination>', methods=['GET'])
def get_transport_modes(source, destination):
    """Get valid transport modes for a route - STRICTLY from Excel"""
    if not parser.is_loaded:
        return jsonify({
            'success': False,
            'error': 'No dataset loaded',
            'modes': []
        }), 400
    
    # Validate route
    validation = parser.validate_selection(source=source, destination=destination)
    if not validation['valid']:
        return jsonify({
            'success': False,
            'errors': validation['errors'],
            'modes': []
        }), 400
    
    modes = parser.get_modes_for_route(source, destination)
    
    # Add mode details
    mode_details = []
    for mode in modes:
        detail = {'code': mode}
        if mode in parser.TRANSPORT_INFO:
            detail['name'] = parser.TRANSPORT_INFO[mode]['name']
            detail['vehicle_capacity'] = parser.TRANSPORT_INFO[mode]['vehicle_capacity']
        else:
            detail['name'] = mode
            detail['vehicle_capacity'] = 'Not available'
        mode_details.append(detail)
    
    return jsonify({
        'success': True,
        'source': source,
        'destination': destination,
        'modes': mode_details,
        'note': 'Transport modes available for this route in uploaded dataset'
    })


@app.route('/api/periods', methods=['GET'])
def get_periods():
    """Get available periods - ONLY from Excel"""
    if not parser.is_loaded:
        return jsonify({
            'success': False,
            'error': 'No dataset loaded',
            'periods': []
        }), 400
    
    return jsonify({
        'success': True,
        'periods': parser.metadata.get('periods', []),
        'note': 'Periods extracted from uploaded dataset - no assumptions'
    })


# ============================================================================
# ROUTE INSIGHTS (COMPUTED FROM EXCEL ONLY)
# ============================================================================

@app.route('/api/route', methods=['GET'])
def get_route_data():
    """Get all insights for a route - computed from Excel only using optimizer"""
    if not parser.is_loaded:
        return jsonify({
            'success': False,
            'error': 'No dataset loaded'
        }), 400
    
    source = request.args.get('source')
    destination = request.args.get('destination')
    mode = request.args.get('mode')
    period = request.args.get('period', type=int)
    
    if not all([source, destination, mode, period]):
        return jsonify({
            'success': False,
            'error': 'Missing parameters: source, destination, mode, period required'
        }), 400
    
    # Validate selection
    validation = parser.validate_selection(source, destination, mode, period)
    if not validation['valid']:
        return jsonify({
            'success': False,
            'errors': validation['errors'],
            'data': None
        }), 400
    
    # Use optimizer to calculate MILP solution
    route_data = optimizer.get_all_data_for_route(source, destination, mode, period)
    
    return jsonify({
        'success': True,
        **route_data,
        'note': 'All values derived exclusively from uploaded dataset'
    })


@app.route('/api/model', methods=['GET'])
def get_mathematical_model():
    """Get the mathematical optimization model formulation"""
    model = optimizer.get_mathematical_model()
    summary = optimizer.get_model_summary() if optimizer.is_loaded else {}
    
    return jsonify({
        'success': True,
        'model': model,
        'summary': summary
    })


@app.route('/api/validate', methods=['POST'])
def validate_selection():
    """Validate a user selection against Excel data"""
    if not parser.is_loaded:
        return jsonify({
            'success': False,
            'error': 'No dataset loaded'
        }), 400
    
    data = request.get_json() or {}
    
    validation = parser.validate_selection(
        source=data.get('source'),
        destination=data.get('destination'),
        mode=data.get('mode'),
        period=data.get('period')
    )
    
    return jsonify({
        'success': True,
        'validation': validation
    })


# ============================================================================
# ANALYTICS (ALL COMPUTED FROM EXCEL)
# ============================================================================

@app.route('/api/analytics/demand', methods=['GET'])
def get_demand_analytics():
    """Get demand analytics - computed from Excel"""
    if not parser.is_loaded:
        return jsonify({
            'success': False,
            'error': 'No dataset loaded'
        }), 400
    
    summary = parser.get_demand_summary()
    
    return jsonify({
        'success': True,
        'data': summary,
        'note': 'Demand analytics computed from uploaded dataset'
    })


@app.route('/api/analytics/capacity', methods=['GET'])
def get_capacity_analytics():
    """Get capacity analytics - computed from Excel"""
    if not parser.is_loaded:
        return jsonify({
            'success': False,
            'error': 'No dataset loaded'
        }), 400
    
    summary = parser.get_capacity_summary()
    
    return jsonify({
        'success': True,
        'data': summary,
        'note': 'Capacity analytics computed from uploaded dataset'
    })


@app.route('/api/analytics/routes', methods=['GET'])
def get_routes_analytics():
    """Get routes summary - from Excel"""
    if not parser.is_loaded:
        return jsonify({
            'success': False,
            'error': 'No dataset loaded'
        }), 400
    
    routes = parser.get_all_routes_summary()
    
    return jsonify({
        'success': True,
        'data': routes,
        'count': len(routes),
        'note': 'Routes summary from uploaded dataset'
    })


@app.route('/api/analytics/inventory', methods=['GET'])
def get_inventory_analytics():
    """Get inventory analytics - from Excel"""
    if not parser.is_loaded:
        return jsonify({
            'success': False,
            'error': 'No dataset loaded'
        }), 400
    
    if 'OpeningStock' not in parser.data or 'ClosingStock' not in parser.data:
        return jsonify({
            'success': False,
            'error': 'Inventory data not available in uploaded dataset'
        }), 400
    
    opening_df = parser.data['OpeningStock']
    closing_df = parser.data['ClosingStock']
    
    inventory_data = []
    for _, row in opening_df.iterrows():
        plant = row['IUGU CODE']
        plant_data = {
            'plant': plant,
            'opening_stock': float(row['OPENING STOCK']),
            'periods': {}
        }
        
        for period in parser.metadata.get('periods', []):
            closing_match = closing_df[(closing_df['IUGU CODE'] == plant) & 
                                       (closing_df['TIME PERIOD'] == period)]
            if not closing_match.empty:
                cr = closing_match.iloc[0]
                plant_data['periods'][period] = {
                    'min_close_stock': float(cr['MIN CLOSE STOCK']) if pd.notna(cr['MIN CLOSE STOCK']) else None,
                    'max_close_stock': float(cr['MAX CLOSE STOCK']) if pd.notna(cr['MAX CLOSE STOCK']) else None
                }
        
        inventory_data.append(plant_data)
    
    return jsonify({
        'success': True,
        'data': inventory_data,
        'note': 'Inventory data from uploaded dataset'
    })


@app.route('/api/data/raw/<sheet_name>', methods=['GET'])
def get_raw_data(sheet_name):
    """Get raw data from a specific sheet"""
    if not parser.is_loaded:
        return jsonify({
            'success': False,
            'error': 'No dataset loaded'
        }), 400
    
    if sheet_name not in parser.data:
        return jsonify({
            'success': False,
            'error': f'Sheet "{sheet_name}" not found in uploaded dataset',
            'available_sheets': list(parser.data.keys())
        }), 400
    
    df = parser.data[sheet_name]
    
    return jsonify({
        'success': True,
        'sheet': sheet_name,
        'columns': df.columns.tolist(),
        'row_count': len(df),
        'data': df.head(100).to_dict('records'),
        'note': 'Raw data from uploaded dataset (first 100 rows)'
    })


# ============================================================================
# PLANT DETAILS
# ============================================================================

@app.route('/api/plant/<plant_code>', methods=['GET'])
def get_plant_details(plant_code):
    """Get all details for a specific plant from Excel"""
    if not parser.is_loaded:
        return jsonify({
            'success': False,
            'error': 'No dataset loaded'
        }), 400
    
    # Check if plant exists
    all_plants = parser.metadata.get('plants', [])
    if plant_code not in all_plants:
        return jsonify({
            'success': False,
            'error': f'Plant "{plant_code}" not found in uploaded dataset'
        }), 400
    
    plant_data = {
        'code': plant_code,
        'type': None,
        'capacity': {},
        'production_cost': {},
        'demand': {},
        'opening_stock': None,
        'closing_stock': {},
        'outbound_routes': [],
        'inbound_routes': []
    }
    
    # Get plant type
    if 'IUGUType' in parser.data:
        type_match = parser.data['IUGUType'][parser.data['IUGUType']['IUGU CODE'] == plant_code]
        if not type_match.empty:
            plant_data['type'] = type_match.iloc[0]['PLANT TYPE']
    
    # Get capacity (IU only)
    if 'Capacity' in parser.data:
        cap_df = parser.data['Capacity']
        cap_match = cap_df[cap_df['IU CODE'] == plant_code]
        for _, row in cap_match.iterrows():
            plant_data['capacity'][int(row['TIME PERIOD'])] = float(row['CAPACITY'])
    
    # Get production cost (IU only)
    if 'ProductionCost' in parser.data:
        cost_df = parser.data['ProductionCost']
        cost_match = cost_df[cost_df['IU CODE'] == plant_code]
        for _, row in cost_match.iterrows():
            plant_data['production_cost'][int(row['TIME PERIOD'])] = float(row['PRODUCTION COST'])
    
    # Get demand
    if 'Demand' in parser.data:
        demand_df = parser.data['Demand']
        demand_match = demand_df[demand_df['IUGU CODE'] == plant_code]
        for _, row in demand_match.iterrows():
            plant_data['demand'][int(row['TIME PERIOD'])] = float(row['DEMAND'])
    
    # Get opening stock
    if 'OpeningStock' in parser.data:
        stock_df = parser.data['OpeningStock']
        stock_match = stock_df[stock_df['IUGU CODE'] == plant_code]
        if not stock_match.empty:
            plant_data['opening_stock'] = float(stock_match.iloc[0]['OPENING STOCK'])
    
    # Get closing stock constraints
    if 'ClosingStock' in parser.data:
        close_df = parser.data['ClosingStock']
        close_match = close_df[close_df['IUGU CODE'] == plant_code]
        for _, row in close_match.iterrows():
            period = int(row['TIME PERIOD'])
            plant_data['closing_stock'][period] = {
                'min': float(row['MIN CLOSE STOCK']) if pd.notna(row['MIN CLOSE STOCK']) else None,
                'max': float(row['MAX CLOSE STOCK']) if pd.notna(row['MAX CLOSE STOCK']) else None
            }
    
    # Get routes
    if 'Logistics' in parser.data:
        log_df = parser.data['Logistics']
        # Outbound
        outbound = log_df[log_df['FROM IU CODE'] == plant_code][['TO IUGU CODE', 'TRANSPORT CODE']].drop_duplicates()
        plant_data['outbound_routes'] = outbound.to_dict('records')
        # Inbound
        inbound = log_df[log_df['TO IUGU CODE'] == plant_code][['FROM IU CODE', 'TRANSPORT CODE']].drop_duplicates()
        plant_data['inbound_routes'] = inbound.to_dict('records')
    
    return jsonify({
        'success': True,
        'data': plant_data,
        'note': 'Plant details from uploaded dataset'
    })


# Need pandas import for inventory endpoint
import pandas as pd


# ============================================================================
# RUN SERVER
# ============================================================================

if __name__ == '__main__':
    # Auto-load default data on startup
    print("Loading default dataset...")
    result = parser.load_from_folder(str(DATA_FOLDER))
    if result['success']:
        print(f"✓ Loaded {len(parser.data)} data sheets")
        print(f"✓ Found {len(parser.metadata.get('source_ius', []))} source IUs")
        print(f"✓ Found {len(parser.metadata.get('periods', []))} periods")
        # Load into optimizer
        optimizer.load_data(parser.data)
    else:
        print(f"✗ Failed to load: {result['errors']}")
    
    print("\nStarting API server...")
    print("All insights will be derived exclusively from the loaded dataset.\n")
    
    # Use debug=False to prevent reloader issues
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
