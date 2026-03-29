FROM python:3.11-slim

# System dependencies for Chromium (Patchright) + Xvfb virtual display
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libxss1 \
    libxtst6 \
    xdg-utils \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Patchright Chromium browser
RUN patchright install chromium

# Copy application code
COPY . .

EXPOSE 8000

# Start Xvfb + uvicorn
CMD bash -c "Xvfb :99 -screen 0 1920x1080x24 -ac &>/dev/null & export DISPLAY=:99 && sleep 1 && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
