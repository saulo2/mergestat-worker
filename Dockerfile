FROM mergestat/worker:sha-9e60d92

# Changes to root user
USER root

# Rename podman binary to _podman
RUN mv /usr/bin/podman /usr/bin/_podman

# Copy shell script that will be executed instead of the podman binary
COPY worker/podman /usr/bin/podman
RUN chmod +x /usr/bin/podman

# Install dependencies of python script
RUN pip install kubernetes
RUN pip install python-dotenv

# Copy python script the podman shell script executes
COPY worker/podman.py /usr/bin/podman.py

# Changes back to mergestat user
USER mergestat