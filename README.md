# IKSHANA
### Fake Vote Invigilator | Election Control System

> A full-stack voter authentication and fraud detection system designed to prevent duplicate voting and voter impersonation before a vote is cast.

---

## 📌 Overview

**Ikshana** is a real-time election security system that acts as an authentication layer before a voter proceeds to the Electronic Voting Machine (EVM).

The system verifies a voter using multiple identity factors including:

- Voter ID
- Fingerprint authentication
- Facial verification

It also maintains voting records and detects suspicious activity such as:

- Duplicate voting attempts
- Voter impersonation
- Biometric reuse
- Booth-level inconsistencies
- Suspicious voting activity

Ikshana provides separate interfaces for **Booth Officers** and **Election Administrators**, allowing election activity to be monitored centrally in real time.

---

## 🎯 Problem Statement

Traditional voter verification primarily depends on identity documents and manual verification. This can create vulnerabilities such as:

- Impersonation using another person's voter ID
- Attempts to vote multiple times
- Manual verification errors
- Lack of centralized monitoring
- Delayed detection of suspicious voting activity

Ikshana addresses these problems by introducing a **multi-factor digital authentication and monitoring layer** before voting.

---

## 💡 Solution

The system follows a multi-stage authentication process:

```text
                    Voter
                      │
                      ▼
               ┌─────────────┐
               │   Voter ID  │
               └──────┬──────┘
                      │
                      ▼
              ┌──────────────┐
              │ Fingerprint  │
              │ Verification │
              └──────┬───────┘
                     │
                     ▼
              ┌──────────────┐
              │     Face     │
              │ Verification │
              └──────┬───────┘
                     │
                     ▼
             ┌─────────────────┐
             │ Duplicate Vote  │
             │ / Fraud Check   │
             └────────┬────────┘
                      │
             ┌────────┴────────┐
             │                 │
           Valid             Suspicious
             │                 │
             ▼                 ▼
        Allow Voting       Block / Log
```

---

# ✨ Key Features

## 🧑‍💼 Booth Officer Authentication

Booth officers authenticate themselves before accessing their assigned polling booth.

Features include:

- Officer ID and password authentication
- OTP-based verification
- Session management
- Login lockout protection
- Booth assignment validation

---

## 🪪 Voter Authentication

Voters are authenticated using multiple factors.

### 1. Voter ID

The voter provides their registered voter identification details.

### 2. Fingerprint Verification

A **Mantra MFS100** fingerprint scanner is used to capture and verify the voter's fingerprint.

The system uses biometric matching to determine whether the captured fingerprint corresponds to the registered voter.

### 3. Facial Verification

Facial verification provides an additional authentication factor using **DeepFace**.

The system compares the captured facial information with the registered voter information.

---

## 🚨 Fraud Detection

Ikshana maintains voting and biometric records to identify suspicious activity.

Potential fraud indicators include:

- Voter attempting to vote more than once
- Previously used biometric identity
- Mismatch between voter identity and biometric verification
- Suspicious activity across polling booths
- Repeated authentication failures

Detected events can be recorded in the fraud monitoring system for administrator review.

---

# 🖥️ Admin Dashboard

Election administrators can monitor election activity through a centralized dashboard.

The dashboard provides information such as:

- Election status
- Booth activity
- Officer activity
- Voting statistics
- Fraud logs
- Authentication activity
- Accuracy and verification metrics

This provides election administrators with a centralized view of the polling environment.

---

# 🔄 Real-Time Monitoring

Ikshana uses **Socket.IO** for real-time communication between the backend and frontend.

This allows important election events to be reflected without requiring constant page refreshes.

Examples include:

- Booth status changes
- Election state changes
- Voting activity
- Fraud alerts
- Administrative updates

---

# 🏗️ System Architecture

```text
                        ┌──────────────────────┐
                        │   Vercel Frontend    │
                        │ React + TypeScript   │
                        │ TanStack Router      │
                        └──────────┬───────────┘
                                   │
                         REST API / Socket.IO
                                   │
                                   ▼
                        ┌──────────────────────┐
                        │   Render Backend     │
                        │      FastAPI         │
                        └──────────┬───────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                    │
              ▼                    ▼                    ▼
       ┌─────────────┐      ┌─────────────┐      ┌─────────────┐
       │ PostgreSQL  │      │   DeepFace  │      │ Socket.IO   │
       │  Database   │      │    / Face   │      │  Realtime   │
       └─────────────┘      │ Verification│      └─────────────┘
                            └─────────────┘

              Booth Authentication Environment
                         │
                         ▼
                 ┌───────────────┐
                 │ Mantra MFS100 │
                 │ Fingerprint   │
                 │    Scanner    │
                 └───────────────┘
```

