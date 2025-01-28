# Redirect stdout and stderr to a log file
LOGFILE="/var/log/startup.log"
exec > >(tee -a $LOGFILE) 2>&1


# Run LLM initialization script
echo "Initializing LLMs..."
python modules/loginpagedetection/crawler_backend.py
python modules/loginpagedetection/classify_screenshots.py


# Check if the initialization was successful
if [ $? -ne 0 ]; then
    echo "LLM initialization failed. Exiting."
    exit 1
fi

echo "LLMs initialized successfully. Starting the worker..."

# Start the worker application
python app.py
