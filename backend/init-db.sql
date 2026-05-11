-- init-db.sql
-- PostgreSQL initialization script run on first container startup.
-- Enables PostGIS and pgpointcloud extensions.

-- Connect to the metrostack database
\c metrostack;

-- Enable PostGIS for spatial data types and functions
CREATE EXTENSION IF NOT EXISTS postgis;

-- Enable PostGIS topology support (optional but recommended)
CREATE EXTENSION IF NOT EXISTS postgis_topology;

-- Enable pgpointcloud for point cloud storage
-- Note: This requires the pointcloud extension to be installed in the PostgreSQL image
-- The postgis/postgis image includes it by default
CREATE EXTENSION IF NOT EXISTS pointcloud;
CREATE EXTENSION IF NOT EXISTS pointcloud_postgis;

-- Create a point cloud format for XYZ data (basic 3D points)
-- Ensure we are using ID 1 and a clean schema string
INSERT INTO pointcloud_formats (pcid, srid, schema)
VALUES (1, 0, 
'<?xml version="1.0" encoding="UTF-8"?>
<pc:PointCloudSchema xmlns:pc="http://pointcloud.org/schemas/PC/1.1" 
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <pc:dimension>
    <pc:position>1</pc:position>
    <pc:size>8</pc:size>
    <pc:name>X</pc:name>
    <pc:interpretation>double</pc:interpretation>
  </pc:dimension>
  <pc:dimension>
    <pc:position>2</pc:position>
    <pc:size>8</pc:size>
    <pc:name>Y</pc:name>
    <pc:interpretation>double</pc:interpretation>
  </pc:dimension>
  <pc:dimension>
    <pc:position>3</pc:position>
    <pc:size>8</pc:size>
    <pc:name>Z</pc:name>
    <pc:interpretation>double</pc:interpretation>
  </pc:dimension>
  <pc:metadata>
    <Metadata name="compression">none</Metadata>
  </pc:metadata>
</pc:PointCloudSchema>')
ON CONFLICT (pcid) DO NOTHING;

-- Grant necessary permissions
GRANT ALL PRIVILEGES ON DATABASE metrostack TO postgres;
GRANT ALL ON SCHEMA public TO postgres;

-- Confirm extensions are installed
SELECT 
    extname AS extension_name, 
    extversion AS version 
FROM pg_extension 
WHERE extname IN ('postgis', 'postgis_topology', 'pointcloud', 'pointcloud_postgis')
ORDER BY extname;

\echo 'PostGIS and pgpointcloud extensions installed successfully!'
