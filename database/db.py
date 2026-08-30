import aiosqlite
import os
from contextlib import asynccontextmanager

DATABASE = os.path.join(
    "database",
    "bot.db"
)

@asynccontextmanager
async def open_database():
    db = await aiosqlite.connect(
        DATABASE
    )

    await db.execute(
        "PRAGMA foreign_keys = ON"
    )

    try:
        yield db
    finally:
        await db.close()


async def setup_database():

    async with open_database() as db:

        await db.execute("""

        CREATE TABLE IF NOT EXISTS guild_settings(

        guild_id INTEGER PRIMARY KEY,

        log_channel_id INTEGER,

        verification_log_channel_id INTEGER,

        admin_log_channel_id INTEGER,

        forum_channel_id INTEGER,

        verify_tag TEXT,
        progress_tag TEXT,
        approved_tag TEXT,
        denied_tag TEXT,
        failed_tag TEXT

        )

        """)
        await db.commit()
        print(f"Database path: {DATABASE}")

        for name, column_type in [
            ("verification_log_channel_id", "INTEGER"),
            ("admin_log_channel_id", "INTEGER"),
            ("forum_channel_id", "INTEGER"),
            ("verify_tag", "TEXT"),
            ("progress_tag", "TEXT"),
            ("approved_tag", "TEXT"),
            ("denied_tag", "TEXT"),
            ("failed_tag", "TEXT"),
        ]:
            await ensure_column(db, "guild_settings", name, column_type)

        await db.commit()

        await db.execute("""

        CREATE TABLE IF NOT EXISTS character_configs(

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        guild_id INTEGER,

        game TEXT,

        character_name TEXT,

        character_id INTEGER,

        path TEXT,

        required_trace_count INTEGER,

        signature_lightcone_name TEXT,

        UNIQUE(
        guild_id,
        game,
        character_name
        )

        )

        """)
        await db.commit()

        await db.execute("""

        CREATE UNIQUE INDEX IF NOT EXISTS
        idx_character_configs_guild_character

        ON character_configs(
        guild_id,
        character_name
        )

        """)

        await db.commit()

        await db.execute("""

        CREATE TABLE IF NOT EXISTS character_roles(

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        guild_id INTEGER,

        character_name TEXT,

        role_type TEXT,

        role_id INTEGER,

        UNIQUE(

        guild_id,
        character_name,
        role_type

        ),

        FOREIGN KEY(
        guild_id,
        character_name
        )

        REFERENCES character_configs(
        guild_id,
        character_name
        )

        ON DELETE CASCADE

        )

        """)

        await db.commit()

        await db.execute("""

        CREATE TABLE IF NOT EXISTS character_role_requirements(

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        guild_id INTEGER,

        character_name TEXT,

        role_id INTEGER,

        required_eidolons INTEGER,

        required_superimpose INTEGER,

        require_signature INTEGER,

        require_max_traces INTEGER,

        UNIQUE(

        guild_id,
        character_name,
        role_id

        ),

        FOREIGN KEY(
        guild_id,
        character_name
        )

        REFERENCES character_configs(
        guild_id,
        character_name
        )

        ON DELETE CASCADE

        )

        """)

        await db.commit()

        await db.execute("""

        CREATE TABLE IF NOT EXISTS custom_roles(

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        guild_id INTEGER,

        character_name TEXT,

        role_id INTEGER,

        start_date TEXT,

        end_date TEXT,

        source_type TEXT,

        UNIQUE(

        guild_id,
        character_name,
        role_id

        ),

        FOREIGN KEY(
        guild_id,
        character_name
        )

        REFERENCES character_configs(
        guild_id,
        character_name
        )

        ON DELETE CASCADE

        )

        """)

        await db.commit()

        await migrate_character_child_tables(db)


async def ensure_column(
    db,
    table_name,
    column_name,
    column_type
):

    async with db.execute(
        f"PRAGMA table_info({table_name})"
    ) as cursor:

        rows=await cursor.fetchall()

    existing_columns={
        row[1]
        for row in rows
    }

    if column_name in existing_columns:
        return

    await db.execute(
        f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
    )

async def table_has_foreign_keys(
    db,
    table_name
):

    async with db.execute(
        f"PRAGMA foreign_key_list({table_name})"
    ) as cursor:

        rows=await cursor.fetchall()

        return bool(rows)

