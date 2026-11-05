-- The DMPs and their versions.
--
--   dmps              one row per DMP: its key, its project, template or
--                     production
--   dmp_versions      one row per version of a DMP, and the project version
--                     that produced it
--
-- Every row of dmp_versions is added and never changed; a DMP version can be
-- deleted.
--
-- A project's template DMP is written version by version. Its production
-- DMPs are created from a version of the template.

-- The number the next production DMP of a project takes: 1 gives -0001.
ALTER TABLE projects
    ADD COLUMN next_number integer NOT NULL DEFAULT 1 CHECK (next_number >= 1);

CREATE TABLE dmps (
    -- <organization>-<project>-template or <organization>-<project>-<number>,
    -- never given to another DMP.
    key         text PRIMARY KEY CHECK (key ~ '^[a-z0-9-]{1,160}$'),
    project_id  text NOT NULL REFERENCES projects (id),
    kind        text NOT NULL CHECK (kind IN ('template', 'production')),
    created_at  timestamptz NOT NULL DEFAULT now(),
    -- What the foreign key of dmp_versions below points at.
    UNIQUE (key, project_id)
);

-- One template per project.
CREATE UNIQUE INDEX dmps_one_template_per_project
    ON dmps (project_id) WHERE kind = 'template';

CREATE TABLE dmp_versions (
    dmp_key      text NOT NULL,
    -- 1 for the first, then the previous one plus 1. The primary key refuses
    -- a second row with the same number: of two writes based on the same
    -- version, the first is kept, the second is refused.
    version      integer NOT NULL CHECK (version >= 1),
    -- The DMP's project: the first foreign key below ties it to the DMP's
    -- own, the second, with project_version, to a version of it.
    project_id       text NOT NULL,
    -- The version of the project the document was produced from. Its rules
    -- are the ones project_rules lists for it.
    project_version  text NOT NULL,
    -- The version of the project's template DMP a production DMP's version was
    -- filled from. Empty for a template's own versions. No foreign key: a
    -- template version can be deleted, its existence is checked when this one
    -- is written.
    from_template_version  integer CHECK (from_template_version >= 1),
    -- The dmp object, dmp_id set to the key.
    document     jsonb NOT NULL,
    -- The assessment of the document.
    assessment   jsonb NOT NULL,
    -- What wrote this version, as the writer names itself.
    source       text NOT NULL CHECK (source ~ '^[a-z0-9_-]{1,64}$'),
    created_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (dmp_key, version),
    FOREIGN KEY (dmp_key, project_id) REFERENCES dmps (key, project_id),
    FOREIGN KEY (project_id, project_version) REFERENCES project_versions
);

CREATE TRIGGER dmp_versions_no_update
    BEFORE UPDATE ON dmp_versions
    FOR EACH ROW EXECUTE FUNCTION refuse_update();
