FROM mcr.microsoft.com/playwright/python:v1.35.0-jammy

# Set non-interactive mode for apt-get
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    ca-certificates \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libx11-xcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm-dev \
    libasound2 \
    libpango1.0-0 \
    fonts-liberation \
    libappindicator3-1 \
    xdg-utils \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js (Latest LTS Version)
RUN curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - && \
    apt-get install -y nodejs && \
    node -v && npm -v

# Set working directory
WORKDIR /app

##############################
# Install Node.js Dependencies
##############################
# Copy only the dependency files for the loginpagedetection module
COPY modules/loginpagedetection/package.json modules/loginpagedetection/package-lock.json ./modules/loginpagedetection/
WORKDIR /app/modules/loginpagedetection
RUN npm install

##############################
# Install Python Dependencies
##############################
WORKDIR /app
# Copy only Pipfile and Pipfile.lock for caching
COPY Pipfile Pipfile.lock ./
# Install pipenv and Python dependencies
RUN pip install pipenv && \
    PIPENV_VENV_IN_PROJECT=1 pipenv install --system

##############################
# Copy Application Code
##############################
WORKDIR /app
COPY . .