---

# 🧰 Technology Stack

## Frontend

- React
- TypeScript
- TanStack Router
- TanStack Start
- Vite
- Socket.IO Client

## Backend

- Python
- FastAPI
- Uvicorn
- Python Socket.IO
- Pydantic

## Database

- PostgreSQL

## Biometrics

- Mantra MFS100
- Mantra MFS100 SDK
- Python.NET
- Fingerprint matching
- SHA-256 hashing for biometric identifiers

## Facial Verification

- DeepFace
- TensorFlow
- OpenCV
- FaceNet

## Authentication & Security

- OTP authentication
- Session-based authentication
- Argon2 password hashing
- SHA-256 hashing
- CORS protection
- Login lockout mechanisms

## Deployment

- Vercel — Frontend
- Render — Backend
- Render PostgreSQL — Database

---

# 🗃️ Database

The production database contains tables supporting authentication, election management, voter records, biometric activity, and fraud monitoring.

Major tables include:

```text
admin_sessions
biometric_log
booth_officers
booth_sessions
election_action_log
election_status
fraud_log
officer_login_log
otp_codes
voters
```

### Example relationships

```text
Voters
  │
  ├── Voting Status
  ├── Biometric Records
  └── Fraud Detection

Booth Officers
  │
  ├── Booth Sessions
  ├── Login Logs
  └── Election Actions

Election
  │
  ├── Election Status
  ├── Booth Activity
  └── Fraud Monitoring
```

---

# 🔐 Security Considerations

Ikshana incorporates multiple security mechanisms.

### Password Security

Officer passwords are stored using **Argon2 hashing** rather than plaintext passwords.

### Biometric Protection

Raw fingerprint information is not stored as plain biometric data. A SHA-256 based representation is used for biometric identity handling.

### Session Security

Authenticated sessions are maintained using server-side session mechanisms.

### OTP Authentication

OTP verification provides an additional authentication layer for administrative access.

### Login Protection

Repeated failed authentication attempts can trigger login lockout mechanisms.

### Production Database Safety

Production database operations are protected against destructive development operations such as dropping the biometric database.

---

# 📁 Project Structure

```text
Ikshana/
│
├── backend/
│   ├── main.py
│   ├── database.py
│   ├── schema.py
│   ├── requirements.txt
│   │
│   ├── biometrics/
│   │   └── fingerprint.py
│   │
│   └── routers/
│       ├── admin.py
│       ├── election.py
│       ├── biometric.py
│       └── ...
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── lib/
│   │   │   └── api.ts
│   │   └── ...
│   │
│   ├── package.json
│   └── vite.config.ts
│
└── README.md
```

---

# ⚙️ Local Setup

## Prerequisites

Install:

- Python 3.12+
- Node.js
- npm
- PostgreSQL
- Git
- Mantra MFS100 SDK and drivers for fingerprint functionality

---

## 1. Clone the Repository

```bash
git clone <repository-url>
cd Ikshana
```

---

# 🐍 Backend Setup

Navigate to the backend:

```bash
cd backend
```

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it on Windows:

```bash
.venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create the required environment variables.

Example:

```env
DB_USER=your_database_user
DB_PASSWORD=your_database_password
DB_HOST=localhost
DB_PORT=5432
DB_NAME=election_db

BIOMETRIC_DB_NAME=biometric_db

FRONTEND_ORIGIN=http://localhost:8080

ENVIRONMENT=development
```

Run the backend:

```bash
uvicorn main:app --reload --port 8000
```

Backend:

```text
http://localhost:8000
```

API documentation:

```text
http://localhost:8000/docs
```

---

# ⚛️ Frontend Setup

Navigate to the frontend:

```bash
cd frontend
```

Install dependencies:

```bash
npm install
```

Create:

```text
.env
```

Add:

```env
VITE_API_URL=http://localhost:8000
```

Start the frontend:

```bash
npm run dev
```

---

# 🖨️ Fingerprint Scanner Setup

Fingerprint authentication requires the physical **Mantra MFS100** scanner and its Windows SDK/driver.

The scanner integration uses:

```text
MANTRA.MFS100.dll
```

The scanner must be connected to the machine running the biometric capture component.

### Important

The physical fingerprint scanner cannot be directly accessed by a cloud deployment.

Therefore:

```text
Cloud Backend
      │
      │ API
      ▼
