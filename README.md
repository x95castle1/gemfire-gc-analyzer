# GemFire GC Log Analyzer

A containerized, interactive dashboard built with Python, Streamlit, and Pandas to analyze Java Garbage Collection (GC) logs from GemFire environments.

This tool specifically parses **Java 11+ Unified JVM Logging** configured for the **G1GC** garbage collector. It extracts critical memory allocation metrics, calculates throughput, and visualizes pause durations to help you pinpoint performance bottlenecks.

## 🚀 Features

* **Multi-file Upload:** Drag and drop multiple GC log files at once for aggregated analysis.
* **Time-Range Filtering:** Isolate specific windows of time to analyze spikes or issues using the interactive sidebar.
* **Dynamic Visualizations:** Automatically generates line charts tracking Total vs. Used Heap memory over time.
* **Deep-Dive Metrics:** * Overall KPIs (Throughput %, Max/Avg Pause, Total Runtime)
    * Pause Duration Distributions (Bucketed in 100ms intervals)
    * Granular GC Phase Statistics (e.g., Concurrent Marking, Evacuate Collection Set)
    * GC Cause aggregations
* **Fully Containerized:** Runs seamlessly anywhere using Docker.

## 📁 Project Structure

\`\`\`text
gemfire-gc-analyzer/
├── Dockerfile          # Instructions to build the container image
├── Makefile            # Shortcut commands for building and running
├── requirements.txt    # Python dependencies (Streamlit, Pandas)
├── parser.py           # Core logic: Regex parsing and Pandas data crunching
├── app.py              # The Streamlit frontend / UI layout
└── README.md           # You are here!
\`\`\`

## 🛠️ Prerequisites

To run this application, you only need one thing installed on your machine:
* [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Make sure the Docker engine is running).

*(Optional but recommended): A UNIX-like terminal (Mac/Linux/WSL) to use the `make` commands.*

## 🏁 Quick Start (Using Make)

We've included a `Makefile` to make building and running the application a one-click process. Open your terminal in the root of this project and run:

1. **Build the Docker Image:**
   \`\`\`bash
   make build
   \`\`\`
   *Note: You only need to run this the first time, or if you modify the Python code/requirements.*

2. **Run the Application:**
   \`\`\`bash
   make run
   \`\`\`

3. **Access the Dashboard:**
   Open your web browser and navigate to: **[http://localhost:8501](http://localhost:8501)**

4. **Stop the Application:**
   When you are done, press `Ctrl+C` in your terminal. The container will automatically clean itself up.

## 🐳 Manual Start (Without Make)

If you are on standard Windows Command Prompt or don't have `make` installed, you can run the raw Docker commands:

**Build:**
\`\`\`bash
docker build -t gemfire-analyzer .
\`\`\`

**Run:**
\`\`\`bash
docker run -p 8501:8501 --rm --name gemfire-analyzer-app gemfire-analyzer
\`\`\`

## 📊 Usage Instructions

1. Once the app is loaded in your browser, look at the **Sidebar** on the left.
2. Use the file uploader to select one or more `.log` or `.txt` GemFire GC log files.
3. Use the **Date and Time** inputs to narrow down the exact window you want to analyze.
4. The dashboard will automatically parse the logs, apply the time filters, and render your KPIs, charts, and tables!