async def rebuild_character_child_table(
    db,
    table_name,
    create_sql,
    columns
):

    temp_table=f"{table_name}_fk_new"
    column_list=", ".join(columns)
    source_columns=", ".join(
        f"old.{column}"
        for column in columns
    )

    await db.execute(
        f"DROP TABLE IF EXISTS {temp_table}"
    )

    await db.execute(
        create_sql.format(table_name=temp_table)
    )

    await db.execute(f"""

    INSERT OR IGNORE INTO {temp_table}
    ({column_list})

    SELECT {source_columns}

    FROM {table_name} old

    WHERE EXISTS(
        SELECT 1
        FROM character_configs parent
        WHERE parent.guild_id=old.guild_id
        AND parent.character_name=old.character_name
    )

    """)

    await db.execute(
        f"DROP TABLE {table_name}"
    )

    await db.execute(
        f"ALTER TABLE {temp_table} RENAME TO {table_name}"
    )

async def migrate_character_child_tables(
    db
):

    table_specs=[
        {
            "name": "character_roles",
            "columns": [
                "id",
                "guild_id",
                "character_name",
                "role_type",
                "role_id"
            ],
            "create_sql": """
            CREATE TABLE {table_name}(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                character_name TEXT,
                role_type TEXT,
                role_id INTEGER,
                UNIQUE(
                    guild_id,
                    character_name,
                    role_type
                ),
                FOREIGN KEY(
                    guild_id,
                    character_name
                )
                REFERENCES character_configs(
                    guild_id,
                    character_name
                )
                ON DELETE CASCADE
            )
            """
        },
        {
            "name": "character_role_requirements",
            "columns": [
                "id",
                "guild_id",
                "character_name",
                "role_id",
                "required_eidolons",
                "required_superimpose",
                "require_signature",
                "require_max_traces"
            ],
            "create_sql": """
            CREATE TABLE {table_name}(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                character_name TEXT,
                role_id INTEGER,
                required_eidolons INTEGER,
                required_superimpose INTEGER,
                require_signature INTEGER,
                require_max_traces INTEGER,
                UNIQUE(
                    guild_id,
                    character_name,
                    role_id
                ),
                FOREIGN KEY(
                    guild_id,
                    character_name
                )
                REFERENCES character_configs(
                    guild_id,
                    character_name
                )
                ON DELETE CASCADE
            )
            """
        },
        {
            "name": "custom_roles",
            "columns": [
                "id",
                "guild_id",
                "character_name",
                "role_id",
                "start_date",
                "end_date",
                "source_type"
            ],
            "create_sql": """
            CREATE TABLE {table_name}(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                character_name TEXT,
                role_id INTEGER,
                start_date TEXT,
                end_date TEXT,
                source_type TEXT,
                UNIQUE(
                    guild_id,
                    character_name,
                    role_id
                ),
                FOREIGN KEY(
                    guild_id,
                    character_name
                )
                REFERENCES character_configs(
                    guild_id,
                    character_name
                )
                ON DELETE CASCADE
            )
            """
        }
    ]

    needs_migration=False

    for spec in table_specs:
        if not await table_has_foreign_keys(
            db,
            spec["name"]
        ):
            needs_migration=True
            break

    if not needs_migration:
        return

    await db.commit()
    await db.execute(
        "PRAGMA foreign_keys = OFF"
    )

    for spec in table_specs:
        if await table_has_foreign_keys(
            db,
            spec["name"]
        ):
            continue

        await rebuild_character_child_table(
            db,
            spec["name"],
            spec["create_sql"],
            spec["columns"]
        )

    await db.commit()
    await db.execute(
        "PRAGMA foreign_keys = ON"
    )

    async with db.execute(
        "PRAGMA foreign_key_check"
    ) as cursor:

        violations=await cursor.fetchall()

    if violations:
        raise RuntimeError(
            f"Foreign key migration failed: {violations}"
        )


async def save_log_channel(
    guild_id,
    channel_id
):

    async with open_database() as db:

        await db.execute("""

        INSERT INTO guild_settings
        (guild_id, log_channel_id)

        VALUES (?,?)

        ON CONFLICT(guild_id)

        DO UPDATE SET

        log_channel_id=
        excluded.log_channel_id

        """,

        (
            guild_id,
            channel_id
        )
        )

        await db.commit()

async def get_log_channel(
    guild_id
):

    async with open_database() as db:

        async with db.execute("""

        SELECT log_channel_id

        FROM guild_settings

        WHERE guild_id=?

        """,

        (guild_id,)

        ) as cursor:

            result=await cursor.fetchone()

            if result:
                return result[0]

            return None

