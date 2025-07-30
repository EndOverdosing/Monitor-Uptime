# Uptime Monitor

A sleek, simple, and free tool to keep an eye on your web services, built with FastAPI and deployable in minutes on Render.

## Features

- **Simple UI**: A clean, modern interface for monitoring URLs.
- **Real-time Status**: Shows uptime/downtime counts and the latest HTTP status code.
- **Detailed Logs**: View a history of checks for each URL with timestamps, status codes, and response times.
- **IP-Based Ownership**: Users can only add one URL and can only delete the URL they added.
- **Automatic Checks**: A background cron job automatically checks all monitored URLs every 5 minutes.
- **Easy Deployment**: Deployable to Render with a single `render.yaml` file.
- **Light/Dark Mode**: Switch themes to your preference.

## Tech Stack

- **Backend**: FastAPI, Uvicorn
- **Database**: PostgreSQL (via SQLAlchemy)
- **Frontend**: Jinja2 Templates, CSS, JavaScript
- **HTTP Client**: HTTPX
- **Deployment**: Render

## Deployment on Render

This project is configured for easy deployment on [Render](https://render.com/) using a "Blueprint" configuration.

1.  **Fork this Repository**: Click the 'Fork' button at the top-right of this page to create a copy of this repository in your GitHub account.

2.  **Create a New Blueprint on Render**:
    *   Go to your [Render Dashboard](https://dashboard.render.com/).
    *   Click **New +** and select **Blueprint**.
    *   Connect the GitHub repository you just forked.
    *   Render will automatically detect the `render.yaml` file and propose a plan. Give your service a unique name.

3.  **Approve the Plan**:
    *   Render will create a PostgreSQL database and a Web Service for the application.
    *   It will also create a **Cron Job** responsible for triggering the checks.
    *   Click **Approve** to build and deploy the services.

4.  **IMPORTANT: Configure the Cron Job**:
    *   Once the initial deployment is complete, your `uptime-monitor-web` service will have a public URL (e.g., `https://your-app-name.onrender.com`).
    *   Go to the dashboard for your new services.
    *   Navigate to the **Environment** tab of the `uptime-checker-cron` service.
    *   You will see an environment variable named `WEB_SERVICE_URL`. **You must edit this variable** and replace the placeholder value (`https://YOUR_APP_NAME.onrender.com`) with the actual public URL of your `uptime-monitor-web` service.
    *   Save the changes. The cron job will now be able to successfully trigger the checks every 5 minutes.

## How It Works

### Adding a URL
- The application homepage provides a form to submit a URL for monitoring.
- To prevent abuse, the system limits monitoring to **one URL per public IP address**.
- You can only delete a URL if you are accessing the site from the same IP address that submitted it.

### Uptime Checking
- The core checking logic is an async function that sends an HTTP GET request to a URL. It records the status code, response time, and any errors.
- This logic is not running constantly. It is triggered by sending a `POST` request to the `/run-check/{secret_token}` endpoint.
- The **Cron Job** (`uptime-checker-cron`) service you configured on Render is responsible for sending this `POST` request automatically every 5 minutes, ensuring your monitored URLs are checked consistently. Without this cron job, no checks will ever run.