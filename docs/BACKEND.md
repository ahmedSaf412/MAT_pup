# Backend Technology Documentation

## Tech Stack

| Technology | Version | Purpose |
|-----------|---------|---------|
| **FastAPI** | 0.110+ | Async Python web framework with auto-docs |
| **Uvicorn** | 0.27+ | ASGI server to run FastAPI |
| **SQLAlchemy** | 2.0+ | ORM for database models |
| **PostgreSQL** | 15+ | Primary relational database |
| **Alembic** | 1.13+ | Database migrations |
| **python-jose** | 3.3+ | JWT token creation/verification |
| **Passlib + bcrypt** | — | Password hashing |
| **TensorFlow** | 2.15+ | Load & run the trained LSTM model |
| **WebSockets** | Built-in | Real-time pose data streaming |

---

## Why These Technologies?

### FastAPI
- **Async by default** — handles many concurrent WebSocket connections
- **Auto-generated OpenAPI docs** at `/docs` (Swagger UI)
- **Pydantic** validation — request/response schemas are type-safe
- Built-in **WebSocket** support (critical for real-time pose streaming)
- Fastest Python web framework (after Starlette, which it's built on)

### PostgreSQL
- **ACID-compliant** relational database
- **JSON columns** for flexible move data storage
- Scales well for production
- Great tooling (pgAdmin, psql, Alembic migrations)

### JWT Authentication
- **Stateless** — no server-side sessions
- **Scalable** — any backend instance can verify the token
- Token contains user ID and expiry, signed with a secret key

---

## API Endpoints

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register` | Register new user (email, password, name) |
| POST | `/api/auth/login` | Login → returns `{access_token, token_type}` |

### Users
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/users/me` | Yes | Get current user profile |
| PUT | `/api/users/me` | Yes | Update profile (name, belt_level) |

### Training Sessions
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/sessions` | Yes | List user's training sessions |
| GET | `/api/sessions/{id}` | Yes | Get session details |
| POST | `/api/sessions` | Yes | Save completed session data |

### Move Catalog
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/moves` | No | List all available moves |
| GET | `/api/moves/{id}` | No | Get move details + reference angles |

### WebSocket
| Endpoint | Description |
|----------|-------------|
| `ws://host/ws/pose` | Bidirectional real-time pose stream |

---

## WebSocket Protocol

### Client → Server (every ~100ms)
```json
{
  "type": "pose_data",
  "timestamp": 1709123456.789,
  "landmarks": [
    {"x": 0.5, "y": 0.3, "z": -0.1, "visibility": 0.99},
    ...
  ]
}
```

### Server → Client (after processing)
```json
{
  "type": "classification",
  "move": "front_kick",
  "move_display": "Front Kick",
  "confidence": 0.92,
  "corrections": [
    {
      "joint": "left_knee",
      "message": "Raise your left knee higher — aim for waist height",
      "severity": "warning"
    },
    {
      "joint": "right_hand",
      "message": "Keep your guard hand near your chin",
      "severity": "info"
    }
  ]
}
```

---

## Database Schema

### `users` Table
| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PK, auto-increment |
| email | VARCHAR(255) | UNIQUE, NOT NULL |
| hashed_password | VARCHAR(255) | NOT NULL |
| full_name | VARCHAR(100) | NOT NULL |
| belt_level | VARCHAR(20) | DEFAULT 'white' |
| created_at | TIMESTAMP | DEFAULT now() |

### `training_sessions` Table
| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PK, auto-increment |
| user_id | INTEGER | FK → users.id |
| start_time | TIMESTAMP | NOT NULL |
| end_time | TIMESTAMP | — |
| moves_performed | JSON | Array of move results |
| overall_score | FLOAT | 0.0–100.0 |

### `move_catalog` Table
| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PK, auto-increment |
| name | VARCHAR(100) | UNIQUE, NOT NULL |
| martial_art | VARCHAR(50) | DEFAULT 'karate' |
| description | TEXT | — |
| reference_angles | JSON | Ideal joint angles |

---

## ML Service Integration

The `ml_service.py` module:
1. **Loads the LSTM model** at startup (`model.h5`)
2. **Loads the scaler** (`scaler.pkl`) and label encoder (`label_encoder.pkl`)
3. Exposes a `predict(landmarks_sequence)` function:
   - Input: 30 frames × 33 landmarks × 3 coords = shape `(1, 30, 99)`
   - Computes joint angles from landmarks → feature vector
   - Scales features using the saved scaler
   - Runs model prediction → returns `(move_name, confidence)`

## Correction Service

The `correction.py` module:
1. Loads **reference angles** from the move catalog for the predicted move
2. Compares user's current joint angles to the reference
3. If angle difference exceeds threshold (e.g., >15°), generates a correction
4. Returns list of `{joint, message, severity}` corrections

---

## Running the Backend

```bash
# 1. Create virtual environment
python -m venv venv
venv\Scripts\activate    # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up PostgreSQL (create DB)
# createdb martial_arts_db

# 4. Run migrations
alembic upgrade head

# 5. Start the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Access auto-docs at: `http://localhost:8000/docs`

---

## Environment Variables

```env
DATABASE_URL=postgresql://user:password@localhost:5432/martial_arts_db
SECRET_KEY=your-super-secret-key-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
```
