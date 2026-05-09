"""Initial schema

Revision ID: 001
Revises: 
Create Date: 2025-01-15

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable PostGIS extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute("CREATE EXTENSION IF NOT EXISTS pointcloud")
    op.execute("CREATE EXTENSION IF NOT EXISTS pointcloud_postgis")
    
    # Projects
    op.create_table(
        'projects',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text),
        sa.Column('part_number', sa.String(100)),
        sa.Column('revision', sa.String(20)),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    
    # CAD Models
    op.create_table(
        'cad_models',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('filename', sa.String(512), nullable=False),
        sa.Column('file_path', sa.String(1024), nullable=False),
        sa.Column('file_format', sa.String(20), nullable=False),
        sa.Column('file_size_bytes', sa.BigInteger, server_default='0'),
        sa.Column('vertex_count', sa.Integer),
        sa.Column('face_count', sa.Integer),
        sa.Column('is_watertight', sa.Boolean),
        sa.Column('bbox_min_x', sa.Double),
        sa.Column('bbox_min_y', sa.Double),
        sa.Column('bbox_min_z', sa.Double),
        sa.Column('bbox_max_x', sa.Double),
        sa.Column('bbox_max_y', sa.Double),
        sa.Column('bbox_max_z', sa.Double),
        sa.Column('repair_log', sa.Text),
        sa.Column('is_processed', sa.Boolean, server_default='false'),
        sa.Column('uploaded_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    )
    
    # Scan Clouds
    op.create_table(
        'scan_clouds',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('filename', sa.String(512), nullable=False),
        sa.Column('file_path', sa.String(1024), nullable=False),
        sa.Column('file_format', sa.String(20), nullable=False),
        sa.Column('file_size_bytes', sa.BigInteger, server_default='0'),
        sa.Column('point_count', sa.BigInteger),
        sa.Column('has_normals', sa.Boolean),
        sa.Column('has_intensity', sa.Boolean),
        sa.Column('has_rgb', sa.Boolean),
        sa.Column('bbox_min_x', sa.Double),
        sa.Column('bbox_min_y', sa.Double),
        sa.Column('bbox_min_z', sa.Double),
        sa.Column('bbox_max_x', sa.Double),
        sa.Column('bbox_max_y', sa.Double),
        sa.Column('bbox_max_z', sa.Double),
        sa.Column('units', sa.String(20)),
        sa.Column('is_processed', sa.Boolean, server_default='false'),
        sa.Column('uploaded_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    )
    
    # Alignments
    op.create_table(
        'alignments',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column('method', sa.String(50), nullable=False),
        sa.Column('transform_matrix', sa.Text, nullable=False),
        sa.Column('inlier_rmse_mm', sa.Double),
        sa.Column('fitness_score', sa.Double),
        sa.Column('inlier_count', sa.Integer),
        sa.Column('iteration_count', sa.Integer),
        sa.Column('datum_constraints', sa.Text),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    )
    
    # Analysis Jobs
    op.create_table(
        'analysis_jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('analysis_type', sa.String(50), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='queued'),
        sa.Column('celery_task_id', sa.String(255)),
        sa.Column('progress_pct', sa.Integer, server_default='0'),
        sa.Column('progress_msg', sa.String(512)),
        sa.Column('error_message', sa.Text),
        sa.Column('parameters', sa.Text),
        sa.Column('started_at', sa.DateTime(timezone=True)),
        sa.Column('finished_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    )
    op.create_index('idx_jobs_project_type', 'analysis_jobs', ['project_id', 'analysis_type'])
    
    # Deviation Summaries
    op.create_table(
        'deviation_summaries',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('point_count', sa.BigInteger, nullable=False),
        sa.Column('dev_min_mm', sa.Double, nullable=False),
        sa.Column('dev_max_mm', sa.Double, nullable=False),
        sa.Column('dev_mean_mm', sa.Double, nullable=False),
        sa.Column('dev_rms_mm', sa.Double, nullable=False),
        sa.Column('dev_p95_mm', sa.Double, nullable=False),
        sa.Column('dev_p99_mm', sa.Double, nullable=False),
        sa.Column('scale_min_mm', sa.Double),
        sa.Column('scale_max_mm', sa.Double),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['job_id'], ['analysis_jobs.id'], ondelete='CASCADE'),
    )
    
    # GD&T Features
    op.create_table(
        'gdt_features',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('feature_type', sa.String(50), nullable=False),
        sa.Column('nominal_x', sa.Double),
        sa.Column('nominal_y', sa.Double),
        sa.Column('nominal_z', sa.Double),
        sa.Column('nominal_diameter', sa.Double),
        sa.Column('roi_min_x', sa.Double),
        sa.Column('roi_min_y', sa.Double),
        sa.Column('roi_min_z', sa.Double),
        sa.Column('roi_max_x', sa.Double),
        sa.Column('roi_max_y', sa.Double),
        sa.Column('roi_max_z', sa.Double),
        sa.Column('primary_datum', sa.String(10)),
        sa.Column('secondary_datum', sa.String(10)),
        sa.Column('tertiary_datum', sa.String(10)),
        sa.Column('tolerance_upper_mm', sa.Double),
        sa.Column('tolerance_lower_mm', sa.Double),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    )
    
    # GD&T Results
    op.create_table(
        'gdt_results',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('feature_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('actual_value_mm', sa.Double, nullable=False),
        sa.Column('nominal_value_mm', sa.Double),
        sa.Column('deviation_mm', sa.Double),
        sa.Column('in_tolerance', sa.Boolean, nullable=False),
        sa.Column('fit_center_x', sa.Double),
        sa.Column('fit_center_y', sa.Double),
        sa.Column('fit_center_z', sa.Double),
        sa.Column('fit_normal_x', sa.Double),
        sa.Column('fit_normal_y', sa.Double),
        sa.Column('fit_normal_z', sa.Double),
        sa.Column('fit_radius', sa.Double),
        sa.Column('fit_residual_rms', sa.Double),
        sa.Column('point_count_used', sa.Integer),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['feature_id'], ['gdt_features.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['job_id'], ['analysis_jobs.id'], ondelete='CASCADE'),
    )
    
    # Wall Thickness Samples
    op.create_table(
        'wall_thickness_samples',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('sample_x', sa.Double, nullable=False),
        sa.Column('sample_y', sa.Double, nullable=False),
        sa.Column('sample_z', sa.Double, nullable=False),
        sa.Column('thickness_mm', sa.Double, nullable=False),
        sa.Column('normal_x', sa.Double),
        sa.Column('normal_y', sa.Double),
        sa.Column('normal_z', sa.Double),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['job_id'], ['analysis_jobs.id'], ondelete='CASCADE'),
    )
    op.create_index('idx_wall_thickness_project_job', 'wall_thickness_samples', ['project_id', 'job_id'])


def downgrade() -> None:
    op.drop_table('wall_thickness_samples')
    op.drop_table('gdt_results')
    op.drop_table('gdt_features')
    op.drop_table('deviation_summaries')
    op.drop_table('analysis_jobs')
    op.drop_table('alignments')
    op.drop_table('scan_clouds')
    op.drop_table('cad_models')
    op.drop_table('projects')
