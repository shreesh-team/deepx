# Plan: Database Login & Registration (spec 01-database-login)

## Context

The spec requires a user registration and login system backed by the existing PostgreSQL database. The DB connection and async session infrastructure are already in place (`app/db/database.py`, `app/core/config.py`). There are no models, schemas, or route handlers yet. No migration tool is set up, so the `users` table will be created via SQLAlchemy `metadata.create_all()` at startup.

---

## New Dependencies

None — password hashing uses Python's stdlib `hashlib` (see note below).

---

## Files to Create

### `app/models/__init__.py`
Empty init; exposes the `Base` declarative base and imports `User` so `metadata.create_all` discovers the table.

### `app/models/base.py`
Defines `Base = DeclarativeBase()` — shared by all models.

### `app/models/user.py`
SQLAlchemy ORM model matching the spec schema:
```
id          INTEGER     primary key, autoincrement
name        TEXT        not null
email       TEXT        not null, unique
password    TEXT        not null  (stored as PBKDF2-SHA256 hash)
created_at  TIMESTAMP   server_default=func.now()
```

### `app/schemas/__init__.py`
Empty init.

### `app/schemas/user.py`
Pydantic v2 schemas:
- `RegisterRequest` — `name: str`, `email: EmailStr`, `password: str`
- `LoginRequest` — `email: EmailStr`, `password: str`
- `UserResponse` — `id: int`, `name: str`, `email: str`, `created_at: str` (formatted YYYY-MM-DD per spec)

### `app/core/security.py`
Two utility functions using **stdlib `hashlib.pbkdf2_hmac` (SHA-256, 260 000 iterations)**:
- `hash_password(plain: str) -> str` — generates a random 32-byte salt, hashes with PBKDF2-SHA256, returns base64(salt + key)
- `verify_password(plain: str, hashed: str) -> bool` — extracts salt from stored hash and re-derives

> **Why not bcrypt/passlib?** `passlib 1.7.4` (latest) is incompatible with `bcrypt ≥ 4.0` (passlib reads `bcrypt.__about__.__version__` which no longer exists). `bcrypt 5.0.0` additionally dropped its `__init__.py` on Windows, making direct import impossible. PBKDF2-SHA256 with 260 k iterations is NIST-approved and requires no external dependencies.

### `app/routers/__init__.py`
Empty init.

### `app/routers/auth.py`
Two endpoints, both using `get_db` dependency from `app/db/database.py`:

**POST `/register`**
1. Check if email already exists → 409 `{"detail": "Email already registered"}`
2. Hash password via `hash_password()`
3. Insert new `User` row, `db.commit()`
4. Return 201 + `UserResponse`

**POST `/login`**
1. Look up user by email → 401 `{"detail": "Invalid email or password"}` if not found
2. `verify_password()` → same 401 if mismatch
3. Return 200 + `UserResponse`

---

## Files to Modify

### `main.py`
1. Import `Base` from `app/models/__init__.py` and `engine` (already imported)
2. In `lifespan`, after the `SELECT 1` health check, call `async with engine.begin() as conn: await conn.run_sync(Base.metadata.create_all)` to create the `users` table if it doesn't exist
3. Import and include `auth_router` from `app/routers/auth.py` with prefix `/auth` (giving `/auth/register` and `/auth/login`) — or no prefix per spec (giving `/register` and `/login`). **Spec says `/login` and `/register`**, so include with no prefix.

---

## Final File Structure

```
app/
├── models/
│   ├── __init__.py      (imports Base + User)
│   ├── base.py          (DeclarativeBase)
│   └── user.py          (User ORM model)
├── schemas/
│   ├── __init__.py
│   └── user.py          (RegisterRequest, LoginRequest, UserResponse)
├── core/
│   ├── config.py        (unchanged)
│   └── security.py      (hash_password, verify_password)
├── routers/
│   ├── __init__.py
│   └── auth.py          (/register, /login)
└── db/
    └── database.py      (unchanged — get_db reused as-is)
main.py                  (add create_all + include router)
```

---

## Verification

1. `uv run fastapi dev main.py` — startup should print `[DB] PostgreSQL connection: OK` and create the `users` table
2. `POST /register` with `{"name":"Alice","email":"alice@example.com","password":"secret"}` → 201 with user object, `created_at` in `YYYY-MM-DD`
3. Repeat same email → 409 `{"detail": "Email already registered"}`
4. `POST /login` with correct credentials → 200 with user object
5. `POST /login` with wrong password → 401
6. `POST /login` with unknown email → 401
