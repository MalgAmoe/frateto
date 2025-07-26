#!/usr/bin/env python3
"""
HowTheyVote Data Scraper
Scrapes European Parliament voting data and stores it in a database for AI agent access.
"""

import os
import requests
import pandas as pd
import sqlite3
import logging
from typing import Dict, Optional
import tempfile

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class HowTheyVoteScraper:
    def __init__(self, db_path: str = "parliament_votes.db"):
        self.db_path = db_path
        self.base_url = "https://api.github.com/repos/HowTheyVote/data"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'HowTheyVote-Scraper/1.0',
            'Accept': 'application/vnd.github.v3+json'
        })

        # Expected CSV files and their schemas
        self.table_schemas = {
            'members': {
                'id': 'INTEGER PRIMARY KEY',
                'first_name': 'TEXT',
                'last_name': 'TEXT',
                'country_code': 'TEXT',
                'date_of_birth': 'DATE',
                'email': 'TEXT',
                'facebook': 'TEXT',
                'twitter': 'TEXT',
                'FOREIGN KEY (country_code)': 'REFERENCES countries(code)'
            },
            'countries': {
                'code': 'TEXT PRIMARY KEY',
                'iso_alpha_2': 'TEXT',
                'label': 'TEXT'
            },
            'groups': {
                'code': 'TEXT PRIMARY KEY',
                'official_label': 'TEXT',
                'label': 'TEXT',
                'short_label': 'TEXT'
            },
            'group_memberships': {
                'member_id': 'INTEGER',
                'group_code': 'TEXT',
                'term': 'INTEGER',
                'start_date': 'DATE',
                'end_date': 'DATE',
                'FOREIGN KEY (member_id)': 'REFERENCES members(id)',
                'FOREIGN KEY (group_code)': 'REFERENCES groups(code)'
            },
            'votes': {
                'id': 'INTEGER PRIMARY KEY',
                'timestamp': 'DATETIME',
                'display_title': 'TEXT',
                'reference': 'TEXT',
                'description': 'TEXT',
                'is_main': 'BOOLEAN',
                'procedure_reference': 'TEXT',
                'procedure_title': 'TEXT',
                'procedure_type': 'TEXT',
                'procedure_stage': 'TEXT',
                'count_for': 'INTEGER',
                'count_against': 'INTEGER',
                'count_abstention': 'INTEGER',
                'count_did_not_vote': 'INTEGER',
                'result': 'TEXT'
            },
            'member_votes': {
                'vote_id': 'INTEGER',
                'member_id': 'INTEGER',
                'position': 'TEXT',
                'country_code': 'TEXT',
                'group_code': 'TEXT',
                'PRIMARY KEY (vote_id, member_id)': '',
                'FOREIGN KEY (vote_id)': 'REFERENCES votes(id)',
                'FOREIGN KEY (member_id)': 'REFERENCES members(id)'
            },
            'eurovoc_concepts': {
                'id': 'TEXT PRIMARY KEY',
                'label': 'TEXT'
            },
            'eurovoc_concept_votes': {
                'vote_id': 'INTEGER',
                'eurovoc_concept_id': 'TEXT',
                'FOREIGN KEY (vote_id)': 'REFERENCES votes(id)',
                'FOREIGN KEY (eurovoc_concept_id)': 'REFERENCES eurovoc_concepts(id)'
            },
            'oeil_subjects': {
                'code': 'TEXT PRIMARY KEY',
                'label': 'TEXT'
            },
            'oeil_subject_votes': {
                'vote_id': 'INTEGER',
                'oeil_subject_code': 'TEXT',
                'FOREIGN KEY (vote_id)': 'REFERENCES votes(id)',
                'FOREIGN KEY (oeil_subject_code)': 'REFERENCES oeil_subjects(code)'
            },
            'geo_areas': {
                'code': 'TEXT PRIMARY KEY',
                'label': 'TEXT',
                'iso_alpha_2': 'TEXT'
            },
            'geo_area_votes': {
                'vote_id': 'INTEGER',
                'geo_area_code': 'TEXT',
                'FOREIGN KEY (vote_id)': 'REFERENCES votes(id)',
                'FOREIGN KEY (geo_area_code)': 'REFERENCES geo_areas(code)'
            },
            'committees': {
                'code': 'TEXT PRIMARY KEY',
                'label': 'TEXT',
                'abbreviation': 'TEXT'
            },
            'responsible_committee_votes': {
                'vote_id': 'INTEGER',
                'committee_code': 'TEXT',
                'FOREIGN KEY (vote_id)': 'REFERENCES votes(id)',
                'FOREIGN KEY (committee_code)': 'REFERENCES committees(code)'
            }
        }

    def get_latest_release(self) -> Dict:
        """Get information about the latest data release."""
        try:
            response = self.session.get(f"{self.base_url}/releases/latest")
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Failed to fetch latest release: {e}")
            raise

    def get_specific_release(self, tag: str) -> Dict:
        """Get information about a specific release by tag."""
        try:
            response = self.session.get(f"{self.base_url}/releases/tags/{tag}")
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Failed to fetch release {tag}: {e}")
            raise

    def create_database_schema(self):
        """Create the database schema with proper foreign key relationships."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Enable foreign key constraints
            cursor.execute("PRAGMA foreign_keys = ON")

            # Define creation order - parent tables first, then children
            table_creation_order = [
                # Reference tables first (no dependencies)
                'countries',
                'groups',
                'committees',
                'eurovoc_concepts',
                'oeil_subjects',
                'geo_areas',

                # Core entities
                'members',  # depends on countries
                'votes',    # no dependencies

                # Junction/relationship tables (depend on core entities)
                'group_memberships',           # depends on members, groups
                'member_votes',               # depends on members, votes
                'eurovoc_concept_votes',      # depends on votes, eurovoc_concepts
                'oeil_subject_votes',         # depends on votes, oeil_subjects
                'geo_area_votes',             # depends on votes, geo_areas
                'responsible_committee_votes' # depends on votes, committees
            ]

            for table_name in table_creation_order:
                if table_name not in self.table_schemas:
                    continue

                schema = self.table_schemas[table_name]

                # Drop table if exists
                cursor.execute(f"DROP TABLE IF EXISTS {table_name}")

                # Create table with proper foreign keys
                columns = []
                constraints = []

                for column, definition in schema.items():
                    if column.startswith('PRIMARY KEY'):
                        constraints.append(f"{column} {definition}")
                    elif column.startswith('FOREIGN KEY'):
                        constraints.append(f"{column} {definition}")
                    else:
                        columns.append(f"{column} {definition}")

                create_sql = f"CREATE TABLE {table_name} (\n"
                create_sql += ",\n".join(columns)
                if constraints:
                    create_sql += ",\n" + ",\n".join(constraints)
                create_sql += "\n)"

                logger.info(f"Creating table: {table_name}")
                cursor.execute(create_sql)

            # Create indexes for common queries
            indexes = [
                "CREATE INDEX IF NOT EXISTS idx_member_votes_vote_id ON member_votes(vote_id)",
                "CREATE INDEX IF NOT EXISTS idx_member_votes_member_id ON member_votes(member_id)",
                "CREATE INDEX IF NOT EXISTS idx_votes_timestamp ON votes(timestamp)",
                "CREATE INDEX IF NOT EXISTS idx_votes_procedure_type ON votes(procedure_type)",
                "CREATE INDEX IF NOT EXISTS idx_group_memberships_member_id ON group_memberships(member_id)",
                "CREATE INDEX IF NOT EXISTS idx_group_memberships_group_code ON group_memberships(group_code)",
                "CREATE INDEX IF NOT EXISTS idx_eurovoc_concept_votes_vote_id ON eurovoc_concept_votes(vote_id)",
                "CREATE INDEX IF NOT EXISTS idx_oeil_subject_votes_vote_id ON oeil_subject_votes(vote_id)",
                "CREATE INDEX IF NOT EXISTS idx_geo_area_votes_vote_id ON geo_area_votes(vote_id)",
                "CREATE INDEX IF NOT EXISTS idx_responsible_committee_votes_vote_id ON responsible_committee_votes(vote_id)"
            ]

            for index_sql in indexes:
                cursor.execute(index_sql)

            conn.commit()
            conn.close()
            logger.info("Database schema created successfully with foreign key relationships")

        except Exception as e:
            logger.error(f"Failed to create database schema: {e}")
            raise

    def load_csv_to_database(self, csv_path: str, table_name: str, conn: sqlite3.Connection):
        """Load a CSV file into the database."""
        try:
            if not os.path.exists(csv_path):
                logger.warning(f"CSV file not found: {csv_path}")
                return

            logger.info(f"Loading {table_name} from {csv_path}")

            # Read CSV with pandas (handles gzipped files automatically)
            df = pd.read_csv(csv_path, compression='gzip')

            # Handle empty values
            df = df.where(pd.notnull(df), None)

            # Convert boolean columns
            if 'is_main' in df.columns:
                df['is_main'] = df['is_main'].astype(bool)

            # Load into database - use append since tables already exist with proper schema
            df.to_sql(table_name, conn, if_exists='append', index=False)

            row_count = len(df)
            logger.info(f"Loaded {row_count} rows into {table_name}")

        except Exception as e:
            logger.error(f"Failed to load {table_name}: {e}")
            raise

    def scrape_and_store(self, release_tag: Optional[str] = None):
        """Main method to scrape data and store in database."""
        logger.info("Starting HowTheyVote data scraping...")

        try:
            # Get release information
            if release_tag:
                release_info = self.get_specific_release(release_tag)
                logger.info(f"Using specific release: {release_tag}")
            else:
                release_info = self.get_latest_release()
                logger.info(f"Using latest release: {release_info['tag_name']}")

            tag_name = release_info['tag_name']

            # Create database schema with proper foreign keys
            self.create_database_schema()

            # Create temporary directory for downloads
            with tempfile.TemporaryDirectory() as temp_dir:
                # Load CSV files into database in proper order (parents before children)
                load_order = [
                    # Reference tables first
                    'countries', 'groups', 'committees', 'eurovoc_concepts', 'oeil_subjects', 'geo_areas',
                    # Core entities
                    'members', 'votes',
                    # Relationship tables last
                    'group_memberships', 'member_votes', 'eurovoc_concept_votes',
                    'oeil_subject_votes', 'geo_area_votes', 'responsible_committee_votes'
                ]

                conn = sqlite3.connect(self.db_path)

                for table_name in load_order:
                    if table_name not in self.table_schemas:
                        continue

                    # Download individual CSV.gz file
                    csv_url = f"https://github.com/HowTheyVote/data/releases/download/{tag_name}/{table_name}.csv.gz"
                    csv_path = os.path.join(temp_dir, f"{table_name}.csv.gz")

                    logger.info(f"Downloading {csv_url}")
                    try:
                        response = self.session.get(csv_url)
                        response.raise_for_status()

                        with open(csv_path, 'wb') as f:
                            f.write(response.content)

                        self.load_csv_to_database(csv_path, table_name, conn)

                    except requests.RequestException as e:
                        logger.warning(f"Failed to download {table_name}.csv.gz: {e}")
                        continue

                conn.close()

            logger.info(f"Successfully scraped and stored data in {self.db_path}")
            self.print_database_stats()

        except Exception as e:
            logger.error(f"Scraping failed: {e}")
            raise

    def verify_foreign_keys(self):
        """Verify that foreign key relationships were created properly."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            print("\n" + "="*50)
            print("FOREIGN KEY RELATIONSHIPS")
            print("="*50)

            # Check foreign keys for each table
            tables_with_fks = ['members', 'group_memberships', 'member_votes', 'eurovoc_concept_votes',
                             'oeil_subject_votes', 'geo_area_votes', 'responsible_committee_votes']

            for table_name in tables_with_fks:
                cursor.execute(f"PRAGMA foreign_key_list({table_name})")
                fks = cursor.fetchall()

                if fks:
                    print(f"\n{table_name}:")
                    for fk in fks:
                        # fk = (id, seq, table, from, to, on_update, on_delete, match)
                        print(f"  {fk[3]} → {fk[2]}.{fk[4]}")
                else:
                    print(f"\n{table_name}: No foreign keys found")

            conn.close()

        except Exception as e:
            logger.error(f"Failed to verify foreign keys: {e}")

    def print_database_stats(self):
        """Print statistics about the loaded data."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            print("\n" + "="*50)
            print("DATABASE STATISTICS")
            print("="*50)

            for table_name in self.table_schemas.keys():
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                    count = cursor.fetchone()[0]
                    print(f"{table_name:25}: {count:>8} rows")
                except sqlite3.OperationalError:
                    print(f"{table_name:25}: {'N/A':>8} (table not found)")

            # Additional interesting stats (only if tables exist)
            try:
                cursor.execute("SELECT COUNT(DISTINCT country_code) FROM members")
                countries = cursor.fetchone()[0]
                print(f"\nCountries represented: {countries}")
            except sqlite3.OperationalError:
                pass

            try:
                cursor.execute("SELECT MIN(timestamp), MAX(timestamp) FROM votes WHERE timestamp IS NOT NULL")
                date_range = cursor.fetchone()

                cursor.execute("SELECT COUNT(*) FROM votes WHERE is_main = 1")
                main_votes = cursor.fetchone()[0]

                if date_range[0] and date_range[1]:
                    print(f"Vote date range: {date_range[0]} to {date_range[1]}")
                print(f"Main votes: {main_votes}")
            except sqlite3.OperationalError:
                pass

            conn.close()

            # Verify foreign key relationships
            self.verify_foreign_keys()

        except Exception as e:
            logger.error(f"Failed to generate stats: {e}")

def main():
    """CLI interface for the scraper."""
    import argparse

    parser = argparse.ArgumentParser(description='Scrape HowTheyVote EU Parliament data')
    parser.add_argument('--db-path', default='parliament_votes.db',
                       help='Path to SQLite database file')
    parser.add_argument('--release-tag', help='Specific release tag (e.g., 2025-07-21)')
    parser.add_argument('--stats-only', action='store_true',
                       help='Only show database statistics')

    args = parser.parse_args()

    scraper = HowTheyVoteScraper(db_path=args.db_path)

    if args.stats_only:
        if os.path.exists(args.db_path):
            scraper.print_database_stats()
        else:
            print(f"Database not found: {args.db_path}")
        return

    scraper.scrape_and_store(release_tag=args.release_tag)

if __name__ == "__main__":
    main()
