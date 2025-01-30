FROM nvidia/cuda:12.1.1-devel-ubuntu22.04 

# Install system dependencies
RUN apt update && apt install -y \
    wget \
    curl \
    git \
    bzip2 \
    ca-certificates \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install Miniconda (latest version)
ENV CONDA_DIR /opt/conda
RUN wget -O miniconda.sh https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh && \
    bash miniconda.sh -b -p $CONDA_DIR && \
    rm miniconda.sh

# Set environment variables for Conda
ENV PATH=$CONDA_DIR/bin:$PATH

# Update Conda and create the environment
RUN conda update -n base -c defaults conda -y && \
    conda create -n qwen_env python=3.12 -y

# Activate Conda for every RUN command
SHELL ["conda", "run", "-n", "qwen_env", "/bin/bash", "-c"]

# Set the working directory
WORKDIR /app

# Copy the necessary files
COPY crawler_backend.py .

# Install dependencies inside Conda
RUN pip install --upgrade pip
RUN pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121 
RUN pip install tensorflow
RUN pip install transformers
RUN pip install qwen-vl-utils
RUN pip install accelerate
RUN pip install tf-keras

# Expose the socket server port
EXPOSE 5000

# Ensure Conda is activated at runtime
CMD ["/bin/bash", "-c", "source activate qwen_env && python crawler_backend.py"]
