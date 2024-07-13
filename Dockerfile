# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r scraper/requirements.txt

# Install cron
RUN apt-get update && apt-get install -y cron

# Copy the cron job file into the cron.d directory
COPY scraper/cronjob /etc/cron.d/manga_cron

# Give execution rights on the cron job
RUN chmod 0644 /etc/cron.d/manga_cron

# Database env variables 
ARG PGHOST
ARG PGUSER
ARG PGPASSWORD
ARG PGDATABASE
ARG PGPORT

# Apply the cron job
RUN crontab /etc/cron.d/manga_cron

# Create the log file to be able to run tail
RUN touch /var/log/cron.log

# Run the command on container startup
CMD cron && tail -f /var/log/cron.log
