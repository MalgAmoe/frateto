import sqlite3

DB_PATH = "./db_stuff/parliament_votes.db"

def get_vote_details(vote_id: int) -> dict:
    """Get complete details about a specific vote including context and topics.

    Args:
        vote_id: The unique ID of the vote to analyze

    Returns:
        Dict containing vote details, procedure info, vote counts, and related topics
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Get vote details with topics
        cursor.execute("""
            SELECT v.id, v.display_title, v.timestamp, v.procedure_title, v.procedure_type,
                   v.count_for, v.count_against, v.count_abstention, v.count_did_not_vote,
                   v.result, v.description, v.is_main,
                   GROUP_CONCAT(ec.label, '; ') as topics
            FROM votes v
            LEFT JOIN eurovoc_concept_votes ecv ON v.id = ecv.vote_id
            LEFT JOIN eurovoc_concepts ec ON ecv.eurovoc_concept_id = ec.id
            WHERE v.id = ?
            GROUP BY v.id
        """, (vote_id,))

        result = cursor.fetchone()
        conn.close()

        if not result:
            return {"error": f"Vote {vote_id} not found"}

        return {
            "vote_id": result[0],
            "title": result[1],
            "timestamp": result[2],
            "procedure_title": result[3],
            "procedure_type": result[4],
            "votes_for": result[5],
            "votes_against": result[6],
            "abstentions": result[7],
            "did_not_vote": result[8],
            "result": result[9],
            "description": result[10],
            "is_main_vote": bool(result[11]),
            "policy_topics": result[12] if result[12] else "No topics available",
            "total_participating": (result[5] or 0) + (result[6] or 0) + (result[7] or 0)
        }

    except Exception as e:
        return {"error": f"Database error: {str(e)}"}

def get_controversial_votes(limit: int) -> dict:
    """Find the most controversial votes (closest margins between FOR and AGAINST).

    Args:
        limit: Maximum number of controversial votes to return (default 10)

    Returns:
        Dict containing list of controversial votes with margin analysis
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT v.id, v.display_title, v.timestamp,
                   v.count_for, v.count_against, v.count_abstention,
                   ABS(v.count_for - v.count_against) as margin,
                   ROUND(ABS(v.count_for - v.count_against) * 100.0 /
                         NULLIF(v.count_for + v.count_against, 0), 2) as margin_percentage,
                   v.result
            FROM votes v
            WHERE v.count_for > 0 AND v.count_against > 0
            ORDER BY margin_percentage ASC, margin ASC
            LIMIT ?
        """, (limit,))

        results = cursor.fetchall()
        conn.close()

        controversial_votes = []
        for row in results:
            controversial_votes.append({
                "vote_id": row[0],
                "title": row[1],
                "timestamp": row[2],
                "votes_for": row[3],
                "votes_against": row[4],
                "abstentions": row[5],
                "vote_margin": row[6],
                "margin_percentage": row[7],
                "result": row[8]
            })

        return {
            "controversial_votes": controversial_votes,
            "count": len(controversial_votes),
            "explanation": "Votes ordered by smallest margin between FOR and AGAINST votes"
        }

    except Exception as e:
        return {"error": f"Database error: {str(e)}"}

def get_group_voting_breakdown(vote_id: int) -> dict:
    """Analyze how each political group voted on a specific vote.

    Args:
        vote_id: The unique ID of the vote to analyze

    Returns:
        Dict containing breakdown of voting positions by political group
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # First verify the vote exists and get its timestamp
        cursor.execute("SELECT display_title, timestamp FROM votes WHERE id = ?", (vote_id,))
        vote_info = cursor.fetchone()
        if not vote_info:
            conn.close()
            return {"error": f"Vote {vote_id} not found"}

        # Use the group_code from member_votes table directly (it's already the group at time of vote)
        cursor.execute("""
            SELECT
                COALESCE(g.label, 'Non-attached') as political_group,
                COALESCE(g.short_label, 'NI') as short_label,
                mv.position,
                COUNT(*) as mep_count,
                ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (PARTITION BY COALESCE(mv.group_code, 'NI')), 2) as group_percentage
            FROM member_votes mv
            LEFT JOIN groups g ON mv.group_code = g.code
            WHERE mv.vote_id = ?
            GROUP BY COALESCE(g.label, 'Non-attached'), COALESCE(g.short_label, 'NI'), mv.position
            ORDER BY COALESCE(g.label, 'Non-attached'),
                     CASE mv.position
                         WHEN 'FOR' THEN 1
                         WHEN 'AGAINST' THEN 2
                         WHEN 'ABSTENTION' THEN 3
                         WHEN 'DID_NOT_VOTE' THEN 4
                     END
        """, (vote_id,))

        results = cursor.fetchall()
        conn.close()

        # Organize results by political group
        group_breakdown = {}
        for row in results:
            group_name = row[0]
            short_label = row[1]
            position = row[2]
            count = row[3]
            percentage = row[4]

            if group_name not in group_breakdown:
                group_breakdown[group_name] = {
                    "group_short_name": short_label,
                    "positions": {},
                    "total_meps": 0
                }

            group_breakdown[group_name]["positions"][position] = {
                "count": count,
                "percentage": percentage
            }
            group_breakdown[group_name]["total_meps"] += count

        return {
            "vote_id": vote_id,
            "vote_title": vote_info[0],
            "vote_timestamp": vote_info[1],
            "group_breakdown": group_breakdown,
            "explanation": "Shows how MEPs from each political group voted (groups as they were at time of vote)"
        }

    except Exception as e:
        return {"error": f"Database error: {str(e)}"}

