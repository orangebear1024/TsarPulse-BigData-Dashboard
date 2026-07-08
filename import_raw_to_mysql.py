"""
TsarPulse — Raw Data Import Script
Reads 4 .dat files and imports them into MySQL 'tsar_pulse' database.
Uses chunked pandas reading for memory efficiency on large files.
"""
import pandas as pd
import pymysql
from sqlalchemy import create_engine, text
import os
import sys

# ── Configuration ──────────────────────────────────────────
DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': '123456',
    'charset': 'utf8mb4',
}
DB_NAME = 'tsar_pulse'

DATA_DIR = os.path.dirname(os.path.abspath(__file__))

FILES = {
    'disk_tsar':    os.path.join(DATA_DIR, 'data', 'disk_tsar.dat'),
    'host_detail':  os.path.join(DATA_DIR, 'data', 'host_detail.dat'),
    'mod_detail':   os.path.join(DATA_DIR, 'data', 'mod_detail.dat'),
    'pref_tsar':    os.path.join(DATA_DIR, 'data', 'pref_tsar.dat'),
}

# Columns for each table (tsar-style data shares the same schema)
TSAR_COLUMNS = ['ts', 'hostid', 'type', 'mod', 'value', 'tag']
HOST_COLUMNS = ['hostid', 'hostname', 'owner', 'model', 'location1', 'location2']
MOD_COLUMNS  = ['mod', 'type', 'desc', 'unit', 'tag']

CHUNKSIZE = 5000   # rows per chunk for large files

# ── Database bootstrap ─────────────────────────────────────
def get_engine(db_name=None):
    target = db_name if db_name else ''
    return create_engine(
        f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@"
        f"{DB_CONFIG['host']}:{DB_CONFIG['port']}/{target}"
        f"?charset={DB_CONFIG['charset']}",
    )

