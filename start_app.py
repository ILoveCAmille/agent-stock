import subprocess, sys, os

# Check streamlit
try:
    import streamlit
    print("streamlit OK, version:", streamlit.__version__)
except ImportError:
    print("Installing streamlit...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "streamlit", "pandas", "plotly", "-q"])
    print("Install done")

# Launch streamlit app
print("\nStarting AI Stock Analysis System...")
subprocess.run([sys.executable, "-m", "streamlit", "run", "app.py", "--server.port", "8501"])