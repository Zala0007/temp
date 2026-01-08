'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { 
  Upload, FileSpreadsheet, Truck, Train, Ship, 
  MapPin, Calendar, ArrowRight, BarChart3, AlertCircle,
  CheckCircle2, TrendingUp, Package, DollarSign, Info,
  RefreshCw, Database, Calculator, Target, Sigma, BookOpen,
  Activity, Gauge, PieChart, TrendingDown, Zap, Shield,
  Clock, Boxes, Scale, Route, Percent, ArrowUpDown,
  CheckCircle, XCircle, AlertTriangle, Lightbulb, Binary
} from 'lucide-react';

// Types based on Excel data structure - MILP Model Response
interface DecisionVariable {
  value: number;
  description: string;
  unit: string;
  formula?: string;
}

interface CostComponent {
  formula: string;
  calculation: string;
  value: number;
  rate?: number;
  total?: number;
  freight?: { rate: number; total: number };
  handling?: { rate: number; total: number };
}

interface ObjectiveFunction {
  type: string;
  formula: string;
  production_cost: CostComponent;
  transport_cost: CostComponent;
  holding_cost: CostComponent;
  total_Z: number;
  cost_per_ton: number;
}

interface MassBalanceNode {
  node: string;
  I_t_minus_1: number;
  P_t: number;
  inbound: number;
  outbound: number;
  D_t: number;
  I_t: number;
  equation_string: string;
}

interface Constraint {
  name: string;
  formula: string;
  lhs?: number;
  rhs?: number | string;
  satisfied?: boolean;
  slack?: number;
  utilization_pct?: number;
  vehicle_capacity?: number;
  safety_stock?: number;
  current?: number;
  max_capacity?: number | string;
}

interface StrategicConstraint {
  bound_type: string;
  value_type: string;
  value: number;
  transport_code: string;
  target_iugu: string;
}

interface PerformanceMetrics {
  capacity_utilization_pct: number;
  demand_fulfillment_pct: number;
  inventory_turnover_source: number;
  inventory_turnover_dest: number;
  days_of_supply_source: number;
  days_of_supply_dest: number;
  transport_efficiency: number;
  cost_breakdown_pct: {
    production: number;
    transport: number;
    holding: number;
  };
}

interface RouteData {
  route: {
    source: string;
    destination: string;
    mode: string;
    period: number;
    freight_cost: number | string;
    handling_cost: number | string;
    total_logistics_cost: number | string;
    production_cost: number | string;
    source_capacity: number | string;
    source_type: string;
    destination_type: string;
    destination_demand: number | string;
    source_opening_stock: number | string;
    destination_opening_stock: number | string;
    constraints: StrategicConstraint[];
  };
  decision_variables: {
    P_i_t: DecisionVariable;
    X_i_j_m_t: DecisionVariable;
    I_source_t: DecisionVariable;
    I_dest_t: DecisionVariable;
    T_i_j_m_t: DecisionVariable;
  };
  objective_function: ObjectiveFunction;
  mass_balance: {
    equation: string;
    source_node: MassBalanceNode;
    destination_node: MassBalanceNode;
  };
  constraints: {
    production_capacity: Constraint;
    shipment_upper_bound: Constraint;
    inventory_source: Constraint;
    inventory_destination: Constraint;
    strategic_constraints: StrategicConstraint[];
  };
  metrics: PerformanceMetrics;
  feasibility: {
    is_feasible: boolean;
    issues: string[];
  };
}

interface DataStatus {
  loaded: boolean;
  source: string;
  sheets: string[];
  total_routes: number;
  total_plants: number;
  periods: string[];
}

interface TransportMode {
  code: string;
  name: string;
  vehicle_capacity: string | number;
}

interface MathModel {
  name: string;
  type: string;
  objective: {
    type: string;
    description: string;
    formula: string;
    components: Array<{ name: string; formula: string; unit: string }>;
  };
  decision_variables: Array<{ symbol: string; description: string; unit: string; domain: string }>;
  constraints: Array<{ name: string; formula: string; description: string; scope: string }>;
  indices: Array<{ symbol: string; description: string; set: string }>;
  parameters: Array<{ symbol: string; description: string; source: string }>;
}

const NOT_AVAILABLE = 'Not available in uploaded dataset';