async def get_verification_log_channel(
    guild_id
):

    settings=await get_guild_settings(
        guild_id
    )

    if not settings:
        return None

    return (
        settings.get("verification_log_channel_id")
        or settings.get("log_channel_id")
    )

async def get_admin_log_channel(
    guild_id
):

    settings=await get_guild_settings(
        guild_id
    )

    if not settings:
        return None

    return (
        settings.get("admin_log_channel_id")
        or settings.get("log_channel_id")
    )

async def update_settings(
    guild_id,
    **kwargs
):

    allowed_columns = {
        "log_channel_id",
        "verification_log_channel_id",
        "admin_log_channel_id",
        "forum_channel_id",
        "verify_tag",
        "progress_tag",
        "approved_tag",
        "denied_tag",
        "failed_tag"
    }

    columns=[]
    values=[guild_id]

    for key,value in kwargs.items():

        if key not in allowed_columns:
            raise ValueError(f"Invalid guild setting: {key}")

        if value is not None:

            columns.append(
                key
            )

            values.append(
                value
            )

    if not columns:
        return

    placeholders = ",".join(["?"] * (len(columns) + 1))

    update_clause = ",".join(
        f"{column}=excluded.{column}"
        for column in columns
    )

    query=f"""

    INSERT INTO guild_settings
    (guild_id,{",".join(columns)})

    VALUES ({placeholders})

    ON CONFLICT(guild_id)

    DO UPDATE SET

    {update_clause}

    """

    async with open_database() as db:

        await db.execute(
            query,
            values
        )

        await db.commit()

async def get_guild_settings(
    guild_id
):

    async with open_database() as db:

        db.row_factory=aiosqlite.Row

        async with db.execute("""

        SELECT *

        FROM guild_settings

        WHERE guild_id=?

        """,

        (guild_id,)

        ) as cursor:

            row=await cursor.fetchone()

            if not row:
                return None

            return dict(row)

async def save_character(

    guild_id,
    game,
    name,
    character_id,
    path,
    traces,
    lc
):

    async with open_database() as db:

        await db.execute("""

        INSERT INTO character_configs(

        guild_id,
        game,
        character_name,
        character_id,
        path,
        required_trace_count,
        signature_lightcone_name

        )

        VALUES(
        ?,?,?,?,?,?,?
        )

        ON CONFLICT(

        guild_id,
        game,
        character_name

        )

        DO UPDATE SET

        character_id=excluded.character_id,
        path=excluded.path,
        required_trace_count=excluded.required_trace_count,
        signature_lightcone_name=excluded.signature_lightcone_name

        """,

        (

        guild_id,
        game,
        name,
        character_id,
        path,
        traces,
        lc

        )
        )

        await db.commit()

async def get_character_configs(
    guild_id
):

    async with open_database() as db:

        db.row_factory=aiosqlite.Row

        async with db.execute(

        """

        SELECT *

        FROM character_configs

        WHERE guild_id=?

        """,

        (guild_id,)

        ) as cursor:

            rows=await cursor.fetchall()

            return [

                dict(row)

                for row in rows
            ]

async def get_configured_character_names(guild_id):

    characters = await get_character_configs(guild_id)

    return sorted(
        character["character_name"]
        for character in characters
    )

async def get_configured_character_roles(
    guild_id,
    character_name
):

    async with open_database() as db:

        db.row_factory = aiosqlite.Row

        async with db.execute(
            """
            SELECT role_id, role_type

            FROM character_roles

            WHERE guild_id=?
            AND character_name=?
            """,
            (
                guild_id,
                character_name
            )
        ) as cursor:

            return [
                dict(row)
                for row in await cursor.fetchall()
            ]

async def get_configured_requirement_roles(
    guild_id,
    character_name
):

    async with open_database() as db:

        db.row_factory = aiosqlite.Row

        async with db.execute(
            """
            SELECT role_id

            FROM character_role_requirements

            WHERE guild_id=?
            AND character_name=?
            """,
            (
                guild_id,
                character_name
            )
        ) as cursor:

            return [
                dict(row)
                for row in await cursor.fetchall()
            ]

async def get_configured_custom_roles(
    guild_id,
    character_name
):

    async with open_database() as db:

        db.row_factory = aiosqlite.Row

        async with db.execute(
            """
            SELECT role_id

            FROM custom_roles

            WHERE guild_id=?
            AND character_name=?
            """,
            (
                guild_id,
                character_name
            )
        ) as cursor:

            return [
                dict(row)
                for row in await cursor.fetchall()
            ]