def search_votes_by_topic(topic_keyword: str) -> dict:
    """Find votes related to a specific policy topic or keyword.

    Args:
        topic_keyword: Keyword to search for in policy topics (case-insensitive)

    Returns:
        Dict containing votes related to the specified topic
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT DISTINCT v.id, v.display_title, v.timestamp, v.result,
                   v.count_for, v.count_against, v.count_abstention,
                   COUNT(DISTINCT mv.member_id) as participating_meps,
                   GROUP_CONCAT(DISTINCT ec.label, '; ') as matching_topics
            FROM votes v
            JOIN eurovoc_concept_votes ecv ON v.id = ecv.vote_id
            JOIN eurovoc_concepts ec ON ecv.eurovoc_concept_id = ec.id
            LEFT JOIN member_votes mv ON v.id = mv.vote_id
            WHERE ec.label LIKE ?
            GROUP BY v.id
            ORDER BY v.timestamp DESC
            LIMIT 20
        """, (f"%{topic_keyword}%",))

        results = cursor.fetchall()
        conn.close()

        if not results:
            return {
                "topic_keyword": topic_keyword,
                "votes": [],
                "count": 0,
                "message": f"No votes found related to '{topic_keyword}'"
            }

        topic_votes = []
        for row in results:
            topic_votes.append({
                "vote_id": row[0],
                "title": row[1],
                "timestamp": row[2],
                "result": row[3],
                "votes_for": row[4],
                "votes_against": row[5],
                "abstentions": row[6],
                "participating_meps": row[7],
                "related_topics": row[8]
            })

        return {
            "topic_keyword": topic_keyword,
            "votes": topic_votes,
            "count": len(topic_votes),
            "explanation": f"Votes related to '{topic_keyword}' ordered by most recent first"
        }

    except Exception as e:
        return {"error": f"Database error: {str(e)}"}

