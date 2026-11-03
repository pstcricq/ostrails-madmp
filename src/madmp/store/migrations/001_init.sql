-- The definitions, as they were copied: the rules files and the projects at
-- their version.
--
--   rules             one row per rules file of definitions/rules/, at one
--                     version
--   projects          one row per project of definitions/projects/
--   project_versions  one row per version of a project, its YAML as it was
--   project_rules     the rules each project version pins, base first
--
-- Every row of rules, project_versions and project_rules is added and never
-- changed.

CREATE TABLE rules (
    -- definitions/rules/<standard>/<version>.json
    standard    text NOT NULL CHECK (standard ~ '^[a-z0-9_]{1,64}$'),
    version     text NOT NULL CHECK (version ~ '^[0-9]+\.[0-9]+\.[0-9]+$'),
    -- The rules file, as its content: jsonb compares by content, the order
    -- of the keys and the layout of the file left out.
    content     jsonb NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (standard, version)
);

CREATE TABLE projects (
    -- The id of definitions/projects/<id>/.
    id          text PRIMARY KEY CHECK (id ~ '^[a-z0-9-]{1,64}$'),
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE project_versions (
    -- definitions/projects/<id>/<version>.yaml
    project_id  text NOT NULL REFERENCES projects (id),
    -- The project's `version`.
    version     text NOT NULL CHECK (version ~ '^[0-9]+\.[0-9]+\.[0-9]+$'),
    -- The YAML, as its content.
    content     jsonb NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (project_id, version)
);

CREATE TABLE project_rules (
    project_id     text NOT NULL,
    version        text NOT NULL,
    -- The order the project writes its pins in: 1 is the base, then the
    -- extensions.
    position       integer NOT NULL CHECK (position >= 1),
    standard       text NOT NULL,
    rules_version  text NOT NULL,
    PRIMARY KEY (project_id, version, position),
    UNIQUE (project_id, version, standard),
    FOREIGN KEY (project_id, version) REFERENCES project_versions,
    FOREIGN KEY (standard, rules_version) REFERENCES rules (standard, version)
);

-- What is added is never changed.
CREATE FUNCTION refuse_update() RETURNS trigger
    LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION '% rows are never updated, add a version instead', TG_TABLE_NAME;
END;
$$;

CREATE TRIGGER rules_no_update
    BEFORE UPDATE ON rules
    FOR EACH ROW EXECUTE FUNCTION refuse_update();

CREATE TRIGGER project_versions_no_update
    BEFORE UPDATE ON project_versions
    FOR EACH ROW EXECUTE FUNCTION refuse_update();

CREATE TRIGGER project_rules_no_update
    BEFORE UPDATE ON project_rules
    FOR EACH ROW EXECUTE FUNCTION refuse_update();