def ensure_database():
    engine_no_db = get_engine()
    with engine_no_db.connect() as conn:
        conn.execute(text(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` "
                          f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))
        conn.commit()
    print(f"[OK] Database '{DB_NAME}' ready.")

def create_tables(engine):
    ddl_statements = [
        # ── Performance TSAR data ──
        f"""CREATE TABLE IF NOT EXISTS `pref_tsar` (
            `id`       BIGINT AUTO_INCREMENT PRIMARY KEY,
            `ts`       BIGINT       NOT NULL,
            `hostid`   VARCHAR(20)  NOT NULL,
            `type`     VARCHAR(20)  NOT NULL,
            `mod`      VARCHAR(50)  NOT NULL,
            `value`    DOUBLE       NOT NULL,
            `tag`      VARCHAR(40)  NOT NULL,
            INDEX idx_hostid (`hostid`),
            INDEX idx_tag    (`tag`),
            INDEX idx_ts     (`ts`),
            INDEX idx_host_tag_ts (`hostid`, `tag`, `ts`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

        # ── Disk TSAR data ──
        f"""CREATE TABLE IF NOT EXISTS `disk_tsar` (
            `id`       BIGINT AUTO_INCREMENT PRIMARY KEY,
            `ts`       BIGINT       NOT NULL,
            `hostid`   VARCHAR(20)  NOT NULL,
            `type`     VARCHAR(20)  NOT NULL,
            `mod`      VARCHAR(50)  NOT NULL,
            `value`    DOUBLE       NOT NULL,
            `tag`      VARCHAR(40)  NOT NULL,
            INDEX idx_hostid (`hostid`),
            INDEX idx_tag    (`tag`),
            INDEX idx_ts     (`ts`),
            INDEX idx_host_tag_ts (`hostid`, `tag`, `ts`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

        # ── Host detail (metadata) ──
        f"""CREATE TABLE IF NOT EXISTS `host_detail` (
            `hostid`    VARCHAR(20)  PRIMARY KEY,
            `hostname`  VARCHAR(100) NOT NULL,
            `owner`     VARCHAR(50),
            `model`     VARCHAR(50),
            `location1` VARCHAR(50),
            `location2` VARCHAR(50)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

        # ── Module detail (metadata) ──
        f"""CREATE TABLE IF NOT EXISTS `mod_detail` (
            `id`    INT AUTO_INCREMENT PRIMARY KEY,
            `mod`   VARCHAR(50) NOT NULL,
            `type`  VARCHAR(20),
            `desc`  VARCHAR(200),
            `unit`  VARCHAR(20),
            `tag`   VARCHAR(40)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    ]

    with engine.connect() as conn:
        for ddl in ddl_statements:
            conn.execute(text(ddl))
        conn.commit()
    print("[OK] Tables created/verified.")

# ── File import ────────────────────────────────────────────
def import_tsar_file(engine, table_name, file_path, columns):
    """Import a TSAR-format .dat file using chunked pandas reading."""
    if not os.path.isfile(file_path):
        print(f"[WARN] File not found: {file_path}")
        return 0

    # First, truncate table
    with engine.connect() as conn:
        conn.execute(text(f"TRUNCATE TABLE `{table_name}`"))
        conn.commit()

    total_rows = 0
    print(f"[>>>] Importing {table_name} from {os.path.basename(file_path)} ...")

    try:
        for chunk in pd.read_csv(
            file_path,
            sep='\t',
            names=columns,
            header=0,
            chunksize=CHUNKSIZE,
            dtype={
                'ts': 'int64',
                'hostid': 'str',
                'type': 'str',
                'mod': 'str',
                'value': 'float64',
                'tag': 'str',
            },
            na_filter=False,
        ):
            chunk.to_sql(
                table_name,
                con=engine,
                if_exists='append',
                index=False,
                method='multi',
            )
            total_rows += len(chunk)
            if total_rows % 50000 == 0:
                print(f"    {total_rows:,} rows imported ...")

        print(f"[OK] {table_name}: {total_rows:,} rows imported.")
    except Exception as e:
        print(f"[ERR] {table_name} import failed: {e}")
        return 0

    return total_rows

def import_small_file(engine, table_name, file_path, columns):
    """Import a small metadata .dat file."""
    if not os.path.isfile(file_path):
        print(f"[WARN] File not found: {file_path}")
        return 0

    with engine.connect() as conn:
        conn.execute(text(f"TRUNCATE TABLE `{table_name}`"))
        conn.commit()

    print(f"[>>>] Importing {table_name} from {os.path.basename(file_path)} ...")

    try:
        df = pd.read_csv(file_path, sep='\t', names=columns, header=0,
                         dtype='str', na_filter=False)
        df.to_sql(table_name, con=engine, if_exists='append', index=False)
        count = len(df)
        print(f"[OK] {table_name}: {count:,} rows imported.")
        return count
    except Exception as e:
        print(f"[ERR] {table_name} import failed: {e}")
        return 0

# ── Verification ───────────────────────────────────────────
def verify(engine):
    print()
    print("=" * 55)
    print("  IMPORT VERIFICATION")
    print("=" * 55)
    tables = ['disk_tsar', 'pref_tsar', 'host_detail', 'mod_detail']
    total = 0
    with engine.connect() as conn:
        for t in tables:
            r = conn.execute(text(f"SELECT COUNT(*) AS cnt FROM `{t}`"))
            cnt = r.fetchone()[0]
            total += cnt
            print(f"  {t:<18} {cnt:>12,} rows")
    print(f"  {'─'*30}")
    print(f"  {'TOTAL':<18} {total:>12,} rows")
    print("=" * 55)

# ── Main ───────────────────────────────────────────────────
def main():
    print("=" * 55)
    print("  TsarPulse — Raw Data Importer")
    print("=" * 55)
    print(f"  MySQL: {DB_CONFIG['host']}:{DB_CONFIG['port']}")
    print(f"  Target DB: {DB_NAME}")
    print()

    ensure_database()
    engine = get_engine(DB_NAME)
    create_tables(engine)

    print()

    # Import TSAR data files (large, chunked)
    import_tsar_file(engine, 'pref_tsar', FILES['pref_tsar'], TSAR_COLUMNS)
    import_tsar_file(engine, 'disk_tsar', FILES['disk_tsar'], TSAR_COLUMNS)

    # Import metadata files (small)
    import_small_file(engine, 'host_detail', FILES['host_detail'], HOST_COLUMNS)
    import_small_file(engine, 'mod_detail',  FILES['mod_detail'],  MOD_COLUMNS)

    verify(engine)
    print()
    print("[DONE] All data imported successfully.")

if __name__ == '__main__':
    main()
