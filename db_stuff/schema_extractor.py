#!/usr/bin/env python3
"""
Database Schema Extractor for AI Agent
Extracts comprehensive schema information optimized for Q&A and data visualization.
"""

import sqlite3
import json
from typing import Dict, List, Any
from datetime import datetime

class SchemaExtractor:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def extract_full_schema(self) -> Dict[str, Any]:
        """Extract comprehensive schema information for AI agent."""

        schema = {
            "metadata": {
                "database_name": "European Parliament Voting Database",
                "description": "Comprehensive database tracking MEP voting behavior, political affiliations, and legislative procedures in the European Parliament",
                "extraction_date": datetime.now().isoformat(),
                "total_tables": 0,
                "data_period": None
            },
            "tables": {},
            "relationships": {},
            "domain_knowledge": self._get_domain_knowledge(),
            "common_questions": self._get_common_questions(),
            "visualization_suggestions": self._get_visualization_suggestions(),
            "query_patterns": self._get_query_patterns()
        }

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        schema["metadata"]["total_tables"] = len(tables)

        # Extract each table's information
        for table in tables:
            schema["tables"][table] = self._extract_table_info(cursor, table)

        # Extract relationships
        schema["relationships"] = self._extract_relationships(cursor, tables)

        # Get data period
        try:
            cursor.execute("SELECT MIN(timestamp), MAX(timestamp) FROM votes WHERE timestamp IS NOT NULL")
            date_range = cursor.fetchone()
            if date_range[0] and date_range[1]:
                schema["metadata"]["data_period"] = {
                    "start": date_range[0],
                    "end": date_range[1]
                }
        except:
            pass

        conn.close()
        return schema

    def _extract_table_info(self, cursor, table_name: str) -> Dict[str, Any]:
        """Extract detailed information about a specific table."""

        # Get table info
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns_info = cursor.fetchall()

        # Get row count
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        row_count = cursor.fetchone()[0]

        # Get sample data
        cursor.execute(f"SELECT * FROM {table_name} LIMIT 3")
        sample_rows = cursor.fetchall()

        table_info = {
            "description": self._get_table_description(table_name),
            "row_count": row_count,
            "columns": {},
            "primary_key": None,
            "sample_data": sample_rows,
            "analysis_potential": self._get_analysis_potential(table_name),
            "visualization_types": self._get_suitable_chart_types(table_name)
        }

        # Process columns
        for col in columns_info:
            # PRAGMA table_info returns: (cid, name, type, notnull, dflt_value, pk)
            cid, col_name, data_type, not_null, default_val, is_pk = col

            if is_pk:
                table_info["primary_key"] = col_name

            table_info["columns"][col_name] = {
                "type": data_type,
                "nullable": not not_null,
                "description": self._get_column_description(table_name, col_name),
                "data_category": self._categorize_column(table_name, col_name, data_type),
                "visualization_role": self._get_viz_role(table_name, col_name, data_type)
            }

            # Get value statistics for certain columns
            if table_name in ['votes', 'member_votes', 'members'] and row_count > 0:
                table_info["columns"][col_name]["sample_values"] = self._get_sample_values(cursor, table_name, col_name)

        return table_info

    def _extract_relationships(self, cursor, tables: List[str]) -> Dict[str, Any]:
        """Extract foreign key relationships between tables."""

        relationships = {
            "foreign_keys": {},
            "entity_relationships": {},
            "join_paths": {}
        }

        for table in tables:
            cursor.execute(f"PRAGMA foreign_key_list({table})")
            fks = cursor.fetchall()

            if fks:
                relationships["foreign_keys"][table] = []
                for fk in fks:
                    relationships["foreign_keys"][table].append({
                        "column": fk[3],
                        "references_table": fk[2],
                        "references_column": fk[4]
                    })

        # Define semantic relationships
        relationships["entity_relationships"] = {
            "members": {
                "related_tables": ["member_votes", "group_memberships", "countries"],
                "relationship_type": "central_entity",
                "description": "MEPs are the central actors who vote and belong to groups"
            },
            "votes": {
                "related_tables": ["member_votes", "eurovoc_concept_votes", "geo_area_votes"],
                "relationship_type": "central_entity",
                "description": "Votes are the central events that connect to topics, geography, and individual positions"
            },
            "member_votes": {
                "related_tables": ["members", "votes"],
                "relationship_type": "junction_table",
                "description": "Junction table recording how each MEP voted on each issue"
            }
        }

        # Common join paths for queries
        relationships["join_paths"] = {
            "member_voting_history": "members → member_votes → votes",
            "party_voting_patterns": "members → group_memberships → groups, members → member_votes",
            "vote_by_topic": "votes → eurovoc_concept_votes → eurovoc_concepts",
            "geographic_voting": "votes → geo_area_votes → geo_areas"
        }

        return relationships

    def _get_sample_values(self, cursor, table_name: str, col_name: str) -> List:
        """Get sample values for a column."""
        try:
            cursor.execute(f"SELECT DISTINCT {col_name} FROM {table_name} WHERE {col_name} IS NOT NULL LIMIT 5")
            return [row[0] for row in cursor.fetchall()]
        except:
            return []

    def _get_table_description(self, table_name: str) -> str:
        """Get human-readable description of table purpose."""
        descriptions = {
            "members": "Individual Members of European Parliament (MEPs) with personal information and country affiliation",
            "votes": "Roll-call votes held in plenary sessions with procedure details and vote counts",
            "member_votes": "Individual voting positions (FOR/AGAINST/ABSTENTION) of each MEP on each vote",
            "countries": "EU member states and their country codes",
            "groups": "Political groups in the European Parliament (parties/coalitions)",
            "group_memberships": "Historical record of which political group each MEP belonged to over time",
            "committees": "Parliamentary committees responsible for specific policy areas",
            "eurovoc_concepts": "Standardized topic classifications for EU legislation",
            "oeil_subjects": "Legislative procedure subjects from the Legislative Observatory",
            "geo_areas": "Geographic entities (countries, regions) relevant to specific votes",
            "eurovoc_concept_votes": "Links votes to their policy topic categories",
            "oeil_subject_votes": "Links votes to legislative procedure subjects",
            "geo_area_votes": "Links votes to relevant geographic areas",
            "responsible_committee_votes": "Links votes to the parliamentary committee responsible"
        }
        return descriptions.get(table_name, f"Database table: {table_name}")

    def _get_column_description(self, table_name: str, col_name: str) -> str:
        """Get description of what each column represents."""

        # Common column patterns
        if col_name == "id":
            return f"Unique identifier for {table_name}"
        elif col_name.endswith("_id"):
            ref_table = col_name[:-3]
            return f"Foreign key reference to {ref_table} table"
        elif col_name.endswith("_code"):
            return f"Code/identifier for {col_name[:-5]}"
        elif col_name == "timestamp":
            return "Date and time when the vote took place"
        elif col_name == "position":
            return "How the MEP voted: FOR, AGAINST, ABSTENTION, or DID_NOT_VOTE"
        elif col_name == "is_main":
            return "Whether this is a main vote (vs amendment vote)"
        elif col_name in ["count_for", "count_against", "count_abstention"]:
            return f"Number of MEPs who voted {col_name.split('_')[1]}"
        elif col_name == "result":
            return "Official outcome: ADOPTED, REJECTED, or LAPSED"

        return f"Column {col_name} in {table_name} table"

    def _categorize_column(self, table_name: str, col_name: str, data_type: str) -> str:
        """Categorize column for analysis purposes."""

        if col_name in ["id"] or col_name.endswith("_id"):
            return "identifier"
        elif col_name in ["timestamp", "start_date", "end_date", "date_of_birth"]:
            return "temporal"
        elif col_name in ["country_code", "group_code", "position", "result", "procedure_type"]:
            return "categorical"
        elif col_name.startswith("count_") or col_name == "term":
            return "quantitative"
        elif col_name in ["first_name", "last_name", "label", "description", "display_title"]:
            return "text"
        elif col_name in ["is_main"]:
            return "boolean"
        else:
            return "nominal"

    def _get_viz_role(self, table_name: str, col_name: str, data_type: str) -> str:
        """Determine visualization role for Vega-Lite."""

        if col_name == "timestamp":
            return "temporal"
        elif col_name.startswith("count_") or col_name == "term":
            return "quantitative"
        elif col_name in ["country_code", "group_code", "position", "result", "procedure_type"]:
            return "nominal"
        elif col_name in ["first_name", "last_name"]:
            return "nominal"
        elif col_name in ["is_main"]:
            return "nominal"
        else:
            return "nominal"

    def _get_analysis_potential(self, table_name: str) -> List[str]:
        """Suggest what kinds of analysis this table enables."""

        analysis_map = {
            "members": ["demographic analysis", "country representation", "MEP profiles"],
            "votes": ["voting trends over time", "procedure type analysis", "vote outcome patterns"],
            "member_votes": ["individual voting behavior", "party discipline analysis", "voting similarity"],
            "group_memberships": ["political group changes", "party switching analysis"],
            "eurovoc_concept_votes": ["policy topic analysis", "issue-based voting patterns"],
            "geo_area_votes": ["geographic voting patterns", "regional interests"]
        }

        return analysis_map.get(table_name, ["general data analysis"])

    def _get_suitable_chart_types(self, table_name: str) -> List[str]:
        """Suggest appropriate Vega-Lite chart types for this table."""

        chart_map = {
            "members": ["bar chart (by country)", "pie chart (by group)", "map (geographic distribution)"],
            "votes": ["line chart (votes over time)", "bar chart (by procedure type)", "histogram (vote counts)"],
            "member_votes": ["heatmap (MEP vs votes)", "stacked bar (voting positions)", "scatter plot (voting patterns)"],
            "group_memberships": ["timeline", "sankey diagram (group changes)"],
            "eurovoc_concept_votes": ["treemap (topic hierarchy)", "network diagram (vote-topic connections)"],
            "geo_area_votes": ["map visualization", "bar chart (by region)"]
        }

        return chart_map.get(table_name, ["bar chart", "scatter plot"])

    def _get_domain_knowledge(self) -> Dict[str, Any]:
        """Provide EU Parliament domain knowledge."""

        return {
            "glossary": {
                "MEP": "Member of European Parliament",
                "Roll-call vote": "Recorded vote where each MEP's position is documented",
                "Plenary": "Full parliament session where all MEPs can participate",
                "Political group": "Coalition of political parties from different EU countries",
                "EuroVoc": "Multilingual thesaurus covering EU policy areas",
                "OEIL": "Legislative Observatory tracking EU legislative procedures"
            },
            "voting_positions": {
                "FOR": "MEP voted in favor of the proposal",
                "AGAINST": "MEP voted against the proposal",
                "ABSTENTION": "MEP abstained from voting",
                "DID_NOT_VOTE": "MEP was not present or did not participate"
            },
            "procedure_types": {
                "COD": "Ordinary Legislative Procedure (co-decision)",
                "RSP": "Resolution/Report procedure",
                "BUD": "Budget-related procedure"
            },
            "temporal_notes": {
                "group_membership": "MEPs can change political groups during parliamentary terms",
                "voting_context": "group_code in member_votes reflects the group MEP belonged to at time of vote"
            }
        }

    def _get_common_questions(self) -> List[Dict[str, str|List[str]]]:
        """Define common questions the AI should be able to answer."""

        return [
            {
                "question": "How did [MEP name] vote on [topic/vote]?",
                "query_pattern": "member voting history",
                "tables_needed": ["members", "member_votes", "votes"]
            },
            {
                "question": "What is the voting pattern of [political group] on [topic]?",
                "query_pattern": "group voting analysis",
                "tables_needed": ["groups", "group_memberships", "member_votes", "votes", "eurovoc_concept_votes"]
            },
            {
                "question": "How do MEPs from [country] typically vote?",
                "query_pattern": "country voting patterns",
                "tables_needed": ["members", "member_votes", "countries"]
            },
            {
                "question": "What were the most controversial votes in [time period]?",
                "query_pattern": "controversial vote analysis",
                "tables_needed": ["votes", "member_votes"]
            },
            {
                "question": "Show me voting trends over time for [topic]",
                "query_pattern": "temporal voting analysis",
                "tables_needed": ["votes", "eurovoc_concept_votes", "member_votes"]
            }
        ]

    def _get_visualization_suggestions(self) -> Dict[str, List[Dict]]:
        """Suggest specific visualizations for common analysis."""

        return {
            "voting_patterns": [
                {
                    "type": "heatmap",
                    "description": "MEPs (y-axis) vs Votes (x-axis), color by position",
                    "vega_lite_type": "rect",
                    "encoding": {"x": "vote_id", "y": "member_id", "color": "position"}
                },
                {
                    "type": "stacked_bar",
                    "description": "Vote outcomes by political group",
                    "vega_lite_type": "bar",
                    "encoding": {"x": "group_code", "y": "count", "color": "position"}
                }
            ],
            "temporal_analysis": [
                {
                    "type": "line_chart",
                    "description": "Number of votes over time",
                    "vega_lite_type": "line",
                    "encoding": {"x": "timestamp", "y": "count"}
                }
            ],
            "geographic_analysis": [
                {
                    "type": "choropleth_map",
                    "description": "Voting patterns by country",
                    "vega_lite_type": "geoshape",
                    "encoding": {"color": "voting_score"}
                }
            ]
        }

    def _get_query_patterns(self) -> Dict[str, str]:
        """Provide SQL query templates for common questions."""

        return {
            "member_voting_history": """
                SELECT m.first_name, m.last_name, v.display_title, mv.position, v.timestamp
                FROM members m
                JOIN member_votes mv ON m.id = mv.member_id
                JOIN votes v ON mv.vote_id = v.id
                WHERE m.id = ?
                ORDER BY v.timestamp DESC
            """,

            "group_voting_patterns": """
                SELECT g.label, mv.position, COUNT(*) as vote_count
                FROM groups g
                JOIN group_memberships gm ON g.code = gm.group_code
                JOIN member_votes mv ON gm.member_id = mv.member_id
                JOIN votes v ON mv.vote_id = v.id
                WHERE v.id = ?
                GROUP BY g.label, mv.position
            """,

            "country_voting_analysis": """
                SELECT c.label, mv.position, COUNT(*) as vote_count
                FROM countries c
                JOIN members m ON c.code = m.country_code
                JOIN member_votes mv ON m.id = mv.member_id
                WHERE mv.vote_id = ?
                GROUP BY c.label, mv.position
            """,

            "controversial_votes": """
                SELECT v.id, v.display_title, v.timestamp,
                       ABS(v.count_for - v.count_against) as margin,
                       (v.count_for + v.count_against + v.count_abstention) as total_votes
                FROM votes v
                WHERE v.count_for > 0 AND v.count_against > 0
                ORDER BY (ABS(v.count_for - v.count_against) * 1.0 / (v.count_for + v.count_against)) ASC
                LIMIT 20
            """,

            "topic_voting_trends": """
                SELECT v.timestamp, ec.label, COUNT(*) as vote_count
                FROM votes v
                JOIN eurovoc_concept_votes ecv ON v.id = ecv.vote_id
                JOIN eurovoc_concepts ec ON ecv.eurovoc_concept_id = ec.id
                WHERE ec.id = ?
                GROUP BY DATE(v.timestamp), ec.label
                ORDER BY v.timestamp
            """
        }

    def save_schema(self, output_path: str) -> None:
        """Extract and save schema to JSON file."""

        schema = self.extract_full_schema()

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(schema, f, indent=2, ensure_ascii=False)

        print(f"Schema extracted and saved to {output_path}")
        print(f"Total tables: {schema['metadata']['total_tables']}")
        if schema['metadata']['data_period']:
            print(f"Data period: {schema['metadata']['data_period']['start']} to {schema['metadata']['data_period']['end']}")

def main():
    """Extract schema from the parliament database."""

    extractor = SchemaExtractor("parliament_votes.db")
    extractor.save_schema("parliament_schema.json")

    # Also create a simplified version for quick reference
    schema = extractor.extract_full_schema()

    # Create simplified schema
    simplified = {
        "tables": {name: {"description": table["description"], "columns": list(table["columns"].keys())}
                  for name, table in schema["tables"].items()},
        "relationships": schema["relationships"]["join_paths"],
        "common_questions": [q["question"] for q in schema["common_questions"]]
    }

    with open("parliament_schema_simple.json", 'w') as f:
        json.dump(simplified, f, indent=2)

    print("\nSimplified schema also saved to parliament_schema_simple.json")

if __name__ == "__main__":
    main()