async def remove_character(

    guild_id,
    character_name
):

    async with open_database() as db:

        await db.execute("""

        DELETE

        FROM character_configs

        WHERE

        guild_id=?
        AND
        character_name=?

        """,

        (

        guild_id,
        character_name

        ))

        await db.commit()

async def save_character_role(

    guild_id,

    character_name,

    role_type,

    role_id
):

    async with open_database() as db:

        await db.execute("""

        INSERT INTO character_roles(

        guild_id,
        character_name,
        role_type,
        role_id

        )

        VALUES(?,?,?,?)

        ON CONFLICT(

        guild_id,
        character_name,
        role_type

        )

        DO UPDATE SET

        role_id=excluded.role_id

        """,

        (

        guild_id,
        character_name,
        role_type,
        role_id

        )
        )

        await db.commit()

async def get_character_roles(
    guild_id
):

    async with open_database() as db:

        db.row_factory=aiosqlite.Row

        async with db.execute("""

        SELECT *

        FROM character_roles

        WHERE guild_id=?

        """,

        (guild_id,)

        ) as cursor:

            rows=await cursor.fetchall()

            return [

                dict(row)

                for row in rows
            ]

async def remove_character_role(

    guild_id,
    character_name,
    role_type
):

    async with open_database() as db:

        await db.execute("""

        DELETE FROM character_roles

        WHERE guild_id=?
        AND character_name=?
        AND role_type=?

        """,

        (
            guild_id,
            character_name,
            role_type
        ))

        await db.commit()

async def save_character_role_requirement(

    guild_id,
    character_name,
    role_id,
    required_eidolons,
    required_superimpose,
    require_signature,
    require_max_traces
):

    async with open_database() as db:

        await db.execute("""

        INSERT INTO character_role_requirements(

        guild_id,
        character_name,
        role_id,
        required_eidolons,
        required_superimpose,
        require_signature,
        require_max_traces

        )

        VALUES(?,?,?,?,?,?,?)

        ON CONFLICT(

        guild_id,
        character_name,
        role_id

        )

        DO UPDATE SET

        required_eidolons=excluded.required_eidolons,
        required_superimpose=excluded.required_superimpose,
        require_signature=excluded.require_signature,
        require_max_traces=excluded.require_max_traces

        """,

        (
            guild_id,
            character_name,
            role_id,
            required_eidolons,
            required_superimpose,
            int(require_signature),
            int(require_max_traces)
        ))

        await db.commit()

async def get_character_role_requirements(
    guild_id
):

    async with open_database() as db:

        db.row_factory=aiosqlite.Row

        async with db.execute("""

        SELECT *

        FROM character_role_requirements

        WHERE guild_id=?

        """,

        (guild_id,)

        ) as cursor:

            rows=await cursor.fetchall()

            return [
                dict(row)
                for row in rows
            ]

async def remove_character_role_requirement(

    guild_id,
    character_name,
    role_id
):

    async with open_database() as db:

        await db.execute("""

        DELETE FROM character_role_requirements

        WHERE guild_id=?
        AND character_name=?
        AND role_id=?

        """,

        (
            guild_id,
            character_name,
            role_id
        ))

        await db.commit()

async def save_custom_role(

    guild_id,
    character_name,
    role_id,
    start_date,
    end_date,
    source_type
):

    async with open_database() as db:

        await db.execute("""

        INSERT INTO custom_roles(

        guild_id,
        character_name,
        role_id,
        start_date,
        end_date,
        source_type

        )

        VALUES(?,?,?,?,?,?)

        ON CONFLICT(

        guild_id,
        character_name,
        role_id

        )

        DO UPDATE SET

        start_date=excluded.start_date,
        end_date=excluded.end_date,
        source_type=excluded.source_type

        """,

        (
            guild_id,
            character_name,
            role_id,
            start_date,
            end_date,
            source_type
        ))

        await db.commit()

async def get_custom_roles(
    guild_id
):

    async with open_database() as db:

        db.row_factory=aiosqlite.Row

        async with db.execute("""

        SELECT *

        FROM custom_roles

        WHERE guild_id=?

        """,

        (guild_id,)

        ) as cursor:

            rows=await cursor.fetchall()

            return [
                dict(row)
                for row in rows
            ]

async def remove_custom_role(

    guild_id,
    character_name,
    role_id
):

    async with open_database() as db:

        await db.execute("""

        DELETE FROM custom_roles

        WHERE guild_id=?
        AND character_name=?
        AND role_id=?

        """,

        (
            guild_id,
            character_name,
            role_id
        ))

        await db.commit()
