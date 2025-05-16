@echo off
echo ==================================
echo Cai dat thu vien cho LMS-RAG-Chatbot
echo ==================================

echo Kiem tra Python...
python --version
if %ERRORLEVEL% NEQ 0 (
    echo Loi: Python chua duoc cai dat! Vui long cai dat Python va thu lai.
    pause
    exit /b
)

echo.
echo Tao moi truong ao...
python -m venv venv
if %ERRORLEVEL% NEQ 0 (
    echo Loi: Khong the tao moi truong ao! Thu cai dat thu vien python-venv.
    pause
    exit /b
)

echo.
echo Kich hoat moi truong ao...
call venv\Scripts\activate
if %ERRORLEVEL% NEQ 0 (
    echo Loi: Khong the kich hoat moi truong ao!
    pause
    exit /b
)

echo.
echo Nang cap pip...
python -m pip install --upgrade pip
if %ERRORLEVEL% NEQ 0 (
    echo Canh bao: Khong the nang cap pip. Se tiep tuc cai dat cac goi...
)

echo.
echo Cai dat cac goi tu requirements.txt...
pip install -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo Loi: Khong the cai dat thu vien!
    pause
    exit /b
)

echo.
echo Cai dat cac goi bo sung cho RAG...
pip install pymongo python-dotenv langchain-community==0.0.13 langchain-core==0.1.8 langchain==0.0.314 langchain-text-splitters==0.0.1 langchain-google-genai==0.0.5 langchain-huggingface==0.0.1 faiss-cpu==1.7.4 google-generativeai==0.3.1 sentence-transformers==2.2.2 huggingface-hub==0.17.3
if %ERRORLEVEL% NEQ 0 (
    echo Canh bao: Khong the cai dat thu vien bo sung! Kiem tra loi o tren.
    pause
    exit /b
)

echo.
echo Tao file .env tu .env-example...
if not exist .env (
    copy .env-example .env
    if %ERRORLEVEL% NEQ 0 (
        echo Canh bao: Khong the tao file .env
    ) else (
        echo Da tao file .env tu .env-example.
        echo Hay chinh sua file .env de cau hinh MongoDB va API key.
    )
) else (
    echo File .env da ton tai.
)

echo.
echo ===========================================
echo Cai dat hoan tat! Thu chay test_db.py de kiem tra ket noi MongoDB:
echo.
echo venv\Scripts\activate
echo python test_db.py
echo ===========================================
echo.

pause 