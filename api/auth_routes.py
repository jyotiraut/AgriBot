from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
import jwt
from db.mongo import get_db
from config import get_settings
from bson import ObjectId

router = APIRouter()
settings = get_settings()

security = HTTPBearer()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
# JWT config comes from settings (single source of truth). Set JWT_SECRET in the
# environment for production — the default is only safe for local development.
SECRET_KEY = settings.jwt_secret
ALGORITHM = settings.jwt_algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = settings.jwt_expire_hours * 60

class UserRegister(BaseModel):
    email: EmailStr
    password: str
    name: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    user_id: str

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: timedelta):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    db = get_db()
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid auth credentials")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid auth credentials")
        
    user = await db["users"].find_one({"_id": ObjectId(user_id)})
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user

@router.post("/register", response_model=Token)
async def register_user(user: UserRegister):
    db = get_db()
    collection = db["users"]
    
    # Check if user exists
    if await collection.find_one({"email": user.email}):
        raise HTTPException(status_code=400, detail="Email already registered")
        
    # Create profile
    hashed_pw = get_password_hash(user.password)
    new_user = {
        "email": user.email,
        "password": hashed_pw,
        "name": user.name,
        "created_at": datetime.now(timezone.utc),
        "is_active": True
    }
    
    res = await collection.insert_one(new_user)
    user_id = str(res.inserted_id)
    
    # Generate token
    token = create_access_token(data={"sub": user_id}, expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    return {"access_token": token, "token_type": "bearer", "user_id": user_id}

@router.post("/login", response_model=Token)
async def login_user(user: UserLogin):
    db = get_db()
    collection = db["users"]
    
    profile = await collection.find_one({"email": user.email})
    if not profile or not verify_password(user.password, profile.get("password", "")):
        raise HTTPException(status_code=401, detail="Invalid email or password")
        
    user_id = str(profile["_id"])
    token = create_access_token(data={"sub": user_id}, expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    
    return {"access_token": token, "token_type": "bearer", "user_id": user_id}