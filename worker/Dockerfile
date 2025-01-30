# FROM mcr.microsoft.com/playwright/python:v1.35.0-jammy


# # Set environment variables to avoid interactive prompts
# ENV DEBIAN_FRONTEND=noninteractive

# # Update package lists and install necessary dependencies
# RUN apt-get update && apt-get install -y \
#     curl \
#     gnupg \
#     ca-certificates \
#     libnss3 \
#     libatk1.0-0 \
#     libatk-bridge2.0-0 \
#     libx11-xcb1 \
#     libxcomposite1 \
#     libxcursor1 \
#     libxdamage1 \
#     libxfixes3 \
#     libxrandr2 \
#     libgbm-dev \
#     libasound2 \
#     libpango1.0-0 \
#     fonts-liberation \
#     libappindicator3-1 \
#     xdg-utils \
#     xvfb \
#     && rm -rf /var/lib/apt/lists/*

# # Install Node.js (Latest LTS Version)
# RUN curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - && \
#     apt-get install -y nodejs && \
#     node -v && npm -v

# WORKDIR /app
# # copy app
# COPY . .
# # Install Node.js dependencies

# # Move to the correct directory before running npm install
# WORKDIR /app/modules/loginpagedetection

# RUN npm cache clean --force && npm install

# # Set the working directory back to /app
# WORKDIR /app

# # install pipenv
# RUN pip install pipenv
# ENV PIPENV_VENV_IN_PROJECT=1

# # create app directory
# RUN mkdir -p /app
# WORKDIR /app

# # install python dependencies
# ADD Pipfile .
# ADD Pipfile.lock .
# RUN pipenv install --system



# Use Playwright's official image as the base
FROM mcr.microsoft.com/playwright/python:v1.35.0-jammy

# Set non-interactive mode for package installations
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies before copying files
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

# Set the working directory
WORKDIR /app

# ✅ Copy only dependency files first (for caching)
COPY modules/loginpagedetection/package.json modules/loginpagedetection/package-lock.json ./modules/loginpagedetection/

# ✅ Install Node.js dependencies BEFORE copying all files
WORKDIR /app/modules/loginpagedetection
RUN npm install

# ✅ Copy remaining application files AFTER installing dependencies
WORKDIR /app
COPY . .

# Install pipenv
RUN pip install pipenv
ENV PIPENV_VENV_IN_PROJECT=1

# ✅ Copy only Python dependency files first (for caching)
COPY Pipfile Pipfile.lock ./

# ✅ Install Python dependencies separately to leverage caching
RUN pipenv install --system

