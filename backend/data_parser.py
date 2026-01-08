"""
Excel Data Parser - Dynamically parses uploaded Excel/CSV files
All data is derived exclusively from the uploaded dataset - NO defaults, NO assumptions
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Any, Optional
import json

class ExcelDataParser:
    """
    Parser that treats Excel as the single source of truth.
    If data is not in Excel, it does not exist in the system.
    """
    
    # Expected sheet names and their column mappings
    SHEET_CONFIG = {
        'IUGUType': {
            'file': 'IUGUType.csv',
            'columns': ['IUGU CODE', 'PLANT TYPE'],
            'required': True
        },
        'Logistics': {
            'file': 'LogisticsIUGU.csv', 
            'columns': ['FROM IU CODE', 'TO IUGU CODE', 'TRANSPORT CODE', 'TIME PERIOD', 
                       'FREIGHT COST', 'HANDLING COST', 'QUANTITY MULTIPLIER'],
            'required': True
        },
        'Demand': {
            'file': 'ClinkerDemand.csv',
            'columns': ['IUGU CODE', 'TIME PERIOD', 'DEMAND'],
            'required': True
        },
        'Capacity': {
            'file': 'ClinkerCapacity.csv',
            'columns': ['IU CODE', 'TIME PERIOD', 'CAPACITY'],
            'required': True
        },
        'ProductionCost': {
            'file': 'ProductionCost.csv',
            'columns': ['IU CODE', 'TIME PERIOD', 'PRODUCTION COST'],
            'required': True
        },
        'OpeningStock': {
            'file': 'IUGUOpeningStock.csv',
            'columns': ['IUGU CODE', 'OPENING STOCK'],
            'required': True
        },
        'ClosingStock': {
            'file': 'IUGUClosingStock.csv',
            'columns': ['IUGU CODE', 'TIME PERIOD', 'MIN CLOSE STOCK', 'MAX CLOSE STOCK'],
            'required': True
        },
        'Constraints': {
            'file': 'IUGUConstraint.csv',
            'columns': ['IU CODE', 'TRANSPORT CODE', 'IUGU CODE', 'TIME PERIOD', 
                       'BOUND TYPEID', 'VALUE TYPEID', 'Value'],
            'required': False
        },
        'HubOpeningStock': {
            'file': 'HubOpeningStock.csv',
            'columns': ['IU', 'IUGU', 'Opening Stock'],
            'required': False
        }
    }
    
    # Transport mode info (only used if mode exists in Excel)
    TRANSPORT_INFO = {
        'T1': {'name': 'Road', 'vehicle_capacity': 30, 'emission_factor': 0.062},
        'T2': {'name': 'Rail', 'vehicle_capacity': 3000, 'emission_factor': 0.022},
        'T3': {'name': 'Sea', 'vehicle_capacity': 10000, 'emission_factor': 0.010}
    }
    
    def __init__(self):
        self.data: Dict[str, pd.DataFrame] = {}
        self.metadata: Dict[str, Any] = {}
        self.is_loaded = False
        self.load_errors: List[str] = []
    
    def load_from_folder(self, folder_path: str) -> Dict[str, Any]:
        """Load all CSV files from a folder"""
        self.data = {}
        self.metadata = {}
        self.load_errors = []
        
        folder = Path(folder_path)
        
        for sheet_name, config in self.SHEET_CONFIG.items():
            file_path = folder / config['file']
            if file_path.exists():
                try:
                    df = pd.read_csv(file_path)
                    # Clean column names
                    df.columns = df.columns.str.strip()
                    self.data[sheet_name] = df
                except Exception as e:
                    if config['required']:
                        self.load_errors.append(f"Failed to load {config['file']}: {str(e)}")
            elif config['required']:
                self.load_errors.append(f"Required file missing: {config['file']}")
        
        if not self.load_errors:
            self.is_loaded = True
            self._extract_metadata()
        
        return {
            'success': len(self.load_errors) == 0,
            'errors': self.load_errors,
            'metadata': self.metadata if self.is_loaded else {}
        }
    
    def load_single_csv(self, csv_path: str, filename: str) -> Dict[str, Any]:
        """
        Single CSV upload is NOT allowed. 
        User must upload an Excel file with all required sheets OR use the default CSV folder.
        """
        required_sheets = [name for name, config in self.SHEET_CONFIG.items() if config['required']]
        
        return {
            'success': False,
            'errors': [
                '❌ Single CSV file upload is not supported.',
                '',
                '📋 Please upload an Excel file (.xlsx) containing ALL required sheets:',
                f"   Required sheets: {', '.join(required_sheets)}",
                '',
                'OR use the "Load Default Data" option to load from the CSV files in the project folder.',
                '',
                '💡 Tip: Create an Excel file with multiple sheets, each sheet containing one of the required data tables.'
            ],
            'metadata': {}
        }
    
    def validate_complete_dataset(self) -> Dict[str, Any]:
        """Validate that all required data sheets are loaded"""
        required_sheets = {name: config for name, config in self.SHEET_CONFIG.items() if config['required']}
        missing = []
        present = []
        
        for sheet_name, config in required_sheets.items():
            if sheet_name in self.data:
                present.append(sheet_name)
            else:
                missing.append(sheet_name)
        
        return {
            'complete': len(missing) == 0,
            'present': present,
            'missing': missing,
            'total_required': len(required_sheets),
            'loaded_count': len(present)
        }
    
    def _map_filename_to_sheet(self, filename: str) -> Optional[str]:
        """Map a CSV filename to a sheet name"""
        filename_lower = filename.lower().replace('.csv', '')
        
        # Direct mappings
        mappings = {
            'iugutype': 'IUGUType',
            'logisticsiugu': 'Logistics',
            'logistics': 'Logistics',
            'clinkerdemand': 'Demand',
            'demand': 'Demand',
            'clinkercapacity': 'Capacity',
            'capacity': 'Capacity',
            'productioncost': 'ProductionCost',
            'iuguopeningstock': 'OpeningStock',
            'openingstock': 'OpeningStock',
            'iuguclosingstock': 'ClosingStock',
            'closingstock': 'ClosingStock',
            'iuguconstraint': 'Constraints',
            'constraint': 'Constraints',
            'constraints': 'Constraints',
            'hubopeningstock': 'HubOpeningStock'
        }
        
        return mappings.get(filename_lower)
    
    def _detect_sheet_from_columns(self, df: pd.DataFrame) -> Optional[str]:
        """Auto-detect sheet type based on column names"""
        cols = set(col.upper() for col in df.columns)
        
        # Check for Logistics columns
        if 'FROM IU CODE' in cols and 'TO IUGU CODE' in cols and 'FREIGHT COST' in cols:
            return 'Logistics'
        
        # Check for Demand columns
        if 'DEMAND' in cols and 'IUGU CODE' in cols:
            return 'Demand'
        
        # Check for Capacity columns
        if 'CAPACITY' in cols and 'IU CODE' in cols:
            return 'Capacity'
        
        # Check for ProductionCost columns
        if 'PRODUCTION COST' in cols and 'IU CODE' in cols:
            return 'ProductionCost'
        
        # Check for OpeningStock columns
        if 'OPENING STOCK' in cols and 'IUGU CODE' in cols:
            return 'OpeningStock'
        
        # Check for ClosingStock columns
        if ('MIN CLOSE STOCK' in cols or 'MAX CLOSE STOCK' in cols) and 'IUGU CODE' in cols:
            return 'ClosingStock'
        
        # Check for Constraints columns
        if 'BOUND TYPEID' in cols and 'VALUE TYPEID' in cols:
            return 'Constraints'
        
        # Check for IUGUType columns
        if 'PLANT TYPE' in cols and 'IUGU CODE' in cols:
            return 'IUGUType'
        
        return None
    
    def load_from_excel(self, excel_path: str) -> Dict[str, Any]:
        """Load data from a single Excel file with multiple sheets.
        STRICT VALIDATION: File must contain ALL 7 required sheets with correct structure.
        """
        self.data = {}
        self.metadata = {}
        self.load_errors = []
        validation_errors = []
        missing_sheets = []
        invalid_columns = []
        
        try:
            excel_file = pd.ExcelFile(excel_path)
            sheet_names = excel_file.sheet_names
            
            # First pass: Check all required sheets exist
            required_sheets = {name: config for name, config in self.SHEET_CONFIG.items() if config['required']}
            
            for sheet_name, config in self.SHEET_CONFIG.items():
                # Try to match sheet name (case-insensitive)
                matched_sheet = None
                for s in sheet_names:
                    if s.lower() == sheet_name.lower() or s.lower() == config['file'].replace('.csv', '').lower():
                        matched_sheet = s
                        break
                
                if matched_sheet:
                    try:
                        df = pd.read_excel(excel_file, sheet_name=matched_sheet)
                        df.columns = df.columns.str.strip()
                        
                        # Validate required columns exist
                        if config['required']:
                            df_cols_upper = set(col.upper() for col in df.columns)
                            required_cols = config['columns']
                            missing_cols = [col for col in required_cols if col.upper() not in df_cols_upper]
                            
                            if missing_cols:
                                invalid_columns.append(f"Sheet '{matched_sheet}' missing columns: {', '.join(missing_cols)}")
                            else:
                                self.data[sheet_name] = df
                        else:
                            self.data[sheet_name] = df
                            
                    except Exception as e:
                        if config['required']:
                            validation_errors.append(f"Failed to read sheet '{matched_sheet}': {str(e)}")
                elif config['required']:
                    missing_sheets.append(f"{sheet_name} (expected: {config['file'].replace('.csv', '')})")
            
            # Build comprehensive error message
            if missing_sheets:
                self.load_errors.append(f"❌ Missing required sheets: {', '.join(missing_sheets)}")
            
            if invalid_columns:
                for err in invalid_columns:
                    self.load_errors.append(f"❌ {err}")
            
            if validation_errors:
                for err in validation_errors:
                    self.load_errors.append(f"❌ {err}")
            
            # Only mark as loaded if ALL required sheets are present and valid
            if not self.load_errors:
                self.is_loaded = True
                self._extract_metadata()
            else:
                # Provide helpful message about required structure
                self.load_errors.append("")
                self.load_errors.append("📋 Required sheets and columns:")
                for sheet_name, config in required_sheets.items():
                    self.load_errors.append(f"  • {sheet_name} ({config['file']}): {', '.join(config['columns'])}")
                
        except Exception as e:
            self.load_errors.append(f"❌ Failed to open Excel file: {str(e)}")
        
        return {
            'success': len([e for e in self.load_errors if e.startswith('❌')]) == 0,
            'errors': self.load_errors,
            'metadata': self.metadata if self.is_loaded else {},
            'sheets_found': list(self.data.keys()),
            'sheets_required': list(required_sheets.keys())
        }
    
    def _extract_metadata(self):
        """Extract all metadata dynamically from the loaded data"""
        
        # Extract plant types
        if 'IUGUType' in self.data:
            df = self.data['IUGUType']
            self.metadata['plants'] = df['IUGU CODE'].unique().tolist()
            self.metadata['iu_plants'] = df[df['PLANT TYPE'] == 'IU']['IUGU CODE'].unique().tolist()
            self.metadata['gu_plants'] = df[df['PLANT TYPE'] == 'GU']['IUGU CODE'].unique().tolist()
        
        # Extract source IUs from Logistics (FROM IU CODE) - will filter later
        if 'Logistics' in self.data:
            df = self.data['Logistics']
            all_sources = df['FROM IU CODE'].unique().tolist()
            self.metadata['all_destinations'] = df['TO IUGU CODE'].unique().tolist()
            self.metadata['transport_modes'] = df['TRANSPORT CODE'].unique().tolist()
            # Will be filtered after all data is loaded
            self.metadata['source_ius'] = all_sources
        
        # Extract periods
        if 'Logistics' in self.data:
            self.metadata['periods'] = sorted(self.data['Logistics']['TIME PERIOD'].unique().tolist())
        elif 'Demand' in self.data:
            self.metadata['periods'] = sorted(self.data['Demand']['TIME PERIOD'].unique().tolist())
        
        # Count records
        self.metadata['record_counts'] = {
            sheet: len(df) for sheet, df in self.data.items()
        }
        
        # Build route index for quick lookup
        if 'Logistics' in self.data:
            self._build_route_index()
        
        # Filter sources to only those with at least one valid destination
        self._filter_sources_with_complete_data()
    
    def _filter_sources_with_complete_data(self):
        """Filter source_ius to only sources that have at least one destination with complete data"""
        if 'source_ius' not in self.metadata:
            return
        
        all_sources = self.metadata.get('source_ius', [])
        valid_sources = []
        
        for source in all_sources:
            destinations = self.get_destinations_for_source(source)
            if destinations:  # Has at least one valid destination
                valid_sources.append(source)
        
        self.metadata['source_ius'] = valid_sources
        self.metadata['all_sources_count'] = len(all_sources)
        self.metadata['valid_sources_count'] = len(valid_sources)
    
    def _build_route_index(self):
        """Build an index of valid routes from Logistics data"""
        df = self.data['Logistics']
        
        # Routes by source
        self.metadata['routes_by_source'] = {}
        for source in df['FROM IU CODE'].unique():
            source_df = df[df['FROM IU CODE'] == source]
            destinations = source_df['TO IUGU CODE'].unique().tolist()
            self.metadata['routes_by_source'][source] = destinations
        
        # Modes by route
        self.metadata['modes_by_route'] = {}
        for _, row in df[['FROM IU CODE', 'TO IUGU CODE', 'TRANSPORT CODE']].drop_duplicates().iterrows():
            route_key = f"{row['FROM IU CODE']}_{row['TO IUGU CODE']}"
            if route_key not in self.metadata['modes_by_route']:
                self.metadata['modes_by_route'][route_key] = []
            if row['TRANSPORT CODE'] not in self.metadata['modes_by_route'][route_key]:
                self.metadata['modes_by_route'][route_key].append(row['TRANSPORT CODE'])
    
    def get_destinations_for_source(self, source_iu: str) -> List[str]:
        """Get valid destinations for a given source IU - only pairs with COMPLETE data"""
        if not self.is_loaded or 'Logistics' not in self.data:
            return []
        
        df = self.data['Logistics']
        all_destinations = df[df['FROM IU CODE'] == source_iu]['TO IUGU CODE'].unique().tolist()
        
        # Filter to only destinations with complete data for MILP
        valid_destinations = []
        for dest in all_destinations:
            if self._has_complete_data(source_iu, dest):
                valid_destinations.append(dest)
        
        return valid_destinations
    
    def _has_complete_data(self, source: str, destination: str) -> bool:
        """Check if a source-destination pair has all required data for MILP calculations"""
        # 1. Must have logistics data (freight cost)
        if 'Logistics' not in self.data:
            return False
        logistics_df = self.data['Logistics']
        route_data = logistics_df[(logistics_df['FROM IU CODE'] == source) & 
                                   (logistics_df['TO IUGU CODE'] == destination)]
        if route_data.empty:
            return False
        
        # Check freight cost exists and is valid
        freight = route_data['FREIGHT COST'].iloc[0] if 'FREIGHT COST' in route_data.columns else None
        if freight is None or (isinstance(freight, float) and pd.isna(freight)):
            return False
        
        # 2. Must have production cost for source (stored as 'ProductionCost', column is 'IU CODE')
        if 'ProductionCost' in self.data:
            prod_df = self.data['ProductionCost']
            # Try both column names
            if 'IU CODE' in prod_df.columns:
                source_prod = prod_df[prod_df['IU CODE'] == source]
            elif 'IUGU CODE' in prod_df.columns:
                source_prod = prod_df[prod_df['IUGU CODE'] == source]
            else:
                return False
            if source_prod.empty:
                return False
        else:
            return False
        
        # 3. Must have capacity for source (stored as 'Capacity', column is 'IU CODE')
        if 'Capacity' in self.data:
            cap_df = self.data['Capacity']
            # Try both column names
            if 'IU CODE' in cap_df.columns:
                source_cap = cap_df[cap_df['IU CODE'] == source]
            elif 'IUGU CODE' in cap_df.columns:
                source_cap = cap_df[cap_df['IUGU CODE'] == source]
            else:
                return False
            if source_cap.empty:
                return False
        else:
            return False
        
        # 4. Must have demand for destination (stored as 'Demand', column is 'IUGU CODE')
        if 'Demand' in self.data:
            demand_df = self.data['Demand']
            dest_demand = demand_df[demand_df['IUGU CODE'] == destination] if 'IUGU CODE' in demand_df.columns else pd.DataFrame()
            if dest_demand.empty:
                return False
        else:
            return False
        
        return True
    
    def get_modes_for_route(self, source: str, destination: str) -> List[str]:
        """Get valid transport modes for a given route - strictly from Excel"""
        if not self.is_loaded or 'Logistics' not in self.data:
            return []
        
        df = self.data['Logistics']
        modes = df[(df['FROM IU CODE'] == source) & 
                   (df['TO IUGU CODE'] == destination)]['TRANSPORT CODE'].unique().tolist()
        return modes
    
    def get_route_data(self, source: str, destination: str, mode: str, period: int) -> Dict[str, Any]:
        """Get all data for a specific route - strictly from Excel"""
        if not self.is_loaded:
            return {'exists': False, 'error': 'Data not loaded'}
        
        result = {
            'exists': False,
            'source': source,
            'destination': destination,
            'mode': mode,
            'period': period
        }
        
        # Check if route exists in Logistics
        if 'Logistics' not in self.data:
            result['error'] = 'Logistics data not available in uploaded dataset'
            return result
        
        logistics_df = self.data['Logistics']
        route_data = logistics_df[
            (logistics_df['FROM IU CODE'] == source) &
            (logistics_df['TO IUGU CODE'] == destination) &
            (logistics_df['TRANSPORT CODE'] == mode) &
            (logistics_df['TIME PERIOD'] == period)
        ]
        
        if route_data.empty:
            result['error'] = 'Route not found in uploaded dataset'
            return result
        
        result['exists'] = True
        row = route_data.iloc[0]
        
        # Logistics data
        result['freight_cost'] = float(row.get('FREIGHT COST', 0))
        result['handling_cost'] = float(row.get('HANDLING COST', 0))
        result['quantity_multiplier'] = float(row.get('QUANTITY MULTIPLIER', 1))
        
        # Transport mode info
        if mode in self.TRANSPORT_INFO:
            result['mode_name'] = self.TRANSPORT_INFO[mode]['name']
            result['vehicle_capacity'] = self.TRANSPORT_INFO[mode]['vehicle_capacity']
            result['emission_factor'] = self.TRANSPORT_INFO[mode]['emission_factor']
        else:
            result['mode_name'] = mode
            result['vehicle_capacity'] = 'Not available in uploaded dataset'
            result['emission_factor'] = 'Not available in uploaded dataset'
        
        # Source capacity
        result['source_capacity'] = self._get_capacity(source, period)
        result['source_production_cost'] = self._get_production_cost(source, period)
        
        # Destination demand
        result['destination_demand'] = self._get_demand(destination, period)
        
        # Inventory data
        result['source_opening_stock'] = self._get_opening_stock(source)
        result['destination_opening_stock'] = self._get_opening_stock(destination)
        result['destination_min_close_stock'] = self._get_min_close_stock(destination, period)
        result['destination_max_close_stock'] = self._get_max_close_stock(destination, period)
        
        # Constraints
        result['constraints'] = self._get_constraints(source, destination, mode, period)
        
        # Computed metrics
        result['computed'] = self._compute_route_metrics(result)
        
        return result
    
    def _get_capacity(self, iu_code: str, period: int) -> Any:
        """Get capacity from Excel - returns 'Not available' if not found"""
        if 'Capacity' not in self.data:
            return 'Not available in uploaded dataset'
        
        df = self.data['Capacity']
        match = df[(df['IU CODE'] == iu_code) & (df['TIME PERIOD'] == period)]
        
        if match.empty:
            return 'Not available in uploaded dataset'
        return float(match.iloc[0]['CAPACITY'])
    
    def _get_production_cost(self, iu_code: str, period: int) -> Any:
        """Get production cost from Excel"""
        if 'ProductionCost' not in self.data:
            return 'Not available in uploaded dataset'
        
        df = self.data['ProductionCost']
        match = df[(df['IU CODE'] == iu_code) & (df['TIME PERIOD'] == period)]
        
        if match.empty:
            return 'Not available in uploaded dataset'
        return float(match.iloc[0]['PRODUCTION COST'])
    
    def _get_demand(self, iugu_code: str, period: int) -> Any:
        """Get demand from Excel"""
        if 'Demand' not in self.data:
            return 'Not available in uploaded dataset'
        
        df = self.data['Demand']
        match = df[(df['IUGU CODE'] == iugu_code) & (df['TIME PERIOD'] == period)]
        
        if match.empty:
            return 'Not available in uploaded dataset'
        return float(match.iloc[0]['DEMAND'])
    
    def _get_opening_stock(self, iugu_code: str) -> Any:
        """Get opening stock from Excel"""
        if 'OpeningStock' not in self.data:
            return 'Not available in uploaded dataset'
        
        df = self.data['OpeningStock']
        match = df[df['IUGU CODE'] == iugu_code]
        
        if match.empty:
            return 'Not available in uploaded dataset'
        return float(match.iloc[0]['OPENING STOCK'])
    
    def _get_min_close_stock(self, iugu_code: str, period: int) -> Any:
        """Get min closing stock from Excel"""
        if 'ClosingStock' not in self.data:
            return 'Not available in uploaded dataset'
        
        df = self.data['ClosingStock']
        match = df[(df['IUGU CODE'] == iugu_code) & (df['TIME PERIOD'] == period)]
        
        if match.empty:
            return 'Not available in uploaded dataset'
        val = match.iloc[0]['MIN CLOSE STOCK']
        return float(val) if pd.notna(val) else 'Not available in uploaded dataset'
    
    def _get_max_close_stock(self, iugu_code: str, period: int) -> Any:
        """Get max closing stock from Excel"""
        if 'ClosingStock' not in self.data:
            return 'Not available in uploaded dataset'
        
        df = self.data['ClosingStock']
        match = df[(df['IUGU CODE'] == iugu_code) & (df['TIME PERIOD'] == period)]
        
        if match.empty:
            return 'Not available in uploaded dataset'
        val = match.iloc[0]['MAX CLOSE STOCK']
        return float(val) if pd.notna(val) else 'Not available in uploaded dataset'
    
    def _get_constraints(self, source: str, destination: str, mode: str, period: int) -> List[Dict]:
        """Get constraints from Excel"""
        if 'Constraints' not in self.data:
            return []
        
        df = self.data['Constraints']
        constraints = []
        
        # Match constraints for this route
        for _, row in df.iterrows():
            iu_match = pd.isna(row['IU CODE']) or row['IU CODE'] == source
            mode_match = pd.isna(row['TRANSPORT CODE']) or row['TRANSPORT CODE'] == mode
            dest_match = pd.isna(row['IUGU CODE']) or row['IUGU CODE'] == destination
            period_match = row['TIME PERIOD'] == period
            
            if iu_match and mode_match and dest_match and period_match:
                constraints.append({
                    'iu': row['IU CODE'] if pd.notna(row['IU CODE']) else 'Any',
                    'mode': row['TRANSPORT CODE'] if pd.notna(row['TRANSPORT CODE']) else 'Any',
                    'destination': row['IUGU CODE'] if pd.notna(row['IUGU CODE']) else 'Any',
                    'bound_type': row['BOUND TYPEID'],
                    'value_type': row['VALUE TYPEID'],
                    'value': float(row['Value']) if pd.notna(row['Value']) else None
                })
        
        return constraints
    
    def _compute_route_metrics(self, route_data: Dict) -> Dict[str, Any]:
        """Compute derived metrics from Excel data - no assumptions"""
        computed = {}
        
        # Total cost per unit
        freight = route_data.get('freight_cost', 0)
        handling = route_data.get('handling_cost', 0)
        if isinstance(freight, (int, float)) and isinstance(handling, (int, float)):
            computed['total_cost_per_unit'] = freight + handling
        else:
            computed['total_cost_per_unit'] = 'Cannot compute - missing data in dataset'
        
        # Trips required (if demand and capacity available)
        demand = route_data.get('destination_demand')
        vehicle_cap = route_data.get('vehicle_capacity')
        
        if isinstance(demand, (int, float)) and isinstance(vehicle_cap, (int, float)) and vehicle_cap > 0:
            computed['estimated_trips'] = int(np.ceil(demand / vehicle_cap))
            computed['total_freight_cost'] = computed['estimated_trips'] * freight if isinstance(freight, (int, float)) else 'Cannot compute'
        else:
            computed['estimated_trips'] = 'Cannot compute - missing data in dataset'
            computed['total_freight_cost'] = 'Cannot compute - missing data in dataset'
        
        # Carbon emissions estimate
        emission_factor = route_data.get('emission_factor')
        if isinstance(demand, (int, float)) and isinstance(emission_factor, (int, float)):
            # Simplified: emissions = demand * emission_factor * avg_distance (unknown)
            computed['emission_intensity'] = emission_factor
            computed['carbon_note'] = 'Full calculation requires distance data (not in dataset)'
        else:
            computed['emission_intensity'] = 'Cannot compute - missing data in dataset'
        
        # Demand volatility (requires historical data - compute if multiple periods)
        if 'Demand' in self.data and 'destination_demand' in route_data:
            dest = route_data.get('destination')
            if dest:
                demand_df = self.data['Demand']
                dest_demands = demand_df[demand_df['IUGU CODE'] == dest]['DEMAND']
                if len(dest_demands) > 1:
                    computed['demand_std'] = float(dest_demands.std())
                    computed['demand_mean'] = float(dest_demands.mean())
                    computed['demand_cv'] = computed['demand_std'] / computed['demand_mean'] if computed['demand_mean'] > 0 else 0
                    # Elastic Safety Stock: Z * σ * √L (assume L=3 days if not specified)
                    z_score = 1.65  # 95% service level
                    lead_time = 3  # Default lead time - would be from Excel if available
                    computed['ess'] = z_score * computed['demand_std'] * np.sqrt(lead_time)
                else:
                    computed['demand_volatility_note'] = 'Insufficient periods in dataset to compute volatility'
        
        return computed
    
    def get_all_routes_summary(self) -> List[Dict]:
        """Get summary of all routes in the dataset"""
        if not self.is_loaded or 'Logistics' not in self.data:
            return []
        
        df = self.data['Logistics']
        routes = df.groupby(['FROM IU CODE', 'TO IUGU CODE', 'TRANSPORT CODE']).agg({
            'FREIGHT COST': 'mean',
            'HANDLING COST': 'mean',
            'TIME PERIOD': 'count'
        }).reset_index()
        
        return routes.to_dict('records')
    
    def get_demand_summary(self) -> Dict[str, Any]:
        """Get demand summary from dataset"""
        if not self.is_loaded or 'Demand' not in self.data:
            return {'error': 'Demand data not available in dataset'}
        
        df = self.data['Demand']
        
        return {
            'total_demand': float(df['DEMAND'].sum()),
            'by_period': df.groupby('TIME PERIOD')['DEMAND'].sum().to_dict(),
            'by_plant': df.groupby('IUGU CODE')['DEMAND'].sum().to_dict(),
            'plant_count': df['IUGU CODE'].nunique(),
            'period_count': df['TIME PERIOD'].nunique()
        }
    
    def get_capacity_summary(self) -> Dict[str, Any]:
        """Get capacity summary from dataset"""
        if not self.is_loaded or 'Capacity' not in self.data:
            return {'error': 'Capacity data not available in dataset'}
        
        df = self.data['Capacity']
        
        return {
            'total_capacity': float(df['CAPACITY'].sum()),
            'by_period': df.groupby('TIME PERIOD')['CAPACITY'].sum().to_dict(),
            'by_iu': df.groupby('IU CODE')['CAPACITY'].sum().to_dict(),
            'iu_count': df['IU CODE'].nunique(),
            'period_count': df['TIME PERIOD'].nunique()
        }
    
    def validate_selection(self, source: str = None, destination: str = None, 
                           mode: str = None, period: int = None) -> Dict[str, Any]:
        """Validate user selection against Excel data"""
        validation = {
            'valid': True,
            'errors': [],
            'warnings': []
        }
        
        if not self.is_loaded:
            validation['valid'] = False
            validation['errors'].append('No dataset loaded')
            return validation
        
        if source and source not in self.metadata.get('source_ius', []):
            validation['valid'] = False
            validation['errors'].append(f'Source "{source}" not found in uploaded dataset')
        
        if source and destination:
            valid_destinations = self.get_destinations_for_source(source)
            if destination not in valid_destinations:
                validation['valid'] = False
                validation['errors'].append(f'Route {source} → {destination} not found in uploaded dataset')
        
        if source and destination and mode:
            valid_modes = self.get_modes_for_route(source, destination)
            if mode not in valid_modes:
                validation['valid'] = False
                validation['errors'].append(f'Transport mode "{mode}" not available for route {source} → {destination}')
        
        if period and period not in self.metadata.get('periods', []):
            validation['valid'] = False
            validation['errors'].append(f'Period {period} not found in uploaded dataset')
        
        return validation


# Singleton instance
parser = ExcelDataParser()