Local Booth Computer
      │
      ▼
Mantra MFS100 Scanner
```

A future production architecture can use a lightweight **Booth Agent** running on each polling-station computer to communicate securely with the cloud backend.

---

# ☁️ Deployment

## Frontend

The frontend is deployed using **Vercel**.

Production frontend:

```text
https://ikshana-six.vercel.app
```

Set:

```env
VITE_API_URL=https://ikshana-2.onrender.com
```

Do not add a trailing slash.

---

## Backend

The FastAPI backend is deployed using **Render**.

Production backend:

```text
https://ikshana-2.onrender.com
```

The backend requires production environment variables for:

- PostgreSQL
- Frontend origin
- OTP/email services
- Encryption
- Application environment

Secrets should be stored as environment variables and must not be committed to Git.

---

# 🔌 API

The backend exposes REST endpoints for:

- Authentication
- OTP verification
- Election management
- Voter verification
- Biometric verification
- Booth management
- Officer management
- Fraud monitoring
- Dashboard statistics

Interactive API documentation is available through:

```text
https://ikshana-2.onrender.com/docs
```

---

# 🔄 Election Workflow

```text
Admin
 │
 ▼
Start Election
 │
 ▼
Booth Officer Login
 │
 ▼
Officer Authentication
 │
 ▼
Voter Arrives
 │
 ▼
Voter ID Verification
 │
 ▼
Fingerprint Verification
 │
 ▼
Facial Verification
 │
 ▼
Duplicate / Fraud Check
 │
 ├───────────────┐
 │               │
 ▼               ▼
Verified       Suspicious
 │               │
 ▼               ▼
Allow Vote     Log / Block
 │
 ▼
Record Voting Activity
 │
 ▼
Admin Dashboard
```

---

# 🧪 Testing

The system should be tested across the following areas.

### Authentication

- Valid officer login
- Invalid credentials
- OTP verification
- OTP expiry
- Login lockout
- Session validation

### Voter Verification

- Valid voter
- Invalid voter
- Valid fingerprint
- Invalid fingerprint
- Face match
- Face mismatch

### Fraud Detection

- Duplicate voting attempt
- Biometric reuse
- Cross-booth activity
- Suspicious authentication

### Election Management

- Start election
- Active election
- End election
- Booth activation/deactivation

### Deployment

- Frontend → Backend communication
- CORS
- API authentication
- PostgreSQL connectivity
- Real-time Socket.IO communication

---

# 🛡️ Production Safety

Production deployment uses safeguards to prevent destructive development database operations.

In particular, biometric database creation/deletion behavior differs between development and production environments.

Production must never execute destructive database operations as part of normal election lifecycle operations.

---

# 🚀 Future Enhancements

Potential improvements include:

- Dedicated booth-side biometric agent
- Hardware abstraction layer for multiple fingerprint scanners
- Secure biometric template storage
- Encrypted object storage for evidence
- Advanced fraud scoring
- Cross-booth anomaly detection
- Real-time fraud alert notifications
- Role-based access control
- Audit log visualization
- Offline booth authentication with secure synchronization
- Deployment monitoring and health checks
- Automated security auditing

---

# 📊 Project Impact

Ikshana demonstrates how biometric authentication, facial verification, real-time communication, and centralized monitoring can be combined to strengthen election authentication workflows.

The system is designed as a **prototype/engineering solution** for demonstrating secure voter verification and fraud detection concepts.

It should not be considered a production-certified election system without extensive security audits, biometric accuracy validation, hardware certification, legal compliance, accessibility testing, and independent election-security evaluation.

---

# 👩‍💻 Author

**Monika R**

Full-Stack Developer | Data & Cloud Enthusiast

---

# 📜 License

This project is intended for academic, research, and demonstration purposes.

Add an appropriate open-source license here if the repository is intended for public redistribution.

---

## ⭐ Ikshana

**Authenticate. Verify. Detect. Protect.**
