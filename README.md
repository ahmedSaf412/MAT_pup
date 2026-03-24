# Setup Guide for Martial Arts AI Trainer

## **1. Clone the Repository**
```bash
git clone https://github.com/mohamedaboelenin617-web/martial-arts-trainer.git
cd martial-arts-trainer
```

---

## **2. Frontend Setup (Next.js - Node.js)**

### Prerequisites
- **Node.js** (v16 or higher)
- **npm** or **yarn**

### Installation Steps
```bash
cd frontend

# Install dependencies
npm install
# or
yarn install

# Create environment file (if needed)
cp .env.example .env.local  # If .env.example exists, otherwise create .env.local manually

# Start development server
npm run dev
# or
yarn dev
```

**Frontend will be available at:** `http://localhost:3000`

### Available Scripts
- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm start` - Start production server

### Frontend Dependencies
- **Next.js** 16.1.6
- **React** 19.2.3
- **MediaPipe** (Pose detection)
- **Chart.js** (Data visualization)
- **Axios** (HTTP client)

---

## **3. Backend Setup (Python/FastAPI)**

### Prerequisites
- **Python 3.8+**
- **pip** (Python package manager)
- **Virtual Environment** (recommended)

### Installation Steps
```bash
cd backend

# Create a virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create environment file
touch .env
# Add your configuration variables to .env file
# Example: DATABASE_URL, SECRET_KEY, etc.

# Run migrations (if applicable)
alembic upgrade head

# Start development server
uvicorn app.main:app --reload
```

**Backend will be available at:** `http://localhost:8000`
**API docs:** `http://localhost:8000/docs`

### Backend Dependencies
- **FastAPI** 0.110.0 - Web framework
- **Uvicorn** 0.27.1 - ASGI server
- **SQLAlchemy** 2.0.27 - ORM
- **Alembic** 1.13.1 - Database migrations
- **Pydantic** 2.6.1 - Data validation
- **NumPy** 1.26.4 - Numerical computing
- **Scikit-learn** 1.4.0 - Machine learning
- **Python-dotenv** 1.0.1 - Environment variables
- **WebSockets** 12.0 - Real-time communication

---

## **4. Environment Configuration**

### Backend (.env file)
```bash
# Database Configuration
DATABASE_URL=sqlite:///./martial_arts.db

# JWT Configuration
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256

# CORS Settings (if needed)
ALLOWED_ORIGINS=http://localhost:3000

# API Configuration
API_PORT=8000
```

### Frontend (.env.local file - if needed)
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## **5. Complete Startup Process**

### Terminal 1 - Backend
```bash
cd backend
source venv/bin/activate  # On Windows: venv\Scripts\activate
uvicorn app.main:app --reload
```

### Terminal 2 - Frontend
```bash
cd frontend
npm run dev
```

### Verify Everything Works
- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8000`
- Swagger Docs: `http://localhost:8000/docs`

---

## **6. Troubleshooting**

### Frontend Issues
- **Port 3000 already in use:** `npm run dev -- -p 3001`
- **Module not found:** Delete `node_modules` and `package-lock.json`, then reinstall

### Backend Issues
- **Port 8000 already in use:** `uvicorn app.main:app --reload --port 8001`
- **Database errors:** Check `.env` DATABASE_URL configuration
- **Virtual environment issues:** Deactivate and recreate: `deactivate` then `python -m venv venv`

---

## **📁 Project Structure**
```
martial-arts-trainer/
├── frontend/          (Next.js React app)
│   ├── app/          (App router)
│   ├── package.json
│   └── public/
├── backend/          (FastAPI Python app)
│   ├── app/          (Main application)
│   ├── requirements.txt
│   └── alembic/      (Database migrations)
└── docs/
```

---

That's it! Your teammate should follow these steps in order and the project will be running. 🎉