def get_country_voting_patterns(vote_id: int) -> dict:
    """Analyze how MEPs from each country voted on a specific vote.

    Args:
        vote_id: The unique ID of the vote to analyze

    Returns:
        Dict containing breakdown of voting positions by country
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # First verify the vote exists
        cursor.execute("SELECT display_title FROM votes WHERE id = ?", (vote_id,))
        vote_info = cursor.fetchone()
        if not vote_info:
            conn.close()
            return {"error": f"Vote {vote_id} not found"}

        cursor.execute("""
            SELECT c.label as country, c.code as country_code,
                   mv.position, COUNT(*) as mep_count,
                   ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (PARTITION BY c.code), 2) as country_percentage
            FROM member_votes mv
            JOIN members m ON mv.member_id = m.id
            JOIN countries c ON m.country_code = c.code
            WHERE mv.vote_id = ?
            GROUP BY c.label, c.code, mv.position
            ORDER BY c.label,
                     CASE mv.position
                         WHEN 'FOR' THEN 1
                         WHEN 'AGAINST' THEN 2
                         WHEN 'ABSTENTION' THEN 3
                         WHEN 'DID_NOT_VOTE' THEN 4
                     END
        """, (vote_id,))

        results = cursor.fetchall()
        conn.close()

        # Organize results by country
        country_breakdown = {}
        for row in results:
            country_name = row[0]
            country_code = row[1]
            position = row[2]
            count = row[3]
            percentage = row[4]

            if country_name not in country_breakdown:
                country_breakdown[country_name] = {
                    "country_code": country_code,
                    "positions": {},
                    "total_meps": 0
                }

            country_breakdown[country_name]["positions"][position] = {
                "count": count,
                "percentage": percentage
            }
            country_breakdown[country_name]["total_meps"] += count

        return {
            "vote_id": vote_id,
            "vote_title": vote_info[0],
            "country_breakdown": country_breakdown,
            "explanation": "Shows how MEPs from each EU country voted"
        }

    except Exception as e:
        return {"error": f"Database error: {str(e)}"}

def search_meps(name: str) -> dict:
    """Search for MEPs by name in the parliament database.

    Args:
        name: Name or partial name of the MEP to search for

    Returns:
        dict: Search results with MEP information
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, first_name, last_name, country_code, date_of_birth, email, facebook, twitter
        FROM members
        WHERE first_name LIKE ? OR last_name LIKE ?
    """, (f"%{name}%", f"%{name}%"))
    results = cursor.fetchall()
    conn.close()
    return {"meps": results}


def get_recent_votes(limit: int) -> dict:
    """Get recent parliament votes.

    Args:
        limit: Number of recent votes to return

    Returns:
        dict: Recent vote information
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, timestamp, display_title, reference, description, is_main, procedure_reference, procedure_title, procedure_type, procedure_stage, count_for, count_against, count_abstention, count_did_not_vote, result
        FROM votes
        ORDER BY timestamp DESC
        LIMIT ?
    """, (limit,))
    results = cursor.fetchall()
    conn.close()
    return {"recent_votes": results}

def get_mep_voting_history(member_id: int, limit: int) -> dict:
    """Get recent voting history for a specific MEP.

    Args:
        member_id: The unique ID of the MEP to analyze
        limit: Maximum number of recent votes to return (default 10)

    Returns:
        Dict containing MEP's recent voting history with vote details
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # First get MEP basic info
        cursor.execute("""
            SELECT first_name, last_name, country_code
            FROM members
            WHERE id = ?
        """, (member_id,))

        mep_info = cursor.fetchone()
        if not mep_info:
            conn.close()
            return {"error": f"MEP with ID {member_id} not found"}

        # Get recent voting history
        cursor.execute("""
            SELECT v.id, v.display_title, v.timestamp, mv.position,
                   v.procedure_title, v.procedure_type, v.result,
                   v.count_for, v.count_against, v.count_abstention,
                   mv.group_code, g.label as group_name
            FROM member_votes mv
            JOIN votes v ON mv.vote_id = v.id
            LEFT JOIN groups g ON mv.group_code = g.code
            WHERE mv.member_id = ?
            ORDER BY v.timestamp DESC
            LIMIT ?
        """, (member_id, limit))

        voting_history = cursor.fetchall()
        conn.close()

        # Format the results
        votes = []
        for row in voting_history:
            votes.append({
                "vote_id": row[0],
                "vote_title": row[1],
                "timestamp": row[2],
                "mep_position": row[3],
                "procedure_title": row[4],
                "procedure_type": row[5],
                "vote_result": row[6],
                "total_for": row[7],
                "total_against": row[8],
                "total_abstention": row[9],
                "mep_group_at_time": row[10],
                "group_name": row[11] or "Non-attached"
            })

        # Calculate voting pattern summary
        position_counts = {}
        for vote in votes:
            pos = vote["mep_position"]
            position_counts[pos] = position_counts.get(pos, 0) + 1

        return {
            "member_id": member_id,
            "mep_name": f"{mep_info[0]} {mep_info[1]}",
            "country": mep_info[2],
            "recent_votes": votes,
            "votes_analyzed": len(votes),
            "voting_pattern_summary": position_counts,
            "explanation": f"Recent voting history for {mep_info[0]} {mep_info[1]} from {mep_info[2]}"
        }

    except Exception as e:
        return {"error": f"Database error: {str(e)}"}

