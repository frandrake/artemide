"""Idempotent seed: headhunter intelligence dataset.

Populates firms (12 + 2 supporting), partners (28), per-partner notes,
and a 6-track 12-month engagement calendar.

Usage:
    uv run python scripts/seed_headhunters.py
    docker compose exec artemide uv run python scripts/seed_headhunters.py
    docker compose run --rm artemide uv run python scripts/seed_headhunters.py

PLAN_START_DATE env var (ISO 8601) sets day-0 for calendar offsets.
Defaults to today if not set.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.db import get_connection, init_db  # noqa: E402
from src.ulid_helpers import new_ulid  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _insert_audit(conn: sqlite3.Connection, entity_type: str, entity_id: int,
                  name: str, action: str = "create") -> None:
    conn.execute(
        "INSERT INTO audit_log (ulid, entity_type, entity_id, action, actor, transport, payload) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (new_ulid(), entity_type, str(entity_id), action,
         "seed", "system", json.dumps({"name": name, "source": "seed_headhunters_v1"})),
    )


def _day(start: date, offset: int) -> str:
    return (start + timedelta(days=offset)).isoformat()


def _week(start: date, n: int) -> str:
    """Week n starts at day (n-1)*7."""
    return _day(start, (n - 1) * 7)


# ---------------------------------------------------------------------------
# Firm data
# ---------------------------------------------------------------------------

FIRMS = [
    # (name, tier_col, region, market_tier, strategic_fit, ned_practice_strength,
    #  hq_address, sectors, cmo_practice_depth, comp_transparency,
    #  candidate_reputation, b2b_fs_reputation)
    (
        "Spencer Stuart", "primary", "Global",
        "tier-1-global", "HIGH", "HIGH",
        "55 Baker Street, London W1U 8EW",
        "Financial Services, Technology, Consumer, Professional Services, Media",
        "Largest dedicated CMO franchise of any global search firm. Publishes the annual CMO Tenure Study — the definitive longitudinal benchmark on marketing leadership tenure and succession. Deep bench across FS, TMT and information services. Multiple partners with exclusive CMO mandates in FTSE 100 and Fortune 500.",
        "CMO Tenure Study includes high-level compensation bands by sector. Individual package terms disclosed only within an active engagement.",
        "Considered the most rigorous process among generalist firms. Candidates report structured role briefings, realistic timelines, and substantive feedback loops.",
        "Dominant in FTSE FS CMO appointments and large-cap B2B technology. Multiple cross-practice placements where CMO brief overlapped with CFO and CEO succession.",
    ),
    (
        "Heidrick & Struggles", "primary", "Global",
        "tier-1-global", "HIGH", "HIGH",
        "4 Grosvenor Place, London SW1X 7DL",
        "Financial Services, Technology, Consumer, Industrial, Professional Services",
        "Deepest single-partner CMO pedigree in London via Richard Sumner. Produces the CAG Moves newsletter and CMO Barometer benchmarking survey — practitioner-facing content platforms with high readership. Heidrick Leadership Podcast regularly features senior marketing-leader guests.",
        "CMO Barometer includes compensation benchmarking data shared with participants. Does not publish individual ranges publicly.",
        "Strong reputation on transformation and digitally-enabled CMO mandates. Kit Bingham's EPOC Network and NED practice add a board-level dimension unusual among CMO-focused search teams.",
        "Richard Sumner has placed CMOs at B2B fintech, enterprise software, and regulated-industry clients. EPOC gives the firm credible NED mandate sourcing across FTSE 250.",
    ),
    (
        "Russell Reynolds", "primary", "Global",
        "tier-1-global", "HIGH", "HIGH",
        "Almack House, 28 King Street, London SW1Y 6QW",
        "Financial Services, Technology, Consumer, Industrial, Private Equity",
        "Greg Hodge leads the UK CMO/CCO practice with a focus on transformation mandates in FS and B2B technology. Tristan Jervis adds a tech-native and AI dimension. 'The New CEO' book provides board-level thought-leadership access and bridges into Laura Sanderson's NED practice.",
        "Does not publish compensation data independently. Ranges shared confidentially within active engagements.",
        "Widely cited for long-term relationship management. Candidates note structured processes and strong post-placement follow-through.",
        "Greg Hodge has placed CMOs at Tier-1 banks and global information-services businesses. Tristan Jervis covers scale-up and enterprise B2B tech CMO. Strong FS mandate book in London.",
    ),
    (
        "Egon Zehnder", "primary", "Europe",
        "tier-1-global", "HIGH", "HIGH",
        "Devonshire House, Mayfair, London W1J 8AJ",
        "Financial Services, Industrial, Consumer, Technology, Private Equity",
        "Strongest NED and board-placement practice of any search firm. CMO franchise is narrower than Spencer Stuart or H&S but strategic for FS (Miranda Pode) and consumer markets (Sophie Hanson). NED gateway through Karoline Vinsrygg and Çağla Bekbölet in board consulting.",
        "Does not publish compensation data. Ranges shared within engagement process only.",
        "Bespoke, high-touch process. Often slower than peer firms but valued for rigour and confidentiality. Preferred for sensitive or politically complex searches.",
        "Miranda Pode has placed CMOs in FS and professional services. Egon Zehnder's broad FS presence across banking, insurance, and asset management makes them a credible path for large-cap FS CMO mandates.",
    ),
    (
        "Korn Ferry", "primary", "Global",
        "tier-1-global", "HIGH", "MEDIUM",
        "6 New Street Square, London EC4A 3BF",
        "Technology, Financial Services, Consumer, Industrial, Healthcare",
        "Grant Duncan is consistently cited as the single most active CMO placer in London. Produces the Modern Marketer report. Sonamara Jeffreys adds depth in FS CMO. Korn Ferry's proprietary KF Architect pay database provides unmatched compensation benchmarking across the market.",
        "Publishes extensive compensation benchmarking through KF Architect and Modern Marketer reports. Most transparent of the Tier-1 firms on compensation data.",
        "Efficient, well-resourced processes. Some candidates note a transactional feel versus boutiques, but placement rate and speed of process compensate. Strong on structured assessments.",
        "Grant Duncan has placed CMOs across B2B SaaS, fintech, and enterprise technology. Sonamara Jeffreys is the primary FS CMO resource at KF London.",
    ),
    (
        "TML Partners", "specialist", "London",
        "specialist-boutique", "HIGH", "MEDIUM",
        "London, EC2",
        "Marketing Leadership, Professional Services, Technology, Financial Services",
        "Marketing-leadership-only boutique — the most focused CMO specialist in London. Publishes The CMO Report annually, with original data on CMO tenure, mandate scope, and successor profiles. Only firm in the ecosystem with an exclusive marketing-leadership focus. Existing warm relationship via Simon Bassett.",
        "Shares compensation data informally with warm contacts. Does not publish benchmarks externally.",
        "Highly personal process. Small team means direct partner involvement throughout. Recognised across the market for sector-agnostic CMO specialism and depth of brief quality.",
        "Active across B2B SaaS, information services, and professional services CMO searches. Simon Bassett has placed CMOs at several global FS and B2B technology clients. Book co-authoring and endorsement history with senior marketing figures.",
    ),
    (
        "Odgers Berndtson", "specialist", "London",
        "specialist-boutique", "MEDIUM", "HIGH",
        "9 Waterloo Place, London SW1Y 4BE",
        "Public Sector, Financial Services, Professional Services, Consumer, Technology",
        "Mark Freebairn leads the NED/Board practice — a more relevant gateway than the CMO practice directly. Virginia Bottomley adds chair-level NED capability. Odgers has the widest public-sector search mandate in London and strong FTSE NED presence.",
        "Does not publish compensation data independently.",
        "Strong on long-form, relationship-led processes. More public-sector and board oriented but credible for FTSE NED mandates where sector overlap exists.",
        "Freebairn's NED network bridges financial services and FTSE 250 boards. CMO practice is thinner than Tier-1 peers but the NED gateway is high value for board-track ambitions.",
    ),
    (
        "MBS Group", "specialist", "London",
        "specialist-boutique", "MEDIUM", "MEDIUM",
        "Albany House, Petty France, London SW1H 9EA",
        "Consumer, Retail, Luxury, Media, Marketing Services",
        "Consumer and luxury specialist. Elliott Goldstein leads CMO search with a focus on premium consumer brands and digital commerce. Moira Benigson adds board and NED capability particularly in consumer sectors. Less relevant for pure B2B mandates.",
        "Does not publish compensation benchmarks externally.",
        "High-touch boutique approach. Well regarded in luxury, retail, and media verticals. Personal partner involvement throughout.",
        "Limited B2B FS coverage. Best suited for consumer-facing CMO searches with a premium brand or digital-commerce dimension.",
    ),
    (
        "Grace Blue Partnership", "specialist", "London",
        "specialist-boutique", "MEDIUM", "LOW",
        "4 Cavendish Square, London W1G 0PG",
        "Marketing Services, Agency, Brand, Technology, Media",
        "Agency and marketing-services specialist. Jay Haines (via Sinecure/Grace Blue) covers the AI-native and agency-to-brand crossover CMO segment. Sarah Skinner focuses on brand transformation mandates. Less active on large corporate CMO than Tier-1 peers.",
        "Does not publish compensation data.",
        "Creative, network-led process. Strong in marketing services and agency ecosystems. Particularly useful for candidates crossing from agency to client-side.",
        "Very limited FS exposure. Better suited to consumer, media, and creative-industry CMOs rather than B2B FS mandates.",
    ),
    (
        "Eric Salmon & Partners", "specialist", "Europe",
        "specialist-boutique", "LOW", "N/A",
        "1 King William Street, London EC4N 7AF",
        "Luxury, Consumer, Retail, Technology",
        "Italian heritage, European coverage. London office is smaller than continental presence. Useful for pan-European and Italian-market mandates where dual-language profile is relevant. CMO practice is a secondary offering alongside broader C-suite.",
        "European practice operates with different norms. Limited public compensation transparency.",
        "Niche positioning. Useful for Italian or European C-suite searches where cultural familiarity with continental European markets is required.",
        "Not a primary path for B2B FS mandates in London. European optionality is the relevant use case.",
    ),
    (
        "True Search", "specialist", "Global",
        "specialist-boutique", "MEDIUM", "N/A",
        "London, W1",
        "Technology, Venture, Private Equity, Financial Services",
        "Tech and venture-backed CMO specialist. Active in scale-up and Series B–D searches. Lower relevance for FTSE CMO mandates but useful for tech-sector optionality and cross-referral relationships.",
        "Does not publish compensation benchmarks.",
        "Fast-moving, tech-native process. Good track record in SaaS and fintech scale-up. Less suited to complex matrix organisations.",
        "Relevant for B2B SaaS and fintech CMO at growth stage. Less active in large-cap FS.",
    ),
    (
        "Acertitude", "specialist", "Global",
        "specialist-boutique", "MEDIUM", "N/A",
        "London, EC2",
        "Private Equity, Technology, Financial Services, Professional Services",
        "PE portfolio and mid-market specialist. Useful for CMO-to-CEO succession mandates in PE-backed businesses and for cross-referral from PE portfolio relationships. Growing mandate book across B2B services.",
        "Does not publish compensation data.",
        "Emerging presence with a growing PE mandate book. Useful as a secondary relationship for PE-backed optionality.",
        "Active in PE-backed B2B services. Growing FS mandate book in mid-market.",
    ),
    # Additional firms required by P27 and P28 — not in core 12 but needed for FK integrity.
    (
        "Erevena", "specialist", "London",
        "honourable-mention", "MEDIUM", "N/A",
        "London, W1",
        "Technology, SaaS, Scale-up, Venture",
        "Technology-focused boutique specialising in scale-up and venture-backed CMO searches. Flo Bown leads the CMO practice with a focus on tech-native, AI-adjacent mandates.",
        "Does not publish compensation data.",
        "Lean team, fast process. Strong in Series C–IPO technology mandates.",
        "B2B SaaS and enterprise tech primary focus. Limited FS exposure.",
    ),
    (
        "Sapphire Partners", "ned", "London",
        "honourable-mention", "MEDIUM", "HIGH",
        "London, SW1",
        "NED, Board Advisory, FTSE, Diversity",
        "NED and board-composition specialist. Kate Grussing CBE leads the practice with a focus on FTSE board diversity, audit committee, and remuneration committee appointments.",
        "Does not publish compensation data.",
        "High-touch, long-tenure relationship model. Specialist NED track with strong diversity credentials.",
        "Board-level FS mandates within FTSE scope. Not relevant for executive CMO searches.",
    ),
]

# ---------------------------------------------------------------------------
# Partner data
# ---------------------------------------------------------------------------

# (name, firm_name, title, practice, seniority, ned_gateway,
#  strategic_relevance, practice_focus, warm_intro_angle,
#  linkedin_url, thought_leadership, prior_career)
PARTNERS = [
    # Spencer Stuart
    (
        "Jonathan Harper", "Spencer Stuart",
        "Managing Director", "CMO & Chief Growth Officer Practice", "Managing Director",
        0, "HIGH",
        "Exec CMO mandates across FTSE 100 and global FS, TMT, and professional services.",
        "Route via the AESC (Association of Executive Search Consultants) annual conference — Jonathan Harper chairs or participates in the CMO talent breakout. Alternatively, cite the CMO Tenure Study in published commentary and request a brief exchange on data interpretation.",
        "https://www.linkedin.com/in/jonathan-harper-spencer-stuart",
        "CMO Tenure Study (Spencer Stuart, annual), B2B CMO Succession Patterns (AESC, 2024)",
        "Senior Partner at Egon Zehnder before joining Spencer Stuart.",
    ),
    (
        "Emanuela Aureli", "Spencer Stuart",
        "Partner", "CMO Practice / TMT & Information Services", "Partner",
        0, "HIGH",
        "TMT and information-services CMO mandates in Europe and globally.",
        "AESC Women's Leadership Forum participant. Approach via a commentary note on the CMO Tenure Study's TMT sub-dataset — Aureli co-authors sections on digital transformation mandates. A warm intro via a shared AESC contact or Marketing Society Fellow accelerates access.",
        "https://www.linkedin.com/in/emanuela-aureli",
        "CMO Tenure Study — TMT Supplement (Spencer Stuart, 2024), Digital CMO Leadership in Information Services (AESC, 2023)",
        "Head of Marketing at a global FS data firm before moving to executive search.",
    ),
    (
        "Will House", "Spencer Stuart",
        "Partner", "CMO Practice / Consumer & Retail", "Partner",
        0, "MEDIUM",
        "Consumer, retail, and lifestyle CMO mandates in the UK and Europe.",
        "Marketing Society member network. Will House has spoken at the Marketing Society annual conference — reference shared interest in brand-led growth models as an entry angle.",
        "https://www.linkedin.com/in/will-house-spencer-stuart",
        "Consumer CMO Playbook (Spencer Stuart, 2023)",
        "Brand Director at a major FMCG group before transitioning to search.",
    ),
    # Heidrick & Struggles
    (
        "Richard Sumner", "Heidrick & Struggles",
        "Partner", "Marketing Officer Practice", "Partner",
        0, "HIGH",
        "Exec CMO mandates across B2B technology, FS, and transformation-anchored businesses. Deepest single-partner CMO pedigree in London.",
        "Heidrick Leadership Podcast: pitch a guest slot on the agentic-AI-and-CMO-mandate-scope thesis. Sumner actively sources guests with original data or frameworks — the 'Rules Have Changed' manuscript angle is a direct fit. Alternatively, engage via CAG Moves newsletter response.",
        "https://www.linkedin.com/in/richard-sumner-heidrick",
        "CMO Barometer (Heidrick & Struggles, annual), The Transformation CMO (Heidrick & Struggles, 2024), CAG Moves newsletter (bi-monthly)",
        "Partner at Korn Ferry before joining Heidrick. Early career in management consulting.",
    ),
    (
        "Aliceson Robinson", "Heidrick & Struggles",
        "Partner", "Marketing Officer Practice / Media & Consumer Tech", "Partner",
        0, "MEDIUM",
        "Media, consumer technology, and digital-native CMO mandates.",
        "Women in Marketing annual summit — Aliceson Robinson is a regular panellist. Approach via a note referencing shared interest in CMO tenure data in consumer tech.",
        "https://www.linkedin.com/in/aliceson-robinson-heidrick",
        "Digital CMO Talent Landscape (Heidrick & Struggles, 2023)",
        "Senior Marketing Director at a UK media group before executive search.",
    ),
    (
        "Kit Bingham", "Heidrick & Struggles",
        "Partner", "Board & CEO Practice / EPOC Network", "Partner",
        1, "HIGH",
        "NED and board-composition mandates via EPOC Network. Gateway to Heidrick's NED mandate flow.",
        "EPOC Network 'Meet the Headhunters' events — Kit Bingham co-organises these sessions for senior executives exploring NED appointments. Attend as a participant or propose a roundtable contribution on CMO-to-board pathways.",
        "https://www.linkedin.com/in/kit-bingham-heidrick",
        "CMO-to-Board: The Emerging Pathway (Heidrick & Struggles, 2024)",
        "Partner at Spencer Stuart (board practice) before joining Heidrick.",
    ),
    (
        "Jenni Hibbert", "Heidrick & Struggles",
        "Global Managing Partner", "Global Marketing Officer Practice", "Global Managing Partner",
        0, "MEDIUM",
        "Global CMO practice leadership. Senior firm relationship; primarily relevant for partnership-level introductions.",
        "AESC global conference delegate. Jenni Hibbert speaks at Davos and major global marketing forums — cite shared interest in CMO succession data in a brief written note to her EA.",
        "https://www.linkedin.com/in/jenni-hibbert-heidrick",
        "Future of the CMO Role (Heidrick & Struggles, 2024), AESC Global CMO Outlook (2023)",
        "CMO at a global professional services firm before transitioning to executive search.",
    ),
    # Russell Reynolds Associates
    (
        "Greg Hodge", "Russell Reynolds",
        "Managing Director", "CMO & Marketing Officer Practice", "Managing Director",
        0, "HIGH",
        "Exec CMO mandates across FS, B2B technology, and complex multi-stakeholder businesses. Highest-priority RRA contact.",
        "Chicago Booth alumni network — Greg Hodge is a Booth alumnus; reference shared alumni community as an opening. Alternatively, cite 'Rules Have Changed' book content in a note on CMO mandate scope evolution; Hodge is on record discussing how CMO briefs are shifting.",
        "https://www.linkedin.com/in/greg-hodge-rra",
        "The Changing CMO Brief (Russell Reynolds, 2024), CAG Moves co-contributor (bi-monthly), CMO Succession in Financial Services (RRA, 2023)",
        "Partner at Spencer Stuart before joining Russell Reynolds. Earlier career in brand management at a global FMCG.",
    ),
    (
        "Tristan Jervis", "Russell Reynolds",
        "Managing Director", "Technology & AI Practice / CMO", "Managing Director",
        0, "HIGH",
        "Tech-native and AI-adjacent CMO mandates. Also serves as UK Managing Director.",
        "Marketing Society Annual Conference — Tristan Jervis is a regular keynote or panellist on AI and the future of the CMO brief. Cite the agentic-AI chapter of 'Rules Have Changed' as a shared frame of reference.",
        "https://www.linkedin.com/in/tristan-jervis-rra",
        "AI and the CMO Mandate (Russell Reynolds, 2025), The Agentic Enterprise (RRA, 2024)",
        "VP Marketing at a global enterprise software business before moving to search.",
    ),
    (
        "Laura Sanderson", "Russell Reynolds",
        "Partner", "Board Practice / NED Gateway", "Partner",
        1, "HIGH",
        "NED and board advisory mandates across FTSE and large-cap listed. Key NED gateway at RRA.",
        "'The New CEO' book by Roger Parry (which Sanderson contributed to) is a natural conversation opener — reference the board-oversight-of-CMO chapter and the growing demand for marketing-literate NEDs on FTSE boards.",
        "https://www.linkedin.com/in/laura-sanderson-rra",
        "The New CEO contributor (Profile Books, 2024), Board Diversity in FTSE 350 (RRA, 2024)",
        "Senior Partner at KPMG Advisory before joining Russell Reynolds board practice.",
    ),
    (
        "Agnes Greaves", "Russell Reynolds",
        "Partner", "CMO Practice / Technology", "Partner",
        0, "MEDIUM",
        "Technology CMO mandates, particularly in scale-up and enterprise software.",
        "Marketing Week Live conference — Agnes Greaves has spoken on CMO talent at enterprise tech firms. Reference shared interest in B2B SaaS marketing leadership.",
        "https://www.linkedin.com/in/agnes-greaves-rra",
        "Tech CMO Talent Report (Russell Reynolds, 2023)",
        "CMO at a UK-listed SaaS business before joining RRA.",
    ),
    # Egon Zehnder
    (
        "Miranda Pode", "Egon Zehnder",
        "Partner", "CMO Practice / Financial Services", "Partner",
        0, "HIGH",
        "FS CMO and CCO mandates in asset management, banking, and insurance.",
        "The Marketing Society Fellows community — Miranda Pode is a Fellow. Open with a note on FS CMO mandate scope evolution citing the 'Rules Have Changed' FS data chapter; request a 20-minute exchange on market context.",
        "https://www.linkedin.com/in/miranda-pode-ez",
        "CMO Tenure in Financial Services (Egon Zehnder, 2024)",
        "Head of Marketing at a global asset manager before joining Egon Zehnder.",
    ),
    (
        "Karoline Vinsrygg", "Egon Zehnder",
        "Partner", "Board Advisory Practice / NED Gateway", "Partner",
        1, "HIGH",
        "NED and board composition in FTSE and large-cap European listed. Key NED gateway at EZ.",
        "The 350 Club and Women on Boards UK networks — Karoline Vinsrygg actively participates in both. Approach via a shared connection in the Women on Boards community, referencing board-level demand for marketing-literate candidates.",
        "https://www.linkedin.com/in/karoline-vinsrygg-ez",
        "Marketing Leaders on Boards (Egon Zehnder, 2024), The 350 Club annual report contributor (2023)",
        "CFO and board advisory background at a European consulting firm before joining EZ.",
    ),
    (
        "Çağla Bekbölet", "Egon Zehnder",
        "Partner", "Board Consulting / NED", "Partner",
        1, "HIGH",
        "Board consulting and NED mandates with a particular focus on diversity and emerging-markets-listed companies.",
        "Women Corporate Directors (WCD) Foundation events — Çağla Bekbölet is a regular speaker. Approach via a WCD conference introduction or a note referencing shared interest in board diversity and marketing-leader progression to NED.",
        "https://www.linkedin.com/in/cagla-bekbolet-ez",
        "Board Diversity and the CMO Profile (Egon Zehnder, 2023)",
        "Corporate governance advisor and partner at a European law firm before joining Egon Zehnder board practice.",
    ),
    (
        "Sophie Hanson", "Egon Zehnder",
        "Partner", "CMO Practice / Consumer", "Partner",
        0, "MEDIUM",
        "Consumer goods, retail, and lifestyle CMO mandates across UK and Europe.",
        "Marketing Society annual event speaker network. Sophie Hanson has participated in consumer-CMO panels. Reference shared interest in CMO succession in premium consumer brands.",
        "https://www.linkedin.com/in/sophie-hanson-ez",
        "Consumer CMO Outlook (Egon Zehnder, 2023)",
        "Marketing Director at a global luxury goods group before moving to search.",
    ),
    # Korn Ferry
    (
        "Grant Duncan", "Korn Ferry",
        "Senior Partner", "CMO Practice UK & Europe", "Senior Partner",
        0, "HIGH",
        "Exec CMO mandates across all sectors; highest placement volume of any CMO partner in London. Single highest-priority contact in the ecosystem.",
        "Map the Marketing Society / IPA / RTS fellow network for a warm bridge — Grant Duncan is an IPA Fellow and Marketing Society member. The Modern Marketer report is a direct co-content angle: propose a data-contribution or interview contribution before making a relationship ask. Chicago Booth alumni connection if applicable.",
        "https://www.linkedin.com/in/grant-duncan-korn-ferry",
        "Modern Marketer (Korn Ferry, annual), CMO Pay and Incentives (KF Architect, 2024), The New CMO Brief (Korn Ferry, 2025)",
        "Group Marketing Director at a FTSE 100 conglomerate, then Partner at Spencer Stuart, before joining Korn Ferry.",
    ),
    (
        "Sonamara Jeffreys", "Korn Ferry",
        "Partner", "CMO Practice / Financial Services", "Partner",
        0, "HIGH",
        "FS CMO and CCO mandates in banking, insurance, and asset management.",
        "CFA Society UK and Investment Marketing Forum events — Sonamara Jeffreys is active in FS marketing circles. Approach via a note referencing FS CMO mandate scope data in 'Rules Have Changed'; cite the information-services and data-business chapters as relevant.",
        "https://www.linkedin.com/in/sonamara-jeffreys-kf",
        "Financial Services CMO Landscape (Korn Ferry, 2024), Modern Marketer — FS Edition (KF, 2023)",
        "CMO at a UK asset manager, then Regional Marketing Director at a global bank, before joining Korn Ferry.",
    ),
    (
        "Tim Manasseh", "Korn Ferry",
        "Partner", "CMO Practice / Consumer", "Partner",
        0, "MEDIUM",
        "Consumer goods, FMCG, and retail CMO mandates.",
        "Cannes Lions CMO Global Forum — Tim Manasseh attends annually and participates in content sessions. Approach on-site or cite a shared interest in the intersection of creativity and performance marketing data.",
        "https://www.linkedin.com/in/tim-manasseh-kf",
        "Modern Marketer — Consumer Edition (Korn Ferry, 2023)",
        "Marketing Director at a leading consumer goods group before joining Korn Ferry.",
    ),
    # Odgers Berndtson
    (
        "Mark Freebairn", "Odgers Berndtson",
        "Partner", "Board & NED Practice", "Partner",
        1, "HIGH",
        "NED and CFO/audit-committee gateway across FTSE 250 and listed financial services. Key NED gateway at Odgers.",
        "GlobalData plc and information-services sector board network — Mark Freebairn has placed NEDs across listed data and analytics businesses. Use GlobalData or similar information-services context to open: reference the board-level demand for analytically literate CMOs as an emerging NED profile.",
        "https://www.linkedin.com/in/mark-freebairn-odgers",
        "NED Market Report (Odgers Berndtson, annual), FTSE 250 Board Composition (Odgers, 2024)",
        "Partner at Heidrick & Struggles (board practice) before joining Odgers Berndtson.",
    ),
    (
        "Virginia Bottomley", "Odgers Berndtson",
        "Non-Executive Chair", "Board & NED Practice", "Non-Executive Chair",
        1, "MEDIUM",
        "Chair-level NED mandates and senior board advisory across FTSE and public-sector organisations.",
        "Senior Women in Business Network and House of Lords connections. Virginia Bottomley is Baroness Bottomley of Nettlestone — approach via a shared political or governance network, or via a written note referencing her published views on board composition and diversity.",
        "https://www.linkedin.com/in/virginia-bottomley-odgers",
        "Board Leadership in Regulated Industries (Odgers Berndtson, 2023)",
        "Secretary of State for Health; then Partner at KPMG Advisory; then joined Odgers board practice.",
    ),
    # TML Partners
    (
        "Simon Bassett", "TML Partners",
        "Managing Partner", "CMO Practice", "Managing Partner",
        0, "HIGH",
        "Exec CMO mandates across all sectors. Warm existing relationship. Publishes The CMO Report.",
        "Existing warm relationship. Advance via a concrete next step: propose contribution to the next edition of The CMO Report (interview, dataset, or co-authored chapter). 'Rules Have Changed' book provides a natural content partnership angle.",
        "https://www.linkedin.com/in/simon-bassett-tml",
        "The CMO Report (TML Partners, annual), CMO Tenure and Succession Benchmarks (TML, 2024)",
        "CMO at a global professional services firm, then co-founder of TML Partners.",
    ),
    (
        "Annabel Venner", "TML Partners",
        "Partner", "NED Practice / Marketing Board", "Partner",
        1, "MEDIUM",
        "NED appointments for senior marketing leaders. Book endorser and Marketing Society Fellow.",
        "Marketing Society Fellows peer network — Annabel Venner is an active Fellow and speaker. The 'Rules Have Changed' book is a direct endorsement ask: Venner has endorsed previous marketing leadership books. Open with a co-authored contribution to The CMO Report before progressing to the endorsement conversation.",
        "https://www.linkedin.com/in/annabel-venner-tml",
        "The CMO Report — NED Edition (TML Partners, 2024), Marketing Leaders on Boards (TML, 2023)",
        "Global CMO at Hiscox, then Non-Executive Director roles, then joined TML Partners NED practice.",
    ),
    # Grace Blue Partnership
    (
        "Jay Haines", "Grace Blue Partnership",
        "Partner", "CMO Practice / Agency-to-Brand & AI", "Partner",
        0, "MEDIUM",
        "Agency-CMO and AI-native marketing leader mandates; crossover between marketing services and corporate CMO.",
        "Campaign magazine and The Drum senior executive networks — Jay Haines is a regular contributor and panellist. Reference the AI-and-marketing-leadership chapter of 'Rules Have Changed' as a conversation anchor.",
        "https://www.linkedin.com/in/jay-haines-grace-blue",
        "AI and the Agency CMO (Grace Blue, 2024), Agency-to-Corporate: The CMO Crossover (Campaign, 2023)",
        "Founding partner of Sinecure (now merged with Grace Blue). Earlier career in advertising and brand consulting.",
    ),
    (
        "Sarah Skinner", "Grace Blue Partnership",
        "Partner", "CMO Practice / Brand Transformation", "Partner",
        0, "MEDIUM",
        "Brand transformation and purpose-led CMO mandates in UK and Europe.",
        "Marketing Week and Contagious magazine editor/contributor networks. Sarah Skinner has featured in Marketing Week's Most Effective CMO lists — cite shared interest in measuring marketing effectiveness as an entry angle.",
        "https://www.linkedin.com/in/sarah-skinner-grace-blue",
        "Brand Transformation and CMO Mandate Scope (Grace Blue, 2024)",
        "CMO at a global FMCG brand, then consulting, then joined Grace Blue.",
    ),
    # MBS Group
    (
        "Elliott Goldstein", "MBS Group",
        "Partner", "CMO Practice / Consumer & NED", "Partner",
        0, "MEDIUM",
        "Consumer, retail, and digital-commerce CMO mandates. Occasional NED introductions.",
        "Retail Week and IGD senior executive events. Elliott Goldstein is active in consumer and retail circles. Use a shared interest in digital-commerce CMO mandate evolution as an entry point.",
        "https://www.linkedin.com/in/elliott-goldstein-mbs",
        "Consumer CMO Trends (MBS Group, 2024)",
        "Senior Partner at Korn Ferry (consumer practice) before joining MBS Group.",
    ),
    (
        "Moira Benigson", "MBS Group",
        "Managing Partner", "Board & NED Practice", "Managing Partner",
        1, "MEDIUM",
        "Board-level and NED mandates, particularly in premium consumer and media. Senior firm relationship.",
        "WACL (Women in Advertising & Communications Leadership) annual conference — Moira Benigson is a long-standing WACL member and sponsor. Approach via the WACL network or a note referencing shared interest in senior marketing leader board progression.",
        "https://www.linkedin.com/in/moira-benigson-mbs",
        "The Value of Marketing Leadership on Boards (MBS Group, 2023)",
        "Co-founder of MBS Group. Earlier career in luxury fashion and consumer retail.",
    ),
    # Erevena
    (
        "Flo Bown", "Erevena",
        "Partner", "CMO Practice / Technology & Scale-up", "Partner",
        0, "MEDIUM",
        "Tech-native and AI-adjacent CMO mandates at scale-up and Series B–IPO stage.",
        "Silicon Valley Bank and Molten Ventures ecosystem events — Flo Bown is active in the VC-backed scale-up community. Reference the 'Rules Have Changed' startup-to-enterprise CMO chapter as a shared frame.",
        "https://www.linkedin.com/in/flo-bown-erevena",
        "Scale-up CMO: From Traction to Exit (Erevena, 2024)",
        "CMO at a Series D SaaS business before joining Erevena.",
    ),
    # Sapphire Partners
    (
        "Kate Grussing CBE", "Sapphire Partners",
        "Founder and Managing Director", "NED Practice / FTSE Diversity", "Founder and MD",
        1, "MEDIUM",
        "FTSE NED and board diversity mandates. Specialist in placing marketing leaders into NED roles.",
        "FTSE Women Leaders Review and FTSE 350 diversity networks — Kate Grussing CBE chairs or contributes to diversity-in-leadership forums. Approach via a note on the marketing-leader-to-NED pathway, citing 'Rules Have Changed' board chapter and requesting a brief exchange.",
        "https://www.linkedin.com/in/kate-grussing-sapphire",
        "FTSE NED Diversity Report (Sapphire Partners, annual), Marketing Leaders and Board Roles (Sapphire, 2024)",
        "Partner at Spencer Stuart (board practice), then founded Sapphire Partners.",
    ),
]

# ---------------------------------------------------------------------------
# Notes (warm intro + thought leadership, one per partner)
# ---------------------------------------------------------------------------

SEED_NOTE_SENTINEL = "[headhunter-seed-v1]"


# ---------------------------------------------------------------------------
# Engagement calendar entries
# ---------------------------------------------------------------------------

# Each entry: (track, day_offset_or_week_tuple, title, description, firm_name, partner_name_or_None)
# Use ('week', n) for week-based offsets, ('day', n) for day offsets.

CALENDAR_ENTRIES = [
    # --- Track 1: RRA / TML (0–90 days) ---
    ("track-1", ("week", 1),
     "Research Greg Hodge — recent publications and LinkedIn activity",
     "Map Greg Hodge's recent articles, podcast appearances, CAG Moves contributions, and LinkedIn posts. Identify specific content angles that overlap with 'Rules Have Changed' thesis.",
     "Russell Reynolds", "Greg Hodge"),
    ("track-1", ("week", 2),
     "Draft outreach to Greg Hodge — Chicago Booth alumni + content angle",
     "Draft a personalised note referencing the Chicago Booth alumni connection and the CMO mandate scope evolution argument in 'Rules Have Changed'. Offer to share data or a pre-publication chapter relevant to his CMO Barometer work.",
     "Russell Reynolds", "Greg Hodge"),
    ("track-1", ("week", 4),
     "Send outreach to Greg Hodge",
     "Send the drafted note via LinkedIn message or direct email. Target a 20-minute call.",
     "Russell Reynolds", "Greg Hodge"),
    ("track-1", ("week", 6),
     "Simon Bassett (TML) — The CMO Report next-edition collaboration",
     "Approach Simon Bassett with a concrete proposal for The CMO Report next edition: offer a data contribution, co-authored section, or interview slot. Advance the existing warm relationship into a published collaboration.",
     "TML Partners", "Simon Bassett"),
    ("track-1", ("week", 8),
     "Annabel Venner (TML) — Marketing Society Fellows + book endorsement",
     "Request a conversation with Annabel Venner via the Marketing Society Fellows network. Bring a draft foreword or endorsement request for 'Rules Have Changed'. Co-content angle: CMO Report NED edition contribution.",
     "TML Partners", "Annabel Venner"),
    ("track-1", ("week", 10),
     "Follow-up with RRA — confirm relationship status",
     "Review response from Greg Hodge outreach. If no reply, send one follow-up note. Assess whether to escalate to Tristan Jervis in parallel.",
     "Russell Reynolds", None),

    # --- Track 2: Heidrick & Struggles (0–90 days) ---
    ("track-2", ("week", 2),
     "Research Richard Sumner — Heidrick Leadership Podcast episode history",
     "Listen to or read transcripts of at least three Heidrick Leadership Podcast episodes hosted or featuring Richard Sumner. Identify specific arguments to reference in the pitch.",
     "Heidrick & Struggles", "Richard Sumner"),
    ("track-2", ("week", 4),
     "Draft pitch — Heidrick Leadership Podcast guest slot",
     "Draft a one-page pitch for a podcast guest slot. Hook: the agentic-AI-and-CMO-mandate-scope thesis from 'Rules Have Changed'. Offer exclusive pre-publication data on CMO brief evolution relevant to the CMO Barometer.",
     "Heidrick & Struggles", "Richard Sumner"),
    ("track-2", ("week", 6),
     "Send podcast pitch to Richard Sumner",
     "Send the podcast pitch note to Richard Sumner via LinkedIn or direct email. Keep to two paragraphs; attach a one-page summary of the book thesis.",
     "Heidrick & Struggles", "Richard Sumner"),
    ("track-2", ("week", 10),
     "Kit Bingham — EPOC Network 'Meet the Headhunters' event",
     "Register for or request an invitation to the next EPOC Network 'Meet the Headhunters' event. Attend as a prospective NED candidate; use the session to establish a direct relationship with Kit Bingham.",
     "Heidrick & Struggles", "Kit Bingham"),
    ("track-2", ("week", 12),
     "Follow-up Heidrick — confirm Sumner and Bingham relationship status",
     "Review response from Richard Sumner podcast pitch. Chase if no reply. Separately confirm whether the EPOC event established a direct Bingham relationship.",
     "Heidrick & Struggles", None),

    # --- Track 3: Spencer Stuart (90–180 days) ---
    ("track-3", ("day", 90),
     "Research Emanuela Aureli — AESC activity and CMO Tenure Study commentary",
     "Review Emanuela Aureli's published commentary on CMO Tenure Study TMT data and any AESC Women's Leadership Forum contributions. Identify a specific data point or finding to reference in outreach.",
     "Spencer Stuart", "Emanuela Aureli"),
    ("track-3", ("day", 100),
     "Draft outreach to Emanuela Aureli — AESC route + TMT/information-services angle",
     "Draft a personalised note citing the CMO Tenure Study TMT sub-dataset and how 'Rules Have Changed' intersects with the information-services CMO mandate. Propose a brief exchange on market context.",
     "Spencer Stuart", "Emanuela Aureli"),
    ("track-3", ("day", 110),
     "Send outreach to Aureli; copy Jonathan Harper if appropriate",
     "Send the drafted note. If a warm connection to Jonathan Harper exists by this stage, copy him briefly. Target a 30-minute call.",
     "Spencer Stuart", "Emanuela Aureli"),
    ("track-3", ("day", 130),
     "Follow-up Aureli — request 30-min conversation",
     "Send one follow-up note if no response. Offer a specific time slot. Separately assess whether to open a parallel direct outreach to Jonathan Harper.",
     "Spencer Stuart", None),

    # --- Track 4: Korn Ferry / Grant Duncan (90–180 days) ---
    ("track-4", ("day", 90),
     "Map Grant Duncan's Marketing Society / IPA / RTS network — find warm bridge",
     "Identify a first- or second-degree connection in the Marketing Society Fellows, IPA, or RTS networks who has a direct relationship with Grant Duncan. Document the warmest potential bridge.",
     "Korn Ferry", "Grant Duncan"),
    ("track-4", ("day", 100),
     "Draft approach to Grant Duncan — Modern Marketer co-content angle",
     "Draft a note proposing a data contribution or co-authored section for the Modern Marketer annual report. Reference 'Rules Have Changed' data on CMO mandate scope as complementary to the Modern Marketer dataset.",
     "Korn Ferry", "Grant Duncan"),
    ("track-4", ("day", 120),
     "Send to Grant Duncan — warm intro if identified, direct if not",
     "Send the approach via the warm bridge identified at day 90, or direct via LinkedIn if no bridge found. Attach a one-page data summary.",
     "Korn Ferry", "Grant Duncan"),
    ("track-4", ("day", 150),
     "Follow-up Grant Duncan — progress to substantive conversation",
     "Follow up with one note. If no reply, escalate to Sonamara Jeffreys as a parallel FS-specific entry point.",
     "Korn Ferry", None),

    # --- Track 5: NED portfolio (180–270 days) ---
    ("track-5", ("day", 180),
     "Karoline Vinsrygg (EZ) — The 350 Club / Women on Boards route",
     "Approach Karoline Vinsrygg via the 350 Club or Women on Boards UK networks. Frame the conversation around board demand for marketing-literate candidates with operating CMO experience.",
     "Egon Zehnder", "Karoline Vinsrygg"),
    ("track-5", ("day", 195),
     "Kit Bingham (H&S) — EPOC Network follow-up; NED portfolio conversation",
     "Follow up the EPOC event relationship (Track 2, week 10) with a more substantive conversation about NED mandate pipeline. Reference any progress on the H&S podcast relationship as a trust signal.",
     "Heidrick & Struggles", "Kit Bingham"),
    ("track-5", ("day", 210),
     "Laura Sanderson (RRA) — 'The New CEO' book overlap; board advisory angle",
     "Approach Laura Sanderson referencing 'The New CEO' book she contributed to and the overlap with 'Rules Have Changed' on CMO-to-board transitions. Request a conversation about board advisory positioning.",
     "Russell Reynolds", "Laura Sanderson"),
    ("track-5", ("day", 225),
     "Mark Freebairn (Odgers) — GlobalData plc sector bridge; NED conversation",
     "Use the information-services and data-analytics sector as a bridging context. Mark Freebairn has placed NEDs at listed data businesses; cite GlobalData or similar as a sector anchor.",
     "Odgers Berndtson", "Mark Freebairn"),
    ("track-5", ("day", 270),
     "Kate Grussing CBE (Sapphire) — FTSE NED diversity route",
     "Approach Kate Grussing CBE via the FTSE Women Leaders Review network or a written note citing the marketing-leader-to-NED pathway data in 'Rules Have Changed'. Request a brief assessment conversation.",
     "Sapphire Partners", "Kate Grussing CBE"),

    # --- Track 6: Book v2 content partnerships (180–360 days) ---
    ("track-6", ("day", 180),
     "Identify co-content opportunities across five reports",
     "Map co-content angles for: CMO Barometer (H&S), CMO Tenure Study (Spencer Stuart), CAG Moves (RRA), Modern Marketer (KF), The CMO Report (TML). Prioritise two for active proposals by day 200.",
     None, None),
    ("track-6", ("day", 200),
     "Draft co-content proposals for two priority content partners",
     "Draft formal one-page proposals for the two highest-priority co-content partnerships identified at day 180. Lead with data contribution, offer co-authorship or foreword.",
     None, None),
    ("track-6", ("day", 240),
     "Cannes Lions — CMO Global Forum (22–26 June 2026)",
     "Attend Cannes Lions CMO Global Forum. Map which search-firm partners are present. Target one-on-one meetings with Grant Duncan (KF), Richard Sumner (H&S), and Greg Hodge (RRA) if they attend.",
     None, None),
    ("track-6", ("day", 280),
     "Gartner Marketing Symposium London — CMO Circle (11–12 May 2026)",
     "Attend Gartner Marketing Symposium London. Participate in CMO Circle roundtable. Identify which search-firm partners are present and schedule breakout conversations.",
     None, None),
    ("track-6", ("day", 300),
     "Marketing Society Global Conference (7 May 2026) — confirm attendance",
     "Confirm attendance at the Marketing Society Global Conference. Use as a venue for Marketing Society Fellows peer engagement and for follow-up with Annabel Venner (TML) and Miranda Pode (EZ).",
     None, None),
    ("track-6", ("day", 360),
     "Festival of Marketing (14 October 2026) — Q4 anchor for book v2 momentum",
     "Attend Festival of Marketing as a speaker or session anchor for book v2 launch momentum. Confirm speaking slot or roundtable contribution by Q2. Co-present with a search-firm partner where possible.",
     None, None),
]


# ---------------------------------------------------------------------------
# Main seed function
# ---------------------------------------------------------------------------

def seed(conn: sqlite3.Connection, start: date) -> None:
    print(f"\nPlan start date: {start.isoformat()}")

    # --- Firms ---
    print("\n── Firms ──────────────────────────────────────────────────────────")
    firm_id_map: dict[str, int] = {}

    for (name, tier_col, region, market_tier, strategic_fit, ned_practice_strength,
         hq_address, sectors, cmo_depth, comp_transp, cand_rep, b2b_fs) in FIRMS:

        row = conn.execute("SELECT id FROM firms WHERE name = ?", (name,)).fetchone()

        if row:
            firm_id_map[name] = row[0]
            conn.execute(
                "UPDATE firms SET market_tier=?, strategic_fit=?, ned_practice_strength=?, "
                "hq_address=?, sectors=?, cmo_practice_depth=?, comp_transparency=?, "
                "candidate_reputation=?, b2b_fs_reputation=? WHERE id=?",
                (market_tier, strategic_fit, ned_practice_strength, hq_address, sectors,
                 cmo_depth, comp_transp, cand_rep, b2b_fs, row[0]),
            )
            print(f"  [updated] {name}")
        else:
            ulid = new_ulid()
            cur = conn.execute(
                "INSERT INTO firms (ulid, name, tier, region, relationship_state, "
                "market_tier, strategic_fit, ned_practice_strength, hq_address, sectors, "
                "cmo_practice_depth, comp_transparency, candidate_reputation, b2b_fs_reputation) "
                "VALUES (?, ?, ?, ?, 'cold', ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (ulid, name, tier_col, region, market_tier, strategic_fit,
                 ned_practice_strength, hq_address, sectors, cmo_depth,
                 comp_transp, cand_rep, b2b_fs),
            )
            firm_id_map[name] = cur.lastrowid
            _insert_audit(conn, "firm", cur.lastrowid, name)
            print(f"  [created] {name}")

    # --- Partners ---
    print("\n── Partners ───────────────────────────────────────────────────────")
    partner_id_map: dict[str, int] = {}  # name → id

    for (pname, firm_name, title, practice, seniority, ned_gw,
         strategic_rel, practice_focus, warm_intro, linkedin_url,
         thought_lead, prior_career) in PARTNERS:

        firm_id = firm_id_map.get(firm_name)
        if firm_id is None:
            print(f"  [skip]    {pname} — firm '{firm_name}' not found")
            continue

        row = conn.execute(
            "SELECT id FROM partners WHERE firm_id = ? AND name = ?",
            (firm_id, pname),
        ).fetchone()

        if row:
            partner_id_map[pname] = row[0]
            conn.execute(
                "UPDATE partners SET title=?, practice=?, seniority=?, linkedin_url=?, "
                "ned_gateway=?, strategic_relevance=?, practice_focus=?, "
                "warm_intro_angle=?, thought_leadership=?, prior_career=? WHERE id=?",
                (title, practice, seniority, linkedin_url, ned_gw, strategic_rel,
                 practice_focus, warm_intro, thought_lead, prior_career, row[0]),
            )
            print(f"  [updated] {pname} @ {firm_name}")
        else:
            ulid = new_ulid()
            cur = conn.execute(
                "INSERT INTO partners (ulid, firm_id, name, title, practice, seniority, "
                "linkedin_url, relationship_state, ned_gateway, strategic_relevance, "
                "practice_focus, warm_intro_angle, thought_leadership, prior_career) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, 'cold', ?, ?, ?, ?, ?, ?)",
                (ulid, firm_id, pname, title, practice, seniority, linkedin_url,
                 ned_gw, strategic_rel, practice_focus, warm_intro, thought_lead, prior_career),
            )
            partner_id_map[pname] = cur.lastrowid
            _insert_audit(conn, "partner", cur.lastrowid, pname)
            print(f"  [created] {pname} @ {firm_name}")

    # --- Notes (warm intro angle + thought leadership) ---
    print("\n── Notes ──────────────────────────────────────────────────────────")
    for (pname, firm_name, _title, _practice, _seniority, _ned_gw,
         _strategic_rel, _practice_focus, warm_intro, _linkedin_url,
         thought_lead, _prior_career) in PARTNERS:

        partner_id = partner_id_map.get(pname)
        if partner_id is None:
            continue
        if not warm_intro and not thought_lead:
            continue

        # Fetch partner ULID for notes.entity_id
        ulid_row = conn.execute("SELECT ulid FROM partners WHERE id = ?", (partner_id,)).fetchone()
        if not ulid_row:
            continue
        partner_ulid = ulid_row[0]

        # Idempotency: skip if a seed note already exists for this partner.
        existing = conn.execute(
            "SELECT id FROM notes WHERE entity_type='partner' AND entity_id=? "
            "AND body LIKE ?",
            (partner_ulid, f"{SEED_NOTE_SENTINEL}%"),
        ).fetchone()
        if existing:
            print(f"  [exists]  note for {pname}")
            continue

        body_parts = [SEED_NOTE_SENTINEL]
        if warm_intro:
            body_parts.append(f"\n**Warm intro angle:** {warm_intro}")
        if thought_lead:
            body_parts.append(f"\n**Thought leadership:** {thought_lead}")
        body = "\n".join(body_parts)

        note_ulid = new_ulid()
        cur = conn.execute(
            "INSERT INTO notes (ulid, entity_type, entity_id, body) VALUES (?, 'partner', ?, ?)",
            (note_ulid, partner_ulid, body),
        )
        _insert_audit(conn, "partner", partner_id, f"note:{pname}", action="note")
        print(f"  [created] note for {pname}")

    # --- Engagement calendar ---
    print("\n── Engagement calendar ────────────────────────────────────────────")
    for (track, offset_spec, title, description, cal_firm_name, cal_partner_name) in CALENDAR_ENTRIES:
        # Compute due_date
        offset_type, offset_val = offset_spec
        if offset_type == "week":
            due_date = _week(start, offset_val)
        else:
            due_date = _day(start, offset_val)

        # Idempotency: skip if entry with same title + track exists.
        existing = conn.execute(
            "SELECT id FROM engagement_calendar WHERE title = ? AND track = ?",
            (title, track),
        ).fetchone()
        if existing:
            print(f"  [exists]  [{track}] {title[:60]}")
            continue

        # Look up firm_id and partner_id (optional)
        cal_firm_id: int | None = firm_id_map.get(cal_firm_name) if cal_firm_name else None
        cal_partner_id: int | None = partner_id_map.get(cal_partner_name) if cal_partner_name else None

        cal_ulid = new_ulid()
        conn.execute(
            "INSERT INTO engagement_calendar "
            "(ulid, firm_id, partner_id, due_date, title, description, track) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (cal_ulid, cal_firm_id, cal_partner_id, due_date, title, description, track),
        )
        who = f"{cal_partner_name} @ {cal_firm_name}" if cal_partner_name else (cal_firm_name or "—")
        print(f"  [created] [{track}] {due_date} — {title[:55]} ({who})")


def main() -> int:
    plan_start_str = os.environ.get("PLAN_START_DATE", "")
    if plan_start_str:
        try:
            start = date.fromisoformat(plan_start_str)
        except ValueError:
            print(f"Invalid PLAN_START_DATE: {plan_start_str!r}. Must be YYYY-MM-DD.", file=sys.stderr)
            return 1
    else:
        start = date.today()
        print(f"PLAN_START_DATE not set; using today: {start.isoformat()}")

    init_db()
    conn = get_connection()
    conn.execute("BEGIN")
    try:
        seed(conn, start)
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()

    print("\n✓ Headhunter seed complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
