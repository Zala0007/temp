# Clinker Supply Chain Optimizer

An Excel-driven dynamic supply chain optimization system where **all data comes exclusively from the uploaded dataset**. No defaults, no assumptions, no fallback values.

## Core Principle

> **HARD RULE**: The system behaves as a "data mirror" of the uploaded Excel. If something is not present in the Excel → it does not exist in the system.

## Features

- **Dynamic Dropdowns**: All selection options populated ONLY from Excel data
- **Cascading Filters**: 
  - Source → Destination filtering based on available routes
  - Destination → Transport Mode based on route configuration
  - All periods extracted from Excel only
- **Complete Insights**: Cost breakdown, capacity, inventory, constraints - all from Excel
- **Data Validation**: Invalid selections not in Excel are blocked
- **Completeness Indicators**: Shows what data is available/missing for each route

## Data Structure

The system expects these data sheets (either as separate CSV files or Excel sheets):

| Sheet | Purpose | Key Columns |
|-------|---------|-------------|
| IUGUType | Plant classification | IUGU_CODE, TYPE (IU/GU) |
| LogisticsIUGU | Route definitions | FROM IU CODE, TO IUGU CODE, TRANSPORT CODE, TIME PERIOD, FREIGHT COST, HANDLING COST |
| ClinkerCapacity | Production capacity | IU CODE, TIME PERIOD, IU CAPACITY |
| ClinkerDemand | Demand by plant | IUGU CODE, TIME PERIOD, DEMAND |
| ProductionCost | Production costs | IU CODE, TIME PERIOD, PRODUCTION COST |
| IUGUOpeningStock | Initial inventory | IUGU CODE, OPENING STOCK |
| IUGUClosingStock | Stock limits | IUGU CODE, TIME PERIOD, MIN CLOSING STOCK, MAX CLOSING STOCK |
| IUGUConstraint | Constraints | Various constraint definitions |

## Quick Start

### Prerequisites

- Python 3.8+
- Node.js 18+

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Run the server
python api.py
```

The backend runs on `http://localhost:5000`

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev
```

The frontend runs on `http://localhost:3000`

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/upload` | POST | Upload Excel file |
| `/api/load-default` | POST | Load CSV files from project folder |
| `/api/sources` | GET | Get all source IU codes |
| `/api/destinations/<source>` | GET | Get valid destinations for a source |
| `/api/modes/<source>/<dest>` | GET | Get transport modes for a route |
| `/api/periods` | GET | Get all time periods |
| `/api/route` | GET | Get complete route insights |
| `/api/plant/<code>` | GET | Get plant details |

## Transport Modes

| Code | Mode | Capacity |
|------|------|----------|
| T1 | Road | 30 tons |
| T2 | Rail | 3,000 tons |
| T3 | Sea | 10,000 tons |

## Project Structure

```
AIDTM/
├── backend/
│   ├── api.py              # Flask REST API
│   ├── data_parser.py      # Excel/CSV parsing engine
│   └── requirements.txt    # Python dependencies
├── frontend/
│   ├── src/
│   │   └── app/
│   │       ├── globals.css # Global styles
│   │       ├── layout.tsx  # Root layout
│   │       └── page.tsx    # Main application
│   ├── package.json        # Node dependencies
│   ├── next.config.js      # API proxy config
│   └── tailwind.config.js  # Tailwind configuration
└── *.csv                   # Data files
```

## Usage Flow

1. **Upload Excel** or let the system load default CSV files
2. **Select Source** - Dropdown shows only IU codes from Excel
3. **Select Destination** - Filtered to show only valid routes from the source
4. **Select Mode** - Auto-derived from Excel for the selected route
5. **Select Period** - Shows periods available in the dataset
6. **View Insights** - All data computed from Excel exclusively

## Key Behaviors

- If a route doesn't exist in Excel → Selection blocked
- If cost data missing → Shows "Not available in uploaded dataset"
- If capacity missing → Shows "Not available in uploaded dataset"
- No synthetic data ever generated
- Footer always displays: "All decisions and insights are derived exclusively from the uploaded dataset"

## Technologies

**Backend:**
- Python 3.8+
- Flask + Flask-CORS
- Pandas, NumPy
- Openpyxl (Excel parsing)

**Frontend:**
- Next.js 14
- React 18
- TypeScript
- Tailwind CSS
- Lucide React (icons)

---

*Built with strict data integrity principles - the system shows exactly what's in your Excel, nothing more, nothing less.*
