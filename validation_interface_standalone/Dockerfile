FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY validation_interface.py .
COPY templates/ templates/

# Create directories for data and results
RUN mkdir -p /app/data /app/validation_results

# Expose the port the app runs on
EXPOSE 5001

# Command to run the application
CMD ["python", "validation_interface.py", "--host", "0.0.0.0", "--port", "5001", "--data-file", "/app/data/validation_data.json"]