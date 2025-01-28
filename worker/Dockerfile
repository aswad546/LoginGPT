# # Base image with Playwright and Python
# FROM mcr.microsoft.com/playwright/python:v1.35.0-jammy

# # Set environment variables for Conda and Pipenv
# ENV PATH="/opt/conda/bin:$PATH"
# ENV PIPENV_VENV_IN_PROJECT=1

# # Install required system dependencies
# RUN apt-get update && apt-get install -y \
#     curl \
#     wget \
#     build-essential \
#     libglib2.0-0 \
#     libnss3 \
#     libx11-xcb1 \
#     libxcomposite1 \
#     libxcursor1 \
#     libxdamage1 \
#     libxrandr2 \
#     libasound2 \
#     libpangocairo-1.0-0 \
#     libatk1.0-0 \
#     libcups2 \
#     libdrm2 \
#     libxshmfence1 \
#     libgbm1 \
#     && rm -rf /var/lib/apt/lists/*

# # Install Miniconda
# RUN wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O miniconda.sh && \
#     bash miniconda.sh -b -p /opt/conda && \
#     rm miniconda.sh

# # Create a Conda environment and install Python 3.12
# RUN conda create -n new-env python=3.10 -y

# # Install Node.js and npm
# RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
#     apt-get install -y nodejs && \
#     npm install -g npm@latest && \
#     rm -rf /var/lib/apt/lists/*

# # Activate Conda environment and install Python packages
# RUN /bin/bash -c "source activate new-env && \
#     pip install pipenv && \
#     pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121 && \
#     pip install tensorflow transformers qwen-vl-utils accelerate tf-keras"

# # Install Puppeteer-Extra via npm
# RUN rm -rf /node_modules /package-lock.json ~/.npm ~/.cache && \
#     npm cache clean --force && \
#     mkdir -p /app && cd /app && \
#     npm init -y && \
#     npm install puppeteer-extra puppeteer-extra-plugin-stealth sharp

# # Create app directory and set as the working directory
# RUN mkdir -p /app
# WORKDIR /app

# # Copy application dependencies
# COPY Pipfile Pipfile.lock ./
# RUN /bin/bash -c "source activate new-env && pipenv install --system"

# # Copy application code
# COPY . .

# # Ensure startup script is executable
# RUN chmod +x start_worker.sh

# # Set the default command to execute the startup script
# CMD ["./start_worker.sh"]


FROM mcr.microsoft.com/playwright/python:v1.35.0-jammy

# install pipenv
RUN pip install pipenv
ENV PIPENV_VENV_IN_PROJECT=1

# create app directory
RUN mkdir -p /app
WORKDIR /app

# Install required system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    build-essential \
    libglib2.0-0 \
    libnss3 \
    libx11-xcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxrandr2 \
    libasound2 \
    libpangocairo-1.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdrm2 \
    libxshmfence1 \
    libgbm1 \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js and npm
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    npm install -g npm@latest && \
    rm -rf /var/lib/apt/lists/*

# Install Puppeteer-Extra via npm
RUN rm -rf /node_modules /package-lock.json ~/.npm ~/.cache && \
    npm cache clean --force && \
    mkdir -p /app && cd /app && \
    npm init -y && \
    npm install puppeteer-extra puppeteer-extra-plugin-stealth sharp

# install python dependencies
ADD Pipfile .
ADD Pipfile.lock .
RUN pipenv install --system
RUN pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121 && \
    pip install tensorflow transformers qwen-vl-utils accelerate tf-keras

# copy app
COPY . .

# Ensure startup script is executable
RUN chmod +x start_worker.sh

# Set the default command to execute the startup script
CMD ["./start_worker.sh"]