def get_mep_details(member_id: int) -> dict:
    """Get complete MEP profile with current political group and statistics.

    Args:
        member_id: The unique ID of the MEP to analyze

    Returns:
        Dict containing complete MEP profile and voting statistics
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Get basic MEP information
        cursor.execute("""
            SELECT id, first_name, last_name, country_code, date_of_birth, email, facebook, twitter
            FROM members
            WHERE id = ?
        """, (member_id,))

        mep_basic = cursor.fetchone()
        if not mep_basic:
            conn.close()
            return {"error": f"MEP with ID {member_id} not found"}

        # Get country name
        cursor.execute("""
            SELECT label FROM countries WHERE code = ?
        """, (mep_basic[3],))
        country_name = cursor.fetchone()
        country_label = country_name[0] if country_name else mep_basic[3]

        # Get current political group (most recent group membership)
        cursor.execute("""
            SELECT gm.group_code, g.label, g.short_label, gm.start_date, gm.end_date, gm.term
            FROM group_memberships gm
            LEFT JOIN groups g ON gm.group_code = g.code
            WHERE gm.member_id = ?
            ORDER BY gm.start_date DESC, gm.term DESC
            LIMIT 1
        """, (member_id,))

        current_group = cursor.fetchone()

        # Get voting statistics
        cursor.execute("""
            SELECT
                COUNT(*) as total_votes,
                SUM(CASE WHEN position = 'FOR' THEN 1 ELSE 0 END) as votes_for,
                SUM(CASE WHEN position = 'AGAINST' THEN 1 ELSE 0 END) as votes_against,
                SUM(CASE WHEN position = 'ABSTENTION' THEN 1 ELSE 0 END) as abstentions,
                SUM(CASE WHEN position = 'DID_NOT_VOTE' THEN 1 ELSE 0 END) as did_not_vote
            FROM member_votes
            WHERE member_id = ?
        """, (member_id,))

        vote_stats = cursor.fetchone()

        # Get participation rate (percentage of available votes they participated in)
        cursor.execute("""
            SELECT COUNT(DISTINCT v.id) as total_available_votes
            FROM votes v
            WHERE v.timestamp >= (
                SELECT MIN(gm.start_date)
                FROM group_memberships gm
                WHERE gm.member_id = ?
            )
        """, (member_id,))

        total_available = cursor.fetchone()
        participation_rate = 0
        if total_available and total_available[0] > 0:
            participated = vote_stats[0] - vote_stats[4]  # total - did_not_vote
            participation_rate = round((participated / total_available[0]) * 100, 2)

        # Get most active policy areas (top topics this MEP votes on)
        cursor.execute("""
            SELECT ec.label, COUNT(*) as vote_count
            FROM member_votes mv
            JOIN eurovoc_concept_votes ecv ON mv.vote_id = ecv.vote_id
            JOIN eurovoc_concepts ec ON ecv.eurovoc_concept_id = ec.id
            WHERE mv.member_id = ? AND mv.position != 'DID_NOT_VOTE'
            GROUP BY ec.label
            ORDER BY vote_count DESC
            LIMIT 5
        """, (member_id,))

        top_topics = cursor.fetchall()

        # Get recent group changes (if any)
        cursor.execute("""
            SELECT gm.group_code, g.label, gm.start_date, gm.end_date, gm.term
            FROM group_memberships gm
            LEFT JOIN groups g ON gm.group_code = g.code
            WHERE gm.member_id = ?
            ORDER BY gm.start_date DESC, gm.term DESC
            LIMIT 3
        """, (member_id,))

        group_history = cursor.fetchall()

        conn.close()

        # Format current group info
        current_group_info = {
            "group_code": current_group[0] if current_group else None,
            "group_name": current_group[1] if current_group else "Non-attached",
            "group_short_name": current_group[2] if current_group else "NI",
            "member_since": current_group[3] if current_group else None,
            "membership_end": current_group[4] if current_group else None,
            "parliamentary_term": current_group[5] if current_group else None
        }

        # Format voting statistics
        voting_statistics = {
            "total_votes_cast": vote_stats[0],
            "votes_for": vote_stats[1],
            "votes_against": vote_stats[2],
            "abstentions": vote_stats[3],
            "did_not_vote": vote_stats[4],
            "participation_rate_percent": participation_rate,
            "voting_percentages": {
                "for_percent": round((vote_stats[1] / vote_stats[0]) * 100, 1) if vote_stats[0] > 0 else 0,
                "against_percent": round((vote_stats[2] / vote_stats[0]) * 100, 1) if vote_stats[0] > 0 else 0,
                "abstention_percent": round((vote_stats[3] / vote_stats[0]) * 100, 1) if vote_stats[0] > 0 else 0,
                "absent_percent": round((vote_stats[4] / vote_stats[0]) * 100, 1) if vote_stats[0] > 0 else 0
            }
        }

        # Format top policy areas
        policy_interests = []
        for topic in top_topics:
            policy_interests.append({
                "policy_area": topic[0],
                "votes_count": topic[1]
            })

        # Format group history
        political_group_history = []
        for group in group_history:
            political_group_history.append({
                "group_code": group[0],
                "group_name": group[1] or "Non-attached",
                "start_date": group[2],
                "end_date": group[3],
                "term": group[4]
            })

        return {
            "member_id": member_id,
            "personal_info": {
                "first_name": mep_basic[1],
                "last_name": mep_basic[2],
                "full_name": f"{mep_basic[1]} {mep_basic[2]}",
                "country_code": mep_basic[3],
                "country_name": country_label,
                "date_of_birth": mep_basic[4],
                "email": mep_basic[5],
                "facebook": mep_basic[6],
                "twitter": mep_basic[7]
            },
            "current_political_group": current_group_info,
            "voting_statistics": voting_statistics,
            "top_policy_interests": policy_interests,
            "political_group_history": political_group_history,
            "explanation": f"Complete profile for MEP {mep_basic[1]} {mep_basic[2]} from {country_label}"
        }

    except Exception as e:
        return {"error": f"Database error: {str(e)}"}
