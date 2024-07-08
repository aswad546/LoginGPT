FROM mcr.microsoft.com/playwright/python:v1.35.0-jammy

# install pipenv
RUN pip install pipenv
ENV PIPENV_VENV_IN_PROJECT=1

# create app directory
RUN mkdir -p /app
WORKDIR /app

# install python dependencies
ADD Pipfile .
ADD Pipfile.lock .
RUN pipenv install --system

# copy app
COPY . .