export default function Home() {
  // Data state
  const [dataStatus, setDataStatus] = useState<DataStatus | null>(null);
  const [sources, setSources] = useState<string[]>([]);
  const [destinations, setDestinations] = useState<string[]>([]);
  const [modes, setModes] = useState<TransportMode[]>([]);
  const [periods, setPeriods] = useState<string[]>([]);
  const [mathModel, setMathModel] = useState<MathModel | null>(null);
  const [showModel, setShowModel] = useState(false);
  
  // Selection state
  const [selectedSource, setSelectedSource] = useState<string>('');
  const [selectedDestination, setSelectedDestination] = useState<string>('');
  const [selectedMode, setSelectedMode] = useState<string>('');
  const [selectedPeriod, setSelectedPeriod] = useState<string>('');
  
  // Route data
  const [routeData, setRouteData] = useState<RouteData | null>(null);
  
  // UI state
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [validationErrors, setValidationErrors] = useState<string[]>([]);
  const [dragOver, setDragOver] = useState(false);

  // Load default data on mount
  useEffect(() => {
    loadDefaultData();
    fetchMathModel();
  }, []);

  const fetchMathModel = async () => {
    try {
      const res = await fetch('/api/model');
      const data = await res.json();
      if (data.success) {
        setMathModel(data.model);
      }
    } catch (err) {
      console.error('Failed to fetch model:', err);
    }
  };

  const loadDefaultData = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/load-default', { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        setDataStatus({
          loaded: true,
          source: 'CSV files from project folder',
          sheets: data.sheets || [],
          total_routes: data.total_routes || 0,
          total_plants: data.total_plants || 0,
          periods: data.periods || []
        });
        await fetchSources();
        await fetchPeriods();
      } else {
        setError(data.error || 'Failed to load default data');
      }
    } catch (err) {
      setError('Failed to connect to backend. Make sure the server is running.');
    } finally {
      setLoading(false);
    }
  };

  const handleFileUpload = async (file: File) => {
    setUploading(true);
    setError(null);
    setValidationErrors([]);
    
    const formData = new FormData();
    formData.append('file', file);
    
    try {
      const res = await fetch('/api/upload', {
        method: 'POST',
        body: formData
      });
      const data = await res.json();
      
      if (data.success) {
        setDataStatus({
          loaded: true,
          source: file.name,
          sheets: data.sheets_found || data.sheets || [],
          total_routes: data.total_routes || 0,
          total_plants: data.total_plants || 0,
          periods: data.periods || []
        });
        // Reset selections
        setSelectedSource('');
        setSelectedDestination('');
        setSelectedMode('');
        setSelectedPeriod('');
        setRouteData(null);
        // Fetch new data
        await fetchSources();
        await fetchPeriods();
      } else {
        // Show detailed validation errors
        if (data.errors && Array.isArray(data.errors) && data.errors.length > 0) {
          setValidationErrors(data.errors);
        } else {
          setError(data.error || 'Failed to parse file. Please ensure it contains all required sheets.');
        }
      }
    } catch (err) {
      setError('Failed to upload file');
    } finally {
      setUploading(false);
    }
  };

  const fetchSources = async () => {
    try {
      const res = await fetch('/api/sources');
      const data = await res.json();
      setSources(data.sources || []);
    } catch (err) {
      console.error('Failed to fetch sources:', err);
    }
  };

  const fetchPeriods = async () => {
    try {
      const res = await fetch('/api/periods');
      const data = await res.json();
      setPeriods(data.periods || []);
    } catch (err) {
      console.error('Failed to fetch periods:', err);
    }
  };

  const fetchDestinations = async (source: string) => {
    if (!source) {
      setDestinations([]);
      return;
    }
    try {
      const res = await fetch(`/api/destinations/${encodeURIComponent(source)}`);
      const data = await res.json();
      setDestinations(data.destinations || []);
    } catch (err) {
      console.error('Failed to fetch destinations:', err);
    }
  };

  const fetchModes = async (source: string, destination: string) => {
    if (!source || !destination) {
      setModes([]);
      return;
    }
    try {
      const res = await fetch(`/api/modes/${encodeURIComponent(source)}/${encodeURIComponent(destination)}`);
      const data = await res.json();
      setModes(data.modes || []);
    } catch (err) {
      console.error('Failed to fetch modes:', err);
    }
  };

  const fetchRouteData = async () => {
    if (!selectedSource || !selectedDestination || !selectedMode || !selectedPeriod) {
      return;
    }
    setLoading(true);
    try {
      const params = new URLSearchParams({
        source: selectedSource,
        destination: selectedDestination,
        mode: selectedMode,
        period: selectedPeriod
      });
      const res = await fetch(`/api/route?${params}`);
      const data = await res.json();
      setRouteData(data);
    } catch (err) {
      console.error('Failed to fetch route data:', err);
    } finally {
      setLoading(false);
    }
  };

  // Handle source change
  const handleSourceChange = async (value: string) => {
    setSelectedSource(value);
    setSelectedDestination('');
    setSelectedMode('');
    setRouteData(null);
    await fetchDestinations(value);
  };

  // Handle destination change
  const handleDestinationChange = async (value: string) => {
    setSelectedDestination(value);
    setSelectedMode('');
    setRouteData(null);
    await fetchModes(selectedSource, value);
  };

  // Handle mode change
  const handleModeChange = (value: string) => {
    setSelectedMode(value);
    setRouteData(null);
  };

  // Handle period change
  const handlePeriodChange = (value: string) => {
    setSelectedPeriod(value);
    setRouteData(null);
  };

  // Fetch route data when all selections are made
  useEffect(() => {
    if (selectedSource && selectedDestination && selectedMode && selectedPeriod) {
      fetchRouteData();
    }
  }, [selectedSource, selectedDestination, selectedMode, selectedPeriod]);

  // Drag and drop handlers
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(true);
  };

  const handleDragLeave = () => {
    setDragOver(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    setValidationErrors([]);
    const file = e.dataTransfer.files[0];
    if (file && (file.name.endsWith('.xlsx') || file.name.endsWith('.xls'))) {
      handleFileUpload(file);
    } else {
      setError('Please upload an Excel file (.xlsx or .xls) containing all 7 required data sheets.');
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    setValidationErrors([]);
    const file = e.target.files?.[0];
    if (file) {
      handleFileUpload(file);
    }
  };

  // Get transport icon
  const getTransportIcon = (mode: string) => {
    const modeUpper = mode.toUpperCase();
    if (modeUpper.includes('ROAD') || modeUpper === 'T1') return <Truck className="w-5 h-5" />;
    if (modeUpper.includes('RAIL') || modeUpper === 'T2') return <Train className="w-5 h-5" />;
    if (modeUpper.includes('SEA') || modeUpper === 'T3') return <Ship className="w-5 h-5" />;
    return <Truck className="w-5 h-5" />;
  };

  // Format value or show not available
  const formatValue = (value: any, suffix: string = '') => {
    if (value === NOT_AVAILABLE || value === null || value === undefined) {
      return <span className="not-available">{NOT_AVAILABLE}</span>;
    }
    if (typeof value === 'number') {
      return `${value.toLocaleString()}${suffix}`;
    }
    return `${value}${suffix}`;
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100">
      {/* Header */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-gradient-to-r from-teal-500 to-primary-500 rounded-xl">
                <BarChart3 className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-xl font-bold text-slate-800">Clinker Supply Chain Optimizer</h1>
                <p className="text-sm text-slate-500">Excel-driven dynamic optimization</p>
              </div>
            </div>
            {dataStatus?.loaded && (
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-2 px-4 py-2 bg-green-50 rounded-lg">
                  <Database className="w-4 h-4 text-green-600" />
                  <span className="text-sm font-medium text-green-700">
                    {dataStatus.source}
                  </span>
                </div>
                <button 
                  onClick={loadDefaultData}
                  className="p-2 text-slate-500 hover:text-slate-700 hover:bg-slate-100 rounded-lg transition-colors"
                  title="Reload default data"
                >
                  <RefreshCw className="w-5 h-5" />
                </button>
              </div>
            )}
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8">
        {/* Error Display */}
        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-xl flex items-center gap-3">
            <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0" />
            <p className="text-red-700">{error}</p>
            <button onClick={() => setError(null)} className="ml-auto text-red-500 hover:text-red-700">
              ×
            </button>
          </div>
        )}

        {/* Validation Errors Display */}
        {validationErrors.length > 0 && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-xl">
            <div className="flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
              <div className="flex-1">
                <h3 className="font-semibold text-red-700 mb-2">File Validation Failed</h3>
                <div className="space-y-1">
                  {validationErrors.map((err, idx) => (
                    <p key={idx} className={`text-sm ${err.startsWith('❌') ? 'text-red-600' : err.startsWith('📋') || err.startsWith('💡') ? 'text-slate-600' : err.startsWith('  •') ? 'text-slate-500 ml-4 font-mono text-xs' : 'text-red-600'}`}>
                      {err || '\u00A0'}
                    </p>
                  ))}
                </div>
              </div>
              <button onClick={() => setValidationErrors([])} className="text-red-500 hover:text-red-700">
                ×
              </button>
            </div>
          </div>
        )}

        {/* File Upload Section */}
        <section className="mb-8">
          <div 
            className={`upload-zone ${dragOver ? 'dragging' : ''}`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
          >
            <input 
              type="file" 
              accept=".xlsx,.xls" 
              onChange={handleFileSelect}
              className="hidden" 
              id="file-upload"
            />
            <label htmlFor="file-upload" className="cursor-pointer">
              {uploading ? (
                <div className="flex flex-col items-center">
                  <div className="spinner w-12 h-12 mb-4"></div>
                  <p className="text-slate-600">Validating file structure...</p>
                </div>
              ) : (
                <>
                  <div className="p-4 bg-teal-100 rounded-full w-fit mx-auto mb-4">
                    <FileSpreadsheet className="w-8 h-8 text-teal-600" />
                  </div>
                  <h3 className="text-lg font-semibold text-slate-700 mb-2">
                    Upload Excel File
                  </h3>
                  <p className="text-slate-500 mb-2">
                    Drag & drop or click to browse
                  </p>
                  <p className="text-sm text-slate-400">
                    Supported: .xlsx, .xls
                  </p>
                  <p className="text-xs text-amber-600 mt-2">
                    ⚠️ Must contain all 7 required data sheets
                  </p>
                </>
              )}
            </label>
          </div>
          
          {/* Data Stats */}
          {dataStatus?.loaded && (
            <div className="mt-4 grid grid-cols-4 gap-4">
              <div className="card p-4 text-center">
                <p className="data-label">Total Routes</p>
                <p className="data-value text-teal-600">{dataStatus.total_routes}</p>
              </div>
              <div className="card p-4 text-center">
                <p className="data-label">Plants</p>
                <p className="data-value text-primary-600">{dataStatus.total_plants}</p>
              </div>
              <div className="card p-4 text-center">
                <p className="data-label">Periods</p>
                <p className="data-value text-amber-600">{dataStatus.periods.length}</p>
              </div>
              <div className="card p-4 text-center">
                <p className="data-label">Data Sheets</p>
                <p className="data-value text-blue-600">{dataStatus.sheets.length}</p>
              </div>
            </div>
          )}
          
          {/* Mathematical Model Toggle */}
          {dataStatus?.loaded && (
            <div className="mt-4">
              <button 
                onClick={() => setShowModel(!showModel)}
                className="btn-secondary flex items-center gap-2"
              >
                <Calculator className="w-5 h-5" />
                {showModel ? 'Hide' : 'View'} Mathematical Optimization Model
              </button>
            </div>
          )}
        </section>

        {/* Mathematical Model Section */}
        {showModel && mathModel && (
          <section className="card p-6 mb-8 bg-gradient-to-br from-slate-50 to-blue-50">
            <h2 className="section-title mb-6 flex items-center gap-2">
              <Sigma className="w-5 h-5 text-blue-600" />
              {mathModel.name}
              <span className="ml-2 text-sm font-normal text-slate-500">({mathModel.type})</span>
            </h2>

            {/* Objective Function */}
            <div className="mb-6">
              <h3 className="font-semibold text-slate-700 mb-3 flex items-center gap-2">
                <Target className="w-4 h-4 text-green-600" />
                Objective: {mathModel.objective.type} {mathModel.objective.description}
              </h3>
              <div className="p-4 bg-white rounded-xl border border-slate-200 font-mono text-sm">
                <p className="text-blue-700 font-semibold">{mathModel.objective.formula}</p>
                <div className="mt-3 space-y-1">
                  {mathModel.objective.components.map((comp, idx) => (
                    <p key={idx} className="text-slate-600">
                      <span className="text-green-600">•</span> {comp.name}: <code className="bg-slate-100 px-1 rounded">{comp.formula}</code>
                    </p>
                  ))}
                </div>
              </div>
            </div>

            {/* Decision Variables */}
            <div className="mb-6">
              <h3 className="font-semibold text-slate-700 mb-3 flex items-center gap-2">
                <Calculator className="w-4 h-4 text-purple-600" />
                Decision Variables
              </h3>
              <div className="grid grid-cols-3 gap-3">
                {mathModel.decision_variables.map((v, idx) => (
                  <div key={idx} className="p-3 bg-white rounded-lg border border-slate-200">
                    <p className="font-mono text-purple-600 font-semibold">{v.symbol}</p>
                    <p className="text-sm text-slate-600 mt-1">{v.description}</p>
                    <p className="text-xs text-slate-400 mt-1">Unit: {v.unit} | Domain: {v.domain}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Constraints */}
            <div className="mb-6">
              <h3 className="font-semibold text-slate-700 mb-3 flex items-center gap-2">
                <AlertCircle className="w-4 h-4 text-red-600" />
                Constraints
              </h3>
              <div className="space-y-2">
                {mathModel.constraints.map((c, idx) => (
                  <div key={idx} className="p-3 bg-white rounded-lg border border-slate-200">
                    <div className="flex items-start justify-between">
                      <div>
                        <p className="font-medium text-slate-700">{c.name}</p>
                        <p className="font-mono text-sm text-red-600 mt-1">{c.formula}</p>
                        <p className="text-xs text-slate-500 mt-1">{c.description}</p>
                      </div>
                      <span className="text-xs bg-slate-100 px-2 py-1 rounded">{c.scope}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Parameters & Indices */}
            <div className="grid grid-cols-2 gap-6">
              <div>
                <h3 className="font-semibold text-slate-700 mb-3 flex items-center gap-2">
                  <BookOpen className="w-4 h-4 text-amber-600" />
                  Indices
                </h3>
                <div className="space-y-2">
                  {mathModel.indices.map((idx, i) => (
                    <div key={i} className="flex items-center gap-2 text-sm">
                      <span className="font-mono bg-amber-100 text-amber-700 px-2 py-1 rounded">{idx.symbol}</span>
                      <span className="text-slate-600">{idx.description}</span>
                      <span className="text-slate-400">∈ {idx.set}</span>
                    </div>
                  ))}
                </div>
              </div>
              <div>
                <h3 className="font-semibold text-slate-700 mb-3 flex items-center gap-2">
                  <Database className="w-4 h-4 text-teal-600" />
                  Parameters (from Excel)
                </h3>
                <div className="space-y-2 max-h-48 overflow-y-auto">
                  {mathModel.parameters.map((p, i) => (
                    <div key={i} className="flex items-center gap-2 text-sm">
                      <span className="font-mono bg-teal-100 text-teal-700 px-2 py-1 rounded">{p.symbol}</span>
                      <span className="text-slate-600 flex-1">{p.description}</span>
                      <span className="text-xs text-slate-400">{p.source}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </section>
        )}

        {/* Selection Section */}
        {dataStatus?.loaded && (
          <section className="card p-6 mb-8">
            <h2 className="section-title mb-6 flex items-center gap-2">
              <MapPin className="w-5 h-5 text-teal-500" />
              Route Selection
              <span className="excel-notice ml-auto">Options from uploaded Excel only</span>
            </h2>
            
            <div className="grid grid-cols-4 gap-6">
              {/* Source */}
              <div>
                <label className="block data-label mb-2">Source Plant (IU)</label>
                <select 
                  className="select-dropdown"
                  value={selectedSource}
                  onChange={(e) => handleSourceChange(e.target.value)}
                  disabled={sources.length === 0}
                >
                  <option value="">Select source...</option>
                  {sources.map(s => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
                {sources.length === 0 && (
                  <p className="not-available mt-1">No sources in dataset</p>
                )}
              </div>

              {/* Destination */}
              <div>
                <label className="block data-label mb-2">Destination Plant</label>
                <select 
                  className="select-dropdown"
                  value={selectedDestination}
                  onChange={(e) => handleDestinationChange(e.target.value)}
                  disabled={!selectedSource || destinations.length === 0}
                >
                  <option value="">Select destination...</option>
                  {destinations.map(d => (
                    <option key={d} value={d}>{d}</option>
                  ))}
                </select>
                {selectedSource && destinations.length === 0 && (
                  <p className="not-available mt-1">No routes from {selectedSource}</p>
                )}
              </div>

              {/* Transport Mode */}
              <div>
                <label className="block data-label mb-2">Transport Mode</label>
                <select 
                  className="select-dropdown"
                  value={selectedMode}
                  onChange={(e) => handleModeChange(e.target.value)}
                  disabled={!selectedDestination || modes.length === 0}
                >
                  <option value="">Select mode...</option>
                  {modes.map(m => (
                    <option key={m.code} value={m.code}>{m.code} - {m.name} ({m.vehicle_capacity} tons)</option>
                  ))}
                </select>
                {selectedDestination && modes.length === 0 && (
                  <p className="not-available mt-1">No modes for this route</p>
                )}
              </div>

              {/* Period */}
              <div>
                <label className="block data-label mb-2">Time Period</label>
                <select 
                  className="select-dropdown"
                  value={selectedPeriod}
                  onChange={(e) => handlePeriodChange(e.target.value)}
                  disabled={periods.length === 0}
                >
                  <option value="">Select period...</option>
                  {periods.map(p => (
                    <option key={p} value={p}>{p}</option>
                  ))}
                </select>
              </div>
            </div>

            {/* Selected Route Summary */}
            {selectedSource && selectedDestination && (
              <div className="mt-6 p-4 bg-slate-50 rounded-xl flex items-center gap-4">
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-slate-700">{selectedSource}</span>
                  <ArrowRight className="w-4 h-4 text-slate-400" />
                  <span className="font-semibold text-slate-700">{selectedDestination}</span>
                </div>
                {selectedMode && (
                  <div className="flex items-center gap-2 px-3 py-1 bg-white rounded-lg border border-slate-200">
                    {getTransportIcon(selectedMode)}
                    <span className="text-sm font-medium">{selectedMode}</span>
                  </div>
                )}
                {selectedPeriod && (
                  <div className="flex items-center gap-2 px-3 py-1 bg-white rounded-lg border border-slate-200">
                    <Calendar className="w-4 h-4 text-slate-500" />
                    <span className="text-sm font-medium">{selectedPeriod}</span>
                  </div>
                )}
              </div>
            )}
          </section>
        )}

        {/* Route Insights */}
        {loading && !routeData && (
          <div className="card p-12 flex items-center justify-center">
            <div className="spinner w-8 h-8"></div>
            <span className="ml-4 text-slate-600">Loading route data...</span>
          </div>
        )}

        {routeData && (
          <div className="space-y-6">
            {/* Feasibility Banner */}
            {routeData.feasibility && (
              <div className={`p-4 rounded-xl flex items-center gap-3 ${routeData.feasibility.is_feasible ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'}`}>
                {routeData.feasibility.is_feasible ? (
                  <>
                    <CheckCircle2 className="w-6 h-6 text-green-600" />
                    <div>
                      <p className="font-semibold text-green-800">Solution is Feasible</p>
                      <p className="text-sm text-green-600">All constraints are satisfied</p>
                    </div>
                  </>
                ) : (
                  <>
                    <AlertCircle className="w-6 h-6 text-red-600" />
                    <div className="flex-1">
                      <p className="font-semibold text-red-800">Infeasible Solution</p>
                      <div className="text-sm text-red-600">
                        {routeData.feasibility.issues.map((issue, idx) => (
                          <p key={idx}>• {issue}</p>
                        ))}
                      </div>
                    </div>
                  </>
                )}
              </div>
            )}

            {/* Decision Variables Section */}
            {routeData.decision_variables && (
              <section className="card p-6 bg-gradient-to-br from-purple-50 to-indigo-50">
                <h2 className="section-title mb-6 flex items-center gap-2">
                  <Binary className="w-5 h-5 text-purple-600" />
                  Decision Variables (MILP Solution)
                </h2>
                <div className="grid grid-cols-5 gap-4">
                  <div className="p-4 bg-white rounded-xl shadow-sm">
                    <p className="font-mono text-purple-600 font-bold text-lg">P[i,t]</p>
                    <p className="text-2xl font-bold text-purple-800">{routeData.decision_variables.P_i_t?.value?.toLocaleString() || 0}</p>
                    <p className="text-xs text-purple-500 mt-1">tons</p>
                    <p className="text-xs text-slate-500 mt-2">{routeData.decision_variables.P_i_t?.description}</p>
                  </div>
                  <div className="p-4 bg-white rounded-xl shadow-sm">
                    <p className="font-mono text-indigo-600 font-bold text-lg">X[i,j,m,t]</p>
                    <p className="text-2xl font-bold text-indigo-800">{routeData.decision_variables.X_i_j_m_t?.value?.toLocaleString() || 0}</p>
                    <p className="text-xs text-indigo-500 mt-1">tons shipped</p>
                    <p className="text-xs text-slate-500 mt-2">{routeData.decision_variables.X_i_j_m_t?.description}</p>
                  </div>
                  <div className="p-4 bg-white rounded-xl shadow-sm">
                    <p className="font-mono text-blue-600 font-bold text-lg">I[source,t]</p>
                    <p className="text-2xl font-bold text-blue-800">{routeData.decision_variables.I_source_t?.value?.toLocaleString() || 0}</p>
                    <p className="text-xs text-blue-500 mt-1">tons inventory</p>
                    <p className="text-xs text-slate-500 mt-2">{routeData.decision_variables.I_source_t?.description}</p>
                  </div>
                  <div className="p-4 bg-white rounded-xl shadow-sm">
                    <p className="font-mono text-cyan-600 font-bold text-lg">I[dest,t]</p>
                    <p className="text-2xl font-bold text-cyan-800">{routeData.decision_variables.I_dest_t?.value?.toLocaleString() || 0}</p>
                    <p className="text-xs text-cyan-500 mt-1">tons inventory</p>
                    <p className="text-xs text-slate-500 mt-2">{routeData.decision_variables.I_dest_t?.description}</p>
                  </div>
                  <div className="p-4 bg-white rounded-xl shadow-sm">
                    <p className="font-mono text-teal-600 font-bold text-lg">T[i,j,m,t]</p>
                    <p className="text-2xl font-bold text-teal-800">{routeData.decision_variables.T_i_j_m_t?.value || 0}</p>
                    <p className="text-xs text-teal-500 mt-1">trips (integer)</p>
                    <p className="text-xs text-slate-500 mt-2">{routeData.decision_variables.T_i_j_m_t?.description}</p>
                  </div>
                </div>
                {/* Show formula for trips */}
                {routeData.decision_variables.T_i_j_m_t?.formula && (
                  <div className="mt-4 p-3 bg-white rounded-lg">
                    <p className="text-sm text-slate-600 font-mono">{routeData.decision_variables.T_i_j_m_t.formula}</p>
                  </div>
                )}
              </section>
            )}

            {/* Objective Function Section */}
            {routeData.objective_function && (
              <section className="card p-6 bg-gradient-to-br from-green-50 to-emerald-50">
                <h2 className="section-title mb-6 flex items-center gap-2">
                  <Target className="w-5 h-5 text-green-600" />
                  Objective Function: {routeData.objective_function.type}
                </h2>
                <div className="p-4 bg-white rounded-xl mb-4">
                  <p className="font-mono text-green-700 font-semibold">{routeData.objective_function.formula}</p>
                </div>
                <div className="grid grid-cols-3 gap-4 mb-4">
                  <div className="p-4 bg-white rounded-xl">
                    <p className="data-label text-amber-600">Production Cost</p>
                    <p className="text-2xl font-bold text-amber-700">₹{routeData.objective_function.production_cost?.value?.toLocaleString() || 0}</p>
                    <p className="text-xs text-slate-500 mt-2 font-mono">{routeData.objective_function.production_cost?.calculation}</p>
                  </div>
                  <div className="p-4 bg-white rounded-xl">
                    <p className="data-label text-blue-600">Transport Cost</p>
                    <p className="text-2xl font-bold text-blue-700">₹{routeData.objective_function.transport_cost?.value?.toLocaleString() || 0}</p>
                    <p className="text-xs text-slate-500 mt-2 font-mono">{routeData.objective_function.transport_cost?.calculation}</p>
                    <div className="mt-2 text-xs text-slate-400">
                      <p>Freight: ₹{routeData.objective_function.transport_cost?.freight?.total?.toLocaleString() || 0}</p>
                      <p>Handling: ₹{routeData.objective_function.transport_cost?.handling?.total?.toLocaleString() || 0}</p>
                    </div>
                  </div>
                  <div className="p-4 bg-white rounded-xl">
                    <p className="data-label text-purple-600">Holding Cost</p>
                    <p className="text-2xl font-bold text-purple-700">₹{routeData.objective_function.holding_cost?.value?.toLocaleString() || 0}</p>
                    <p className="text-xs text-slate-500 mt-2 font-mono">{routeData.objective_function.holding_cost?.formula}</p>
                    <div className="mt-2 text-xs text-slate-400">
                      <p>Source: ₹{routeData.objective_function.holding_cost?.source?.cost?.toLocaleString() || 0} (excess: {routeData.objective_function.holding_cost?.source?.excess_inventory?.toLocaleString() || 0} tons)</p>
                      <p>Dest: ₹{routeData.objective_function.holding_cost?.destination?.cost?.toLocaleString() || 0} (excess: {routeData.objective_function.holding_cost?.destination?.excess_inventory?.toLocaleString() || 0} tons)</p>
                    </div>
                  </div>
                </div>
                {/* Total Z */}
                <div className="p-4 bg-gradient-to-r from-green-100 to-emerald-100 rounded-xl border border-green-300">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-semibold text-green-800">Total Cost (Z*)</p>
                      <p className="text-3xl font-bold text-green-900">₹{routeData.objective_function.total_Z?.toLocaleString() || 0}</p>
                    </div>
                    <div className="text-right">
                      <p className="text-sm text-green-700">Cost per ton (Z / Fulfilled Demand)</p>
                      <p className="text-xl font-bold text-green-800">₹{routeData.objective_function.cost_per_ton?.toLocaleString() || 0}/ton</p>
                      <p className="text-xs text-green-600">Demand: {routeData.objective_function.fulfilled_demand?.toLocaleString() || 0} tons</p>
                    </div>
                  </div>
                </div>
              </section>
            )}

            {/* Mass Balance Equations */}
            {routeData.mass_balance && (
              <section className="card p-6 bg-gradient-to-br from-blue-50 to-cyan-50">
                <h2 className="section-title mb-6 flex items-center gap-2">
                  <Scale className="w-5 h-5 text-blue-600" />
                  Mass Balance Equations
                </h2>
                <div className="p-4 bg-white rounded-xl mb-4">
                  <p className="font-mono text-blue-700 font-semibold">{routeData.mass_balance.equation}</p>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  {/* Source Node */}
                  <div className="p-4 bg-white rounded-xl">
                    <h3 className="font-semibold text-amber-700 mb-3 flex items-center gap-2">
                      <MapPin className="w-4 h-4" /> Source: {routeData.mass_balance.source_node?.node}
                    </h3>
                    <div className="space-y-2 text-sm">
                      <div className="flex justify-between"><span className="text-slate-600">Opening Inventory (I[t-1]):</span><span className="font-semibold">{routeData.mass_balance.source_node?.I_t_minus_1?.toLocaleString()}</span></div>
                      <div className="flex justify-between"><span className="text-slate-600">+ Production (P[t]):</span><span className="font-semibold text-green-600">+{routeData.mass_balance.source_node?.P_t?.toLocaleString()}</span></div>
                      <div className="flex justify-between"><span className="text-slate-600">+ Inbound:</span><span className="font-semibold text-blue-600">+{routeData.mass_balance.source_node?.inbound?.toLocaleString()}</span></div>
                      <div className="flex justify-between"><span className="text-slate-600">- Outbound:</span><span className="font-semibold text-red-600">-{routeData.mass_balance.source_node?.outbound?.toLocaleString()}</span></div>
                      <div className="flex justify-between"><span className="text-slate-600">- Demand (D[t]):</span><span className="font-semibold text-red-600">-{routeData.mass_balance.source_node?.D_t?.toLocaleString()}</span></div>
                      <div className="border-t pt-2 flex justify-between"><span className="text-slate-700 font-semibold">= Ending Inventory (I[t]):</span><span className="font-bold text-amber-700">{routeData.mass_balance.source_node?.I_t?.toLocaleString()}</span></div>
                    </div>
                    <div className="mt-3 p-2 bg-slate-50 rounded text-xs font-mono text-slate-600">
                      {routeData.mass_balance.source_node?.equation_string}
                    </div>
                  </div>
                  {/* Destination Node */}
                  <div className="p-4 bg-white rounded-xl">
                    <h3 className="font-semibold text-blue-700 mb-3 flex items-center gap-2">
                      <MapPin className="w-4 h-4" /> Destination: {routeData.mass_balance.destination_node?.node}
                    </h3>
                    <div className="space-y-2 text-sm">
                      <div className="flex justify-between"><span className="text-slate-600">Opening Inventory (I[t-1]):</span><span className="font-semibold">{routeData.mass_balance.destination_node?.I_t_minus_1?.toLocaleString()}</span></div>
                      <div className="flex justify-between"><span className="text-slate-600">+ Production (P[t]):</span><span className="font-semibold text-green-600">+{routeData.mass_balance.destination_node?.P_t?.toLocaleString()}</span></div>
                      <div className="flex justify-between"><span className="text-slate-600">+ Inbound:</span><span className="font-semibold text-blue-600">+{routeData.mass_balance.destination_node?.inbound?.toLocaleString()}</span></div>
                      <div className="flex justify-between"><span className="text-slate-600">- Outbound:</span><span className="font-semibold text-red-600">-{routeData.mass_balance.destination_node?.outbound?.toLocaleString()}</span></div>
                      <div className="flex justify-between"><span className="text-slate-600">- Demand (D[t]):</span><span className="font-semibold text-red-600">-{routeData.mass_balance.destination_node?.D_t?.toLocaleString()}</span></div>
                      <div className="border-t pt-2 flex justify-between"><span className="text-slate-700 font-semibold">= Ending Inventory (I[t]):</span><span className="font-bold text-blue-700">{routeData.mass_balance.destination_node?.I_t?.toLocaleString()}</span></div>
                    </div>
                    <div className="mt-3 p-2 bg-slate-50 rounded text-xs font-mono text-slate-600">
                      {routeData.mass_balance.destination_node?.equation_string}
                    </div>
                  </div>
                </div>
              </section>
            )}

            {/* Constraints Analysis */}
            {routeData.constraints && (
              <section className="card p-6">
                <h2 className="section-title mb-6 flex items-center gap-2">
                  <AlertCircle className="w-5 h-5 text-red-500" />
                  Constraints Analysis
                </h2>
                <div className="grid grid-cols-2 gap-4 mb-4">
                  {/* Production Capacity */}
                  <div className={`p-4 rounded-xl ${routeData.constraints.production_capacity?.satisfied ? 'bg-green-50' : 'bg-red-50'}`}>
                    <div className="flex items-center justify-between mb-2">
                      <p className="font-semibold text-slate-700">{routeData.constraints.production_capacity?.name}</p>
                      {routeData.constraints.production_capacity?.satisfied ? (
                        <CheckCircle className="w-5 h-5 text-green-600" />
                      ) : (
                        <XCircle className="w-5 h-5 text-red-600" />
                      )}
                    </div>
                    <p className="font-mono text-sm text-slate-600">{routeData.constraints.production_capacity?.formula}</p>
                    <div className="mt-2 text-sm">
                      <p>LHS: {routeData.constraints.production_capacity?.lhs} | RHS: {routeData.constraints.production_capacity?.rhs}</p>
                      <p className="text-green-600">Slack: {routeData.constraints.production_capacity?.slack} tons</p>
                      <p>Utilization: {routeData.constraints.production_capacity?.utilization_pct}%</p>
                    </div>
                  </div>
                  {/* Shipment Upper Bound */}
                  <div className={`p-4 rounded-xl ${routeData.constraints.shipment_upper_bound?.satisfied ? 'bg-green-50' : 'bg-red-50'}`}>
                    <div className="flex items-center justify-between mb-2">
                      <p className="font-semibold text-slate-700">{routeData.constraints.shipment_upper_bound?.name}</p>
                      {routeData.constraints.shipment_upper_bound?.satisfied ? (
                        <CheckCircle className="w-5 h-5 text-green-600" />
                      ) : (
                        <XCircle className="w-5 h-5 text-red-600" />
                      )}
                    </div>
                    <p className="font-mono text-sm text-slate-600">{routeData.constraints.shipment_upper_bound?.formula}</p>
                    <div className="mt-2 text-sm">
                      <p>LHS: {routeData.constraints.shipment_upper_bound?.lhs} | RHS: {routeData.constraints.shipment_upper_bound?.rhs}</p>
                      <p className="text-slate-500">Vehicle Capacity: {routeData.constraints.shipment_upper_bound?.vehicle_capacity} tons/trip</p>
                    </div>
                  </div>
                  {/* Inventory Source */}
                  <div className={`p-4 rounded-xl ${routeData.constraints.inventory_source?.satisfied ? 'bg-green-50' : 'bg-red-50'}`}>
                    <div className="flex items-center justify-between mb-2">
                      <p className="font-semibold text-slate-700">{routeData.constraints.inventory_source?.name}</p>
                      {routeData.constraints.inventory_source?.satisfied ? (
                        <CheckCircle className="w-5 h-5 text-green-600" />
                      ) : (
                        <XCircle className="w-5 h-5 text-red-600" />
                      )}
                    </div>
                    <p className="font-mono text-sm text-slate-600">{routeData.constraints.inventory_source?.formula}</p>
                    <div className="mt-2 text-sm">
                      <p>Safety Stock: {routeData.constraints.inventory_source?.safety_stock}</p>
                      <p>Current: {routeData.constraints.inventory_source?.current}</p>
                      <p>Max Capacity: {routeData.constraints.inventory_source?.max_capacity}</p>
                    </div>
                  </div>
                  {/* Inventory Destination */}
                  <div className={`p-4 rounded-xl ${routeData.constraints.inventory_destination?.satisfied ? 'bg-green-50' : 'bg-red-50'}`}>
                    <div className="flex items-center justify-between mb-2">
                      <p className="font-semibold text-slate-700">{routeData.constraints.inventory_destination?.name}</p>
                      {routeData.constraints.inventory_destination?.satisfied ? (
                        <CheckCircle className="w-5 h-5 text-green-600" />
                      ) : (
                        <XCircle className="w-5 h-5 text-red-600" />
                      )}
                    </div>
                    <p className="font-mono text-sm text-slate-600">{routeData.constraints.inventory_destination?.formula}</p>
                    <div className="mt-2 text-sm">
                      <p>Safety Stock: {routeData.constraints.inventory_destination?.safety_stock}</p>
                      <p>Current: {routeData.constraints.inventory_destination?.current}</p>
                      <p>Max Capacity: {routeData.constraints.inventory_destination?.max_capacity}</p>
                    </div>
                  </div>
                </div>
                {/* Strategic Constraints */}
                {routeData.constraints.strategic_constraints && routeData.constraints.strategic_constraints.length > 0 && (
                  <div className="mt-4">
                    <h3 className="font-semibold text-slate-700 mb-3">Strategic Constraints (from IUGUConstraint.csv)</h3>
                    <div className="space-y-2">
                      {routeData.constraints.strategic_constraints.map((c, idx) => (
                        <div key={idx} className="p-3 bg-amber-50 rounded-lg">
                          <p className="text-sm">
                            <span className="font-semibold">Bound:</span> {c.bound_type} | 
                            <span className="font-semibold"> Value Type:</span> {c.value_type} | 
                            <span className="font-semibold"> Value:</span> {c.value}
                            {c.transport_code && ` | Transport: ${c.transport_code}`}
                            {c.target_iugu && ` | Target: ${c.target_iugu}`}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </section>
            )}

            {/* Performance Metrics */}
            {routeData.metrics && (
              <section className="card p-6">
                <h2 className="section-title mb-6 flex items-center gap-2">
                  <Activity className="w-5 h-5 text-teal-500" />
                  Performance Metrics
                </h2>
                <div className="grid grid-cols-4 gap-4 mb-4">
                  <div className="p-4 bg-teal-50 rounded-xl">
                    <p className="data-label text-teal-600">Capacity Utilization</p>
                    <p className={`text-2xl font-bold ${routeData.metrics.capacity_utilization_pct > 100 ? 'text-red-700' : 'text-teal-700'}`}>
                      {routeData.metrics.capacity_utilization_pct?.toFixed(1)}%
                    </p>
                  </div>
                  <div className="p-4 bg-emerald-50 rounded-xl">
                    <p className="data-label text-emerald-600">Demand Fulfillment</p>
                    <p className={`text-2xl font-bold ${routeData.metrics.demand_fulfillment_pct >= 100 ? 'text-emerald-700' : 'text-amber-700'}`}>
                      {routeData.metrics.demand_fulfillment_pct?.toFixed(1)}%
                    </p>
                  </div>
                  <div className="p-4 bg-blue-50 rounded-xl">
                    <p className="data-label text-blue-600">Transport Efficiency</p>
                    <p className="text-2xl font-bold text-blue-700">
                      {routeData.metrics.transport_efficiency?.toFixed(1)}%
                    </p>
                  </div>
                  <div className="p-4 bg-violet-50 rounded-xl">
                    <p className="data-label text-violet-600">Days of Supply (Dest)</p>
                    <p className="text-2xl font-bold text-violet-700">
                      {routeData.metrics.days_of_supply_dest?.toFixed(1) || '∞'}
                    </p>
                  </div>
                </div>
                {/* Inventory Metrics */}
                <div className="grid grid-cols-2 gap-4">
                  <div className="p-4 bg-slate-50 rounded-xl">
                    <p className="data-label">Inventory Turnover (Source)</p>
                    <p className="text-xl font-bold">{routeData.metrics.inventory_turnover_source?.toFixed(2) || 0}x</p>
                  </div>
                  <div className="p-4 bg-slate-50 rounded-xl">
                    <p className="data-label">Inventory Turnover (Dest)</p>
                    <p className="text-xl font-bold">{routeData.metrics.inventory_turnover_dest?.toFixed(2) || 0}x</p>
                  </div>
                </div>
                {/* Cost Breakdown Chart */}
                {routeData.metrics.cost_breakdown_pct && (
                  <div className="mt-4 p-4 bg-slate-50 rounded-xl">
                    <p className="data-label mb-3">Cost Breakdown (%)</p>
                    <div className="flex items-center gap-2">
                      <div 
                        className="h-8 bg-amber-500 rounded-l-lg flex items-center justify-center text-white text-xs font-medium"
                        style={{ width: `${routeData.metrics.cost_breakdown_pct.production}%`, minWidth: routeData.metrics.cost_breakdown_pct.production > 5 ? '80px' : '0' }}
                      >
                        {routeData.metrics.cost_breakdown_pct.production > 5 && `Prod ${routeData.metrics.cost_breakdown_pct.production.toFixed(0)}%`}
                      </div>
                      <div 
                        className="h-8 bg-blue-500 flex items-center justify-center text-white text-xs font-medium"
                        style={{ width: `${routeData.metrics.cost_breakdown_pct.transport}%`, minWidth: routeData.metrics.cost_breakdown_pct.transport > 5 ? '80px' : '0' }}
                      >
                        {routeData.metrics.cost_breakdown_pct.transport > 5 && `Transport ${routeData.metrics.cost_breakdown_pct.transport.toFixed(0)}%`}
                      </div>
                      <div 
                        className="h-8 bg-purple-500 rounded-r-lg flex items-center justify-center text-white text-xs font-medium"
                        style={{ width: `${routeData.metrics.cost_breakdown_pct.holding}%`, minWidth: routeData.metrics.cost_breakdown_pct.holding > 5 ? '80px' : '0' }}
                      >
                        {routeData.metrics.cost_breakdown_pct.holding > 5 && `Hold ${routeData.metrics.cost_breakdown_pct.holding.toFixed(0)}%`}
                      </div>
                    </div>
                    <div className="flex justify-around mt-2 text-xs text-slate-500">
                      <span className="flex items-center gap-1"><div className="w-3 h-3 bg-amber-500 rounded"></div> Production</span>
                      <span className="flex items-center gap-1"><div className="w-3 h-3 bg-blue-500 rounded"></div> Transport</span>
                      <span className="flex items-center gap-1"><div className="w-3 h-3 bg-purple-500 rounded"></div> Holding</span>
                    </div>
                  </div>
                )}
              </section>
            )}

            {/* Raw Excel Data Section */}
            {routeData.route && (
              <section className="card p-6">
                <h2 className="section-title mb-6 flex items-center gap-2">
                  <Database className="w-5 h-5 text-slate-500" />
                  Raw Data from Excel Files
                </h2>
                <div className="grid grid-cols-4 gap-4">
                  <div className="p-3 bg-slate-50 rounded-lg">
                    <p className="data-label">Source Type</p>
                    <p className="font-semibold">{routeData.route.source_type || 'N/A'}</p>
                  </div>
                  <div className="p-3 bg-slate-50 rounded-lg">
                    <p className="data-label">Destination Type</p>
                    <p className="font-semibold">{routeData.route.destination_type || 'N/A'}</p>
                  </div>
                  <div className="p-3 bg-slate-50 rounded-lg">
                    <p className="data-label">Freight Cost</p>
                    <p className="font-semibold">{formatValue(routeData.route.freight_cost, ' ₹/ton')}</p>
                  </div>
                  <div className="p-3 bg-slate-50 rounded-lg">
                    <p className="data-label">Handling Cost</p>
                    <p className="font-semibold">{formatValue(routeData.route.handling_cost, ' ₹/ton')}</p>
                  </div>
                  <div className="p-3 bg-slate-50 rounded-lg">
                    <p className="data-label">Production Cost</p>
                    <p className="font-semibold">{formatValue(routeData.route.production_cost, ' ₹/ton')}</p>
                  </div>
                  <div className="p-3 bg-slate-50 rounded-lg">
                    <p className="data-label">Source Capacity</p>
                    <p className="font-semibold">{formatValue(routeData.route.source_capacity, ' tons')}</p>
                  </div>
                  <div className="p-3 bg-slate-50 rounded-lg">
                    <p className="data-label">Destination Demand</p>
                    <p className="font-semibold">{formatValue(routeData.route.destination_demand, ' tons')}</p>
                  </div>
                  <div className="p-3 bg-slate-50 rounded-lg">
                    <p className="data-label">Total Logistics</p>
                    <p className="font-semibold">{formatValue(routeData.route.total_logistics_cost, ' ₹/ton')}</p>
                  </div>
                </div>
              </section>
            )}
          </div>
        )}

        {/* Empty State */}
        {dataStatus?.loaded && !routeData && !loading && (
          <div className="card p-12 text-center">
            <div className="p-4 bg-slate-100 rounded-full w-fit mx-auto mb-4">
              <MapPin className="w-8 h-8 text-slate-400" />
            </div>
            <h3 className="text-lg font-semibold text-slate-700 mb-2">Select a Route</h3>
            <p className="text-slate-500">
              Choose source, destination, transport mode, and period to view route insights
            </p>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="mt-12 border-t border-slate-200 bg-white">
        <div className="max-w-7xl mx-auto px-6 py-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm text-slate-500">
              <Database className="w-4 h-4" />
              <span>All decisions and insights are derived exclusively from the uploaded dataset</span>
            </div>
            <div className="text-sm text-slate-400">
              Clinker Supply Chain Optimizer v1.0
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
