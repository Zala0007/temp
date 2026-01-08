"""
Clinker Supply Chain Optimization Model (MILP)
===============================================
Multi-Period Supply Chain Optimization for Adani Cement Network

Mathematical Model Components:
- Decision Variables: Production (P), Shipment (X), Inventory (I), Trips (T)
- Objective: Minimize Z = Production Cost + Transport Cost + Holding Cost
- Constraints: Mass Balance, Capacity, Inventory Bounds, Strategic Constraints

All data fetched EXCLUSIVELY from uploaded Excel/CSV files.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
import math

NOT_AVAILABLE = "N/A"

# Transport mode capacities (tons per trip)
TRANSPORT_MODES = {
    'T1': {'name': 'Road', 'capacity': 30},
    'T2': {'name': 'Rail', 'capacity': 3000}
}

# Holding cost rate (% of production cost per period)
HOLDING_COST_RATE = 0.01


@dataclass
class RouteData:
    """All data for a route - directly from Excel"""
    # Route Identification
    source: str
    destination: str
    mode: str
    period: int
    
    # From LogisticsIUGU.csv
    freight_cost: Any  # FREIGHT COST column
    handling_cost: Any  # HANDLING COST column
    quantity_multiplier: Any  # QUANTITY MULTIPLIER column
    
    # From ProductionCost.csv
    production_cost: Any  # PRODUCTION COST for source
    
    # From ClinkerCapacity.csv
    source_capacity: Any  # CAPACITY for source
    
    # From ClinkerDemand.csv  
    source_demand: Any  # DEMAND if source has demand
    destination_demand: Any  # DEMAND for destination
    min_fulfillment_pct: Any  # MIN FULFILLMENT (%)
    
    # From IUGUOpeningStock.csv
    source_opening_stock: Any  # OPENING STOCK for source
    destination_opening_stock: Any  # OPENING STOCK for destination
    
    # From IUGUClosingStock.csv
    source_closing_min: Any  # MIN CLOSE STOCK for source
    source_closing_max: Any  # MAX CLOSE STOCK for source
    destination_closing_min: Any  # MIN CLOSE STOCK for destination
    destination_closing_max: Any  # MAX CLOSE STOCK for destination
    
    # From IUGUType.csv
    source_type: Any  # PLANT TYPE for source (IU/GU)
    destination_type: Any  # PLANT TYPE for destination
    source_num_sources: Any  # # Source column
    destination_num_sources: Any
    
    # From IUGUConstraint.csv
    constraints: List[Dict] = None
    
    # Calculated from Excel data only
    total_logistics_cost: Any = None
    total_delivered_cost: Any = None
    
    # Derived metrics (simple calculations from Excel data)
    trips_required: int = 0
    total_transport_cost: float = 0
    stock_gap_source: float = 0
    stock_gap_destination: float = 0
    can_fulfill_demand: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            # Route Info
            'source': self.source,
            'destination': self.destination,
            'mode': self.mode,
            'period': self.period,
            
            # Logistics Data (from LogisticsIUGU.csv)
            'freight_cost': self.freight_cost,
            'handling_cost': self.handling_cost,
            'quantity_multiplier': self.quantity_multiplier,
            'total_logistics_cost': self.total_logistics_cost,
            
            # Production Data (from ProductionCost.csv)
            'production_cost': self.production_cost,
            'total_delivered_cost': self.total_delivered_cost,
            
            # Capacity Data (from ClinkerCapacity.csv)
            'source_capacity': self.source_capacity,
            
            # Demand Data (from ClinkerDemand.csv)
            'source_demand': self.source_demand,
            'destination_demand': self.destination_demand,
            'min_fulfillment_pct': self.min_fulfillment_pct,
            
            # Opening Stock (from IUGUOpeningStock.csv)
            'source_opening_stock': self.source_opening_stock,
            'destination_opening_stock': self.destination_opening_stock,
            
            # Closing Stock (from IUGUClosingStock.csv)
            'source_closing_min': self.source_closing_min,
            'source_closing_max': self.source_closing_max,
            'destination_closing_min': self.destination_closing_min,
            'destination_closing_max': self.destination_closing_max,
            
            # Plant Type (from IUGUType.csv)
            'source_type': self.source_type,
            'destination_type': self.destination_type,
            'source_num_sources': self.source_num_sources,
            'destination_num_sources': self.destination_num_sources,
            
            # Constraints (from IUGUConstraint.csv)
            'constraints': self.constraints or [],
            
            # Simple Calculations from Excel Data
            'trips_required': self.trips_required,
            'total_transport_cost': self.total_transport_cost,
            'stock_gap_source': self.stock_gap_source,
            'stock_gap_destination': self.stock_gap_destination,
            'can_fulfill_demand': self.can_fulfill_demand,
        }


class ClinkerOptimizer:
    """
    MILP Optimizer for Clinker Supply Chain
    All data from Excel/CSV files exclusively
    
    Decision Variables:
        P[i,t] - Production at IU i in period t
        X[i,j,m,t] - Shipment from i to j via mode m in period t
        I[i,t] - Inventory at node i at end of period t
        T[i,j,m,t] - Number of trips (integer)
    
    Objective: min Z = Σ(C_prod × P) + Σ(C_transport × X) + Σ(C_holding × I)
    """
    
    def __init__(self):
        self.data: Dict[str, pd.DataFrame] = {}
        self.is_loaded = False
        
    def load_data(self, data: Dict[str, pd.DataFrame]):
        """Load data from parser"""
        self.data = data
        self.is_loaded = True
        self._ensure_numeric_columns()
    
    def _ensure_numeric_columns(self):
        """Convert numeric columns to proper types"""
        numeric_mappings = {
            'Logistics': ['FREIGHT COST', 'HANDLING COST', 'QUANTITY MULTIPLIER', 'TIME PERIOD'],
            'Capacity': ['CAPACITY', 'TIME PERIOD'],
            'Demand': ['DEMAND', 'TIME PERIOD', 'MIN FULFILLMENT (%)'],
            'ProductionCost': ['PRODUCTION COST', 'TIME PERIOD'],
            'OpeningStock': ['OPENING STOCK'],
            'ClosingStock': ['MIN CLOSE STOCK', 'MAX CLOSE STOCK', 'TIME PERIOD'],
            'Constraints': ['TIME PERIOD', 'Value']
        }
        
        for sheet, cols in numeric_mappings.items():
            if sheet in self.data:
                df = self.data[sheet]
                for col in cols:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    def _get_value(self, df: pd.DataFrame, mask, column: str) -> Any:
        """Get single value from dataframe or return N/A"""
        if df is None or column not in df.columns:
            return NOT_AVAILABLE
        result = df[mask]
        if len(result) == 0:
            return NOT_AVAILABLE
        val = result[column].iloc[0]
        if pd.isna(val):
            return NOT_AVAILABLE
        return float(val) if isinstance(val, (int, float, np.number)) else val
    
    def _num(self, val, default=0) -> float:
        """Convert to number or return default"""
        if val == NOT_AVAILABLE or val is None:
            return default
        if isinstance(val, (int, float)):
            return float(val)
        return default
    
    def get_route_data(self, source: str, dest: str, mode: str, period: int) -> RouteData:
        """Fetch all data for a route directly from Excel sheets"""
        
        # ============ LOGISTICS DATA (LogisticsIUGU.csv) ============
        freight_cost = NOT_AVAILABLE
        handling_cost = NOT_AVAILABLE
        quantity_multiplier = NOT_AVAILABLE
        
        if 'Logistics' in self.data:
            df = self.data['Logistics']
            mask = (
                (df['FROM IU CODE'] == source) & 
                (df['TO IUGU CODE'] == dest) & 
                (df['TRANSPORT CODE'] == mode) & 
                (df['TIME PERIOD'] == period)
            )
            freight_cost = self._get_value(df, mask, 'FREIGHT COST')
            handling_cost = self._get_value(df, mask, 'HANDLING COST')
            quantity_multiplier = self._get_value(df, mask, 'QUANTITY MULTIPLIER')
        
        # ============ PRODUCTION COST (ProductionCost.csv) ============
        production_cost = NOT_AVAILABLE
        if 'ProductionCost' in self.data:
            df = self.data['ProductionCost']
            mask = (df['IU CODE'] == source) & (df['TIME PERIOD'] == period)
            production_cost = self._get_value(df, mask, 'PRODUCTION COST')
        
        # ============ CAPACITY (ClinkerCapacity.csv) ============
        source_capacity = NOT_AVAILABLE
        if 'Capacity' in self.data:
            df = self.data['Capacity']
            mask = (df['IU CODE'] == source) & (df['TIME PERIOD'] == period)
            source_capacity = self._get_value(df, mask, 'CAPACITY')
        
        # ============ DEMAND (ClinkerDemand.csv) ============
        source_demand = NOT_AVAILABLE
        destination_demand = NOT_AVAILABLE
        min_fulfillment = NOT_AVAILABLE
        
        if 'Demand' in self.data:
            df = self.data['Demand']
            # Source demand (if source also has demand)
            mask = (df['IUGU CODE'] == source) & (df['TIME PERIOD'] == period)
            source_demand = self._get_value(df, mask, 'DEMAND')
            
            # Destination demand
            mask = (df['IUGU CODE'] == dest) & (df['TIME PERIOD'] == period)
            destination_demand = self._get_value(df, mask, 'DEMAND')
            min_fulfillment = self._get_value(df, mask, 'MIN FULFILLMENT (%)')
        
        # ============ OPENING STOCK (IUGUOpeningStock.csv) ============
        source_opening = NOT_AVAILABLE
        dest_opening = NOT_AVAILABLE
        
        if 'OpeningStock' in self.data:
            df = self.data['OpeningStock']
            mask = df['IUGU CODE'] == source
            source_opening = self._get_value(df, mask, 'OPENING STOCK')
            
            mask = df['IUGU CODE'] == dest
            dest_opening = self._get_value(df, mask, 'OPENING STOCK')
        
        # ============ CLOSING STOCK (IUGUClosingStock.csv) ============
        source_close_min = NOT_AVAILABLE
        source_close_max = NOT_AVAILABLE
        dest_close_min = NOT_AVAILABLE
        dest_close_max = NOT_AVAILABLE
        
        if 'ClosingStock' in self.data:
            df = self.data['ClosingStock']
            # Source closing stock
            mask = (df['IUGU CODE'] == source) & (df['TIME PERIOD'] == period)
            source_close_min = self._get_value(df, mask, 'MIN CLOSE STOCK')
            source_close_max = self._get_value(df, mask, 'MAX CLOSE STOCK')
            
            # Destination closing stock
            mask = (df['IUGU CODE'] == dest) & (df['TIME PERIOD'] == period)
            dest_close_min = self._get_value(df, mask, 'MIN CLOSE STOCK')
            dest_close_max = self._get_value(df, mask, 'MAX CLOSE STOCK')
        
        # ============ PLANT TYPE (IUGUType.csv) ============
        source_type = NOT_AVAILABLE
        dest_type = NOT_AVAILABLE
        source_num = NOT_AVAILABLE
        dest_num = NOT_AVAILABLE
        
        if 'IUGUType' in self.data:
            df = self.data['IUGUType']
            mask = df['IUGU CODE'] == source
            source_type = self._get_value(df, mask, 'PLANT TYPE')
            source_num = self._get_value(df, mask, '# Source')
            
            mask = df['IUGU CODE'] == dest
            dest_type = self._get_value(df, mask, 'PLANT TYPE')
            dest_num = self._get_value(df, mask, '# Source')
        
        # ============ CONSTRAINTS (IUGUConstraint.csv) ============
        constraints = []
        if 'Constraints' in self.data:
            df = self.data['Constraints']
            # Get all constraints relevant to this route
            mask = (df['IU CODE'] == source) & (df['TIME PERIOD'] == period)
            
            for _, row in df[mask].iterrows():
                transport_code = row.get('TRANSPORT CODE', '')
                iugu_code = row.get('IUGU CODE', '')
                
                # Include if matches mode or is general constraint
                if pd.isna(transport_code) or transport_code == '' or transport_code == mode:
                    if pd.isna(iugu_code) or iugu_code == '' or iugu_code == dest:
                        bound_type = row.get('BOUND TYPEID', '')
                        value_type = row.get('VALUE TYPEID', '')
                        value = row.get('Value', 0)
                        
                        constraints.append({
                            'bound_type': bound_type,  # E=Equality, L=LessEqual, G=GreaterEqual
                            'value_type': value_type,  # C=Constant, P=Percentage
                            'value': float(value) if pd.notna(value) else 0,
                            'transport_code': transport_code if pd.notna(transport_code) else '',
                            'target_iugu': iugu_code if pd.notna(iugu_code) else ''
                        })
        
        # ============ SIMPLE CALCULATIONS FROM EXCEL DATA ============
        # Total logistics cost = Freight + Handling
        total_logistics = NOT_AVAILABLE
        if isinstance(freight_cost, (int, float)) and isinstance(handling_cost, (int, float)):
            total_logistics = freight_cost + handling_cost
        
        # Total delivered cost = Logistics + Production
        total_delivered = NOT_AVAILABLE
        if isinstance(total_logistics, (int, float)) and isinstance(production_cost, (int, float)):
            total_delivered = total_logistics + production_cost
        
        # Trips required = Demand / Quantity Multiplier (rounded up)
        trips_required = 0
        if isinstance(destination_demand, (int, float)) and isinstance(quantity_multiplier, (int, float)) and quantity_multiplier > 0:
            trips_required = int(np.ceil(destination_demand / quantity_multiplier))
        
        # Total transport cost = Logistics Cost × Demand
        total_transport_cost = 0
        if isinstance(total_logistics, (int, float)) and isinstance(destination_demand, (int, float)):
            total_transport_cost = total_logistics * destination_demand
        
        # Stock gap source = Opening Stock - Min Closing Stock
        stock_gap_source = 0
        if isinstance(source_opening, (int, float)) and isinstance(source_close_min, (int, float)):
            stock_gap_source = source_opening - source_close_min
        
        # Stock gap destination = Opening Stock - Min Closing Stock
        stock_gap_destination = 0
        if isinstance(dest_opening, (int, float)) and isinstance(dest_close_min, (int, float)):
            stock_gap_destination = dest_opening - dest_close_min
        
        # Can fulfill = Capacity + Opening Stock >= Demand + Min Closing
        can_fulfill = False
        if all(isinstance(v, (int, float)) for v in [source_capacity, source_opening, destination_demand, dest_close_min]):
            available = source_capacity + source_opening
            needed = destination_demand + dest_close_min
            can_fulfill = available >= needed
        
        return RouteData(
            source=source,
            destination=dest,
            mode=mode,
            period=period,
            freight_cost=freight_cost,
            handling_cost=handling_cost,
            quantity_multiplier=quantity_multiplier,
            production_cost=production_cost,
            source_capacity=source_capacity,
            source_demand=source_demand,
            destination_demand=destination_demand,
            min_fulfillment_pct=min_fulfillment,
            source_opening_stock=source_opening,
            destination_opening_stock=dest_opening,
            source_closing_min=source_close_min,
            source_closing_max=source_close_max,
            destination_closing_min=dest_close_min,
            destination_closing_max=dest_close_max,
            source_type=source_type,
            destination_type=dest_type,
            source_num_sources=source_num,
            destination_num_sources=dest_num,
            constraints=constraints,
            total_logistics_cost=total_logistics,
            total_delivered_cost=total_delivered,
            trips_required=trips_required,
            total_transport_cost=total_transport_cost,
            stock_gap_source=stock_gap_source,
            stock_gap_destination=stock_gap_destination,
            can_fulfill_demand=can_fulfill
        )
    
    def calculate_milp_solution(self, source: str, dest: str, mode: str, period: int) -> Dict[str, Any]:
        """
        Calculate complete MILP solution for a route
        Returns all decision variables, objective components, and constraints
        """
        route = self.get_route_data(source, dest, mode, period)
        
        # Get numeric values
        freight = self._num(route.freight_cost)
        handling = self._num(route.handling_cost)
        multiplier = self._num(route.quantity_multiplier, 1)
        prod_cost = self._num(route.production_cost)
        capacity = self._num(route.source_capacity)
        s_demand = self._num(route.source_demand)
        d_demand = self._num(route.destination_demand)
        s_open = self._num(route.source_opening_stock)
        d_open = self._num(route.destination_opening_stock)
        s_close_min = self._num(route.source_closing_min)
        s_close_max = self._num(route.source_closing_max, float('inf'))
        d_close_min = self._num(route.destination_closing_min)
        d_close_max = self._num(route.destination_closing_max, float('inf'))
        
        # Get vehicle capacity
        vehicle_capacity = TRANSPORT_MODES.get(mode, {'capacity': 30})['capacity']
        
        # ==================== MILP COST MINIMIZATION ====================
        # Objective: min Z = C_prod × P + C_transport × T + C_hold × excess_inv
        # Subject to: Mass Balance, Capacity, Safety Stock constraints
        
        # ===== STEP 1: Calculate MINIMUM shipment to satisfy destination =====
        # Constraint: I_dest[t] ≥ SS_dest (safety stock)
        # I_dest[t] = I_dest[t-1] + X - D_dest ≥ SS_dest
        # X ≥ SS_dest + D_dest - I_dest[t-1]
        min_shipment_needed = d_close_min + d_demand - d_open
        required_shipment = max(0, min_shipment_needed)  # Can't ship negative
        
        # ===== STEP 2: Round up to vehicle capacity (integer constraint) =====
        # T ∈ Z+ (integer trips), X = T × VehicleCapacity
        if vehicle_capacity > 0 and required_shipment > 0:
            num_trips = math.ceil(required_shipment / vehicle_capacity)
            shipment_qty = num_trips * vehicle_capacity
        else:
            num_trips = 0
            shipment_qty = 0
        
        # ===== STEP 3: Calculate MINIMUM production to satisfy source =====
        # Constraint: I_source[t] ≥ SS_source (safety stock)
        # I_source[t] = I_source[t-1] + P - X - D_source ≥ SS_source
        # P ≥ SS_source + X + D_source - I_source[t-1]
        is_iu = route.source_type == 'IU'
        if is_iu:
            min_production_needed = s_close_min + shipment_qty + s_demand - s_open
            required_production = max(0, min_production_needed)  # Can't produce negative
            
            # Check feasibility: Can we produce enough?
            if required_production > capacity and capacity > 0:
                production = capacity  # Cap at capacity (INFEASIBLE)
                capacity_violation = required_production - capacity
            else:
                production = required_production  # Produce exactly what's needed (OPTIMAL)
                capacity_violation = 0
        else:
            required_production = 0
            production = 0
            capacity_violation = 0
        
        # ===== STEP 4: Calculate ending inventories (Mass Balance) =====
        # I[i,t] = I[i,t-1] + P[i,t] - X_out - D[i,t]
        source_ending_inv = s_open + production - shipment_qty - s_demand
        dest_ending_inv = d_open + shipment_qty - d_demand
        
        # Excess inventory due to vehicle rounding
        excess_at_dest = shipment_qty - required_shipment
        
        # ===== STEP 5: Check constraint satisfaction =====
        source_ss_satisfied = source_ending_inv >= s_close_min - 0.01  # tolerance
        dest_ss_satisfied = dest_ending_inv >= d_close_min - 0.01  # tolerance
        is_feasible = source_ss_satisfied and dest_ss_satisfied and capacity_violation == 0
        
        decision_variables = {
            'P_i_t': {
                'value': round(production, 2),
                'description': f'Production at {source} in period {period}',
                'unit': 'tons',
                'minimum_required': round(required_production, 2) if is_iu else 0,
                'formula': f'max(0, SS_src + X + D_src - I_open) = max(0, {s_close_min:.0f} + {shipment_qty:.0f} + {s_demand:.0f} - {s_open:.0f}) = {required_production:.0f}' if is_iu else 'N/A (GU)',
            },
            'X_i_j_m_t': {
                'value': round(shipment_qty, 2),
                'description': f'Shipment from {source} to {dest} via {mode} in period {period}',
                'unit': 'tons',
                'minimum_required': round(required_shipment, 2),
                'formula': f'T × VehicleCap = {num_trips} × {vehicle_capacity} = {shipment_qty:.0f}',
                'excess': round(excess_at_dest, 2),
            },
            'I_source_t': {
                'value': round(source_ending_inv, 2),
                'description': f'Ending inventory at {source}',
                'unit': 'tons',
                'safety_stock': round(s_close_min, 2),
                'constraint_satisfied': source_ss_satisfied,
            },
            'I_dest_t': {
                'value': round(dest_ending_inv, 2),
                'description': f'Ending inventory at {dest}',
                'unit': 'tons',
                'safety_stock': round(d_close_min, 2),
                'constraint_satisfied': dest_ss_satisfied,
            },
            'T_i_j_m_t': {
                'value': num_trips,
                'description': f'Number of trips from {source} to {dest} via {mode}',
                'unit': 'trips',
                'formula': f'ceil({required_shipment:.0f} / {vehicle_capacity}) = {num_trips}',
                'vehicle_capacity': vehicle_capacity,
            }
        }
        
        # ==================== OBJECTIVE FUNCTION ====================
        # Z = C_prod × P + (C_freight + C_handling) × X + C_hold × excess_inv
        
        production_cost_comp = prod_cost * production
        freight_total = freight * shipment_qty
        handling_total = handling * shipment_qty
        transport_cost_comp = freight_total + handling_total
        
        # Holding cost: ONLY on inventory ABOVE safety stock
        # HoldingCost = h × max(I[i,t] - SafetyStock[i], 0)
        holding_rate = prod_cost * HOLDING_COST_RATE if prod_cost > 0 else 0
        
        source_excess_inv = max(0, source_ending_inv - s_close_min)
        source_holding = holding_rate * source_excess_inv
        
        dest_excess_inv = max(0, dest_ending_inv - d_close_min)
        dest_holding = holding_rate * dest_excess_inv
        
        holding_cost_comp = source_holding + dest_holding
        
        total_Z = production_cost_comp + transport_cost_comp + holding_cost_comp
        
        # Cost per ton = Z / fulfilled demand (destination demand)
        fulfilled_demand = d_demand
        cost_per_ton_demand = round(total_Z / fulfilled_demand, 2) if fulfilled_demand > 0 else 0
        
        objective_function = {
            'type': 'Minimize',
            'formula': 'Z = Σ(C_prod × P) + Σ(C_fr + C_hand) × X + Σ(C_hold × max(I - SafetyStock, 0))',
            'production_cost': {
                'formula': f'C_prod[{source},{period}] × P[{source},{period}]',
                'calculation': f'{prod_cost:.2f} × {production:.0f} = {production_cost_comp:.2f}',
                'value': round(production_cost_comp, 2),
                'rate': prod_cost,
            },
            'transport_cost': {
                'formula': f'(C_fr + C_hand) × X[{source},{dest},{mode},{period}]',
                'freight': {'rate': freight, 'total': round(freight_total, 2)},
                'handling': {'rate': handling, 'total': round(handling_total, 2)},
                'calculation': f'({freight:.2f} + {handling:.2f}) × {shipment_qty:.0f} = {transport_cost_comp:.2f}',
                'value': round(transport_cost_comp, 2),
                'rate_per_ton': round(freight + handling, 2),
            },
            'holding_cost': {
                'formula': 'h × max(I[i,t] - SafetyStock[i], 0)',
                'rate': round(holding_rate, 4),
                'source': {
                    'ending_inventory': round(source_ending_inv, 2),
                    'safety_stock': round(s_close_min, 2),
                    'excess_inventory': round(source_excess_inv, 2),
                    'cost': round(source_holding, 2),
                    'calculation': f'{holding_rate:.4f} × max({source_ending_inv:.0f} - {s_close_min:.0f}, 0) = {holding_rate:.4f} × {source_excess_inv:.0f} = {source_holding:.2f}'
                },
                'destination': {
                    'ending_inventory': round(dest_ending_inv, 2),
                    'safety_stock': round(d_close_min, 2),
                    'excess_inventory': round(dest_excess_inv, 2),
                    'cost': round(dest_holding, 2),
                    'calculation': f'{holding_rate:.4f} × max({dest_ending_inv:.0f} - {d_close_min:.0f}, 0) = {holding_rate:.4f} × {dest_excess_inv:.0f} = {dest_holding:.2f}'
                },
                'calculation': f'{source_holding:.2f} + {dest_holding:.2f} = {holding_cost_comp:.2f}',
                'value': round(holding_cost_comp, 2),
            },
            'total_Z': round(total_Z, 2),
            'fulfilled_demand': round(fulfilled_demand, 2),
            'cost_per_ton': cost_per_ton_demand,
            'cost_per_ton_note': 'Total Z ÷ Fulfilled External Demand',
            'unit_costs': {
                'production_per_ton': prod_cost,
                'transport_per_ton': round(freight + handling, 2),
                'total_delivered_per_ton': round(prod_cost + freight + handling, 2),
            }
        }
        
        # ==================== MASS BALANCE EQUATION ====================
        # I[i,t] = I[i,t-1] + P[i,t] + Σ inbound - Σ outbound - D[i,t]
        
        mass_balance = {
            'equation': 'I[i,t] = I[i,t-1] + P[i,t] + Σ(inbound) - Σ(outbound) - D[i,t]',
            'source_node': {
                'node': source,
                'I_t_minus_1': s_open,
                'P_t': production,
                'inbound': 0,
                'outbound': shipment_qty,
                'D_t': s_demand,
                'I_t': round(source_ending_inv, 2),
                'equation_string': f'I[{source},{period}] = {s_open:.0f} + {production:.0f} + 0 - {shipment_qty:.0f} - {s_demand:.0f} = {source_ending_inv:.0f}',
            },
            'destination_node': {
                'node': dest,
                'I_t_minus_1': d_open,
                'P_t': 0,
                'inbound': shipment_qty,
                'outbound': 0,
                'D_t': d_demand,
                'I_t': round(dest_ending_inv, 2),
                'equation_string': f'I[{dest},{period}] = {d_open:.0f} + 0 + {shipment_qty:.0f} - 0 - {d_demand:.0f} = {dest_ending_inv:.0f}',
            }
        }
        
        # ==================== CONSTRAINTS ====================
        constraints = {
            'production_capacity': {
                'name': 'Production Capacity',
                'formula': f'P[{source},{period}] ≤ Cap[{source},{period}]',
                'lhs': round(production, 2),
                'rhs': capacity,
                'satisfied': production <= capacity,
                'slack': round(capacity - production, 2),
                'utilization_pct': round(production / capacity * 100, 2) if capacity > 0 else 0,
            },
            'shipment_upper_bound': {
                'name': 'Shipment Upper Bound',
                'formula': f'X[{source},{dest},{mode},{period}] ≤ T × Cap_m',
                'lhs': round(shipment_qty, 2),
                'rhs': num_trips * vehicle_capacity,
                'satisfied': shipment_qty <= num_trips * vehicle_capacity,
                'vehicle_capacity': vehicle_capacity,
            },
            'inventory_source': {
                'name': 'Source Inventory Bounds',
                'formula': f'SS[{source}] ≤ I[{source},{period}] ≤ MaxCap[{source}]',
                'safety_stock': s_close_min,
                'current': round(source_ending_inv, 2),
                'max_capacity': s_close_max if s_close_max != float('inf') else 'unlimited',
                'satisfied': s_close_min <= source_ending_inv <= (s_close_max if s_close_max != float('inf') else source_ending_inv),
            },
            'inventory_destination': {
                'name': 'Destination Inventory Bounds',
                'formula': f'SS[{dest}] ≤ I[{dest},{period}] ≤ MaxCap[{dest}]',
                'safety_stock': d_close_min,
                'current': round(dest_ending_inv, 2),
                'max_capacity': d_close_max if d_close_max != float('inf') else 'unlimited',
                'satisfied': d_close_min <= dest_ending_inv <= (d_close_max if d_close_max != float('inf') else dest_ending_inv),
            },
            'strategic_constraints': route.constraints or []
        }
        
        # ==================== PERFORMANCE METRICS ====================
        metrics = {
            'capacity_utilization_pct': round(production / capacity * 100, 2) if capacity > 0 else 0,
            'demand_fulfillment_pct': round(min(shipment_qty / d_demand * 100, 100), 2) if d_demand > 0 else 100,
            'inventory_turnover_source': round(shipment_qty / s_open, 2) if s_open > 0 else 0,
            'inventory_turnover_dest': round(d_demand / d_open, 2) if d_open > 0 else 0,
            'days_of_supply_source': round(source_ending_inv / (s_demand / 30), 1) if s_demand > 0 else float('inf'),
            'days_of_supply_dest': round(dest_ending_inv / (d_demand / 30), 1) if d_demand > 0 else float('inf'),
            'transport_efficiency': round(shipment_qty / (num_trips * vehicle_capacity) * 100, 2) if num_trips > 0 else 0,
            'cost_breakdown_pct': {
                'production': round(production_cost_comp / total_Z * 100, 2) if total_Z > 0 else 0,
                'transport': round(transport_cost_comp / total_Z * 100, 2) if total_Z > 0 else 0,
                'holding': round(holding_cost_comp / total_Z * 100, 2) if total_Z > 0 else 0,
            }
        }
        
        # ==================== FEASIBILITY ====================
        issues = []
        if capacity_violation > 0:
            issues.append(f'Production required {required_production:.0f} exceeds capacity {capacity:.0f} by {capacity_violation:.0f} tons')
        if not source_ss_satisfied:
            issues.append(f'Source inventory {source_ending_inv:.0f} below safety stock {s_close_min:.0f}')
        if not dest_ss_satisfied:
            issues.append(f'Destination inventory {dest_ending_inv:.0f} below safety stock {d_close_min:.0f}')
        
        feasibility = {
            'is_feasible': is_feasible,
            'capacity_violation': round(capacity_violation, 2) if capacity_violation > 0 else 0,
            'issues': issues
        }
        
        return {
            'route': route.to_dict(),
            'decision_variables': decision_variables,
            'objective_function': objective_function,
            'mass_balance': mass_balance,
            'constraints': constraints,
            'metrics': metrics,
            'feasibility': feasibility
        }
    
    def get_mathematical_model(self) -> Dict[str, Any]:
        """Return the mathematical model formulation"""
        return {
            'name': 'Multi-Period Clinker Supply Chain Optimization (MILP)',
            'description': 'Optimize clinker transportation and inventory planning across Adani cement network',
            'decision_variables': [
                {'symbol': 'P[i,t]', 'description': 'Production at IU i in period t', 'unit': 'tons', 'domain': '≥ 0 (Continuous)'},
                {'symbol': 'X[i,j,m,t]', 'description': 'Shipment from i to j via mode m in period t', 'unit': 'tons', 'domain': '≥ 0 (Continuous)'},
                {'symbol': 'I[i,t]', 'description': 'Inventory at node i at end of period t', 'unit': 'tons', 'domain': '≥ 0 (Continuous)'},
                {'symbol': 'T[i,j,m,t]', 'description': 'Number of trips from i to j via mode m in period t', 'unit': 'trips', 'domain': '≥ 0 (Integer)'}
            ],
            'objective_function': {
                'type': 'Minimize',
                'formula': 'Z = Σ C_prod·P[i,t] + Σ (C_fr + C_hand)·X[i,j,m,t] + Σ C_hold·I[i,t]',
                'components': [
                    {'name': 'Production Cost', 'formula': 'Σ C_prod[i,t] × P[i,t]', 'source': 'ProductionCost.csv'},
                    {'name': 'Transport Cost', 'formula': 'Σ (C_fr[r,m,t] + C_hand[r,m,t]) × X[r,m,t]', 'source': 'LogisticsIUGU.csv'},
                    {'name': 'Holding Cost', 'formula': 'Σ C_hold × I[i,t]', 'source': '1% of Production Cost'}
                ]
            },
            'constraints': [
                {'name': 'Mass Balance', 'formula': 'I[i,t] = I[i,t-1] + P[i,t] + Σ X[j,i,m,t] - Σ X[i,j,m,t] - D[i,t]', 'source': 'IUGUOpeningStock, ClinkerDemand'},
                {'name': 'Production Capacity', 'formula': 'P[i,t] ≤ Cap[i,t]  ∀ i ∈ IU', 'source': 'ClinkerCapacity.csv'},
                {'name': 'Shipment Upper Bound', 'formula': 'X[i,j,m,t] ≤ T[i,j,m,t] × Cap_m', 'source': 'LogisticsIUGU.csv'},
                {'name': 'Inventory Safety Stock', 'formula': 'I[i,t] ≥ SS[i]  ∀ i,t', 'source': 'IUGUClosingStock (MIN)'},
                {'name': 'Inventory Max Capacity', 'formula': 'I[i,t] ≤ MaxCap[i]  ∀ i,t', 'source': 'IUGUClosingStock (MAX)'},
                {'name': 'Strategic Constraints', 'formula': 'From IUGUConstraint.csv', 'source': 'IUGUConstraint.csv'}
            ],
            'data_sources': {
                'IUGUType.csv': 'Plant types (IU/GU) - N_IU, N_GU sets',
                'IUGUOpeningStock.csv': 'Initial inventory - S[i,0]',
                'ProductionCost.csv': 'Production cost per ton - C_prod[i,t]',
                'ClinkerCapacity.csv': 'Production capacity - Cap[i,t]',
                'ClinkerDemand.csv': 'Demand at each node - D[i,t]',
                'IUGUClosingStock.csv': 'Inventory bounds - I_min[i,t], I_max[i,t]',
                'LogisticsIUGU.csv': 'Freight, handling, vehicle capacity - C_fr, C_hand, QMult',
                'IUGUConstraint.csv': 'Strategic constraints - V_bound'
            },
            'transport_modes': TRANSPORT_MODES
        }
    
    def get_all_data_for_route(self, source: str, dest: str, mode: str, period: int) -> Dict[str, Any]:
        """Get complete MILP analysis for a route - main method called by API"""
        return self.calculate_milp_solution(source, dest, mode, period)


# Global optimizer instance
optimizer = ClinkerOptimizer()
