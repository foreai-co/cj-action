# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY  . /app

# Install required packages
RUN pip install requests

# Make the script executable
RUN chmod +x /app/script.py

# Define the command to run your script
ENTRYPOINT ["python", "/app/script.py"]
