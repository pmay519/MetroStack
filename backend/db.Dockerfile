# Use your existing PostGIS image as the foundation
FROM postgis/postgis:15-3.4

# Install the missing pointcloud extension binaries
RUN apt-get update && \
    apt-get install -y postgresql-15-pointcloud && \
    rm -rf /var/lib/apt/lists/*