@echo off
echo ============================================
echo    CureAI - Medical Assistant
echo ============================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Install Python 3.9+
    pause
    exit /b 1
)

:: Install backend dependencies
echo [1/3] Installing backend dependencies...
cd backend
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)

:: Check .env
if not exist .env (
    echo ERROR: backend\.env not found. Copy .env.example to .env and fill in your keys.
    pause
    exit /b 1
)

:: Start backend
echo [2/3] Starting backend server on port 5000...
start "CureAI Backend" cmd /k "python app.py"
cd ..

:: Wait for backend to start
timeout /t 3 /nobreak >nul

:: Start frontend
echo [3/3] Starting frontend on port 8000...
cd frontend\static
start "CureAI Frontend" cmd /k "python -m http.server 8000"
cd ..\..

echo.
echo ============================================
echo  Backend:  http://localhost:5000
echo  Frontend: http://localhost:8000
echo ============================================
echo.

:: Open browser
timeout /t 2 /nobreak >nul
start http://localhost:8000

echo Press any key to exit (servers will keep running)...
pause >nul
